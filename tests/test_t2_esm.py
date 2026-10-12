"""Network-free tests for tools/t2_esm.py.

The pure-stdlib helpers only: HGVS protein-change parsing, ESM windowing,
LLR math, percentile/AUC helpers, panel selection, MockScorer end-to-end
assembly. No torch, no network - runs in the main venv.
"""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "t2_esm", REPO / "tools" / "t2_esm.py")
te = importlib.util.module_from_spec(SPEC)
sys.modules["t2_esm"] = te
SPEC.loader.exec_module(te)


def test_parse_hgvsp_missense_and_ter():
    assert te.parse_hgvsp(
        "NM_001211.6(BUB1B):c.3006T>G (p.Asn1002Lys)") == {
        "pos": 1002, "wt": "N", "mut": "K", "hgvsp": "p.Asn1002Lys"}
    assert te.parse_hgvsp("x p.Leu737Ter")["mut"] == "*"
    assert te.parse_hgvsp("NM_001211.6(BUB1B):c.2786del (p.Gly929fs)") is None
    assert te.parse_hgvsp("NM_001211.6(BUB1B):c.1058+2T>G") is None


def test_window_bounds_clamps_to_termini():
    L, win = 1050, 1022
    assert te.window_bounds(L, 0, win) == (0, 1022)
    assert te.window_bounds(L, 1049, win) == (28, 1050)
    assert te.window_bounds(L, 1001, win) == (28, 1050)   # pos1002 in-window
    s, e = te.window_bounds(L, 520, win)
    assert s == 520 - 511 and e == s + 1022 and s <= 520 < e
    assert te.window_bounds(300, 10, win) == (0, 300)      # short protein


def test_llr_from_logprobs():
    lp = {"N": -0.5, "K": -2.0, "X": -9.0}
    assert te.llr_from_logprobs(lp, "N", "K") == pytest.approx(-1.5)
    # '*' falls back to 'X' when absent
    assert te.llr_from_logprobs(lp, "N", "*") == pytest.approx(-8.5)
    lp2 = dict(lp); lp2["*"] = -3.0
    assert te.llr_from_logprobs(lp2, "N", "*") == pytest.approx(-2.5)


def test_percentile_and_median():
    bg = [-1.0] * 50 + [-5.0] * 50
    assert te.percentile_rank(-5.0, bg) == 50.0   # fraction <= value
    assert te.percentile_rank(-6.0, bg) == 0.0
    assert te.percentile_rank(0.0, bg) == 100.0
    assert te.percentile_rank(-1.0, bg) == 100.0
    # deleteriousness: fraction of bg the variant is MORE damaging than
    assert te.deleteriousness_pct(-5.0, bg) == 50.0
    assert te.deleteriousness_pct(-6.0, bg) == 100.0
    assert te.deleteriousness_pct(0.0, bg) == 0.0
    assert te.median([3, 1, 2]) == 2
    assert te.median([]) is None


def test_auc_from_labels_direction():
    # damaging (label=1) should get LOWER llr; perfect separation -> AUC 1
    scores = [-9, -8, -7, -1, -0.5, -0.1]
    labels = [1, 1, 1, 0, 0, 0]
    assert te.auc_from_labels(scores, labels) == 1.0
    assert te.auc_from_labels(scores[::-1], labels) == 0.0
    assert te.auc_from_labels([1], [1]) is None  # one class empty


def _synthetic_inputs() -> dict:
    seq = ("M" + "ACDEFGHIKLMNPQRSTVWY" * 52 + "QRSTVWYACE")[:1050]
    seq = list(seq)
    seq[736], seq[1001] = "L", "N"      # L737, N1002 as in O60566
    seq = "".join(seq)
    return {"schema": "t2.esm_inputs/1", "fetched_at": "2026-10-12T00:00:00Z",
            "uniprot": {"accession": "O60566", "url": "u", "header": "h",
                        "length": len(seq)},
            "sequence_sha256": "x", "sequence": seq,
            "clinvar": {
                "queries": {"missense_classified": "q1",
                            "pathogenic_all": "q2"},
                "missense": [
                    {"pos": 10, "wt": seq[9], "mut": "G",
                     "hgvsp": "p.X10G", "clinsig": "Benign", "uid": "1",
                     "title": "t"},
                    {"pos": 20, "wt": seq[19], "mut": "W",
                     "hgvsp": "p.X20W", "clinsig": "Likely benign",
                     "uid": "2", "title": "t"},
                    {"pos": 30, "wt": seq[29], "mut": "R",
                     "hgvsp": "p.X30R", "clinsig": "Likely pathogenic",
                     "uid": "3", "title": "t"}],
                "pathogenic_all": [
                    {"pos": 40, "wt": seq[39], "mut": "*",
                     "hgvsp": "p.X40Ter", "clinsig": "Pathogenic",
                     "uid": "4", "title": "t"},
                    {"pos": 41, "wt": seq[40], "mut": "Z",  # fs -> no pc? keep
                     "hgvsp": "p.X41Z", "clinsig": "Pathogenic",
                     "uid": "5", "title": "t"}]},
            "gnomad": {"dataset": "gnomad_r4", "api": "u",
                       "n_missense": 4,
                       "variants": [
                           {"pos": 50, "wt": seq[49], "mut": "A",
                            "hgvsp": "p.X50A", "variant_id": "v1",
                            "max_af": 2e-4, "max_ac": 100},
                           {"pos": 60, "wt": seq[59], "mut": "C",
                            "hgvsp": "p.X60C", "variant_id": "v2",
                            "max_af": 1e-7, "max_ac": 1},
                           {"pos": 70, "wt": seq[69], "mut": "D",
                            "hgvsp": "p.X70D", "variant_id": "v3",
                            "max_af": 1e-5, "max_ac": 3},
                           {"pos": 1002, "wt": "N", "mut": "K",
                            "hgvsp": "p.Asn1002Lys",
                            "variant_id": "15-40220612-T-G",
                            "max_af": 6.8e-7, "max_ac": 1}]},
            "query_variant": {"pos": 1002, "wt": "N", "mut": "K",
                              "hgvsp": "p.Asn1002Lys"}}


def test_select_panels_partitioning():
    inputs = _synthetic_inputs()
    p = te.select_panels(inputs)
    assert len(p["clinvar_benign"]) == 2
    assert len(p["clinvar_pathogenic"]) == 1
    assert len(p["clinvar_nonsense"]) == 1           # only the Ter row
    assert [v["variant_id"] for v in p["gnomad_common"]] == ["v1"]
    assert {v["variant_id"] for v in p["gnomad_ultrarare"]} >= {"v2"}


def test_score_end_to_end_mock():
    inputs = _synthetic_inputs()
    scorer = te.MockScorer()
    res = te.score(inputs, scorer=scorer)
    q = res["query"]
    assert q["variant"] == "p.Asn1002Lys"
    assert isinstance(q["llr"], float)
    assert 0 <= q["deleteriousness_percentile_vs_gnomad_missense"] <= 100
    cal = res["calibration"]
    assert cal["clinvar_benign"]["n"] == 2
    assert cal["clinvar_pathogenic_missense"]["n"] == 1
    assert cal["clinvar_nonsense_proxy"]["n"] == 1
    # query variant present in gnomAD is flagged and excluded from bg
    assert q["gnomad_af"] == pytest.approx(6.8e-7)
    assert all("panel" in s for s in res["scores"])


def test_mock_scorer_rejects_wt_mismatch():
    scorer = te.MockScorer()
    with pytest.raises(ValueError):
        scorer.score_variants("ACDE", [{"pos": 2, "wt": "G", "mut": "A"}])
