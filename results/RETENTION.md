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
| results/sensitivity.json | 3x3 threshold-grid sensitivity artifact | KEEP | Rank-1 robustness evidence |
| results/eda_spike/ | EDA/QC report on the synthetic VCF | KEEP | Aggregate stats only |
| results/eda_real_spike/ | EDA/QC report on the real-spike VCF | KEEP | Real-data audit: 272 rec, Ti/Tv 1.90 |
| results/arm_concordance.json | Arm A(Exomiser)/B(funnel) top-20 overlap + truth rank, real-spike | KEEP | Plan section-5 cross-method metric: PAH rank 1 both arms |
| results/arm_concordance_spike.json | Same metric on the synthetic case | KEEP | Arm A absent for fake gene - no false confidence expected |
| results/arm_concordance_control.json | Same metric on the negative control | KEEP | Both arms silent - Arm A max score 0.0003, Arm B 0 emitted |
