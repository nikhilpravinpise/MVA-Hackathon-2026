"""Network-free tests for tools/t2_prism.py.

Pure-stdlib paths only: the OLS-with-absorbed-fixed-effects regression, the
incomplete-beta t-CDF, BH q-values, Spearman rho, drug-name normalisation,
screen-collapse policy, and an end-to-end analyze() run on tiny synthetic
CSVs written to tmp_path (no network, no heavy deps - runs in the main
venv).
"""
import csv
import importlib.util
import math
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "t2_prism", REPO / "tools" / "t2_prism.py")
tp = importlib.util.module_from_spec(SPEC)
sys.modules["t2_prism"] = tp
SPEC.loader.exec_module(tp)


# ---------------------------------------------------------------- stats
def test_ols_group_slope_recovers_beta_and_fe():
    # y = 2 + 3*x + lineage effect (+10 for 'B'), tiny noise-free data
    xs, ys, gs = [], [], []
    for i in range(60):
        g = "B" if i % 2 else "A"
        x = (i % 17) - 8
        xs.append(float(x))
        gs.append(g)
        ys.append(2.0 + 3.0 * x + (10.0 if g == "B" else 0.0))
    fit = tp.ols_group_slope(ys, xs, gs)
    assert fit["beta"] == pytest.approx(3.0, abs=1e-9)
    assert fit["se"] < 1e-6
    assert fit["n"] == 60 and fit["k_groups"] == 2
    assert fit["p"] < 1e-10


def test_ols_group_slope_ignores_confounded_intercept():
    # lineage B has both higher x and higher y; within-group slope is ~0
    xs, ys, gs = [], [], []
    for i in range(40):
        g = "B" if i % 2 else "A"
        x = (i % 9) + (50.0 if g == "B" else 0.0)
        xs.append(x)
        gs.append(g)
        ys.append(5.0 + (20.0 if g == "B" else 0.0) + 0.001 * (i % 3))
    fit = tp.ols_group_slope(ys, xs, gs)
    assert abs(fit["beta"]) < 0.01
    assert 0.0 <= fit["p"] <= 1.0


def test_ols_group_slope_unidentified():
    assert tp.ols_group_slope([1, 2], [1, 1], ["a", "a"]) is None
    assert tp.ols_group_slope([1, 2, 3], [1, 1, 1], ["a", "a", "a"]) is None


def test_t_two_sided_p_monotone_and_bounds():
    p_small = tp.t_two_sided_p(0.0, 10)
    p_big = tp.t_two_sided_p(5.0, 10)
    assert p_small == pytest.approx(1.0)
    assert 0.0 < p_big < 0.001
    # t=1.8125, df=10 -> two-sided p ~ 0.100 (standard t table)
    assert tp.t_two_sided_p(1.8125, 10) == pytest.approx(0.100, abs=0.002)
    # df=1, t=1 -> p = 0.5 exactly (Cauchy)
    assert tp.t_two_sided_p(1.0, 1) == pytest.approx(0.5, abs=1e-9)


def test_betai_edges():
    assert tp.betai(2, 3, 0.0) == 0.0
    assert tp.betai(2, 3, 1.0) == 1.0
    # I_0.5(1,1) = 0.5
    assert tp.betai(1, 1, 0.5) == pytest.approx(0.5)


def test_bh_qvalues():
    p = [0.001, 0.02, 0.04, 0.5, 0.9]
    q = tp.bh_qvalues(p)
    # sorted p = .001,.02,.04,.5,.9 ; q_i = min over k>=rank_i of p_k*m/k
    assert q[0] == pytest.approx(0.001 * 5 / 1)
    assert q[4] == pytest.approx(0.9)
    assert q[3] == pytest.approx(min(0.5 * 5 / 4, 0.9))   # 0.625
    assert q[2] == pytest.approx(min(0.04 * 5 / 3, q[3]))  # 0.0667
    assert q[1] == pytest.approx(min(0.02 * 5 / 2, q[2]))  # 0.05
    assert all(0 <= v <= 1 for v in q)


def test_spearman_perfect_and_inverted():
    x = list(range(1, 30))
    assert tp.spearman(x, x)["rho"] == pytest.approx(1.0)
    assert tp.spearman(x, [-v for v in x])["rho"] == pytest.approx(-1.0)
    r = tp.spearman([1, 2, 3, 4, 5, 6], [1, 1, 1, 9, 9, 9])
    assert r["rho"] > 0.8


def test_norm_drug_name_salts():
    assert tp.norm_drug_name("Cytarabine Hydrochloride") == "cytarabine"
    assert tp.norm_drug_name("Barasertib-HQPA") == "barasertib-hqpa"
    assert tp.norm_drug_name("nutlin-3") == "nutlin-3"
    assert tp.norm_drug_name("atenolol (+/-)") == "atenolol"


# ------------------------------------------------------- collapse_screens
def test_collapse_screens_prefers_mts010():
    rows = [
        ("B1", "ACH-1", "HTS002", 1.0, "d", "m", "t", "Launched"),
        ("B1", "ACH-1", "MTS010", 0.9, "d", "m", "t", "Launched"),
        ("B1", "ACH-1", "MTS005", 0.5, "d", "m", "t", "Launched"),
        ("B1", "ACH-2", "HTS002", 1.1, "d", "m", "t", "Launched"),
    ]
    best = tp.collapse_screens(rows)
    assert best[("B1", "ACH-1")]["auc"] == 0.9
    assert best[("B1", "ACH-1")]["screen"] == "MTS010"
    assert best[("B1", "ACH-2")]["screen"] == "HTS002"


# --------------------------------------------------- end-to-end synthetic
def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def _make_raw(tmp_path: Path) -> Path:
    """Tiny synthetic dataset where drugA is strongly aneuploid-selective
    and drugB is inert; exercises the full analyze() path."""
    raw = tmp_path / "raw"
    der = raw / "derived"
    der.mkdir(parents=True)
    n_lines = 40
    line_ids = [f"ACH-{i:06d}" for i in range(n_lines)]
    _write_csv(
        der / "aneuploidy.csv",
        ["depmap_id", "ccle_name", "aneuploidy_score", "aneuploidy_group"],
        [[d, f"CL{i}", str(i % 30), "x"] for i, d in enumerate(line_ids)])
    _write_csv(
        der / "bub1b_expr_cn.csv",
        ["depmap_id", "bub1b_expr_log2tpm", "bub1b_cn_rel"],
        [[d, str(4.0 + (i % 7) * 0.3), str(0.8 + (i % 5) * 0.1)]
         for i, d in enumerate(line_ids)])
    _write_csv(
        der / "cell_lines.csv",
        ["depmap_id", "ccle_name", "primary_tissue", "lineage",
         "passed_str_profiling"],
        [[d, f"CL{i}", ["lung", "skin", "breast", "colon"][i % 4], "",
          "TRUE"] for i, d in enumerate(line_ids)])
    hdr = ["broad_id", "depmap_id", "ccle_name", "screen_id",
           "upper_limit", "lower_limit", "slope", "r2", "auc", "ec50",
           "ic50", "name", "moa", "target", "disease.area", "indication",
           "smiles", "phase", "passed_str_profiling", "row_name"]
    rows = []
    for i, d in enumerate(line_ids):
        ascore = i % 30
        # drugA: AUC = 1.5 - 0.02*AS -> strongly aneuploid-selective
        rows.append(["BRD-A", d, f"CL{i}", "HTS002", 1, 2, -1, 0.9,
                     f"{1.5 - 0.02 * ascore:.6f}", 1, 1, "drugA",
                     "test moa", "TGT", "onc", "ind", "C", "Launched",
                     "TRUE", d])
        # drugB: flat
        rows.append(["BRD-B", d, f"CL{i}", "HTS002", 1, 2, -1, 0.9,
                     "1.100000", 1, 1, "drugB", "test moa", "TGT", "onc",
                     "ind", "C", "Launched", "TRUE", d])
        # drugC: preclinical, aneuploid-RESISTANT
        rows.append(["BRD-C", d, f"CL{i}", "HTS002", 1, 2, -1, 0.9,
                     f"{1.0 + 0.02 * ascore:.6f}", 1, 1, "drugC", "moa",
                     "TGT", "onc", "ind", "C", "Preclinical", "TRUE", d])
    _write_csv(raw / "secondary-screen-dose-response-curve-parameters.csv",
               hdr, rows)
    (raw / "manifest.json").write_text("{}", encoding="utf-8")
    return raw


def test_analyze_end_to_end(tmp_path):
    raw = _make_raw(tmp_path)
    res = tp.analyze(raw, min_lines=10)
    launched = {r["name"]: r for r in res["aneuploidy"]["all_results"]
                if r["phase"] == "Launched"}
    assert launched["drugA"]["beta"] == pytest.approx(-0.02, abs=1e-9)
    assert launched["drugA"]["q"] < 0.05
    assert abs(launched["drugB"]["beta"]) < 1e-6
    pre = {r["name"]: r for r in res["aneuploidy"]["all_results"]}
    assert pre["drugC"]["beta"] == pytest.approx(+0.02, abs=1e-9)
    # launched-only views exclude preclinical drugC
    assert "drugC" not in launched
    assert res["bub1b_expression"]["n_compounds_tested"] >= 3
    # quartile sanity: top-minus-bottom AUC must be negative for drugA
    assert launched["drugA"]["quartiles"]["auc_top_minus_bottom"] < 0


def test_iter_auc_rows_filters_str(tmp_path):
    p = tmp_path / "d.csv"
    _write_csv(p, ["broad_id", "depmap_id", "screen_id", "auc", "name",
                   "moa", "target", "phase", "passed_str_profiling"],
               [["B", "ACH-1", "HTS002", "1.0", "d", "m", "t", "Launched",
                 "TRUE"],
                ["B", "ACH-2", "HTS002", "1.0", "d", "m", "t", "Launched",
                 "FALSE"],
                ["B", "ACH-3", "HTS002", "NA", "d", "m", "t", "Launched",
                 "TRUE"]])
    rows = list(tp.iter_auc_rows(p))
    assert len(rows) == 1 and rows[0][1] == "ACH-1"
