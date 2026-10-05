# Track 1 data audit - 2026-10-03

> **Resolution status (2026-10-05):** point-in-time audit; its "pending"
> rows have since run - the CNV/SV + coverage arms completed on
> 2026-10-03 (manta + cnvpytor, mosdepth), the extended-MHC
> `artifact_loci` mask was added and the funnel re-run twice (masked,
> then the indel-CSQ-matching fix), and `data/case/patient.vcf.gz` was
> deleted as a sha256-verified duplicate. This file remains verbatim;
> current state lives in `docs/status.md` and `docs/track1_closeout.md`.

Question answered: do we have all the data required for Track 1, is any more
needed, and is the data legitimate (real files, internally consistent, not
placeholder/slop). Method: byte-level verification against the gated-dataset
manifest, header/record forensics, and independent recomputation of the key
claims (read-level pileup, tabix queries of the annotation stores). Every claim
below was re-derived from the files on disk on this date.

## Verdict

- **All 11 gated-dataset files are present and byte-identical to the published
  manifest** (size + sha256/git-blob-sha1 verified). Nothing from the dataset
  is missing except `README.md`/`.gitattributes` (repo metadata, not data).
- **The data is real.** The VCF carries a full Sentieon/GATK provenance chain,
  the FASTQs form one coherent NovaSeq run, and our independently realigned
  BAM reproduces the shipped VCF's allele counts at every checked site.
- **No new downloads are strictly required.** The gaps below are analysis
  coverage choices and pending runs on data already on hand - with one optional
  exception (external phasing reference data, discussed in 5.2).

## 1. Gated patient data (`data/`) - verified against HF manifest

Source: gated HF dataset `SageBio/mva-hackathon-2026-data`, fetched 2026-10-01/02.
Manifest: `data/.cache/huggingface/trees/59e322...json` (records sizes +
`lfs_sha256` for LFS files, git `blob_id` sha1 for small files).

| File | Manifest check | Result |
|---|---|---|
| `WGS_EX2312012_HGWCNDSX7.vcf.gz` (315.2 MB) | sha256 = `bec64c68...` | **match** |
| `WGS_EX2312012_HGWCNDSX7.vcf.gz.tbi` | sha256 = `6f8fed62...` | **match** |
| `Challenge_Clinical_Phenotype_1.docx` | git blob sha1 = `e585da0c...` | **match** |
| 8x `..._S16_L00{1-4}_R{1,2}_001.fastq.gz` (82.4 GB total) | all sizes byte-exact | **match** |

Note: the docx is a non-LFS git object, so its manifest hash is the git blob
sha1 (`sha1("blob <size>\0" + bytes)`), not a raw sha256 - verified accordingly.

### 1.1 VCF forensics (re-derived, not assumed)

- Caller chain in header: Sentieon 202308.02 `Haplotyper` (emit GVCF) ->
  `GVCFtyper` -> GATK 4.2.4.0 `VariantFiltration`, run on DNAnexus Feb 4-5 2025.
  Reference: `GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr`.
- Contigs: GRCh38 no-`chr` convention (1..22, X, Y, M + decoys/randoms). Header
  declares `PGT`/`PID` FORMAT (read-backed phasing) and the within-sample `AF`
  INFO trap documented in plan.md.
- `results/eda_patient`: 5,012,204 records; 4.08M SNV / 0.93M indel;
  **Ti/Tv 1.9413** (WGS expectation ~2.0); 4.74M PASS; het 3.11M / hom-alt 1.90M;
  770,458 phased genotypes; per-contig counts sane; QUAL/FILTER histograms
  enumerated. Sex check classified **ambiguous** (X-het 7.3%, 13.8k Y calls) -
  noted, not blocking; worth a sentence in the report's limitations.
- These stats are incompatible with synthetic/placeholder data (Ti/Tv, het/hom
  ratio, LD-phase structure, and DNAnexus provenance are all consistent with a
  real clinical WGS run).

### 1.2 FASTQs - one coherent sequencing run

- All 8 files share read-header instrument/run/flowcell IDs from one
  coherent NovaSeq run (barcode-level identifiers redacted for the
  public repo); lanes 1-4 x R1/R2, dual-indexed. Exactly the structure
  of a real 4-lane NovaSeq WGS run.
- Integrity proven two ways: (a) all sizes byte-match the manifest; (b) the
  full realignment consumed every file end-to-end (1,076,022,541 reads,
  99.61% mapped, 98.12% properly paired, 12.9% marked duplicates) - any
  truncated/corrupt member would have aborted the stream.
- Effective depth ~536M read pairs x 151 bp ≈ 160 Gb → ~50x raw coverage,
  deeper than the participant-reported ~404M-pair expectation (more data,
  not less).

### 1.3 Clinical phenotype

docx is a real clinical narrative (not a template): rhabdomyosarcoma,
nephrocalcinosis, short stature, failure to thrive, skeletal muscle
atrophy, prematurity, severe IUGR, parental recurrent miscarriages.
(Exact gestational age and birth weight are redacted from the public
repo - they are re-identifying narrative detail beyond the HPO terms.)
All 8 extracted terms in `data/hpo_terms.json` resolve to real ontology names
in `env/corpus/hp.obo` and match the document 1:1:

HP:0002859 Rhabdomyosarcoma · HP:0000121 Nephrocalcinosis · HP:0004322 Short
stature · HP:0001508 Failure to thrive · HP:0003202 Skeletal muscle atrophy ·
HP:0001622 Premature birth · HP:0001518 Small for gestational age ·
HP:0200067 Recurrent spontaneous abortion

## 2. Derived patient artifacts - verified

| Artifact | Check |
|---|---|
| `data/case/patient.vcf.gz` (= VEP-annotated exon slice, 179 MB, 478,174 records) | CSQ header carries the full plugin stack: `CADD_PHRED`, `CADD_RAW`, `AlphaMissense_{class,score}`, all 4 `SpliceAI_pred_DS_*`, `REVEL`, `gnomADe_*_AF` (9 populations), `CLIN/CLIN_SIG`. VEP ran cache-free (GTF+fasta mode); warnings file contains only benign UTR/start_codon feature ignores. |
| `env/exomiser/patient.chr.vcf` (1.16 GB) | chr-normalized copy for Arm A; ran to completion → `results/exomiser_patient/` (BUB1B_AR **rank 1**, score 0.9819; BUB1B_AD also rank 4). |
| `region.bam` (3.3 MB, root) + `.bai` | Valid BAM, no-chr dictionary, coordinate-sorted. Full provenance in `@PG`: per-lane `bwa mem 0.7.19` with correct `@RG` (SM=WGS_EX2312012, PL=ILLUMINA) -> samtools 1.24 sort/merge/collate/fixmate/markdup -> `samtools view 15:40100000-40250000`. |
| `bub1b_region.vcf` / `phased_local.vcf` / `results/track1_patient_modal/realign/{phased,region_variants}.vcf` | Consistent across local and Modal runs; both candidate sites remain `0/1` (see 5.2). |

## 3. Reference + annotation corpus (`env/`) - verified

- **Reference**: `env/ref/GRCh38_no_alt_plus_hs38d1.fna` + `.fai` + complete bwa
  index (.0123/.amb/.ann/.bwt/.pac/.sa) - matches the VCF's `##reference` line.
  Root `ref.fna` is a byte-identical duplicate (see housekeeping).
- **gnomAD**: `env/vep_ann/gnomade_custom.vcf.gz` (2.2 GB, exomes slice) + `tbi`;
  dense real entries at the BUB1B locus verified by tabix query. Plus
  `env/corpus/gnomad_constraint_v4.1.tsv` (LOEUF/constraint).
- **ClinVar**: `env/vep_ann/clinvar_sig.vcf.gz` + `tbi`; dense MVA1-linked
  BUB1B records verified.
- **CADD v1.7** (SNV 82 GB + InDels 1.2 GB), **AlphaMissense** hg38 TSV,
  **REVEL v1.3** converted to indexed VCF, **SpliceAI** masked SNV GRCh38
  (28.5 GB) + `tbi` - all present, indexed, and wired into the CSQ fields above.
- **HPO corpus**: hp.obo, phenotype.hpoa, genes_to_phenotype, gene_to_hpo,
  gene2disease (mirrored into `data/case/`).
- **Exomiser**: cli-14.0.0 + `2406_hg38` + `2406_phenotype` bundles.
- **dbNSFP absent by design** (registration auto-rejected; replaced by the
  direct sources above - documented in `docs/runtime_log.md`, arguably better
  provenance anyway).

## 4. Evidence recomputed at the candidate loci (the "is it slop" test)

The strongest possible check: does our independently realigned BAM reproduce
the shipped VCF, and do the annotation stores corroborate?

| Site (chr15) | VCF call | Our pileup on `region.bam` | gnomAD exomes | ClinVar | Predictors |
|---|---|---|---|---|---|
| 40209701 T>G (c.2210T>G, p.Leu737Ter) | het 0/1, AD 21/25, GQ99 | **25 T / 27 G** (VAF 52%) | rs759242053, AF 7.87e-05 | **Pathogenic/LP**, MVA1 OMIM:257300 | stop_gained, CADD 36, SpliceAI ~0 |
| 40220612 T>G (c.3006T>G, p.Asn1002Lys) | het 0/1, AD 15/13, GQ99 | **16 T / 16 G** (VAF 50%) | AF 6.84e-07 | not reported (T>A VUS, T>C LB at same pos) | missense, CADD 24.5, AM 0.9229 LP, REVEL 0.472 |
| 40216470 A>G (deep intronic) | het 0/1, AD 28/18 | **30 A / 20 G** (VAF 40%) | n/a (outside exome slice) | none | SpliceAI all deltas 0.00 |

Read-level allele balance from our own alignment independently reproduces all
three shipped genotype calls. gnomAD AFs queried directly match the VEP-CSQ
values bit-for-bit. The ClinVar Pathogenic record (ALLELEID 529272) matches
what Exomiser reported. The data is internally consistent at every layer.

## 5. Gaps and caveats (analysis coverage, not missing downloads)

5.1 **Funnel input is exon-only.** `patient.vcf.gz` was sliced by
`exons_pm200bp.bed` (478K of 5.01M records). The deep-intronic hypothesis site
40216470 - present in the raw VCF with clean AD 28/18 - is **1,026 bp from the
nearest BUB1B exon**, outside the slice, so the funnel could never evaluate it
despite plan.md requiring "evaluate it on evidence, not ignore it." Two cheap
fixes, no downloads needed: (a) annotate just the off-slice candidate sites
(SpliceAI row already pulled above: all deltas 0.00 - it would score as
splice-benign anyway); or (b) regenerate the slice from `genic_pm5kb.bed`,
which already exists on disk and covers the full BUB1B body
(40156022-40399288). Also note gnomAD coverage is exomes-only - a true
deep-intronic hit would have no genome AF regardless.

5.2 **In-trans phasing is structurally unresolvable from this data.** The two
sites are 10,911 bp apart vs ~465 bp mean insert (max proper-pair span ~1.3
kb): 0 spanning templates in the region BAM, no `PGT`/`PID` at either site,
and the only phased records between them are homozygous `1|1` sites
(uninformative for het phasing). WhatsHap (both local and Modal runs) correctly
left them `0/1`. The only intermediate het site is 40216470 itself - still
4-7 kb from each flank, beyond read linking. Remaining honest avenues:
population/LD phasing against a reference panel (external data explicitly
sanctioned by the organizers, discussion #22 - All of Us named), or reporting
phase as proven-unknown (already the plan's position; PM3 is correctly
withheld in `acmg_report.json`).

5.3 **Pending runs on existing data** (not new data): CNV/SV arm
(cnvpytor/manta) on the realigned BAM on the Modal `mva-data` volume - a
deletion allele would change the compound-het story and plan Gate 2 requires
checking it; mosdepth coverage stats; a fastp/fastqc QC table for the report
(flagstat already proves integrity, but the per-base-quality/dup metrics feed
the methods write-up).

5.4 **Ranking issue, not a data issue.** Current `submission.csv` ranks an
HLA-DRB1 compound-het (epcr 0.32) above BUB1B (0.064) - a classic MHC
hypervariable-region artifact that Exomiser also surfaces (rank 2). Being
handled via the disclosed `artifact_loci` exclusion in the active plan; no
data change required.

5.5 **Housekeeping** (zero-risk cleanup): `env/vep_ann;C` - stray empty dir
from a mangled Windows path; `env/vep_cache/homo_sapiens_vep_116_GRCh38.tar.gz
.part00-15` (~22 GB) never assembled and now unnecessary (cache-free VEP mode
worked); root `ref.fna` duplicates `env/ref/GRCh38_no_alt_plus_hs38d1.fna`
byte-for-byte (~3.1 GB reclaimable).

## 6. Summary - what we still need

| Need | Status |
|---|---|
| Patient VCF/tbi/docx/FASTQs | have, hash-verified |
| Reference genome + indexes | have |
| VEP annotation + all predictors | have (exon-scoped) |
| gnomAD AFs | have exomes; genomes absent (acceptable for exonic answer; limits off-slice analysis) |
| HPO corpus | have |
| Exomiser + data bundles | have, patient run done (BUB1B rank 1) |
| Realigned BAM + phasing | have (Modal volume + local region.bam); phase unresolvable by construction |
| CNV/SV + coverage metrics | data exists; runs pending |
| External phasing reference panel | optional fallback only |
| Off-slice candidate annotation | 1-variant job, sources on disk |

Bottom line: the data is legitimate (cryptographically verified against the
organizers' manifest and independently reproduced by our own alignment) and
complete for the exonic answer the pipeline produced. The honest limitations
to carry into the report: exon-scoped funnel input, exome-only AFs, and
structurally unresolvable phase - all three are statements about our analysis
envelope, not about data quality.
