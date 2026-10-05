# Track 1 close-out ledger - 2026-10-05

One page that answers "is Track 1 actually, provably done?" - every
plan.md Phase 0-6 item mapped to its evidence, every remaining action
listed with its prep state. Verified server-side, not self-reported:

- **Leaderboard:** row 139, `nikhilpise (@T0X1N)`, `model1_nikhilpise_answer-blind-funnel.csv`,
  **rank_points 100.0 / F-max 1.000 / full match at rank 1**,
  submitted 2026-10-04 07:30 UTC (public `leaderboard_df` read-back).
- **Submitted bytes:** `nikhilpise_answer-blind-funnel.csv` ==
  `results/track1_patient_modal/track1_final_indelfix/submission.csv` ==
  `submissions/model1_nikhilpise_answer-blind-funnel.csv` (byte-identical,
  pinned by `tools/audit_freshness.py`).
- **The call:** BUB1B compound_het `chr15:40209701 T>G` (p.Leu737Ter) +
  `chr15:40220612 T>G` (p.Asn1002Lys), internal rank 7 of 2,025,791
  hypotheses, epcr 0.0749.

## Completion map (plan.md Phases 0-6 -> evidence)

### Phase 0 - access, identity, scaffolding

| Item | Status | Evidence |
|---|---|---|
| HF account + gated dataset access | DONE | granted + fetched 2026-10-01 (`runtime_log.md`) |
| Attestation read before patient data touched compute | DONE | `docs/attestation_hf_gated_access.md` (verbatim 15-field dump) |
| display_name decided + recorded | DONE | `docs/team.md` -> `nikhilpise` (locked pre-submission) |
| GitHub repo created + pushed | DONE | private per rules (public flip at close-out); pushed + synced |
| VCF + .tbi + docx + 8 FASTQs downloaded | DONE | `data/` (sha256s in `data_audit_2026-10-03.md`) |
| `evaluation.py` vendored + parity test | DONE | `scorer/`, `tests/test_oracle_parity.py`, `make audit` |
| ledgers initialized | DONE | `decisions.md`, `llm_log.md`, `runtime_log.md`, `RETENTION.md`s |
| Discussions-watch cadence | OPEN (standing) | `tools/check_discussions.py` - runbook below |

### Phase 1 - data audit / EDA

| Item | Status | Evidence |
|---|---|---|
| docx -> HPO terms | DONE | `data/case/hpo_terms.json` (8 terms), `tools/extract_hpo.py` |
| VCF header forensics | DONE | `docs/data_audit_2026-10-03.md` (bare contigs, no PGT/PID) |
| bcftools-stats equivalent | DONE | `results/eda_patient/eda_report.json` (5,012,204 records, Ti/Tv 1.94) |
| variant-count sanity vs expectation | DONE | same - inside the 4-5M WGS band |
| fastp/fastqc on 8 FASTQs | DONE | `track1_final/fastq_qc/` (expectation deviation investigated + dispositioned in decisions.md) |
| contamination/sex check | DONE | X-het 7.3%, 13.8k Y calls - ambiguous, consistent with mosaicism |
| EDA in report | DONE | report section 2 + `docs/data_audit_2026-10-03.md` |

### Phase 2 - the prioritization model

| Item | Status | Evidence |
|---|---|---|
| both arms on synthetic spike FIRST | DONE | spike recovered rank 1 (report section 3) |
| both arms on proband + top-20 concordance | DONE | `arm_concordance.json` (overlap = BUB1B); Arm-A `BUB1B_AR` rank 1 @ 0.9819 |
| splice check on near-splice candidates | DONE | offslice_eval.json (`15:40216470` splice-benign verdict) |
| CNV/SV arm feeds back | DONE | manta+cnvpytor: 0 calls overlapping BUB1B (report section 4a) |
| funnel emits the pair | DONE | 1 emitted hypothesis of 2,025,791 |

### Phase 3 - phasing & read-level validation

| Item | Status | Evidence |
|---|---|---|
| GRCh38 no-alt reference | DONE | fetched + used by bwa realign (env/ref deleted post-run; record in runbook) |
| PGT/PID parse + chaining | DONE | `src/phasing.py`; VCF carries no PGT/PID -> read-level is the only evidence |
| bwa re-align sorted BAM | DONE | `mva-data:realign` (volume now deleted; `realign/region.sam` retained) |
| DeepVariant locus recall | DONE | both sites 0/1 PASS (GQ42/35), `deepvariant/dv_findings.json` |
| mosdepth locus + genome | DONE | 45.26x locus, 42.08x WGS (report section 2a + figure) |
| second phase call (WhatsHap) | DONE | 15 phase blocks, neither site joins -> honest `unknown` (report section 4) |

### Phase 4 - secondary findings & clinical layer

| Item | Status | Evidence |
|---|---|---|
| 84 ACMG SF v3.3 genes scanned | DONE | `sf_findings.json`; none emitted as submission rows |
| ACMG/AMP classify the pair | DONE | `acmg_report.json` - Pathogenic (PVS1+PM2_P+PP3, 11 pts) |
| disclosure-ethics position | DONE | `docs/disclosure_position.md` |

### Phase 5 - submission engineering

| Item | Status | Evidence |
|---|---|---|
| `submit.py` CSV contract | DONE | byte-level writer, tests pin every clause |
| adversarial fixture battery | DONE | 60 scorer fixtures + 19 mutation fixtures, all green (`make audit`) |
| upload-form dry-run checklist | DONE | `docs/submission_checklist.md` (exercised live on upload) |
| submit once + verify leaderboard | DONE | row 139 verified via public read-back 2026-10-04 |

### Phase 6 - the write-up

| Item | Status | Evidence |
|---|---|---|
| `report_map.md` 13-prompt mapping | DONE | verified by `check_section_refs` |
| report regenerated from artifacts | DONE | `make report-patient` / `make report-upload`; nothing hand-typed |
| mandated acknowledgement | DONE | report + README + community docs + `report_model2.md` |
| evidence figures | DONE | `docs/figures/` (5 SVGs + inline ASCII pileup) |
| disclosed limitations | DONE | report sections 12-13 (ablation fragility, unresolvable phasing, post-observation mask) |

## Post-audit hardening (2026-10-05)

- `tools/make_figures.py` + `docs/figures/`: evidence figures generated
  from artifacts, regenerated deterministically.
- `submissions/`: model1 archive + two oracle-verified model2 candidates
  (v2 HGVS-notes, Exomiser arm) + `docs/report_model2.md`.
- `tools/audit_freshness.py` + `make freshness`: the "nothing stale"
  gate - doc claims vs artifacts, path/section/line refs, CSV identity,
  figure determinism, hygiene scans.
- Resolution banners on the four dated/snapshot docs; live-claim drift
  fixed (test count, upload filename, RETENTION row, plan.md em-dashes).

## Remaining actions - operator-side, all prepped

| Action | When | Prep state |
|---|---|---|
| (Optional) model2 upload | any time while quota remains | `submissions/` holds both candidates + `docs/report_model2.md`; form fields in `submission_checklist.md`; equal score cannot hurt the existing entry |
| Repo public flip | 2026-10-24 close | run `python tools/public_release_check.py`, review findings, then flip visibility; steps in checklist below |
| Deletion email | within 30 days of close | draft staged at `docs/deletion_email_draft.md`; mailbox per `docs/deletion_runbook.md` |
| Discussions-watch | every ~3 days | `python tools/check_discussions.py` - lists threads since last check |
| Freshness sweep | before any upload + after any change | `make freshness` (exit nonzero on drift) + `pytest -m gate` |

### Public-flip pre-flight (one pass when the deadline lands)

```sh
python tools/public_release_check.py   # history scan -> docs/public_release_audit.md
# review the report, esp. any identifier hits (known: commit 265b686)
git remote -v                          # confirm the URL judges will get
gh repo edit --visibility public --accept-visibility-change-consequences
# then browse logged-out and open: README, docs/report.md, docs/figures/*
```

## Deliberately-unresolved (disclosed, not gaps)

- In-trans phasing: unresolvable by construction (sites 10.9 kb apart, 0
  spanning reads, no PGT/PID, WhatsHap blocks don't reach either site) -
  reported `unknown`, honestly.
- Top-5 ablation rule fails on 4/5 source drops - disclosed verbatim in
  the report; the Exomiser-arm convergence is the counter-evidence.
- Track-1 leaderboard position among ~116 equal-score ties is fixed by
  submission timestamp - no further score action exists.
