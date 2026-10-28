# env/ retention manifest

**2026-10-28 disposition:** The locally present patient-derived DELETE targets
`env/exomiser/patient.chr.vcf`, `env/realign*`, and top-level BAM/BAI files
were removed or absent; the specified patterns were rechecked with no matches.
Public reference data was retained. See `docs/runtime_log.md`.

Everything under `env/` is gitignored. Every artifact here is either:

| Path | Class | Disposition |
|---|---|---|
| `env/corpus/` | public refs (hp.obo, phenotype.hpoa, genes_to_phenotype) | DELETE/RE-FETCH - re-downloadable via `tools/fetch_refs.py` |
| `env/public_vcfs/` | public data (ClinVar, HG002 slice) | DELETE/RE-FETCH - `tools/fetch_refs.py` |
| `env/real_spike/` | derived fixture (public genome + public ClinVar + cached REST VEP) | KEEP spec (`truth.json`, `BUILD_REPORT.json` reproducible via `tools/build_real_spike.py`) / DELETE bulky VCF+cache as needed |
| `env/ref/` | public reference FASTA (when fetched) | DELETE/RE-FETCH |
| `env/realign*/`, `env/*.bam`, `env/*.bai` | patient-derived aligned reads (if ever produced from proband FASTQs) | **DELETE** - patient-derived data; same deletion day as `data/` |
| `env/exomiser/` | exomiser-cli-14.0.0 distribution (~330 MB unpacked) | DELETE/RE-FETCH - Monarch data portal |
| `env/exomiser_data/` | 2406_hg38 + 2406_phenotype bundles (~30 GB) | DELETE/RE-FETCH - public bundles, no patient data |
| `env/exomiser/*.yml`, `env/exomiser/*-exomiser.*`, `env/exomiser/*.chr.vcf` | generated analysis YAML + output + chr-normalized VCF copies | KEEP spec / DELETE bulky output as needed |
| `env/exomiser/patient.chr.vcf` | chr-normalized copy of the patient VCF (2026-10-01, for Arm-A hg38 bundle) | **DELETE** - patient genotype-scale derived data |
| `env/vep_ann/` | public annotation store (~327 GB): CADD/AlphaMissense/SpliceAI/REVEL/ClinVar custom VCFs, `gnomad_exomes/` raw downloads, `gnomad_slices/`, `gnomade|g_custom.vcf.gz` builds | DELETE/RE-FETCH - all public; rebuild via fetch/build scripts |
| `env/vep_cache/` | VEP 116 cache (~22 GB) | DELETE/RE-FETCH - Ensembl public cache |
| `env/gnomad_chrY_head.bgz` | 256 KB remote-range probe of gnomAD chrY sites | DELETE - public data probe |
| `env/var{1,2}_dbnsfp.json` | dbNSFP lookup probe responses for the two candidate sites | KEEP spec / DELETE - public annotation values, re-queryable |

Housekeeping executed 2026-10-04: `env/vep_cache/*.part*` (~22 GB of
never-assembled cache parts; cache-free `--gtf/--fasta` mode made them moot)
DELETED; repo-root `ref.fna`/`ref.fna.fai` (~3.1 GB, SHA256-verified byte-dups
of `env/ref/` copies) DELETED; `env/vep_ann;C` stray empty dir removed
(previously). ~25 GB total reclaimed.

Rule: nothing under env/ is committed. If a derived artifact contains
patient reads or genotypes at scale it is DELETE-class per plan.md 2.3.

2026-10-12 note: GRCh38 reference bases cited in audits can be re-checked
after local `env/ref/` deletion via the public Ensembl REST `sequence/region`
endpoint or UCSC - no local FASTA copy required.
