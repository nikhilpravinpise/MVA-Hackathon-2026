"""Replay-mode engine tests - fully network-free.

Replays the recorded fixtures under tests/fixtures/track2/engine/ and
checks (a) the engine reproduces the committed evidence JSON and
(b) two runs are byte-identical once timestamps are stripped
(determinism).  If fixtures are absent these tests skip - they are not
meant to hit the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.track2 import benchmark, engine, httpcache, t2config  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "track2" / "engine"
MVA_CACHE = FIX / "mva"
BENCH_CACHE = FIX / "benchmark"
CANDIDATES = REPO / "docs" / "track2" / "evidence" / "candidates.json"
BENCHMARK_JSON = REPO / "docs" / "track2" / "evidence" / "benchmark.json"


def _cfg():
    return t2config.load_config()


def _mva_case(cfg):
    return {
        "name": cfg["case"]["name"], "disease": cfg["case"]["disease"],
        "disease_gene": cfg["case"]["disease_gene"],
        "hpo_terms": cfg["case"].get("hpo_terms", []),
        "variants": cfg["case"].get("variants", []),
        "seed_genes": cfg["seed_genes"], "run_lincs": True,
    }


def _strip_volatile(d):
    d = json.loads(json.dumps(d))
    d.pop("generated_at", None)
    d.pop("config_sha", None)
    return d


fixtures_present = pytest.mark.skipif(
    not MVA_CACHE.exists() or not any(MVA_CACHE.glob("*.json")),
    reason="engine fixtures not recorded")


@fixtures_present
def test_mva_replay_is_deterministic():
    cfg = _cfg()
    r1 = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                              mode="replay"),
                         cfg, _mva_case(cfg))
    r2 = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                              mode="replay"),
                         cfg, _mva_case(cfg))
    assert _strip_volatile(r1) == _strip_volatile(r2)


# ---------------------------------------------------------------------------
# L11 regeneration delta (2026-10-13)
#
# The openFDA label-resolution hardening (single-ingredient preference,
# form-word name variants, pref_name-first lookup) plus the three-section
# pediatric classifier change the engine output vs the committed
# candidates.json, which L10 regenerates once both lanes land.  Until
# then replay and committed evidence legitimately differ on exactly the
# leaf fields below - the test asserts the delta is contained in this
# set, so an unexpected drift still fails.  After L10 regenerates the
# file the diff is empty and the assertions stay valid.
#
# drug -> (committed pediatric_flag, replay pediatric_flag)
_L11_FLAG_DIFFS = {
    "cyclophosphamide anhydrous": ("none", "labeled_pediatric_indication"),
    "cytarabine": ("pediatric_text_only", "labeled_pediatric_indication"),
    "dasatinib anhydrous": ("none", "labeled_pediatric_indication"),
    "daunorubicin": ("none", "labeled_pediatric_indication"),
    "daunorubicin hydrochloride": ("none", "labeled_pediatric_indication"),
    "metformin": ("none", "labeled_pediatric_indication"),
    "metformin hydrochloride": ("none", "labeled_pediatric_indication"),
    "methenamine": ("none", "labeled_pediatric_indication"),
    "methylprednisolone": ("labeled_pediatric_indication", "none"),
    "valproic acid": ("pediatric_text_only", "labeled_pediatric_indication"),
}

# drug -> (committed fda_set_id, replay fda_set_id)
_L11_SET_ID_DIFFS = {
    "apomorphine hydrochloride": ("444c1f4c-dd0c-4525-bb65-c0c211c9487f",
                                  "aedf70e4-1949-44bc-bf1b-0f282c4f0705"),
    "dasatinib anhydrous": (None, "02b04c6f-4ea5-4fcb-bf6d-2631d5ab31e4"),
    "glycerin": (None, "00071697-4ac6-4962-8eee-388b8b52bd40"),
    "metformin": ("0098dec4-f0e5-45d5-8aa4-5d0faf9ab142",
                  "011de1a5-1ac0-4831-9e8d-26ec79ba2205"),
    "metformin hydrochloride": ("0098dec4-f0e5-45d5-8aa4-5d0faf9ab142",
                                "011de1a5-1ac0-4831-9e8d-26ec79ba2205"),
    "methenamine": ("02af5576-d75c-4553-9431-9c482997c8bb",
                    "131a1322-0182-7a4e-e063-6394a90accbf"),
    "methylprednisolone": ("01ca16de-ab2e-4e19-e063-6394a90a0510",
                           "01f0126c-da22-4ac0-8755-3bc589602e6a"),
    "mycophenolic acid": ("0f1704e2-a66a-4be5-8127-ebb5947c7b64",
                          "26b31126-4262-4a15-8a16-234c86763176"),
    "niraparib": ("8245a990-3268-4613-b5c5-9537858a1eb9",
                  "b7f675e2-159c-490c-b6f4-3f16d9492b7d"),
    "octocrylene": ("0200a00f-2b57-454d-933d-a7d48644be6e",
                    "00280745-908b-468f-e063-6294a90aa12f"),
    "paclitaxel": ("135502ff-002c-4a29-ba93-60855cf44f31",
                   "0c12c77c-5fd4-48dc-a318-e96892233992"),
}

# drug -> other leaf fields allowed to differ (set_id/flag handled above)
_L11_OTHER_DIFFS = {
    "glycerin": {"approval.evidence"},
    "dasatinib anhydrous": {"approval.evidence"},
    "metformin": {"pediatric_labeling", "approval.pediatric_labeling"},
    "metformin hydrochloride": {"pediatric_labeling",
                                "approval.pediatric_labeling"},
    "mycophenolic acid": {"pediatric_labeling",
                          "approval.pediatric_labeling"},
    "niraparib": {"pediatric_labeling", "approval.pediatric_labeling"},
    "apomorphine hydrochloride": {"pediatric_labeling",
                                  "approval.pediatric_labeling"},
    "paclitaxel": {"pediatric_labeling", "approval.pediatric_labeling"},
    "methylprednisolone": {"pediatric_labeling",
                           "approval.pediatric_labeling",
                           "warnings.black_box", "warnings.openfda_boxed"},
}

def _norm_cand(c):
    """Candidate dict minus the L11-added approval fields and flag
    evidence; fda_set_id stays (it predates L11 at top level)."""
    c = dict(c)
    c.pop("pediatric_flag_evidence", None)
    ap = dict(c.get("approval") or {})
    for k in ("fda_set_id", "combination_label", "openfda_match"):
        ap.pop(k, None)
    c["approval"] = ap
    return c


def _leaf_diffs(a, b, prefix=""):
    """Flattened old->new diffs between two JSON-ish trees."""
    out = {}
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out.update(_leaf_diffs(a.get(k, "<absent>"),
                                   b.get(k, "<absent>"),
                                   f"{prefix}.{k}" if prefix else k))
    elif isinstance(a, list) and isinstance(b, list):
        for i in range(max(len(a), len(b))):
            x = a[i] if i < len(a) else "<absent>"
            y = b[i] if i < len(b) else "<absent>"
            out.update(_leaf_diffs(x, y, f"{prefix}[{i}]"))
    elif a != b:
        out[prefix] = (a, b)
    return out


@fixtures_present
@pytest.mark.skipif(not CANDIDATES.exists(), reason="evidence not generated")
def test_mva_replay_matches_committed_evidence():
    cfg = _cfg()
    r = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                             mode="replay"),
                        cfg, _mva_case(cfg))
    committed = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    new, old = _strip_volatile(r), _strip_volatile(committed)
    # committed evidence predates L11 until L10 regenerates it; the
    # funnel.merged key is the marker that tells the two generations apart
    stale = "merged" not in (old.get("funnel") or {})
    for section in ("candidates", "excluded_mechanism_opposed"):
        old_by = {c["drug"]: _norm_cand(c) for c in old[section]}
        new_by = {c["drug"]: _norm_cand(c) for c in new[section]}
        assert set(old_by) == set(new_by)
        for drug in old_by:
            diffs = _leaf_diffs(old_by[drug], new_by[drug])
            if not stale:
                assert not diffs, f"{drug}: {diffs}"
                continue
            paths = {p.split("[")[0] for p in diffs}
            allowed = (_L11_OTHER_DIFFS.get(drug, set())
                       | {"pediatric_flag", "fda_set_id"})
            assert paths <= allowed, f"{drug}: unexpected diffs " \
                f"{sorted(paths - allowed)}"
            flag = diffs.get("pediatric_flag")
            if flag is not None:
                assert _L11_FLAG_DIFFS.get(drug) == flag, \
                    f"{drug} flag diff {flag} not the L11-pinned value"
            sid = diffs.get("fda_set_id")
            if sid is not None:
                assert _L11_SET_ID_DIFFS.get(drug) == sid, \
                    f"{drug} set_id diff {sid} not the L11-pinned value"
        if stale:
            changed = {d for d in old_by
                       if _leaf_diffs(old_by[d], new_by[d])}
            for drug in _L11_FLAG_DIFFS:
                if drug in old_by:
                    assert drug in changed, \
                        f"expected flag diff for {drug} did not occur"
    # funnel: the only added key is `merged`, which must close the counts
    fun_new, fun_old = dict(new["funnel"]), dict(old["funnel"])
    merged = fun_new.pop("merged")
    assert fun_new == fun_old
    tot = sum(fun_new[k] for k in (
        "gated_in", "gated_out_no_chembl", "gated_out_phase",
        "gated_out_withdrawn", "gated_out_unresolved")) + merged
    assert fun_new["collected"] - fun_new["dropped_over_cap"] == tot


bench_fixtures = pytest.mark.skipif(
    not BENCH_CACHE.exists() or not any(BENCH_CACHE.glob("*.json")),
    reason="benchmark fixtures not recorded")


@bench_fixtures
def test_benchmark_replay_runs_and_recovers():
    cfg = _cfg()
    out = benchmark.run_benchmark(
        httpcache.CachedHttp(cache_dir=BENCH_CACHE, mode="replay"), cfg)
    assert out["n_cases"] == len(cfg["benchmark"]["cases"])
    assert 0.0 <= out["recall_at_10"] <= 1.0
    # the best-documented positive control must be recovered
    tsc2 = next(c for c in out["cases"] if c["gene"] == "TSC2")
    ranks = [k["rank"] for k in tsc2["known_drugs"] if k["found"]]
    assert ranks and min(ranks) <= 10


@bench_fixtures
@pytest.mark.skipif(not BENCHMARK_JSON.exists(),
                    reason="evidence not generated")
def test_benchmark_replay_matches_committed_evidence():
    cfg = _cfg()
    out = benchmark.run_benchmark(
        httpcache.CachedHttp(cache_dir=BENCH_CACHE, mode="replay"), cfg)
    committed = json.loads(BENCHMARK_JSON.read_text(encoding="utf-8"))
    out, old = _strip_volatile(out), _strip_volatile(committed)
    # L11: the only legitimate delta vs stale evidence is the new
    # funnel.merged counter per case; it must close the case arithmetic.
    for case in out["cases"]:
        f = case["funnel"]
        merged = f.pop("merged", None)
        tot = sum(f[k] for k in (
            "gated_in", "gated_out_no_chembl", "gated_out_phase",
            "gated_out_withdrawn", "gated_out_unresolved"))
        assert f["collected"] - f["dropped_over_cap"] == tot + merged
    for case in committed["cases"]:
        case["funnel"].pop("merged", None)
    assert out == old
