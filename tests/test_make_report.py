"""Tests for tools/make_report.py - GATE 6 (regenerated numbers, no
hand-typed stats).

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.make_report import runtime_section, submission_summary
import pytest

pytestmark = pytest.mark.gate


def _hyp(chrom, pos=1000, ref="A", alt="T", gene="GENEX", model="dominant_het"):
    return {"gene": gene, "model": model, "score": 0.9, "variant_damage": 1.0,
            "pheno_score": 0.7, "inheritance_score": 0.5, "epcr": 0.95,
            "in_trans": "unknown", "emitted": True,
            "variants": [{"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}]}


def test_submission_summary_no_double_chr_prefix_on_chr_contig():
    """Falsification: a source VCF using chr-prefixed contigs must render
    'chr7:...' in the headline call, not 'chrchr7:...' - the exact
    double-prefix bug the reinvented (rather than reused)
    to_submission_chrom logic produced."""
    result = {"ranked": [_hyp("chr7", pos=140453136)]}
    summary = submission_summary(result, truth=None)
    assert "chrchr7" not in summary
    assert "chr7:140453136" in summary


def test_submission_summary_normalizes_bare_contig():
    """Falsification: a bare contig ('15', the challenge VCF convention)
    must still be normalized to 'chr15' in the report, matching
    to_submission_chrom used everywhere else in the writer."""
    result = {"ranked": [_hyp("15", pos=40000001)]}
    summary = submission_summary(result, truth=None)
    assert "chr15:40000001" in summary


def test_runtime_section_fixture_count_matches_test_module():
    """Falsification: GATE 6 forbids hand-typed stats in the report; a
    literal '57' would silently drift from the real adversarial-battery
    size the moment a fixture is added or removed. The rendered count
    must equal the actual MUTATIONS+NOOP_MUTATIONS size in
    tests/test_adversarial.py, and no bogus fixed 'seconds' duration may
    be rendered for a job that was never timed."""
    sys.path.insert(0, str(REPO / "tests"))
    import test_adversarial as ta
    expected_n = len(ta.MUTATIONS) + len(ta.NOOP_MUTATIONS)

    section = runtime_section(None, {"runtime_sec": 1.23})
    assert f"{expected_n}-fixture" in section
    assert "seconds |" not in section


def _minimal_run(tmp_path):
    """Smallest valid run dir + artifacts to drive main() end-to-end."""
    run = tmp_path / "run"
    run.mkdir()
    (run / "result.json").write_text(json.dumps({
        "ranked": [{"gene": "G", "model": "compound_het", "score": 0.9,
                    "variant_damage": 1.0, "pheno_score": 0.8,
                    "inheritance_score": 1.0, "epcr": 0.95,
                    "in_trans": "trans", "emitted": True, "rank": 1,
                    "variants": [{"chrom": "7", "pos": 1, "ref": "A",
                                  "alt": "T"},
                                 {"chrom": "7", "pos": 2, "ref": "G",
                                  "alt": "C"}]}],
        "emitted": [{"gene": "G"}],
        "funnel": {"records": 2, "alt_gene_facts": 2, "qc_pass": 2,
                   "rare": 2, "candidates": 2, "hypotheses": 1,
                   "emitted": 1},
        "monotonicity_violations": [],
        "provenance": {"vcf": "x.vcf", "config_sha256": "ab" * 32,
                       "runtime_sec": 0.1}}))
    return run


def test_control_line_enriched_by_arm_a_tsv(tmp_path):
    """Falsification: the negative-control claim cites BOTH arms'
    silence. If --arm-a-control's genes.tsv is dropped, a typo'd column
    name, or its '#RANK' header confuses DictReader, the Arm-A score must
    not silently vanish from the report - this test pins the enriched
    sentence."""
    from tools.make_report import main
    ctrl = tmp_path / "ctrl"
    ctrl.mkdir()
    (ctrl / "result.json").write_text(json.dumps(
        {"ranked": [], "emitted": [], "funnel": {"emitted": 0},
         "monotonicity_violations": [], "provenance": {}}))
    tsv = tmp_path / "genes.tsv"
    tsv.write_text("#RANK\tGENE_SYMBOL\tEXOMISER_GENE_COMBINED_SCORE\n"
                   "1\tMAD1L1\t0.0003\n2\tVWF\t0.0001\n")
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--control-dir", str(ctrl),
               "--arm-a-control", str(tsv),
               "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    assert "0 hypotheses emitted" in body
    assert "Arm A (Exomiser) max gene score 0.0003 - also silent" in body


def test_arm_concordance_line_derived_from_artifact(tmp_path):
    """Falsification: the concordance claim must come from the
    compare_arms artifact - if the JSON keys drift (top_n, truth_rank_*)
    the rendered sentence must still report the artifact's real values
    rather than a stale 'not yet run' fallback."""
    from tools.make_report import main
    conc = tmp_path / "conc.json"
    conc.write_text(json.dumps({
        "top_n": 20, "top20_overlap": ["PAH"], "top20_overlap_n": 1,
        "truth_gene": "PAH", "truth_rank_arm_a": 1,
        "truth_rank_arm_b": 1}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--arm-concordance", str(conc),
               "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    conc_line = next(l for l in body.splitlines()
                     if "Arm A vs Arm B concordance" in l)
    assert "not yet run" not in conc_line
    assert ("top-20 gene overlap 1 (PAH); PAH ranked 1 by Arm B, "
            "1 by Arm A") in conc_line


def test_arm_concordance_missing_renders_fallback(tmp_path):
    """Falsification: without the artifact the report must honestly say
    'not yet run' on the concordance line - never fabricate a claim."""
    from tools.make_report import main
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    conc_line = next(l for l in body.splitlines()
                     if "Arm A vs Arm B concordance" in l)
    assert "not yet run" in conc_line
