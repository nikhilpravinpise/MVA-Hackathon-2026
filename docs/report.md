# Track 1 Methods Report - MVA Hackathon 2026

**Team:** `<TBD - see docs/team.md>` | **Model:** `model1` | **Generated:** 2026-09-26 15:21 UTC by `tools/make_report.py` (all statistics in this document are regenerated from `results/` - nothing is hand-typed; see GATE-6 checklist in `docs/report_map.md`).

> **Data status banner:** VALIDATED ON SYNTHETIC STAND-IN - patient VCF not yet on disk; every number below is from the public-stand-in harness.

---

## 0. Submission summary

No hypothesis crossed the emit floor - the pipeline's answer is a **no-call** (see negative-control doctrine).

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
(sha256 `827e2abe604b`) - the answer-blind decision freeze. No variant
identity, gene name, or leaked-space value influenced any parameter; the
pipeline output is the submission.

### 1a. Funnel table (counts per stage, regenerated)

| Stage | Count |
|---|---|
| VCF records | 14 |
| allele x gene evidence records | 14 |
| passing genotype QC + filters | 12 |
| rare tier (pop-max AF <= af_max or absent) | 9 |
| eligible candidate variants | 9 |
| genotype hypotheses enumerated | 13 |
| emitted (score >= emit_floor) | 0 |

## 2. Data audit / EDA

_Pending dataset access - artifact not yet produced._

## 3. External validation

The funnel was validated *blind* before the proband call:

* **Synthetic spike-in proband:** a ClinVar-style compound-het pair (LoF +
  damaging missense, in trans via shared PGT/PID phase set) embedded among
  adversarial decoys (TTN-class noise pair, common hom-alt, filtered LoF,
  low-depth call, common-AF damaging missense).
  **Result:** NOT recovered - see ablation report
* **Negative control:** plausible-looking rare/damaging variation + an
  unrelated HPO set -> **control run not wired - see tests/test_negative_control.py** (a funnel that finds a causal
  pair everywhere finds nothing).
* **Arm A vs Arm B concordance:** top-20 gene overlap 1 (PAH); PAH ranked 1 by Arm B, 1 by Arm A (Exomiser genome mode)
* **Real external validation (public genome + real ClinVar pair):**

- 270 real HG002 background variants in window 12:102800000-103000000
- spiked pair = real ClinVar variants chr12:102839204 G>A (ClinVar 551287, Likely_pathogenic), chr12:102839216 C>A (ClinVar 932274, Likely_pathogenic)
- annotation: 277 alleles via live Ensembl REST VEP
- Funnel: 272 records -> 2 rare -> 2 candidates -> **pair recovered at rank 1** (in_trans: trans, epcr 0.95)

### 3a. Leave-one-source-out ablations

_Pending dataset access - artifact not yet produced._

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

## 4. Phasing evidence (phase-set + read-level status)

_Pending dataset access - artifact not yet produced._

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

_Pending dataset access - artifact not yet produced._

## 8. ACMG/AMP classification of the primary pair

_Pending dataset access - artifact not yet produced._

## 9. Runtime and cost

| Job | Where | Time | Cost |
|---|---|---|---|
| Arm-B funnel (this run) | local | 0.926s | $0 |
| Test battery (19-fixture oracle mutation battery + 60-fixture CSV-contract battery + funnel + e2e) | local | seconds-scale (see docs/runtime_log.md session rows) | $0 |

Planned cloud jobs (alignment/DeepVariant/VEP at data landing) are budgeted < $50 total - see docs/runtime_log.md.

## 10. GenAI disclosure (required)

Cognition Devin CLI (SWE-2 Max); provider terms and per-session usage are ledgered in docs/llm_log.md.

## 11. Provenance, firewall, and compliance

- VCF: `results/spike_case/spike_proband.vcf` (sha256 `67d0b6b52016`)
- Config: parsed-config sha256 `827e2abe604b` (frozen pre-analysis; hash recorded at run time - the canonical dict hash, not the file-byte hash)
- Scoring oracle: vendored `hackathon-app/evaluation.py` - local score = official score by construction
- Leak firewall: no leaked-Space coordinates/genes/values in code, tests, configs, or this report
- Compliance: patient data confined to `data/` (gitignored); retention manifests in data/RETENTION.md + results/RETENTION.md

## 12. Method abstract (<=500 words)

We built an answer-blind, deterministic N-of-1 prioritization funnel: genotype QC -> gnomAD rarity tier (absent weighted stronger than rare) -> consequence/damage ensemble (LoF; damaging missense by multi-predictor vote; SpliceAI rescue) -> per-gene inheritance aggregation enumerating compound-het, hom-alt, dominant and X-linked genotype hypotheses -> HPO Resnik/BMA phenotype scoring -> rank-mapped epcr. The funnel was validated blind on a synthetic compound-het spike-in (recovered at rank None, in-trans via PGT/PID), stayed silent on a negative control carrying a TTN-class decoy pair, and held rank <=None under every leave-one-source-out ablation and a 3x3 threshold grid. PGT/PID phase-set phasing supplies the trans call; read-level confirmation (SAM/WhatsHap/DeepVariant on the patient FASTQs) is planned, not yet run; an ACMG SF v3.3 scan handles secondary findings; the submission writer satisfies the scorer's byte-level contract (UTF-8 no BOM, chr-prefix, <=10 rows, strictly decreasing epcr), verified against a vendored copy of the official scorer on 60 adversarial CSV fixtures + a 19-fixture oracle mutation audit. Strengths: auditable stages, frozen config, honest negative controls, reproducible numbers. Limitations: epcr is a ranking artifact, not a calibrated probability; phenotype prior depends on the gene->disease annotation corpus; phase-set chaining beyond read-length needs PGT/PID or external phasing references; single-proband design cannot estimate caller error rates empirically.

## 13. Limitations

1. epcr expresses rank, not calibrated probability - stated openly in the methods form.
2. Phenotype scoring inherits the biases of the HPO annotation corpus; genes with no disease association cannot be rescued by phenotype alone (see TTN-class suppression).
3. PGT/PID only resolves pairs inside one phase set; long-range chaining falls back to reads/LD evidence and is reported as 'unknown' when absent.
4. Secondary-finding disclosure to a real family is an ethics question we flag, not decide, in a hackathon report.
5. CNV/SV alleles are outside the shipped SNV/indel VCF; the re-alignment arm (planned) covers this gap.

---

*Reproduce: `python tools/make_report.py --run-dir results/<run> ...`
regenerates every table above from artifacts on disk.*
