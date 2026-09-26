"""ACMG/AMP evidence evaluation for the primary pair (plan.md Phase 4).

The Track-1 report needs the *criteria math* for the primary hypothesis,
not a black-box call. This module implements a curated, explicitly-ruled
subset of Richards 2015 (PMID 25741868) criteria mapped onto the
Tavtigian 2018 point system (PMID 29300386) - every assignment is
recomputable from the emitted rationale strings.

Criteria implemented (deliberately narrow, defensible):

* PVS1 (+8, very strong) - damage_tier 'lof' AND the caller asserts
  lof_mechanism for the gene. The flag is caller-supplied because
  mechanism is gene biology, not variant annotation; when not asserted a
  caveat notes PVS1 was withheld rather than guessed.
* PM2 (+2, moderate) - allele ABSENT from gnomAD (gnomad_present False).
* PM2_P (+1, supporting) - present in gnomAD but popmax <= RARE_AF (1e-4).
* BS1 (-4, benign strong) - popmax >= BS1_AF (5e-3): clearly too common
  for an ultra-rare recessive disorder. Between RARE_AF and BS1_AF no
  frequency criterion fires (indeterminate zone, documented).
* PP3 (+1, supporting) - >=2 computational damage votes among the four
  quantitative predictors: CADD>=20, REVEL>=0.5, AlphaMissense>=0.564,
  SpliceAI>=0.5 (same thresholds as config.consequence.predictors).
* BP4 (-1, benign supporting) - damage_tier 'other' AND votes <=1 AND no
  ClinVar assertion at all.
* PM3 (+2) / PM3_Strong (+4) - pair level only (evaluate_pair): recessive
  mechanism + in_trans == 'trans' + the OTHER allele established
  pathogenic (clinsig_pathogenic or damage_tier 'lof'). PM3_Strong when
  BOTH alleles are established P/LP. Awarded to the variant under
  evaluation whose partner is pathogenic (Richards usage: a novel allele
  earns PM3 in trans with a known-pathogenic one).
* PP4 (+1, supporting) - pair level: pheno_score >= PP4_PHENO_MIN (0.6,
  the frozen BMA HPO similarity cutoff; chosen a-priori, documented here
  and in the report).

Point table (Tavtigian 2018; benign side negative):

    PVS1            +8   very strong
    PS*, PM3_Strong +4   strong
    PM2, PM3        +2   moderate
    PM2_P, PP3, PP4 +1   supporting
    BP4             -1   benign supporting
    BS1             -4   benign strong
    BA1             -8   benign stand-alone (reserved; not emitted here)

Classification bands on the summed points:

    >=10  Pathogenic
    6..9  Likely pathogenic
    0..5  VUS
    -1..-6 Likely benign
    <=-7  Benign

The pair-level combined score sums both variants' criteria plus
pair-level PP4 - it is a *hypothesis-level* aggregate for ranking/report,
explicitly NOT a clinical-grade per-variant classification (see caveats
in every report dict).
"""
from __future__ import annotations

import dataclasses
from .triage import VariantFacts

# --- point system (see module docstring for the full table) -------------
STRENGTH_POINTS = {
    "very_strong": 8,
    "strong": 4,
    "moderate": 2,
    "supporting": 1,
    "benign_supporting": -1,
    "benign_strong": -4,
    "benign_standalone": -8,
}

CLASSIFICATION_BANDS = (
    (10, "Pathogenic"),
    (6, "Likely pathogenic"),
    (0, "VUS"),
    (-6, "Likely benign"),
    (-float("inf"), "Benign"),
)

RARE_AF = 1e-4        # matches config rarity.af_max
BS1_AF = 5e-3         # 'too common for a rare recessive disorder' floor
PP4_PHENO_MIN = 0.6   # BMA HPO similarity cutoff for PP4

# Computational damage votes for PP3: the four quantitative predictors.
_PRED_THRESHOLDS = (
    ("cadd", 20.0, "CADD>=20"),
    ("revel", 0.5, "REVEL>=0.5"),
    ("alphamissense", 0.564, "AlphaMissense>=0.564"),
    ("spliceai", 0.5, "SpliceAI>=0.5"),
)

_RULE_TABLE = (
    "Richards2015 criteria subset scored on Tavtigian2018 points: "
    "PVS1=8, strong=4 (PM3_Strong), moderate=2 (PM2,PM3), supporting=1 "
    "(PM2_P,PP3,PP4); benign: BP4=-1, BS1=-4, BA1=-8. Bands: >=10 P, "
    "6-9 LP, 0-5 VUS, -1..-6 LB, <=-7 B.")


def _crit(code: str, strength: str, rationale: str) -> dict:
    return {"code": code, "strength": strength,
            "points": STRENGTH_POINTS[strength], "rationale": rationale}


def _pred_votes(vf: VariantFacts) -> tuple[int, list[str]]:
    """Count quantitative computational damage votes (PP3 evidence)."""
    hits = []
    for attr, thr, label in _PRED_THRESHOLDS:
        v = getattr(vf, attr, None)
        if v is not None and v >= thr:
            hits.append(label)
    return len(hits), hits


def _established_pathogenic(vf: VariantFacts) -> bool:
    """'Established' pathogenic for PM3 partner checks: ClinVar P/LP or a
    predicted-LoF allele (a LoF allele in a recessive gene is treated as
    the canonical pathogenic partner per Richards/ClinGen PM3 usage)."""
    return vf.clinsig_pathogenic or vf.damage_tier == "lof"


def _finish(res: dict) -> dict:
    """Recompute points + classification on a criteria list (in place)."""
    res["points"] = sum(c["points"] for c in res["criteria"])
    res["points_map"] = {c["code"]: c["points"] for c in res["criteria"]}
    res["classification"] = classification(res["points_map"])
    return res


def evaluate_variant(vf: VariantFacts, ctx: dict | None = None) -> dict:
    """Assign per-variant criteria from the curated subset.

    ``ctx`` keys (all optional):
      lof_mechanism  bool - gene disease mechanism permits PVS1 (default
                     False: PVS1 is withheld, never guessed)
      rare_af        float - PM2_P ceiling (default 1e-4)
      bs1_af         float - BS1 floor (default 5e-3)

    Returns a JSON-able dict: variant vid, criteria list
    [{code, strength, points, rationale}], predictor votes, total points,
    per-variant classification, caveats.
    """
    ctx = ctx or {}
    lof_mech = bool(ctx.get("lof_mechanism", False))
    rare_af = float(ctx.get("rare_af", RARE_AF))
    bs1_af = float(ctx.get("bs1_af", BS1_AF))
    criteria: list[dict] = []
    caveats: list[str] = []

    # --- consequence / PVS1 -------------------------------------------
    if vf.damage_tier == "lof":
        if lof_mech:
            criteria.append(_crit(
                "PVS1", "very_strong",
                f"{vf.consequence} predicted LoF in a gene where LoF is "
                f"an asserted disease mechanism"))
        else:
            caveats.append(
                "damage_tier='lof' but lof_mechanism not asserted by "
                "caller - PVS1 withheld (mechanism is gene biology, not "
                "annotation)")

    # --- frequency axis ------------------------------------------------
    if not vf.gnomad_present:
        criteria.append(_crit(
            "PM2", "moderate", "absent from gnomAD exomes+genomes"))
    elif vf.popmax_af is not None:
        if vf.popmax_af >= bs1_af:
            criteria.append(_crit(
                "BS1", "benign_strong",
                f"popmax AF {vf.popmax_af:g} >= {bs1_af:g} - too common "
                f"for a rare recessive disorder"))
        elif vf.popmax_af <= rare_af:
            criteria.append(_crit(
                "PM2_P", "supporting",
                f"popmax AF {vf.popmax_af:g} <= {rare_af:g} - rare"))

    # --- computational evidence ---------------------------------------
    votes, hits = _pred_votes(vf)
    if votes >= 2:
        criteria.append(_crit(
            "PP3", "supporting",
            f"{votes} computational damage votes ({', '.join(hits)})"))
    if (vf.damage_tier == "other" and votes <= 1
            and not vf.clin_sig):
        criteria.append(_crit(
            "BP4", "benign_supporting",
            "no damage signal: 'other' tier, <=1 predictor vote, no "
            "ClinVar assertion"))

    res = {"variant": vf.vid, "gene": vf.gene,
           "consequence": vf.consequence, "damage_tier": vf.damage_tier,
           "clinsig_pathogenic": vf.clinsig_pathogenic,
           "predictor_votes": votes, "predictor_hits": hits,
           "criteria": criteria, "caveats": caveats}
    return _finish(res)


def evaluate_pair(h1_variants: list[VariantFacts] | tuple,
                  mechanism: str = "recessive",
                  in_trans: str = "unknown",
                  pheno_score: float = 0.0,
                  gene_known_for_disease: bool = False,
                  lof_mechanism: bool | None = None) -> dict:
    """Pair-level evaluation of a genotype hypothesis (1-2 variants).

    Adds the criteria that only exist at pair level:

    * PM3/PM3_Strong - recessive mechanism AND in_trans=='trans' AND the
      partner allele is established pathogenic. Awarded per variant whose
      partner qualifies; PM3_Strong (+4) replaces PM3 when BOTH alleles
      are established P/LP. cis or unknown phase -> never fires (the
      whole point of the phasing gate; falsification: a cis pair must not
      show PM3).
    * PP4 - pheno_score >= 0.6 (PP4_PHENO_MIN): the proband's HPO set is
      highly specific to the gene's disease. Pair-level, added once.

    ``lof_mechanism`` defaults to (mechanism == 'recessive'): canonical
    recessive disease is biallelic LoF; dominant/x-linked callers should
    pass it explicitly. Returns per-variant evaluate_variant dicts plus
    pair_criteria, a merged points_breakdown, and the combined
    hypothesis-level classification.
    """
    variants = list(h1_variants)
    if lof_mechanism is None:
        lof_mechanism = mechanism == "recessive"
    ctx = {"lof_mechanism": lof_mechanism}
    results = [evaluate_variant(vf, ctx) for vf in variants]
    caveats: list[str] = []

    # --- PM3: only meaningful biallelic, only provable in trans --------
    both_established = (len(variants) >= 2
                        and all(_established_pathogenic(v) for v in variants))
    if mechanism == "recessive" and in_trans == "trans":
        for i, res in enumerate(results):
            partners = [v for j, v in enumerate(variants) if j != i]
            if partners and all(_established_pathogenic(p)
                                for p in partners):
                if both_established:
                    res["criteria"].append(_crit(
                        "PM3_Strong", "strong",
                        "both alleles established P/LP, observed in "
                        "trans"))
                else:
                    res["criteria"].append(_crit(
                        "PM3", "moderate",
                        "in trans with an established pathogenic allele"))
                _finish(res)
    elif mechanism == "recessive" and in_trans != "trans":
        caveats.append(
            f"in_trans='{in_trans}': PM3 not applicable without proven "
            f"trans phase")

    # --- pair-level phenotype evidence ---------------------------------
    pair_criteria: list[dict] = []
    if pheno_score >= PP4_PHENO_MIN:
        pair_criteria.append(_crit(
            "PP4", "supporting",
            f"phenotype score {pheno_score:.3f} >= {PP4_PHENO_MIN}: "
            f"proband HPO highly specific to this gene's disease"))

    points_map: dict[str, int] = {}
    for res in results:
        for c in res["criteria"]:
            points_map[c["code"]] = points_map.get(c["code"], 0) + c["points"]
    for c in pair_criteria:
        points_map[c["code"]] = points_map.get(c["code"], 0) + c["points"]

    caveats.append(
        "combined score aggregates evidence across both alleles - a "
        "hypothesis-level call for ranking, not a per-variant clinical "
        "classification")
    if not gene_known_for_disease:
        caveats.append(
            "gene-disease validity not externally asserted; phenotype "
            "match is computational (HPO semantic similarity)")

    return {
        "mechanism": mechanism, "in_trans": in_trans,
        "lof_mechanism": lof_mechanism,
        "gene_known_for_disease": gene_known_for_disease,
        "pheno_score": pheno_score,
        "variants": results,
        "pair_criteria": pair_criteria,
        "points_breakdown": points_map,
        "combined_points": sum(points_map.values()),
        "combined_classification": classification(points_map),
        "rule_table": _RULE_TABLE,
        "caveats": caveats,
    }


def classification(points: dict) -> str:
    """Map a {criterion_code: signed_points} dict to a Richards class.

    Bands (Tavtigian-2018 point adaptation, see module docstring):
    >=10 Pathogenic, 6-9 Likely pathogenic, 0-5 VUS, -1..-6 Likely
    benign, <=-7 Benign.
    """
    total = sum(points.values())
    for floor, label in CLASSIFICATION_BANDS:
        if total >= floor:
            return label
    return "Benign"


def _as_vf(v) -> VariantFacts:
    """Coerce a VariantFacts or a pipeline-dict variant into VariantFacts."""
    if isinstance(v, VariantFacts):
        return v
    if isinstance(v, dict):
        d = dict(v)
        if "tier" in d and "damage_tier" not in d:
            d["damage_tier"] = d.pop("tier")
        keep = {f.name for f in dataclasses.fields(VariantFacts)}
        # required positional fields of VariantFacts get safe defaults so a
        # partial pipeline dict (tier/popmax/consequence only) still coerces
        base = {}
        for fld in dataclasses.fields(VariantFacts):
            if fld.default is dataclasses.MISSING and \
                    fld.default_factory is dataclasses.MISSING:
                base[fld.name] = 0 if fld.name == "pos" else ""
        base.update({k: val for k, val in d.items() if k in keep})
        return VariantFacts(**base)
    raise TypeError(f"cannot coerce {type(v)} to VariantFacts")


def _model_to_mechanism(model: str) -> str:
    return {
        "compound_het": "recessive",
        "hom_alt": "recessive",
        "dominant_het": "dominant",
        "x_linked": "x_linked",
    }.get(model or "", "recessive")


def acmg_report(hypothesis_dict_or_variants, ctx: dict | None = None) -> dict:
    """Full JSON-able ACMG report for the Track-1 report's criteria table.

    Accepts a Hypothesis object, a pipeline ``ranked`` dict (variants as
    plain dicts are coerced; note tier->damage_tier mapping), or a bare
    list/tuple of VariantFacts. ``ctx`` overrides for evaluate_pair:
    mechanism, in_trans, pheno_score, gene_known_for_disease,
    lof_mechanism. Deterministic: same inputs -> byte-identical JSON.
    """
    ctx = dict(ctx or {})
    gene = ""
    model = ""
    if isinstance(hypothesis_dict_or_variants, dict):
        h = hypothesis_dict_or_variants
        gene = h.get("gene", "")
        model = h.get("model", "")
        variants = [_as_vf({"gene": gene, **v})
                    for v in h.get("variants", [])]
        ctx.setdefault("in_trans", h.get("in_trans", "unknown"))
        ctx.setdefault("pheno_score", h.get("pheno_score", 0.0))
    elif hasattr(hypothesis_dict_or_variants, "variants"):
        h = hypothesis_dict_or_variants
        gene = getattr(h, "gene", "")
        model = getattr(h, "model", "")
        variants = [_as_vf(v) for v in h.variants]
        ctx.setdefault("in_trans", getattr(h, "in_trans", "unknown"))
        ctx.setdefault("pheno_score", getattr(h, "pheno_score", 0.0))
    else:
        variants = [_as_vf(v) for v in hypothesis_dict_or_variants]
        gene = variants[0].gene if variants else ""
    ctx.setdefault("mechanism", _model_to_mechanism(model))

    pair = evaluate_pair(variants, **{
        k: ctx[k] for k in ("mechanism", "in_trans", "pheno_score",
                            "gene_known_for_disease", "lof_mechanism")
        if k in ctx})
    return {
        "framework": "ACMG/AMP Richards2015 subset + Tavtigian2018 points",
        "gene": gene, "model": model,
        "n_variants": len(variants),
        "variants": pair["variants"],
        "pair_criteria": pair["pair_criteria"],
        "points_breakdown": pair["points_breakdown"],
        "combined_points": pair["combined_points"],
        "combined_classification": pair["combined_classification"],
        "rule_table": pair["rule_table"],
        "caveats": pair["caveats"],
    }
