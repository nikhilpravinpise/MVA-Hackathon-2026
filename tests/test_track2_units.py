"""Unit tests for the Track 2 engine - pure functions, no network, no
fixtures needed.  Covers the scoring channels, tiering, Guney proximity
(determinism included), name normalisation, config loading and the
record/replay cache layer (transport monkeypatched).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.track2 import engine, httpcache, proximity, scoring, sources, t2config  # noqa: E402


# ------------------------------------------------------------- scoring ----
def test_channel_target_overlap():
    assert scoring.channel_target_overlap(["A", "B"], {"A"}) == 0.5
    assert scoring.channel_target_overlap(["A"], {"A"}) == 1.0
    assert scoring.channel_target_overlap([], {"A"}) == 0.0
    assert scoring.channel_target_overlap(["A"], set()) == 0.0


def test_channel_proximity_piecewise():
    assert scoring.channel_proximity(-3.0, -2.0, 0.0) == 1.0
    assert scoring.channel_proximity(0.5, -2.0, 0.0) == 0.0
    assert scoring.channel_proximity(-1.0, -2.0, 0.0) == 0.5
    assert scoring.channel_proximity(None, -2.0, 0.0) == 0.0


def test_channel_reversal_and_lit():
    assert scoring.channel_reversal(10.0, 20.0) == 0.5
    assert scoring.channel_reversal(99.0, 20.0) == 1.0
    assert scoring.channel_reversal(None, 20.0) == 0.0
    assert scoring.channel_literature(3) == 1.0
    assert scoring.channel_literature(1) == pytest.approx(1 / 3)
    assert scoring.channel_interactions(2) == 1.0
    assert scoring.channel_interactions(1) == 0.5


def test_score_is_weighted_sum_and_clamps():
    w = {"target_overlap": 0.5, "network_proximity": 0.5}
    ch = {"target_overlap": 1.0, "network_proximity": 0.0}
    assert scoring.score_candidate(ch, w) == 0.5
    # out-of-range channel values are clamped into [0,1]
    ch = {"target_overlap": 7.0, "network_proximity": -3.0}
    assert scoring.score_candidate(ch, w) == 0.5


def test_tiering():
    tiers = {"T1": 0.45, "T2": 0.25}
    ch2 = {"target_overlap": 0.9, "network_proximity": 0.2}
    assert scoring.tier(0.6, ch2, tiers, 2) == "T1"
    # T1 also requires >= t1_min_channels non-zero channels
    ch1 = {"target_overlap": 0.9}
    assert scoring.tier(0.6, ch1, tiers, 2) == "T2"
    assert scoring.tier(0.3, ch2, tiers, 2) == "T2"
    assert scoring.tier(0.1, ch2, tiers, 2) == "T3"


# ------------------------------------------------------------ proximity ---
def _edges(*pairs):
    return [{"a": a, "b": b, "score": 0.8} for a, b in pairs]


def test_closest_distance_small_graph():
    universe = {"BUB1B", "X", "Y", "Z", "FAR"}
    adj = proximity.adjacency(
        _edges(("X", "BUB1B"), ("Y", "X"), ("Z", "Y")), universe)
    index = proximity.DistanceIndex(adj, {"BUB1B"}, unreachable=6)
    assert index.to_module("BUB1B") == 0
    assert index.to_module("X") == 1
    assert index.to_module("Z") == 3
    assert index.to_module("FAR") == 6       # unreachable bound
    assert proximity.closest_distance(index, ["X", "Z"]) == 2.0


def test_proximity_zscore_is_deterministic():
    # ring graph: every node degree 2, module one node
    nodes = [f"G{i}" for i in range(12)]
    ed = _edges(*[(nodes[i], nodes[(i + 1) % 12]) for i in range(12)])
    adj = proximity.adjacency(ed, set(nodes))
    kw = dict(module={"G0"}, targets=["G1", "G2"], n_random=50,
              seed=42, unreachable=6)
    a = proximity.proximity_zscore(adj, **kw)
    b = proximity.proximity_zscore(adj, **kw)
    assert a == b                      # fixed seed -> identical result
    assert a["n_random"] == 50 and a["seed"] == 42
    assert a["distance"] == 1.5        # (1+2)/2 on the ring
    assert a["z"] < 0                  # nearer than random average


def test_build_universe_cap_deterministic():
    module = {"A"}
    partners = {"A": [f"N{i}" for i in range(100)]}
    u = proximity.build_universe(module, partners, cap=10)
    assert len(u) == 10
    assert u == proximity.build_universe(module, partners, cap=10)


# ------------------------------------------------------ name normalisation -
def test_drug_key_aliases_and_salts():
    assert engine._drug_key("Rapamycin", {"rapamycin": "sirolimus"}) == "sirolimus"
    assert engine._drug_key("Glyburide", {"glyburide": "glibenclamide"}) == "glibenclamide"
    assert engine._drug_key("Sirolimus Hydrochloride", {}) == "sirolimus"
    assert engine._norm("FK-506") == "fk506"


def test_code_name_regex():
    assert engine._CODE_NAME.match("CC-115")
    assert engine._CODE_NAME.match("AZD-8055")
    assert engine._CODE_NAME.match("PD-0325901")
    assert not engine._CODE_NAME.match("sirolimus")
    assert not engine._CODE_NAME.match("metformin")


# -------------------------------------------------------------- config ----
def test_config_loads_and_validates():
    cfg = t2config.load_config()
    for s in t2config.REQUIRED_SECTIONS:
        assert s in cfg
    assert cfg["case"]["disease_gene"] == "BUB1B"
    assert len(cfg["seed_genes"]) >= 15
    for g in cfg["seed_genes"]:
        assert g.get("justification"), f"{g['symbol']} missing justification"
        assert g.get("axis") in ("A", "B", "C"), g["symbol"]
    # benchmark truth is frozen in config
    genes = [c["gene"] for c in cfg["benchmark"]["cases"]]
    assert len(genes) >= 8 and len(set(genes)) == len(genes)
    for c in cfg["benchmark"]["cases"]:
        assert c["known_drugs"] and c["citations"]
        for cit in c["citations"]:
            assert cit["pmid"] and cit["title"] and cit["year"]


def test_config_missing_section_fails(tmp_path):
    bad = tmp_path / "bad.yaml"
    bad.write_text("case: {}\nseed_genes: []\n", encoding="utf-8")
    with pytest.raises(ValueError):
        t2config.load_config(bad)


# ------------------------------------------------------------- httpcache --
class _FakeHttp(httpcache.CachedHttp):
    """_fetch stubbed - no network at all."""

    def __init__(self, *a, script=None, **kw):
        super().__init__(*a, **kw)
        self.script = script or {}
        self.calls = []

    def _fetch(self, method, url, data, content_type):
        self.calls.append((method, url, data))
        if url in self.script:
            return self.script[url]
        return 200, '{"ok": true}'


def test_record_then_replay_roundtrip(tmp_path):
    url = "https://example.org/x.json"
    rec = _FakeHttp(cache_dir=tmp_path, mode="record",
                    script={url: (200, '{"v": 1}')})
    status, body = rec.get_json(url)
    assert status == 200 and body == {"v": 1}
    assert len(list(tmp_path.glob("*.json"))) == 1

    rep = _FakeHttp(cache_dir=tmp_path, mode="replay")
    status, body = rep.get_json(url)
    assert body == {"v": 1}
    assert rep.calls == []            # replay made zero transport calls


def test_replay_cache_miss_raises(tmp_path):
    rep = _FakeHttp(cache_dir=tmp_path, mode="replay")
    with pytest.raises(httpcache.CacheMiss):
        rep.get_json("https://nope.example/x")


def test_record_reuses_existing_entry(tmp_path):
    url = "https://example.org/y.json"
    rec = _FakeHttp(cache_dir=tmp_path, mode="record",
                    script={url: (200, '{"v": 1}')})
    rec.get_json(url)
    rec2 = _FakeHttp(cache_dir=tmp_path, mode="record",
                     script={url: (200, '{"v": 2}')})
    _, body = rec2.get_json(url)
    assert body == {"v": 1}           # existing entry wins - resumable


def test_trim_cache_shrinks(tmp_path):
    url = "https://api.fda.gov/drug/label.json?search=x"
    big = json.dumps({"results": [{
        "id": "x", "set_id": "s", "pediatric_use": ["T" * 900],
        "boxed_warning": ["b"], "meta": {"huge": "drop me"},
        "openfda": {"generic_name": ["D"], "spl_id": "zzz"}}]})
    rec = _FakeHttp(cache_dir=tmp_path, mode="record",
                    script={url: (200, big)})
    rec.get_json(url)
    rep = httpcache.trim_cache(tmp_path)
    assert rep["bytes_after"] < rep["bytes_before"]
    # replay still returns the same key, with trimmed content
    out = _FakeHttp(cache_dir=tmp_path, mode="replay").get_json(url)[1]
    r = out["results"][0]
    assert r["pediatric_use"][0] == "T" * 800    # clipped
    assert "meta" not in r and r["openfda"]["generic_name"] == ["D"]


# ------------------------------------------------ openFDA label matching --
class _Scripted:
    """get_json stub keyed on URL substrings - no network."""

    def __init__(self, script):
        self.script = script              # [(url_substring, (status, body))]
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        for pat, ret in self.script:
            if pat in url:
                return ret
        return 404, {"error": "no match"}


_MISS = (404, {"error": "no match"})
_ZITUVIMET = {"set_id": "z", "openfda": {
    "generic_name": ["SITAGLIPTIN AND METFORMIN HYDROCHLORIDE"],
    "substance_name": ["SITAGLIPTIN", "METFORMIN HYDROCHLORIDE"]}}
_METFORMIN = {"set_id": "m", "openfda": {
    "generic_name": ["METFORMIN HYDROCHLORIDE"],
    "substance_name": ["METFORMIN HYDROCHLORIDE"]}}


def test_openfda_name_variants():
    assert sources.openfda_name_variants("dasatinib anhydrous") == \
        ["dasatinib anhydrous", "dasatinib"]
    assert sources.openfda_name_variants("metformin hydrochloride") == \
        ["metformin hydrochloride", "metformin"]
    assert sources.openfda_name_variants("dextran sulfate sodium") == \
        ["dextran sulfate sodium", "dextran"]
    assert sources.openfda_name_variants("sodium chloride") == \
        ["sodium chloride"]          # leading word never stripped


def test_openfda_combo_detection_and_pick():
    assert sources.openfda_is_combo(_ZITUVIMET)
    assert not sources.openfda_is_combo(_METFORMIN)
    assert sources.openfda_pick_single(
        [_ZITUVIMET, _METFORMIN], "metformin") is _METFORMIN
    assert sources.openfda_pick_single([_ZITUVIMET], "metformin") is None
    # a single-ingredient label for a DIFFERENT drug is not a pick
    assert sources.openfda_pick_single(
        [{"openfda": {"substance_name": ["INSULIN LISPRO"]}}],
        "insulin glargine") is None


def test_openfda_label_variant_retry():
    """'dasatinib anhydrous' generic 404 -> 'dasatinib' variant hits."""
    lab = {"set_id": "S", "openfda": {"generic_name": ["DASATINIB"]}}
    http = _Scripted([
        ("brand_name", _MISS),
        ("%22DASATINIB%20ANHYDROUS%22", _MISS),
        ("%22DASATINIB%22", (200, {"results": [lab]})),
    ])
    label, meta = sources.openfda_label(http, "ep", "dasatinib anhydrous")
    assert label is lab
    assert meta["combo"] is False
    assert "on name variant 'dasatinib'" in meta["note"]


def test_openfda_label_prefers_single_ingredient_over_combo():
    """A combination first hit triggers the limit-5 refinement and the
    single-ingredient label covering the drug wins."""
    http = _Scripted([
        ("brand_name", _MISS),
        ("limit=5", (200, {"results": [_ZITUVIMET, _METFORMIN]})),
        ("%22METFORMIN%20HYDROCHLORIDE%22",
         (200, {"results": [_ZITUVIMET]})),
    ])
    label, meta = sources.openfda_label(http, "ep",
                                        "metformin hydrochloride")
    assert label is _METFORMIN
    assert meta["combo"] is False
    assert "single-ingredient label preferred" in meta["note"]


def test_openfda_label_keeps_combo_when_no_single():
    """No single-ingredient hit among the top hits -> keep the combo and
    flag it."""
    http = _Scripted([
        ("brand_name", _MISS),
        ("limit=5", (200, {"results": [_ZITUVIMET]})),
        ("%22METFORMIN%20HYDROCHLORIDE%22",
         (200, {"results": [_ZITUVIMET]})),
    ])
    label, meta = sources.openfda_label(http, "ep",
                                        "metformin hydrochloride")
    assert label is _ZITUVIMET
    assert meta["combo"] is True
    assert "combination label kept" in meta["note"]


def test_openfda_label_brand_fallback():
    """Generic miss on every variant -> brand_name hit is used."""
    lab = {"set_id": "B", "openfda": {"generic_name": ["D"]}}
    http = _Scripted([
        ("generic_name", _MISS),
        ("brand_name", (200, {"results": [lab]})),
    ])
    label, meta = sources.openfda_label(http, "ep", "dasatinib")
    assert label is lab and "brand_name" in meta["note"]


def test_openfda_label_no_hit():
    http = _Scripted([])
    label, meta = sources.openfda_label(http, "ep", "unicorn")
    assert label == {} and meta["status"] == "no_hit"


def test_resolve_chembl_merged_counter(monkeypatch):
    """A name resolving to a ChEMBL id already held by another candidate
    is union-merged into it and counted in stats['merged'] - the funnel
    term that closes collected = gate outcomes + unresolved + merged."""
    existing = {"chembl_id": "CHEMBL1", "names": {"aspirin"},
                "module_hits": set(), "dgidb_pmids": set(),
                "dgidb_sources": {"S"}, "dgidb_types": set(),
                "ot_stage": "", "hit_types": {}}
    merging = {"chembl_id": None, "names": {"acetylsalicylic acid"},
               "module_hits": {"BUB1B"}, "dgidb_pmids": {"PMID:1"},
               "dgidb_sources": {"S"}, "dgidb_types": {"inhibitor"},
               "ot_stage": "", "hit_types": {}}
    cand = {"CHEMBL1": existing, "name:acetylsalicylic acid": merging}
    monkeypatch.setattr(
        sources, "mychem_drugcentral",
        lambda http, ep, name: (
            {"chembl": {"molecule_chembl_id": "CHEMBL1"},
             "drugcentral": {}}, {}))
    cfg = {"endpoints": {"mychem": "e"},
           "collection": {"chembl_name_lookup": True}, "workers": 1}
    out, stats = engine.resolve_chembl(None, cfg, cand)
    assert stats["merged"] == 1
    assert out["CHEMBL1"]["names"] == {"aspirin", "acetylsalicylic acid"}
    assert out["CHEMBL1"]["module_hits"] == {"BUB1B"}
    assert "name:acetylsalicylic acid" not in out


# -------------------------------------------------- committed evidence ----
CANDIDATES = REPO / "docs" / "track2" / "evidence" / "candidates.json"
BENCHMARK = REPO / "docs" / "track2" / "evidence" / "benchmark.json"

REQ_TOP = {"schema", "generated_by", "config_sha", "seed_genes", "candidates"}
REQ_CAND = {"drug", "chembl_id", "drugcentral_id", "approval", "targets",
            "axis", "mechanism_of_action", "evidence", "score", "tier",
            "rationale_keys"}
REQ_APPR = {"max_phase", "fda", "ema", "first_approval",
            "pediatric_labeling", "evidence"}
REQ_EV = {"target_overlap", "network_proximity_z", "signature_reversal",
          "prism_aneuploidy", "literature"}


@pytest.mark.skipif(not CANDIDATES.exists(), reason="evidence not generated")
def test_candidates_json_schema():
    d = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    assert REQ_TOP <= d.keys()
    assert d["schema"] == "t2.candidates/1"
    assert d["candidates"], "no candidates"
    for c in d["candidates"]:
        assert REQ_CAND <= c.keys(), c["drug"]
        assert REQ_APPR <= c["approval"].keys(), c["drug"]
        assert REQ_EV <= c["evidence"].keys(), c["drug"]
        assert c["tier"] in ("T1", "T2", "T3")
        assert c["approval"]["max_phase"] == 4          # gate held
        assert c["approval"]["withdrawn"] is False
        assert isinstance(c["score"], (int, float))
        # contribution reporting: channels + rationale must be non-empty
        assert c["channels"] and c["rationale_keys"]


@pytest.mark.skipif(not BENCHMARK.exists(), reason="evidence not generated")
def test_benchmark_json_schema():
    d = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    assert d["schema"] == "t2.benchmark/1"
    assert len(d["cases"]) >= 8
    for c in d["cases"]:
        assert c["gene"] and c["known_drugs"]
        assert "rank_of_known" in c and "k" in c
    for k in ("recall_at_1", "recall_at_5", "recall_at_10"):
        assert 0.0 <= d[k] <= 1.0
