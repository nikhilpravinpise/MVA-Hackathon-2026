---
title: Repurposing engine
nav_order: 4
parent: Track 2
---
# Track 2 repurposing engine (lane L2)

A deterministic, gene-agnostic pipeline that maps a disease mechanism plus
its network context to a ranked list of **already-approved** drug
candidates, with every evidence contribution disclosed.  The engine is the
scalability receipt for Track 2: the same code ranks the MVA case and runs
blind on retrospective benchmark cases.

**This engine produces research hypotheses, not medical advice.**
Approved means licensed somewhere for some indication; it does NOT mean
safe, dosed, or appropriate for a child - see *Limitations*.

## Architecture

```
 config/track2.yaml (frozen: seeds, weights, axes, benchmark truth)
        |
        v
 disease gene + seed genes
        |  STRING 12.5 (score>=700, top-60)          --> disease module M
        |  + partners of every module gene (cap)     --> routing universe U
        |  STRING network edges within U             --> graph G
        v
 candidate drugs for every g in M
        |  Open Targets GraphQL  target.drugAndClinicalCandidates
        |  DGIdb v5 GraphQL      gene.interactions (sources, pmids, types)
        |  per-gene cap 50, code-name and weak-name filters
        v
 name -> ChEMBL id (conceptId | MyChem.info synonyms)
        v
 APPROVAL GATE  =  ChEMBL max_phase == 4 AND not withdrawn
        |          (batch molecule lookup; EMA-only flagged)
        +-- openFDA label      -> fda flag, pediatric_use, boxed_warning
        +-- DrugCentral/MyChem -> approval agencies (FDA/EMA/PMDA), id
        +-- OT drug record     -> MoA targets, warnings, indication count
        v
 evidence channels
        |  target_overlap | network_proximity (Guney 2016 z, seed fixed)
        |  signature_reversal (SigCom LINCS ranktwosided)
        |  interaction_evidence | literature
        v
 score = SUM(w_i * c_i)  ->  tier T1/T2/T3 + axis A/B/C
        |
        v
 DIRECTION LAYER (added post-freeze 2026-10-12, lane L2b)
        |  rules classify each candidate opposed | aligned | neutral
        |  opposed -> excluded_mechanism_opposed (kept w/ would-be rank)
        |  aligned/neutral -> ranked list (score unchanged, re-ranked)
        |  + pediatric_flag from openFDA pediatric_use text
        |  + PRISM aneuploidy overlay (reported channel, weight 0)
        v
 docs/track2/evidence/candidates.json   (schema t2.candidates/1)
 docs/track2/evidence/benchmark.json    (schema t2.benchmark/1)
```

All HTTP goes through one caching layer (`src/track2/httpcache.py`):
`live` fetches only; `record` fetches and writes every raw response to a
cache dir keyed by sha256(method+url+body); `replay` serves identical
requests offline, byte-for-byte.  Tests run in replay mode - zero network.

## Sources (all pulled live 2026-10-12)

| Source | Endpoint / version | Used for |
|---|---|---|
| Open Targets Platform | `api.platform.opentargets.org` GraphQL (schema introspected live; `drugAndClinicalCandidates`, `maximumClinicalStage`) | target->drug rows, MoA targets, warnings, indications |
| ChEMBL | REST `ChEMBL_37` (release 2026-05-01) | `max_phase`, `withdrawn_flag`, `first_approval`, `black_box_warning`, cross-references, mechanism text |
| DGIdb | v5 GraphQL `dgidb.org/api/graphql` | drug-gene interactions with sources/pmids/types |
| STRING | `string-db.org` **12.5**, `required_score>=700` | module build, routing universe, proximity edges |
| openFDA | `api.fda.gov/drug/label.json` | FDA label presence, `pediatric_use`, `boxed_warning`, `set_id` |
| DrugCentral | via `mychem.info/v1` (BioThings) | approval agencies + drugcentral id (direct drugcentral.org endpoints 404 - documented fallback) |
| SigCom LINCS | `maayanlab.cloud/sigcom-lincs` metadata-api + data-api `/enrich/ranktwosided`, library `l1000_cp` | two-sided signature reversal of the disease proxy signature |

Verified infrastructure citations (abstracts read):
Open Targets PMID 36399499 (2023) *"The next-generation Open Targets
Platform: reimagined, redesigned, rebuilt"*; ChEMBL PMID 37933841 (2024);
DGIdb PMID 33237278 (2021); STRING PMID 39558183 (2025); openFDA
PMID 26644398 (2016); SigCom LINCS PMID 35524556 (2022); MyChem/BioThings
PMID 27154141 (2016).

## Approval criteria

```
approved  <=>  ChEMBL molecule.max_phase == 4  AND  withdrawn_flag is false
```

Cross-checks are recorded as evidence, never as the gate itself:
`openfda` label hit -> `fda: true`; DrugCentral approval rows -> agency set
(FDA/EMA/PMDA); a molecule with EMA/PMDA only gets `ema_only: true` (kept,
flagged).  No approval is ever inferred from memory or names.

## Candidate-space funnel (recorded per run)

module genes -> OT clinical rows + DGIdb interactions -> per-gene cap 50
(OT-approved first, then DGIdb source count) -> code-name skip
(`CC-115`, `AZD-8055`...) -> weak-name skip (single source, no type, no
pmid) -> MyChem name resolution -> global cap 800 -> approval gate ->
scored candidates.  Every stage's count lands in `funnel`, and the
arithmetic closes explicitly:

```
collected - dropped_over_cap
    == gated_in + gated_out_no_chembl + gated_out_phase
     + gated_out_withdrawn + gated_out_unresolved + merged
```

`merged` (added 2026-10-13, lane L11) counts names whose MyChem lookup
resolved to a ChEMBL id a *different* candidate already held - the name
is union-merged into that candidate (its name set, module hits, DGIdb
sources/types) rather than scoring twice.  13 names merged this way in
the MVA run; without the counter the funnel sums left a silent gap.

## Scoring

Five normalized channels `[0,1]`, transparent weighted sum:

| Channel | Definition | Weight |
|---|---|---|
| `target_overlap` | |drug MoA targets ∩ M| / |targets| | 0.30 [repo:config/track2.yaml] |
| `network_proximity` | Guney z mapped piecewise: z<=-2 -> 1, z>=0 -> 0, linear between | 0.25 [repo:config/track2.yaml] |
| `signature_reversal` | best matching LINCS reverser `-log10(p)` / 20 | 0.20 [repo:config/track2.yaml] |
| `interaction_evidence` | min(1, #module genes with DGIdb interaction / 2) | 0.15 [repo:config/track2.yaml] |
| `literature` | min(1, DGIdb publication count / 3) | 0.10 [repo:config/track2.yaml] |

A failed/absent channel contributes 0 with its weight kept in the
denominator - a drug is never inflated because a source was down.
Tiers: **T1** score>=0.45 and >=2 non-zero channels; **T2** score>=0.25;
else **T3** [repo:config/track2.yaml].  Every channel value is emitted
under `channels` plus a human-readable `rationale_keys` list.

**Axis assignment** (config target->axis map,
[repo:config/track2.yaml]): A = residual-BubR1 rescue
(SAC/kinetochore module), B = senescence/damage response, C = aneuploid
vulnerability.  A drug gets the sorted set of axes of its
module-overlapping targets; `none` when the overlap hits only
axis-unannotated neighbours (e.g. TOP2A).  The axis is a *hypothesis
bucket*, not evidence of benefit - it says which arm of the strategy a
drug's target overlap nominates it for, nothing more (see Limitations).

## Mechanism-direction safety layer (added 2026-10-12, AFTER the L2 freeze)

**This section documents a post-freeze patch** (lane L2b, same day).  The
frozen v1 engine scored *evidence density only*; on the MVA case it ranked
doxorubicin, epirubicin, temozolomide and other genotoxic/aneugenic
agents at the top of the table - evidence-dense, and mechanistically the
exact wrong direction for a spindle-checkpoint-deficient child
(`evidence/mechanism.json` contraindications; `evidence/rejected.json`).

`src/track2/direction.py` + the versioned `direction:` block in
`config/track2.yaml` classify every approved candidate
([repo:src/track2/direction.py], [repo:config/track2.yaml]):

| direction | meaning | rank effect |
|---|---|---|
| `opposed` | at least one opposed rule fired | removed from `candidates` into `excluded_mechanism_opposed`, keeping its would-be rank, score and reasons [repo:src/track2/direction.py] |
| `aligned` | no opposed rule; >=1 aligned rule | stays ranked |
| `neutral` | no rule fired | stays ranked |

Every candidate also gets `direction_reasons` (fired rule ids - a drug
matching both classes shows the conflict; opposed always wins) and
`rank_before_direction`.  Scores, channels, tiers are untouched: the
layer filters direction, it does not re-weight evidence.

### Rule families (config-declared, citations resolved live + abstracts read)

Opposed (9 rules): `opp_topoisomerase_poison` (TOP2A/TOP2B/TOP1 or MoA
"topoisomerase" - PMID 15475955, 20516114, 33505028);
`opp_dna_damaging` (alkylating/cross-linking/intercalating, ChEMBL
action_type `CROSS-LINKING AGENT`, name classes incl. phosphamides -
PMID 15475955, 20516114, 39169218);
`opp_antimetabolite_dna_synthesis` (TYMS/DHFR/RRM1/RRM2, hydroxyurea and
nucleoside-analogue names - PMID 37931001 showed hydroxyurea elevates
mutation rates *including aneuploidy*; PMID 15475955);
`opp_antimitotic_tubulin` (tubulin/microtubule/spindle MoA, TUB* genes,
taxane/vinca/benzimidazole names - PMID 7739397 showed centromere-positive
micronuclei from benzimidazoles at in-vivo plasma levels; 33505028;
20516114); `opp_sac_kinase` (TTK/AURKA-C/PLK1/KIF18A/KIF11/CDK1/BUB1,
inhibitory edge required - PMID 33505028, 33505027, 20516114);
`opp_pp2a_inhibitor` (PPP2CA/B - PP2A-B56 is the BubR1 error-correction
phosphatase - PMID 23079597, 23345399, 33207204);
`opp_sirt2_inhibitor` (SIRT2 inhibitors destabilise BubR1 protein -
PMID 25672491, 24825348, 38009412); `opp_p53_axis_suppression`
(MDM2/MDM4/p53 inhibitors - PMID 20123995, 23602569);
`opp_growth_axis` (GH/IGF-1 agonists - precautionary; PMID 16822820,
32738133, 30500870).

Aligned (6 rules): `aln_mtorc1_inhibition` (PMID 26147250, 26280535,
31738183 - BubR1-mutant sarcopenia tracks mTORC1 hyperactivity - with the
honest caveat 37931001 on record); `aln_senolytic_class` (SRC/ABL +
BCL-2-family inhibitors - PMID 22048312, 25754370, 31542391, 18516091);
`aln_ampk_energy_stress` (PRKAA activator edges / metformin class -
PMID 21315436, 23521863, 18516091); `aln_nad_sirt2_axis` (NAD+/niacin -
PMID 24825348, 23242215, 38009412, 41436848);
`aln_autophagy_lysosomal` (PMID 21315436, 23461901, 39169218);
`aln_tetraploid_elimination` (aspirin class - PMID 24516128, 32534647).

### Matching semantics (why dasatinib is not excluded)

Rules match on MoA text **and** on per-edge target evidence.  Target
rules with `require_inhibitory` fire only when the (drug, gene) edge
carries inhibitory evidence - a curated Open Targets MoA row with
INHIBITOR action_type, or a DGIdb interaction typed
inhibitor/antagonist.  Dasatinib's AURKB link is a loose DGIdb edge with
no type; its *curated* mechanism targets are SRC-family/ABL kinases, so
it stays and matches `aln_senolytic_class`.  Cantharidin (PPP2CA,
typed `inhibitor`) and panobinostat (SIRT2, typed `inhibitor`) do fire.

**PARP inhibitors are intentionally NOT opposed** - no citation in the
evidence files supports a genotoxic-in-MVA claim, so they remain ranked
as neutral (documented rather than asserted).

### What it changed on the MVA run (2026-10-12, replayed)

Pre-freeze top-20 was: doxorubicin, epirubicin, temozolomide,
cyclophosphamide, mitomycin, pixantrone, cantharidin, daunorubicin,
daunorubicin HCl, doxorubicin HCl, etoposide phosphate, idarubicin,
idarubicin HCl, mitoxantrone, mitoxantrone HCl, podofilox, valrubicin,
palbociclib, irinotecan, fluorouracil - **19 of 20 mechanism-opposed**
(only palbociclib survived the filter)
[repo:docs/track2/evidence/candidates.json].

Post-layer: **37 of 96 approved candidates excluded** (all cytotoxic
genotoxins + cantharidin + panobinostat); 59 ranked (10 aligned, 49
neutral) [repo:docs/track2/evidence/candidates.json].  New top-10: palbociclib, **sirolimus** (aligned,
pediatric-labeled), glycerin, methenamine, octocrylene, omacetaxine,
pentetic acid, phenylbutanoic acid, abemaciclib, gefitinib.  The
residual non-oncology noise (excipients/chelators ranking by module
proximity) is a scoring limitation, not a direction error - documented
under Limitations; it is exactly the curation surface L3 works on.

### Pediatric flag (hardened 2026-10-13, lane L11)

`pediatric_flag` derives from the matched openFDA label.  Two
independent bugs were found in v1 ([repo:src/track2/direction.py],
[repo:src/track2/sources.py]):

- **Wrong section read.**  v1 scanned only the `pediatric_use` (8.4)
  field; pediatric age floors often live in INDICATIONS AND USAGE or
  DOSAGE AND ADMINISTRATION instead - dasatinib's "pediatric patients 1
  year of age and older" sits in the indication bullets (verbatim
  strings in [repo:tests/test_track2_direction.py]), and its candidate
  name `dasatinib anhydrous` also never resolved a label at all.
- **Wrong label selected.**  A `limit=1` generic-name query returns
  whatever openFDA happens to rank first - for metformin that was
  ZITUVIMET (sitagliptin/metformin), a combination label whose 8.4 says
  "have not been established" for the COMBINATION.  The same bug also
  produced a false POSITIVE: methylprednisolone matched a 6-ingredient
  procedure-kit label and inherited bupivacaine's pediatric approval
  sentence (and its boxed warning).

Label resolution now retries trailing salt/hydrate/ester name variants
(`dasatinib anhydrous` -> `dasatinib`), queries the ChEMBL `pref_name`
first so a union-merged name cannot attach the wrong label, and when
the first hit is a combination product issues one extra `limit=5`
search preferring the first single-ingredient label covering the drug;
a combination label is kept (and flagged `combination_label: true`)
only when no single-ingredient label is among the top hits.  The match
path is disclosed verbatim per candidate in `approval.openfda_match`.

The classifier then scans all three sections
([repo:src/track2/direction.py], real-label test corpus in
[repo:tests/test_track2_direction.py]):
`labeled_pediatric_indication` when a sentence asserts
established/indicated/approved for a pediatric population, or - in
INDICATIONS/DOSAGE text only, where an age or weight bound is an
indication bound - names an affirmative pediatric threshold ("1 year of
age and older", "pediatric patients >= 31 kg").  Age ranges inside 8.4
are study populations, not indications ("25 pediatric patients, range
3-20 years"), and adult age floors ("in adults 75 years or older")
never count.  The winning sentence is quoted verbatim in
`pediatric_flag_evidence` `{section, text}`, clipped on a word
boundary.  It is a coarse label-derived flag, not a pediatric-safety
assessment.

When no positive sentence is found the lower tiers say *what the
checked text actually contains* (lane L15, redteam2 r4 - `none` must
never assert a denial the data does not carry)
[repo:src/track2/direction.py]:

- `none` - a formal denial exists: some pediatric-population sentence
  matches "not established"/"not recommended"/"do not use".  The label
  considered pediatric use and declined it.
- `pediatric_text_only` - pediatric text exists with no positive and no
  denial: descriptive use (cyclosporine's transplant labels - "patients
  as young as 6 months of age have received cyclosporine" - flag
  `pediatric_text_only`, set_id 5e5926a7
  [repo:openFDA label 5e5926a7]), risk statements, "ask a
  doctor" directions, cross-reference stubs.
- `unknown` - nothing examined bears on pediatric populations at all:
  no label hit (11 MVA candidates, e.g. omacetaxine mepesuccinate), or
  a label whose fields are silent on pediatrics (glycerin, flutamide).
  Pre-L15 these all printed `none`, which asserted a negative the data
  did not contain.

**Pediatric deep scan** (lane L15): a `limit=1` first hit can be an
OTC label silent on pediatrics (acetaminophen: openFDA returns 3,300+
labels and the OTC crowd outranks the pediatric-positive injection
labels) or a route-specific product shadowing the canonical drug
(cyclosporine's Vevye *ophthalmic* label denies <18 use while the
systemic transplant labels document it).  Whenever the picked label is
not already pediatric-positive the resolver issues one extra
`(generic OR substance) AND _exists_:pediatric_use limit=25` query and
prefers the covering single-ingredient label with the most
pediatric-informative text (positive > descriptive > negated >
silent), unqualified generic names before route-qualified ones
[repo:src/track2/sources.py].  The re-picked label is disclosed by
`approval.openfda_match` = "..._exists_:pediatric_use scan;
pediatric-bearing single-ingredient label preferred".  On the recorded
corpus this recovers acetaminophen's `labeled_pediatric_indication`
(injection label 0f67c1bd, ">=2 years") and cyclosporine's transplant
text; drugs whose deeper labels are all negated keep their first label
only when a deeper label would not improve the flag.

**Active matching is token-exact** (lane L15, redteam2 n4): a label's
active token set minus salt/form words must equal the queried base's.
The old bidirectional substring test accepted "SIROLIMUS" inside
"TEMSIROLIMUS" and would have attached "INSULIN" labels to "insulin
glargine" - wrong molecules.

Residual limits: the scan is bound to the first 25
pediatric_use-bearing hits per drug (a label whose positive statement
lives only in INDICATIONS/DOSAGE while its 8.4 field is absent cannot
surface this way, and a negated first-hit can still shadow a positive
label beyond rank 25); openFDA hit ordering is not clinically ranked;
and `pediatric_flag`/`pediatric_flag_evidence`/`pediatric_labeling`
always describe the *picked* label - check `approval.openfda_match`
and `approval.combination_label` to see which one that was
[repo:src/track2/sources.py].

## PRISM aneuploidy overlay (added 2026-10-12, lane L2b)

`evidence.prism_aneuploidy` per candidate is filled from
`evidence/prism.json` (lane L5;
[repo:docs/track2/evidence/prism.json]): PRISM Repurposing 19Q4 pooled
screen, 1498 compounds x ~500 cell lines; for each compound, OLS
regression of
drug AUC on a per-line aneuploidy score with lineage fixed effects.
beta < 0 = more-aneuploid lines are more sensitive; `q` = BH FDR over the
screen; `n_lines` = lines used.  Candidates absent from the screen are
marked `not_in_screen` (never a fake zero); a missing file degrades to
`unavailable`.

**Weight is exactly 0** (`prism.weight`): the screen found no
FDR-significant launched drug, so it must not drive ranking.  It stays
visible because a checked-and-null channel is evidence: e.g. sirolimus
beta +0.002 (q 0.45, n=422 lines) - aneuploidy did NOT predict
sensitivity to our top aligned hit; dasatinib beta -0.0018 (q 0.63,
n=458) trends selective but non-significant
[repo:docs/track2/evidence/prism.json].  Caveats: cell-line
aneuploidy is cancer-genome aneuploidy, not constitutional mosaic
aneuploidy; AUC associations at n~450 lines are noisy for weak effects.

## Network proximity (Guney et al. 2016, PMID 26831545)

*"Network-based in silico drug efficacy screening"* - abstract verified.

For drug target set T and module M on graph G (STRING score>=700):

```
d_c(T, M) = (1/|T|) * sum_{t in T} min_{s in M} dist(t, s)
```

- `unreachable_distance` = 6 assigned when a target is outside the routing
  universe or disconnected (conservative bound;
  [repo:config/track2.yaml]).
- z-score vs `n_random=200` degree-matched random target sets, `seed
  20261012` fixed (log2 degree bins; `random.Random` - fully
  deterministic).
- Routing universe = M + first neighbours of every module gene
  (limit 40/gene, cap 450 nodes) - a documented approximation of
  full-STRING distances that keeps fixtures small; shortcuts through
  unqueried nodes are missed, so distances are *upper bounds*.
- Implementation: one multi-source BFS from M precomputes all distances;
  random sets reuse the table.

## LINCS signature reversal

Disease-proxy signature declared in config (assumption, not data):
aneuploidy-driven senescence/SASP program UP (`CDKN1A CDKN2A TP53
SERPINE1 IL6 GLB1`), weakened mitotic/checkpoint module DOWN (`BUB1B BUB1
CDC20 MAD2L1 TTK AURKB KNL1`).  Resolved to SigCom entities, queried via
`/enrich/ranktwosided` on `l1000_cp`; reversers' perturbagens matched to
candidates by INN (alias map for rapamycin->sirolimus etc.).  If the API
is unreachable the channel degrades to 0 and `lincs.status` records it
([repo:config/track2.yaml], [repo:src/track2/sources.py]).

## Benchmark methodology (retrospective, decision-frozen)

`tools/run_track2.py --benchmark` runs the identical engine on 9
independent gene -> approved-repurposed-drug cases declared in
`config/track2.yaml` BEFORE the first run.  Each case seeds only the
disease gene (+ its STRING neighbours); the known drug is never seeded.
For each known drug we report `stage`: `ranked` (with rank), or
`collected_not_approved`, or `not_collected` (target outside the module).
recall@k = fraction of cases whose best-ranked declared drug is <= k.

Results:

| run | recall@1 | recall@5 | recall@10 | recall@25 |
|---|---|---|---|---|
| v1 frozen (pre-direction, 2026-10-12) - `v1_frozen` in benchmark.json | 0.0 | 0.333 | 0.444 | 0.556 |
| post-direction layer (same replay) | 0.0 | 0.333 | **0.556** | 0.556 |

The safety layer did not hurt recall - it **improved @10**: glibenclamide
moved 11 -> 10 because an opposed drug ranked above it was excluded, and
no declared benchmark drug is mechanism-opposed (everolimus, sirolimus
and alpelisib are `aligned`; glibenclamide, ivacaftor, migalastat are
`neutral`).  Known drugs found in the exclusion list would appear with
stage `excluded_mechanism_opposed` (still `found: false`); none did.

v1 recovered: alpelisib#2 (PIK3CA), migalastat#2 (GLA), everolimus#3
+ sirolimus#4 (TSC2), ivacaftor#6 (CFTR), glibenclamide#10 (KCNJ11).
Missed: losartan (FBN1), fenfluramine (SCN1A), palovarotene (ACVR1),
acetazolamide (CACNA1A) - all `not_collected`: their targets (AGTR1,
5-HT receptors, RARG, carbonic anhydrases) are not STRING neighbours of
the disease gene.  Structural lesson the engine reports honestly: it
finds drugs that *hit the module*; downstream-acting drugs invisible to
target-overlap harvesting are systematically missed.

## How to run on another gene

```
# one command: same engine, disease gene TANGO6
python tools/run_track2.py --benchmark          # frozen retrospective suite
python tools/run_track2.py                       # the MVA case (default)
# another gene/disease: edit config case+seed_genes (all params documented),
# or call engine.run_case with a case dict {disease_gene, seed_genes:[...]}
```

Makefile-ready commands for the lead:

```
track2-candidates: ; $(PY) tools/run_track2.py --mode live --out docs/track2/evidence/candidates.json
track2-benchmark:  ; $(PY) tools/run_track2.py --benchmark --mode live --out docs/track2/evidence/benchmark.json
track2-record:     ; $(PY) tools/run_track2.py --mode record --cache-dir tests/fixtures/track2/engine/mva
track2-test:       ; $(PY) -m pytest tests/test_track2_units.py tests/test_track2_engine.py -q
track2-trim:       ; $(PY) tools/run_track2.py --trim-cache tests/fixtures/track2/engine/mva && $(PY) tools/run_track2.py --trim-cache tests/fixtures/track2/engine/benchmark
```

## Limitations (read before using the output)

- **Oncology bias - mitigated, not solved.**  Interaction and indication
  databases are densest for cancer; module neighbours in a checkpoint/
  cell-cycle disease pull cytotoxics and kinase inhibitors to the top.
  The direction layer removes the *wrong-direction* share (genotoxic/
  aneugenic agents [repo:src/track2/direction.py]) but cannot judge
  remaining noise: palbociclib,
  glycerin, methenamine, pentetic acid etc. are neutral (not opposed)
  and stay evidence-dense at the top.  Non-genotoxic oncology agents
  (CDK4/6, EGFR, BRAF inhibitors) remain by design - the list is a
  curation surface for L3, not a recommendation.
- **Approved != safe in children.**  The gate checks licensure only.
  `pediatric_flag` is a coarse label-derived hint (labeled indication /
  text-only / none / unknown), not a pediatric-safety assessment;
  dosing, contraindications and age floors are L3 dossier work.  The
  flag is only as good as the label openFDA happens to serve: v1 missed
  the pediatric indication entirely for dasatinib (name variant never
  resolved), read a combination-product label for metformin, and a
  `limit=1` first hit still landed on pediatric-silent OTC labels
  (acetaminophen) or route-specific products shadowing the canonical
  drug (cyclosporine) - all fixed 2026-10-13 (see Pediatric flag): one
  `_exists_:pediatric_use` deep scan now recovers the best
  pediatric-bearing single-ingredient label within 25 hits, and
  silent labels read `unknown` rather than `none`.  Residual: a
  pediatric statement outside `pediatric_use` on a label without an
  8.4 field, or a positive label beyond hit 25, still escapes; the
  flag remains a label-presence check, not the drug's pediatric
  status.
- **Axis labels are a config hypothesis map, not evidence of benefit.**
  A candidate's axis comes solely from `config/track2.yaml`'s
  target->axis table.  Gefitinib sits on axis C because EGFR is a
  module neighbour tagged to that axis - nothing in the axis label says
  gefitinib benefits a BUB1B-hypomorph child; that question belongs to
  the direction layer and the dossier lanes.
- **`collected` names can merge onto another candidate's ChEMBL id.**
  13 of 482 collected names in the MVA run resolved to a ChEMBL id a
  different candidate already held; they union-merge into it and are
  counted explicitly in `funnel.merged` so
  `collected - dropped_over_cap = gate outcomes + merged` closes
  [repo:docs/track2/evidence/candidates.json].
- **The approved count double-counts salt/ester forms.**  The 96
  approved records of the MVA run are 89 distinct actives: 7 records are
  salt/ester/prodrug forms of an active already counted (metformin
  hydrochloride, doxorubicin hydrochloride, daunorubicin
  hydrochloride, etoposide phosphate, idarubicin hydrochloride,
  mitoxantrone hydrochloride, dexrazoxane hydrochloride).  They are
  distinct ChEMBL molecules, so the gate correctly treats each as
  separately approved [repo:src/track2/engine.py]; portfolio reading
  should group them.
- **Direction rules are mechanism-generic, not verdicts.**  An `opposed`
  label means "this mechanism class pushes the documented disease
  mechanism the wrong way given the cited evidence" - it is not a claim
  that the drug is always harmful in any disease, and `aligned` is not
  a claim of benefit.  Rules fire on recorded evidence (MoA text,
  action types, typed interactions); drugs with no recorded mechanism
  can only be caught by name-class patterns, so a genotoxic drug whose
  sources are silent on both may slip through as neutral.
- **PRISM is reported, not scored** (weight 0): the screen had no
  FDR-significant launched hit; cell-line aneuploidy != constitutional
  mosaic aneuploidy.
- **Proximity assumptions.**  STRING combines evidence types; a
  score>=700 edge is not necessarily a physical interaction.  The routing
  universe is truncated (cap 450) so distances are upper bounds;
  degree-matched resampling controls for hubs but not for module-internal
  clustering density.
- **Candidate-space bounds.**  per-gene caps, code-name and weak-name
  skips are disclosed heuristics; counts are in `funnel` and the full
  pre-gate name list in `collected_names`.
- **LINCS signature is a declared proxy.**  No MVA transcriptome exists;
  the up/down gene sets are a mechanism-based assumption.  L1000 measures
  acute cancer-cell-line responses, not patient tissue; reversal hits are
  corroborating evidence, never standalone justification.
- **Missing-source statuses are preserved** (`lincs.status`,
  `provenance`, per-drug `evidence` lists) instead of silently scoring.
- **Evidence heterogeneity.**  DGIdb sources range from curated ChEMBL to
  text-mined mentions; `interaction_evidence`/`literature` channels cap
  their contribution accordingly.
- **Phasing unknown** [repo:config/track2.yaml] - the engine treats the genotype as a reduced-function SAC phenotype (null + likely hypomorph per `case.variants[].allele_role`); it does not model allele-specific rescue and asserts nothing about cis/trans.
- **Not a rank of "best drugs"** - a rank of *evidence density* for
  module-targeted approved compounds.  Drugs acting downstream of the
  module (losartan-in-Marfan class) are structurally invisible here.
