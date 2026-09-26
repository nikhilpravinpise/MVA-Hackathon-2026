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
| results/run_spike/ | Funnel output on synthetic case | KEEP | Ranked hypotheses, funnel counts |
| results/run_control/ | Funnel output on control case | KEEP | Must show no emitted pair (Gate 2) |
