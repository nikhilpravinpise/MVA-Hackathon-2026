"""Tests for src/genes.py::attach_scores - inheritance-bonus gating.

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch.
"""
from __future__ import annotations

from src.config import load_config
from src.genes import Hypothesis, attach_scores
from src.triage import VariantFacts


def _vf(gene="GENEX", pos=1000, alt="T", score=1.0):
    return VariantFacts(
        chrom="7", pos=pos, ref="A", alt=alt, gene=gene, gene_id="ENSG0X",
        transcript="ENST0X", consequence="stop_gained", impact="HIGH",
        biotype="protein_coding", is_het=True, score=score)


def _hyp(model, in_trans, gene="GENEX", n_variants=2):
    variants = tuple(_vf(gene=gene, pos=1000 + i * 4000)
                     for i in range(n_variants))
    return Hypothesis(gene=gene, model=model, variants=variants,
                      in_trans=in_trans)


def test_cis_confirmed_comphet_loses_inheritance_bonus():
    """Falsification: a compound_het pair PROVEN cis (one haplotype, not
    biallelic) must not earn the same inheritance_score as a trans pair -
    fails if in_trans is recorded as evidence but never consulted by
    scoring, letting a biologically invalid compound-het rank as if trans
    had been confirmed."""
    cfg = load_config()
    cis = attach_scores([_hyp("compound_het", "cis")],
                        lambda g: 0.0, cfg)[0]
    trans = attach_scores([_hyp("compound_het", "trans")],
                          lambda g: 0.0, cfg)[0]
    unknown = attach_scores([_hyp("compound_het", "unknown")],
                            lambda g: 0.0, cfg)[0]
    assert cis.inheritance_score == 0.0
    assert trans.inheritance_score > 0.0
    assert unknown.inheritance_score == trans.inheritance_score
    assert cis.score < trans.score


def test_noise_gene_loses_inheritance_bonus():
    """Falsification: a hypothesis in a documented negative-control noise
    gene (config negative_control.noise_genes, e.g. TTN) must not earn
    recessive-model credit - fails if the config list is loaded but never
    consulted, leaving the negative-control gate to depend purely on
    incidental score arithmetic elsewhere."""
    cfg = load_config()
    noise_gene = cfg["negative_control"]["noise_genes"][0]
    noisy = attach_scores([_hyp("hom_alt", "unknown", gene=noise_gene,
                                n_variants=1)],
                          lambda g: 0.0, cfg)[0]
    clean = attach_scores([_hyp("hom_alt", "unknown", gene="GENEX",
                                n_variants=1)],
                          lambda g: 0.0, cfg)[0]
    assert noisy.inheritance_score == 0.0
    assert clean.inheritance_score > 0.0
    assert noisy.score < clean.score
