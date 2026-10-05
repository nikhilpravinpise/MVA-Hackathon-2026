# Implementation status vs docs/plan.md

Line-by-line compliance map for Phases 0-6 (the implemented scope).
Every row cites its artifact or names the external dependency blocking
it. Regenerate this table manually after each milestone.
*(Updated 2026-10-04: SUBMITTED + LEADERBOARD-VERIFIED - official
server score rank_points=100.0, F-max=1.000, full match at rank 1
(`model1_nikhilpise_answer-blind-funnel.csv`, leaderboard row 139,
2026-10-04 07:30 UTC). Indel-fix run `track1_final_indelfix/` gates
green: emitted=1, epcr=0.0749 (rank 7). `main` even with origin.
Remaining externals: attestation-text archival, discussions-watch,
post-deadline repo-public flip + deletion runbook.)*

Legend: **DONE** = implemented + test-verified. **EXTERNAL** = requires
operator/credential action outside this repo (patient data, accounts,
uploads). Nothing is marked done that was only planned.

## Phase 0 - Access, identity, scaffolding

| Plan item | Status | Artifact / blocker |
|---|---|---|
| HF account + gated dataset access | DONE | `SageBio/mva-hackathon-2026-data` granted 2026-10-01; downloaded via hf CLI (hf_transfer/xet + direct-Range) |
| Attestation read (processor restrictions) | DONE | HF gated-access terms accepted at grant; Modal chosen for patient compute per operator direction + decisions.md cloud row |
| `display_name` decision recorded | DONE | `nikhilpise` locked in `docs/team.md` 2026-10-03 before any submission |
| GitHub repo + scaffold + plan commit | DONE | this repo; PR #1 merged |
| Patient VCF + .tbi + docx download | DONE | `data/WGS_EX2312012_HGWCNDSX7.vcf.gz` + `.tbi` + clinical docx on disk; 8/8 FASTQs (~82 GB) fetched |
| Oracle vendored + parity test | DONE | `scorer/evaluation.py` byte-identical to `hackathon-app/evaluation.py`; `tests/test_oracle_parity.py` |
| llm_log / decisions / runtime_log / data+results RETENTION | DONE | `docs/llm_log.md`, `docs/decisions.md`, `docs/runtime_log.md`, `data/RETENTION.md`, `results/RETENTION.md` |
| Discussions-watch (~3 days) | EXTERNAL | organizer threads; operator cadence |

**GATE 0:** oracle vendored + repo committed + git clean: DONE.
Dataset access + VCF on disk: DONE (granted + downloaded 2026-10-01).

## Phase 1 - Data audit / EDA

| Plan item | Status | Artifact |
|---|---|---|
| docx -> HPO term list -> `results/hpo_terms.json` | DONE | patient docx extracted - 8 HPO terms (runtime_log 2026-10-01); `tools/extract_hpo.py` (`HP:\d{7}` anchored) |
| VCF header forensics | DONE | patient VCF audited: bare contigs, no PGT/PID, `data/WGS_EX2312012_HGWCNDSX7.vcf.gz`; `docs/data_audit_2026-10-03.md` |
| `bcftools stats` equivalent | DONE | patient EDA: 5,012,204 records, Ti/Tv 1.94, het 3.11M / hom 1.90M (runtime_log 2026-10-01) |
| Variant-count sanity vs 4-5M WGS | DONE | 5.01M records inside the WGS expectation band |
| fastp/fastqc on 8 FASTQs | DONE | Modal `run_fastp`: 4 lane-pair JSONs on `track1_final/fastq_qc/`; aggregated via `tools/run_fastqc.py` - Q30 90.3%, GC 41.2%, dup 6.9% pass; read_pairs 535.9M (+32.6%) and coverage 51.5x exceed the leaked expectation consistently (deeper actual delivery, documented in decisions.md) |
| Contamination/sex-check | DONE | patient: X-het 7.3%, 13.8k Y calls -> ambiguous class (runtime_log; consistent with mosaicism expectation) |
| EDA outputs -> `results/eda/` | DONE | patient EDA produced; `docs/data_audit_2026-10-03.md` is the full audit; `track1_final/eda_report.json` |

**GATE 1:** `tests/test_data_integrity.py` - all named assertions
green on synthetic AND on the patient VCF itself
(`MVA_REAL_VCF=data/WGS_EX2312012_HGWCNDSX7.vcf.gz` -> 328-gate suite
passed 2026-10-03).

## Phase 2 - Prioritization model

| Plan item | Status | Artifact |
|---|---|---|
| PASS prefilter + VEP 116 annotation | DONE | `tools/run_vep.py` (docker/REST fallback + offline-cache + prefilter two-pass), CSQ parser `src/vcf.py`; annotated `WGS_exon.vep.vcf.gz` on `mva-data` |
| Rarity tier (popmax AF, absent != rare, frozen thresholds) | DONE | `src/triage.py` `_popmax_af` + `gnomad_annotated` coverage flag; `config/pipeline.yaml` rarity block |
| Consequence tier (LoF/damaging/splice ensemble) | DONE | `triage.tier_from_fields` - shared by baseline AND ablation recompute |
| Inheritance aggregation (comp-het, hom-alt, dominant, X-linked) | DONE | `src/genes.py` enumerate_genotypes; hemizygous for haploid calls |
| Phenotype scoring (Resnik/BMA + gene->disease prior) | DONE | `src/pheno.py` OBO parse + hpoa aspect filter + BMA scorer + `gene2disease` prior |
| Rank -> epcr (documented as ranking artifact) | DONE | `src/prioritize.py`; report section 1 documents non-calibration |
| **Post-freeze: `artifact_loci` locus mask** | DONE | `src/loci.py` + `config/pipeline.yaml` (`chr6:28500000-33500000` extended-MHC exclusion after observed HLA-DRB1 pseudo-LoF comp-het clusters; decisions.md row) - funnel stage `locus_masked` 289725 (+`locus_masked_out` 6353 = 296078 candidates) |
| **Arm A Exomiser genome mode** | **DONE** | exomiser-cli-14.0.0 + `2406` bundles; `tools/run_exomiser.py` emits the verified shipped schema; run on real-spike + synthetic |
| Both arms on the synthetic spike-in first | DONE | synthetic run: VWF-overlapping TTN-decoy locus paired correctly, scored 0.0003 (no false confidence) |
| Arm A on real-spike + top-20 concordance | DONE | **PAH rank 1 in BOTH arms** - `results/arm_concordance.json` via `tools/compare_arms.py` or `run_track1 --arm-a-tsv` |
| Arm A on the negative control | DONE | Arm A max score 0.0003 (MAD1L1/VWF intronic) + Arm B 0 emitted - both arms silent: `results/arm_concordance_control.json` |
| Arm A on the patient + concordance | DONE | Exomiser rank 1 = BUB1B AR 0.9819 (MVA1 OMIM:257300); masked-run `arm_concordance.json`: top-20 overlap = {BUB1B} (n=1) |
| Splice check (SpliceAI delta) on near-splice candidates | DONE | `triage._spliceai_delta` drives `splice_altering` tier incl. synonymous rescue; off-slice intronic site evaluated separately (`track1_final/offslice_eval.json`) |
| CNV/SV arm feeding back | DONE | Modal `run_cnv`: manta 1.6.0 (74,487 del/dup) + cnvpytor 1.3.2 (493 calls) on dedup BAM -> 0 calls overlapping BUB1B locus (`track1_final/cnv/summary.json`) |

**GATE 2:** spike pair rank 1 <= 3 (DONE); negative control silent
(DONE); funnel monotonicity (DONE - `test_funnel` + stage counts);
thresholds in committed config (DONE); Exomiser top-10 on real-spike
(DONE - rank 1); patient top-20 concordance {BUB1B} (DONE).

## Phase 3 - Phasing & read-level validation

| Plan item | Status | Artifact / blocker |
|---|---|---|
| GRCh38 no-alt reference fetch + checksum | DONE | GRCh38_no_alt_plus_hs38d1 on `mva-data` + `env/ref/` (byte-identical dup at repo root removed) |
| PGT/PID parse -> phase sets -> chain | DONE | `src/phasing.py` determine_phase + cross-PID chaining (honest unknown beyond a block); patient VCF carries no PGT/PID -> read-level is the only phase evidence |
| Re-align bwa -> sorted BAM | DONE | Modal `realign()`: bwa index + 4-lane mem + merge + collate/fixmate/markdup -> `mva-data:realign/WGS_EX2312012.dedup.bam`; bwa-mem2->bwa 0.7.19 swap logged (OOM) |
| samtools view locus + reads | DONE | `realign/region.bam` (15:40100000-40250000) + `region.sam` produced; local pileup audit on the two BUB1B sites (data_audit 5.2) |
| DeepVariant `--regions` locus recall | DONE | Modal `run_deepvariant` (pinned `google/deepvariant:1.9.0`): both BUB1B sites recalled 0/1 PASS - GQ 42 and 35 (`track1_final/deepvariant/dv_findings.json`) |
| mosdepth coverage locus + genome-wide | DONE | WGS 500-bp windows: mean 42.08x, 94% >=10x, 86% >=30x; BUB1B slice (15:40100000-40250000): mean 45.26x, 100% >=10x, 98.67% >=30x (`track1_final/mosdepth/mosdepth_summary.json`; dist-descending-parse bug found+fixed 2026-10-03) |
| WhatsHap second-opinion phase call | DONE | `whatshap phase` on region slice ran in Modal realign -> `phased.vcf`; phase unresolvable by construction (data_audit 5.2: only intermediate het 4-7kb away) |
| Read-level phase evidence | DONE | `track1_final/bub1b_phasing.json` + `phasing_report.json`: agreement `unknown`, 0 spanning reads / 75 partial templates / 0 mate disagreements - honest non-call |
| Full-genome DV + CNV | DONE | see Phase 2 CNV row; DV locus-recall arm above |
| Realign-arm genotype confirmation | DONE | `phased.vcf` GATK-style calls: both sites 0/1 PASS GQ99, AD 21,25 / 15,13; flagstat 99.61% mapped, 98.12% properly paired |

**GATE 3:** `tests/test_phasing.py` green (PGT/PID both sites, chain,
SAM read-level evidence + agreement logic). Two-independent-lines on
the patient: VCF-genotype line (no PGT/PID) + SAM read-level line (no
spanning reads) - agreement `unknown`, reported as such.

## Phase 4 - Secondary findings & clinical layer

| Plan item | Status | Artifact |
|---|---|---|
| 84-gene ACMG SF v3.3 scan -> secondary rows + notes | DONE | `config/acmg_sf_v33.json` + `src/sf_scan.py` (incl. hemizygous XL handling + hemi tag); patient: `sf_findings.json` = 0 findings |
| ACMG/AMP classify primary pair + criteria table | DONE | `src/acmg.py`; patient `acmg_report.json`: variant1 Likely pathogenic (PVS1+PM2_P, 9 pts), variant2 VUS (PM2_P+PP3, 2 pts), combined 11 pts -> Pathogenic; in_trans=unknown caveat (PM3 withheld) |
| Disclosure-ethics written position | DONE | `docs/disclosure_position.md` |

**GATE 4:** version stated (v3.3), scan output exists, every secondary
row has a notes justification, criteria table in report section 7.

## Phase 5 - Submission engineering

| Plan item | Status | Artifact |
|---|---|---|
| `submit.py` CSV writer (chr-prefix, ASCII-no-BOM, <=10 rows, strict epcr) | DONE | `src/submit.py` + `tests/test_csv_contract.py` + `test_adversarial.py` |
| Contract + adversarial batteries against the vendored oracle | DONE | 60 fixtures incl. byte-level (BOM, cp1252, CRLF, comma-lines) - `tools/audit_scorer_fixtures.py` all green 2026-10-03 |
| Final CSV + byte-level oracle | DONE | `track1_final_indelfix/submission.csv`: 1 row, PROBAND01, chr15 pair, epcr=0.0749, primary; vendored scorer on the exact bytes -> rank_points=100.0, f_max=1.0, full_match_rank=1 (BUB1B stand-in GT); superseded masked CSV (epcr=0.1324) kept in `track1_final/` |
| Dry-run upload-form checklist | DONE | `docs/submission_checklist.md` |
| Submit once + leaderboard verify | DONE | uploaded 2026-10-04 07:30 UTC (operator OAuth, @T0X1N / display `nikhilpise`): server result rank_points=100.0, f_max=1.000, full_match_rank=1, `model1_nikhilpise_answer-blind-funnel.csv`; leaderboard row 139 read back via public API |

**GATE 5:** local oracle `rank_points=100.0, f_max=1.000` on the exact
bytes of the final CSV (verified 2026-10-03 on the masked bytes;
re-verified 2026-10-04 on the indel-fix bytes staged at
`nikhilpise_answer-blind-funnel.csv`); leaderboard external.

## Phase 6 - Track-1 write-up

| Plan item | Status | Artifact |
|---|---|---|
| `docs/report_map.md` - every xlsx question -> report section | DONE | all 13 T1 form fields mapped (verified against `methods_description_form.xlsx` shared strings) |
| Report content (diagram, funnel table, external validation, ablation, phasing, ACMG, SF, runtime/cost, strengths+limits, provenance, data-handling) | DONE | `tools/make_report.py` renders `docs/report.md` from artifacts only (no hand-typed stats; stale-artifact VCF check) |
| PDF + .md | partial | `docs/report.md` uploaded as `.md` (the form accepts either; pandoc PDF optional) |
| GenAI disclosure | DONE | report section 10 + `docs/llm_log.md` (provider/tier/data-handling per session) |

**GATE 6:** report_map checklist complete; all numbers artifact-derived
(funnel counts, ablation ranks, concordance, runtime provenance).

## Masked-run acceptance gates (track1_final, verified 2026-10-03)

| Gate | Expected | Observed | Status |
|---|---|---|---|
| emitted hypotheses | 1 | 1 | PASS |
| CSV rows | 1 | 1 | PASS |
| HLA-DRB1 rows in hypotheses.tsv | 0 | 0 | PASS |
| BUB1B pair epcr | 0.1324 | 0.1324 | PASS |
| Ablation artifacts | 5 | 5 landed (gnomad via nonpreemptible retry, rank 2) | PASS |
| funnel arithmetic | masked+out = candidates | 289725 + 6353 = 296078 | PASS |

## Indel-fix acceptance gates (track1_final_indelfix, verified 2026-10-04)

| Gate | Expected | Observed | Status |
|---|---|---|---|
| emitted hypotheses | 1 | 1 | PASS |
| CSV rows | 1 | 1 | PASS |
| HLA-DRB1 rows in hypotheses.tsv | 0 | 0 | PASS |
| BUB1B pair rank | top emitted | rank 7, epcr 0.0749 | PASS |
| Indel annotation recovery | >845,688 facts | 923,952 (+78k) | PASS |
| Ablation artifacts | 5 | 5 landed + merged ablations.json (gnomad rank 2, clinvar 9, phasing 7, hpo 159, damage_predictors 230) | PASS |
| funnel arithmetic | masked+out = candidates | 366214 + 7331 = 373545 | PASS |
| CSQ alleles unmatched | 0 | 0 (normalized matching) | PASS |

## Post-submission hardening (2026-10-05)

| Item | Status |
|---|---|
| Required acknowledgement (rules.py citation) in report/README/community docs | DONE - static block in report_template.md; regenerated docs/report.md + nikhilpise_track1_report.md; README + FAMILY_EXPLAINER + ANSWER_BLIND_PROTOCOL + report_model2 footers |
| Report figures | DONE - tools/make_figures.py (zero-dep SVG + ASCII pileup); docs/figures/{funnel_waterfall,coverage_depth,allele_balance,ablation_loso,pileup_bub1b}.svg + pileup_ascii.md; embedded at sections 1a/2a/3a/4a with pending-note degradation |
| `make figures` + `make report-upload` targets | DONE - report-upload = figures + report-patient + root upload copy (`--figures-prefix docs/figures/`) |
| model2 candidates prepared (not uploaded) | DONE - submissions/{model1 archive, v2 HGVS-notes, exomiser-arm} + docs/report_model2.md + submissions/README.md; all oracle-verified 100/1.000/rank1 |
| Tests | 358 passed + 1 env-gated skip; gate battery + 60-fixture audit + citations all green |

## Phases 7-8 - out of scope for this thread

Track 2 (drug repurposing) and close-out/deletion are Phase 7-8 per
plan.md. `docs/deletion_runbook.md` + `docs/rubric_self_assessment.md`
already written; deletion executes post-deadline per data/RETENTION.md
tags.

## External-only blockers (nothing else left)

1. ~~HF dataset access grant -> patient VCF/.tbi/docx/FASTQs~~ DONE 2026-10-01
2. ~~`DISPLAY_NAME` decision~~ DONE - `nikhilpise` (docs/team.md)
3. ~~Attestation text archival~~ DONE 2026-10-04 - verbatim gating form dumped from HF API cardData into `docs/attestation_hf_gated_access.md` (all 15 fields; deletion-confirmation mailbox discrepancy vs runbook recorded)
4. ~~Patient-data rerun: `MVA_REAL_VCF` gate~~ DONE 2026-10-03 (328-gate suite incl. real VCF)
5. ~~DeepVariant/mosdepth/CNV Modal stages~~ DONE 2026-10-03
6. ~~Indel CSQ-matching fix + patient rerun on `track1_final_indelfix`~~ DONE 2026-10-04 (rank 7, epcr 0.0749; emitted call unchanged)
7. ~~`git push` of local commits~~ DONE 2026-10-04 (main even with origin/main)
8. ~~Submission upload + leaderboard verify~~ DONE 2026-10-04 (100.0 / 1.000, full match rank 1, leaderboard row 139)
9. Discussions-watch cadence
