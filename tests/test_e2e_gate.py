"""The full E2E gate (plan.md section 6): pipeline -> submission CSV ->
vendored oracle -> 100/1.000 on the synthetic ground truth, then a
field-by-field mutation audit of the produced bytes.

Falsification: any break in the chain (funnel rank, writer contract, chrom
normalization, epcr ordering, oracle parse) shows up as <100/<1.000 or an
exception - the exact failures that sank real leaderboard teams.
"""
from __future__ import annotations

import pytest

from src import synth
from src.pipeline import run_pipeline
from src.vcf import to_submission_chrom


@pytest.fixture(scope="module")
def spike_run(tmp_path_factory):
    d = tmp_path_factory.mktemp("gate")
    case = synth.spike_in_case(d)
    res = run_pipeline(
        case["vcf"], case["truth"]["hpo_terms"],
        obo_path=case["obo"], hpoa_path=case["hpoa"],
        g2d_path=case["gene2disease"], out_dir=d / "run")
    return case, res


def _gt_from_truth(truth):
    return frozenset(
        (v["chrom"], v["pos"], v["ref"], v["alt"]) for v in truth["pair"])


@pytest.mark.gate
def test_pipeline_to_oracle_100_1000(spike_run, tmp_path):
    """Falsification: end-to-end output does not score 100/1.000 - some link
    (pair not rank 1, chrom prefix wrong, epcr structure, writer bytes)
    breaks the verified contract."""
    from src.submit import submission_bytes, validate_submission_bytes, build_rows
    case, res = spike_run
    gt = _gt_from_truth(case["truth"])
    rows = build_rows(res["ranked"], cfg=None)
    data = submission_bytes(rows)
    assert not data.startswith(b"\xef\xbb\xbf")
    data.decode("ascii")  # contract: pure ASCII on the wire
    r = validate_submission_bytes(data, gt)
    assert r.rank_points == 100.0 and r.f_max == pytest.approx(1.0)
    assert r.full_match_rank == 1


@pytest.mark.gate
def test_chrom_normalization_e2e(spike_run):
    """Falsification: submission rows carry bare contigs ('7' not 'chr7') -
    the exact convention trap that zeroed real teams."""
    from src.submit import build_rows
    case, res = spike_run
    rows = build_rows(res["ranked"])
    assert rows, "no rows built"
    for row in rows:
        for ck in ("chrom_1", "chrom_2"):
            c = row.get(ck) or ""
            if c:
                assert c.startswith("chr"), f"{ck}={c} lacks chr prefix"
                assert c == to_submission_chrom(c)


@pytest.mark.gate
def test_mutation_audit_on_built_csv(spike_run, tmp_path):
    """Falsification: a corruption of the real output bytes scores the same
    as clean bytes - either the oracle ignores the field (document it) or
    the writer emits something the scorer can't see."""
    from src.submit import (build_rows, submission_bytes,
                            validate_submission_bytes)
    case, res = spike_run
    gt = _gt_from_truth(case["truth"])
    base = submission_bytes(build_rows(res["ranked"]))
    base_score = validate_submission_bytes(base, gt)
    text = base.decode("ascii")

    def mutated_score(new_text):
        try:
            r = validate_submission_bytes(new_text.encode("ascii"), gt)
            return (r.rank_points, round(r.f_max, 3))
        except Exception:
            return "RAISED"

    mutations = {
        "chr->CHR case flip": text.replace("chr7", "CHR7"),
        "drop chr prefix": text.replace("chr7", "7"),
        "pos1 +1": text.replace("1000000", "1000001", 1),
        "epcr 0.95->0": text.replace("0.95", "0", 1),
        "epcr->1.5": text.replace("0.95", "1.5", 1),
        "bogus finding_type": text.replace("primary", "bogus", 1),
        "pid lowercase": text.replace("PROBAND01", "proband01"),
    }
    expected = (base_score.rank_points, round(base_score.f_max, 3))
    failures = {}
    for name, mtext in mutations.items():
        got = mutated_score(mtext)
        if got == expected:
            failures[name] = got
    assert not failures, f"mutations with no scoring effect: {failures}"

    # Documented no-ops (oracle semantics already verified in the section-6
    # battery): junk strictly below the top epcr never reaches the F=1.0
    # threshold and can't outrank the pair; notes is ignored by the scorer.
    documented_noops = {
        "low-epcr junk row appended": text + "PROBAND01,chr9,5,A,C,,,,,0.1,primary,\n",
        "notes content changed": text.replace(",primary,", ",primary,x9z", 1),
    }
    for name, mtext in documented_noops.items():
        got = mutated_score(mtext)
        assert got == expected, \
            f"{name}: expected documented no-op, got {got}"
