"""Network-free tests for the L2b mechanism-direction layer, PRISM overlay
and pediatric flag.

Synthetic candidates are classified directly through
src/track2/direction.py; the shipped config's rule set (compiled from
config/track2.yaml) is used for the positive/negative examples so tests
fail if a rule stops matching reality (e.g. "MTOR inhibitor" must never
become opposed).
"""
import json
import pathlib

import pytest

from src.track2 import direction as direction_mod
from src.track2 import prism as prism_mod
from src.track2 import t2config

ROOT = pathlib.Path(__file__).resolve().parents[1]
CFG = t2config.load_config(ROOT / "config" / "track2.yaml")
RULES = direction_mod.compile_rules(CFG)


def cand(drug="x", moa="", names=None, action_types=(), targets=(),
         module_targets=(), moa_target_actions=None, hit_types=None):
    """Minimal classify()-shaped candidate."""
    return {"drug": drug,
            "names": sorted(set((names or []) + [drug])),
            "mechanism_of_action": moa,
            "action_types": sorted(action_types),
            "targets": sorted(set(targets)),
            "module_targets": sorted(set(module_targets)),
            "moa_target_actions": dict(moa_target_actions or {}),
            "hit_types": dict(hit_types or {})}


# ------------------------------------------------------------- matching ---

def test_negative_mtor_inhibitor_not_opposed():
    """Spec negative: 'MTOR inhibitor' must NOT classify as opposed."""
    d, reasons = direction_mod.classify(
        cand(drug="sirolimus", moa="MTOR inhibitor",
             action_types=["INHIBITOR"],
             moa_target_actions={"FKBP1A": ["INHIBITOR"],
                                 "MTOR": ["INHIBITOR"]},
             targets=["FKBP1A", "MTOR"]), RULES)
    assert d == "aligned"
    assert "aln_mtorc1_inhibition" in reasons
    assert not any(r.startswith("opp_") for r in reasons)


def test_topoisomerase_inhibitor_is_opposed():
    """Spec positive: 'DNA topoisomerase II alpha inhibitor' IS opposed."""
    d, reasons = direction_mod.classify(
        cand(drug="doxorubicin", moa="DNA topoisomerase II alpha inhibitor",
             action_types=["INHIBITOR"],
             moa_target_actions={"TOP2A": ["INHIBITOR"]},
             targets=["TOP2A"]), RULES)
    assert d == "opposed"
    assert "opp_topoisomerase_poison" in reasons


def test_dna_inhibitor_moa_opposed():
    d, _ = direction_mod.classify(
        cand(drug="temozolomide", moa="DNA inhibitor"), RULES)
    assert d == "opposed"


def test_cross_linking_action_type_opposed():
    """ChEMBL action_type CROSS-LINKING AGENT fires without MoA text."""
    d, reasons = direction_mod.classify(
        cand(drug="pixantrone", moa="DNA cross-linking agent",
             action_types=["CROSS-LINKING AGENT"]), RULES)
    assert d == "opposed"
    assert "opp_dna_damaging" in reasons


def test_name_pattern_catches_empty_moa():
    """Name-class rules catch cytotoxics whose MoA text is empty."""
    d, reasons = direction_mod.classify(
        cand(drug="cyclophosphamide anhydrous",
             names=["cyclophosphamide"], moa=""), RULES)
    assert d == "opposed"
    assert "opp_dna_damaging" in reasons
    d, reasons = direction_mod.classify(
        cand(drug="epirubicin", moa=""), RULES)
    assert d == "opposed"


def test_tubulin_moa_and_name_opposed():
    d, reasons = direction_mod.classify(
        cand(drug="vinblastine", moa="Tubulin inhibitor"), RULES)
    assert d == "opposed"
    assert "opp_antimitotic_tubulin" in reasons
    d, _ = direction_mod.classify(
        cand(drug="paclitaxel", moa=""), RULES)
    assert d == "opposed"


def test_target_gene_hit_without_inhibitory_evidence():
    """Bare TOP2A module hit fires the topo rule (no inhibition needed)."""
    d, reasons = direction_mod.classify(
        cand(drug="podofilox", moa="", targets=["TOP2A"],
             module_targets=["TOP2A"]), RULES)
    assert d == "opposed"
    assert "opp_topoisomerase_poison" in reasons


def test_sac_kinase_requires_inhibitory_edge():
    """Loose DGIdb edges (no inhibitor type) must NOT trigger SAC rule."""
    # dasatinib: AURKB is a module hit with NO interaction type -> stays
    c = cand(drug="dasatinib anhydrous",
             moa="Tyrosine-protein kinase ABL inhibitor",
             action_types=["INHIBITOR"],
             moa_target_actions={"SRC": ["INHIBITOR"],
                                 "ABL1": ["INHIBITOR"]},
             targets=["AURKB", "SRC", "ABL1"],
             module_targets=["AURKB"],
             hit_types={"AURKB": []})
    d, reasons = direction_mod.classify(c, RULES)
    assert d == "aligned"          # senolytic SRC/ABL class
    assert "opp_sac_kinase" not in reasons
    # ...but a real inhibitory AURKB edge IS opposed
    c["hit_types"] = {"AURKB": ["inhibitor"]}
    d, reasons = direction_mod.classify(c, RULES)
    assert d == "opposed"
    assert "opp_sac_kinase" in reasons
    # opposed beats aligned when both fire (safety-first)
    assert "aln_senolytic_class" in reasons


def test_curated_moa_target_with_inhibitor_action_fires():
    c = cand(drug="fakeaurora",
             moa_target_actions={"AURKB": ["INHIBITOR"]},
             targets=["AURKB"])
    d, reasons = direction_mod.classify(c, RULES)
    assert d == "opposed"
    assert "opp_sac_kinase" in reasons


def test_pp2a_inhibitor_edge_opposed():
    d, reasons = direction_mod.classify(
        cand(drug="cantharidin", moa="",
             module_targets=["PPP2CA"], targets=["PPP2CA"],
             hit_types={"PPP2CA": ["inhibitor"]}), RULES)
    assert d == "opposed"
    assert "opp_pp2a_inhibitor" in reasons


def test_sirt2_inhibitor_edge_opposed():
    d, reasons = direction_mod.classify(
        cand(drug="panobinostat", moa="Histone deacetylase inhibitor",
             module_targets=["SIRT2"], targets=["SIRT2"],
             hit_types={"SIRT2": ["inhibitor"]}), RULES)
    assert d == "opposed"
    assert "opp_sirt2_inhibitor" in reasons


def test_ampk_activator_aligned_not_opposed():
    """Metformin: PRKAA activator edge + complex I MoA -> aligned."""
    d, reasons = direction_mod.classify(
        cand(drug="metformin",
             moa="Mitochondrial complex I (NADH dehydrogenase) inhibitor",
             module_targets=["PRKAA1", "PRKAA2"],
             targets=["PRKAA1", "PRKAA2"],
             hit_types={"PRKAA1": ["activator"],
                        "PRKAA2": ["activator"]}), RULES)
    assert d == "aligned"
    assert "aln_ampk_energy_stress" in reasons


def test_antimetabolite_name_and_targets():
    d, _ = direction_mod.classify(
        cand(drug="hydroxyurea", moa=""), RULES)
    assert d == "opposed"
    d, reasons = direction_mod.classify(
        cand(drug="fluorouracil", moa="", targets=["TYMS"],
             module_targets=["TYMS"]), RULES)
    assert d == "opposed"
    assert "opp_antimetabolite_dna_synthesis" in reasons


def test_benign_drug_stays_neutral():
    d, reasons = direction_mod.classify(
        cand(drug="acetaminophen",
             moa="Prostaglandin G/H synthase 2 inhibitor",
             targets=["PTGS2"]), RULES)
    assert d == "neutral"
    assert reasons == []


def test_no_rules_all_neutral():
    """Direction disabled -> everything neutral, nothing excluded."""
    assert direction_mod.compile_rules({"direction": {"enabled": False}}) \
        == []
    assert direction_mod.classify(cand(moa="DNA inhibitor"), []) \
        == ("neutral", [])


def test_every_rule_has_reason_and_opposed_rules_have_cites():
    for r in RULES:
        assert r.id and r.direction in {"opposed", "aligned"}
        assert r.reason, r.id
        assert r.cites, r.id
        assert all(c.startswith("PMID:") for c in r.cites)


# ---------------------------------------------------------- pediatric ---

def test_pediatric_flag_negated():
    assert direction_mod.pediatric_flag(
        "Safety and effectiveness in pediatric patients have not been "
        "established.") == "none"
    assert direction_mod.pediatric_flag(
        "The safety and effectiveness in pediatric patients (below 18 "
        "years of age) have not been established. Use of cladribine is "
        "not recommended in pediatric patients") == "none"


def test_pediatric_flag_positive():
    assert direction_mod.pediatric_flag(
        "The safety and effectiveness of everolimus have been "
        "established in pediatric patients age 1 year and older") == \
        "labeled_pediatric_indication"
    assert direction_mod.pediatric_flag(
        "Levothyroxine sodium is indicated in patients from birth to "
        "less than 17 years of age") == "labeled_pediatric_indication"
    assert direction_mod.pediatric_flag(
        "Celecoxib is approved for relief of the signs and symptoms of "
        "Juvenile Rheumatoid Arthritis in patients 2 years and older") \
        == "labeled_pediatric_indication"


def test_pediatric_flag_mixed_label():
    """Sirolimus-style label: negated <13y but established >=13y."""
    assert direction_mod.pediatric_flag(
        "The safety and efficacy of sirolimus in pediatric patients "
        "< 13 years have not been established. The safety and efficacy "
        "of sirolimus have been established for prophylaxis of organ "
        "rejection in renal transplantation in children >= 13 years") == \
        "labeled_pediatric_indication"


def test_pediatric_flag_text_only_and_empty():
    assert direction_mod.pediatric_flag(
        "See INDICATIONS AND USAGE.") == "unknown"
    assert direction_mod.pediatric_flag(
        "pediatric patients treated with doxorubicin are at risk for "
        "developing late cardiovascular dysfunction") == \
        "pediatric_text_only"
    assert direction_mod.pediatric_flag("") == "unknown"
    assert direction_mod.pediatric_flag(None) == "unknown"


# ---------------------------------------------------------------------------
# L11 - pediatric classifier on REAL recorded openFDA label strings
# (fetched 2026-10-13; set_ids noted per constant)
# ---------------------------------------------------------------------------

# dasatinib label set_id 02b04c6f-4ea5-4fcb-bf6d-2631d5ab31e4 (generic
# DASATINIB): the pediatric age floor lives in INDICATIONS AND USAGE,
# not in 8.4 - the old classifier never saw it.
_DASATINIB_IND = (
    "1 INDICATIONS AND USAGE Dasatinib tablets are indicated for the "
    "treatment of adult patients with newly diagnosed Philadelphia "
    "chromosome-positive (Ph+) chronic myeloid leukemia (CML) in chronic "
    "phase. chronic, accelerated, or myeloid or lymphoid blast phase Ph+ "
    "CML with resistance or intolerance to prior therapy including "
    "imatinib. Philadelphia chromosome-positive acute lymphoblastic "
    "leukemia (Ph+ ALL) with resistance or intolerance to prior therapy. "
    "Dasatinib tablets are indicated for the treatment of pediatric "
    "patients 1 year of age and older with Ph+ CML in chronic phase. "
    "newly diagnosed Ph+ ALL in combination with chemotherapy.")

# metformin hydrochloride tablets label set_id
# 011de1a5-1ac0-4831-9e8d-26ec79ba2205 (single ingredient)
_METFORMIN_PED = (
    "8.4 Pediatric Use Metformin Hydrochloride Tablets The safety and "
    "effectiveness of metformin hydrochloride tablets for the treatment "
    "of type 2 diabetes mellitus have been established in pediatric "
    "patients 10 to 16 years old. Safety and effectiveness of metformin "
    "hydrochloride tablets have not been established in pediatric "
    "patients less than 10 years old.")

# ZITUVIMET (sitagliptin/metformin combo) label - the product the old
# matcher returned for "metformin" and "metformin hydrochloride"
_ZITUVIMET_PED = (
    "8.4 Pediatric Use The safety and effectiveness of ZITUVIMET have "
    "not been established in pediatric patients.")
_ZITUVIMET_IND = (
    "1 INDICATIONS AND USAGE ZITUVIMET is a combination of sitagliptin "
    "and metformin hydrochloride indicated as an adjunct to diet and "
    "exercise to improve glycemic control in adults with type 2 "
    "diabetes mellitus.")

# everolimus recorded dossier (docs/track2/evidence/dossiers/)
_EVEROLIMUS_PED = (
    "The safety and effectiveness of everolimus have been established "
    "in pediatric patients age 1 year and older for TSC-associated "
    "partial-onset seizures, TSC-associated SEGA requiring intervention, "
    "and renal angiomyolipoma.")

# NIACOR label set_id bf287412-160b-403f-8eb4-57f29a475902: negated only
_NIACOR_PED = (
    "Pediatric Use - Safety and effectiveness in children and "
    "adolescents have not been established.")

# hydroxychloroquine sulfate label: pediatric malaria use established,
# RA/SLE pediatric use negated, weight floor excludes small children
_HCQ_PED = (
    "8.4 Pediatric Use The safety and effectiveness of "
    "hydroxychloroquine sulfate have been established in pediatric "
    "patients for the treatment of uncomplicated malaria due to P. "
    "falciparum, P. malariae, P. vivax, and P. ovale, as well as for "
    "the prophylaxis of malaria in geographic areas where chloroquine "
    "resistance is not reported. However, this product cannot be "
    "directly administered to pediatric patients weighing less than "
    "31 kg because the film-coated tablets cannot be crushed or "
    "divided. The safety and effectiveness of hydroxychloroquine "
    "sulfate have not been established in pediatric patients for the "
    "treatment of rheumatoid arthritis, chronic discoid lupus "
    "erythematosus, or systemic lupus erythematosus.")
_HCQ_DOS = (
    "2 DOSAGE AND ADMINISTRATION Malaria in Adult and Pediatric "
    "Patients (2.2): - Adults: 400 mg once a week - Pediatric "
    "patients >= 31 kg: 6.5 mg/kg up to 400 mg, once a week")


def test_pediatric_dasatinib_via_indications():
    flag, ev = direction_mod.classify_pediatric("", _DASATINIB_IND, "")
    assert flag == "labeled_pediatric_indication"
    assert ev["section"] == "indications_and_usage"
    assert "1 year of age and older" in ev["text"]


def test_pediatric_metformin_positive_band():
    flag, _ = direction_mod.classify_pediatric(_METFORMIN_PED, "", "")
    assert flag == "labeled_pediatric_indication"


def test_pediatric_zituvimet_combo_negative():
    """Combination label: negated pediatric_use + adults-only indication
    is 'none' - a combo must not donate pediatric status."""
    flag, _ = direction_mod.classify_pediatric(
        _ZITUVIMET_PED, _ZITUVIMET_IND, "")
    assert flag == "none"


def test_pediatric_everolimus_true_positive():
    flag, _ = direction_mod.classify_pediatric(_EVEROLIMUS_PED, "", "")
    assert flag == "labeled_pediatric_indication"


def test_pediatric_niacin_true_negative():
    flag, _ = direction_mod.classify_pediatric(_NIACOR_PED, "", "")
    assert flag == "none"


def test_pediatric_hydroxychloroquine_weight_threshold():
    """A positive malaria indication in 8.4 wins even though another
    sentence denies pediatric RA/SLE use and a weight floor excludes
    small children."""
    flag, ev = direction_mod.classify_pediatric(_HCQ_PED, "", _HCQ_DOS)
    assert flag == "labeled_pediatric_indication"
    assert ev["section"] == "pediatric_use"


def test_pediatric_weight_threshold_dosage_channel():
    """Dosage text naming a pediatric weight bound is itself a labeled
    pediatric indication even with an empty 8.4."""
    flag, ev = direction_mod.classify_pediatric(
        "", "", "- Pediatric patients >= 31 kg: 6.5 mg/kg up to 400 mg")
    assert flag == "labeled_pediatric_indication"
    assert ev["section"] == "dosage_and_administration"


def test_pediatric_negative_thresholds_not_positive():
    """'less than'/'under' bounds and study-population age ranges are
    not affirmative indications."""
    for text in (
            "cannot be directly administered to pediatric patients "
            "weighing less than 31 kg.",
            "The safety and effectiveness of hydroxychloroquine "
            "sulfate have not been established in pediatric patients.",
            "In an open-label trial, 25 pediatric patients (median "
            "age 14 years, range 3-20 years) were randomized.",
            "Twenty-eight female pediatric patients, aged 2 to 10 "
            "years, were treated for up to 12 months."):
        flag, _ = direction_mod.classify_pediatric(text, "", "")
        assert flag != "labeled_pediatric_indication", text


def test_pediatric_adult_age_floor_not_positive():
    """An ADULT age floor in INDICATIONS must not count as pediatric;
    adult-only text carries no pediatric evidence either way (L15)."""
    ind = ("1.2 Acute Myeloid Leukemia VENCLEXTA is indicated in "
           "combination with azacitidine for the treatment of newly "
           "diagnosed acute myeloid leukemia (AML) in adults 75 years "
           "or older, or who have comorbidities.")
    flag, _ = direction_mod.classify_pediatric("", ind, "")
    assert flag == "unknown"


def test_pediatric_positive_wins_over_negated_elsewhere():
    """A positive indication survives a negated sentence elsewhere in
    the label (task rule: positive wins)."""
    flag, _ = direction_mod.classify_pediatric(
        _ZITUVIMET_PED, _DASATINIB_IND, "")
    assert flag == "labeled_pediatric_indication"


# ---------------------------------------------------------------------------
# L15 - redteam2 r4/n3: 'unknown' tier, denial-priority, word-boundary clip.
# Label strings below are the real recorded openFDA texts (set_ids noted).
# ---------------------------------------------------------------------------

# cyclosporine transplant label set_id 5e5926a7-1de0-4b54-a5c0-286b6200ff82
# (bare generic CYCLOSPORINE; the label the _exists_ deep scan picks):
# pediatric use documented descriptively - no indication, no denial.
_CYCLOSPORINE_TX_PED = (
    "Pediatric Use Although no adequate and well-controlled studies "
    "have been conducted in children, patients as young as 6 months of "
    "age have received cyclosporine with no unusual adverse effects.")

# cyclosporine Vevye ophthalmic label set_id
# 0a60fccf-7e1b-44fe-e063-6394a90aadd5 - the limit=1 first hit: a formal
# denial for the ophthalmic product.
_CYCLOSPORINE_VEVYE_PED = (
    "8.4 Pediatric Use Safety and effectiveness in pediatric patients "
    "below the age of 18 years have not been established.")

# acetaminophen injection label set_id 0f67c1bd-915b-4681-88dd-22f5154a80b3
# (bare generic ACETAMINOPHEN; reachable only via the _exists_ deep
# scan - the limit=1 OTC label is silent on pediatrics).
_ACETAMINOPHEN_INJ_PED = (
    "8.4 Pediatric Use Treatment of Acute Pain The safety and "
    "effectiveness of acetaminophen injection for the treatment of "
    "acute pain in pediatric patients ages 2 years and older is "
    "supported by evidence from adequate and well-controlled studies "
    "of acetaminophen injection in adults and safety and "
    "pharmacokinetic data from adult and 483 pediatric patients "
    "across all age groups")

# acetaminophen OTC label set_id 0005aafa-08f8-4990-a54d-cc097195708f:
# uses-only indications, no pediatric text anywhere in the record.
_ACETAMINOPHEN_OTC_IND = (
    "Uses temporarily relieves minor aches and pains due to: headache "
    "the common cold backache minor pain of arthritis toothache "
    "muscular aches premenstrual and menstrual cramps temporarily "
    "reduces fever")


def test_pediatric_cyclosporine_transplant_descriptive():
    """redteam2 r4: the transplant label documents pediatric use without
    establishing it - text_only, not 'none' (the Vevye denial) and not
    'labeled' (no established indication)."""
    flag, ev = direction_mod.classify_pediatric(
        _CYCLOSPORINE_TX_PED, "", "")
    assert flag == "pediatric_text_only"
    assert ev is None


def test_pediatric_cyclosporine_vevye_negated():
    flag, _ = direction_mod.classify_pediatric(
        _CYCLOSPORINE_VEVYE_PED, "", "")
    assert flag == "none"


def test_pediatric_acetaminophen_injection_positive():
    flag, ev = direction_mod.classify_pediatric(
        _ACETAMINOPHEN_INJ_PED, "", "")
    assert flag == "labeled_pediatric_indication"
    assert "2 years and older" in ev["text"]


def test_pediatric_acetaminophen_otc_silent_unknown():
    """redteam2 r4: an OTC label silent on pediatrics is 'unknown' - no
    evidence either way - not 'none' (which asserts a denial)."""
    flag, _ = direction_mod.classify_pediatric(
        "", _ACETAMINOPHEN_OTC_IND, "")
    assert flag == "unknown"


def test_pediatric_denial_beats_descriptive():
    """A label carrying BOTH a formal denial and descriptive pediatric
    text is 'none': the denial is the label's verdict, the descriptive
    text does not soften it."""
    flag, _ = direction_mod.classify_pediatric(
        _CYCLOSPORINE_TX_PED + " " + _CYCLOSPORINE_VEVYE_PED, "", "")
    assert flag == "none"


def test_pediatric_evidence_clips_on_word_boundary():
    """redteam2 n3: quoted evidence text must end at a word boundary +
    ' ...', never mid-word ('glomerular'/'of which' style cuts)."""
    sent = ("The safety and effectiveness of TESTOPHEN have been "
            "established in pediatric patients one year of age and "
            "older for the treatment of serious infections caused by "
            "susceptible gram negative organisms including extended "
            "spectrum beta lactamase producing strains in complicated "
            "intra-abdominal infections and complicated urinary tract "
            "infections in clinical trials")
    flag, ev = direction_mod.classify_pediatric(sent, "", "")
    assert flag == "labeled_pediatric_indication"
    text = ev["text"]
    assert text.endswith(" ...")
    body = text[:-4]
    assert len(body) <= 240
    # verbatim prefix ending between words (no mid-word cut)
    assert sent.startswith(body)
    rest = sent[len(body):]
    assert rest.startswith((" ", ",", ";", ":", "-", "(")), rest[:20]


# ---------------------------------------------------------------- PRISM ---

def test_prism_overlay_join(tmp_path):
    fixture = {"aneuploidy": {"all_results": [
        {"name": "sirolimus", "beta": -0.01, "q": 0.4, "n_lines": 422},
        {"name": "doxorubicin", "beta": 0.002, "q": 0.9, "n_lines": 451},
    ]}}
    f = tmp_path / "prism.json"
    f.write_text(json.dumps(fixture), encoding="utf-8")
    cfg = {"prism": {"enabled": True, "file": str(f), "weight": 0.0}}
    index, meta = prism_mod.load_index(cfg)
    assert meta["status"] == "ok" and meta["n_rows"] == 2
    # name match incl. salt/form variants
    a = prism_mod.annotate(index, ["sirolimus tablets", "sirolimus"])
    assert a["status"] == "screened" and a["beta"] == -0.01 \
        and a["q"] == 0.4 and a["n_lines"] == 422
    a = prism_mod.annotate(index, ["doxorubicin hydrochloride"])
    assert a["status"] == "screened" and a["prism_name"] == "doxorubicin"
    # absent -> explicit not_in_screen, never a fake zero
    a = prism_mod.annotate(index, ["metformin"])
    assert a["status"] == "not_in_screen" and a["beta"] is None
    # disabled/missing -> unavailable, no crash
    index2, meta2 = prism_mod.load_index(
        {"prism": {"enabled": False}})
    assert prism_mod.annotate(index2, ["x"])["status"] == "unavailable"


def test_prism_overlay_real_file():
    """The committed prism.json joins real candidates by name."""
    cfg = {"prism": {"enabled": True,
                     "file": "docs/track2/evidence/prism.json",
                     "weight": 0.0}}
    index, meta = prism_mod.load_index(cfg)
    assert meta["status"] == "ok" and meta["n_rows"] > 1000
    a = prism_mod.annotate(index, ["sirolimus"])
    assert a["status"] == "screened"
    assert a["beta"] is not None and a["q"] is not None
    a = prism_mod.annotate(index, ["aspirin"])
    assert a["status"] in {"screened", "not_in_screen"}


def test_prism_weight_is_zero_and_excluded_from_score():
    """PRISM is a reported channel only: weight must be exactly 0 and it
    must not appear in the scoring weights."""
    assert CFG["prism"]["weight"] == 0.0
    weights = CFG["scoring"]["weights"]
    assert "prism" not in " ".join(weights).lower()


# -------------------------------------------- real MVA replay (fixture) ---

@pytest.fixture(scope="module")
def mva_result():
    from src.track2 import engine, httpcache
    case = {"name": CFG["case"]["name"],
            "disease": CFG["case"]["disease"],
            "disease_gene": CFG["case"]["disease_gene"],
            "hpo_terms": CFG["case"].get("hpo_terms", []),
            "variants": CFG["case"].get("variants", []),
            "seed_genes": CFG["seed_genes"], "run_lincs": True}
    return engine.run_case(
        httpcache.CachedHttp(
            cache_dir=str(ROOT / "tests/fixtures/track2/engine/mva"),
            mode="replay"), CFG, case)


def test_replay_excludes_opposed_and_preserves_records(mva_result):
    res = mva_result
    excluded = res["excluded_mechanism_opposed"]
    assert len(excluded) > 0
    # no opposed drug may remain in the ranked list
    assert all(c["direction"] != "opposed" for c in res["candidates"])
    # excluded records keep identity + would-be rank + reasons
    top = excluded[0]
    assert top["drug"] == "doxorubicin"
    assert top["rank_before_direction"] == 1
    assert "rank" not in top
    assert top["score"] > 0 and top["direction_reasons"]
    assert top["pediatric_flag"] in {
        "labeled_pediatric_indication", "pediatric_text_only", "none",
        "unknown"}
    # ranked list re-ranks from 1 without gaps
    assert [c["rank"] for c in res["candidates"][:5]] == [1, 2, 3, 4, 5]
    assert all(c["rank"] <= c["rank_before_direction"]
               for c in res["candidates"])
    # totals conserve
    assert len(res["candidates"]) + len(excluded) == \
        len(res["candidates"]) + res["direction"]["n_opposed_excluded"]


def test_replay_direction_summary_and_fields(mva_result):
    res = mva_result
    d = res["direction"]
    assert d["enabled"] and d["version"] == 2
    assert d["n_opposed_excluded"] > 0
    assert d["n_aligned"] > 0
    assert d["added_after_freeze"]
    for c in res["candidates"]:
        assert c["direction"] in {"aligned", "neutral"}
        assert isinstance(c["direction_reasons"], list)
        assert c["rank_before_direction"] >= c["rank"]


def test_replay_known_top_after_direction(mva_result):
    """Sirolimus (aligned, pediatric-labeled) must be top-2 after split."""
    res = mva_result
    by_name = {c["drug"]: c for c in res["candidates"]}
    assert by_name["sirolimus"]["direction"] == "aligned"
    assert by_name["sirolimus"]["rank"] <= 2
    assert by_name["sirolimus"]["pediatric_flag"] == \
        "labeled_pediatric_indication"
    assert by_name["everolimus"]["direction"] == "aligned"


def test_replay_prism_annotates_candidates(mva_result):
    res = mva_result
    all_c = res["candidates"] + res["excluded_mechanism_opposed"]
    assert res["prism"]["status"] == "ok"
    assert res["prism"]["weight"] == 0.0
    n_screened = sum(1 for c in all_c
                     if c["evidence"]["prism_aneuploidy"]["status"]
                     == "screened")
    assert n_screened > 0
    sirol = next(c for c in all_c if c["drug"] == "sirolimus")
    pa = sirol["evidence"]["prism_aneuploidy"]
    assert pa["status"] == "screened"
    assert pa["beta"] is not None and pa["n_lines"] > 0
    # PRISM must not have changed the score channel weighting
    assert "prism" not in res["candidates"][0]["channels"]


def test_replay_determinism_byte_identical():
    """Two replay runs differ only in generated_at/config_sha."""
    import copy
    from src.track2 import engine, httpcache
    case = {"name": CFG["case"]["name"],
            "disease": CFG["case"]["disease"],
            "disease_gene": CFG["case"]["disease_gene"],
            "hpo_terms": CFG["case"].get("hpo_terms", []),
            "variants": CFG["case"].get("variants", []),
            "seed_genes": CFG["seed_genes"], "run_lincs": True}

    def run():
        return engine.run_case(
            httpcache.CachedHttp(
                cache_dir=str(ROOT / "tests/fixtures/track2/engine/mva"),
                mode="replay"), CFG, copy.deepcopy(case))

    r1, r2 = run(), run()
    for r in (r1, r2):
        r["generated_at"] = ""
        r["config_sha256"] = ""
        for c in r.get("cases", []):
            c.pop("generated_at", None)
    assert json.dumps(r1, sort_keys=True, default=str) == \
        json.dumps(r2, sort_keys=True, default=str)


# ------------------------------------------------- benchmark safety net ---

def test_benchmark_known_drugs_never_opposed():
    """Every declared benchmark drug must not classify as opposed."""
    from src.track2 import benchmark, httpcache
    out = benchmark.run_benchmark(
        httpcache.CachedHttp(
            cache_dir=str(ROOT / "tests/fixtures/track2/engine/benchmark"),
            mode="replay"), CFG)
    bad = []
    for case in out["cases"]:
        for kd in case["known_drugs"]:
            if kd["direction"] == "opposed" or \
                    kd["stage"] == "excluded_mechanism_opposed":
                bad.append((case["gene"], kd["drug"]))
    assert bad == []
    # frozen v1 block present and unchanged
    assert out["v1_frozen"]["recall_at_5"] == \
        pytest.approx(0.333, abs=1e-3)
    assert out["v1_frozen"]["recall_at_25"] == \
        pytest.approx(0.556, abs=1e-3)
    # post-layer recall must be >= frozen (exclusions only remove
    # wrong-direction drugs; a known drug can only gain rank)
    assert out["recall_at_5"] >= out["v1_frozen"]["recall_at_5"] - 1e-9
    assert out["recall_at_25"] >= out["v1_frozen"]["recall_at_25"] - 1e-9
