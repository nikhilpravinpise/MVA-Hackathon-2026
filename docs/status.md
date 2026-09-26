# Implementation status vs docs/plan.md

Line-by-line compliance map for Phases 0-6 (the implemented scope).
Every row cites its artifact or names the external dependency blocking
it. Regenerate this table manually after each milestone.

Legend: **DONE** = implemented + test-verified. **EXTERNAL** = requires
operator/credential action outside this repo (patient data, accounts,
uploads). Nothing is marked done that was only planned.

## Phase 0 - Access, identity, scaffolding

| Plan item | Status | Artifact / blocker |
|---|---|---|
| HF account + gated dataset access | EXTERNAL | needs the operator's HF login + attestation sign-off |
| Attestation read (processor restrictions) | EXTERNAL | attestation text arrives with access grant |
| `display_name` decision recorded | EXTERNAL | `docs/team.md` holds `DISPLAY_NAME: <TBD>` - operator decision, not inventable |
| GitHub repo + scaffold + plan commit | DONE | this repo; PR #1 open |
| Patient VCF + .tbi + docx download | EXTERNAL | gated dataset not yet granted |
| Oracle vendored + parity test | DONE | `scorer/evaluation.py` byte-identical to `hackathon-app/evaluation.py`; `tests/test_oracle_parity.py` |
| llm_log / decisions / runtime_log / data+results RETENTION | DONE | `docs/llm_log.md`, `docs/decisions.md`, `docs/runtime_log.md`, `data/RETENTION.md`, `results/RETENTION.md` |
| Discussions-watch (~3 days) | EXTERNAL | organizer threads; operator cadence |

**GATE 0:** oracle vendored + repo committed + git clean: DONE.
Dataset access + VCF on disk: EXTERNAL.

## Phase 1 - Data audit / EDA

| Plan item | Status | Artifact |
|---|---|---|
| docx -> HPO term list -> `results/hpo_terms.json` | DONE (tool) / EXTERNAL (patient docx) | `tools/extract_hpo.py` (all `word/*.xml` parts, `HP:\d{7}` anchored); tested on synthetic docx |
| VCF header forensics | DONE | `src/vcf_qc.py` integrity_report: fileformat, contigs, chr-prefix check, PGT/PID FORMAT, caller line, INFO-AF trap documented |
| `bcftools stats` equivalent | DONE | `vcf_qc.compute_stats` (records, SNV/indel, Ti/Tv, het/hom, rsid, per-contig, QUAL/FILTER histos) |
| Variant-count sanity vs 4-5M WGS | DONE | Gate-1 `n_bounds` assertion in `tests/test_data_integrity.py` |
| fastp/fastqc on 8 FASTQs | DONE (tool) / EXTERNAL (files) | `tools/run_fastqc.py` (fastp+fastqc commands, JSON parse, expectation compare, corrupt-JSON fail) |
| Contamination/sex-check | DONE | `vcf_qc.sex_check` (X-het-rate + Y-call-count classes, tested male/female/ambiguous) |
| EDA outputs -> `results/eda/` | DONE | `tools/run_eda.py`; artifact on synthetic case at `results/eda_spike/` |

**GATE 1:** `tests/test_data_integrity.py` - all named assertions
implemented (contigs-no-chr, PGT/PID, count bounds, Ti/Tv, FILTER
enumeration, `HP:\d{7}` HPO, fastq-count expectation) and green on
synthetic; the `MVA_REAL_VCF` parametrization is env-gated pending the
patient file.

## Phase 2 - Prioritization model

| Plan item | Status | Artifact |
|---|---|---|
| PASS prefilter + VEP 116 annotation | DONE | `tools/run_vep.py` (docker/REST fallback + offline-cache + prefilter two-pass), CSQ parser `src/vcf.py` |
| Rarity tier (popmax AF, absent != rare, frozen thresholds) | DONE | `src/triage.py` `_popmax_af` + `gnomad_annotated` coverage flag; `config/pipeline.yaml` rarity block |
| Consequence tier (LoF/damaging/splice ensemble) | DONE | `triage.tier_from_fields` - shared by baseline AND ablation recompute |
| Inheritance aggregation (comp-het, hom-alt, dominant, X-linked) | DONE | `src/genes.py` enumerate_genotypes; hemizygous for haploid calls |
| Phenotype scoring (Resnik/BMA + gene->disease prior) | DONE | `src/pheno.py` OBO parse + hpoa aspect filter + BMA scorer + `gene2disease` prior |
| Rank -> epcr (documented as ranking artifact) | DONE | `src/prioritize.py`; report section 1 documents non-calibration |
| **Arm A Exomiser genome mode** | **DONE** | exomiser-cli-14.0.0 + `2406` bundles; `tools/run_exomiser.py` emits the verified shipped schema; run on real-spike + synthetic |
| Both arms on the synthetic spike-in first | DONE | synthetic run: VWF-overlapping TTN-decoy locus paired correctly, scored 0.0003 (no false confidence) |
| Arm A on real-spike + top-20 concordance | DONE | **PAH rank 1 in BOTH arms** - `results/arm_concordance.json` via `tools/compare_arms.py` or `run_track1 --arm-a-tsv` |
| Splice check (SpliceAI delta) on near-splice candidates | DONE | `triage._spliceai_delta` drives `splice_altering` tier incl. synonymous rescue |
| CNV/SV arm feeding back | DONE (runner) / EXTERNAL (BAM) | `tools/run_cnv.py` emits cnvpytor/manta commands for the aligned BAM |

**GATE 2:** spike pair rank 1 <= 3 (DONE); negative control silent
(DONE); funnel monotonicity (DONE - `test_funnel` + stage counts);
thresholds in committed config (DONE); Exomiser top-10 on real-spike
(DONE - rank 1).

## Phase 3 - Phasing & read-level validation

| Plan item | Status | Artifact / blocker |
|---|---|---|
| GRCh38 no-alt reference fetch + checksum | DONE (tool) / partial (fetch) | `tools/fetch_refs.py` handles the public refs |
| PGT/PID parse -> phase sets -> chain | DONE | `src/phasing.py` determine_phase + cross-PID chaining (honest unknown beyond a block) |
| Re-align bwa-mem2 -> sorted BAM | DONE (script) / EXTERNAL (FASTQs) | `tools/run_realign.py` emits the full script (bwa, samtools, mosdepth, whatshap, deepvariant, locus export) |
| samtools view locus + IGV reads | EXTERNAL | needs patient BAM |
| DeepVariant `--regions` locus recall | DONE (script) / EXTERNAL | inside `run_realign.py` emitted script |
| mosdepth coverage locus + genome-wide | DONE (script) / EXTERNAL | inside `run_realign.py` emitted script |
| WhatsHap second-opinion phase call | DONE (tool) / EXTERNAL (real BAM) | `tools/run_phasing.py` on synthetic SAM battery; real run awaits BAM |
| Full-genome DV + CNV (optional depth) | EXTERNAL | gated on FASTQs |

**GATE 3:** `tests/test_phasing.py` green (PGT/PID both sites, chain,
SAM read-level evidence + agreement logic). The two-independent-lines
requirement is met for stand-ins (PGT/PID + synthetic SAM); the real-BAM
evidence is external.

## Phase 4 - Secondary findings & clinical layer

| Plan item | Status | Artifact |
|---|---|---|
| 84-gene ACMG SF v3.3 scan -> secondary rows + notes | DONE | `config/acmg_sf_v33.json` + `src/sf_scan.py` (incl. hemizygous XL handling + hemi tag) |
| ACMG/AMP classify primary pair + criteria table | DONE | `src/acmg.py` (SVI-corrected PVS1/PM3/PM2 semantics, withheld-evidence caveats) |
| Disclosure-ethics written position | DONE | `docs/disclosure_position.md` |

**GATE 4:** version stated (v3.3), scan output exists, every secondary
row has a notes justification, criteria table in report section 7.

## Phase 5 - Submission engineering

| Plan item | Status | Artifact |
|---|---|---|
| `submit.py` CSV writer (chr-prefix, ASCII-no-BOM, <=10 rows, strict epcr) | DONE | `src/submit.py` + `tests/test_csv_contract.py` + `test_adversarial.py` |
| Contract + adversarial batteries against the vendored oracle | DONE | 60 fixtures incl. byte-level (BOM, cp1252, CRLF, comma-lines) - `tools/audit_scorer_fixtures.py` all green |
| Dry-run upload-form checklist | DONE | `docs/submission_checklist.md` |
| Submit once + leaderboard verify | EXTERNAL | needs dataset access + display_name |

**GATE 5:** local oracle `rank_points=100.0, f_max=1.000` on the exact
bytes (verified via `tests/test_e2e_gate.py`); leaderboard external.

## Phase 6 - Track-1 write-up

| Plan item | Status | Artifact |
|---|---|---|
| `docs/report_map.md` - every xlsx question -> report section | DONE | all 13 T1 form fields mapped (verified against `methods_description_form.xlsx` shared strings) |
| Report content (diagram, funnel table, external validation, ablation, phasing, ACMG, SF, runtime/cost, strengths+limits, provenance, data-handling) | DONE | `tools/make_report.py` renders `docs/report.md` from artifacts only (no hand-typed stats; stale-artifact VCF check) |
| PDF + .md | partial | `docs/report.md` uploaded as `.md` (the form accepts either; pandoc PDF optional) |
| GenAI disclosure | DONE | report section 10 + `docs/llm_log.md` (provider/tier/data-handling per session) |

**GATE 6:** report_map checklist complete; all numbers artifact-derived
(funnel counts, ablation ranks, concordance, runtime provenance).

## Phases 7-8 - out of scope for this thread

Track 2 (drug repurposing) and close-out/deletion are Phase 7-8 per
plan.md and were not part of the "till phase 6" instruction.

## External-only blockers (nothing else left)

1. HF dataset access grant -> patient VCF/.tbi/docx/FASTQs
2. `DISPLAY_NAME` decision (all members identical)
3. Attestation read (Modal-vs-AWS compute choice)
4. Patient-data rerun: `MVA_REAL_VCF=<vcf> pytest tests/test_data_integrity.py`
5. Realign/WhatsHap/DeepVariant/mosdepth on the real BAM
6. Submission upload + leaderboard verify
7. Discussions-watch cadence
