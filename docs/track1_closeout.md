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
| VCF header forensics | DONE | `docs/data_audit_2026-10-03.md` (bare contigs; PGT/PID declared, 770,458 records carry them, neither BUB1B site does) |
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
| PGT/PID parse + chaining | DONE | `src/phasing.py`; neither BUB1B site carries PGT/PID (elsewhere 770,458 records do) -> read-level is the only evidence |
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

## Final adversarial audit (2026-10-12)

Independent re-verification against primary sources (raw VCF, artifacts,
live Space, organizer threads), not against this repo's own claims.

| # | Finding | Severity | Resolution |
|---|---|---|---|
| A1 | Leaderboard re-read live (gradio `leaderboard_df`, 154 rows): exactly one `nikhilpise (@T0X1N)` entry, row 139, 100.0 / 1.000, 2026-10-04 07:30 UTC. No duplicate (cf. threads #19, #27). GitHub `main` == local HEAD. | verified | none needed |
| A2 | Artifact claims re-derived: CNV 0 overlaps / 74,487 + 493 calls, SF 0 findings, mosdepth 42.08x / 45.26x, ACMG per-variant classes, VCF 5,012,204 records. All match. | verified | none needed |
| A3 | **GenAI disclosure was incomplete and non-compliant**: listed only Devin with opt-out "not asserted" (default allows training); no Claude Code session was ledgered; "no genotypes ever enter a prompt" was too absolute. Organizer rule (thread #2, 2026-09-28): consumer or commercial tier is fine only with training opt-out and no feedback, documented. | blocking | Operator confirmed 2026-10-12: Devin Data Controls opt-out ON; Claude Pro/Max opt-out ON, no feedback. Report section 10 (generated), `docs/llm_log.md` rewritten truthfully; report regenerated. Per thread #10 the repo copy is the authoritative update - no resubmission. |
| A4 | **False claim that the whole VCF lacks PGT/PID** in status.md and this ledger. Truth: header declares PGT/PID, 770,458 of 5,012,204 records carry them; neither BUB1B site does (one participant noted this publicly in thread #17). The report itself was correctly scoped ("at either site"). | blocking for truthfulness | Wording fixed; `check_truth_claims` added to `make freshness` + `test_truth_claims` so it cannot regress. Interpretation unchanged: phase stays `unknown`. |
| A5 | The 15-check freshness gate passed throughout A3/A4: it only checks claims it was taught. | process | New truth-claims check; absolute negatives swept against artifacts (A2). |
| A6 | ACMG "combined 11 pts -> Pathogenic" appears in status/ledger shorthand. The report (section 7) already labels it a hypothesis-level ranking aggregate, with the per-allele classes (LP + VUS) as the clinical call and PM3 withheld. | low | Ledger shorthand is a summary of the report, which carries the caveat. Do not quote the aggregate as a classification externally. |
| A7 | Public flip blind spot: `public_release_check.py` scans identifiers, not genotype content. Tracked docs name patient loci beyond the causal pair: the HLA-DRB1 pseudo-LoF cluster (chr6:325-326 Mb, an artifact shown as a mask rationale) and `15:40216470` (benign off-slice site). Thread #20: organizers asked another team to keep the repo private until IRB guidance arrives on incidental findings; no ruling seen yet. | decision | See open decisions below. |
| A8 | Dates: submissions close and the leaderboard freezes 2026-10-24 23:59 UTC; qualitative evaluation 2026-10-24 to 2026-11-24 (Space About tab); winners 2026-12-18 (thread #26). Repo must be public once evaluation begins. | verified | flip on 2026-10-24 |
| A9 | model2 upload: threads #19 and #27 show a second entry creates a duplicate the organizers must retract. | decision | Default: do NOT upload. `submissions/` stays as an archive. |

### Open decisions and remaining steps (operator)

1. **Merge this branch** (report, ledgers and gate corrections) to `main`
   before the flip so the public repo carries the corrected disclosure.
2. **Public flip, 2026-10-24** (not earlier): run
   `python tools/public_release_check.py`, decide on A7 (accept the
   HLA-DRB1 and off-slice loci as non-clinical method evidence, or redact
   them from tracked docs), re-check thread #20 for an IRB ruling on
   incidental findings (this repo has 0 secondary findings), then flip.
3. **Deletion**: email within 30 days of close (by 2026-11-23, window
   closes 2026-11-24); drafts and runbook are staged. Local `data/` (~80 GB)
   and `results/` (~11 GB) are the remaining patient-derived footprint; Modal
   is already empty.
4. **Discussions**: thread #25 (FASTQ lane/library provenance) was updated
   2026-10-11 by a participant; nothing in it changes our submission.
5. **Do not** upload model2 (A9).

## Remaining actions - operator-side, all prepped

| Action | When | Prep state |
|---|---|---|
| model2 upload | NOT recommended (see A9) | `submissions/` holds both candidates + `docs/report_model2.md`; a second entry creates a duplicate leaderboard row that organizers must retract (threads #19, #27) |
| Repo public flip | 2026-10-24 close (winners Dec 18 per discussion #26 - judging extension only) | run `python tools/public_release_check.py`, review findings, then flip visibility; steps in checklist below |
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
  spanning reads, no PGT/PID at either site, WhatsHap blocks don't reach either site) -
  reported `unknown`, honestly.
- Top-5 ablation rule fails on 4/5 source drops - disclosed verbatim in
  the report; the Exomiser-arm convergence is the counter-evidence.
- Track-1 leaderboard position among ~116 equal-score ties is fixed by
  submission timestamp - no further score action exists.
