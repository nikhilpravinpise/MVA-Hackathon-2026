"""Real-corpus e2e: the funnel + the REAL downloaded HPO corpus
(hp.obo + phenotype.hpoa + genes_to_phenotype) recovering a synthetic
compound-het pair placed in a REAL recessive-disease gene.

Gene: PAH (phenylketonuria, OMIM:261600) - firewall-clean (not the proband's
gene, not anywhere near leaked coordinates). Pair: synthetic ClinVar-style
LoF + damaging missense, in trans via shared PGT/PID.

Falsification: if the real annotation corpus + real HPO semantics cannot
lift PAH over the decoys, the phenotype layer only works on toy data -
the pipeline's central claim fails before the patient VCF ever lands.

Skips when env/corpus is absent (fresh clone): run tools/fetch_refs.py first.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import synth
from src.pipeline import run_pipeline

CORPUS = Path(__file__).resolve().parents[1] / "env" / "corpus"
pytestmark = pytest.mark.skipif(
    not (CORPUS / "hp.obo").exists() or not (CORPUS / "phenotype.hpoa").exists(),
    reason="env/corpus missing - run tools/fetch_refs.py")


def _real_pah_case(tmp_path):
    """PAH comp-het pair + decoys; proband HPO = real PKU terms."""
    from src.pheno import load_hpoa
    d2h = load_hpoa(CORPUS / "phenotype.hpoa")
    pku_terms = sorted(d2h.get("OMIM:261600", set()))
    # a handful of specific PKU terms as the proband's presentation
    proband_hpo = [t for t in pku_terms
                   if t not in ("HP:0000007", "HP:0000006")][:6]
    variants = [
        # TRUE PAIR: PAH, nonsense + damaging missense, in trans
        synth.SVar("12", 102_890_000, "C", "T", gt="0/1", pgt="1|0",
                   pid="PS_PAH",
                   anns=[synth.Ann("T", "stop_gained", "HIGH", "PAH",
                                   "ENSG00000171759",
                                   extra={"CADD_PHRED": 39, "LOEUF": 0.42,
                                          "CLIN_SIG": "pathogenic"})]),
        synth.SVar("12", 102_910_000, "G", "A", gt="0/1", pgt="0|1",
                   pid="PS_PAH",
                   anns=[synth.Ann("A", "missense_variant", "MODERATE", "PAH",
                                   "ENSG00000171759",
                                   extra={"CADD_PHRED": 28, "REVEL": 0.87,
                                          "AlphaMissense_score": 0.9,
                                          "SIFT": "deleterious",
                                          "PolyPhen": "probably_damaging",
                                          "CLIN_SIG": "pathogenic"})]),
        # intervening common het linking the phase set
        synth.SVar("12", 102_900_000, "T", "G", gt="0/1", pgt="0|1",
                   pid="PS_PAH",
                   anns=[synth.Ann("G", "synonymous_variant", "LOW", "PAH",
                                   "ENSG00000171759",
                                   extra={"gnomADe_AF": 0.3})]),
        # DECOYS
        synth.SVar("1", 5_000_000, "A", "T", gt="0/1",
                   anns=[synth.Ann("T", "stop_gained", "HIGH", "TTN",
                                   "ENSG00000155657",
                                   extra={"CADD_PHRED": 38})]),
        synth.SVar("1", 5_010_000, "G", "C", gt="0/1",
                   anns=[synth.Ann("C", "missense_variant", "MODERATE", "TTN",
                                   "ENSG00000155657",
                                   extra={"CADD_PHRED": 31, "REVEL": 0.85})]),
        synth.SVar("7", 8_000_000, "T", "A", gt="1/1", ad=(0, 40),
                   anns=[synth.Ann("A", "stop_gained", "HIGH", "MUC16",
                                   "ENSG00000181143",
                                   extra={"gnomADe_AF": 8e-6,
                                          "CADD_PHRED": 37})]),
        synth.SVar("X", 2_000_000, "C", "G", gt="0/1",
                   anns=[synth.Ann("G", "missense_variant", "MODERATE",
                                   "DMD", "ENSG00000198947",
                                   extra={"CADD_PHRED": 29, "REVEL": 0.8})]),
    ]
    vcf = synth.write_vcf(tmp_path / "real_pah.vcf", variants)
    truth = {"gene": "PAH",
             "pair": [{"pos": 102_890_000, "alt": "T"},
                      {"pos": 102_910_000, "alt": "A"}],
             "proband_hpo": proband_hpo}
    return vcf, truth


@pytest.mark.gate
def test_pah_pair_top_with_real_corpus(tmp_path):
    """Falsification: real HPO corpus doesn't discriminate - PAH can't beat
    decoys, meaning the phenotype stage is decoration, not signal."""
    vcf, truth = _real_pah_case(tmp_path)
    res = run_pipeline(vcf, truth["proband_hpo"],
                       obo_path=CORPUS / "hp.obo",
                       hpoa_path=CORPUS / "phenotype.hpoa",
                       g2d_path=CORPUS / "gene2disease.json")
    emitted = [h for h in res["ranked"] if h["emitted"]]
    assert emitted, "nothing emitted"
    top = emitted[0]
    assert top["gene"] == "PAH" and top["model"] == "compound_het"
    got = sorted((v["pos"], v["alt"]) for v in top["variants"])
    want = sorted((v["pos"], v["alt"]) for v in truth["pair"])
    assert got == want
    assert top["in_trans"] == "trans"
    assert top["pheno_score"] > 0, "real corpus gave zero phenotype score"


@pytest.mark.gate
def test_pah_decoys_below_floor(tmp_path):
    """Falsification: a decoy gene with zero real disease annotation crosses
    the emit floor - the floor depends on toy-gene absence, not scoring."""
    vcf, truth = _real_pah_case(tmp_path)
    res = run_pipeline(vcf, truth["proband_hpo"],
                       obo_path=CORPUS / "hp.obo",
                       hpoa_path=CORPUS / "phenotype.hpoa",
                       g2d_path=CORPUS / "gene2disease.json")
    emitted = {h["gene"] for h in res["ranked"] if h["emitted"]}
    assert emitted == {"PAH"}, f"unexpected emissions: {emitted}"
