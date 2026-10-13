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
# openFDA label text -> coarse pediatric flag.
# Evaluated sentence by sentence: an explicit POSITIVE pediatric statement
# (established/indicated/approved in children) wins even when another
# sentence is negative - e.g. sirolimus "not established <13y ... have been
# established for renal transplant in children >=13y" -> labeled.
#
# L11 (2026-10-13): the flag now reads three label sections, not only
# "8.4 Pediatric Use".  Labels put pediatric indications in INDICATIONS
# AND USAGE (dasatinib: "pediatric patients 1 year of age and older" while
# its own pediatric_use field is empty) and weight-threshold pediatric
# dosing in DOSAGE AND ADMINISTRATION (hydroxychloroquine: "Pediatric
# patients >= 31 kg").  A positive sentence in ANY section wins even when
# another sentence says safety/effectiveness was "not established" for a
# different indication - labels routinely carry both, and the old
# pediatric_use-only scan produced false negatives for exactly that
# pattern (redteam m8).  Threshold patterns are AFFIRMATIVE only: "less
# than", "under", "younger than", "weighing less than" can never match.
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
    r"not recommended|"
    r"should not be (used|prescribed|administered)|"
    r"do not (administer|give|use)|"
    r"cannot be directly administered|"
    r"is not indicated in (pediatric|children)|"
    r"not (for|approved for) use in (children|pediatric|infants)", re.I)
# strict pediatric-population term - the threshold patterns below only
# count when one of these is present in the same sentence.  The loose
# _POP alternatives ("years or older") match adult age floors such as
# venetoclax's "in adults 75 years or older" and must not gate them.
_PED_POP = re.compile(r"pediatric|children|child\b|adolescen|infant|"
                      r"neonat|newborn|postpubertal", re.I)
# affirmative pediatric age floors/bands - "1 year of age and older",
# "10 years and older", "10 to 16 years old", "2 years to 17 years",
# "from birth", "neonates" (no "less than"/"under" form can match)
_PED_AGE = re.compile(
    r"\b\d+\s*(?:year|month)s?\s*(?:of age\s*)?(?:and|or)\s+(?:older|over)\b"
    r"|\b(?:year|month)s?\s+of age\s+(?:and|or)\s+(?:older|over)\b"
    r"|\baged?\s+\d+\s+(?:year|month)s?\s+(?:and|or)\s+(?:older|over)\b"
    r"|\b\d+\s*(?:year|month)s?\s*(?:-|to)\s*\d+\s*(?:year|month)s?"
    r"|\b\d+\s*(?:-|to)\s*\d+\s*(?:year|month)s?(?:\s*old|\s*of age)?\b"
    r"|\bfrom\s+birth\b|\bneonates?\b|\bnewborns?\b", re.I)
# affirmative pediatric weight floors - "weighing at least 31 kg",
# ">=31 kg", "patients >= 31 kg", "31 kg or more"
_PED_WEIGHT = re.compile(
    r"\bweighing\s+(?:at least|more than|>=|>|over)\s*\d+"
    r"|\b(?:>=|≥)\s*\d+\s*kg\b"
    r"|\b\d+\s*kg\s+or\s+(?:more|greater|heavier)\b"
    r"|\bpatients?\s+(?:>=|≥|at least|over)\s*\d+\s*kg\b", re.I)


def _clip_words(text, limit=240):
    """Clip on a word boundary + ' ...' (same convention as
    tools/make_track2_report.clip): a quoted evidence sentence must
    never end mid-word - 'of which'/'glomerular' fragments read as
    bugs to a clinician inspecting the record."""
    t = re.sub(r"\s+", " ", (text or "").strip())
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0].rstrip(" ,;:-(")
    return cut + " ..."


def _pediatric_positive(sent, section):
    """One sentence -> explicit positive pediatric statement.

    Population evidence differs per section: in "8.4 Pediatric Use" the
    loose _POP suffices (the whole section is pediatric) and only
    verb-positives count - an age range there is usually a study
    population ("25 pediatric patients, range 3-20 years"), not a
    labeled indication.  In INDICATIONS/DOSAGE the sentence must name a
    strict pediatric population term (_PED_POP) - otherwise adult age
    floors like "in adults 75 years or older" would count - and may then
    qualify by affirmative verb OR by an affirmative age/weight bound.
    """
    pop_ok = (_POP.search(sent) if section == "pediatric_use"
              else _PED_POP.search(sent))
    if not pop_ok:
        return False
    if _NEGWORD.search(sent) or _NEGATED_ANY.search(sent):
        return False
    if _POSVERB.search(sent):
        return True
    if section == "pediatric_use":
        return False
    return bool(_PED_AGE.search(sent) or _PED_WEIGHT.search(sent))


def classify_pediatric(pediatric_text, indications_text="",
                       dosage_text=""):
    """-> (flag, evidence); evidence = {"section", "text"} of the winning
    positive sentence, or None.

    A positive sentence in any of the three sections wins.  When none is
    found the lower tiers distinguish *what the checked text actually
    contains* (L15, redteam2 r4 - "none" must never assert a negative
    the data does not carry):

      "none"                - a formal denial exists in the checked
                              text: some pediatric-population sentence
                              matches a denial pattern ("not
                              established", "not recommended", "do not
                              use"): the label considered pediatric use
                              and declined it.
      "pediatric_text_only" - pediatric text exists with no positive
                              and no formal denial: descriptive use
                              ("transplant recipients as young as one
                              year have received the drug"), risk
                              statements, "ask a doctor" directions,
                              cross-reference stubs.
      "unknown"             - nothing in the checked text bears on
                              pediatric populations at all: no label
                              hit, or a label silent on pediatrics.
    """
    fields = (("pediatric_use", pediatric_text),
              ("indications_and_usage", indications_text),
              ("dosage_and_administration", dosage_text))
    for fname, text in fields:
        for sent in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
            if sent and _pediatric_positive(sent, fname):
                return "labeled_pediatric_indication", \
                    {"section": fname, "text": _clip_words(sent, 240)}
    mentions = []
    for fname, text in fields:
        for sent in re.split(r"(?<=[.!?])\s+", (text or "").strip()):
            # strict pediatric-population terms only: loose _POP would
            # count geriatric text ("patients 65 years and older") as a
            # pediatric mention and inflate text_only
            if sent and _PED_POP.search(sent):
                mentions.append(sent)
    if not mentions:
        return "unknown", None
    if any(_NEGATED_ANY.search(s) for s in mentions):
        return "none", None
    return "pediatric_text_only", None


def pediatric_flag(pediatric_text, indications_text="", dosage_text=""):
    """-> "labeled_pediatric_indication" | "pediatric_text_only" |
    "none" | "unknown".

    "none" = a formal denial exists in the checked text ("not
    established", "not recommended", "do not use") - the label
    considered pediatric use and declined it.  "pediatric_text_only" =
    pediatric-population text exists with no positive and no denial
    (descriptive use, risk statements, cross-reference stubs).
    "unknown" = no label hit, or the checked text is silent on
    pediatric populations - no evidence either way.  See
    classify_pediatric for the multi-section positive scan.
    """
    flag, _ = classify_pediatric(pediatric_text, indications_text,
                                 dosage_text)
    return flag
