# env/ retention manifest

Everything under `env/` is gitignored. Every artifact here is either:

| Path | Class | Disposition |
|---|---|---|
| `env/corpus/` | public refs (hp.obo, phenotype.hpoa, genes_to_phenotype) | DELETE/RE-FETCH - re-downloadable via `tools/fetch_refs.py` |
| `env/public_vcfs/` | public data (ClinVar, HG002 slice) | DELETE/RE-FETCH - `tools/fetch_refs.py` |
| `env/real_spike/` | derived fixture (public genome + public ClinVar + cached REST VEP) | KEEP spec (`truth.json`, `BUILD_REPORT.json` reproducible via `tools/build_real_spike.py`) / DELETE bulky VCF+cache as needed |
| `env/ref/` | public reference FASTA (when fetched) | DELETE/RE-FETCH |
| `env/realign*/`, `env/*.bam`, `env/*.bai` | patient-derived aligned reads (if ever produced from proband FASTQs) | **DELETE** - patient-derived data; same deletion day as `data/` |

Rule: nothing under env/ is committed. If a derived artifact contains
patient reads or genotypes at scale it is DELETE-class per plan.md 2.3.
