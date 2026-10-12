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
scored candidates.  Every stage's count lands in `funnel`.

## Scoring

Five normalized channels `[0,1]`, transparent weighted sum:

| Channel | Definition | Weight |
|---|---|---|
| `target_overlap` | |drug MoA targets ∩ M| / |targets| | 0.30 |
| `network_proximity` | Guney z mapped piecewise: z<=-2 -> 1, z>=0 -> 0, linear between | 0.25 |
| `signature_reversal` | best matching LINCS reverser `-log10(p)` / 20 | 0.20 |
| `interaction_evidence` | min(1, #module genes with DGIdb interaction / 2) | 0.15 |
| `literature` | min(1, DGIdb publication count / 3) | 0.10 |

A failed/absent channel contributes 0 with its weight kept in the
denominator - a drug is never inflated because a source was down.
Tiers: **T1** score>=0.45 and >=2 non-zero channels; **T2** score>=0.25;
else **T3**.  Every channel value is emitted under `channels` plus a
human-readable `rationale_keys` list.

**Axis assignment** (config target->axis map): A = residual-BubR1 rescue
(SAC/kinetochore module), B = senescence/damage response, C = aneuploid
vulnerability.  A drug gets the sorted set of axes of its
module-overlapping targets; `none` when the overlap hits only
axis-unannotated neighbours (e.g. TOP2A).

## Network proximity (Guney et al. 2016, PMID 26831545)

*"Network-based in silico drug efficacy screening"* - abstract verified.

For drug target set T and module M on graph G (STRING score>=700):

```
d_c(T, M) = (1/|T|) * sum_{t in T} min_{s in M} dist(t, s)
```

- `unreachable_distance` = 6 assigned when a target is outside the routing
  universe or disconnected (conservative bound).
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
is unreachable the channel degrades to 0 and `lincs.status` records it.

## Benchmark methodology (retrospective, decision-frozen)

`tools/run_track2.py --benchmark` runs the identical engine on 9
independent gene -> approved-repurposed-drug cases declared in
`config/track2.yaml` BEFORE the first run.  Each case seeds only the
disease gene (+ its STRING neighbours); the known drug is never seeded.
For each known drug we report `stage`: `ranked` (with rank), or
`collected_not_approved`, or `not_collected` (target outside the module).
recall@k = fraction of cases whose best-ranked declared drug is <= k.

Results (2026-10-12 run): **recall@1 0.0, @5 0.333, @10 0.444, @25 0.556**
(n=9).  Recovered: alpelisib#2 (PIK3CA), migalastat#2 (GLA), everolimus#3
+ sirolimus#4 (TSC2), ivacaftor#6 (CFTR), glibenclamide#11 (KCNJ11).
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

- **Oncology bias.**  Interaction and indication databases are densest for
  cancer; module neighbours in a checkpoint/cell-cycle disease pull
  cytotoxics and kinase inhibitors to the top.  This is why the top of the
  MVA list is oncology-heavy - expected, documented, and exactly what the
  axis labels are for (L3 curates, engine reports).
- **Approved != safe in children.**  The gate checks licensure only.
  Pediatric label text is extracted verbatim but not interpreted; dosing,
  contraindications and age floors are L3 dossier work.
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
- **Phasing unknown.**  The engine treats the genotype as a reduced-
  function SAC phenotype (null + likely hypomorph); it does not model
  allele-specific rescue and asserts nothing about cis/trans.
- **Not a rank of "best drugs"** - a rank of *evidence density* for
  module-targeted approved compounds.  Drugs acting downstream of the
  module (losartan-in-Marfan class) are structurally invisible here.
