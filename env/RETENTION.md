# env/ retention manifest

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

Rule: nothing under env/ is committed. If a derived artifact contains
patient reads or genotypes at scale it is DELETE-class per plan.md 2.3.
