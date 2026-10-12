"""Mechanism-direction safety layer (added post-L2-freeze, disease-agnostic).

The L2 engine ranks approved candidates by *evidence density*.  For a
chromosomal-instability disease that is not enough: genotoxic, aneugenic,
antimitotic and spindle-checkpoint-weakening agents are evidence-dense yet
pharmacologically push the disease mechanism the wrong way
(docs/track2/evidence/mechanism.json "contraindications", rejected.json).

This module classifies every approved candidate as::

    opposed  - at least one opposed rule fired: the candidate is REMOVED
               from the ranked list into ``excluded_mechanism_opposed``
               (with its would-be rank kept for transparency)
    aligned  - no opposed rule fired; at least one aligned rule fired
    neutral  - no rule fired

Rules are data, not code: they live in ``config/track2.yaml`` under
``direction.rules`` and each carries a one-line reason plus PMIDs already
resolved in the evidence files.  A rule can match on three channels:

    moa_patterns    regexes over ``mechanism_of_action`` text joined with
                    the drug's action_type strings (Open Targets
                    mechanismsOfAction.actionType, ChEMBL
                    mechanism.action_type)
    name_patterns   regexes over the drug's collected names - needed for
                    cytotoxics whose MoA text is empty in every source
                    (e.g. cyclophosphamide, epirubicin)
    target_genes    gene symbols.  A hit counts against the drug's
                    curated mechanism targets (``moa_targets``, Open
                    Targets rows) and/or its module-gene interactions.
                    ``require_inhibitory`` restricts the hit to genes
                    whose interaction evidence is inhibitory - a per-edge
                    DGIdb type ("inhibitor"/"antagonist"/...) or a curated
                    OT MoA row with an INHIBITOR-family action_type.
                    This is what keeps e.g. dasatinib out of the
                    SAC-kinase rule: its AURKB edge carries no inhibitory
                    annotation, it is a loose interaction, not its
                    mechanism.  ``activator_only`` instead requires an
                    activating edge type (metformin -> PRKAA 'activator').

``direction_reasons`` lists every rule that fired, so a drug matching
both aligned and opposed rules shows the conflict; ``opposed`` always
wins (safety-first).
"""
from __future__ import annotations

import re

INHIBITORY = {"inhibitor", "antagonist", "blocker", "suppressor",
              "negative modulator", "inverse agonist", "inactivator",
              "inhibitory", "degrader", "inhibits", "cytotoxic"}
ACTIVATING = {"activator", "agonist", "potentiator", "stimulator",
              "positive modulator", "inducer", "partial agonist",
              "activates", "chaperone"}


def _typed(types, vocab):
    return any(t and t.lower() in vocab for t in types)


class Rule:
    """One compiled direction rule (see config/track2.yaml)."""

    __slots__ = ("id", "direction", "reason", "cites", "moa_re",
                 "name_re", "genes", "require_inhibitory", "activator_only")

    def __init__(self, spec):
        self.id = spec["id"]
        self.direction = spec["direction"]
        self.reason = spec.get("reason", "")
        self.cites = list(spec.get("cites", []))
        self.moa_re = [re.compile(p, re.I)
                       for p in spec.get("moa_patterns", [])]
        self.name_re = [re.compile(p, re.I)
                        for p in spec.get("name_patterns", [])]
        self.genes = set(spec.get("target_genes", []))
        self.require_inhibitory = bool(spec.get("require_inhibitory"))
        self.activator_only = bool(spec.get("activator_only"))


def compile_rules(cfg):
    """Config ``direction.rules`` -> [Rule]; [] when disabled/absent."""
    d = cfg.get("direction") or {}
    if not d.get("enabled", True):
        return []
    return [Rule(r) for r in d.get("rules", [])]


def _gene_hit(cand, rule):
    """Rule-gene match, honouring per-edge action-type requirements."""
    moa_actions = cand.get("moa_target_actions") or {}
    hit_types = cand.get("hit_types") or {}
    hits = []
    for g in sorted(rule.genes):
        actions = [a for a in moa_actions.get(g, [])]
        types = list(hit_types.get(g, []))
        if rule.activator_only:
            ok = _typed(types, ACTIVATING) or _typed(actions, ACTIVATING)
        elif rule.require_inhibitory:
            ok = _typed(types, INHIBITORY) or _typed(actions, INHIBITORY)
        else:
            ok = bool(actions) or g in (cand.get("targets") or []) \
                or g in (cand.get("module_targets") or [])
        if ok:
            hits.append(g)
    return hits


def classify(cand, rules):
    """-> (direction, [fired rule ids]).

    ``cand`` needs: drug, names (iterable), mechanism_of_action,
    action_types, targets, module_targets, moa_target_actions, hit_types.
    """
    names = " ; ".join(sorted(set(cand.get("names") or [cand.get("drug")])))
    moa_text = " ; ".join(
        [cand.get("mechanism_of_action") or ""] +
        sorted(cand.get("action_types") or []))
    fired = []
    for rule in rules:
        if any(p.search(moa_text) for p in rule.moa_re):
            fired.append(rule.id)
            continue
        if any(p.search(names) for p in rule.name_re):
            fired.append(rule.id)
            continue
        if _gene_hit(cand, rule):
            fired.append(rule.id)
    direction = "neutral"
    for rule in rules:
        if rule.id in fired and rule.direction == "aligned":
            direction = "aligned"
        if rule.id in fired and rule.direction == "opposed":
            direction = "opposed"   # opposed wins over aligned
            break
    return direction, sorted(fired)


# ------------------------------------------------------ pediatric flag ---
# openFDA label "8.4 Pediatric Use" text -> coarse pediatric flag.
# Evaluated sentence by sentence: an explicit POSITIVE pediatric statement
# (established/indicated/approved in children) wins even when another
# sentence is negative - e.g. sirolimus "not established <13y ... have been
# established for renal transplant in children >=13y" -> labeled.
_POP = re.compile(r"pediatric|children|child\b|adolescen|infant|neonat|"
                  r"\bbirth\b|years? of age|months? of age|\bage \d|\baged?\s*\d|"
                  r"years? (of age )?(and|or) older|years? and older|"
                  r"year[s]? old", re.I)
_POSVERB = re.compile(r"established|is indicated|are indicated|indicated for|"
                      r"indicated under|approved for|recommended for use|"
                      r"demonstrated|supported by evidence|"
                      r"dosage schedule", re.I)
_NEGWORD = re.compile(r"\bnot\b|\bno\b|\bnever\b|contraindicat|"
                      r"should not be|do not use|risk of", re.I)
_NEGATED_ANY = re.compile(
    r"not (been )?established|assessed,? but not established|"
    r"has not been (established|studied|demonstrated)|"
    r"have not been (performed|studied)|"
    r"not recommended in (pediatric|children)|"
    r"should not be (used|prescribed|administered)|"
    r"is not indicated in (pediatric|children)|"
    r"not approved for use in (children|pediatric)", re.I)


def pediatric_flag(pediatric_text):
    """-> "labeled_pediatric_indication" | "pediatric_text_only" | "none".

    "none" covers: no label hit, empty pediatric_use text, and text whose
    only pediatric statements say safety/effectiveness was NOT established
    (or use not recommended).  "pediatric_text_only" = pediatric text
    exists but neither clearly establishes nor clearly denies pediatric
    use (e.g. risk-only or "see indications" stubs).
    """
    t = (pediatric_text or "").strip()
    if not t:
        return "none"
    for sent in re.split(r"(?<=[.!?])\s+", t):
        if (_POP.search(sent) and _POSVERB.search(sent)
                and not _NEGWORD.search(sent)):
            return "labeled_pediatric_indication"
    if _NEGATED_ANY.search(t):
        return "none"
    return "pediatric_text_only"
