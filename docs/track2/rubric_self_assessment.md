# Track 2 rubric self-assessment (L9, hostile review)

Date: 2026-10-13. Reviewed version: `docs/track2_report.md` generated
from commit `9a2083d` (committed `97ea2b7`). Official weights:
**Scientific Rigor 35%, Potential Impact 25%, Innovation 25%,
Scalability 15%**. Gate 7 (docs/track2_plan.md section 3) requires
self-score >= 85% per criterion with justification - stated plainly
below where we are below that.

Self-scores are deliberately harsh: each is what a skeptical judge who
verified the claims would defend, not what the authors hope for.

---

## Scientific Rigor - weight 35% - **84/100** - BELOW GATE 7

### Evidence for the score

- Every number in the submission is generated from committed evidence
  files (report header line 5; `portfolio.json`, `candidates.json`,
  `mechanism.json`, `prism.json`, `esm.json`, `benchmark.json`) and
  every one I re-derived matches - funnel, ranks, recall, PRISM, ESM,
  screen flow, citation count (redteam.md "checked clean" ledger).
- Citation gate: 136/136 resolve, retraction-checked, offline
  (`tools/verify_citations.py`, report line 341). Every load-bearing
  abstract I read supports its claim (redteam.md).
- Uncertainty is carried, not smoothed: phase unknown (lines 23, 65,
  349), NMD as prediction (line 67), REVEL 0.472 flagged (line 68),
  ESM model disagreement reported (lines 160-163), PRISM null result
  published (line 141), benchmark misses named with cause (line 135).
- Approval status machine-verified; supplements never presented as
  approved; pediatric label facts quoted verbatim, never converted to
  dosing advice.
- Counter-evidence is in-line, not buried: the D+Q tumor-suppression
  risk (line 196), metformin's own genotoxicity (line 280),
  nicotinamide's sirtuin paradox (line 241), the GH mixed-evidence
  framing (line 290).

### Strongest argument against

The rigor machinery is excellent but the review still found **two
factual errors in the submission text** - the false sirolimus
"non-cytotoxic" superlative (M1) and the everolimus 4.1-year data cited
to a PMID that does not contain it (M2) - plus a funnel sentence that
cannot be summed from printed numbers (m2), 7 undisclosed salt-form
duplicates inside "96 approved" (m3), an abstract/report version
mismatch on the headline recall figure (m1), and a "committed before
the run" claim contradicted by git timestamps (m4). A panel judge who
spot-checks either MAJOR finds a claim the artifacts do not support -
which is precisely what the "no number hand-typed" promise says cannot
happen.

### Highest-impact improvement

Fix M1 and M2 (both one-line changes) and reconcile the abstract's
recall numbers with the report's (m1). The submission's rigor claim is
self-referential - the machinery proves the numbers are generated - so
every remaining hand-typed claim must be checked with the same
severity.

---

## Potential Impact - weight 25% - **86/100** - meets gate

### Evidence for the score

- Every lead and adjunct maps to a concrete assay inside the MVA
  Society's four funded programs with explicit GO/NO-GO thresholds,
  cost tier and time-to-result (report lines 311-330;
  `testability.json`): the fibroblast aneuploidy panel is cheap (T1),
  decisive and carries an internal euploid control - the strongest
  possible impact artifact without running an experiment.
- A non-drug recommendation that is actionable today: mechanism-guided
  cancer surveillance per the AACR genomic-instability workshop
  (lines 284, 75) - the one line in the document that could change
  care now.
- The axis framing generalizes: same three axes apply to other BUB1B
  null+hypomorph genotypes and to CEP57/TRIP13 disease (config seeds
  already named).
- The rejected table (lines 288-305) is itself impact-relevant - it
  answers the questions families and clinicians will actually ask
  (growth hormone, HSCT, mebendazole) and answers them honestly with
  mixed-evidence framing.

### Strongest argument against

There is no MVA-specific drug-treatment study in existence - every
candidate is mechanistic extrapolation and the report says so. The
four-lead portfolio rests on a mouse senolytic result (BubR1
hypomorph), a correlational mTORC1-sarcopenia observation, an NAD+/SIRT2
axis never tested in MVA tissue, and a chloroquine screen in engineered
trisomic MEFs - respectively one, two and three model-systems away from
the child. Nothing proposed can be given to anyone today (correctly),
so "potential" is entirely contingent on unran experiments. The
portfolio also converges substantially on the same candidates other
teams found (landscape.md), so impact novelty is limited.

### Highest-impact improvement

Nothing the report can write changes the evidence distance - the
improvement is presentational: lead section 7 with the ONE decisive
experiment (fibroblast aneuploidy-rate panel) rather than the full
matrix, and say in one sentence what a positive result would unlock.
Right now the decisive path is findable but not foregrounded.

---

## Innovation - weight 25% - **85/100** - AT GATE 7

### Evidence for the score

- Per `landscape.md` (~30 repos, ~8 substantive T2 efforts): no
  competitor has a frozen retrospective recall@k benchmark, an
  approval-by-code gate, a citation-resolution+retraction gate, a
  pediatric-label filter, or a program-mapped testability matrix. These
  are real, demonstrated differentiators - not asserted ones.
- The mechanism-direction layer is genuinely novel among the field:
  it removes 37 mechanism-opposed approved drugs and *publishes their
  would-be ranks* (line 115) instead of hiding them - adversarial
  honesty nobody else shows.
- "Residual-allele rescue" as an axis for a null+hypomorph genotype is
  a mechanistically distinctive frame (report line 72).
- The rejected-candidates table turns the weakest part of every
  competitor's submission (unjustified exclusions) into auditable
  evidence.
- Reproducibility infrastructure: byte-exact offline replay of every
  API response; a generator that cannot emit an unverified number.

### Strongest argument against

The drug list itself is not novel: senolytics, mTOR inhibition, NAD+
and autophagy are exactly the convergence points landscape.md reports
across competitors. The engine's algorithmic core (target overlap +
STRING proximity + LINCS reversal) is conventional repurposing
machinery - the innovation is in the *rigor wrapper*, not the search
method. And the engine only independently surfaces 2 of the 4 leads
(dasatinib #43, everolimus #12); the other two were never collected,
making the portfolio largely a literature-curated artifact dressed in
engine clothing. A judge who scores "novel candidate identification"
rather than "novel verification pipeline" will see a conventional
shortlist.

### Highest-impact improvement

Say explicitly what the engine *proved* rather than what it found: it
independently corroborates mTOR (sirolimus #2, everolimus #12) and
dasatinib (#43) without being told the mechanism, and it demonstrates
why the field's default answer (top-ranked = cytotoxics) is unsafe -
that argument exists in the materials but is not made anywhere as a
claim.

---

## Scalability - weight 15% - **87/100** - meets gate

### Evidence for the score

- Gene-agnostic engine, one command, config-driven
  (`config/track2.yaml`, engine.md "How to run on another gene");
  nothing BUB1B-specific in `src/track2/`.
- The benchmark is the measured receipt: the same pipeline runs blind
  on 9 unrelated diseases and reports honest recall including the
  structural misses - the strongest possible scalability evidence for
  a hackathon.
- Offline replay: every external response recorded to fixtures; the
  full pipeline reruns with zero network; the citation gate is a
  drop-in tool usable by any team.
- Other MVA genes (CEP57, TRIP13, MAD1L1) are already seeded in the
  config.

### Strongest argument against

The ceiling is 0.56 recall@10 - the engine structurally misses drugs
acting outside the disease module (4 of 9 benchmark cases), so
"scalable" means "scalably finds module-adjacent drugs", which
underdelivers for diseases whose real repurposings act downstream. The
name-resolution tail is messy in ways a new-gene run will hit too:
252 unresolvable names, 7 salt duplicates, pediatric-flag false
negatives (dasatinib, metformin classes). And "reruns offline" means
replay of THIS run - a new gene still needs the full live API pass.
The benchmark is honest about all of this, but the honest number is
the honest number.

### Highest-impact improvement

None required to stay above gate; the credible ceiling-raiser is
widening the module (neighbour_limit or phenotype-driven seeds) and
re-running the benchmark to show recall improvement - engine.md
already names this lever.

---

## Weighted self-score

| Criterion | Weight | Score | Weighted |
|---|---|---|---|
| Scientific Rigor | 35% | 84 | 29.4 |
| Potential Impact | 25% | 86 | 21.5 |
| Innovation | 25% | 85 | 21.25 |
| Scalability | 15% | 87 | 13.05 |
| **Total** | | | **85.2** |

**Gate 7 status: 2 of 4 criteria below/at the 85 line** (Rigor 84,
Innovation 85). The fix list below clears the Rigor deficit in an
afternoon; Innovation is at threshold and depends on framing, not new
work.

---

## Prioritised fix list (what raises the score most per hour of work)

1. **M1** - s/"non-cytotoxic"/"mechanism-aligned"/ in report lines 211,
   279 and both `portfolio.json` rows. Removes the only false statement
   in the submission.
2. **M2** - re-source the everolimus 4.1y/growth/<6y-infection facts to
   `[repo:openFDA label 01f7b5fb]` (already recorded) and/or add the
   correct extension-study citation.
3. **m1** - print identical labeled recall pairs in abstract.md and the
   report ("0.44 frozen / 0.56 post-direction").
4. **m2+m3** - one funnel sentence that sums: add the 13 merged names
   and the salt-duplicate disclosure ("96 approved entities, 89
   distinct ingredients").
5. **m4** - "truth declared in config before the run" (not "committed").
6. **m6** - fix the mid-word truncated table cells.
7. **m5** - one phase-caveat clause in FAMILY_SUMMARY and the report's
   plain-language paragraph.
8. **m7** - "a large French survivor cohort" in mechanism.md.
9. **m8** - name the pediatric-flag false-negative pattern in
   engine.md limitations.
10. **N1-N4** - regenerate to refresh stale counters (22 uncovered,
    510 tests); fill niacin first-approval; fix L3/L4 lane-doc drift.
11. **Framing** - one sentence in section 4 making explicit what the
    engine proved (independent mTOR/dasatinib corroboration + the
    excluded-cytotoxic argument) and foregrounding the single decisive
    fibroblast experiment in section 7.

## Verdict on top-three placement

Against the field described in landscape.md this is the most defensible
submission by a wide margin: it is the only one with a measured engine
benchmark, a code-checked approval gate, a verified citation layer,
and a testability matrix on funded programs - exactly the four things
a methods-skeptical panel can verify rather than take on trust. Where
it is beatable is candidate novelty: the four leads are the same
molecules the strongest competitors also found, and a judge who
weights insight over rigor could rank texdata's KG work or a
mechanistically bolder portfolio ahead on the drug list. Honest call:
**top three, probably top two** - the floor is guaranteed by rigor no
competitor publicly matches; the ceiling depends entirely on whether
the two MAJOR factual errors are fixed before the Oct 23 submission,
because a package whose headline promise is "no number hand-typed"
cannot afford a printed claim the artifacts disprove.
