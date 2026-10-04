"""End-to-end Arm-B funnel orchestration.

    VCF --extract--> VariantFacts --filter--> candidates --group-->
    Hypotheses --score--> ranked --emit--> results/

Every stage writes its counts into the funnel table (the report's Table 1
regenerates from this file - no hand-typed stats). Ablations are expressed as
evidence-drop flags (plan.md 2.1.3): drop a source, rerun, compare ranks.
"""
from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .config import config_dict_hash, config_hash, load_config
from .genes import Hypothesis, attach_scores, enumerate_hypotheses
from .loci import in_artifact_locus, validate_artifact_loci
from .pheno import (InformationContent, OboOntology, best_match_average,
                    gene_disease_map, gene_hpo_terms, load_hpoa)
from .prioritize import emitted, rank_hypotheses
from .triage import VariantFacts, eligible, extract_facts
from .vcf import VcfReader

ABLATION_SOURCES = ("gnomad", "damage_predictors", "clinvar", "hpo", "phasing")


@dataclass
class FunnelCounts:
    """Per-stage variant/hypothesis counts - the monotonicity audit."""
    stage_counts: dict = field(default_factory=dict)

    def check_monotonic(self) -> list[str]:
        """Return a list of violations (empty = clean). Stage outputs must be
        non-increasing among fact-level filters: one VCF record legitimately
        yields SEVERAL (alt x gene) facts, so 'records' is excluded - the
        funnel may fan out at extraction but must never grow after it."""
        order = ["alt_gene_facts", "qc_pass", "rare", "candidates",
                 "locus_masked"]
        prev = None
        bad = []
        for s in order:
            v = self.stage_counts.get(s)
            if v is None:
                continue
            if prev is not None and v > prev:
                bad.append(f"{s}={v} > prev={prev}")
            prev = v
        return bad


def _vcf_sha(vcf_path) -> str | None:
    """SHA-256 of the input VCF bytes (streamed - a real WGS file is GBs,
    hash it in chunks). Provenance so 'sha-tracked' is literal."""
    import hashlib
    try:
        h = hashlib.sha256()
        with open(vcf_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def load_corpus(obo_path=None, hpoa_path=None, g2d_path=None):
    """Load the phenotype corpus: ontology, disease->HPO, gene->diseases."""
    ont = OboOntology.parse(obo_path) if obo_path else OboOntology()
    disease2hpo = load_hpoa(hpoa_path) if hpoa_path else {}
    g2d = gene_disease_map(g2d_path) if g2d_path else {}
    return ont, disease2hpo, g2d


def make_pheno_scorer(proband_hpo: list[str], ont: OboOntology,
                      disease2hpo: dict, g2d: dict,
                      drop_hpo: bool = False,
                      cfg_ph: dict | None = None):
    """Build the gene -> [0,1] phenotype score callable.

    ``score.stats`` reports how many proband terms the ontology actually
    recognized - a proband set that fully drops silently scores every
    gene 0, which looks like a legitimate negative."""
    ph_cfg = cfg_ph or {}
    enabled = ph_cfg.get("enabled", True)  # consumed: phenotype.enabled
    ic_floor = float(ph_cfg.get("ic_floor", 0.0))
    qset = set(proband_hpo)
    dropped = sorted(t for t in qset if not ont.valid(t))
    stats = {"n_query_terms": len(qset),
             "n_recognized": len(qset) - len(dropped),
             "dropped_terms": dropped}
    if drop_hpo or not proband_hpo or not enabled:
        zero = lambda gene: 0.0
        zero.stats = stats
        return zero
    ic = InformationContent.from_annotations(
        [set(v) for v in disease2hpo.values() if v], ont)

    def score(gene: str) -> float:
        terms = gene_hpo_terms(gene, g2d, disease2hpo)
        if not terms:
            return 0.0
        return best_match_average(ont, ic, qset, terms,
                                  ic_floor=ic_floor)
    score.stats = stats
    return score


def _apply_ablation(facts: list[VariantFacts], drops: set[str],
                    cfg: dict) -> list[VariantFacts]:
    """Recompute eligibility/score with an evidence source removed.

    Honest ablation semantics:
      gnomAD            -> rarity filter can't fire; every QC-pass fact is
                         'rare' at neutral rarity_score (the funnel leans on
                         consequence+phenotype alone)
      damage_predictors -> missense votes zeroed; only consequence class and
                         SpliceAI remain (missense collapses to 'other')
      clinvar           -> ClinVar bonus removed
      hpo               -> pheno_score=0 for all genes (handled downstream)
      phasing           -> in_trans left 'unknown' (evidence only)
    """
    if not drops:
        return facts
    rar_cfg = cfg.get("rarity", {})
    con_cfg = dict(cfg.get("consequence", {}))
    if "damage_predictors" in drops:
        con_cfg["predictors"] = {}
        con_cfg["min_votes"] = 99
    out = []
    for vf in facts:
        if "gnomad" in drops:
            rare, absent, rscore, popmax = True, False, 0.5, vf.popmax_af
        else:
            # re-derive from the stored annotation-equivalent fields;
            # 'absent' still requires gnomad_annotated (coverage unknown
            # is not absence)
            absent = vf.gnomad_annotated and not vf.gnomad_present
            af_max = rar_cfg.get("af_max", 1e-4)
            rare = absent or (vf.popmax_af is not None
                              and vf.popmax_af <= af_max)
            # same formula as triage._rarity's absent branch
            rscore = (min(1.0, 0.5 + float(rar_cfg.get("absent_bonus", 0.5)))
                      if absent else vf.rarity_score)
            popmax = vf.popmax_af
        cons = set((vf.consequence or "").split("&"))
        votes = 0 if "damage_predictors" in drops else vf.damage_votes
        pred = con_cfg.get("predictors", {})
        sai = vf.spliceai or 0.0
        sai_hit = sai >= pred.get("spliceai_delta_min", 0.5)
        # tier assignment goes through triage.tier_from_fields - the ONE
        # implementation - so an ablation can't drift from baseline
        # semantics (the splice rescue is unconditional there too)
        from .triage import TIER_BASE, tier_from_fields
        tier = tier_from_fields(cons, votes, sai_hit, con_cfg)
        cp = False if "clinvar" in drops else vf.clinsig_pathogenic
        # same rfac rule as extract_facts' score block
        rfac = 0.9
        if absent:
            rfac = 1.0 if rar_cfg.get("absent_is_stronger", True) else 0.95
        score = min(1.0, TIER_BASE[tier] * rfac + (0.05 if cp else 0.0))
        out.append(VariantFacts(**{**asdict(vf),
                                   "rare": rare, "absent": absent,
                                   "rarity_score": rscore, "popmax_af": popmax,
                                   "damage_tier": tier, "damage_votes": votes,
                                   "clinsig_pathogenic": cp, "score": score}))
    return out


def run_pipeline(vcf_path: str | Path, proband_hpo: list[str],
                 obo_path=None, hpoa_path=None, g2d_path=None,
                 cfg: dict | None = None, cfg_path=None,
                 sample: str | None = None,
                 drops: frozenset[str] = frozenset(),
                 out_dir: str | Path | None = None) -> dict:
    """Run the funnel; return the results dict (also written to out_dir).

    ``drops`` names ablation sources (ABLATION_SOURCES). Output keys:
    ranked (all hypotheses), emitted, funnel counts, config hash, provenance.
    """
    t0 = time.time()
    cfg = cfg or load_config(cfg_path)
    validate_artifact_loci(cfg)
    ont, disease2hpo, g2d = load_corpus(obo_path, hpoa_path, g2d_path)
    pheno_of_gene = make_pheno_scorer(
        proband_hpo, ont, disease2hpo, g2d,
        drop_hpo="hpo" in drops, cfg_ph=cfg.get("phenotype"))

    counts = FunnelCounts()
    facts: list[VariantFacts] = []
    reader = VcfReader(vcf_path)
    if sample is None:
        sample = reader.samples[0] if reader.samples else ""
    elif reader.samples and sample not in reader.samples:
        reader.close()
        raise ValueError(
            f"sample {sample!r} not in VCF (samples: {reader.samples}) - "
            "a misspelled sample name would produce a silent zero-genotype "
            "run, not a real result")
    try:
        n_records = 0
        for rec in reader.records(sample=sample):
            n_records += 1
            facts.extend(extract_facts(rec, sample, cfg))
    finally:
        reader.close()
    # duplicate VCF records produce duplicate facts -> duplicate
    # hypotheses -> wasted CSV rows; collapse exact (key, gene) dupes
    seen_facts: set[tuple] = set()
    deduped: list[VariantFacts] = []
    for f in facts:
        sig = (f.key, f.gene)
        if sig in seen_facts:
            continue
        seen_facts.add(sig)
        deduped.append(f)
    if len(deduped) != len(facts):
        counts.stage_counts["duplicate_facts_dropped"] = \
            len(facts) - len(deduped)
        facts = deduped

    counts.stage_counts["records"] = n_records
    counts.stage_counts["alt_gene_facts"] = len(facts)
    counts.stage_counts["qc_pass"] = sum(1 for f in facts if f.qc_pass)

    facts_abl = _apply_ablation(facts, set(drops), cfg)
    # 'rare' counts rarity among QC-passing facts only - rarity over the
    # unconditioned pool makes 'rare > qc_pass' a false monotonicity
    # violation (a filtered-but-absent variant is rare yet not qc_pass).
    # It must count facts_abl, not facts: under --drop gnomad the ablation
    # sets rare=True on every QC-pass fact ('rarity neutralized'), and
    # comparing candidates-from-abl against a baseline 'rare' count is a
    # spurious candidates>rare violation on top of a wrong stage number.
    counts.stage_counts["rare"] = sum(1 for f in facts_abl
                                      if f.qc_pass and f.rare)
    cand = [f for f in facts_abl if eligible(f, cfg,
            cfg.get("inheritance", {}).get("comphet_min_consequence", "other"))]
    # candidates that can actually enter a hypothesis: gene-assigned AND
    # carrying the ALT (ref-ref or gene-less facts are honest funnel
    # attrition, not hypothesis input)
    counts.stage_counts["candidates"] = sum(
        1 for f in cand
        if f.gene and (f.is_het or f.is_hom_alt or f.is_hemi))

    # Artifact-locus mask: declared low-mappability loci (extended MHC et
    # al., config `artifact_loci`) exit the funnel here - disclosed as a
    # stage so the removal is auditable in the funnel table, not hidden.
    masked = [f for f in cand
              if not in_artifact_locus(f.chrom, f.pos, cfg)]
    counts.stage_counts["locus_masked"] = sum(
        1 for f in masked
        if f.gene and (f.is_het or f.is_hom_alt or f.is_hemi))
    counts.stage_counts["locus_masked_out"] = (
        counts.stage_counts["candidates"]
        - counts.stage_counts["locus_masked"])

    hyps = enumerate_hypotheses(masked, cfg)
    attach_scores(hyps, pheno_of_gene, cfg)
    if "phasing" in drops:
        bonus = cfg.get("scoring", {}).get("inheritance_bonus", {})
        for h in hyps:
            if h.model == "compound_het":
                h.in_trans = "unknown"
                h.phase_detail = "ablated: phasing evidence removed"
                if h.evidence.pop("cis_confirmed_invalid_comphet", None):
                    # the cis penalty was applied during attach_scores -
                    # with phasing evidence removed the pair gets its
                    # unphased-model credit back and its score recomputed.
                    # A noise_gene zeroing is independent of phasing and
                    # must NOT be restored by this block.
                    if not h.evidence.get("noise_gene"):
                        h.inheritance_score = bonus.get(h.model, 0.0)
                        sc = cfg.get("scoring", {})
                        h.score = (sc.get("w_variant_damage", 0.45)
                                   * h.variant_damage
                                   + sc.get("w_phenotype", 0.35)
                                   * h.pheno_score
                                   + sc.get("w_inheritance", 0.20)
                                   * h.inheritance_score)
    ranked = rank_hypotheses(hyps, cfg)
    counts.stage_counts["hypotheses"] = len(ranked)
    counts.stage_counts["emitted"] = len(emitted(ranked))
    mono = counts.check_monotonic()

    result = {
        "provenance": {
            "vcf": str(vcf_path), "sample": sample,
            "config_file_sha256": config_hash() if cfg_path is None
                                   else "n/a (dict-supplied)",
            "config_sha256": config_dict_hash(cfg),
            # the effective rarity ceiling (a CLI --af-max override lands in
            # the dict hash but would otherwise be invisible in the artifact)
            "af_max": cfg.get("rarity", {}).get("af_max"),
            "vcf_sha256": _vcf_sha(vcf_path),
            "pheno_terms": getattr(pheno_of_gene, "stats", None),
            "drops": sorted(drops),
            "runtime_sec": round(time.time() - t0, 3),
            "corpus": {"obo": str(obo_path), "hpoa": str(hpoa_path),
                       "g2d": str(g2d_path)},
        },
        "funnel": counts.stage_counts,
        "monotonicity_violations": mono,
        "ranked": [_hyp_to_dict(h) for h in ranked],
        "emitted": [h.rank for h in emitted(ranked)],
    }
    if out_dir:
        od = Path(out_dir)
        od.mkdir(parents=True, exist_ok=True)
        (od / "result.json").write_text(json.dumps(result, indent=1))
        (od / "funnel_counts.json").write_text(
            json.dumps(counts.stage_counts, indent=1))
        (od / "hypotheses.tsv").write_text(_hyp_tsv(ranked))
    return result


def _hyp_to_dict(h: Hypothesis) -> dict:
    return {
        "rank": h.rank, "gene": h.gene, "model": h.model,
        "score": round(h.score, 4), "epcr": round(h.epcr, 4),
        "variant_damage": round(h.variant_damage, 4),
        "pheno_score": round(h.pheno_score, 4),
        "inheritance_score": h.inheritance_score,
        "in_trans": h.in_trans, "emitted": h.evidence.get("emitted", False),
        "variants": [
            {"chrom": v.chrom, "pos": v.pos, "ref": v.ref, "alt": v.alt,
             "consequence": v.consequence, "tier": v.damage_tier,
             "damage_votes": v.damage_votes, "score": round(v.score, 4),
             "absent": v.absent, "gnomad_present": v.gnomad_present,
             "gnomad_annotated": v.gnomad_annotated,
             "clinsig_pathogenic": v.clinsig_pathogenic,
             "clin_sig": v.clin_sig,
             "popmax_af": v.popmax_af, "gt": v.gt, "pgt": v.pgt, "pid": v.pid,
             "cadd": v.cadd, "revel": v.revel,
             "alphamissense": v.alphamissense, "spliceai": v.spliceai,
             "hgvsc": v.hgvsc, "hgvsp": v.hgvsp}
            for v in h.variants],
        "phase_detail": h.phase_detail,
        # CSV notes carry the one-line justification a human reviewer
        # needs at a glance: model, proven phase, consequence classes,
        # then HGVS (protein preferred, else coding) so a reviewer can
        # identify the alleles without reopening the VCF
        "notes": (
            f"{h.gene} {h.model}"
            + {"trans": " trans", "cis": " cis"}.get(h.in_trans, "")
            + (" " + "+".join(dict.fromkeys(
                (v.consequence or "?").split("&")[0]
                for v in h.variants)))
            + (" " + "+".join(
                (v.hgvsp or v.hgvsc or "").split(":")[-1] or v.vid
                for v in h.variants))
        ).strip(),
        # evidence flags (truncated_het_pool / noise_gene / cis-invalidated)
        # must reach the artifact - 'documented in config' is not the same
        # as visible in results
        "evidence": {k: v for k, v in h.evidence.items()
                     if k != "emitted"},
    }


def _hyp_tsv(ranked: list[Hypothesis]) -> str:
    head = ("rank\tgene\tmodel\tscore\tepcr\tdamage\tpheno\tinh\ttrans\t"
            "emitted\tvariants\n")
    lines = [head]
    for h in ranked:
        vs = ";".join(v.vid for v in h.variants)
        lines.append(
            f"{h.rank}\t{h.gene}\t{h.model}\t{h.score:.4f}\t{h.epcr:.4f}\t"
            f"{h.variant_damage:.4f}\t{h.pheno_score:.4f}\t"
            f"{h.inheritance_score}\t{h.in_trans}\t"
            f"{h.evidence.get('emitted', False)}\t{vs}\n")
    return "".join(lines)
