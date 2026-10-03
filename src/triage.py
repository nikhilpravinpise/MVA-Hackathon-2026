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
from dataclasses import dataclass
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


def _popmax_af(ann: dict[str, str]) -> tuple[float | None, bool, bool]:
    """Max AF over all gnomAD subpopulation + pooled fields in one CSQ block.

    Returns (af, present, annotated). ``present=False`` means no AF value
    parsed; ``annotated`` distinguishes "gnomAD fields existed in the CSQ
    format" (truly absent allele) from "the annotation never queried
    gnomAD" (coverage unknown - must not earn absent-allele credit)."""
    vals = []
    annotated = False
    for k, v in ann.items():
        for pfx in _GNOMAD_AF_PREFIXES:
            if k.startswith(pfx) and k.endswith("_AF"):
                annotated = True  # field key present even if value is '.'
                f = _f(v)
                if f is not None:
                    vals.append(f)
    return (max(vals), True, annotated) if vals else (None, False, annotated)


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
        # SIFT/PolyPhen arrive as '&'-joined per-transcript calls
        # ('deleterious(0)&tolerated(0.9)') - scan every token so a
        # damaging call hidden behind a tolerated one still votes; and
        # only PolyPhen's *damaging* class words count ('possibly_damaging'
        # is the weak class, not a full vote)
        "sift": bool(pred_cfg.get("sift_deleterious", True))
            and any(t.startswith("deleterious")
                    for t in str(ann.get("SIFT") or "").lower().split("&")),
        "polyphen": bool(pred_cfg.get("polyphen_damaging", True))
            and any(t.startswith("probably_damaging")
                    for t in str(ann.get("PolyPhen") or "").lower().split("&")),
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
    # True only when the CSQ annotation actually carried gnomAD AF fields -
    # 'absent' vs 'gnomAD never queried' are different evidence states
    gnomad_annotated: bool = True
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
    # hemizygous (haploid GT like '1' on chrX/chrM/male calls) - carried
    # ALT but NOT a diploid homozygote; never enumerates as hom_alt
    is_hemi: bool = False
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
                "is_hemi": False,
                "dp": None, "gq": None, "vaf": None, "pgt": None, "pid": None}
    raw_gt = gt_obj.raw.get("GT", "")
    return {
        "gt": raw_gt,
        "is_het": gt_obj.is_het,
        "is_hom_alt": gt_obj.is_hom_alt,
        "is_hemi": False,  # caller overrides for haploid calls
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


def _rarity(ann: dict[str, str], rar_cfg: dict
            ) -> tuple[bool, bool, bool, float, float | None]:
    """(rare, absent, annotated, rarity_score, popmax). Score: absent->1.0;
    else decays toward 0 as popmax approaches the AF ceiling.

    ``absent`` requires ``annotated`` - a CSQ block with no gnomAD fields
    at all is 'coverage unknown', not 'allele absent from gnomAD'; such a
    variant earns no absent-allele rarity credit (conservative)."""
    popmax, present, annotated = _popmax_af(ann)
    af_max = rar_cfg.get("af_max", 1e-4)
    absent = annotated and not present
    rare = absent or (popmax is not None and popmax <= af_max)
    if absent:
        # absent_bonus: the rarity premium for never-observed alleles
        # (default 0.5 -> score 1.0 = the historical ceiling)
        score = min(1.0, 0.5 + float(rar_cfg.get("absent_bonus", 0.5)))
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
    return rare, absent, annotated, score, popmax


def tier_from_fields(cons: set[str], votes: int, sai_hit: bool,
                     con_cfg: dict) -> str:
    """Consequence tokens + predictor votes + SpliceAI flag -> damage tier.

    The single source of truth for tier assignment - ``_damage_tier`` (from
    a raw annotation dict) and ``pipeline._apply_ablation`` (from stored
    fact fields) both call this, so an ablation run can never diverge from
    the baseline tier semantics.
    """
    if cons & set(con_cfg.get("lof_terms", ())):
        return "lof"
    if cons & set(con_cfg.get("missense_terms", ())) \
            and votes >= con_cfg.get("min_votes", 2):
        return "damaging_missense"
    if (cons & set(con_cfg.get("splice_region_terms", ())) and sai_hit) \
            or sai_hit:
        # high SpliceAI rescues ANY consequence class (deep-exonic cryptic
        # splice on a 'synonymous' allele is biologically real) - the config
        # documents this; excluding synonymous would silently lose it
        return "splice_altering"
    return "other"


def _damage_tier(ann: dict[str, str], con_cfg: dict) -> tuple[str, int, dict]:
    cons = set((ann.get("Consequence") or "").split("&"))
    pred = con_cfg.get("predictors", {})
    votes, vote_detail = _damage_votes(ann, pred)
    sai = _spliceai_delta(ann)
    sai_hit = sai is not None and sai >= pred.get("spliceai_delta_min", 0.5)
    return tier_from_fields(cons, votes, sai_hit, con_cfg), votes, vote_detail


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
        # Per-field predictor evidence is taken as the MAX across that
        # gene's transcript rows: a variant benign on the worst-severity
        # transcript but damaging on another must not lose its predictor
        # votes (audit H-4 - the severity pick and the evidence pick are
        # different columns of different rows).
        per_gene: dict[str, dict[str, str]] = {}
        gene_rows: dict[str, list[dict[str, str]]] = {}
        for a in anns:
            gene = a.get("SYMBOL") or a.get("Gene") or ""
            gene_rows.setdefault(gene, []).append(a)
            cur = per_gene.get(gene)
            if cur is None or _severity(a.get("Consequence", "")) < _severity(
                    cur.get("Consequence", "")):
                per_gene[gene] = a
        # numeric evidence fields where max-across-transcripts is the
        # conservative choice. gnomAD AFs belong here too: the AF is an
        # ALLELE-level value, not transcript-level, so a blank on the
        # worst-severity row while a sibling carries '0.5' would
        # fabricate 'absent' (PM2 vs BS1 - a 6-point ACMG swing). MAX is
        # the safe direction: a documented common allele stays common.
        _EVIDENCE_MAX = {"CADD_PHRED", "REVEL", "AlphaMissense_score",
                         "SpliceAI_pred_DS_AG", "SpliceAI_pred_DS_AL",
                         "SpliceAI_pred_DS_DG", "SpliceAI_pred_DS_DL",
                         "phyloP", "LOEUF"}
        _AF_FIELDS = {k for rows in gene_rows.values() for a in rows
                      for k in a if "_AF" in k}
        for gene, rows in gene_rows.items():
            if len(rows) < 2:
                continue
            base = per_gene[gene]
            for fld in _EVIDENCE_MAX | _AF_FIELDS:
                best, bv = base.get(fld), _f(base.get(fld))
                for a in rows:
                    if a is base:
                        continue
                    av = _f(a.get(fld))
                    if av is not None and (bv is None or av > bv):
                        best, bv = a.get(fld), av
                base[fld] = best if best is not None else ""
            # categorical damage calls: take the most damaging seen on
            # any transcript for the same reason
            for cat, order in (
                    ("SIFT", ("deleterious", "tolerated")),
                    ("PolyPhen", ("probably_damaging", "possibly_damaging",
                                  "benign"))):
                def _rank(v: str) -> int:
                    for i, w in enumerate(order):
                        if str(v).lower().startswith(w):
                            return i
                    return len(order)
                base[cat] = min((a.get(cat) or "" for a in rows),
                                key=_rank)
        if not per_gene:
            per_gene[""] = {}

        gt_obj = rec.samples.get(sample)
        for gene, ann in sorted(per_gene.items()):
            gt_idx = alt_i + 1
            g = _genotype_fields(gt_obj, gt_idx)
            # restrict het/hom flags to THIS alt index in multi-allelic sites
            if gt_obj is not None and gt_obj.called:
                if len(gt_obj.gt) == 1:
                    # haploid call (male chrX / chrM convention '1'):
                    # hemizygous - NOT a diploid homozygote. A chrM/chrY/
                    # autosomal haploid ALT must not enumerate as hom_alt
                    # (biallelic model) - it goes to x_linked on X or the
                    # het-pool elsewhere (audit M-4).
                    g["is_het"] = False
                    g["is_hom_alt"] = False
                    g["is_hemi"] = gt_obj.gt[0] == gt_idx
                else:
                    g["is_het"] = (gt_idx in gt_obj.gt
                                   and len(set(gt_obj.gt)) >= 2)
                    g["is_hom_alt"] = all(x == gt_idx for x in gt_obj.gt)
            rare, absent, annotated, rscore, popmax = _rarity(ann, rar_cfg)
            tier, votes, _vd = _damage_tier(ann, con_cfg)
            # filters_allowed is the consumed FILTER gate: a record passes
            # when FILTER is clean (PASS/.) or every filter name is in the
            # allowed list (e.g. 'q10' tolerated when configured)
            allowed = set(qc_cfg.get("filters_allowed", ["PASS"]))
            filt_ok = rec.passed or all(
                f in allowed for f in rec.filters)
            qc_pass, qc_fails = _qc(
                g["is_het"], g["is_hom_alt"] or g["is_hemi"],
                filt_ok, g, qc_cfg)
            cadd = _f(ann.get("CADD_PHRED"))
            revel = _f(ann.get("REVEL"))
            am = _f(ann.get("AlphaMissense_score"))
            sai = _spliceai_delta(ann)
            clin = ann.get("CLIN_SIG") or ""
            cp = _clinsig_pathogenic(clin)

            # Variant-level evidence score: tier base modulated by rarity
            # (absent is stronger when the knob says so), plus a small
            # ClinVar P/LP bonus.
            rfac = 0.9
            if absent:
                rfac = 1.0 if rar_cfg.get("absent_is_stronger", True) \
                    else 0.95
            score = min(1.0, TIER_BASE[tier] * rfac + (0.05 if cp else 0.0))

            out.append(VariantFacts(
                chrom=rec.chrom, pos=rec.pos, ref=rec.ref, alt=alt,
                gene=gene, gene_id=ann.get("Gene") or "",
                transcript=ann.get("Feature") or "",
                consequence=ann.get("Consequence") or "",
                impact=ann.get("IMPACT") or "", biotype=ann.get("BIOTYPE") or "",
                hgvsc=ann.get("HGVSc") or "", hgvsp=ann.get("HGVSp") or "",
                popmax_af=popmax, gnomad_present=(popmax is not None),
                gnomad_annotated=annotated, clin_sig=clin,
                cadd=cadd, revel=revel, alphamissense=am, spliceai=sai,
                loeuf=_f(ann.get("LOEUF")), phylop=_f(ann.get("phyloP")),
                sift=ann.get("SIFT") or "", polyphen=ann.get("PolyPhen") or "",
                gt=g["gt"], is_het=g["is_het"], is_hom_alt=g["is_hom_alt"],
                is_hemi=g["is_hemi"],
                dp=g["dp"], gq=g["gq"], vaf=g["vaf"],
                pgt=g["pgt"], pid=g["pid"],
                qc_pass=qc_pass, qc_fails=qc_fails,
                rare=rare, absent=absent, rarity_score=rscore,
                damage_tier=tier, damage_votes=votes,
                clinsig_pathogenic=cp, score=score, alt_index=gt_idx))
    # SYMBOL fallback ('SYMBOL or Gene') can split one gene into two
    # groups when one transcript row has a SYMBOL and a sibling has only
    # the ENSG id - the id-named fact then forms an alien 'gene' (pheno
    # 0, duplicate hypotheses). Drop the id-named fact only when a
    # symbolic fact carries the SAME gene_id - a variant annotating gene
    # A (symbolic) plus an unrelated symbol-less gene B must keep B
    # (audit R5: gene B is a real gene, not a split duplicate).
    by_key: dict[tuple, list[VariantFacts]] = {}
    for f in out:
        by_key.setdefault(f.key, []).append(f)
    drop: set[int] = set()
    for fs in by_key.values():
        if len(fs) < 2:
            continue
        id_like = [f for f in fs if f.gene and f.gene == f.gene_id]
        sym_ids = {f.gene_id for f in fs if f.gene and f.gene != f.gene_id}
        for f in id_like:
            if f.gene_id in sym_ids:
                drop.add(id(f))
    if drop:
        out = [f for f in out if id(f) not in drop]
    return out


def eligible(vf: VariantFacts, cfg: dict, min_tier: str = "other") -> bool:
    """Candidate eligibility: QC + rarity + at least ``min_tier`` damage."""
    if not (vf.qc_pass and vf.rare):
        return False
    return TIERS.index(vf.damage_tier) <= TIERS.index(min_tier)
