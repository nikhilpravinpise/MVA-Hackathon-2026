---
title: Deletion runbook
nav_order: 16
---
# Post-deadline deletion runbook (documented, not executed)

Plan.md Phase 8 + hackathon rules item 10: all patient data must be deleted
from participant systems **within 30 days of hackathon close** (deadline
2026-10-24; deletion due by ~2026-11-23). This file IS the procedure.
**Do not execute before the embargo/close boundary and not before the
leaderboard result is final** - several DELETE-class artifacts double as
audit evidence if a submission is disputed.

Tag authority: `data/RETENTION.md`, `results/RETENTION.md`,
`env/RETENTION.md` carry per-path KEEP/DELETE tags. This runbook executes
the DELETE tags; anything untagged defaults to KEEP (findings, methods,
aggregate statistics only).

## 0. Preconditions (verify, don't assume)

- [ ] Hackathon closed (deadline passed) AND leaderboard result accepted.
- [ ] Report + code + aggregate artifacts pushed to the public repo
      (everything KEEP-class is already non-patient by construction).
- [ ] Confirmation email/log drafted (rules require deletion; the log entry
      is the record - `docs/runtime_log.md` gets the execution row).

## 1. Local `data/` tree - all DELETE-tagged

```powershell
# git-bash equivalent shown; run from repo root
rm -f data/WGS_EX2312012_HGWCNDSX7.vcf.gz{,.tbi}
rm -f data/Challenge_Clinical_Phenotype_1.docx
rm -f data/WGS_EX2312012_HGWCNDSX7_S16_L00{1,2,3,4}_R{1,2}_001.fastq.gz
rm -f data/WGS_exon.vcf.gz{,.tbi} data/WGS_exon.vep.vcf.gz data/WGS_exon.vep.vcf.gz_warnings.txt
rm -f data/smoke.vcf data/smoke.vep.txt* data/smoke_region.vcf.gz{,.tbi} data/smoke_region.vep.*
rm -rf data/case/            # patient.vcf.gz is genotype-scale; corpus files re-fetchable
rm -rf data/.cache/          # HF hub download metadata (etags/hashes only, tied to the gated repo)
```

Patient-class strays found OUTSIDE the manifests (storage audit 2026-10-04) -
same DELETE rule applies:

```powershell
rm -f "$env:TEMP/fr.json"       # 2.3 GB full patient funnel dump (stale pre-indelfix copy)
rm -f "$env:TEMP/region.bam"    # 3.3 MB patient locus BAM slice
rm -f "$env:TEMP/smoke.vcf"     # 108 B patient variant line (BUB1B site)
# pytest-of-Nikhil/ temp tree is synthetic fixtures only - no action needed
```

Agent-session transcripts carrying pasted patient variant rows (storage audit
2026-10-04, round 4) - "prompts/logs with pasted variant blocks" per
results/RETENTION.md rules:

```powershell
# ~9 pasted patient VCF rows (chr15:40209701/40209710 locus, chr12 PAH slice)
# across 4 files under:
rm -rf "$env:APPDATA/Devin/cli/summaries"   # or selectively: history_{54e29530,65c86439,a894a81c,be4ab009}*.md
```

KEEP survivors in `data/`: `hpo_terms.json` (extracted term list),
`RETENTION.md` itself.

## 2. Local `results/` tree - DELETE-tagged paths only

```bash
rm -rf results/t1_patient/ results/track1_patient/
# track1_final + track1_final_indelfix pulls - DELETE rows only (KEEP aggregate
# JSONs, submission.csv, result_head.json, funnel_counts.json, manta summary.json
# stays via cnv/summary.json):
rm -f  results/track1_patient_modal/track1_final/funnel/result.json \
       results/track1_patient_modal/track1_final/funnel/hypotheses.tsv \
       results/track1_patient_modal/track1_final/deepvariant/dv_region.vcf \
       results/track1_patient_modal/track1_final/mosdepth/WGS.regions.bed.gz{,.csi} \
       results/track1_patient_modal/track1_final/mosdepth/region.regions.bed.gz{,.csi} \
       results/track1_patient_modal/track1_final/cnv/proband.pytor \
       results/track1_patient_modal/track1_final/cnv/cnvpytor_calls.*.tsv
rm -rf results/track1_patient_modal/track1_final/cnv/manta/    # SV VCFs + pyflow workspace
rm -f  results/track1_patient_modal/track1_final_indelfix/funnel/result.json \
       results/track1_patient_modal/track1_final_indelfix/funnel/hypotheses.tsv
# realign: keep flagstat.txt (KEEP aggregate), drop genotype files:
rm -f  results/track1_patient_modal/realign/region.sam \
       results/track1_patient_modal/realign/region_variants.vcf \
       results/track1_patient_modal/realign/phased.vcf
rm -rf results/track1_patient_modal_run2/funnel/result.json \
       results/track1_patient_modal_run2/funnel/hypotheses.tsv \
       results/track1_patient_modal_run2/funnel/funnel_counts.json \
       results/track1_patient_modal_run2/realign/ \
       results/track1_patient_modal_run2/realign_local/
rm -f  results/exomiser_patient/WGS_EX2312012-PASS_ONLY.{json,html,variants.tsv}
```

KEEP survivors: all aggregate JSONs (run_summary, eda_report, acmg_report,
sf_findings, ablations, arm_concordance, phasing_report, bub1b_phasing),
both submission.csv files, `genes.tsv`, synthetic/spike/control trees,
`results/RETENTION.md`. The `slim_result` output
(`funnel/result_head.json`, first-200 ranked rows) is a curated top-N
excerpt - KEEP per the ranked-variant-list rule.

## 3. Modal volume `mva-data` - EXECUTED EARLY 2026-10-04 (billing stop)

**Both volumes deleted 2026-10-04** - `mva-data` (~280 GB) and `mva-ann`
(~115 GB) removed via `modal volume delete` to stop all volume billing.
Verified `modal volume list` shows only unrelated legacy volumes. All
canonical artifacts were already pulled to `results/` (Phase 4) and the
leaderboard result was verified-final, so no audit evidence was lost.
The commands below are preserved as the record of what the volumes held.

```bash
# Patient genotype-scale objects - all DELETE:
modal volume rm mva-data WGS_EX2312012_HGWCNDSX7.vcf.gz
modal volume rm mva-data WGS_EX2312012_HGWCNDSX7.vcf.gz.tbi
for i in 1 2 3 4; do for r in 1 2; do
  modal volume rm mva-data WGS_EX2312012_HGWCNDSX7_S16_L00${i}_R${r}_001.fastq.gz
done; done
modal volume rm mva-data case/patient.vcf.gz
modal volume rm mva-data realign/WGS_EX2312012.dedup.bam
modal volume rm mva-data realign/WGS_EX2312012.dedup.bam.bai
modal volume rm mva-data realign/region.bam
modal volume rm mva-data realign/region.bam.bai
modal volume rm mva-data realign/region.sam
modal volume rm mva-data realign/region_variants.vcf
modal volume rm mva-data realign/phased.vcf
for i in 1 2 3 4; do
  modal volume rm mva-data realign/lane_L00${i}.bam
done
modal volume rm mva-data realign/merged.bam
modal volume rm mva-data track1_final/funnel/result.json
modal volume rm mva-data track1_final/funnel/hypotheses.tsv
modal volume rm mva-data track1_out/funnel/result.json
modal volume rm mva-data track1_out/funnel/hypotheses.tsv
modal volume rm mva-data track1_final/deepvariant/dv_region.vcf
modal volume rm mva-data track1_final/cnv --recursive   # manta+cnvpytor genotype tables
modal volume rm mva-data track1_final/mosdepth/WGS.regions.bed.gz{,.csi}
modal volume rm mva-data track1_final/mosdepth/region.regions.bed.gz{,.csi}
modal volume rm mva-data track1_final_indelfix/funnel/result.json
modal volume rm mva-data track1_final_indelfix/funnel/hypotheses.tsv
modal volume rm mva-data WGS_exon.vcf.gz{,.tbi}
modal volume rm mva-data WGS_exon.vep.vcf.gz
modal volume rm mva-data WGS_exon.vep.vcf.gz_warnings.txt

# Public-reference objects on the same volume - re-fetchable, KEEP-or-delete
# is a cost call not a compliance one (GRCh38 .fna/.fai/.bwa-*, gnomAD
# slices, VEP cache, annotation VCFs). Delete to stop volume billing anyway:
modal volume rm mva-data GRCh38_no_alt_plus_hs38d1.fna
modal volume rm mva-data GRCh38_no_alt_plus_hs38d1.fna.fai
# ... plus the ann/ subtrees - re-fetchable public data
```

Or simplest: `modal volume delete mva-data` removes the whole volume once
the aggregate JSONs are pulled locally (they are - Phase 4 pull).

Sister volume `mva-ann` (~115 GB, verified 2026-10-04): 16 files, all public
annotation DBs (CADD, SpliceAI, AlphaMissense, REVEL, ClinVar, gnomade_custom,
Ensembl 116 GTF) - zero patient content. `modal volume delete mva-ann` to stop
billing; re-fetchable via `tools/modal_app.py` ann-build functions.

## 4. Local environment scale

- `env/exomiser/patient.chr.vcf` (~1.2 GB) - **compliance DELETE** (patient
  genotype-scale per env/RETENTION.md): `rm -f env/exomiser/patient.chr.vcf`
- `env/exomiser_data/` bundles (~43 GB) + `env/exomiser/` cli (~165 MB) - public
  data, re-fetchable; delete to reclaim disk (not a compliance item).
- `env/vep_cache/` partial downloads - already culled; delete remainder.
- `env/ref/` reference FASTA + bwa index - public data, re-fetchable.
- Docker images (`deepvariant`, exomiser) - `docker image rm` as needed.

## 5. Verification pass

```bash
# No patient-scale files remain:
find data -size +1M -type f           # expect: nothing but RETENTION.md
find results -name "*.vcf*" -o -name "*.bam" -o -name "*.fastq*" -o -name "result.json"
modal volume ls mva-data              # expect: only KEEP aggregates or deleted
modal volume ls mva-data realign/     # expect: flagstat.txt only - no *.bam/*.sam/*.vcf
ls "$TEMP" | grep -iE '\.bam|\.vcf|fr\.json'   # expect: no patient-class strays
git status                            # nothing patient was ever tracked
```

## 6. Record

Append the execution row to `docs/runtime_log.md` (date, paths removed,
approx GB freed, verifier commands run) and mark each manifest table's
deleted rows. Rules item 10 expects deletion inside 30 days - the runtime
log row is the compliance record.

## 7. Confirmation email

Send the deletion confirmation to BOTH mailboxes - the attestation text
(docs/attestation_hf_gated_access.md #6) names
`MVAHackathon2026@synapse.org`, while the rules/runbook text names
`RarediseaserealkidMVAhackathon2026@synapse.org` (rejects senders
without registered Synapse accounts - discussion #15). If either
bounces, post the attempt in Discussions; organizers log it.
