# Track 2 compute note - L5 (pharmacogenomics + protein-LM variant effect)

Written 2026-10-12. Owner: lane L5 (`tools/t2_prism.py`, `tools/t2_esm.py`,
`tools/modal_track2.py`). All data public; no patient files are read or
uploaded (track2_plan.md section 5). The only patient-derived facts used
are the published ones: gene BUB1B, p.Leu737Ter + p.Asn1002Lys on MANE
ENST00000287598.11 / NM_001211.6.

## 1. PRISM repurposing x aneuploidy (`docs/track2/evidence/prism.json`)

**Question.** Across ~500 cancer cell lines screened in the PRISM
Repurposing secondary screen, which *marketed* drugs preferentially kill
highly-aneuploid cells (Axis C of the plan) or cells with low BUB1B
expression?

**Data (all resolved live; sha256 recorded in `prism.json.inputs` and in
`prism_raw/manifest.json`):**

| Input | Source | File |
|---|---|---|
| PRISM secondary-screen dose-response curve parameters (252 MB) | figshare, PRISM Repurposing 19Q4 (`depmap.org/repurposing`) | `secondary-screen-dose-response-curve-parameters.csv` (files/20237739) |
| PRISM cell-line info | same release | `secondary-screen-cell-line-info.csv` (files/20237769) |
| PRISM readme (column semantics, MTS010 recommendation) | same release | `secondary-screen-readme.txt` (files/20238123) |
| Cohen-Sharir Supp Table 1 - per-line aneuploidy scores, n=997 | Springer static-content for `10.1038/s41586-020-03114-6` | `41586_2020_3114_MOESM3_ESM.xlsx` |
| Cohen-Sharir Supp Table 2 - aneuploidy genetic dependencies | same | `..._MOESM4_ESM.xlsx` |
| Cohen-Sharir Supp Table 5 - aneuploidy chemical sensitivities (concordance reference) | same | `..._MOESM7_ESM.xlsx` |
| DepMap Public 19Q4 expression + gene CN | figshare article 11384241 v3 (`10.6084/m9.figshare.11384241`) | `CCLE_expression.csv` (files/20234346), `CCLE_gene_cn.csv` (files/20234367) - only the `BUB1B (701)` column of each is extracted |
| DepMap 19Q4 sample info (lineage cross-check) | same article | `sample_info.csv` (files/20274744) |

Raw downloads live outside git
(`%USERPROFILE%\.claude\jobs\5356bf8a\tmp\prism_raw`); the small derived
tables are committed under `tests/fixtures/track2/prism/derived/`
(aneuploidy scores 997 lines, BUB1B expr/CN 1706 lines, PRISM cell lines
588, Cohen-Sharir SuppTable5-PRISM 1448 drugs, SuppTable2 deps 327 rows;
counts verifiable in [repo:tests/fixtures/track2/prism/derived/]).

**Model.** Per `broad_id`, `AUC ~ feature + C(primary_tissue)`, OLS with
absorbed lineage fixed effects (Frisch-Waugh-Lovell; pure stdlib, tested
against hand-checkable synthetic data). Sensitivity measure = AUC from the
four-parameter fits (lower AUC = more killing). One row per
(broad_id, depmap_id): MTS010 preferred per the readme, else HTS002,
MTS006, MTS005. STR-passed lines only; >= 100 lines per regression
(default). BH q across tested compounds. beta < 0 = more killing in
feature-high lines
[repo:tools/t2_prism.py] [repo:docs/track2/evidence/prism.json].

*Aneuploidy*: beta < 0 = aneuploid-selective. *BUB1B expression*: beta >
0 = low-BUB1B-selective.

**Results (all regenerated into `prism.json`; nothing hand-typed).**

- 1,498 compounds tested (588 "Launched" broad_ids) - [repo:docs/track2/evidence/prism.json],
  ~457 lines median per regression after screen collapse.
- **No launched drug reaches FDR q < 0.05 for aneuploidy-selectivity** [repo:docs/track2/evidence/prism.json]
  (min launched q = 0.069). Top-of-list is hypothesis-generating only:
  ingenol-mebutate, lomefloxacin, lenalidomide, imatinib, dasatinib
  (beta -0.004 to -0.002 per arm-alteration unit, all q >= 0.2)
  [repo:docs/track2/evidence/prism.json].
- **Concordance check vs Cohen-Sharir's own PRISM analysis (Supp Table
  5): Spearman rho = +0.719, p = 2e-229, sign concordance 80%** across
  1,442 matched drugs - the pipeline reproduces their result on the same
  data. Sign convention verified directly: their effect_size is positive
  when aneuploid lines are *less* sensitive (nutlin-3: +0.154 theirs vs
  +0.124 our top-vs-bottom-quartile AUC gap)
  [repo:docs/track2/evidence/prism.json] (DOI:10.1038/s41586-020-03114-6).
- **SAC/mitotic drugs are mostly aneuploid-*resistant* here** (42/50
  matched show beta > 0): short-course pharmacological SAC inhibition is
  tolerated better by aneuploid lines - exactly the asymmetry
  Cohen-Sharir reported between drug exposure and genetic SAC depletion
  (BUB1B depletion is lethal to aneuploid cells: Supp Table 2
  Achilles-RNAi effect -0.137, q = 5.7e-4; DRIVE-RNAi -0.317,
  q = 1.1e-4; DOI:10.1038/s41586-020-03114-6). Implication for the
  submission: SAC-inhibiting drugs
  belong in the *considered-and-rejected* table - in this screen they do
  not preferentially kill aneuploid cells, and mechanistically they would
  further weaken an already-hypomorphic checkpoint
  [repo:docs/track2/evidence/prism.json].
- **Low-BUB1B-expression sensitivity** (beta > 0 = sensitive at low
  BUB1B): nothing genome-wide significant among launched drugs (min
  q = 0.216); MDM2 inhibitors (nutlin-3 +0.045, idasanutlin +0.037) and
  dasatinib (+0.037, q = 0.24) run in the thesis-consistent direction
  but are not significant. In the *opposite* direction, mitotic
  kinesin/PLK1 inhibitors (ispinesib q = 0.04, volasertib, rigosertib,
  BI-2536) kill *high*-BUB1B lines - consistent with BUB1B marking
  proliferative/mitotic demand rather than a vulnerability to exploit
  [repo:docs/track2/evidence/prism.json].
- **Not screened**: metformin, hydroxychloroquine, chloroquine,
  reversine are absent from the secondary-screen compound set; sirolimus/
  everolimus show no selective signal. Dossier lanes must not cite PRISM
  evidence for drugs absent from this set.

## 2. ESM-2 variant effect for p.Asn1002Lys (`docs/track2/evidence/esm.json`)

**Question.** Is the residual allele's missense (N1002K, in the BubR1
kinase domain) predicted damaging by a protein language model, and how
does it rank against (a) other BUB1B missense observed in the population
and (b) clinically classified missense?

**Inputs (fetched live 2026-10-12, recorded in `esm.json.inputs`):**
UniProt `O60566` (BUB1B_HUMAN, 1050 aa; verified identical to the
ENST00000287598.7/ENSP00000287598.7 MANE translation - pos 737 = L,
pos 1002 = N); ClinVar via E-utilities (both queries stored verbatim);
gnomAD r4 via the public GraphQL API.

**Method.** Masked-marginal LLR (Meier et al. 2021, bioRxiv
10.1101/2021.07.09.450648): mask the variant position in a <= 1022-aa
window (ESM-2 limit 1024 tokens incl. BOS/EOS), forward pass once per
position, `LLR = log P(mut) - log P(wt)`; lower = more damaging.
Variants sharing a window are batched in one forward. Local run:
`facebook/esm2_t30_150M_UR50D` on CPU; the Modal wrapper defaults to
`facebook/esm2_t33_650M_UR50D` on an L4.

**Calibration panel.** ClinVar B/LB missense on NM_001211.6 (n = 35);
ClinVar P/LP *missense* in BUB1B (n = 1: p.Gln467His - reported as a
point estimate, no AUC claimed; BUB1B pathogenicity is overwhelmingly
truncating, which is itself the MVA genotype rule); ClinVar P/LP
*nonsense* scored as loss-of-wildtype via the 'X' token (proxy panel,
n = 35 - ESM has no stop token, so this measures constraint at the
mutated residue, not stop-specific evidence); gnomAD common missense
AF >= 1e-4 (n = 27, benign-enriched) vs ultra-rare AC <= 2 (n = 840
scored after dedup, deleterious-enriched). Percentile background = all 1,273
gnomAD-observed BUB1B missense (17 rows carry non-MANE hgvsp numbering,
pos ~87-94 cluster: 16 explicitly dropped, one deduplicated against a
MANE-consistent row - all logged in `esm.json.dropped_variants`).

## 3. Modal app (`tools/modal_track2.py`, prepared - not run by L5)

App `mva-track2`, volume `mva-t2-cache` (HF cache + raw downloads +
`out/*.json`; public data only).

    MODAL_PROFILE=track2 modal run tools/modal_track2.py::esm_variant_effect \
        --model-name facebook/esm2_t33_650M_UR50D
    MODAL_PROFILE=track2 modal run tools/modal_track2.py::prism_aneuploidy
    modal volume get mva-t2-cache out/esm.json   docs/track2/evidence/esm.json
    modal volume get mva-t2-cache out/prism.json docs/track2/evidence/prism.json

Both functions also return their payload (stdout capture fallback).
`esm_variant_effect`: GPU L4, timeout 1200 s. `prism_aneuploidy`: CPU,
timeout 3600 s, 8 GB.

**Cost estimate vs the $30 credit** (Modal public per-second pricing,
approximate as of writing): L4 ~$2/hr -> ESM run < 10 min incl. 2.6 GB
weight download ~ $0.30; CPU function ~ $0.05/hr-equivalent -> PRISM job
< 30 min ~ $0.05; image builds + volume storage ~ cents. **Total <
$1/run; comfortably inside budget with the hard timeout as the cap.**

## 4. Runtimes observed (local)

| Step | Wall time | Note |
|---|---|---|
| raw downloads | ~3 min | ~1.2 GB total |
| `derive` (xlsx + 2-column scan of 969 MB CSVs) | ~2 min | openpyxl + csv |
| `analyze` (264 MB scan + 3 regressions) | ~4 min | stdlib only |
| ESM-2 150M, 1,319 variants, CPU batch 16 | ~48 min | GPU target: minutes; n = `scores` in [repo:docs/track2/evidence/esm.json] |

## 5. Limitations (for the report's honesty section)

- Cancer cell lines are not a child's tissues. PRISM aneuploidy is
  arm-level somatic copy-number load; MVA is mosaic whole-chromosome
  aneuploidy. Related, not identical.
- Association is not mechanism: beta confounds lineage, proliferation
  rate, ploidy and p53 status; lineage fixed effects absorb only
  tissue-of-origin.
- Nothing here says any drug *helps* this child; the analysis nominates
  drugs for the mechanistically-motivated test panels (fibroblast
  aneuploidy-rate readout), and equally rules direction in (e.g. SAC
  inhibitors look aneuploid-resistant, not selective, in this screen).
- "Launched" is the Broad Repurposing Hub annotation shipped with PRISM
  19Q4 (marketed somewhere, some indication); approval status for the
  report is re-verified per drug by the engine lane against ChEMBL
  max_phase / DrugCentral / openFDA - never from this file alone.
- ESM-2 LLR is a self-supervised compatibility score; it has
  documented-but-modest clinical calibration, does not model dominance
  or mechanism, and cannot score nonsense (the 'X' proxy panel measures
  constraint only).
- ClinVar has exactly one classified pathogenic BUB1B *missense*
  (Q467H): a missense-only AUC is not computable on this gene, so
  calibration relies on the nonsense-proxy and gnomAD frequency-tier
  contrasts, all labelled as such.
