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

# ---------------------------------------------------------------------------
# L15 regeneration delta (2026-10-13, redteam2 r4/n3)
#
# The pediatric-flag hardening - a fourth flag value "unknown" for labels
# carrying no pediatric evidence either way, the _exists_:pediatric_use
# deep-scan refinement, token-exact active matching, and the word-boundary
# clip on quoted evidence - changes the engine output vs the committed
# candidates.json, which the lead regenerates once after these lanes land.
# Until then the tables below pin every legitimate leaf difference so an
# unexpected drift still fails.  A committed file carrying an L15 marker
# (an "unknown" flag or a deep-scan match note) compares strictly.
#
# drug -> (committed pediatric_flag, replay pediatric_flag)
_L15_FLAG_DIFFS = {
    "acetaminophen": ("none", "labeled_pediatric_indication"),
    "clotrimazole": ("none", "labeled_pediatric_indication"),
    "methylprednisolone": ("none", "labeled_pediatric_indication"),
    "cyclosporine": ("none", "pediatric_text_only"),
    "octocrylene": ("none", "pediatric_text_only"),
    "abemaciclib": ("none", "unknown"),
    "amsacrine": ("none", "unknown"),
    "cinnarizine": ("none", "unknown"),
    "copanlisib": ("none", "unknown"),
    "dicumarol": ("none", "unknown"),
    "flutamide": ("none", "unknown"),
    "glycerin": ("none", "unknown"),
    "omacetaxine mepesuccinate": ("none", "unknown"),
    "panobinostat": ("none", "unknown"),
    "phenylbutanoic acid": ("none", "unknown"),
    "pixantrone": ("none", "unknown"),
    "teniposide": ("none", "unknown"),
    "zanubrutinib": ("none", "unknown"),
}

# drug -> (committed fda_set_id, replay fda_set_id) - deep-scan re-picks;
# the flag pair above is pinned separately
_L15_SET_ID_DIFFS = {
    "acetaminophen": ("0005aafa-08f8-4990-a54d-cc097195708f",
                      "0f67c1bd-915b-4681-88dd-22f5154a80b3"),
    "clotrimazole": ("0052992a-819c-4c55-bd88-201a09a3573a",
                     "116be3a8-9a57-4b4a-a873-98a4ce83bcf7"),
    "cyclosporine": ("0a60fccf-7e1b-44fe-e063-6394a90aadd5",
                     "5e5926a7-1de0-4b54-a5c0-286b6200ff82"),
    "etoposide phosphate": ("7499fc35-fae8-44ad-bbab-9a1a589bf3ee",
                            "0dddbe44-b4f4-431f-9011-8a54abbd4cbf"),
    "methylprednisolone": ("01f0126c-da22-4ac0-8755-3bc589602e6a",
                           "1084208f-3b86-4aef-8247-5b6ed6cd50c7"),
    "mitoxantrone": ("1634528a-30c5-4309-acc8-4c0293ae14ae",
                     "accf9569-4b57-4e83-a7db-4e890a75d1ba"),
    "mitoxantrone hydrochloride": ("1634528a-30c5-4309-acc8-4c0293ae14ae",
                                   "accf9569-4b57-4e83-a7db-4e890a75d1ba"),
    "nicotine": ("003b863c-06b0-715d-ccc2-b7da4deac621",
                 "acb7d02d-249b-4645-ac1b-8ff9a56dd244"),
    "valrubicin": ("8739ae02-e4c5-0fa2-e053-2a91aa0a1b74",
                   "e96f30a0-6662-11de-8f80-0002a5d5c51b"),
}

# drugs whose pediatric_flag_evidence.text differs only via the L15
# word-boundary clip (n3) - same winning sentence, cleaner cut
_L15_EVIDENCE_CLIP = {
    "alpelisib", "cyclophosphamide anhydrous", "dabrafenib",
    "daunorubicin", "daunorubicin hydrochloride", "everolimus",
    "levothyroxine", "lonafarnib", "methotrexate", "mycophenolic acid",
    "pentetic acid", "trametinib",
}

# label-derived leaf paths that may legitimately move when a label is
# re-picked (always alongside a pinned flag/set_id diff or a clip drug)
_L15_LABEL_PATHS = {
    "pediatric_labeling", "approval.pediatric_labeling",
    "pediatric_flag_evidence", "pediatric_flag_evidence.text",
    "pediatric_flag_evidence.section",
    "approval.openfda_match", "approval.combination_label",
    "approval.evidence", "warnings.black_box", "warnings.openfda_boxed",
}


def _l15_marked(d):
    """Committed evidence carries an L15 signature (an 'unknown' flag or
    a deep-scan match note) -> it was generated by the hardened engine
    and must compare strictly."""
    for sec in ("candidates", "excluded_mechanism_opposed"):
        for c in d.get(sec, []):
            if c.get("pediatric_flag") == "unknown":
                return True
            if "_exists_:pediatric_use" in (
                    (c.get("approval") or {}).get("openfda_match") or ""):
                return True
    return False

def _norm_cand(c):
    """Candidate dict minus the L11-added approval fields and flag
    evidence; fda_set_id stays (it predates L11 at top level).

    Used ONLY inside the stale-evidence branch (committed file lacking
    funnel.merged).  On the strict path nothing is normalised away:
    every field a reader can audit - pediatric_flag_evidence,
    approval.fda_set_id, combination_label, openfda_match - is
    compared verbatim (redteam2 r3).
    """
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
    stale_l11 = "merged" not in (old.get("funnel") or {})
    # committed evidence predates L15 until the lead regenerates after
    # the pediatric-flag hardening; an 'unknown' flag or a deep-scan
    # match note marks the L15 generation (redteam2 r3/r4)
    stale_l15 = not _l15_marked(old)
    for section in ("candidates", "excluded_mechanism_opposed"):
        old_by = {c["drug"]: c for c in old[section]}
        new_by = {c["drug"]: c for c in new[section]}
        assert set(old_by) == set(new_by)
        for drug in old_by:
            a, b = old_by[drug], new_by[drug]
            if stale_l11:
                a, b = _norm_cand(a), _norm_cand(b)
            diffs = _leaf_diffs(a, b)
            if not (stale_l11 or stale_l15):
                assert not diffs, f"{drug}: {diffs}"
                continue
            paths = {p.split("[")[0] for p in diffs}
            if stale_l11:
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
            else:
                # stale_l15: the L15 deltas are pinned exactly - flags
                # and set_ids as (committed, replay) pairs, and any
                # other label-derived leaf may move only for a drug
                # whose pinned diff exists
                structural = paths - _L15_LABEL_PATHS - {
                    "pediatric_flag", "fda_set_id", "approval.fda_set_id"}
                assert not structural, f"{drug}: unexpected diffs " \
                    f"{sorted(structural)}"
                flag = diffs.get("pediatric_flag")
                if flag is not None:
                    assert _L15_FLAG_DIFFS.get(drug) == flag, \
                        f"{drug} flag diff {flag} not the L15-pinned value"
                for sp in ("fda_set_id", "approval.fda_set_id"):
                    sid = diffs.get(sp)
                    if sid is not None:
                        assert _L15_SET_ID_DIFFS.get(drug) == sid, \
                            f"{drug} {sp} diff {sid} not the L15-pinned value"
                label_paths = paths & _L15_LABEL_PATHS
                if label_paths:
                    pinned = (drug in _L15_FLAG_DIFFS
                              or drug in _L15_SET_ID_DIFFS
                              or drug in _L15_EVIDENCE_CLIP)
                    assert pinned, \
                        f"{drug}: label-field diffs without a pinned " \
                        f"flag/set_id/clip diff: {sorted(label_paths)}"
                    if drug in _L15_EVIDENCE_CLIP \
                            and drug not in _L15_FLAG_DIFFS \
                            and drug not in _L15_SET_ID_DIFFS:
                        assert label_paths == {
                            "pediatric_flag_evidence.text"}, \
                            f"{drug}: clip-only drug must not gain " \
                            f"other label diffs: {sorted(label_paths)}"
        if stale_l15:
            changed = {d for d in old_by
                       if _leaf_diffs(old_by[d], new_by[d])}
            for drug in (set(_L15_FLAG_DIFFS) | set(_L15_SET_ID_DIFFS)
                         | _L15_EVIDENCE_CLIP):
                if drug in old_by:
                    assert drug in changed, \
                        f"expected L15 diff for {drug} did not occur"
        elif stale_l11:
            changed = {d for d in old_by
                       if _leaf_diffs(_norm_cand(old_by[d]),
                                      _norm_cand(new_by[d]))}
            for drug in _L11_FLAG_DIFFS:
                if drug in old_by:
                    assert drug in changed, \
                        f"expected flag diff for {drug} did not occur"
    # every other top-level block is compared too (redteam2 r3): a
    # regeneration must not be able to silently change module, direction,
    # provenance, lincs, collected_names, case, seed_genes, prism, schema
    # or generated_by - the audit fields the package's honesty claims
    # rest on.  Only generated_at/config_sha are volatile (stripped).
    for key in sorted((set(new) | set(old))
                      - {"candidates", "excluded_mechanism_opposed",
                         "funnel"}):
        diffs = _leaf_diffs(old.get(key, "<absent>"),
                            new.get(key, "<absent>"))
        assert not diffs, f"top-level {key!r}: {diffs}"
    # funnel: the only added key is `merged`, which must close the counts.
    # Stale committed evidence lacks it; regenerated evidence carries the
    # same value the engine emits, so pop both sides before comparing.
    fun_new, fun_old = dict(new["funnel"]), dict(old["funnel"])
    merged = fun_new.pop("merged")
    assert fun_old.pop("merged", merged) == merged
    assert fun_new == fun_old
    tot = sum(fun_new[k] for k in (
        "gated_in", "gated_out_no_chembl", "gated_out_phase",
        "gated_out_withdrawn", "gated_out_unresolved")) + merged
    assert fun_new["collected"] - fun_new["dropped_over_cap"] == tot


@pytest.mark.skipif(not CANDIDATES.exists(), reason="evidence not generated")
def test_evidence_comparison_covers_audit_fields():
    """redteam2 r3: the reviewer's scratch-mutations.  Score, flag, drop
    and funnel mutations were already caught; these were the holes and
    every one must now produce a leaf diff the strict comparison sees."""
    old = _strip_volatile(
        json.loads(CANDIDATES.read_text(encoding="utf-8")))

    def per_cand_paths(mutate):
        m = json.loads(json.dumps(old))
        mutate(m["candidates"][0])
        return set(_leaf_diffs(old["candidates"][0],
                               m["candidates"][0]))

    for path, value in (
            ("approval.fda_set_id", "mutated-set-id"),
            ("approval.combination_label", True),
            ("approval.openfda_match", "mutated match note"),
            ("pediatric_flag_evidence",
             {"section": "pediatric_use", "text": "mutated"})):
        got = per_cand_paths(
            lambda c, p=path, v=value: _set_leaf(c, p, v))
        assert any(p == path or p.startswith((path + ".", path + "["))
                   for p in got), (path, sorted(got))

    def top_paths(mutate):
        m = json.loads(json.dumps(old))
        mutate(m)
        return set(_leaf_diffs(old, m))

    for path, value in (
            ("module", {"mutated": 1}),
            ("direction", {"mutated": 1}),
            ("provenance", {"mutated": 1}),
            ("lincs", {"mutated": 1}),
            ("collected_names", ["mutated"])):
        got = top_paths(lambda m, p=path, v=value: m.update({p: v}))
        assert any(p == path or p.startswith((path + ".", path + "["))
                   for p in got), (path, sorted(got))


def _set_leaf(d, path, value):
    parts = path.split(".")
    for p in parts[:-1]:
        d = d[p]
    d[parts[-1]] = value


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
    for case in old["cases"]:
        case["funnel"].pop("merged", None)
    assert out == old
