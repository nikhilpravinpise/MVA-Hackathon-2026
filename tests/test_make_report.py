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


def test_arm_concordance_truth_absent_both_arms(tmp_path):
    """Falsification: a supplied truth gene missed by BOTH arms is the
    exact negative finding this metric exists for - the line must say so,
    not read as if no truth comparison ran."""
    from tools.make_report import main
    conc = tmp_path / "conc.json"
    conc.write_text(json.dumps({
        "top_n": 20, "top20_overlap": [], "top20_overlap_n": 0,
        "truth_gene": "PAH", "truth_rank_arm_a": None,
        "truth_rank_arm_b": None}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--arm-concordance", str(conc), "--out", str(out)])
    assert rc == 0
    conc_line = next(l for l in out.read_text().splitlines()
                     if "Arm A vs Arm B concordance" in l)
    assert "PAH ABSENT from both arms' ranked lists" in conc_line


def test_arm_a_control_high_score_flags_unexpected(tmp_path):
    """Falsification: 'also silent' is a derived claim - a control genes.tsv
    with a high score must render UNEXPECTED, not assert silence."""
    from tools.make_report import main
    ctrl = tmp_path / "ctrl"
    ctrl.mkdir()
    (ctrl / "result.json").write_text(json.dumps(
        {"ranked": [], "emitted": [], "funnel": {"emitted": 0},
         "monotonicity_violations": [], "provenance": {}}))
    tsv = tmp_path / "genes.tsv"
    tsv.write_text("#RANK\tGENE_SYMBOL\tEXOMISER_GENE_COMBINED_SCORE\n"
                   "1\tBRCA1\t0.99\n")
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--control-dir", str(ctrl),
               "--arm-a-control", str(tsv), "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    assert "max gene score 0.9900 - UNEXPECTED - investigate" in body
    assert "also silent" not in body.split("0.9900")[0].split(
        "Arm A (Exomiser)")[-1]


def test_arm_a_control_missing_tsv_says_unverified(tmp_path):
    """Falsification: a missing Arm-A TSV must say 'silence unverified' -
    never silently drop the clause."""
    from tools.make_report import main
    ctrl = tmp_path / "ctrl"
    ctrl.mkdir()
    (ctrl / "result.json").write_text(json.dumps(
        {"ranked": [], "emitted": [], "funnel": {"emitted": 0},
         "monotonicity_violations": [], "provenance": {}}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--control-dir", str(ctrl),
               "--arm-a-control", str(tmp_path / "nope.tsv"),
               "--out", str(out)])
    assert rc == 0
    assert "silence unverified" in out.read_text()


def test_arm_a_control_variants_tsv_rejected(tmp_path):
    """Falsification: a variants.tsv shares the score column - passing it
    would report a variant score as a 'gene' score."""
    from tools.make_report import main
    ctrl = tmp_path / "ctrl"
    ctrl.mkdir()
    (ctrl / "result.json").write_text(json.dumps(
        {"ranked": [], "emitted": [], "funnel": {"emitted": 0},
         "monotonicity_violations": [], "provenance": {}}))
    tsv = tmp_path / "v.tsv"
    tsv.write_text("#RANK\tCHROM\tPOS\tEXOMISER_VARIANT_SCORE\t"
                   "EXOMISER_GENE_COMBINED_SCORE\n"
                   "1\tchr1\t100\t0.9\t0.0003\n")
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--control-dir", str(ctrl),
               "--arm-a-control", str(tsv), "--out", str(out)])
    assert rc == 0
    assert "unreadable" in out.read_text()


def test_ablation_table_post_mask_columns():
    """Falsification: post-mask ablation JSONs carry bub1b_rank/top_emitted
    while pair_rank is null - a table still keying pair_rank renders
    'None' per row and hides the mask evidence."""
    from tools.make_report import ablation_table
    abl = {"gnomad": {"pair_rank": None, "bub1b_rank": 5,
                      "top_emitted": {"gene": "BUB1B",
                                      "model": "compound_het",
                                      "variants": [["15", 1, "T", "G"],
                                                   ["15", 2, "T", "G"]]},
                      "emitted": 1},
           "hpo": {"pair_rank": None, "bub1b_rank": None,
                   "top_emitted": None, "emitted": 0}}
    t = ablation_table(abl, None)
    assert "| gnomad | 5 | BUB1B (compound_het) | 1 |" in t
    assert "| hpo | None | None | 0 |" in t
    assert "Pair rank" not in t.splitlines()[0]  # header uses new names


def test_ablation_table_premask_fallback():
    """Falsification: run-2 artifacts keyed the tracked pair under
    pair_rank with no bub1b_rank - the table must still show the rank
    rather than degrade to None."""
    from tools.make_report import ablation_table
    abl = {"clinvar": {"pair_rank": 2, "emitted": 4}}
    t = ablation_table(abl, None)
    assert "| clinvar | 2 | None | 4 |" in t


def test_abl_fragility_uses_bub1b_rank_post_mask(tmp_path):
    """Falsification: ABSTRACT derives the fragility clause from the
    tracked pair's ablation ranks - post-mask every pair_rank is null,
    so a pair_rank-only derivation renders 'None' ranks (or nothing)
    instead of the real fragility numbers."""
    from tools.make_report import main
    abl = tmp_path / "ablations.json"
    abl.write_text(json.dumps(
        {"clinvar": {"pair_rank": None, "bub1b_rank": 125, "emitted": 0},
         "gnomad": {"pair_rank": None, "bub1b_rank": 2, "emitted": 1}}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--ablations", str(abl), "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    assert "ablation rule on 1 of 2" in body
    assert "clinvar (rank 125)" in body
    assert "(rank None)" not in body


def test_result_head_preferred_over_result(tmp_path):
    """Falsification: result_head.json (the slim Modal artifact) must be
    preferred - reading the 2 GB result.json when a head exists defeats
    the heap-risk mitigation."""
    from tools.make_report import main
    run = _minimal_run(tmp_path)
    (run / "result_head.json").write_text(json.dumps({
        "ranked": [{"gene": "HEADGENE", "model": "compound_het",
                    "score": 0.9, "variant_damage": 1.0,
                    "pheno_score": 0.8, "inheritance_score": 1.0,
                    "epcr": 0.95, "in_trans": "trans", "emitted": True,
                    "rank": 1,
                    "variants": [{"chrom": "7", "pos": 1, "ref": "A",
                                  "alt": "T"},
                                 {"chrom": "7", "pos": 2, "ref": "G",
                                  "alt": "C"}]}],
        "emitted": [1],
        "funnel": {"records": 2, "locus_masked": 2, "emitted": 1},
        "monotonicity_violations": [],
        "provenance": {"vcf": "x.vcf", "config_sha256": "ab" * 32,
                       "runtime_sec": 0.1}}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(run), "--out", str(out)])
    assert rc == 0
    assert "HEADGENE" in out.read_text()


def test_new_slots_pending_when_absent(tmp_path):
    """Falsification: the evidence render slots must render PENDING (not
    crash, not fabricate) when their artifacts aren't wired."""
    from tools.make_report import main
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    assert "{{MOSDEPTH_SECTION}}" not in body
    assert "{{ORTHOGONAL_SECTION}}" not in body
    # the PENDING marker lands in all three new slots
    assert body.count("Pending dataset access") >= 3


def test_new_slots_fill_from_fixtures(tmp_path):
    """Falsification: wired artifacts must surface in the report - a
    slot that drops its JSON silently would publish an empty section."""
    from tools.make_report import main
    md = tmp_path / "mosdepth.json"
    md.write_text(json.dumps(
        {"WGS": {"mean": 43.2, "frac_ge_10x": 0.98, "frac_ge_30x": 0.87},
         "region": {"mean": 51.0, "frac_ge_10x": 1.0,
                    "frac_ge_30x": 0.99}}))
    dv = tmp_path / "dv.json"
    dv.write_text(json.dumps(
        {"caller": "deepvariant-1.9.0",
         "sites": {"40209701": {"gt": "0/1", "gq": "34", "filter": "PASS",
                                 "recalled": True},
                   "40220612": {"gt": "0/1", "gq": "44", "filter": "PASS",
                                 "recalled": True}},
         "all_recalled_het_pass_gq20": True}))
    cnv = tmp_path / "cnv.json"
    cnv.write_text(json.dumps(
        {"bub1b_region": "15:40205000-40232000",
         "bub1b_overlapping_calls": 0, "calls": [],
         "verdict": "none", "callers": ["manta", "cnvpytor"]}))
    fq = tmp_path / "fq.json"
    fq.write_text(json.dumps(
        {"mode": "fastp_json", "status": "ok",
         "stats": {"read_pairs": 404000000},
         "comparison": {"all_pass": True, "n_measured": 5,
                        "checks": {"q30_rate": {"status": "pass",
                                              "value": 0.94,
                                              "expected": 0.935}},
                        "notes": []}}))
    off = tmp_path / "off.json"
    off.write_text(json.dumps(
        {"site": "15:40216470 A>G", "distance_to_nearest_exon_bp": 1026,
         "ad": "28/18", "spliceai_deltas": 0.0,
         "gnomad_genome_cov": "absent",
         "verdict": "evaluated; splice-benign; does not change the call"}))
    out = tmp_path / "report.md"
    rc = main(["--run-dir", str(_minimal_run(tmp_path)),
               "--mosdepth", str(md), "--deepvariant", str(dv),
               "--cnv", str(cnv), "--fastq-qc", str(fq),
               "--offslice", str(off), "--out", str(out)])
    assert rc == 0
    body = out.read_text()
    assert "| WGS | 43.2 | 0.98 | 0.87 |" in body
    assert "| 15:40209701 | 0/1 | 34 | PASS | True |" in body
    assert "**0** del/dup calls" in body or "del/dup" in body
    assert "0.94" in body  # fastq check value
    assert "splice-benign" in body
    assert "{{MOSDEPTH_SECTION}}" not in body
