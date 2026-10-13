# L13 - Second hostile red team on the corrected Track 2 package

Date: 2026-10-13. Reviewer: lane L13, read-only outside owned paths.
Version reviewed: HEAD `4041b35` (committed state; `git status` clean).
The report embeds "generated ... from commit `01d0809`"; content at HEAD
regenerates byte-identical except that stamp (verified, section "checked
clean" below).

Method: read the plan, `redteam.md`, L10/L11/L12 closure reports; then
re-checked every closure against live artifacts, attacked surfaces the
first review never reached (family doc, video script, submission fields,
PDF renderer, Makefile, fresh-clone reproducibility), re-derived every
headline number from committed JSON, spot-checked approval/label facts
against live ChEMBL and openFDA, ran the full suite and the citation
gate, and scratch-mutated committed evidence to probe the equality
tests.

Severity: BLOCKER = disqualifying or materially misleading if submitted;
MAJOR = a judge can catch it and it damages a headline claim;
MINOR = real but small - wording, accounting, or stale number;
NIT = cosmetic.

## Verdict up front

No BLOCKER. **One new MAJOR**: the method prose claims the approval gate
requires an openFDA label; the gate does not, and 11 of the 96 gated
records have no label - the claim is printed in the report, the
submitted abstract, and the video script.

The first review's two MAJORs are genuinely closed (both verified against
primary sources, not just reworded). All eight MINORs are closed except
one residue inside the video script. The new findings are one MAJOR, six
MINORs, and four NITs.

---

## MAJOR

### R1 - "with an openFDA label" / "plus an FDA label" - the described approval gate is not the gate that ran

|||
|---|---|
| Where | `docs/track2_report.md:88` ("keeps only approved medicines (ChEMBL max_phase 4, not withdrawn, **with an openFDA label**)"), generated from `docs/track2_report_template.md:55`; `docs/track2/abstract.md:15` ("ChEMBL max_phase 4, not withdrawn, **openFDA label present**"); `video/scenes.yaml:62` ("96 pass ChEMBL phase 4 **plus an FDA label**") |
| Evidence | `src/track2/engine.py:278-310` - `approval_gate()` checks only `max_phase == 4` and `not withdrawn_flag`. openFDA is queried later, per approved candidate, for evidence. The committed `docs/track2/evidence/candidates.json` contradicts the printed gate directly: 11 of the 96 gated-in records have `fda_set_id: null` and `openfda_match: ""` - omacetaxine mepesuccinate (#6), phenylbutanoic acid (#8), abemaciclib (#9), zanubrutinib, dicumarol, copanlisib, cinnarizine (#55), and in the excluded set pixantrone, amsacrine, teniposide, panobinostat. Recorded 404 fixtures exist for each (the engine asked openFDA and got nothing). Cinnarizine additionally has `fda: false` - no FDA label *and* no FDA approval evidence; it gates in on ChEMBL max_phase 4 alone. Live spot-check confirms these are genuine openFDA coverage misses (e.g. `openfda.generic_name:"OMACETAXINE MEPESUCCINATE"` returns 404 on a 263k-label index), not dropped queries. Three of the no-label records sit inside the printed top-20 table (ranks 6, 8, 9) whose pediatric column reads "none" - a reader who knows "none" can mean "no label hit" can disprove the claim from the submission itself. |
| Severity | MAJOR - a false method claim about the headline differentiator ("approval checked by code"), printed in three submission surfaces including the abstract, and disprovable from the committed evidence file. Same class as L9's M1/M2: a printed claim the artifacts disprove. The engine is correct and `docs/track2/engine.md:83` documents the real gate - only the submission prose lies. |
| Smallest fix | Delete the clause in all three places. Report/template: "(ChEMBL max_phase 4, not withdrawn; openFDA labels read for evidence where present)". Abstract: drop "openFDA label present". scenes.yaml:62: "96 pass ChEMBL phase 4 (openFDA label read where one exists)". |

---

## MINOR

### r1 - NMN credited with the H/H-mouse lifespan extension the paper gave to SIRT2 overexpression

|||
|---|---|
| Where | `docs/track2_report.md:283` ("NMN is the actual NAD+ precursor that raised BubR1 abundance **and extended lifespan in BubR1-hypomorphic mice** (PMID:24825348)") and the identical sentence in `docs/track2/evidence/portfolio.json` adjuncts `NR / NMN` `why` field; softer echo at `docs/track2/FAMILY_SUMMARY.md:50` ("in mice bred to have the same shortage, raising NAD+ helped") |
| Evidence | PMID:24825348 (North 2014) abstract, read live: "Overexpression of SIRT2 or treatment of mice with the NAD(+) precursor nicotinamide mononucleotide (NMN) increases BubR1 abundance in vivo. **Overexpression of SIRT2** in BubR1(H/H) animals increases median lifespan" - the lifespan-in-H/H result belongs to SIRT2 overexpression; NMN's result is BubR1 abundance (in non-H/H animals). The same report states this correctly at lines 233 and 237 ("NMN or SIRT2 overexpression raised BubR1 abundance ... **with SIRT2 overexpression extending lifespan** specifically in BubR1-hypomorphic animals"), so the supplement bullet contradicts the report's own accurate phrasing. This is exactly the mis-citation class L9 flagged as M2 - a correct PMID attached to a claim the paper does not make; the citation gate cannot see it because title/year resolve. |
| Severity | MINOR - one clause in a supplement-adjunct bullet (and the portfolio `why` it renders from), not a lead claim; the true version is printed elsewhere in the same document. |
| Smallest fix | "...that raised BubR1 abundance in vivo in the anchor study (the same study's lifespan extension in BubR1-hypomorphic mice used SIRT2 overexpression)". One clause, in `portfolio.json` only - report regenerates. |

### r2 - Coverage gate cannot see percent claims, and misses ordinary mechanism prose

|||
|---|---|
| Where | `tools/verify_citations.py:125-133` (`_NUM_UNIT` includes `%` inside the unit group but the group ends with `\b`, which can never match after a non-word `%`); `:121-124` (`_MECH_VERBS` is a 14-lemma list); `:483-499` (`_trigger_sentences`) |
| Evidence | Demonstrated on the shipped corpus by calling the gate's own functions: `vc._trigger_sentences("Response rate was 35%.")` -> `[]`; "sign concordance 80% across drugs" -> `[]`; "upto 96% of patients" -> `[]`; a table cell "29.9%" -> `[]`. Unitless numerics also escape: "Spearman rho was 0.72 across the matched drugs." -> `[]`; "Recall at rank 10 was 0.56." -> `[]`. Mechanism claims using verbs outside the list escape: "Sirolimus suppresses SASP secretion in senescent cells." -> `[]` ("suppresses" unlisted); same for clears/stabilises/restores/blocks/blunts. So the strict gate's "0 uncovered claim sentences" (report:341, generated live by `citation_gate_line()`) is literally true but weaker than it reads: entire claim classes are invisible to the detector, not adjudicated and cited. Verified the hole does not bite at HEAD: every %-bearing unit in the report also carries a citation or `[repo:]` ref (the everolimus "96%/35%" risk bullet at report:225 is trigger-invisible but carries `[repo:openFDA label 01f7b5fb]`). |
| Severity | MINOR - a demonstrated detector hole under a generated "0 uncovered" receipt. The shipped text is genuinely cited; the gate's coverage claim overstates what it inspects. |
| Smallest fix | Move `%` out of the `\b`-terminated unit group (or drop the trailing `\b`), add the common pharmacology verbs, and have the strict gate count %-claims. Re-run; expect a few new flags in candidates.md/table rows - fix or exempt them explicitly. |

### r3 - The "strict equality" replay test does not compare all of the evidence it claims to pin

|||
|---|---|
| Where | `tests/test_track2_engine.py:136-145` (`_norm_cand` pops `pediatric_flag_evidence` and `approval.{fda_set_id,combination_label,openfda_match}` from both sides before diffing); `:178-217` (the loop compares only `candidates`, `excluded_mechanism_opposed` and `funnel`; every other top-level key - `module`, `direction`, `provenance`, `lincs`, `collected_names`, `prism`, `case`, `seed_genes`, `schema`, `generated_by` - is never compared) |
| Evidence | Scratch-mutation test (mutated copies of committed `candidates.json`/`benchmark.json`, test logic replicated read-only): mutating `pediatric_flag`, a candidate score, dropping a candidate, `funnel.merged`, and a network-proximity z are all caught. Mutating `module` (71->72), `direction.n_aligned`, `approval.fda_set_id`, `approval.openfda_match`, `pediatric_flag_evidence` (the verbatim winning sentence a reader inspects to judge the flag), and `collected_names` all pass undetected. L12's two-line funnel fix itself is verified correct: `merged` is popped from both sides and the arithmetic closes (482 = 96+115+6+252+13). The gap is that flag/set_id have top-level twins that ARE compared, so the visible headline fields are pinned, but the evidence-record fields behind them are not. |
| Severity | MINOR - the test still catches every mutation that changes a number a reader sees; it does not pin the audit fields the package's honesty claims rest on. |
| Smallest fix | Compare all top-level keys except `generated_at`/`config_sha`, and either keep the `_norm_cand` carve-outs only inside the (now-dead) `stale` branch or drop them. |

### r4 - `pediatric_flag: "none"` for acetaminophen is a published false negative the L11 fix does not reach

|||
|---|---|
| Where | `docs/track2/evidence/candidates.json` - acetaminophen (rank 52): `pediatric_flag: "none"`, `fda_set_id` `0005aafa...`, `openfda_match: "matched via generic_name"`; same residual class on cyclosporine (#25, flag `none` - the picked label is the Vevye ophthalmic label "safety/effectiveness not established", while transplant labels document pediatric use) |
| Evidence | Live openFDA (2026-10-13): `openfda.generic_name:"ACETAMINOPHEN"` returns thousands of labels; the engine's `limit=1` hit (set_id 0005aafa) is an OTC oral label with empty `pediatric_use`/`indications`/`dosage` pediatric text, while other openFDA acetaminophen labels carry an explicit pediatric indication (injection labeling established in patients >=2 years). Under the project's own classifier those labels flag `labeled_pediatric_indication`. The L11 refinement only runs when the first hit is a *combination* product (`sources.py:282-296`); a single-ingredient label with empty pediatric fields wins and is never re-queried. So the flag on acetaminophen records the hit, not the drug's pediatric status. `engine.md:393-400` discloses "the flag is only as good as the label openFDA happens to serve" - but names the combo-hit failure mode, not this single-ingredient empty-fields one. No false positive found anywhere in the committed flags (see checked-clean); this is the remaining false-negative direction, which engine.md says is the preferred error direction - but it is still a published wrong flag on a drug every clinician judge knows. |
| Severity | MINOR - acetaminophen sits at rank 52 and enters no lead or dossier, so nothing downstream consumes the error; the flag's semantics (label-derived hint, not safety call) are documented. It is nevertheless a disprovable published flag. |
| Smallest fix | One line in `engine.md` limitations: "a single-ingredient label with empty pediatric fields is accepted on first hit; drugs with pediatric labeling elsewhere in openFDA (e.g. acetaminophen) can therefore still flag `none`". Optionally: retry `limit=5` also when the picked label has all three sections empty. |

### r5 - Video script carries stale numbers and the un-fixed m4 wording

|||
|---|---|
| Where | `video/scenes.yaml:86,91` ("truth committed before the run", "with the answer committed before the run"); `:138` ("508 tests"); `:144` ("five hundred tests"); `:61` ("482 drug names from Open Targets, ChEMBL, DGIdb and STRING" - STRING supplies module genes, not drug names); `:62` (the R1 gate clause) |
| Evidence | Suite is 531 passed / 10 skipped at HEAD (`pytest tests -q`, run for this review) - "508" predates the L10/L11/L12 test additions. The m4 wording was corrected in the report and template ("declared in config/track2.yaml ... reads at run time") but not in the video script - the audio literally repeats the claim git timestamps disprove. "482 drug names" came from OT clinical rows + DGIdb interactions (funnel JSON); STRING contributed the 71-gene module - the bullet attributes names to a source that yields none. The header comment (scenes.yaml:2-4) says "Every number here must exist in docs/track2/evidence/" - 508 and the FDA-label clause do not. |
| Severity | MINOR - stale/incorrect claims in a submission asset that is already rendered (`video/out/pitch.mp4`, 178.93 s) and awaiting upload; a judge who replays the script against the repo catches "508" in seconds. |
| Smallest fix | "531 tests" (or "over 500"), "the answer declared in the frozen config the engine reads", drop STRING from the name sources, drop the FDA-label clause (R1). Requires a re-render of `pitch.mp4` before upload. |

### r6 - README has no Track 2 reproduction path, though submission_fields tells judges to "see README"

|||
|---|---|
| Where | `docs/track2/submission_fields.md:30` ("One command rebuilds report, figures and video: see README"); `README.md` - entire file is Track 1; the only Track 2 mention is a parenthetical in the tests bullet (also stale: "519 tests") |
| Evidence | A judge cloning the repo per the submission note finds `make track1`, `make report`, `make all` - no Track 2 targets. The real commands exist only in `Makefile` (`track2`, `track2-report`, `track2-citations`, `track2-all`) and work: `make_track2_report.build()` run in-process regenerates the committed report byte-identical (modulo the commit stamp), `verify_citations.py --offline` exits 0 with 0 HTTP requests, `pytest` is green offline. The capability is real; the signpost is wrong. |
| Severity | MINOR - discoverability gap on the headline reproducibility claim; nothing actually fails. |
| Smallest fix | Four-line "Track 2" block in README reproducing the three commands, or change the submission_fields pointer to `Makefile`. |

---

## NIT

| # | Where | What | Fix |
|---|---|---|---|
| n1 | `docs/track2_report.md:5` | Stamp says "generated ... from commit `01d0809`" while the file was committed in `643a70d`; inherent one-commit lag of a generated stamp (the generator embeds HEAD at build time and is committed with its output). Content is current - regenerating at HEAD changes only this line. | Optional: note in `engine.md`/generator docstring that the stamp is the pre-commit HEAD, or post-commit amend regeneration. |
| n2 | `docs/track2/agent_reports/L3.md:17` vs `:31`; `L4.md:87` | N3/N4 remain open: L3.md still reads "51 queries" vs "50" and "1,616 / ~380" vs the committed 1,614/264; L4.md still says "All 12 T2 prompts" where form_map.md maps 11. Internal notes only - nothing submission-facing. | Correct the two lines, or accept as dated lane notes. |
| n3 | `src/track2/direction.py:245` | `pediatric_flag_evidence.text` is clipped at 240 chars with no word-boundary or ellipsis handling: dabrafenib ends "...of which", pentetic acid "...glomerular". The same mid-word clip L9 flagged (m6) in report cells, surviving in the evidence JSON. | Clip on word boundary + " ..." like `make_track2_report.py` does. |
| n4 | `src/track2/sources.py:241` | `openfda_pick_single` uses bidirectional substring match (`base in a or a in base`): "SIROLIMUS" is a substring of "TEMSIROLIMUS", so a temsirolimus label in a sirolimus refinement would pass the coverage test. Not triggered in committed evidence (all picks verified molecule-correct, incl. methylprednisolone 01f0126c, methenamine 131a1322, octocrylene combo correctly flagged). | Token-match on split/upper-cased actives rather than substring. |

---

## Closures verified hostilely (first red team, L9 -> L10/L11/L12)

Each item re-checked in the live artifacts, not in the closure prose.

- **M1 "sirolimus top non-cytotoxic" - CLOSED and now true.** Report
  lines 117/211/279 and `portfolio.json` all read "top
  mechanism-aligned"; candidates.json confirms sirolimus is the top
  `aligned` entry (post-direction #2/59, pre-direction #21/96) with
  neutral non-cytotoxics (palbociclib, glycerin, methenamine) above it.
  No "non-cytotoxic" remains in submission prose.
- **M2 everolimus mis-citation - CLOSED and verified against the live
  label.** Report:211/217 and `dossiers/everolimus.json` now attribute
  115-patient / 4.1-yr / growth-puberty / <6y-infection facts to
  `openFDA set_id 01f7b5fb`, scoping PMID:23158522 to the ~1-year
  EXIST-1 primary. I pulled that label live: it contains exactly
  "median duration of 4.1 years", "did not appear to adversely impact
  growth and pubertal development", and the <6y infection rates
  (96% vs 67%, 35% vs 7% serious). The re-sourcing target is real.
- **m1 abstract/report recall mismatch - CLOSED.** Both print the
  identical labeled pair 0.00/0.33/0.56/0.56 with the frozen
  0.00/0.33/0.44/0.56 beside it (abstract:21-22, report:121).
- **m2 funnel unsummable - CLOSED at data level.** `funnel.merged: 13`
  is now native in candidates.json AND benchmark.json (per-case merged:
  19,29,1,23,14,16,6,48,6); report:90 prints the 13-merge clause;
  arithmetic closes exactly: 96+115+6+252+13 = 482.
- **m3 salt duplicates - CLOSED.** Report:115 names the 7 salt/ester
  forms and prints "distinct active count is 89" (verified: 96 records,
  89 distinct actives).
- **m4 "committed before the run" - CLOSED in report+template
  (:121,:344 now say "declared in config/track2.yaml, which the engine
  reads at run time") but the fix never reached the video script** -
  see r5.
- **m5 phase caveat - CLOSED.** Report:11 plain-language and
  FAMILY_SUMMARY.md:41-45 both carry the unknown-phase caveat now;
  verified the family doc's wording is honest ("nobody has shown it in
  this child").
- **m6 mid-word clip - CLOSED.** `clip()` truncates at word boundary +
  ellipsis (report:176 "... (oral suspension). ..."). Same defect found
  once more in a different surface - n3.
- **m7 "largest" French cohort - CLOSED everywhere.** mechanism.md:186,
  mechanism.json c23 (via the generator, L12 fixed the desync), and the
  rejected-table row all say "a later/large French ... cohort".
- **m8 pediatric false negatives - CLOSED for the tested class.** The
  3-section classifier + pref_name-first label resolution produced the
  pinned deltas (dasatinib/metformin/etc. now `labeled` via real
  sentences); a residual false-negative class survives - r4.
- **N1 uncovered-claims counter - CLOSED.** Report:341's "0 uncovered"
  is generated live by `citation_gate_line()` and matches my offline
  run (136 distinct / 0 unresolved / 0 retracted / 0 mismatches /
  0 uncovered / 0 HTTP requests).
- **N2 niacin first approval - CLOSED.** Dossier records 1982; report
  row prints it; live ChEMBL CHEMBL573/1140 both confirm 1982.
- **N5 STATUS.md "508 tests" - stands as a dated snapshot** (file is
  explicitly "Paused 2026-10-12"); the same number propagated into the
  video is r5.
- **N6 rounding drift - CLOSED.** mechanism.md now prints 91.06 /
  53.7th, matching mechanism.json and the report.
- **N7 abstract word count - CLOSED.** I recounted the body excluding
  `[repo:]` markers: exactly 451 words; the doc says 451 (cap 500).
- **N8 gefitinib "axis A" - mitigated, not removed.** Report table
  still prints axis A for gefitinib, but `portfolio.json
  engine_caveats[0]` now discloses that axis labels are a config map,
  not evidence of benefit (named on gefitinib). Acceptable.
- **L12's out-of-paths test edit - reviewed; correct, with coverage
  caveats in r3.** The two-line `merged` handling keeps the stale-path
  tolerance and the strict path passes; the disclosed intent
  (assert-not-diffs on normalized records) is what the test does - it
  just doesn't normalize away less than the comment implies. No
  weakening found: the pinned L11 delta tables are now dead code (safe
  to delete), not a hole.

## Attacks that did not produce a finding (the hostile homework)

- **Pediatric classifier, five drugs absent from the test corpus** -
  methenamine (dosage-section "pediatric patients 6 to 12 years":
  correct `labeled`; methenamine hippurate really is labeled 6-12y),
  pentetic acid (Tc-99m pentetate label indicates birth-<17y: correct),
  celecoxib (JRA >=2y: correct), levothyroxine ("birth to less than 17
  years": correct), ethinyl estradiol (see below). No false positive
  exists in the committed flags - all 30 `labeled` flags quote real
  label text. The closest to one: **ethinyl estradiol**'s winning
  sentence is a header-glued adult-population claim ("8.4 Pediatric Use
  Safety and efficacy of levonorgestrel and ethinyl estradiol tablets
  have been established in women of reproductive age") - the flag fires
  on the section header's "Pediatric" + "established" while the
  sentence's claim is adult. The outcome is defensible (the label
  extends to postpubertal adolescents) but the quoted evidence does not
  show it - folded into r4's disclosure fix rather than a separate
  finding.
- **Wrong-molecule labels** - every `fda_set_id` attachment in
  candidates.json names the queried active (verified on the risky picks
  live: methylprednisolone -> single-ingredient METHYLPREDNISOLONE;
  methenamine -> METHENAMINE HIPPURATE; octocrylene -> combo kept,
  flagged `combo:true`; temsirolimus -> TEMSIROLIMUS label). The latent
  substring hole is n4.
- **Retained superlatives vs literature** - "only Axis-A candidate"
  (membership fact: niacin is the sole approved-drug lead on axis A;
  NMN/NR are supplement adjuncts, correctly not "candidates"), "only
  candidate with direct aneuploidy-selective evidence" (HCQ - Tang 2011
  screened aneuploid-vs-euploid; aspirin's screen was
  tetraploid-vs-diploid, a distinct claim, verified), "strongest
  pediatric regulatory footing" (everolimus: pediatric indications
  inside a tumour-predisposition syndrome, label-reported 4.1-yr growth
  safety - the comparative is defensible against the other three leads),
  "most direct senolytic after D+Q" (navitoclax, in the rejected table -
  consistent with the senolytics canon). All four survive hostile
  reading; the L10-found false one ("only anchor in the literal disease
  model") is gone.
- **Every spoken/displayed video number** - checked all against
  committed evidence: 71 genes, 482 names, 96 approved, 37 excluded,
  19-of-20 opposed (verified exactly: excluded would-be ranks <=20 count
  19, palbociclib #18 the lone survivor), doxorubicin #1, benchmark
  ranks (alpelisib 2, migalastat 2, everolimus 3, ivacaftor 6,
  glibenclamide 10, losartan not collected), recall@10 0.56 = 5/9,
  "16 rejected" = 16 entries in rejected.json, "four funded programs" =
  mva_programs.json, GO thresholds 50%/30%/1.3x/2-fold = testability.json
  verbatim, "from age 1" dasatinib/everolimus = label-verified, 136/136
  citations = gate-verified. The three wrong numbers are in r5.
- **Fresh-clone reproduction** - report regenerates byte-identical in
  replay/offline mode (only the HEAD stamp moves); citation gate runs
  fully offline; 531 tests pass on recorded fixtures; upload copy is
  byte-identical to the report. Missing piece is only the README
  signpost (r6). Video/PDF need the optional `.venv-video` /
  playwright deps - documented in STATUS/tracked as gitignored outputs;
  the PDF was rebuilt by L12 (386 KB).
- **`make track2-*` semantics** - `track2` runs live mode (a full
  re-pull needs network; honest), `track2-report`/`track2-citations`
  work offline. No target silently fetches in a check path.
- **PDF renderer** - `tools/make_track2_pdf.py` refuses unfilled
  placeholders, inlines `[repo:]` markers as code spans, prints via
  Playwright Chrome; structure sound, PDF exists locally. The renderer
  test is dependency-skipped here (no markdown-it-py/playwright in the
  project venv) - noted, not penalized.

## Checked-clean ledger

Recorded so the lead knows what does not need attention.

- Funnel arithmetic closes natively (482 = 96+115+6+252+13); the
  printed funnel sentence sums.
- Report regenerates byte-identical at HEAD modulo the embedded stamp;
  upload copy byte-identical; no em dash, no unfilled placeholders,
  acknowledgement and GenAI blocks present verbatim.
- Citation gate: 136 distinct, 0 unresolved, 0 retracted, 0 mismatches,
  0 uncovered (strict), 0 HTTP requests - all cache-hit.
- `pytest tests -q`: 531 passed / 10 skipped (expected skips: patient
  data, optional extras). Track 2 glob: 151 collected - matches the
  generated "151 Track 2 tests" line.
- Benchmark numbers reproduce from benchmark.json: recall
  0.00/0.333/0.556/0.556, per-case ranks as printed; config sha
  `f4b0cca2092b` recomputed independently and matches.
- Live ChEMBL spot-check (2026-10-13): all 7 dossier ChEMBL ids return
  max_phase 4, not withdrawn, first_approval matching the dossiers
  (dasatinib 2006, everolimus 2009, HCQ 1955, metformin 1995, niacin
  1982, aspirin 1950, sirolimus 1999).
- Live openFDA spot-check: everolimus label text contains every
  re-sourced fact verbatim; openFDA coverage gaps for the no-label
  candidates are real 404s, not query failures.
- Direction layer: 37 excluded with would-be ranks published;
  "19 of raw top 20" verified; opposed-wins semantics and the
  require_inhibitory guard (dasatinib AURKB stays neutral) check out.
- FAMILY_SUMMARY.md: disclaimer-first, phase caveat present, no
  treatment advice, "sixteen rejected" matches rejected.json, GH
  rejection explained honestly. One soft spot (the NAD+/mice clause)
  folded into r1.
- submission_fields.md: form-field values verified against the live
  form notes; notes-for-judges claims (136/136, recall 0.56, 37
  exclusions) all current; video URL correctly a placeholder for the
  operator.
- testability.json: every threshold the report and video quote exists
  verbatim (T1 2-4w, >=50% senescent-fraction reduction, >=30% SASP,
  >=1.3-fold BubR1, >=2-fold aneuploid preferential depletion,
  universal NO-GO on aneuploidy rise).
- Mutation probe: wrong pediatric_flag / score / candidate drop /
  funnel.merged / proximity-z all still fail the replay tests.
- Two-of-four-leads-not-collected is disclosed in report:117 with the
  engine's "what it proves" argument now explicit (the L9 structural
  observation addressed in prose).

## Prioritised remaining fix list (cost-ranked)

1. **R1** - delete the openFDA-label clause in template/abstract/video
   (three one-line edits + report/video regenerate). Fixes the only
   MAJOR.
2. **r5** - video script staleness (508 -> 531; m4 wording; STRING
   attribution) - same regeneration pass as R1.
3. **r1** - NMN clause in `portfolio.json` (one clause; regenerates
   report:283).
4. **r4** - engine.md one-line disclosure of the empty-label first-hit
   false-negative mode (acetaminophen is the named, checkable example).
5. **r6** - README Track 2 block or repoint submission_fields.
6. **r2** - fix the `%` boundary + verb list in verify_citations.py;
   re-run strict; adjudicate the new flags.
7. **r3** - widen the replay comparison to all top-level keys; confine
   `_norm_cand` carve-outs to the stale branch.
8. **n1-n4** - optional polish.

## Top-three verdict

Against the public field in `docs/track2/landscape.md`, this remains the
most verifiable submission: nobody else shows a frozen blind benchmark,
an approval gate run by code, a citation-resolution+retraction gate, or
a program-mapped falsifiability matrix - and every one of those claims
reproduced under hostile re-verification here. The one new MAJOR is a
one-clause wording fix, not an engineering hole: the real gate is
correct, documented in engine.md, and enforced in evidence; only the
prose overstates it. With R1+r5 fixed before the Oct 23 upload, this is
**top three, most likely top two** - the floor is still the machinery no
competitor publicly matches; the residual risk is unchanged: the four
leads converge on the same molecules the strongest competitors found,
so a panel scoring candidate novelty over verification rigor can still
rank a bolder portfolio first.
