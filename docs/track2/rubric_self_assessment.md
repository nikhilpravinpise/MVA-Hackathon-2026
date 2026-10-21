---
title: Rubric self-assessment
nav_order: 9
parent: Track 2
---
# Track 2 rubric self-assessment (L13, second hostile review)

Date: 2026-10-13. Reviewed version: HEAD `4041b35`
(`docs/track2_report.md` generated from commit `01d0809`, regenerates
byte-identical at HEAD modulo the stamp - verified). Official weights:
**Scientific Rigor 35%, Potential Impact 25%, Innovation 25%,
Scalability 15%**. Gate 7 (docs/track2_plan.md section 3) requires
self-score >= 85% per criterion - stated plainly below where we are
below that.

This supersedes the L9 assessment (84/86/85/87, weighted 85.2). Since
then both MAJORs closed and verified against primary sources, all MINOR
closures checked, and one new MAJOR found in this review (R1, the
openFDA-label clause in the gate description - one-clause fix, three
surfaces). Scores are what a skeptical judge who verified the claims
would defend.

---

## Scientific Rigor - weight 35% - **86/100** - meets gate, thin margin

### Evidence for the score

- Every number in the submission re-derives from committed evidence:
  funnel sums exactly (482 = 96+115+6+252+13, `candidates.json`
  `funnel`), ranks match (`sirolimus` #2/59 post / #21/96 pre),
  "19 of raw top 20 mechanism-opposed" verifies exactly, recall
  0.00/0.33/0.56/0.56 matches `benchmark.json`, config sha
  `f4b0cca2092b` recomputed independently (redteam2.md).
- Citation gate: 136/136 resolve, retraction-checked, 0 uncovered under
  `--coverage-strict`, 0 HTTP requests - verified by re-running
  `tools/verify_citations.py --offline` (exit 0). The line in the
  report is generated live, not typed.
- The two prior MAJORs are properly closed: "top mechanism-aligned"
  replaces the false superlative, and the everolimus 4.1y/growth/
  infection facts were re-sourced to the openFDA label - I pulled
  set_id 01f7b5fb live and every quoted number is verbatim in it.
- Counter-evidence stays in-line: D+Q's tumour-suppression risk
  (report:196), metformin genotoxicity (:280), nicotinamide's sirtuin
  paradox (:241), GH mixed evidence (:81/:290), PRISM null result
  published (:141), model disagreement reported (:163).
- Pediatric flags: all 30 `labeled` flags quote genuine label text
  (independently checked 5 untested ones - methenamine, pentetic acid,
  celecoxib, levothyroxine, ethinyl estradiol); no false positive
  found. Dossier approvals verified live on ChEMBL (7/7 max_phase 4,
  not withdrawn, first-approval years match).
- Uncertainty carried honestly: phase unknown stated at :11, :65,
  :349 and now in the family doc; NMD labeled a prediction; REVEL
  0.472 flagged; "no MVA drug-treatment study exists" repeated.

### Strongest argument against

The package still prints a method claim its own evidence disproves: the
gate is described as requiring "an openFDA label" (report:88,
abstract:15, scenes.yaml:62) while 11 of 96 gated records have
`fda_set_id: null` - three of them in the printed top-20 table (R1).
Add: one literature misattribution the gate cannot see (NMN credited
with the H/H lifespan result that belongs to SIRT2-OE - r1), a
demonstrated hole where percent claims never trigger the coverage
detector that reports "0 uncovered" (r2), a replay test that pins
scores but not the audit fields (`pediatric_flag_evidence`,
`approval.*`, all top-level metadata) the honesty claims rest on (r3),
and a published `none` flag on acetaminophen that openFDA's own corpus
contradicts (r4). The machinery is real; the claim "no number
hand-typed / every claim checked by code" still asks the artifacts to
be stricter than the checks actually are.

### Highest-impact improvement

Fix R1 (one clause in template + abstract + scenes.yaml). It is the
only finding a judge can disprove in under a minute; deleting it
realigns the printed method with the correct one in engine.md:83.

---

## Potential Impact - weight 25% - **86/100** - meets gate

### Evidence for the score

- The testability matrix (report:307-330, `testability.json`) maps
  every lead and adjunct onto the MVA Society's four funded programs
  with assay, GO/NO-GO threshold, cost tier and time - and the
  universal no-go rule (any aneuploidy rise) is stated as the
  override. The fibroblast panel is now foregrounded as "the decisive
  tier" (:330) - the L9 presentation fix.
- A non-drug recommendation stands independently of every drug
  hypothesis: mechanism-guided cancer surveillance per AACR workshop
  (:284, :75) - actionable today.
- The rejected table (:288-305) answers the questions families actually
  ask (growth hormone, HSCT, mebendazole) with mixed-evidence framing.
- FAMILY_SUMMARY.md translates the whole thing honestly - disclaimer
  first, phase caveat inline, "sixteen ideas we rejected" matches
  rejected.json.
- Axis framing generalizes to other MVA genes (CEP57/TRIP13/MAD1L1
  seeded in config).

### Strongest argument against

No MVA drug-treatment study exists - every lead is mechanistic
extrapolation at one-to-three model-systems remove (BubR1-hypomorph
mouse senolysis; a correlational mTORC1-sarcopenia link; an NAD+/SIRT2
axis never tested in MVA tissue; a chloroquine screen in engineered
trisomic MEFs). "Potential" is entirely contingent on unran
experiments, and the candidate list converges on what competitors also
proposed (landscape.md) - the delta is testability, not novelty of
molecule.

### Highest-impact improvement

Unchanged from L9 and partially done: the decisive first experiment
(fibroblast aneuploidy panel) is named at :330 - one more sentence
saying what a positive unlocks (which lead graduates to the Society's
animal-model program) would complete it.

---

## Innovation - weight 25% - **86/100** - meets gate

### Evidence for the score

- Per landscape.md (~30 repos, ~8 substantive T2 efforts), still true
  after this review: no competitor shows a frozen retrospective
  recall@k benchmark, approval-by-code, a citation-resolution +
  retraction gate, a pediatric-label classifier, or a program-mapped
  testability matrix.
- The direction layer remains the field's most original move: 37
  mechanism-opposed drugs excluded *and published with would-be ranks*
  (:115) - adversarial honesty as infrastructure.
- The L9 suggestion is implemented: report:117 now argues explicitly
  what the engine proved (independent mTOR corroboration + the
  exclusion receipt a hand-written shortlist cannot show).
- Byte-exact offline replay of every API response; the generator
  refuses unfilled placeholders and em dashes.

### Strongest argument against

The algorithmic core is conventional (target overlap + STRING proximity
+ LINCS reversal); the innovation is the rigor wrapper, not the search.
Only 2 of 4 leads appear in engine output at all (dasatinib #43,
everolimus #12); niacin and HCQ were never collected - disclosed at
:117, but a judge weighting "novel candidate identification" over
"verification pipeline" sees a literature-curated shortlist in engine
clothing. The new gate-prose error (R1) slightly undercuts the "the
code is the claim" positioning.

### Highest-impact improvement

None new needed. The made-explicit argument at :117 is the right one;
R1's fix protects it.

---

## Scalability - weight 15% - **87/100** - meets gate

### Evidence for the score

- Gene-agnostic engine, config-driven (`config/track2.yaml`,
  engine.md); nothing BUB1B-specific in `src/track2/` - verified by
  reading it.
- The benchmark is the measured receipt: identical pipeline, 9
  unrelated genes, honest recall incl. structural misses.
- Verified end-to-end offline: report regenerates byte-identical,
  citation gate runs on committed cache with 0 requests, 531 tests pass
  on fixtures, upload copy byte-identical.
- The citation gate is a drop-in tool other teams can reuse.

### Strongest argument against

recall@10 = 0.56 is the honest ceiling - the engine structurally misses
drugs acting outside the module (4 of 9 cases), so "scalable" means
"scalably finds module-adjacent drugs". The label-resolution tail still
produces flag false negatives on first-hit empty labels (r4), and a
fresh clone cannot discover the Track 2 rebuild path from README (r6)
- the capability works but the signpost does not. "Replays offline"
also means replay of THIS run; a new gene still needs the live pass.

### Highest-impact improvement

README Track 2 block (r6) - it converts the demonstrated
reproducibility into something a judge can find.

---

## Weighted self-score

| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Scientific Rigor | 35% | 86 | 30.1 |
| Potential Impact | 25% | 86 | 21.5 |
| Innovation | 25% | 86 | 21.5 |
| Scalability | 15% | 87 | 13.05 |
| **Total** | | | **86.15** |

**Gate 7 status: all four criteria at/above 85** - but Rigor sits at 86
on the strength that the *implemented* gate is correct; if a panel
weights the printed method claim (R1) as heavily as L9 weighted the
sirolimus superlative, Rigor is 84-85 until the clause is deleted. The
weighted number masks how thin the Rigor margin is: one unfixed MAJOR
costs ~1-2 points on the 35% criterion.

## Prioritised remaining fix list

1. **R1 (MAJOR)** - drop the openFDA-label clause: template:55 ->
   report:88, abstract.md:15, scenes.yaml:62. Regenerate report + video.
2. **r5** - scenes.yaml staleness in the same pass: 508 -> 531,
   "committed before the run" -> the corrected wording, drop STRING
   from drug-name sources.
3. **r1** - NMN/SIRT2 clause in `portfolio.json` adjunct text
   (propagates to report:283).
4. **r4** - engine.md: name the empty-label first-hit false-negative
   mode (acetaminophen example); optionally retry limit=5 on all-empty
   labels.
5. **r6** - README Track 2 reproduction block.
6. **r2** - coverage detector `%` fix + wider verbs; re-adjudicate.
7. **r3** - replay test compares all top-level keys; `_norm_cand`
   carve-outs confined to the stale branch.
8. **n1-n4** - cosmetic.

## Verdict on top-three placement

**Top three, most likely top two - conditional on the one-line R1 fix
before upload.** The differentiators survived a second hostile pass:
the benchmark, the code-checked approval gate, the citation gate and
the testability matrix are all real and verified, and no competitor in
landscape.md publicly matches any one of them. The residual ceiling is
the same as L9's: candidate novelty (the four leads are the field's
convergent answer) and whether the panel scores verification rigor over
mechanistic boldness.

## Post-review update (2026-10-17)

R1 (the openFDA-label clause) is closed: the report (line 88), abstract
and `video/scenes.yaml` now say the label is looked up per candidate and
is not part of the gate. L14/L15/L16 closed the remaining listed fixes.
The scores above were not re-run; this note only records that the
condition for the Rigor margin (R1 unfixed) no longer holds. Current
counts at HEAD on 2026-10-21: 137/137 citations resolve, and the suite is
575 collected (572 pass, 3 environment-only skips: patient VCF, PDF,
video). The 136/136 and 531-test figures above are the 2026-10-13
snapshot.
