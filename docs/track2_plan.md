# Track 2 plan - Drug Repurposing (panel-judged)

Written 2026-10-12. Source of truth for Track 2. Track 1 is closed
(leaderboard row 139, 100.0 / 1.000, report uploaded). Everything here is
verified against the vendored Space source (`hackathon-app/tabs/submit_track2.py`,
`tabs/rules.py`, `tabs/about.py`, `tabs/faq.py`) and the methods form
(`hackathon-app/static/templates/methods_description_form.xlsx`, sharedStrings
13-20, 22, 23).

## 0. Hard constraints

| Constraint | Source | Consequence |
|---|---|---|
| Submissions close **2026-10-24 23:59 UTC** | `about.py` timeline | 12 days from today |
| Max 3 submissions, **only the latest is reviewed** | `submit_track2.py:22-24`, FAQ | Insurance v1 on **Oct 20**, final on **Oct 23** (one slot kept spare for a deadline-day fix). Supersedes plan.md Phase 7 "submit once, last": a Space outage on deadline day is the bigger risk |
| Required fields: GitHub URL (`https://github.com/` prefix), **pitch video URL** (hard reject if empty), report `.pdf` or `.md` | `submit_track2.py:85-101` | Video is a hard gate, not a nice-to-have |
| Report filename carries the username | `INSTRUCTIONS_MD` | `nikhilpise_track2_report.md` (+ `.pdf`) |
| Repo must be public after close | `INSTRUCTIONS_MD`, FAQ | Already planned (Phase 8); `tools/public_release_check.py` gates it |
| **Market-approved medications only**; combinations allowed if justified | discussion #5, `DEEP_DIVE.md` section 4 | Approval status checked by code (ChEMBL `max_phase=4`, DrugCentral approvals, openFDA label presence), never from model memory. Supplements (NR/NMN, fisetin, quercetin) can appear only as adjuncts or in the considered-and-rejected table |
| GenAI disclosure (provider, plan/tier, data-handling) | form sharedStrings 23 (required, red) | Generated from `docs/llm_log.md` like Track 1 |
| Rubric: Scientific Rigor 35 / Potential Impact 25 / Innovation 25 / Scalability 15 | `rules.py`, `about.py` | Section 3 maps every deliverable to a criterion |
| Judges: researchers, clinicians, **patient advocates**; pre-recorded, no Q&A | `rules.py` section 7 | The video and the report must stand alone; plain-language layer is mandatory |
| Privacy: no re-identifying detail beyond the family's own public posts | `rules.py` citation section | Only the 8 HPO terms and two named variants already published in the Track 1 report appear; `public_release_check.py` runs on every T2 output |
| Phase is **unknown** (0 spanning reads; Track 1 report) | `docs/report.md` phasing section | The mechanism section states the in-trans assumption up front and what it rests on (MVA1 genotype pattern, viability of the genotype, phenotype fit), never asserts it as observed |

## 1. Thesis (what we are submitting)

**"From one child's genotype to a ranked, testable repurposing portfolio - and
the open engine that produced it."**

1. **Mechanism, quantified per allele.** p.Leu737Ter (null: NMD prediction from
   exon structure, truncation before the kinase-like domain) + p.Asn1002Lys
   (hypomorph evidence: domain position, conservation, AlphaMissense/REVEL/CADD,
   protein language-model effect score, structural context on the AlphaFold
   model). Pathway: reduced BubR1 -> weakened spindle assembly checkpoint (SAC)
   and kinetochore-microtubule attachment error correction (BubR1 KARD / PP2A-B56)
   -> chromosome mis-segregation -> mosaic aneuploidy -> (a) p53/p21 + p16
   senescence and proliferation failure (growth restriction), (b) clonal
   evolution and cancer predisposition (rhabdomyosarcoma, Wilms), (c) progeroid
   tissue decline (BubR1 hypomorph mouse literature). Each arrow carries a
   resolved citation.
2. **Three therapeutic axes, each mapped to approved drugs by code:**
   - *Axis A - restore or stabilise residual BubR1 function* (the missense
     allele is the only functional copy; anything that raises its abundance or
     activity is disease-modifying): SIRT2 / NAD+ axis, proteostasis of BubR1.
   - *Axis B - remove or neutralise the damage aneuploidy causes*: senolytics
     and senomorphics (dasatinib, sirolimus/everolimus, metformin), the
     BubR1-hypomorph mouse p16 clearance result as the anchor.
   - *Axis C - aneuploid-cell selective vulnerability and cancer interception*:
     proteotoxic/energy-stress agents (chloroquine/hydroxychloroquine, metformin),
     mitotic-checkpoint dependency of aneuploid cells, plus a non-drug
     surveillance recommendation (whole-body MRI cadence used for CIN cancer
     predisposition syndromes).
3. **A considered-and-rejected table** that is as carefully argued as the
   shortlist (e.g. growth hormone for short stature is contraindicated in a
   cancer-predisposition syndrome; SAC/MPS1/KIF18A inhibitors are the opposite
   of what this child needs; p53 suppression is pro-oncogenic; navitoclax not
   approved). This is the strongest rigor signal available.
4. **Testability matrix** against the MVA Society's four funded programs
   (C. elegans *san-1*/*mdf-1* repurposing screen, patient fibroblasts with a
   direct aneuploidy-rate readout, multi-patient scRNA-seq signature reversal,
   supplements program) - readout, assay, expected direction, go/no-go
   threshold, cost tier per candidate.
5. **The engine** (`src/track2/`): seed genes -> pathway expansion -> drug-target
   evidence (Open Targets, ChEMBL, DGIdb, DrugCentral) -> approved-only filter ->
   network proximity on STRING -> transcriptomic signature reversal (LINCS L1000
   via SigCom LINCS: BUB1B-knockdown and CIN70 signatures) -> pharmacogenomic
   association (PRISM repurposing screen vs aneuploidy score / BUB1B expression,
   DepMap) -> pediatric-safety and label filter (openFDA) -> evidence tiers.
   Deterministic, recorded-fixture tests, one command. **Retrospective
   benchmark**: the engine, run blind on genes with an established
   genotype-to-repurposed-drug success (e.g. TSC1/TSC2 -> everolimus/sirolimus,
   PIK3CA overgrowth -> alpelisib, FBN1 -> losartan, KCNJ11 neonatal diabetes ->
   sulfonylurea, CFTR gating -> ivacaftor, ALK2/ACVR1 FOP -> palovarotene where
   approved), reports recall@k of the known drug. That converts "Scalability"
   from a claim into a measured number.

## 2. Workstreams and file ownership

Each lane owns disjoint paths so lanes can run in parallel in one worktree.

| Lane | Owns | Output contract |
|---|---|---|
| L1 Mechanism | `docs/track2/mechanism.md`, `docs/track2/evidence/mechanism.json`, `tools/t2_mechanism.py`, `tests/test_t2_mechanism.py` | per-allele evidence table (domain, exon/NMD, scores, LM effect, structural context), pathway chain with citations |
| L2 Engine | `src/track2/`, `tools/run_track2.py`, `config/track2.yaml`, `tests/test_track2_*.py`, `tests/fixtures/track2/`, `docs/track2/engine.md` | `docs/track2/evidence/candidates.json` (schema 4.1), benchmark JSON (schema 4.3) |
| L3 Dossiers | `docs/track2/evidence/dossiers/*.json`, `docs/track2/evidence/rejected.json`, `docs/track2/evidence/testability.json`, `docs/track2/candidates.md` | schema 4.2, every claim with a resolved PMID/DOI |
| L4 Rigor tooling | `tools/verify_citations.py`, `tests/test_verify_citations.py`, `docs/track2/citation_cache.json`, `docs/track2/rules_refresh.md`, `docs/track2/landscape.md` | citation gate; Discussions refresh since 2026-10-01; T2 form-question map |
| L5 Compute | `tools/modal_track2.py`, `tools/t2_prism.py`, `tests/test_t2_prism.py`, `docs/track2/evidence/prism.json`, `docs/track2/evidence/esm.json` | aneuploidy-selective approved drugs from PRISM; ESM variant effect for N1002K. Runs on the **new Modal account** (section 5) |
| L6 Report | `tools/make_track2_report.py`, `docs/track2_report_template.md`, `docs/track2_report.md`, `nikhilpise_track2_report.md`, `tests/test_make_track2_report.py` | report rendered from evidence JSON only (no hand-typed numbers), form answers for prompts 13-20/22/23 |
| L7 Video | `video/` (script, slides, narration, captions, build script) | `video/out/pitch.mp4` <= 3:00 (ffprobe-checked), `.srt` captions |
| L8 Community | `docs/track2/FAMILY_SUMMARY.md`, engine CLI/Space app under `apps/repurposing_space/` | patient-facing explainer of the candidates; public demo with zero patient data |
| L9 Red team | `docs/track2/redteam.md`, `docs/track2/rubric_self_assessment.md` | hostile clinician + pharmacologist + patient-advocate reviews; rubric self-score with evidence per point |

Order: L1-L5 in parallel now -> L6 once schemas are populated -> L9 on the
rendered report -> fixes -> L7 on the frozen content -> v1 submit Oct 20 ->
L9 second pass -> final Oct 23.

## 3. Rubric map

| Criterion | Weight | What earns it here |
|---|---|---|
| Scientific Rigor | 35 | per-allele mechanism with quantified evidence; phase-unknown caveat; every claim cited and machine-verified (`verify_citations.py` gate, 100% coverage); approval status checked by code; considered-and-rejected table; pediatric safety/dose sections from FDA labels; retrospective benchmark with recall@k; explicit limitations |
| Potential Impact | 25 | candidates mapped onto the MVA Society's four funded programs with concrete assays and go/no-go thresholds; cancer-surveillance recommendation; candidates applicable to other BUB1B / CEP57 / TRIP13 MVA genotypes |
| Innovation | 25 | multi-modal evidence engine (target evidence + network proximity + L1000 signature reversal + PRISM aneuploidy pharmacogenomics + LM variant effect) with transparent scoring; the "residual-allele rescue" framing for a null + hypomorph genotype |
| Scalability | 15 | one-command engine for any gene/HPO set; retrospective benchmark on independent diseases; public Space/CLI; recorded fixtures so it runs offline |

GATE 7 (from plan.md, kept): self-score >= 85% per criterion with written
justification; 100% citation coverage; all candidates market-approved by code;
form prompts 13-20, 22, 23 answered; video <= 3:00 uploaded and verified while
logged out; submitted as the final entry.

## 4. Schemas

### 4.1 `candidates.json` (L2 writes, L6 reads)

```json
{"schema": "t2.candidates/1", "generated_by": "tools/run_track2.py", "config_sha": "...",
 "seed_genes": [{"symbol": "BUB1B", "role": "disease_gene"}],
 "candidates": [{
   "drug": "sirolimus", "chembl_id": "CHEMBL413", "drugcentral_id": 2468,
   "approval": {"max_phase": 4, "fda": true, "ema": true, "first_approval": 1999,
                "pediatric_labeling": "...", "evidence": ["chembl", "drugcentral", "openfda"]},
   "targets": ["MTOR"], "axis": "B", "mechanism_of_action": "MTOR inhibitor",
   "evidence": {"target_overlap": 0.0, "network_proximity_z": -2.1,
                "signature_reversal": {"score": 0.0, "signature": "BUB1B_shRNA", "source": "sigcom-lincs"},
                "prism_aneuploidy": {"beta": 0.0, "q": 0.0}, "literature": 0},
   "score": 0.0, "tier": "T1|T2|T3", "rationale_keys": ["..."]}]}
```

### 4.2 Dossier `dossiers/<drug>.json` (L3 writes)

```json
{"schema": "t2.dossier/1", "drug": "sirolimus", "axis": "B",
 "claims": [{"id": "c1", "text": "...", "kind": "mechanism|preclinical|clinical|safety",
             "cites": ["PMID:12345678"], "strength": "direct|indirect|analogy"}],
 "pediatric": {"approved_pediatric_indication": "...", "label_source": "openFDA set_id ...",
               "key_risks": ["..."], "monitoring": ["..."]},
 "testability": {"celegans": {...}, "fibroblasts": {...}, "scrnaseq": {...}, "supplements": {...}},
 "verdict": "shortlist|adjunct|rejected", "verdict_reason": "..."}
```

### 4.3 Benchmark `benchmark.json` (L2)

`{"schema": "t2.benchmark/1", "cases": [{"gene": "TSC2", "known_drugs": ["everolimus"], "rank_of_known": 3, "k": 10}], "recall_at_10": 0.0}`.
Known-drug truth comes from cited approvals, fixed in `config/track2.yaml`
**before** the engine is run (decision-freeze discipline carried over from
Track 1).

## 5. Second Modal account (public data only)

- Operator action (one command, browser login):
  `! modal token new --profile track2` (adds a profile to `~/.modal.toml`;
  the existing `nikhilpise2006` profile stays active).
- Every Track 2 Modal command runs with `MODAL_PROFILE=track2` set
  explicitly; the active profile is not changed.
- **Public data only** on this account: PRISM/DepMap downloads, ESM weights,
  AlphaFold DB model, L1000 signatures. No patient file is uploaded, so the
  deletion runbook only needs a "nothing patient-derived ever existed here"
  row plus the volume wipe for hygiene.
- Budget: $30 credit. Planned spend: ESM-2/ESM-1v on one 1052-aa protein on an
  L4 (~cents), PRISM association (CPU, < $1), optional ThermoMPNN/structure
  job (< $2). Hard cap set in the app via `timeout=` and small GPU class; log
  each run in `docs/runtime_log.md`.

## 6. Agent rules (every lane)

- Write only to the lane's owned paths. No `git commit`/`push`/`merge`, no HF
  upload, no Space submission, no Modal command (L5 prepares, the lead runs).
- Never open `data/`, `results/` or `env/` in the main checkout. The only
  patient-derived facts allowed in prompts or files are the ones already
  published in the Track 1 report: gene BUB1B, `chr15:40209701 T>G`
  (c.2210T>G p.Leu737Ter), `chr15:40220612 T>G` (c.3006T>G p.Asn1002Lys),
  MANE ENST00000287598.11 / NM_001211.6, and the 8 HPO terms.
- **No citation from memory.** Every PMID/DOI is resolved through NCBI
  E-utilities (`esummary`) or Crossref and its title recorded next to the
  claim. Unresolved = not cited.
- Approval status from ChEMBL/DrugCentral/openFDA responses only.
- No em dash characters; plain `-`.
- Tests: stdlib + pytest only, network-free (recorded fixtures under
  `tests/fixtures/track2/`), run with
  `C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe -m pytest`.

## 7. Calendar

| Date | Milestone |
|---|---|
| Oct 12-14 | L1-L5 land; merge; engine run; citation gate green |
| Oct 15-16 | L6 report v0; L9 red-team round 1; fixes |
| Oct 17-18 | L7 video v1 (script, slides, narration, captions); L8 community artifacts |
| Oct 19 | Operator uploads video (YouTube unlisted or public), link verified logged-out; PDF render |
| **Oct 20** | **Submission v1 (insurance)** - full package |
| Oct 21-22 | L9 round 2, final polish, release check, repo public-ready |
| **Oct 23** | **Final submission** (latest-only rule); one slot spare |
| Oct 24 23:59 UTC | Close; repo public; deletion runbook (both Modal accounts) |

## 8. Operator-only actions

1. `! modal token new --profile track2` (before L5 compute runs).
2. Upload `video/out/pitch.mp4` to YouTube/Vimeo, paste the link.
3. Click Submit on the Space (OAuth) for v1 and final, with the fields from
   `docs/track2/submission_fields.md`.
4. Flip the repo public at close.
