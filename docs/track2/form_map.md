---
title: Methods form map
nav_order: 15
parent: Track 2
---
# Track 2 methods-form map

Compiled 2026-10-12 by lane L4. Prompt text extracted VERBATIM from the
vendored form template `hackathon-app/static/templates/
methods_description_form.xlsx` (`xl/sharedStrings.xml`, stdlib zipfile -
same extraction as `form_answers_section()` in `tools/make_report.py`).
Track 2 prompt indices: 2, 13-20, 22, 23 (index 21 "Model number" is a
Track-1-only scaffold; index 25 is the Track-2 instruction line, quoted at
the end for context).

For each prompt: where the answer lives (report section / artifact) and the
one-line answer direction. L6 renders these into the report's form-answers
section; this map is the contract it writes against.

| # | sharedStrings idx | Prompt (verbatim) | Answered by |
|---|---|---|---|
| Q1 | 2 | Team name | Submission field + report header. `nikhilpise` / team name per `docs/track2/submission_fields.md` (L6/operator). REQUIRED (red in form). |
| Q2 | 13 | Please describe your approach in detail (how you went from variant/mechanism to candidate medication(s)). | Report methods section + `docs/track2/engine.md`: seed genes -> pathway expansion -> drug-target evidence (Open Targets, ChEMBL, DGIdb, DrugCentral) -> approved-only filter -> STRING proximity -> LINCS L1000 reversal -> PRISM aneuploidy pharmacogenomics -> pediatric-safety filter -> evidence tiers; `docs/track2/evidence/candidates.json` is the emitted artifact. |
| Q3 | 14 | Was candidate identification automated (e.g., via a drug-target database query or LLM-assisted search), or primarily manual literature review and expert curation? | Automated engine first (`tools/run_track2.py`, deterministic, config-frozen), THEN manual curation for dossier claims, pediatric labels and the rejected table - stated honestly as hybrid, with the automated funnel as the candidate source of record. |
| Q4 | 15 | Please describe any manual literature review or expert curation in detail. | Dossier curation: every claim resolved to a real PMID/DOI via `tools/verify_citations.py` (esummary/Crossref + retraction check + title-match against `docs/track2/evidence/dossiers/*.json`); L9 red-team passes logged in `docs/track2/redteam.md`. |
| Q5 | 16 | Please state whether you relied solely on publicly available drug/target databases and literature (preferred), or whether proprietary data sources were also used. | Public only. Answer: solely public; list next answer. No proprietary source anywhere in the pipeline. |
| Q6 | 17 | Please describe the public data sources used in detail (e.g., DrugBank, ChEMBL, ClinicalTrials.gov, OMIM, PubMed literature search). | Enumerated in `docs/track2/engine.md` data-sources table: Open Targets Platform, ChEMBL (max_phase), DrugCentral (approvals), DGIdb, STRING, SigCom LINCS / L1000, DepMap PRISM (24Q4), openFDA drug labels, PubMed E-utilities, OMIM (MVA1 257300), HPO, ClinVar, gnomAD, AlphaFold DB, AlphaMissense/CADD/REVEL. Each with access date + version in the artifact. |
| Q7 | 18 | Please describe any proprietary data sources used in detail. | None. (The gated hackathon dataset is challenge-provided, not proprietary; the only patient-derived facts used are the two variants + 8 HPO terms already public in the Track 1 report.) |
| Q8 | 19 | How did you characterize the variant's mechanism (e.g., loss-of-function vs. gain-of-function, pathway disrupted, downstream biological consequence)? | `docs/track2/mechanism.md` + `docs/track2/evidence/mechanism.json`: per-allele table - p.Leu737Ter as null (NMD prediction, truncation before kinase-like domain), p.Asn1002Lys as hypomorph (domain position, conservation, AlphaMissense/REVEL/CADD, LM effect score, AlphaFold structural context); pathway chain BubR1 loss -> SAC weakening -> missegregation -> mosaic aneuploidy -> senescence/cancer/progeroid decline; phase stated as an assumption, not an observation. |
| Q9 | 20 | Please provide an estimate of time or effort spent on this analysis (if possible). | `docs/runtime_log.md` (per-run ledger, Modal spend) + wall-clock lane timeline in the report; one-command engine rerun cost quoted from the benchmark run. |
| Q10 | 22 | Provide a method abstract (up to 500 words). Please include strengths and limitations of your approach as well as methodological detail. | Report abstract section (L6): <=500 words, strengths (multi-modal evidence, verified citations, code-checked approvals, retrospective benchmark, honest negatives) and limitations (phase unknown, N-of-1, no patient-cell validation, signature-reversal weakness) both explicit. |
| Q11 | 23 | (required) If commercially-available Generative AI was used, record the provider, the plan or tier, and the relevant setting in your methods description. A line is enough, for example, "Anthropic API, Claude Sonnet, commercial terms, no training on customer content." | REQUIRED (red). Generated disclosure line from `docs/llm_log.md` (Devin Pro SWE-2 Max + Claude Pro/Max, training opt-outs, no feedback) - matches organizer guidance in discussion #2 (2026-09-28 update). |

Track-2 instruction line (sharedStrings index 25, verbatim, for context):

> "Please submit your answers with your Track 2 report. All questions (with
> the exception of Question 1, in red) are voluntary; however, submissions
> without a methods description may be judged less favorably on the
> Scientific Rigor and Innovation criteria, since the panel can't assess
> what it can't see. Track 2 accepts one final submission per team."

Note: the form's "one final submission" text predates discussion #7, which
raised the quota to 3 (only the latest reviewed) - live `config.py`
confirms `MAX_TRACK2_SUBMISSIONS = 3`. We answer ALL questions anyway
(Scientific Rigor + Innovation are 60 of 100 points combined).
