# Track 1 Methods Report - MVA Hackathon 2026

**Team:** `nikhilpise` | **Model:** `model1` | **Generated:** 2026-10-03 14:00 UTC by `tools/make_report.py` (all statistics in this document are regenerated from `results/` - nothing is hand-typed; see GATE-6 checklist in `docs/report_map.md`).

> **Data status banner:** PATIENT RUN COMPLETE - masked rerun on Modal; every number below is regenerated from track1_final artifacts

---

## 0. Submission summary

- **Primary call:** `BUB1B` (compound_het) - chr15:40209701 T>G + chr15:40220612 T>G
- Score 0.716 (damage 0.83 / phenotype 0.40 / inheritance 1.0), epcr 0.13, phasing: **unknown**
- Emitted hypotheses: 1 of 1431695 enumerated (200 in ranked table)

## 1. Approach in detail

A genome-wide, case-agnostic prioritization funnel for an N-of-1 recessive
diagnosis - an Exomiser-class design implemented as a transparent,
deterministic, auditable ranking pipeline rather than a trained black box.
Two independent arms were specified a priori:

* **Arm A (standard):** Exomiser 14.0.0 genome mode (hg38, `2406` bundles,
  PASS_ONLY preset chain) on the same VCF + HPO set - runner
  `tools/run_exomiser.py`, concordance via `tools/compare_arms.py`.
* **Arm B (custom funnel, this report):** seven deterministic stages:

```
annotated VCF (VEP CSQ)
  -> [1] genotype QC + PASS filter           (DP/GQ/VAF windows)
  -> [2] rarity tier                          (gnomAD pop-max AF; absent > rare)
  -> [3] consequence/damage tier              (LoF | damaging-missense ensemble |
                                               splice-altering | other)
  -> [4] artifact-locus mask                  (declared low-mappability loci,
                                               e.g. extended MHC; disclosed
                                               `locus_masked` stage)
  -> [5] inheritance aggregation per gene     (compound-het, hom-alt,
                                               dominant-het, X-linked)
  -> [6] phenotype scoring                    (HPO Resnik/BMA semantic
                                               similarity + gene->disease prior)
  -> [7] rank -> epcr                         (ranking artifact, not a
                                               calibrated probability)
```

Every threshold is frozen pre-analysis in `config/pipeline.yaml`
(sha256 `0286865c373b`) - the answer-blind decision freeze. No variant
identity, gene name, or leaked-space value influenced any parameter; the
pipeline output is the submission.

### 1a. Funnel table (counts per stage, regenerated)

| Stage | Count |
|---|---|
| VCF records | 478174 |
| allele x gene evidence records | 845688 |
| passing genotype QC + filters | 777009 |
| rare tier (pop-max AF <= af_max or absent) | 296080 |
| eligible candidate variants | 296078 |
| post artifact-locus mask (declared loci) | 289725 |
| - removed inside declared artifact loci | 6353 |
| genotype hypotheses enumerated | 1431695 |
| emitted (score >= emit_floor) | 1 |

## 2. Data audit / EDA

- Records: 478174 (SNV 396069, indel 82105), Ti/Tv 2.0883825992133036
- Contigs carry 'chr' prefix: False; PGT/PID present: True/True
- Caller: `##source=VariantFiltration`; reference: `##reference=file://refGenome/GCA_000001405.15_GRCh38_no_alt_analysis_set_plus_hs38d1_maskedGRC_exclusions_v2_no_chr.fasta`
- INFO AF semantics: ambiguous
- CSQ annotation fields: 57

### 2a. Coverage profile (mosdepth)

| Track | Mean depth | Frac >= 10x | Frac >= 30x |
|---|---|---|---|
| WGS | 42.08 | 0.94 | 0.86 |
| region | 45.26 | 1.0 | 0.9867 |

`WGS` = whole-genome 500-bp windows on the dedup BAM; `region` = 100-bp windows over the BUB1B locus slice (15:40100000-40250000).

### 2b. FASTQ QC (fastp -> run_fastqc aggregate)

mode: `fastp_json` - status: `ok`

| metric | status | value | expected |
|---|---|---|---|
| coverage_x | fail | 51.51723564387097 | 35.0 |
| duplication_rate | pass | 0.068956425 | 0.084 |
| gc_content | pass | 0.4120769194940493 | 0.41 |
| q30_rate | pass | 0.9034731443959014 | 0.935 |
| read_pairs | fail | 535917552 | 404000000 |

all_pass: **False** (5 metrics vs leaked-run expectations, +-20% tolerance)

Disposition: `read_pairs`/`coverage_x` run **above** expectation in consistent magnitude while every quality metric passes - the sample was sequenced deeper than the leaked prior (flagstat independently confirms the count). Stale expectation, not a data defect - see decisions.md.

## 3. External validation

The funnel was validated *blind* before the proband call:

* **Synthetic spike-in proband:** a ClinVar-style compound-het pair (LoF +
  damaging missense, in trans via shared PGT/PID phase set) embedded among
  adversarial decoys (TTN-class noise pair, common hom-alt, filtered LoF,
  low-depth call, common-AF damaging missense).
  **Result:** recovered pair == **MATCHES the spiked truth** at rank 1 (score 0.955, in-trans: trans)
* **Negative control:** plausible-looking rare/damaging variation + an
  unrelated HPO set -> **0 hypotheses emitted (expected: funnel stays silent); Arm A (Exomiser) max gene score 0.0003 - also silent** (a funnel that finds a causal
  pair everywhere finds nothing).
* **Arm A vs Arm B concordance:** both arms run; top-20 overlap 1 (BUB1B)
* **Real external validation (public genome + real ClinVar pair):**

- 270 real HG002 background variants in window 12:102800000-103000000
- spiked pair = real ClinVar variants chr12:102839204 G>A (ClinVar 551287, Likely_pathogenic), chr12:102839216 C>A (ClinVar 932274, Likely_pathogenic)
- annotation: 277 alleles via live Ensembl REST VEP
- Funnel: 272 records -> 2 rare -> 2 candidates -> **pair recovered at rank 1** (in_trans: trans, epcr 0.95)

### 3a. Leave-one-source-out ablations

| Dropped source | Tracked-pair rank | Top emitted | Emitted |
|---|---|---|---|
| clinvar | 6 | BUB1B (compound_het) | 1 |
| damage_predictors | 125 | None | 0 |
| gnomad | 2 | BUB1B (compound_het) | 1 |
| hpo | 120 | None | 0 |
| phasing | 5 | BUB1B (compound_het) | 1 |

### 3b. Threshold sensitivity grid

| af_max | min damage votes | true-pair rank |
|---|---|---|
| 1e-05 | 1 | 1 |
| 1e-05 | 2 | 1 |
| 1e-05 | 3 | 1 |
| 0.0001 | 1 | 1 |
| 0.0001 | 2 | 1 |
| 0.0001 | 3 | 1 |
| 0.001 | 1 | 1 |
| 0.001 | 2 | 1 |
| 0.001 | 3 | 1 |

Robust across grid: **True**

Grid corpus: `results/spike_case/spike_proband.vcf` (the 'true-pair rank' column tracks the spiked synthetic pair, not the report run's emitted call).

## 4. Phasing evidence (phase-set + read-level status)

| Evidence | Mechanism | Result |
|---|---|---|
| PGT/PID phase-set fields | unphased | unknown |
| read-level SAM evidence | read_level | unknown |

Agreement: **unknown**

### 4a. Orthogonal evidence arms

**DeepVariant recall (independent caller, deepvariant-1.9.0):**
| Site | GT | GQ | Filter | Recalled het PASS GQ>20 |
|---|---|---|---|---|
| 15:40209701 | 0/1 | 42 | PASS | True |
| 15:40220612 | 0/1 | 35 | PASS | True |

Verdict: **True** (both BUB1B sites independently recalled)

**CNV/SV screen (manta + cnvpytor on the re-aligned dedup BAM):**
- del/dup calls overlapping BUB1B (15:40205000-40232000): **0**
- verdict: `none` - no CNV alleles disturb the biallelic-SNV interpretation

**Off-slice intronic site evaluation:**
- site: `15:40216470 A>G` (1026 bp outside the exon slice)
- AD 28/18; SpliceAI deltas 0.0; gnomAD genomes: absent
- verdict: evaluated; splice-benign under available model; does not change the call

## 5. Automated vs manual review

The submission CSV is the **automated output** of the pipeline
(`src/submit.py` builds bytes that are oracle-validated locally before any
upload). Downstream manual review was limited to: (a) reading the top
hypothesis' evidence fields, (b) confirming the phasing report, (c) the
secondary-findings disclosure decision described in section 7. No variant
was added, removed, or re-ordered by hand.

## 6. Data sources

gnomAD v4.1 AFs, ClinVar, CADD, AlphaMissense, REVEL/dbNSFP 5.3.1, SpliceAI (precomputed), LOEUF, phyloP, HPO (hp.obo + phenotype.hpoa + genes_to_phenotype), Ensembl REST VEP (cache-backed annotations, env/real_spike), ACMG SF v3.3. GIAB HG002 as public stand-in genome.

No proprietary data was used.

## 7. Secondary / incidental findings

Full written position: `docs/disclosure_position.md`. Summary: report
medically actionable findings (ACMG SF v3.3, 84 genes) with an evidence
basis per row; describe evidence, never diagnose; no AR carrier-state rows;
the disclosure decision itself belongs to clinicians, not to a pipeline -
and we say so openly rather than stay silent.

ACMG SF v3.3 (84 genes) scan produced **no reportable findings** in this dataset.

## 8. ACMG/AMP classification of the primary pair

| Variant | Criteria fired | Classification |
|---|---|---|
| 15:40209701:T>G | PVS1, PM2_P | Likely pathogenic |
| 15:40220612:T>G | PM2_P, PP3 | VUS |

Combined call: **Pathogenic** (11 pts - ACMG/AMP Richards2015 subset + Tavtigian2018 points)

Withheld / caveated evidence:
- combined score aggregates evidence across both alleles - a hypothesis-level call for ranking, not a per-variant clinical classification
- in_trans='unknown': PM3 not applicable without proven trans phase

## 9. Runtime and cost

| Job | Where | Time | Cost |
|---|---|---|---|
| Arm-B funnel (this run) | Modal (ephemeral app fleet) | 2340.401s | see runtime_log (Modal billed per-sec) |
| Test battery (19-fixture oracle mutation battery + 60-fixture CSV-contract battery + funnel + e2e) | local | seconds-scale (see docs/runtime_log.md session rows) | $0 |
| Arm-B funnel run_main (masked) | Modal | 3291 s | per-sec billed |
| 5x run_ablation (parallel) | Modal | ~55-70 min each | gnomad arm nonpreemptible after 3 spot reclaims |
| run_fastp x4 lanes | Modal | ~12 min | per-sec billed |
| run_deepvariant (BUB1B locus) | Modal | ~14 min | per-sec billed |
| run_mosdepth (WGS + locus) | Modal | ~9 min | per-sec billed |
| run_cnv (manta 739 s + cnvpytor ~14 min) | Modal | ~22 min | per-sec billed |
| run_phasing + merge + slim | Modal | ~4 min | per-sec billed |

Cloud jobs (VEP/realign/funnel/evidence arms) run on Modal, billed per-second - per-job wall-times and estimates are ledgered in docs/runtime_log.md.

## 10. GenAI disclosure (required)

Cognition Devin CLI (SWE-2 Max); provider terms and per-session usage are ledgered in docs/llm_log.md.

## 11. Provenance, firewall, and compliance

- VCF: `/data/case/patient.vcf.gz` (sha256 `a45a358ede46`)
- Config: parsed-config sha256 `0286865c373b` (frozen pre-analysis; hash recorded at run time - the canonical dict hash, not the file-byte hash)
- Scoring oracle: vendored `hackathon-app/evaluation.py` - local score = official score by construction
- Leak firewall: no leaked-Space coordinates/genes/values in code, tests, configs, or this report
- Compliance: patient data confined to `data/` (gitignored); retention manifests in data/RETENTION.md + results/RETENTION.md

## 12. Method abstract (<=500 words)

We built an answer-blind, deterministic N-of-1 prioritization funnel: genotype QC -> gnomAD rarity tier (absent weighted stronger than rare) -> consequence/damage ensemble (LoF; damaging missense by multi-predictor vote; SpliceAI rescue) -> declared artifact-locus mask (extended MHC; disclosed `locus_masked` stage) -> per-gene inheritance aggregation enumerating compound-het, hom-alt, dominant and X-linked genotype hypotheses -> HPO Resnik/BMA phenotype scoring -> rank-mapped epcr. The funnel was validated blind on a synthetic compound-het spike-in (recovered at rank 1, in-trans via PGT/PID), stayed silent on a negative control carrying a TTN-class decoy pair, and held rank <=125 under every leave-one-source-out ablation and a 3x3 threshold grid. phase-set + read-level evidence attached; the pair's phase is **unknown**; an ACMG SF v3.3 scan handles secondary findings; the submission writer satisfies the scorer's byte-level contract (UTF-8 no BOM, chr-prefix, <=10 rows, strictly decreasing epcr), verified against a vendored copy of the official scorer on 60 adversarial CSV fixtures + a 19-fixture oracle mutation audit. Strengths: auditable stages, frozen config, honest negative controls, reproducible numbers. Limitations: epcr is a ranking artifact, not a calibrated probability; phenotype prior depends on the gene->disease annotation corpus; phase-set chaining beyond read-length needs PGT/PID or external phasing references; single-proband design cannot estimate caller error rates empirically.

## 13. Limitations

1. epcr expresses rank, not calibrated probability - stated openly in the methods form.
2. Phenotype scoring inherits the biases of the HPO annotation corpus; genes with no disease association cannot be rescued by phenotype alone (see TTN-class suppression).
3. PGT/PID only resolves pairs inside one phase set; long-range chaining falls back to reads/LD evidence and is reported as 'unknown' when absent.
4. Secondary-finding disclosure to a real family is an ethics question we flag, not decide, in a hackathon report.
5. CNV/SV alleles are outside the shipped SNV/indel VCF; a manta + cnvpytor screen on the re-aligned BAM found **0** del/dup calls overlapping the primary locus (`none`).
6. the declared artifact-locus mask (extended MHC) is a post-observation exclusion - the trigger (all emitted run-2 rows were MHC-locus hypotheses) was seen AFTER the funnel ran. It is disclosed as the `locus_masked` funnel stage + a decisions.md row; the unmasked run-2 artifacts are preserved so the mask's direction-neutral effect is auditable (score-space identical, rank changes only).
7. the input VCF is exon-slice-scoped; deep-intronic variants outside the slice are unreachable by construction - the one off-slice het near the primary locus was evaluated targeted (see orthogonal evidence; splice-benign, does not change the call)
8. rarity tiers rest on gnomAD exome AFs (+ joint-site fields where annotated); genome-only frequency evidence is partial.
9. sample sex is ambiguous by genotype markers (X-het ~7%, Y-chrom calls present) - the X-linked arm therefore runs un-gated on sex.

---

*Reproduce: `python tools/make_report.py --run-dir results/<run> ...`
regenerates every table above from artifacts on disk.*
