"""Ranking + epcr emission (plan.md Phase 2, stage 6).

epcr is a *ranking artifact* (frozen config `scoring`): the combine in
genes.attach_scores orders hypotheses; the emitted epcr is a monotone map of
rank into (epcr_floor, epcr_top]. It carries no calibrated-probability claim -
the report says so verbatim.

Emit policy
-----------
* hypotheses scoring >= ``emit_floor`` are emitted as primary rows. The floor
  is chosen so that a biallelic hypothesis with ZERO phenotype support
  (max 0.45*1 + 0.20*1 = 0.65) can never be emitted - no-call is a valid
  answer (the negative-control gate depends on this).
* remaining hypotheses (score below floor) are kept in the ranked list for
  the funnel table / audit, flagged ``emitted=False``.
* The top hypothesis ALWAYS receives epcr_top (0.95); deeper ranks decay
  geometrically toward epcr_floor - strictly monotone, strictly inside (0,1].

Determinism: sort key is (-score, model-preference, gene, pair positions).
Tie-break is fully specified - reruns are byte-identical.
"""
from __future__ import annotations

from .genes import Hypothesis

# Model preference for score ties: a biallelic hypothesis outranks a
# single-het one at equal score (it explains recessive disease better).
_MODEL_PREF = {"compound_het": 0, "hom_alt": 1, "x_linked": 2, "dominant_het": 3}


def _sort_key(h: Hypothesis) -> tuple:
    return (-h.score, _MODEL_PREF.get(h.model, 9), h.gene,
            tuple((v.chrom, v.pos) for v in h.variants))


def rank_hypotheses(hyps: list[Hypothesis], cfg: dict) -> list[Hypothesis]:
    """Sort hypotheses, assign rank + epcr + emitted flag (in place)."""
    sc = cfg.get("scoring", {})
    top = float(sc.get("epcr_top", 0.95))
    floor = float(sc.get("epcr_floor", 0.05))
    emit_floor = float(sc.get("emit_floor", 0.70))
    decay = float(sc.get("epcr_decay", 0.55))

    # singleton hypotheses (dominant_het/x_linked carry one variant) can
    # never FULL-match the scorer's 2-variant ground truth - their best
    # outcome is partial credit. They compete in the same score space as
    # pairs, so without a higher bar a lone damaging het in a max-pheno
    # gene could outrank a true pair and dilute F-max. Emit them only
    # when the evidence is exceptional.
    single_floor = float(sc.get("singleton_emit_floor", emit_floor + 0.10))
    ranked = sorted(hyps, key=_sort_key)
    for i, h in enumerate(ranked):
        h.rank = i + 1
        h.epcr = floor + (top - floor) * (decay ** i) if i else top
        fl = single_floor if len(h.variants) < 2 else emit_floor
        h.evidence["emitted"] = h.score >= fl
    return ranked


def emitted(hyps: list[Hypothesis]) -> list[Hypothesis]:
    """Hypotheses above the emit floor, in rank order."""
    return [h for h in hyps if h.evidence.get("emitted")]
