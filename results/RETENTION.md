# results/ retention manifest

Pre-registered keep/delete rules for every artifact under `results/`
(plan.md section 2.3). Unlike `data/`, this tree holds pipeline OUTPUTS -
most are KEEP-class findings, but anything derived at genotype scale from
patient data is DELETE-class.

**Tag every file at creation** in the table below. The deletion runbook
(plan Phase 8) removes DELETE-tagged paths within 30 days of close.

## Rules

KEEP (findings, methods artifacts - publishable):

- ranked variant lists / hypothesis tables (hypotheses.tsv, ranked results)
- HPO term lists extracted from the clinical docx (hpo_terms.json)
- gene/pathway rankings, mechanism analysis, drug-candidate tables
- EDA/QC summaries (aggregate stats only - no genotype rows)
- code, configs, reports, figures, leaderboard entries
- synthetic-case bundles (synthetic spike-in VCFs/truth - contain NO patient
  data by construction)

DELETE within 30 days of close (patient genotype-scale derived data):

- annotated full-genome VCF outputs (VEP-annotated proband VCF)
- variant-level dumps at genome scale (CSQ tables, per-variant score sheets)
- **patient-run funnel dumps where hypotheses.tsv/result.json carry the
  full ~1.5M-hypothesis enumeration** - the KEEP-class "ranked variant
  list" means a curated top-N excerpt (report table), not the full
  genotype-scale dump. Synthetic/spike hypotheses.tsv stays KEEP (no
  patient genotypes).
- region BAM exports, phasing evidence VCFs at genotype scale
- notebook state containing genotypes; prompts/logs with pasted variant
  blocks

## Manifest (entries appended at file creation)

| Path | Description | keep_delete | Notes |
|---|---|---|---|
| results/spike_case/ | Synthetic proband bundle (generated, no patient data) | KEEP | External-validation fixture (plan 2.1.2) |
| results/control_case/ | Synthetic negative-control bundle | KEEP | Negative-control fixture |
| results/t1_spike/ | Full Track-1 driver output on synthetic case | KEEP | funnel/ + ablations + sf + phasing + acmg + submission.csv + run_summary |
| results/t1_control/ | Full Track-1 driver output on control case | KEEP | Must show 0 emitted + no submission.csv (Gate 2) |
| results/real_spike_run/ | Funnel output on the real-stand-in case | KEEP | HG002 background + ClinVar PAH spike (public data) |
| results/t1_real_full/ | Full Track-1 driver output on real-spike | KEEP | Complete artifact set: funnel+ablations+sf+phasing+acmg+csv+oracle 100/1.0+arm_concordance |
| results/sensitivity.json | 3x3 threshold-grid sensitivity artifact | KEEP | Rank-1 robustness evidence |
| results/eda_spike/ | EDA/QC report on the synthetic VCF | KEEP | Aggregate stats only |
| results/eda_real_spike/ | EDA/QC report on the real-spike VCF | KEEP | Real-data audit: 272 rec, Ti/Tv 1.90 |
| results/arm_concordance.json | Arm A(Exomiser)/B(funnel) top-20 overlap + truth rank, real-spike | KEEP | Plan section-5 cross-method metric: PAH rank 1 both arms |
| results/arm_concordance_spike.json | Same metric on the synthetic case | KEEP | Arm A absent for fake gene - no false confidence expected |
| results/arm_concordance_control.json | Same metric on the negative control | KEEP | Both arms silent - Arm A max score 0.0003, Arm B 0 emitted |
| results/det1/ | Determinism-check rerun A on synthetic case | KEEP | Byte-identical-vs-det2 evidence |
| results/det2/ | Determinism-check rerun B on synthetic case | KEEP | Byte-identical-vs-det1 evidence |
| results/t1_d1/ | Determinism-check driver run A | KEEP | submission.csv + run_summary |
| results/t1_d2/ | Determinism-check driver run B | KEEP | submission.csv + run_summary |
| results/t1_skip/ | --skip-ablations verification run | KEEP | "external" sentinel path check |
| results/run_control/ | Early funnel-only run, synthetic control | KEEP | Superseded by t1_control/ |
| results/run_spike/ | Early funnel-only run, synthetic spike | KEEP | Superseded by t1_spike/ |
| results/run_verify/ | Early funnel-only verification run | KEEP | Superseded by det1/det2 |
| results/smoke_funnel/ | Early smoke funnel run | KEEP | Superseded |
| results/run_real/ | Early funnel-only run, real-spike (HG002) | KEEP | Public data, superseded by t1_real_full/ |
| results/eda_patient/ | Patient EDA/QC report | KEEP | Aggregate stats only - no genotype rows |
| results/t1_patient/ | Early partial patient driver run | DELETE | Patient variant-scale outputs; superseded by track1_patient_modal_run2/ |
| results/track1_patient/ | Local patient funnel run | DELETE | result.json 2.3 GB + hypotheses.tsv 151 MB = patient genotype-scale dumps; funnel_counts/eda aggregates may be re-derived |
| results/track1_patient_modal_run2/ | Renamed run-2 pull (was `track1_patient_modal/` pre-2026-10-04) - PRE-MASK Modal run, preserved for audit vs the masked `track1_final/` rerun | mixed | Auditable baseline: unmasked artifacts prove the artifact_loci mask is direction-neutral (score-space bit-identical, rank changes only). Volume twin: `track1_out/` |
| results/track1_patient_modal_run2/funnel/result.json | Modal patient funnel full dump (2.2 GB, 1.48M hypotheses) | DELETE | Per-variant patient score sheet |
| results/track1_patient_modal_run2/funnel/hypotheses.tsv | STALE - from the superseded Oct-2 degraded-annotation modal run (BUB1B rank ~136) | DELETE | Do NOT cite; canonical ranking lives in result.json (BUB1B pair rank 8) |
| results/track1_patient_modal_run2/funnel/funnel_counts.json | STALE (emitted:3, same superseded run) | DELETE | Canonical counts: result.json funnel block (emitted:4) |
| results/track1_patient_modal_run2/realign/*.vcf | Patient region/phased VCFs | DELETE | Genotype-scale per retention doctrine |
| results/track1_patient_modal_run2/realign/flagstat.txt | Alignment summary stats | KEEP | Aggregate counts only |
| results/track1_patient_modal_run2/realign_local/ | Root-level stray pull moved in 2026-10-04 (region.bam/.bai, bub1b_region.vcf, phased_local.vcf) | DELETE | Patient genotype-scale; cited by docs/data_audit_2026-10-03.md section 2 - archived not deleted per plan 3.2 |
| results/track1_patient_modal_run2/submission.csv | Run-2 submission artifact (superseded) | KEEP | Audit baseline; canonical CSV lands under `track1_patient_modal/` post-rerun |
| results/track1_patient_modal_run2/{ablations,acmg_report,arm_concordance,bub1b_phasing,eda_report,phasing_report,run_summary,sf_findings}.json | Modal run-2 finding artifacts | KEEP | Aggregates/ranked findings, no genotype-scale rows |
| results/track1_patient_modal/track1_final/ | Canonical MASKED-run pull (2026-10-03, `mva-data:track1_final/`) | mixed | Pre-indel-fix baseline run, kept for audit vs `track1_final_indelfix/`; acceptance-gated at the time: emitted=1, epcr=0.1324, 0 HLA-DRB1 |
| results/track1_patient_modal/track1_final/submission.csv | PRE-FIX Track-1 submission artifact (superseded 2026-10-04) | KEEP | Audit baseline - 1 row, PROBAND01, chr15 BUB1B pair, epcr=0.1324, primary; canonical CSV is now `track1_final_indelfix/submission.csv` |
| results/track1_patient_modal/track1_final_indelfix/ | Indel-fix run pull (2026-10-04, `mva-data:track1_final_indelfix/`) - funnel/ablations re-run under the corrected VEP CSQ allele matcher | mixed | Acceptance-gated canonical run: emitted=1, rank 7, epcr=0.0749, 0 unmatched CSQ alleles, alt_gene_facts 923952 |
| results/track1_patient_modal/track1_final_indelfix/submission.csv | FINAL Track-1 submission artifact | KEEP | The deliverable - 1 row, PROBAND01, chr15 BUB1B pair, epcr=0.0749, primary; byte-copied to `nikhilpise_answer-blind-funnel.csv` |
| leaderboard entry | Server-side submission record `model1_nikhilpise_answer-blind-funnel.csv` | KEEP | Leaderboard row 139: `nikhilpise (@T0X1N)`, rank_points=100.0, f_max=1.000, full_match_rank=1, submitted 2026-10-04 07:30 UTC; verified via public leaderboard_df read-back (147 rows); 5/6 quota slots remain |
| results/track1_patient_modal/track1_final_indelfix/{run_summary,eda_report,acmg_report,arm_concordance,phasing_report,sf_findings}.json | Indel-fix run finding artifacts | KEEP | Aggregates/ranked findings, no genotype-scale rows |
| results/track1_patient_modal/track1_final_indelfix/ablations/*.json + ablations.json | Per-source ablation ranks + merged | KEEP | Aggregate ranks only (gnomad 2 / clinvar 9 / phasing 7 / hpo 159 / damage_predictors 230) |
| results/track1_patient_modal/track1_final_indelfix/funnel/funnel_counts.json | Indel-fix funnel stage counts | KEEP | Aggregate (locus_masked 366214, emitted 1) |
| results/track1_patient_modal/track1_final_indelfix/funnel/result_head.json | Curated top-200 ranked excerpt (slim_result) | KEEP | KEEP-class "ranked variant list" = curated top-N, not the full dump |
| results/track1_patient_modal/track1_final_indelfix/funnel/{result.json,hypotheses.tsv} | Indel-fix full hypothesis enumeration (~3.2 GB, 2.03M rows) | DELETE | Patient genotype-scale dump per doctrine above |
| results/track1_patient_modal/track1_final/{run_summary,eda_report,acmg_report,arm_concordance,phasing_report,bub1b_phasing,sf_findings,offslice_eval}.json | Masked-run finding artifacts | KEEP | Aggregates/ranked findings, no genotype-scale rows |
| results/track1_patient_modal/track1_final/ablations/*.json + ablations.json | Per-source ablation ranks + merged | KEEP | Aggregate ranks only |
| results/track1_patient_modal/track1_final/funnel/funnel_counts.json | Masked funnel stage counts | KEEP | Aggregate (locus_masked 289725, emitted 1) |
| results/track1_patient_modal/track1_final/funnel/result_head.json | Curated top-200 ranked excerpt (slim_result) | KEEP | KEEP-class "ranked variant list" = curated top-N, not the full dump |
| results/track1_patient_modal/track1_final/funnel/{result.json,hypotheses.tsv} | Masked-run full hypothesis enumeration (~2.3 GB, 1.43M rows) | DELETE | Patient genotype-scale dump per doctrine above |
| results/track1_patient_modal/track1_final/mosdepth/{mosdepth_summary.json,*.summary.txt,*.dist.txt} | Coverage aggregates | KEEP | WGS 42.08x / locus 45.26x summary + dist curves - aggregate stats only |
| results/track1_patient_modal/track1_final/mosdepth/*.regions.bed.gz{,.csi} | Per-window coverage exports (~172 MB) | DELETE | Genome-scale patient-derived windows |
| results/track1_patient_modal/track1_final/deepvariant/dv_findings.json | DV recall verdict (both sites 0/1 PASS GQ42/35) | KEEP | Aggregate finding |
| results/track1_patient_modal/track1_final/deepvariant/dv_region.vcf | DV-called locus VCF | DELETE | Genotype-scale VCF |
| results/track1_patient_modal/track1_final/fastq_qc/ | 4x fastp JSON+HTML + aggregate/ | KEEP | Aggregate QC metrics only |
| results/track1_patient_modal/track1_final/cnv/summary.json | CNV verdict (0 BUB1B-overlapping; manta 74487 + cnvpytor 493 total) | KEEP | Aggregate finding |
| results/track1_patient_modal/track1_final/cnv/{cnvpytor_calls.*.tsv,proband.pytor} | CNVpytor call tables + binary DB | DELETE | Genome-scale patient variant calls |
| results/track1_patient_modal/track1_final/cnv/manta/ | Manta results + pyflow workspace | DELETE | Genotype-scale SV VCFs + intermediates |
| results/track1_patient_modal/realign/{region.sam,phased.vcf,region_variants.vcf} | Read-level phasing evidence pull | DELETE | Patient genotypes/read alignments |
| results/track1_patient_modal/realign/flagstat.txt | Alignment summary stats | KEEP | Aggregate counts only |
| results/exomiser_patient/WGS_EX2312012-PASS_ONLY.{json,html,variants.tsv} | Exomiser per-variant patient score dumps (358 MB) | DELETE | Variant-level score sheets |
| results/exomiser_patient/WGS_EX2312012-PASS_ONLY.genes.tsv | Exomiser gene ranking | KEEP | Gene-level findings only |
| results/exomiser_patient/analysis.yml | Exomiser run config | KEEP | Methods record |
