"""Tests for src/acmg.py - ACMG/AMP criteria math for the primary pair.

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch. VariantFacts are built by running the real funnel stage 0
(extract_facts) over synthesized SVar fixtures, so the evaluator consumes
exactly what the pipeline emits.
"""
from __future__ import annotations

import json

import pytest

pytestmark = pytest.mark.gate

from src.config import load_config
from src.synth import SVar, Ann, write_vcf, _af_ann
from src.triage import extract_facts
from src.vcf import VcfReader
from src import acmg


def _facts(tmp_path, variants):
    path = write_vcf(tmp_path / "case.vcf", variants)
    cfg = load_config()
    reader = VcfReader(path)
    sample = reader.samples[0]
    out = []
    try:
        for rec in reader.records(sample=sample):
            out.extend(extract_facts(rec, sample, cfg))
    finally:
        reader.close()
    return out


def _lof_var(chrom="7", pos=1_000_000, gene="GENEX", gt="0/1", clin=""):
    """stop_gained, absent from gnomAD -> damage_tier 'lof', PM2."""
    extra = dict(_af_ann())
    extra["CLIN_SIG"] = clin
    extra["CADD_PHRED"] = 41
    return SVar(chrom, pos, "A", "T", gt=gt,
                anns=[Ann("T", "stop_gained", "HIGH", gene, "ENSG0" + gene,
                          extra=extra)])


def _ms_var(pos=2_000_000, gene="GENEX", chrom="7", votes=True,
            af=None, gt="0/1"):
    """missense; votes=True -> CADD+REVEL+AM+SIFT+PPH2 all fire."""
    extra = dict(_af_ann(af, af))
    if votes:
        extra.update({"CADD_PHRED": 32, "REVEL": 0.91,
                      "AlphaMissense_score": 0.93,
                      "SIFT": "deleterious",
                      "PolyPhen": "probably_damaging"})
    else:
        extra.update({"CADD_PHRED": 12, "REVEL": 0.21,
                      "AlphaMissense_score": 0.2, "SIFT": "tolerated",
                      "PolyPhen": "benign"})
    return SVar(chrom, pos, "G", "C", gt=gt,
                anns=[Ann("C", "missense_variant", "MODERATE", gene,
                          "ENSG0" + gene, extra=extra)])


def _codes(res):
    return {c["code"] for c in res["criteria"]}


# ---------------------------------------------------------------------------
# Per-variant criteria
# ---------------------------------------------------------------------------

def test_pvs1_requires_lof_and_mechanism_flag(tmp_path):
    """Falsification: PVS1 must fire for a LoF allele in a LoF-mechanism
    gene AND be withheld when the caller does not assert the mechanism -
    catches an evaluator that over-calls PVS1 on any stop_gained."""
    vf = _facts(tmp_path, [_lof_var()])[0]
    assert vf.damage_tier == "lof"

    res = acmg.evaluate_variant(vf, {"lof_mechanism": True})
    assert "PVS1" in _codes(res)
    # absent from gnomAD -> PM2 (moderate)
    assert "PM2" in _codes(res)

    res_no = acmg.evaluate_variant(vf, {"lof_mechanism": False})
    assert "PVS1" not in _codes(res_no)
    assert any("PVS1 withheld" in c for c in res_no["caveats"])


def test_pp3_needs_two_votes(tmp_path):
    """Falsification: PP3 requires >=2 computational votes; a vote counter
    that fires on a single predictor or on zero would mislabel evidence."""
    hi = _facts(tmp_path, [_ms_var(pos=2_000_000, votes=True)])[0]
    lo = _facts(tmp_path, [_ms_var(pos=2_100_000, votes=False)])[0]

    res_hi = acmg.evaluate_variant(hi, {})
    assert res_hi["predictor_votes"] >= 2
    assert "PP3" in _codes(res_hi)

    res_lo = acmg.evaluate_variant(lo, {})
    assert res_lo["predictor_votes"] <= 1
    assert "PP3" not in _codes(res_lo)


def test_frequency_axis_pm2_pm2p_bs1(tmp_path):
    """Falsification: the rarity axis must separate absent (PM2),
    present-but-rare (PM2_P), and common (BS1) - a single-threshold
    implementation would silently misclassify one of the three."""
    absent = _facts(tmp_path, [_ms_var(pos=2_000_000)])[0]
    assert "PM2" in _codes(acmg.evaluate_variant(absent, {}))

    rare = _facts(tmp_path, [_ms_var(pos=2_000_000, af=5e-5)])[0]
    assert "PM2_P" in _codes(acmg.evaluate_variant(rare, {}))

    common = _facts(tmp_path, [_ms_var(pos=2_000_000, af=0.02)])[0]
    assert "BS1" in _codes(acmg.evaluate_variant(common, {}))


# ---------------------------------------------------------------------------
# Pair-level criteria (PM3 needs proven trans)
# ---------------------------------------------------------------------------

def test_pm3_fires_in_trans_not_cis(tmp_path):
    """Falsification: PM3 must fire only for a recessive pair proven in
    trans with a pathogenic partner; a cis (or unknown) phase yielding
    PM3 would fake biallelic evidence - the phasing gate exists for this."""
    facts = _facts(tmp_path, [_lof_var(pos=1_000_000),
                              _ms_var(pos=1_004_000)])
    lof_vf, ms_vf = facts[0], facts[1]

    trans = acmg.evaluate_pair([lof_vf, ms_vf], mechanism="recessive",
                               in_trans="trans")
    # the NOVEL missense allele earns PM3 in trans with the LoF partner
    ms_res = next(r for r in trans["variants"] if "missense" in
                  r["consequence"])
    assert "PM3" in _codes(ms_res)

    cis = acmg.evaluate_pair([lof_vf, ms_vf], mechanism="recessive",
                             in_trans="cis")
    assert not any("PM3" in _codes(r) for r in cis["variants"])
    assert any("PM3" in c for c in cis["caveats"])


def test_pm3_strong_when_both_pathogenic(tmp_path):
    """Falsification: two ClinVar-established P/LP alleles in trans must
    upgrade PM3 to PM3_Strong (+4); a flat PM3 would under-score the pair."""
    facts = _facts(tmp_path, [
        _lof_var(pos=1_000_000, clin="pathogenic"),
        _lof_var(pos=1_004_000, clin="pathogenic"),
    ])
    res = acmg.evaluate_pair(facts, mechanism="recessive",
                             in_trans="trans")
    assert all("PM3_Strong" in _codes(r) for r in res["variants"])


def test_pm3_not_strong_when_partner_only_predicted_lof(tmp_path):
    """Falsification: PM3_Strong (+4, heaviest after PVS1) must require
    BOTH partners to be ClinVar-established P/LP - a partner that is only
    predicted-LoF (no ClinVar assertion) must cap the pair at plain PM3
    (+2), never silently upgrade to PM3_Strong on in-silico evidence
    alone."""
    facts = _facts(tmp_path, [
        _lof_var(pos=1_000_000),                       # predicted LoF only
        _lof_var(pos=1_004_000, clin="pathogenic"),    # ClinVar P/LP
    ])
    res = acmg.evaluate_pair(facts, mechanism="recessive",
                             in_trans="trans")
    assert all("PM3" in _codes(r) for r in res["variants"])
    assert not any("PM3_Strong" in _codes(r) for r in res["variants"])


def test_pp4_phenotype_threshold(tmp_path):
    """Falsification: PP4 is pair-level phenotype evidence gated at
    pheno_score >= 0.6; an ungated or variant-level PP4 would inflate
    scores on weak phenotype matches."""
    facts = _facts(tmp_path, [_lof_var()])
    hi = acmg.evaluate_pair(facts[:1], mechanism="recessive",
                            pheno_score=0.7)
    assert "PP4" in _codes({"criteria": hi["pair_criteria"]})
    lo = acmg.evaluate_pair(facts[:1], mechanism="recessive",
                            pheno_score=0.5)
    assert lo["pair_criteria"] == []


# ---------------------------------------------------------------------------
# Classification bands + report shape
# ---------------------------------------------------------------------------

def test_classification_bands():
    """Falsification: the point->class table is the report's math; an
    off-by-one in a band boundary would change the claimed class."""
    assert acmg.classification(
        {"PVS1": 8, "PM2": 2, "PP3": 1, "PM3": 2}) == "Pathogenic"  # 13
    assert acmg.classification(
        {"PVS1": 8, "PM2": -2, "PP3": 1}) == "Likely pathogenic"    # 7
    assert acmg.classification({"PP3": 1}) == "VUS"
    assert acmg.classification(
        {"BS1": -4, "BP4": -1}) == "Likely benign"                  # -5
    assert acmg.classification({"BA1": -8}) == "Benign"


def test_common_no_vote_missense_benign_side(tmp_path):
    """Falsification: a common, predictor-quiet missense must land on the
    benign side (BS1 + BP4) - the evaluator must emit benign evidence,
    not just stay silent."""
    vf = _facts(tmp_path, [_ms_var(pos=2_000_000, votes=False,
                                   af=0.02)])[0]
    res = acmg.evaluate_variant(vf, {})
    assert "BS1" in _codes(res) and "BP4" in _codes(res)
    assert res["classification"] in ("Likely benign", "Benign")


def test_pair_accumulates_to_pathogenic(tmp_path):
    """Falsification: the spec'd accumulation PVS1+PM2+PP3+PM3 must reach
    the pathogenic band on the combined pair score (per the documented
    rule table)."""
    facts = _facts(tmp_path, [_lof_var(pos=1_000_000),
                              _ms_var(pos=1_004_000, votes=True)])
    res = acmg.evaluate_pair(facts, mechanism="recessive",
                             in_trans="trans", pheno_score=0.7)
    total = res["combined_points"]
    # lof: PVS1(8)+PM2(2); missense: PM2(2)+PP3(1)+PM3(2); pair PP4(1) = 16
    assert total == 16, \
        "a silently-dropped criterion (e.g. PP3) would keep >=10 anyway"
    assert res["combined_classification"] == "Pathogenic"


def test_acmg_report_keys_and_determinism(tmp_path):
    """Falsification: the report dict feeds the Track-1 ACMG table; a
    missing key or nondeterministic serialization would break report
    regeneration. Accepts the pipeline's ranked-hypothesis dict shape."""
    facts = _facts(tmp_path, [_lof_var(pos=1_000_000),
                              _ms_var(pos=1_004_000, votes=True)])
    hyp_dict = {"gene": "GENEX", "model": "compound_het",
                "in_trans": "trans", "pheno_score": 0.7,
                "variants": [
                    {"chrom": v.chrom, "pos": v.pos, "ref": v.ref,
                     "alt": v.alt, "consequence": v.consequence,
                     "tier": v.damage_tier, "popmax_af": v.popmax_af,
                     "gt": v.gt} for v in facts]}
    rep1 = acmg.acmg_report(hyp_dict, {"lof_mechanism": True})
    rep2 = acmg.acmg_report(hyp_dict, {"lof_mechanism": True})
    for key in ("framework", "gene", "model", "n_variants", "variants",
                "pair_criteria", "points_breakdown", "combined_points",
                "combined_classification", "rule_table", "caveats"):
        assert key in rep1
    assert rep1["gene"] == "GENEX" and rep1["n_variants"] == 2
    assert rep1["combined_classification"] == "Pathogenic"
    # deterministic: identical JSON on repeat
    assert json.dumps(rep1, sort_keys=True) == json.dumps(
        rep2, sort_keys=True)
    # per-variant blocks carry criteria with codes + rationale
    for vr in rep1["variants"]:
        assert vr["criteria"] and all(
            {"code", "strength", "points", "rationale"} <= set(c)
            for c in vr["criteria"])


def test_evaluate_variant_on_bare_list_input(tmp_path):
    """Falsification: acmg_report must also accept a bare VariantFacts
    list (no hypothesis wrapper) - catches a dict-only implementation."""
    facts = _facts(tmp_path, [_lof_var()])
    rep = acmg.acmg_report(facts, {"mechanism": "recessive",
                                   "lof_mechanism": True})
    assert rep["n_variants"] == 1
    assert rep["gene"] == "GENEX"
