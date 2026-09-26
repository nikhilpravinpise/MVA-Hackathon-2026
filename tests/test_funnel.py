"""Unit tests for funnel stages: extract_facts -> rarity -> damage tier ->
hypothesis enumeration -> scoring. Each test names its falsification
condition - a concrete bug it would catch.
"""
from __future__ import annotations

import pytest

from conftest import REPO  # noqa: F401  (sys.path setup side-effect)
from src import synth
from src.config import load_config
from src.genes import enumerate_hypotheses
from src.prioritize import rank_hypotheses
from src.triage import eligible, extract_facts
from src.vcf import VcfReader

CFG = load_config()


def _facts_for(svars, tmp_path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    vcf = synth.write_vcf(tmp_path / "t.vcf", svars)
    r = VcfReader(vcf)
    out = []
    try:
        for rec in r.records(sample="PROBAND01"):
            out.extend(extract_facts(rec, "PROBAND01", CFG))
    finally:
        r.close()
    return out


class TestExtractFacts:
    def test_csq_fields_mapped(self, tmp_path):
        """Falsification: CSQ parsing dropping/misaligning fields - a variant's
        SYMBOL/Consequence/AF land in the wrong VariantFacts fields."""
        v = [synth.SVar("7", 100, "A", "T",
                        anns=[synth.Ann("T", "stop_gained", "HIGH", "GENEX",
                                        "ENSGX", extra={"CADD_PHRED": 40,
                                                        "gnomADe_AF": 1e-5})])]
        f = _facts_for(v, tmp_path)
        assert len(f) == 1
        vf = f[0]
        assert vf.gene == "GENEX" and vf.consequence == "stop_gained"
        assert vf.cadd == 40.0 and vf.popmax_af == pytest.approx(1e-5)
        assert vf.damage_tier == "lof"

    def test_multi_gene_split(self, tmp_path):
        """Falsification: a variant overlapping two genes must emit one fact
        per gene - dropping a gene loses its hypotheses entirely."""
        v = [synth.SVar("7", 100, "A", "T", anns=[
            synth.Ann("T", "missense_variant", "MODERATE", "GA", "ENSGA"),
            synth.Ann("T", "stop_gained", "HIGH", "GB", "ENSGB")])]
        genes = {f.gene for f in _facts_for(v, tmp_path)}
        assert genes == {"GA", "GB"}

    def test_worst_transcript_wins_per_gene(self, tmp_path):
        """Falsification: representative-annotation pick keeps a benign
        transcript over a severe one on the same gene -> misses LoF."""
        v = [synth.SVar("7", 100, "A", "T", anns=[
            synth.Ann("T", "synonymous_variant", "LOW", "GA", "ENSGA"),
            synth.Ann("T", "stop_gained", "HIGH", "GA", "ENSGA")])]
        f = _facts_for(v, tmp_path)
        assert len(f) == 1 and f[0].consequence == "stop_gained"
        assert f[0].damage_tier == "lof"


class TestRarity:
    def test_absent_vs_present(self, tmp_path):
        """Falsification: absent-from-gnomAD not scored stronger than
        present-but-rare - the config's absent_is_stronger is dead."""
        v = [
            synth.SVar("7", 100, "A", "T",
                       anns=[synth.Ann("T", "missense_variant", "MODERATE",
                                       "GA", "G1")]),
            synth.SVar("7", 200, "A", "T",
                       anns=[synth.Ann("T", "missense_variant", "MODERATE",
                                       "GA", "G1",
                                       extra={"gnomADe_AF": 9e-5})]),
            synth.SVar("7", 300, "A", "T",
                       anns=[synth.Ann("T", "missense_variant", "MODERATE",
                                       "GA", "G1",
                                       extra={"gnomADe_AF": 0.5})]),
        ]
        f = sorted(_facts_for(v, tmp_path), key=lambda x: x.pos)
        assert f[0].absent and f[0].rare and f[0].rarity_score == 1.0
        assert f[1].rare and not f[1].absent and f[1].rarity_score < 1.0
        assert not f[2].rare

    def test_popmax_uses_subpops(self, tmp_path):
        """Falsification: pop-max ignoring subpopulation AFs - a variant
        'rare' overall but common in one population must not pass."""
        v = [synth.SVar("7", 100, "A", "T",
                        anns=[synth.Ann("T", "missense_variant", "MODERATE",
                                        "GA", "G1",
                                        extra={"gnomADe_AF": 1e-5,
                                               "gnomADe_FIN_AF": 0.02})])]
        f = _facts_for(v, tmp_path)[0]
        assert f.popmax_af == pytest.approx(0.02)
        assert not f.rare


class TestDamageTiers:
    def _mk(self, tmp_path, cons, extra, pos=100):
        v = [synth.SVar("7", pos, "A", "T",
                        anns=[synth.Ann("T", cons, "MODERATE", "GA", "G1",
                                        extra=extra)])]
        return _facts_for(v, tmp_path)[0]

    def test_damaging_missense_needs_votes(self, tmp_path):
        """Falsification: single-predictor missense upgraded to damaging -
        the ensemble rule degraded to any-vote."""
        f2 = self._mk(tmp_path, "missense_variant",
                      {"CADD_PHRED": 30, "REVEL": 0.9, "SIFT": "tolerated"})
        assert f2.damage_tier == "damaging_missense" and f2.damage_votes >= 2
        f1 = self._mk(tmp_path, "missense_variant",
                      {"CADD_PHRED": 30, "REVEL": 0.1,
                       "SIFT": "tolerated", "PolyPhen": "benign"}, pos=200)
        assert f1.damage_tier == "other"

    def test_spliceai_rescue(self, tmp_path):
        """Falsification: high-SpliceAI noncanonical variant not reaching the
        splice tier - deep-intronic splice alleles silently dropped."""
        f = self._mk(tmp_path, "splice_region_variant",
                     {"SpliceAI_pred_DS_AG": 0.8})
        assert f.damage_tier == "splice_altering"

    def test_clinvar_bonus(self, tmp_path):
        """Falsification: ClinVar P/LP not reflected in score/pathogenic flag."""
        f = self._mk(tmp_path, "missense_variant",
                     {"CLIN_SIG": "pathogenic", "CADD_PHRED": 30,
                      "REVEL": 0.9})
        assert f.clinsig_pathogenic and f.score > 0.8


class TestQC:
    def test_filter_and_genotype_qc(self, tmp_path):
        """Falsification: non-PASS or low-depth calls surviving eligibility -
        junk QC leaking candidates into enumeration."""
        v = [
            synth.SVar("7", 100, "A", "T", filters=("LowQual",),
                       anns=[synth.Ann("T", "stop_gained", "HIGH", "GA", "G1")]),
            synth.SVar("7", 200, "A", "T", ad=(3, 1), dp=4, gq=9,
                       anns=[synth.Ann("T", "stop_gained", "HIGH", "GA", "G1")]),
        ]
        f = _facts_for(v, tmp_path)
        assert all(not x.qc_pass for x in f)
        assert not any(eligible(x, CFG) for x in f)
        assert "filter_not_pass" in f[0].qc_fails
        assert "low_dp" in f[1].qc_fails


class TestEnumeration:
    def test_comphet_pairs_enumerated(self, tmp_path):
        """Falsification: het x het pairs in one gene not enumerated - the
        core compound-het mechanic broken."""
        v = [
            synth.SVar("7", 100, "A", "T", gt="0/1",
                       anns=[synth.Ann("T", "stop_gained", "HIGH", "GA", "G1")]),
            synth.SVar("7", 200, "G", "C", gt="0/1",
                       anns=[synth.Ann("C", "missense_variant", "MODERATE",
                                       "GA", "G1",
                                       extra={"CADD_PHRED": 30,
                                              "REVEL": 0.9})]),
        ]
        facts = _facts_for(v, tmp_path)
        hyps = enumerate_hypotheses(facts, CFG)
        ch = [h for h in hyps if h.model == "compound_het"]
        assert len(ch) == 1 and {x.pos for x in ch[0].variants} == {100, 200}

    def test_hom_and_dominant_models(self, tmp_path):
        """Falsification: hom_alt/dominant enumeration missing models."""
        v = [synth.SVar("7", 100, "A", "T", gt="1/1", ad=(0, 40),
                        anns=[synth.Ann("T", "stop_gained", "HIGH", "GA", "G1")])]
        hyps = enumerate_hypotheses(_facts_for(v, tmp_path), CFG)
        models = {h.model for h in hyps}
        assert "hom_alt" in models

    def test_no_cross_gene_pairs(self, tmp_path):
        """Falsification: hets in DIFFERENT genes paired - physically
        impossible trans hypothesis emitted."""
        v = [
            synth.SVar("7", 100, "A", "T", gt="0/1",
                       anns=[synth.Ann("T", "stop_gained", "HIGH", "GA", "G1")]),
            synth.SVar("7", 200, "G", "C", gt="0/1",
                       anns=[synth.Ann("C", "stop_gained", "HIGH", "GB", "G2")]),
        ]
        hyps = enumerate_hypotheses(_facts_for(v, tmp_path), CFG)
        assert all(h.model != "compound_het" or
                   len({x.gene for x in h.variants}) == 1 for h in hyps)
        assert not any(h.model == "compound_het" and
                       h.gene not in ("GA", "GB") for h in hyps)


class TestRanking:
    def test_epcr_monotone_and_bounded(self, tmp_path):
        """Falsification: epcr non-monotone, out of (0,1], or rank 1 not at
        the configured top - the submission ordering contract broken."""
        ranked = rank_hypotheses(
            enumerate_hypotheses(
                _facts_for(synth.spike_variants(), tmp_path), CFG), CFG)
        epcrs = [h.epcr for h in ranked]
        assert epcrs == sorted(epcrs, reverse=True)
        assert ranked[0].epcr == CFG["scoring"]["epcr_top"]
        assert all(0 < e <= 1 for e in epcrs)
        assert all(epcrs[i] > epcrs[i + 1] for i in range(len(epcrs) - 1))

    def test_deterministic_order(self, tmp_path):
        """Falsification: reruns produce different hypothesis orderings -
        hidden nondeterminism (dict/set iteration leaking into output)."""
        a = rank_hypotheses(
            enumerate_hypotheses(
                _facts_for(synth.spike_variants(), tmp_path / "a"), CFG), CFG)
        b = rank_hypotheses(
            enumerate_hypotheses(
                _facts_for(synth.spike_variants(), tmp_path / "b"), CFG), CFG)
        assert [h.pair_key for h in a] == [h.pair_key for h in b]
