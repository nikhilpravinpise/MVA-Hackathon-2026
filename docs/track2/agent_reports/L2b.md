# Lane L2b - Mechanism-direction safety layer + PRISM overlay

Date: 2026-10-12 (post-freeze patch; the L2 engine itself is unchanged in
scoring, channels and weights - this lane ADDS a configurable direction
filter, a pediatric flag and a reported-only PRISM overlay).

## Files written / modified

| file | change |
|---|---|
| `src/track2/direction.py` | NEW - rule compiler + `classify()` (opposed/aligned/neutral) + `pediatric_flag()` |
| `src/track2/prism.py` | NEW - prism.json index (cached), name-normalised lookup, `annotate()` |
| `src/track2/engine.py` | collect per-edge `hit_types` (drug,gene interaction types), OT `action_types` + per-target `moa_target_actions`; direction classification + pediatric flag + PRISM annotate per candidate; ranking split into `candidates` + `excluded_mechanism_opposed` with `rank_before_direction`; top-level `direction` and `prism` summary blocks; pediatric_use clip 400 -> 800 chars (matches 800-char fixture trim) |
| `src/track2/benchmark.py` | `_match_excluded` -> stage `excluded_mechanism_opposed` for known drugs found only in the exclusion list; emits `v1_frozen` + `direction` blocks + per-case `n_excluded_mechanism_opposed` |
| `tools/run_track2.py` | summary line now prints aligned/neutral/excluded counts |
| `config/track2.yaml` | NEW `direction:` block (v2, 9 opposed + 6 aligned rules, reason + verified PMIDs each), NEW `prism:` block (weight 0.0), `benchmark.v1_frozen` block |
| `tests/test_track2_direction.py` | NEW - 29 network-free tests |
| `docs/track2/engine.md` | direction-layer + PRISM sections (date, rules, citations, semantics, MVA delta), benchmark before/after table, updated Limitations |
| `docs/track2/evidence/candidates.json` | regenerated (replay) |
| `docs/track2/evidence/benchmark.json` | regenerated (replay), `v1_frozen` preserved |

## What the layer does

`direction.rules` in config are data, not code.  Each rule matches on
(i) regex over `mechanism_of_action` + action_type strings (OT
`actionType`, ChEMBL `action_type`), (ii) regex over collected drug
names (catches cytotoxics whose MoA text is empty - cyclophosphamide,
epirubicin), (iii) `target_genes` against the drug's curated MoA targets
and module hits.  `require_inhibitory` makes a gene hit count only with
inhibitory evidence (per-edge DGIdb type or curated INHIBITOR action);
`activator_only` requires an activating edge.

**Why per-edge evidence matters**: dasatinib's AURKB link is a loose
untyped DGIdb edge - its curated mechanism targets are SRC/ABL kinases,
so it is NOT excluded and instead matches `aln_senolytic_class`.  The
spec example "module target AURKB + inhibitor action -> opposed" holds:
the rule needs inhibitory action on that edge.  Cantharidin (PPP2CA,
typed `inhibitor` - PP2A-B56 is BubR1's error-correction phosphatase)
and panobinostat (SIRT2, typed `inhibitor` - SIRT2i destabilises BubR1,
PMID 25672491) DO fire.  Opposed beats aligned when both fire.

## Key findings (replayed MVA run)

- **37 of 96 approved candidates excluded** as mechanism-opposed;
  59 remain (10 aligned, 49 neutral).  Pre-layer top-20 had **19 of 20**
  opposed drugs (only palbociclib survived).
- Rules fired: `opp_dna_damaging` 26, `opp_topoisomerase_poison` 19,
  `opp_antimetabolite_dna_synthesis` 8, `opp_antimitotic_tubulin` 3,
  `opp_pp2a_inhibitor` 1 (cantharidin), `opp_sirt2_inhibitor` 1
  (panobinostat); `opp_sac_kinase`/`opp_p53_axis_suppression`/
  `opp_growth_axis` 0 (no drug had inhibitory evidence on those edges -
  correct, not silent failure).
- Aligned hits: sirolimus, everolimus, temsirolimus, alpelisib (MTOR);
  dasatinib, venetoclax, imatinib, bosutinib (senolytic class); metformin
  x2 (AMPK activator edge).
- PARP inhibitors deliberately left neutral (no supporting citation).

### New top-20 approved candidates (post-direction)

| # | drug | axis | direction | pediatric_flag |
|---|---|---|---|---|
| 1 | palbociclib | B | neutral | none |
| 2 | sirolimus | B | aligned (mtorc1) | labeled_pediatric_indication |
| 3 | glycerin | B | neutral | none |
| 4 | methenamine | B | neutral | none |
| 5 | octocrylene | none | neutral | none |
| 6 | omacetaxine mepesuccinate | none | neutral | none |
| 7 | pentetic acid | B | neutral | labeled_pediatric_indication |
| 8 | phenylbutanoic acid | B | neutral | none |
| 9 | abemaciclib | B | neutral | none |
| 10 | gefitinib | A | neutral | none |
| 11 | clotrimazole | none | neutral | none |
| 12 | everolimus | B | aligned (mtorc1) | labeled_pediatric_indication |
| 13 | flutamide | B | neutral | none |
| 14 | tamoxifen | B | neutral | none |
| 15 | celecoxib | B | neutral | labeled_pediatric_indication |
| 16 | lapatinib | none | neutral | none |
| 17 | levothyroxine | B | neutral | labeled_pediatric_indication |
| 18 | erlotinib | none | neutral | none |
| 19 | dabrafenib | B | neutral | labeled_pediatric_indication |
| 20 | vemurafenib | B | neutral | none |

### Excluded list: 37 records; top 10 by would-be rank

| was # | drug | score | pediatric_flag | reasons |
|---|---|---|---|---|
| 1 | doxorubicin | 0.800 | pediatric_text_only | opp_dna_damaging, opp_topoisomerase_poison |
| 2 | epirubicin | 0.800 | none | opp_topoisomerase_poison |
| 3 | temozolomide | 0.800 | none | opp_dna_damaging |
| 4 | cyclophosphamide anhydrous | 0.658 | none | opp_dna_damaging |
| 5 | mitomycin | 0.658 | none | opp_dna_damaging |
| 6 | pixantrone | 0.658 | none | opp_dna_damaging, opp_topoisomerase_poison |
| 7 | cantharidin | 0.625 | labeled_pediatric_indication | opp_pp2a_inhibitor |
| 8 | daunorubicin | 0.625 | none | opp_dna_damaging, opp_topoisomerase_poison |
| 9 | daunorubicin hydrochloride | 0.625 | none | opp_dna_damaging, opp_topoisomerase_poison |
| 10 | doxorubicin hydrochloride | 0.625 | pediatric_text_only | opp_dna_damaging, opp_topoisomerase_poison |

Pediatric flag over all 96: 22 labeled_pediatric_indication,
4 pediatric_text_only, 70 none.

### PRISM overlay

`evidence.prism_aneuploidy` filled for **68 of 96 candidates**
(status `screened` with beta/q/n_lines), 28 `not_in_screen`.
Weight 0.0 - no FDR-significant launched drug exists in the screen.
Notable nulls now visible per-candidate: sirolimus beta +0.0024 (q 0.45),
dasatinib beta -0.0018 (q 0.63, trend selective but ns).

## Benchmark before/after (identical replay fixtures)

| | recall@1 | @5 | @10 | @25 |
|---|---|---|---|---|
| v1 frozen | 0.0 | 0.333 | 0.444 | 0.556 |
| post-direction | 0.0 | 0.333 | **0.556** | 0.556 |

The layer IMPROVED recall@10: glibenclamide went 11 -> 10 as an opposed
drug ahead of it was excluded.  No declared benchmark drug is opposed
(everolimus/sirolimus/alpelisib aligned; glibenclamide, ivacaftor,
migalastat neutral).  `v1_frozen` preserved in benchmark.json.

## Test command + result

```
C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe -m pytest tests/test_track2_units.py tests/test_track2_engine.py tests/test_track2_direction.py tests/test_make_track2_report.py -x -q
=> 58 passed in ~18 s
C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe -m pytest tests/ -q
=> 507 passed, 1 failed, 10 skipped
   1 failure = tests/test_freshness.py::test_paths_exist ->
   NameError "GITIGNORED_ROOTS is not defined" inside
   tools/audit_freshness.py (repo-infra bug, NOT this lane's file -
   flagged for the lead; test_csv_identity_and_oracle passed once the
   concurrent Track-1 lane generated its results CSV)
```

New tests cover: MoA/action_type/name/target matching incl. negatives
(`MTOR inhibitor` NOT opposed; `DNA topoisomerase II alpha inhibitor`
opposed), per-edge inhibitory requirements (dasatinib AURKB stays),
opposed>aligned precedence, pediatric flag (positive/negated/mixed/
text-only/empty), PRISM join incl. salts and `not_in_screen`, weight-0
assertion, replay determinism byte-identical modulo timestamps,
exclusion preserves records + `rank_before_direction`, benchmark known
drugs never opposed, `v1_frozen` preserved, recall not degraded.

## Citations

All ~33 PMIDs in the `direction:` block were re-resolved live via NCBI
efetch (titles + abstracts read) on 2026-10-12; each is already in
mechanism.json / rejected.json / a dossier file.  Examples verified:
PMID 25672491 "Selective Sirt2 inhibition..." (SirReal2 destabilises
BubR1); PMID 37931001 (hydroxyurea elevates mutation rates incl.
aneuploidy; rapamycin marginal); PMID 7739397 (benzimidazole
aneugenicity at in-vivo levels); PMID 23521863 (metformin blunts SASP
via NF-kB, NOT AMPK - the rule reason says this honestly).

## Open issues / limitations

- `opp_sac_kinase`, `opp_p53_axis_suppression`, `opp_growth_axis` fired 0
  times here - correct (no drug has inhibitory evidence on those edges),
  not silent failure; rules remain for other cases/future data.
- A genotoxic drug whose sources record no MoA, no action_type, no typed
  interaction AND no name-class match would stay neutral (e.g.
  `omacetaxine` - a translation-inhibitor cytotoxic - remains neutral;
  borderline call, documented).
- Residual non-oncology noise (glycerin, methenamine, pentetic acid,
  octocrylene) still ranks high on evidence density - not a direction
  error; L3 curation surface.  Palbociclib #1 is a cytostatic CDK4/6
  inhibitor - neutral by mechanism, not a recommendation.
- `metformin`'s openFDA hit is the ZITUVIMET combo label (pediatric
  "not established" -> flag none) though plain metformin is pediatric-
  labeled >=10y for T2D; label-name matching limitation, reported as-is.
- PARP inhibitors left neutral pending a citable genotoxic-in-MVA
  argument (recorded in config comment + engine.md).
- `pediatric_flag` is a coarse label hint, not a safety assessment.
