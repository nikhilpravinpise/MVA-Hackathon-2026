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
| _(empty - directory created 2026-09-26, awaiting gated data)_ | | | |
