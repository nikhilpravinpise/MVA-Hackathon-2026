"""Triage stages of the Arm-B funnel: per-variant evidence extraction and tiers.

Design (plan.md Phase 2, stages 1-3). Every stage is a pure function over
``config/pipeline.yaml`` - no hidden knobs, fully deterministic, and every
decision is auditable from the emitted ``VariantFacts`` row.

Stages
------
0. ``extract_facts`` - flatten a VcfRecord into one :class:`VariantFacts` per
   (alt allele, gene). VEP emits one CSQ block per transcript; the SAME allele
   can hit several genes, so each gene keeps its own worst-consequence
   transcript. ``best`` is the maximally severe consequence for the funnel
   (a splice_acceptor transcript beats a synonymous one on the same allele).
1. Genotype QC - PASS filter, DP/GQ floors, VAF window for hets / hom-alts.
2. Rarity tier - pop-max AF across gnomAD exomes+genomes subpopulations.
   "Absent from gnomAD" is a distinct, stronger state than "present but rare"
   (``absent_is_stronger``), per the frozen config.
3. Consequence/damage tier - predicted LoF, damaging missense (ensemble vote,
   never a single predictor), splice-altering (SpliceAI rescue), or other.

A variant is a *candidate* when ``qc_pass and rare and tier != 'other_or_low'``
... actually any tier can still pair - eligibility is decided in genes.py via
``comphet_min_consequence`` so a splice/intronic allele CAN partner a LoF
(the leaked deep-intronic A>G scenario is exactly why).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .vcf import VcfRecord, SampleGenotype

# Ordered most-severe -> least-severe damage tiers.
TIERS = ("lof", "damaging_missense", "splice_altering", "other")

# Base damage score per tier (a-priori, documented as ranking heuristic -
# see config `scoring` section; NOT calibrated probabilities).
TIER_BASE = {
    "lof": 1.0,
    "damaging_missense": 0.8,
    "splice_altering": 0.65,
    "other": 0.2,
}

# Rough severity order over VEP Sequence-Ontology consequence strings.
# Used only to pick a variant's *representative* transcript per gene.
_SO_SEVERITY = [
    "transcript_ablation", "splice_acceptor_variant", "splice_donor_variant",
    "stop_gained", "frameshift_variant", "stop_lost", "start_lost",
    "initiator_codon_variant", "transcript_amplification",
    "inframe_deletion", "inframe_insertion", "missense_variant",
    "protein_altering_variant", "splice_donor_5th_base_variant",
    "splice_donor_region_variant", "splice_polypyrimidine_tract_variant",
    "splice_region_variant", "incomplete_terminal_codon_variant",
    "start_retained_variant", "stop_retained_variant", "synonymous_variant",
    "mature_miRNA_variant", "5_prime_UTR_variant", "3_prime_UTR_variant",
    "non_coding_transcript_exon_variant", "intron_variant",
    "NMD_transcript_variant", "non_coding_transcript_variant",
    "upstream_gene_variant", "downstream_gene_variant",
    "intergenic_variant", "regulatory_region_variant",
]
_SEVERITY_RANK = {t: i for i, t in enumerate(_SO_SEVERITY)}

_GNOMAD_AF_PREFIXES = ("gnomADe", "gnomADg")
_CLINVAR_PATHOGENIC_TOKENS = ("pathogenic", "likely_pathogenic")


def _f(v: Any) -> float | None:
    """Parse a CSQ numeric; '' or non-numeric -> None. Multi-values take max."""
    if v is None:
        return None
    vals = []
    for part in str(v).split("&"):
        try:
            vals.append(float(part))
        except (ValueError, TypeError):
            continue
    return max(vals) if vals else None


def _severity(consequence: str) -> int:
    """Severity rank of the worst SO term in a '&'-joined consequence cell."""
    terms = (consequence or "").split("&")
    return min((_SEVERITY_RANK.get(t, len(_SO_SEVERITY)) for t in terms),
               default=len(_SO_SEVERITY))


def _popmax_af(ann: dict[str, str]) -> tuple[float | None, bool]:
    """Max AF over all gnomAD subpopulation + pooled fields in one CSQ block.

    Returns (af, present). ``present=False`` means the allele is absent from
    gnomAD entirely - the stronger rarity state the config rewards.
    """
    vals = []
    for k, v in ann.items():
        for pfx in _GNOMAD_AF_PREFIXES:
            if k.startswith(pfx) and k.endswith("_AF"):
                f = _f(v)
                if f is not None:
                    vals.append(f)
    return (max(vals), True) if vals else (None, False)


def _spliceai_delta(ann: dict[str, str]) -> float | None:
    ds = [_f(ann.get(k)) for k in (
        "SpliceAI_pred_DS_AG", "SpliceAI_pred_DS_AL",
        "SpliceAI_pred_DS_DG", "SpliceAI_pred_DS_DL")]
    ds = [d for d in ds if d is not None]
    return max(ds) if ds else None


def _damage_votes(ann: dict[str, str], pred_cfg: dict) -> tuple[int, dict[str, bool]]:
    """Count independent damaging-missense predictor votes."""
    votes = {
        "cadd": (_f(ann.get("CADD_PHRED")) or -1) >= pred_cfg.get("cadd_phred_min", 20.0),
        "revel": (_f(ann.get("REVEL")) or -1) >= pred_cfg.get("revel_min", 0.5),
        "alphamissense": (_f(ann.get("AlphaMissense_score")) or -1)
            >= pred_cfg.get("alphamissense_min", 0.564),
        "sift": bool(pred_cfg.get("sift_deleterious", True))
            and str(ann.get("SIFT") or "").lower().startswith("deleterious"),
        "polyphen": bool(pred_cfg.get("polyphen_damaging", True))
            and "damaging" in str(ann.get("PolyPhen") or "").lower(),
    }
    return sum(votes.values()), votes


def _clinsig_pathogenic(clin_sig: str) -> bool:
    s = (clin_sig or "").lower()
    return any(t in s for t in _CLINVAR_PATHOGENIC_TOKENS) and "conflict" not in s


@dataclass(frozen=True)
class VariantFacts:
    """One (alt, gene) evidence record - the funnel's atom of truth."""

    chrom: str          # VCF-convention contig (bare, e.g. '15')
    pos: int
    ref: str
    alt: str
    gene: str           # SYMBOL ('' when CSQ carries none)
    gene_id: str        # Ensembl gene id
    transcript: str
    consequence: str    # worst SO term(s) on the chosen transcript
    impact: str
    biotype: str
    hgvsc: str = ""
    hgvsp: str = ""

    popmax_af: float | None = None
    gnomad_present: bool = False
    clin_sig: str = ""
    cadd: float | None = None
    revel: float | None = None
    alphamissense: float | None = None
    spliceai: float | None = None
    loeuf: float | None = None
    phylop: float | None = None
    sift: str = ""
    polyphen: str = ""

    gt: str = ""        # '0/1', '1/1', '0|1', ...
    is_het: bool = False
    is_hom_alt: bool = False
    dp: int | None = None
    gq: float | None = None
    vaf: float | None = None
    pgt: str | None = None
    pid: str | None = None
    alt_index: int = 1  # 1-based ALT ordinal this fact represents (multiallelic sites)

    qc_pass: bool = True
    qc_fails: tuple = ()
    rare: bool = False
    absent: bool = False
    rarity_score: float = 0.0
    damage_tier: str = "other"
    damage_votes: int = 0
    clinsig_pathogenic: bool = False
    score: float = 0.0  # variant-level evidence score in [0,1]

    @property
    def key(self) -> tuple[str, int, str, str]:
        return (self.chrom, self.pos, self.ref, self.alt)

    @property
    def vid(self) -> str:
        return f"{self.chrom}:{self.pos}:{self.ref}>{self.alt}"


def _genotype_fields(gt_obj: SampleGenotype | None,
                     alt_index: int = 1) -> dict:
    if gt_obj is None:
        return {"gt": "", "is_het": False, "is_hom_alt": False,
                "dp": None, "gq": None, "vaf": None, "pgt": None, "pid": None}
    raw_gt = gt_obj.raw.get("GT", "")
    return {
        "gt": raw_gt,
        "is_het": gt_obj.is_het,
        "is_hom_alt": gt_obj.is_hom_alt,
        "dp": gt_obj.dp,
        "gq": gt_obj.gq,
        "vaf": gt_obj.vaf(alt_index),
        "pgt": gt_obj.pgt,
        "pid": gt_obj.pid,
    }


def _qc(vf_is_het: bool, vf_is_hom: bool, rec_passed: bool,
        g: dict, qc_cfg: dict) -> tuple[bool, tuple]:
    fails = []
    if not rec_passed:
        fails.append("filter_not_pass")
    if g["dp"] is not None and g["dp"] < qc_cfg.get("min_dp", 0):
        fails.append("low_dp")
    if g["gq"] is not None and g["gq"] < qc_cfg.get("min_gq", 0):
        fails.append("low_gq")
    v = g["vaf"]
    if v is not None:
        if vf_is_het and not (qc_cfg.get("het_vaf_min", 0.0) <= v
                              <= qc_cfg.get("het_vaf_max", 1.0)):
            fails.append("het_vaf_outside")
        if vf_is_hom and v < qc_cfg.get("hom_vaf_min", 0.8):
            fails.append("hom_vaf_below")
    return (not fails, tuple(fails))


def _rarity(ann: dict[str, str], rar_cfg: dict) -> tuple[bool, bool, float, float | None]:
    """(rare, absent, rarity_score, popmax). Score: absent->1.0; else decays
    toward 0 as popmax approaches the AF ceiling."""
    popmax, present = _popmax_af(ann)
    af_max = rar_cfg.get("af_max", 1e-4)
    absent = not present
    rare = absent or (popmax is not None and popmax <= af_max)
    if absent:
        score = 1.0
    elif popmax is not None and popmax > 0:
        # log-scale position of popmax between 1e-7 (score~1) and af_max (~0.5)
        denom = math.log10(af_max / 1e-7) if af_max > 0 else 0.0
        if denom <= 0:
            # degenerate ceiling (af_max <= 1e-7): every present variant at
            # or under it is effectively at the ceiling floor
            score = 1.0 if popmax <= af_max else 0.5
        else:
            frac = min(1.0, math.log10(popmax / 1e-7) / denom)
            score = 1.0 - 0.5 * max(0.0, frac)
    else:
        score = 0.8  # present with AF 0 exactly
    return rare, absent, score, popmax


def _damage_tier(ann: dict[str, str], con_cfg: dict) -> tuple[str, int, dict]:
    cons = set((ann.get("Consequence") or "").split("&"))
    pred = con_cfg.get("predictors", {})
    votes, vote_detail = _damage_votes(ann, pred)
    sai = _spliceai_delta(ann)
    sai_hit = sai is not None and sai >= pred.get("spliceai_delta_min", 0.5)

    if cons & set(con_cfg.get("lof_terms", ())):
        tier = "lof"
    elif cons & set(con_cfg.get("missense_terms", ())) and votes >= con_cfg.get("min_votes", 2):
        tier = "damaging_missense"
    elif (cons & set(con_cfg.get("splice_region_terms", ())) and sai_hit) or \
            (sai_hit and not (cons & set(con_cfg.get("synonymous_terms", ())))):
        tier = "splice_altering"
    else:
        tier = "other"
    return tier, votes, vote_detail


def extract_facts(rec: VcfRecord, sample: str, cfg: dict) -> list[VariantFacts]:
    """Flatten one VcfRecord into VariantFacts per (alt, gene).

    A record with no CSQ annotations at all yields a single gene-less fact
    (it can still pass QC/rarity on raw fields - e.g. unannotated inputs).
    """
    qc_cfg = cfg.get("genotype_qc", {})
    rar_cfg = cfg.get("rarity", {})
    con_cfg = cfg.get("consequence", {})
    out: list[VariantFacts] = []

    for alt_i, alt in enumerate(rec.alts):
        anns = rec.csq_for_alt(alt) if rec._csq_fields else []
        # One representative annotation per gene: worst consequence.
        per_gene: dict[str, dict[str, str]] = {}
        for a in anns:
            gene = a.get("SYMBOL") or a.get("Gene") or ""
            cur = per_gene.get(gene)
            if cur is None or _severity(a.get("Consequence", "")) < _severity(
                    cur.get("Consequence", "")):
                per_gene[gene] = a
        if not per_gene:
            per_gene[""] = {}

        gt_obj = rec.samples.get(sample)
        for gene, ann in sorted(per_gene.items()):
            gt_idx = alt_i + 1
            g = _genotype_fields(gt_obj, gt_idx)
            # restrict het/hom flags to THIS alt index in multi-allelic sites
            if gt_obj is not None and gt_obj.called:
                g["is_het"] = gt_idx in gt_obj.gt and len(set(gt_obj.gt)) >= 2
                g["is_hom_alt"] = all(x == gt_idx for x in gt_obj.gt)
            rare, absent, rscore, popmax = _rarity(ann, rar_cfg)
            tier, votes, _vd = _damage_tier(ann, con_cfg)
            qc_pass, qc_fails = _qc(g["is_het"], g["is_hom_alt"],
                                    rec.passed, g, qc_cfg)
            cadd = _f(ann.get("CADD_PHRED"))
            revel = _f(ann.get("REVEL"))
            am = _f(ann.get("AlphaMissense_score"))
            sai = _spliceai_delta(ann)
            clin = ann.get("CLIN_SIG") or ""
            cp = _clinsig_pathogenic(clin)

            # Variant-level evidence score: tier base modulated by rarity
            # (absent is stronger), plus a small ClinVar P/LP bonus.
            rfac = 1.0 if absent else 0.9
            score = min(1.0, TIER_BASE[tier] * rfac + (0.05 if cp else 0.0))

            out.append(VariantFacts(
                chrom=rec.chrom, pos=rec.pos, ref=rec.ref, alt=alt,
                gene=gene, gene_id=ann.get("Gene") or "",
                transcript=ann.get("Feature") or "",
                consequence=ann.get("Consequence") or "",
                impact=ann.get("IMPACT") or "", biotype=ann.get("BIOTYPE") or "",
                hgvsc=ann.get("HGVSc") or "", hgvsp=ann.get("HGVSp") or "",
                popmax_af=popmax, gnomad_present=(not absent), clin_sig=clin,
                cadd=cadd, revel=revel, alphamissense=am, spliceai=sai,
                loeuf=_f(ann.get("LOEUF")), phylop=_f(ann.get("phyloP")),
                sift=ann.get("SIFT") or "", polyphen=ann.get("PolyPhen") or "",
                gt=g["gt"], is_het=g["is_het"], is_hom_alt=g["is_hom_alt"],
                dp=g["dp"], gq=g["gq"], vaf=g["vaf"],
                pgt=g["pgt"], pid=g["pid"],
                qc_pass=qc_pass, qc_fails=qc_fails,
                rare=rare, absent=absent, rarity_score=rscore,
                damage_tier=tier, damage_votes=votes,
                clinsig_pathogenic=cp, score=score, alt_index=gt_idx))
    return out


def eligible(vf: VariantFacts, cfg: dict, min_tier: str = "other") -> bool:
    """Candidate eligibility: QC + rarity + at least ``min_tier`` damage."""
    if not (vf.qc_pass and vf.rare):
        return False
    return TIERS.index(vf.damage_tier) <= TIERS.index(min_tier)
