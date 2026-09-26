"""Gene-level inheritance aggregation (plan.md Phase 2, stage 4).

The funnel does not rank variants - it ranks *genotype hypotheses*, matching
the submission format exactly (a compound-het pair occupies ONE CSV row).
For every gene with candidate variants (QC+ rare + tier-permitted, see
triage.eligible) we enumerate the biologically meaningful hypotheses:

* ``compound_het`` - every unordered het_A x het_B pair in the gene
* ``hom_alt``      - each homozygous-alt candidate
* ``dominant_het`` - each heterozygote proposed alone
* ``x_linked``     - heterozygotes/hemizygotes on chrX (sex unknown ->
                     reported but not boosted)

Noise control: genes with > ``max_hets_per_gene`` eligible hets have their
het pool truncated to the top-scoring ones before pair enumeration
(O(n^2) blow-up guard - documented in config, not silent).

in_trans is resolved via :mod:`src.phasing` PGT/PID and recorded as
evidence on the hypothesis. It does not feed the answer-blind ranking
inputs (damage/phenotype), but a ``compound_het`` hypothesis PROVEN cis is
not a valid recessive call at all (basic Mendelian genetics, not
answer-peeking) - such pairs lose their compound_het inheritance bonus so
they cannot rank as if trans had been confirmed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from . import phasing
from .triage import VariantFacts, TIERS, eligible


@dataclass
class Hypothesis:
    """A gene-level genotype hypothesis - the object that gets ranked."""
    gene: str
    model: str                       # compound_het|hom_alt|dominant_het|x_linked
    variants: tuple[VariantFacts, ...]  # 1 or 2
    variant_damage: float = 0.0      # max variant score in the hypothesis
    pheno_score: float = 0.0
    inheritance_score: float = 0.0
    in_trans: str = "unknown"        # 'trans'|'cis'|'unknown'
    phase_detail: str = ""
    score: float = 0.0
    rank: int = 0
    epcr: float = 0.0
    evidence: dict = field(default_factory=dict)

    @property
    def pair_key(self) -> tuple:
        return tuple(v.key for v in self.variants)

    def summary(self) -> str:
        vs = " + ".join(v.vid for v in self.variants)
        return (f"{self.gene} [{self.model}] {vs} "
                f"score={self.score:.3f} trans={self.in_trans}")


def _by_gene(facts: list[VariantFacts]) -> dict[str, list[VariantFacts]]:
    groups: dict[str, list[VariantFacts]] = {}
    for vf in facts:
        if vf.gene:
            groups.setdefault(vf.gene, []).append(vf)
    return groups


def enumerate_hypotheses(facts: list[VariantFacts], cfg: dict,
                         min_tier: str = "other") -> list[Hypothesis]:
    """Enumerate all genotype hypotheses from candidate VariantFacts."""
    inh = cfg.get("inheritance", {})
    models = set(inh.get("models", ("compound_het", "hom_alt",
                                    "dominant_het", "x_linked")))
    min_tier = inh.get("comphet_min_consequence", min_tier)
    cap = int(inh.get("max_hets_per_gene", 60))

    cand = [vf for vf in facts if vf.gene and eligible(vf, cfg, min_tier)]
    hyps: list[Hypothesis] = []

    for gene, vfs in sorted(_by_gene(cand).items()):
        hets = [v for v in vfs if v.is_het]
        homs = [v for v in vfs if v.is_hom_alt]
        truncated = False
        if len(hets) > cap:
            hets = sorted(hets, key=lambda v: (-v.score, v.pos))[:cap]
            truncated = True

        if "compound_het" in models:
            for a, b in combinations(
                    sorted(hets, key=lambda v: (v.pos, v.alt)), 2):
                if a.key == b.key:
                    continue
                ph = phasing.determine_phase(a, b)
                hyps.append(Hypothesis(
                    gene=gene, model="compound_het", variants=(a, b),
                    in_trans=ph.relation, phase_detail=ph.detail,
                    evidence={"truncated_het_pool": truncated}))
        if "hom_alt" in models:
            for h in homs:
                hyps.append(Hypothesis(gene=gene, model="hom_alt",
                                       variants=(h,)))
        if "dominant_het" in models:
            for h in hets:
                hyps.append(Hypothesis(gene=gene, model="dominant_het",
                                       variants=(h,)))
        if "x_linked" in models:
            for h in hets + homs:
                if h.chrom.upper() == "X":
                    hyps.append(Hypothesis(gene=gene, model="x_linked",
                                           variants=(h,)))
    return hyps


def attach_scores(hyps: list[Hypothesis],
                  pheno_of_gene, cfg: dict) -> list[Hypothesis]:
    """Fill variant_damage/pheno/inheritance/score on each hypothesis.

    ``pheno_of_gene`` maps SYMBOL -> [0,1] HPO semantic score (already
    computed by the caller; genes with no disease annotation score 0).
    """
    sc = cfg.get("scoring", {})
    w_d = sc.get("w_variant_damage", 0.45)
    w_p = sc.get("w_phenotype", 0.35)
    w_i = sc.get("w_inheritance", 0.20)
    bonus = sc.get("inheritance_bonus", {})
    noise_genes = set(cfg.get("negative_control", {}).get("noise_genes", ()))

    for h in hyps:
        h.variant_damage = max(v.score for v in h.variants)
        h.pheno_score = pheno_of_gene(h.gene)
        if h.model == "compound_het" and h.in_trans == "cis":
            # Phasing proved the pair is on one haplotype - not a valid
            # biallelic hit, so it earns no recessive-model credit.
            h.inheritance_score = 0.0
            h.evidence["cis_confirmed_invalid_comphet"] = True
        else:
            h.inheritance_score = bonus.get(h.model, 0.0)
        if h.gene in noise_genes:
            # Documented negative-control gene list (config
            # negative_control.noise_genes): genes famous for spurious
            # rare-LoF hits get no recessive-model credit either.
            h.inheritance_score = 0.0
            h.evidence["noise_gene"] = True
        h.score = (w_d * h.variant_damage + w_p * h.pheno_score
                   + w_i * h.inheritance_score)
        h.evidence["weights"] = {"damage": w_d, "pheno": w_p, "inh": w_i}
    return hyps
