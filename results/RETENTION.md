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
| results/t1_patient/ | Early partial patient driver run | DELETE | Patient variant-scale outputs; superseded by track1_patient_modal/ |
| results/track1_patient/ | Local patient funnel run | DELETE | result.json 2.3 GB + hypotheses.tsv 151 MB = patient genotype-scale dumps; funnel_counts/eda aggregates may be re-derived |
| results/track1_patient_modal/funnel/result.json | Modal patient funnel full dump (2.2 GB, 1.48M hypotheses) | DELETE | Per-variant patient score sheet |
| results/track1_patient_modal/funnel/hypotheses.tsv | STALE - from the superseded Oct-2 degraded-annotation modal run (BUB1B rank ~136) | DELETE | Do NOT cite; canonical ranking lives in result.json (BUB1B pair rank 8) |
| results/track1_patient_modal/funnel/funnel_counts.json | STALE (emitted:3, same superseded run) | DELETE | Canonical counts: result.json funnel block (emitted:4) |
| results/track1_patient_modal/realign/*.vcf | Patient region/phased VCFs | DELETE | Genotype-scale per retention doctrine |
| results/track1_patient_modal/realign/flagstat.txt | Alignment summary stats | KEEP | Aggregate counts only |
| results/track1_patient_modal/submission.csv | Track-1 submission artifact | KEEP | The deliverable itself |
| results/track1_patient_modal/{ablations,acmg_report,arm_concordance,bub1b_phasing,eda_report,phasing_report,run_summary,sf_findings}.json | Modal run finding artifacts | KEEP | Aggregates/ranked findings, no genotype-scale rows |
| results/exomiser_patient/WGS_EX2312012-PASS_ONLY.{json,html,variants.tsv} | Exomiser per-variant patient score dumps (358 MB) | DELETE | Variant-level score sheets |
| results/exomiser_patient/WGS_EX2312012-PASS_ONLY.genes.tsv | Exomiser gene ranking | KEEP | Gene-level findings only |
| results/exomiser_patient/analysis.yml | Exomiser run config | KEEP | Methods record |
