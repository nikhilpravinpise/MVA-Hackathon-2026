# data/ retention manifest

Pre-registered keep/delete rules for every artifact under `data/` (plan.md
section 2.3 - deletion-day is part of the plan). `data/` is gitignored,
single root for patient data, never committed, never in logs/prompts.

**Tag every file at creation** in the table below. At close (Oct 24 +), the
deletion runbook (plan Phase 8) deletes every DELETE-tagged path within 30
days, then a confirmation email is sent/logged.

## Rules

KEEP (reportable, publishable findings - not genotype-scale):

- ranked variant lists (final + intermediate ranked hypotheses)
- extracted HPO term lists
- gene/pathway rankings, mechanism analysis, drug-candidate tables
- code, configs, reports, leaderboard entries

DELETE within 30 days of close (raw or genotype-scale patient data):

- VCF / BAM / FASTQ copies (shipped or self-produced)
- indices (.tbi, .bai, .fai, bwa-mem2 index structures of patient-derived BAMs)
- genotype-scale tables (per-variant dumps, per-sample matrices, GL/PL tables)
- notebook state containing genotypes (ipynb outputs/checkpoints)
- prompts/logs containing pasted variant blocks
- fine-tuned models trained on raw genome data

Publication rule (plan 2.3): a handful of *named* variants in the report = a
finding; genome-scale genotype tables = prohibited derived data.

## Manifest (entries appended at file creation)

| Path | Description | keep_delete | Notes |
|---|---|---|---|
| `data/WGS_EX2312012_HGWCNDSX7.vcf.gz` | patient WGS VCF (gated HF dataset `SageBio/mva-hackathon-2026-data`, fetched 2026-10-01) | DELETE | genotype-scale raw data |
| `data/WGS_EX2312012_HGWCNDSX7.vcf.gz.tbi` | tabix index for the VCF | DELETE | index of patient genotypes |
| `data/Challenge_Clinical_Phenotype_1.docx` | clinical phenotype narrative (gated) | DELETE | patient document |
| `data/hpo_terms.json` | 8 HPO terms extracted from the docx via `tools/extract_hpo.py` | KEEP | extracted term list (reportable) |
| `data/WGS_EX2312012_HGWCNDSX7_S16_L00{1-4}_R{1,2}_001.fastq.gz` | 8 patient FASTQs (4 lanes x R1/R2, ~80 GB, download in progress 2026-10-01) | DELETE | raw reads |
| `data/WGS_exon.vcf.gz` + `.tbi` | exon-slice of the patient VCF | DELETE | patient genotype slice |
| `data/WGS_exon.vep.vcf.gz` + `_warnings.txt` | VEP-annotated exon slice | DELETE | patient genotype annotations |
| `data/smoke.vcf` + `smoke.vep.txt*` | smoke-test slice of the patient VCF | DELETE | patient genotype slice |
| `data/smoke_region.vcf.gz` + `.tbi`, `smoke_region.vep.*` | regional smoke-test slice + VEP outputs | DELETE | patient genotype slice |
| `data/case/` | Modal-style case bundle: public-corpus copies (hp.obo, phenotype.hpoa, gene2disease.json, hpo_terms.json) | DELETE | corpus files are re-fetchable public data; the bundle's `patient.vcf.gz` was deleted 2026-10-04 (sha256-verified duplicate of `data/WGS_exon.vep.vcf.gz` - the annotated canonical) |
