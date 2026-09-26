# Track 1 Methods Report - MVA Hackathon 2026

**Team:** `{{TEAM_NAME}}` · **Model:** `model{{MODEL_N}}` · **Generated:** {{GENERATED_AT}} by `tools/make_report.py` (all statistics in this document are regenerated from `results/` - nothing is hand-typed; see GATE-6 checklist in `docs/report_map.md`).

> **Data status banner:** {{DATA_STATUS}}

---

## 0. Submission summary

{{SUBMISSION_SUMMARY}}

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
(sha256 `{{CONFIG_SHA}}`) - the answer-blind decision freeze. No variant
identity, gene name, or leaked-space value influenced any parameter; the
pipeline output is the submission.

### 1a. Funnel table (counts per stage, regenerated)

{{FUNNEL_TABLE}}

## 2. Data audit / EDA

{{EDA_SECTION}}

## 3. External validation

The funnel was validated *blind* before the proband call:

* **Synthetic spike-in proband:** a ClinVar-style compound-het pair (LoF +
  damaging missense, in trans via shared PGT/PID phase set) embedded among
  adversarial decoys (TTN-class noise pair, common hom-alt, filtered LoF,
  low-depth call, common-AF damaging missense).
  **Result:** {{SPIKE_RESULT}}
* **Negative control:** plausible-looking rare/damaging variation + an
  unrelated HPO set -> **{{CONTROL_RESULT}}** (a funnel that finds a causal
  pair everywhere finds nothing).
* **Real external validation (public genome + real ClinVar pair):**
  {{REAL_SPIKE_SECTION}}

### 3a. Leave-one-source-out ablations

{{ABLATION_TABLE}}

### 3b. Threshold sensitivity grid

{{SENSITIVITY_TABLE}}

## 4. Phasing and read-level in-trans evidence

{{PHASING_SECTION}}

## 5. Automated vs manual review

The submission CSV is the **automated output** of the pipeline
(`src/submit.py` builds bytes that are oracle-validated locally before any
upload). Downstream manual review was limited to: (a) reading the top
hypothesis' evidence fields, (b) confirming the phasing report, (c) the
secondary-findings disclosure decision described in section 7. No variant
was added, removed, or re-ordered by hand.

## 6. Data sources

{{DATA_SOURCES}}

No proprietary data was used.

## 7. Secondary / incidental findings

Full written position: `docs/disclosure_position.md`. Summary: report
medically actionable findings (ACMG SF v3.3, 84 genes) with an evidence
basis per row; describe evidence, never diagnose; no AR carrier-state rows;
the disclosure decision itself belongs to clinicians, not to a pipeline -
and we say so openly rather than stay silent.

{{SF_SECTION}}

## 8. ACMG/AMP classification of the primary pair

{{ACMG_SECTION}}

## 9. Runtime and cost

{{RUNTIME_SECTION}}

## 10. GenAI disclosure (required)

{{GENAI_LINE}}

## 11. Provenance, firewall, and compliance

{{PROVENANCE_SECTION}}

## 12. Method abstract (<=500 words)

{{ABSTRACT}}

## 13. Limitations

{{LIMITATIONS}}

---

*Reproduce: `python tools/make_report.py --run-dir results/<run> ...`
regenerates every table above from artifacts on disk.*
