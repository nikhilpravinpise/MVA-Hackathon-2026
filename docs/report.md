# Track 1 Methods Report - MVA Hackathon 2026

**Team:** `<TBD - see docs/team.md>` · **Model:** `model1` · **Generated:** 2026-09-26 09:32 UTC by `tools/make_report.py` (all statistics in this document are regenerated from `results/` - nothing is hand-typed; see GATE-6 checklist in `docs/report_map.md`).

> **Data status banner:** VALIDATED ON SYNTHETIC STAND-IN - patient VCF not yet on disk; every number below is from the public-stand-in harness.

---

## 0. Submission summary

- **Primary call:** `SPIKEA` (compound_het) - chr7:1000000 A>T + chr7:1004000 G>C
- Score 1.000 (damage 1.00 / phenotype 1.00 / inheritance 1.0), epcr 0.95, phasing: **trans**
- Emitted hypotheses: 3 of 13 ranked
- External-validation check: recovered pair == MATCHES the spiked truth

## 1. Approach in detail

A genome-wide, case-agnostic prioritization funnel for an N-of-1 recessive
diagnosis - an Exomiser-class design implemented as a transparent,
deterministic, auditable ranking pipeline rather than a trained black box.
Two independent arms were specified a priori:

* **Arm A (standard):** Exomiser genome mode on the annotated VCF + HPO term
  set (configuration + runner in `tools/run_exomiser.py`).
* **Arm B (custom funnel, this report):** six deterministic stages:

```
annotated VCF (VEP CSQ)
  -> [1] genotype QC + PASS filter           (DP/GQ/VAF windows)
  -> [2] rarity tier                          (gnomAD pop-max AF; absent > rare)
  -> [3] consequence/damage tier              (LoF | damaging-missense ensemble |
                                               splice-altering | other)
  -> [4] inheritance aggregation per gene     (compound-het, hom-alt,
                                               dominant-het, X-linked)
  -> [5] phenotype scoring                    (HPO Resnik/BMA semantic
                                               similarity + gene->disease prior)
  -> [6] rank -> epcr                         (ranking artifact, not a
                                               calibrated probability)
```

Every threshold is frozen pre-analysis in `config/pipeline.yaml`
(sha256 `1f6b00f2fdde`) - the answer-blind decision freeze. No variant
identity, gene name, or leaked-space value influenced any parameter; the
pipeline output is the submission.

### 1a. Funnel table (counts per stage, regenerated)

| Stage | Count |
|---|---|
| VCF records | 14 |
| allele x gene evidence records | 14 |
| passing genotype QC + filters | 12 |
| rare tier (pop-max AF <= af_max or absent) | 11 |
| eligible candidate variants | 9 |
| genotype hypotheses enumerated | 13 |
| emitted (score >= emit_floor) | 3 |

## 2. Data audit / EDA

- Records: 14 (SNV 14, indel 0), Ti/Tv 1.0
- Contigs carry 'chr' prefix: False; PGT/PID present: True/True
- Caller: `##source=synth-v1`; reference: `##reference=GRCh38_no_alt_analysis_set`
- INFO AF semantics: within_sample_fraction
- CSQ annotation fields: 51

## 3. External validation

The funnel was validated *blind* before the proband call:

* **Synthetic spike-in proband:** a ClinVar-style compound-het pair (LoF +
  damaging missense, in trans via shared PGT/PID phase set) embedded among
  adversarial decoys (TTN-class noise pair, common hom-alt, filtered LoF,
  low-depth call, common-AF damaging missense).
  **Result:** true pair recovered at **rank 1** (score 1.000, in-trans: trans)
* **Negative control:** plausible-looking rare/damaging variation + an
  unrelated HPO set -> **no hypothesis emitted (0 above emit floor) - expected behaviour verified** (a funnel that finds a causal
  pair everywhere finds nothing).
* **Real external validation (public genome + real ClinVar pair):**
  _Pending dataset access - artifact not yet produced._

### 3a. Leave-one-source-out ablations

| Dropped source | Pair rank | Emitted |
|---|---|---|
| clinvar | 1 | 3 |
| damage_predictors | 1 | 2 |
| gnomad | 2 | 5 |
| hpo | 1 | 0 |
| phasing | 1 | 3 |

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

## 4. Phasing and read-level in-trans evidence

| Evidence | Mechanism | Result |
|---|---|---|
| PGT/PID read-backed phasing | pgt_pid_same_set | trans |

Agreement: **trans**

## 5. Automated vs manual review

The submission CSV is the **automated output** of the pipeline
(`src/submit.py` builds bytes that are oracle-validated locally before any
upload). Downstream manual review was limited to: (a) reading the top
hypothesis' evidence fields, (b) confirming the phasing report, (c) the
secondary-findings disclosure decision described in section 7. No variant
was added, removed, or re-ordered by hand.

## 6. Data sources

gnomAD v4.1 AFs, ClinVar, CADD, AlphaMissense, REVEL/dbNSFP 5.3.1, SpliceAI (precomputed), LOEUF, phyloP, HPO (hp.obo + phenotype.hpoa + genes_to_phenotype), Ensembl VEP 116 annotation, ACMG SF v3.3. GIAB HG002 as public stand-in genome.

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
| 7:1000000:A>T | PVS1, PM2 | Pathogenic |
| 7:1004000:G>C | PM2, PM3 | VUS |

Pair-level: PP4

Combined call: **Pathogenic** (15 pts - ACMG/AMP Richards2015 subset + Tavtigian2018 points)

## 9. Runtime and cost

_Pending dataset access - artifact not yet produced._

## 10. GenAI disclosure (required)

Anthropic API / Cognition Devin CLI (SWE-2 Max), commercial terms, no training on customer content - see docs/llm_log.md for the per-session ledger.

## 11. Provenance, firewall, and compliance

- VCF: `results\spike_case\spike_proband.vcf` (sha-tracked)
- Config: `config/pipeline.yaml` sha256 `1f6b00f2fdde` (frozen pre-analysis)
- Scoring oracle: vendored `hackathon-app/evaluation.py` - local score = official score by construction
- Leak firewall: no leaked-Space coordinates/genes/values in code, tests, configs, or this report
- Compliance: patient data confined to `data/` (gitignored); retention manifests in data/RETENTION.md + results/RETENTION.md

## 12. Method abstract (<=500 words)

We built an answer-blind, deterministic N-of-1 prioritization funnel: genotype QC -> gnomAD rarity tier (absent weighted stronger than rare) -> consequence/damage ensemble (LoF; damaging missense by multi-predictor vote; SpliceAI rescue) -> per-gene inheritance aggregation enumerating compound-het, hom-alt, dominant and X-linked genotype hypotheses -> HPO Resnik/BMA phenotype scoring -> rank-mapped epcr. The funnel was validated blind on a synthetic compound-het spike-in (recovered at rank 1, in-trans via PGT/PID), stayed silent on a negative control carrying a TTN-class decoy pair, and held rank <=5 under every leave-one-source-out ablation and a 3x3 threshold grid. PGT/PID read-backed phasing plus planned re-alignment provide independent in-trans evidence; an ACMG SF v3.3 scan handles secondary findings; the submission writer satisfies the scorer's byte-level contract (UTF-8 no BOM, chr-prefix, <=10 rows, strictly decreasing epcr), verified against a vendored copy of the official scorer on 57+ adversarial fixtures including a mutation audit. Strengths: auditable stages, frozen config, honest negative controls, reproducible numbers. Limitations: epcr is a ranking artifact, not a calibrated probability; phenotype prior depends on the gene->disease annotation corpus; phase-set chaining beyond read-length needs PGT/PID or external phasing references; single-proband design cannot estimate caller error rates empirically.

## 13. Limitations

1. epcr expresses rank, not calibrated probability - stated openly in the methods form.
2. Phenotype scoring inherits the biases of the HPO annotation corpus; genes with no disease association cannot be rescued by phenotype alone (see TTN-class suppression).
3. PGT/PID only resolves pairs inside one phase set; long-range chaining falls back to reads/LD evidence and is reported as 'unknown' when absent.
4. Secondary-finding disclosure to a real family is an ethics question we flag, not decide, in a hackathon report.
5. CNV/SV alleles are outside the shipped SNV/indel VCF; the re-alignment arm (planned) covers this gap.

---

*Reproduce: `python tools/make_report.py --run-dir results/<run> ...`
regenerates every table above from artifacts on disk.*
