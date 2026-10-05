# Track 1 Methods Report - MVA Hackathon 2026

**Team:** `{{TEAM_NAME}}` | **Model:** `model{{MODEL_N}}` | **Generated:** {{GENERATED_AT}} by `tools/make_report.py` (all statistics in this document are regenerated from `results/` - nothing is hand-typed; see GATE-6 checklist in `docs/report_map.md`).

> **Data status banner:** {{DATA_STATUS}}

---

## 0. Submission summary

{{SUBMISSION_SUMMARY}}

### 0a. Prior submission iteration

{{PRIOR_CSV}}

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
(sha256 `{{CONFIG_SHA}}`) - the decision freeze. No variant identity, gene
name, or leaked-space value enters any scoring parameter; the pipeline
output is the submission. Two post-freeze config additions were made
after the first run and are disclosed rather than hidden: the
extended-MHC artifact-locus mask and the BUB1B LoF-mechanism allowlist.
One post-freeze code fix also landed: the VEP-indel CSQ allele matcher
(`src/vcf.py::vep_allele`, limitation 10), under which the funnel was
re-run - every funnel/ablation number below is from the fixed run. Each
change is logged in `docs/decisions.md` and described in section 11.

### 1a. Funnel table (counts per stage, regenerated)

{{FUNNEL_TABLE}}

{{FIG_FUNNEL}}

### 1b. Rank and epcr

{{RANK_NOTE}}

## 2. Data audit / EDA

{{EDA_SECTION}}

### 2a. Coverage profile (mosdepth)

{{MOSDEPTH_SECTION}}

{{FIG_COVERAGE}}

### 2b. FASTQ QC (fastp -> run_fastqc aggregate)

{{FASTQ_QC_SECTION}}

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
* **Arm A vs Arm B concordance:** {{ARM_CONCORDANCE}}
* **Real external validation (public genome + real ClinVar pair):**

{{REAL_SPIKE_SECTION}}

### 3a. Leave-one-source-out ablations

{{ABLATION_TABLE}}

{{FIG_ABLATION}}

### 3b. Threshold sensitivity grid

{{SENSITIVITY_TABLE}}

## 4. Phasing evidence (phase-set + read-level status)

{{PHASING_SECTION}}

### 4a. Orthogonal evidence arms

{{ORTHOGONAL_SECTION}}

{{FIG_PILEUP}}

{{FIG_ALLELE_BALANCE}}

## 5. Automated vs manual review

The submission CSV is the **automated output** of the pipeline
(`src/submit.py` builds bytes that are oracle-validated locally before any
upload), with **one disclosed post-observation manual curation step**: the
extended-MHC artifact-locus mask. The trigger was human review - every
emitted run-2 row was an HLA-DRB1/MHC hypothesis, a well-known artifact
class, and the motivation honestly included the score impact
(decisions.md). The mask adds no evidence and raises no *score*, but it
does change *ranks* (it removed 6,353 artifact-locus candidates, so the
BUB1B pair's rank - and therefore its epcr - improved vs the unmasked
run-2 CSV shown in section 0a). We call it "removal of a declared
artifact class", not "direction-neutral". Separately, downstream manual
review was limited to: (a) reading the top hypothesis' evidence fields,
(b) confirming the phasing report, (c) the secondary-findings disclosure
decision described in section 7. No variant was added, removed, or
re-ordered inside the remaining ranked table by hand.

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

### 8a. Primary finding interpretation

{{FINDING_INTERPRETATION}}

## 9. Runtime and cost

{{RUNTIME_SECTION}}

## 10. GenAI disclosure (required)

{{GENAI_LINE}}

## 11. Provenance, firewall, and compliance

{{PROVENANCE_SECTION}}

## 12. Method abstract (<=500 words)

{{ABSTRACT}}

## 12a. Methods form Q&A

{{FORM_ANSWERS}}

## 13. Limitations

{{LIMITATIONS}}

## Acknowledgement

*This work was made possible through the Hackathon, organized by Sage
Bionetworks in partnership with the MVA Society, Hugging Face, and
BEACON (The Benchmarking, Evaluation, and Assessment Consortium for
Science), with prize sponsorship from AWS and Anthropic. We are deeply
grateful to the child and their family who generously contributed their
data and their story to advance research into this rare disease. We
acknowledge their trust in making this Hackathon possible.*

---

*Reproduce: `python tools/make_report.py --run-dir results/<run> ...`
regenerates every table above from artifacts on disk.*
