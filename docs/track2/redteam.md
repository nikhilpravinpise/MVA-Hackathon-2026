---
title: Red team 1
nav_order: 10
parent: Track 2
---
# L9 - Hostile red team on the Track 2 package

Date: 2026-10-13. Reviewer: lane L9, read-only.

Version reviewed: `docs/track2_report.md` generated 2026-10-13 from commit
`9a2083d`, committed in `97ea2b7` (working tree HEAD at review time;
the report file itself says "generated ... from commit 9a2083d").
All evidence JSONs at the same commit. The package was being updated
concurrently during the review; every finding below was re-checked
against the committed state after `97ea2b7`.

Scope rules: no code/evidence edits; findings only, each with severity,
exact file + line/table-row, the evidence, and the smallest fix.
Severity: BLOCKER = disqualifying or materially misleading if submitted;
MAJOR = a judge can catch it and it damages a headline claim;
MINOR = real but small - wording, accounting, or stale number;
NIT = cosmetic.

## Verdict up front

No BLOCKER. Two MAJORs, both in candidate-facing text and both
one-line fixes:

- the sirolimus "highest-placed non-cytotoxic" claim is **false** in
  every ordering the engine produced;
- the everolimus "median 4.1 years of pediatric exposure" data is
  cited to a PMID that does not contain it.

Everything else the review could verify reproduces exactly from the
committed artifacts - the mechanistic numbers, the benchmark, the
PRISM/ESM analyses, the citation gate, the test counts, and every
load-bearing abstract checked. The detailed "checked clean" ledger is
at the bottom so the lead can see what does NOT need attention.

---

## MAJOR

### M1 - "sirolimus is the engine's highest-placed non-cytotoxic candidate" is false

| | |
|---|---|
| Where | `docs/track2_report.md:211` ("It is preferred over sirolimus - the engine's top non-cytotoxic hit"), `docs/track2_report.md:279` ("the engine's highest-placed non-cytotoxic candidate at #21 of 96 approved drugs"), same sentence twice in `docs/track2/evidence/portfolio.json` (sirolimus and everolimus `why` fields) |
| Evidence | Pre-direction ranking in `candidates.json` puts palbociclib (#18), glycerin (#24), methenamine (#26), octocrylene (#27) and other non-cytotoxics above sirolimus (#21). Post-direction the same holds: palbociclib is #1, sirolimus #2 of 59. Under any reading of "non-cytotoxic" - cytostatic-only, non-oncology, non-genotoxic - the claim is wrong. The project's own `engine.md:330-338` names palbociclib, glycerin, methenamine and pentetic acid as neutral (non-cytotoxic) top hits. The TRUE claim is "highest mechanism-aligned candidate" (sirolimus is the top `aligned` entry, #2/59). |
| Severity | MAJOR - a false superlative printed twice in the submission and twice in the evidence JSON; the first thing a methods judge re-checks. |
| Smallest fix | Replace "non-cytotoxic" with "mechanism-aligned" (or "top direction-aligned hit (#2 of 59)") in report lines 211 and 279 and in `portfolio.json` (2 spots). One word in four places; the sentence then verifies. |

### M2 - Everolimus 4.1-year follow-up data is cited to the wrong paper

| | |
|---|---|
| Where | `docs/track2_report.md:217` ("in EXIST-1/Study 2485 open-label follow-up (115 pediatric patients, median 4.1 years exposure), everolimus did not appear to adversely impact growth and pubertal development ... (96% any infection, 35% serious infection). (PMID:23158522)"), and `docs/track2_report.md:211` ("label-reported absence of growth and pubertal harm over a median 4.1 years of pediatric exposure (PMID:23158522)"); same citation in `dossiers/everolimus.json` |
| Evidence | PMID:23158522 is the EXIST-1 **primary** report (Lancet 2013): double-blind, 117 patients, 35% response - no 4.1-year exposure, no growth/puberty analysis, no <6y infection breakdown anywhere in it. Those numbers live in the openFDA label (set_id `01f7b5fb`, already recorded in the dossier) and in the long-term extension publication, not in the cited PMID. Under the project's own rule - "every citation must support the claim" - this fails; the gate cannot catch it because it only checks title/year, not claim content. The substance of the claim is true (the label does report those numbers), so this is a citation-pointer error, not a fabricated fact. |
| Severity | MAJOR - a judge who spot-reads the everolimus abstracts finds the load-bearing pediatric-safety numbers unsupported by the cited paper. |
| Smallest fix | Cite `[repo:openFDA label 01f7b5fb]` for the 4.1y/growth/<6y-infection facts (it is the actual source recorded), and/or add the correct long-term extension citation. One-line change in `everolimus.json` and regeneration. |

---

## MINOR

### m1 - Abstract and report present different recall@10 values

| | |
|---|---|
| Where | `docs/track2/abstract.md:20` ("recall@1/5/10/25 of 0.00/0.33/0.44/0.56") vs `docs/track2_report.md:121` ("0.00 / 0.33 / 0.56 / 0.56 (frozen pre-direction-layer run: 0.00 / 0.33 / 0.44 / 0.56)") |
| Evidence | Same artifact, different headline: the abstract leads with the frozen v1 figure, the report leads with the post-direction figure. Both are true but inconsistent presentation invites the "retrofitted result" question a red team exists to prevent. |
| Severity | MINOR |
| Smallest fix | Show the identical labeled pair in both places, e.g. "0.44 frozen / 0.56 post-direction", with the same parenthetical order. |

### m2 - The funnel sentence cannot be summed from the printed numbers

| | |
|---|---|
| Where | `docs/track2_report.md:90` ("482 distinct drug names -> approval gate: 96 approved, 115 not phase 4, 6 withdrawn, 252 unresolvable names") |
| Evidence | 96 + 115 + 6 + 252 = 469, not 482. The missing 13 are names that resolved to another candidate's ChEMBL id and were merged (`engine.py:255-263` union-merge). The funnel JSON has no `merged` counter, so a statistician cannot reconcile the funnel without reading engine internals. It does reconcile once merges are counted (482 = 127 pre-resolved + 55 code-name + 41 weak-tail + 259 lookups; 259 lookups = 103 resolved + 156 failed; resolved 230 -> 217 unique gated + 13 merges). |
| Severity | MINOR - internally consistent, under-specified in print. |
| Smallest fix | Add a `merged` count to the funnel JSON and one clause to the sentence, e.g. "252 unresolvable, 13 merged into another candidate". |

### m3 - "96 approved" counts 7 salt-form duplicates; undisclosed

| | |
|---|---|
| Where | `docs/track2_report.md:90` funnel line; `candidates.json` rows: `metformin` (#39) and `metformin hydrochloride` (#59) both kept; excluded list: doxorubicin/hydrochloride, daunorubicin/hydrochloride, idarubicin/hydrochloride, mitoxantrone/hydrochloride, dexrazoxane/hydrochloride, etoposide/phosphate |
| Evidence | Each salt resolved to a different ChEMBL record (e.g. CHEMBL1431 vs CHEMBL1703), both legitimately max_phase 4, so the gate is right per-entity - but the 96 contains 89 distinct active ingredients. Nobody told the reader. Also slightly distorts score/rank statistics and the "v1 top ten" narrative (3 of the 10 were salt duplicates). |
| Severity | MINOR - count inflation + nondisclosure, not a logic error. |
| Smallest fix | One disclosure clause in the funnel sentence ("96 approved entities incl. 7 salt-form duplicates") or dedup to distinct parent. |

### m4 - "truth committed before the run" is literally false by git timestamps

| | |
|---|---|
| Where | `docs/track2_report.md:121` ("truth committed in config/track2.yaml before the run"), `docs/track2_report.md:344` |
| Evidence | The first config commit `3a09bf5` landed 2026-10-12 20:13+0530 (14:43 UTC); `benchmark.json` `generated_at` is 14:37 UTC - the run predates the commit by ~6 minutes. The substantive claim is fine (the engine reads truth only from the config it ran on; v1 artifacts are committed and reproduce), but "committed before the run" is not what the timestamps show. |
| Severity | MINOR - the discipline is real, the wording overstates it. |
| Smallest fix | "truth declared in `config/track2.yaml` before the run (the engine scores only against that config; file and artifacts committed together)". |

### m5 - Family-facing docs drop the phase caveat

| | |
|---|---|
| Where | `docs/track2/FAMILY_SUMMARY.md:39-41` ("This child has one BUB1B copy that is silent and one that still works"), `docs/track2_report.md:11` (plain-language paragraph asserts the null + hypomorph model) |
| Evidence | The in-trans configuration is inferred, not observed (report lines 23, 65, 349, abstract) - the single biggest scientific uncertainty, and the one the organizers explicitly say they will not resolve. The two documents a family actually reads present the model as established. If the variants were in cis, the "one silent copy" framing is wrong. |
| Severity | MINOR - the caveat exists everywhere a scientist looks; absent where a parent looks. |
| Smallest fix | One clause in each: e.g. "we believe these changes sit on different copies - we have not seen that directly, and the plan for testing would confirm it". |

### m6 - Shortlist table cells truncated mid-word

| | |
|---|---|
| Where | `docs/track2_report.md:176` (everolimus pediatric cell ends "...oral suspension). (Quot"), `docs/track2_report.md:178` (HCQ cell ends "...RA/discoid") |
| Evidence | `make_track2_report.py:404` clips the cell at 160 chars (`md_cell(ped)[:160]`), cutting mid-word. Visible in the submitted file. |
| Severity | MINOR |
| Smallest fix | Truncate at word boundary + ellipsis, or raise the cap. |

### m7 - mechanism.md calls the French GH cohort "the largest"

| | |
|---|---|
| Where | `docs/track2/mechanism.md:185` ("the largest childhood-cancer-survivor cohort found no significant second-neoplasm increase") |
| Evidence | The French CCS cohort (2,852 survivors, 196 GH-treated) is not the largest - the Ergun/CCSS analysis cited next to it (PMID:16822820) is larger and found the positive signal (RR 2.15). The report's own rejected-table wording is accurate ("a later French CCS cohort"); the mechanism doc mislabels it. |
| Severity | MINOR |
| Smallest fix | "a large French survivor cohort". |

### m8 - Pediatric-flag false negatives published in candidates.json

| | |
|---|---|
| Where | `candidates.json` `dasatinib anhydrous.pediatric_flag: "none"` (and `approval.pediatric_labeling: ""`); same class of issue documented for metformin in `engine.md:339-342` + L2b |
| Evidence | Dasatinib's real label (set_id `02b04c6f`, in the dossier) carries pediatric indications >=1y; the engine's openFDA query resolved a label whose `pediatric_use` field is empty, so the published flag says `none`. The flag is honest metadata about a lookup, but a reader diffing JSON vs dossier sees an apparent contradiction. |
| Severity | MINOR |
| Smallest fix | One line in `engine.md` limitations naming the known false-negative pattern (generic-name query hits a label without `pediatric_use` text). |

---

## NIT

| # | Where | What | Fix |
|---|---|---|---|
| N1 | `docs/track2_report.md:341` | "26 uncovered claim sentences" - the current verifier prints **22**; the report's rigor bullet is a generated number that went stale when the detector changed in the same commit. | Regenerate the report; or phrase the bullet as the report-only count (0 uncovered in the submission under `--coverage-strict`). |
| N2 | `docs/track2_report.md:177` | niacin row shows "first approval -" - the dossier's approval block lacks `chembl_first_approval` for the niacin entry. | Fill the field in `dossiers/nicotinamide.json` (ChEMBL reports 1982 for niacin). |
| N3 | `docs/track2/agent_reports/L3.md:17` vs `:31` | "51 queries" vs "50 queries" in the same file; and stale screen totals "1,616 records, ~380 screened" vs committed candidates.md's 1,614 / 264. | Correct to 50 / 1,614 / 264. |
| N4 | `docs/track2/agent_reports/L4.md:89` | "All 12 T2 prompts" - form_map.md maps 11 prompts (sharedStrings 2, 13-20, 22, 23); the report answers all 11. | "all 11". |
| N5 | `docs/track2/STATUS.md` | "508 tests" - current suite is 510 passed / 10 skipped. | Refresh at next status update. |
| N6 | `docs/track2/mechanism.md` vs report line 44 | Rounding drift: "91.1 / 54th percentile" vs report's "91.06 / 53.7th" - same JSON source, cosmetic mismatch. | Optional - use the JSON decimals in both. |
| N7 | `docs/track2/abstract.md:57` | "Word count: 444" - body measures ~431-458 depending on whether citation tokens count. Under the 500 cap either way. | Recompute or drop the count line. |
| N8 | `docs/track2_report.md:103` | gefitinib shown under "axis A" (rescue) though its SIRT2 edge is the counter-productive direction; flagged neutral only because no typed inhibitory evidence was recorded. Semantics documented in engine.md but a reader may misread "axis A" as "aligned". | Optional one-word header clarification ("axis touched", not "axis aligned"). |

---

## Checked clean - what the hostile review could NOT fault

Recorded so the lead knows what is solid. Every item verified against the
committed artifacts and, where load-bearing, against the primary source.

**Geneticist seat - mechanism claims all reproduce.**

- Per-allele table (report lines 35-48) matches `mechanism.json` exactly:
  stop_gained, exon 17/23, PTC 748 nt upstream of last junction (50-55 nt
  rule), 736-aa/29.9% loss incl. kinase-like domain, CADD phred 36/phyloP
  4.189; missense exon 23/23, SIFT 0.01, PolyPhen 0.997, REVEL 0.472
  (honestly flagged below supporting thresholds), CADD 24.5,
  AlphaMissense 0.9229, phyloP 5.115, pLDDT 91.06, 27 residues <8 A.
- ClinVar exact-allele handling correct: Pathogenic/LP for the stop
  (VCV000533901.9); NO entry for c.3006T>G; the c.3006T>A VUS
  (VCV004600147, single submitter) correctly described as "same
  amino-acid change via", not the queried allele. No exact-allele trap
  error.
- gnomAD figures match: exomes 115/1,461,846 and 1/1,461,878; genomes
  5/152,174 / absent.
- NMD stated as prediction everywhere (table "predicted", u3, pathway
  table "predicted"). Phase caveat present at report lines 23, 65, 349
  and in the abstract's limitations; "0 spanning reads" matches Track 1
  report wording.
- No diagnostic or treatment statement directed at the child anywhere;
  the disclaimer banner (line 7) precedes all content.

**Pharmacologist seat - approvals and label facts verify.**

- Live ChEMBL spot-check (2026-10-13): dasatinib, everolimus, niacin,
  niacinamide, hydroxychloroquine, chloroquine, metformin, aspirin,
  sirolimus - all `max_phase 4`, not withdrawn, first-approval years
  match the dossiers.
- Quercetin plainly labeled a supplement, not a drug, in both report
  (lines 282, 292) and dossier; the D+Q pair is honest that only
  dasatinib is approved.
- Niacin's "no pediatric approval" quoted verbatim from the label; HCQ's
  malaria-only pediatric indication stated; boxed warnings named where
  present (sirolimus malignancy/immunosuppression, metformin lactic
  acidosis); no dosing table is presented as advice - the dossier tags
  label dosing text as "quoted label fact, not advice".
- "Hypothesis, not medical advice" appears at the top banner, plain
  language, methods Q10, the abstract and the family document.
- Label-verbatim pediatric indications check out (dasatinib >=1y
  Ph+ CML/ALL; everolimus TSC-SEGA >=1y, TSC seizures >=2y; metformin
  RIOMET >=10y; sirolimus >=13y transplant).

**Statistician seat - every headline number reproduces.**

- Benchmark (benchmark.json): per-case ranks TSC2 #3 (everolimus),
  PIK3CA #2, KCNJ11 #10, CFTR #6, GLA #2, four null; recall
  0.00/0.333/0.556/0.556 computed independently - matches. `v1_frozen`
  block shows 0.444 pre-direction; git history confirms config+truth in
  the first commit and the direction layer added in `933c196` after -
  disclosure present (engine.md:125, report:121, config comment).
- Engine output: 59 kept / 37 excluded / 96 total; dasatinib anhydrous
  #43, everolimus #12, sirolimus #2, palbociclib #1 - all match the
  shortlist table's "engine placement" column; "not in module" for
  niacin/HCQ verified against `collected_names`.
- PRISM (prism.json): 1,498 compounds, 588 launched, Spearman +0.719 /
  p=2e-229 / 80% sign / 1,442 matched - verified; minimum launched q =
  0.069 (epirubicin, aneuploid-RESISTANT direction - correctly framed as
  "top directional hits", not as significance); 42/50 mitotic drugs
  aneuploid-resistant verified; `prism.weight: 0.0` in config.
- ESM (esm.json/esm_150m.json): -5.81/88th pct vs -0.37/48th pct, 1,319
  scored, 1 classified pathogenic missense, query excluded from
  background - all match report lines 160-163.
- Literature screen: 50 queries, 1,614 hits, 264 screenings, 51 papers -
  summed independently from `candidates.md` query log.
- Citation gate (`tools/verify_citations.py --offline`): 136 distinct,
  0 unresolved, 0 retracted, 0 mismatches - PASS, exit 0.
- Tests: `pytest tests/test_t2_*.py tests/test_track2_*.py
  tests/test_verify_citations.py` -> 132 passed; full suite ->
  **510 passed, 10 skipped** (expected skips only: patient-data and
  optional-extra tests).
- Config hashes: `config_dict_hash` recomputed independently -
  v1 `16a5ee58...`, v2 `f4b0cca2...` - match the recorded artifact
  hashes.
- Citation content spot-checks (abstracts read for every load-bearing
  claim): Baker 2011 p16 clearance, North 2014 SIRT2/NAD+/K668, Zhu 2015
  D+Q pair, Hickson 2019 9-patient pilot, Justice 2019 IPF n=14, Tang
  2011 CQ/AICAR/17-AAG selectivity, Wu 2023 SIRT2-OE conditional on
  BubR1, JCI 2020 mTORC1-sarcopenia correlation, CAPP2 ITT HR 0.65
  (0.43-0.97) colorectal-only, GH RR 2.15 (1.3-3.5) + French null,
  metformin 1-16 mM micronuclei + BUBR1/MAD2, HSCT rejection +47 /
  death +156, benzimidazole in-vitro micronuclei at in-vivo-plasma
  levels, Cohen-Sharir SAC vulnerability, Quinton WGD/KIF18A, AACR
  surveillance recs - all support the claim attached to them.
- No p-hacking signature found: the direction layer's recall gain is
  disclosed as post-freeze, the v1 number is published alongside, the
  misses are listed, and the 37 exclusions are named with would-be
  ranks rather than hidden.

**Patient-advocate seat - respectful, honest, no overreach.**

- FAMILY_SUMMARY.md: truthful ("most ideas that look good at this stage
  do not work out"), no hype, GH rejection explained fairly, nothing
  beyond Track-1-published facts, ends in a falsification plan not a
  promise.
- Acknowledgement present **verbatim** in the report (line 382) and the
  family doc - identical text to Track 1.
- No patient detail anywhere beyond the 8 published HPO terms, 2
  published variants, gene and transcript - checked against Track 1.
- A family member would feel respected, not used: the family doc opens
  with "nothing here should be given to anyone", and the rejected-
  growth-hormone paragraph shows the authors anticipated the question a
  parent would actually ask.

## One structural observation (not a defect, but the panel will notice)

Only 2 of the 4 portfolio leads appear anywhere in the engine's output
(dasatinib #43, everolimus #12); niacin/nicotinamide and HCQ/chloroquine
were never even collected - their targets do not intersect the disease
module. The report discloses this honestly ("not in module", engine.md
structural-blindness section, L3b report), and the benchmark itself
measures that blind spot. But a skeptical panel may ask what the engine
contributes beyond corroboration - the strongest honest answer is the
direction layer plus the benchmark receipt, and the report should make
that argument explicitly rather than leaving the reader to infer it.
