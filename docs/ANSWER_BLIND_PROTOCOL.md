# The Answer-Blind Protocol - a reusable template for N-of-1 genomic challenges

This document packages the methodology used in this repository as a
template any team can adopt when solving a variant-prioritization
challenge where the answer may be partially knowable in advance
(leaderboard forensics, prior participant publications, community
leaks). It is the difference between "we found the answer" and "we can
prove how we found it."

The core problem the protocol solves: **a correct answer with a
contaminated derivation is worth less than a slightly worse answer
with a clean one.** Panels, organizers, and reviewers cannot verify
your score - they can only verify your process. Make the process the
artifact.

## The five pillars

### 1. Decision freeze (before data arrives)

Every threshold, weight, filter, and emit rule is written to a
versioned config file and **committed before the patient data is
touched**. The freeze timestamp is in git; any later change is a diff
against it.

- Ours: `config/pipeline.yaml`, frozen before the gated dataset grant.
- Why: otherwise every parameter becomes a knob that can be tuned
  toward a known answer, and nothing you report can be trusted -
  including by yourself.
- Template: one YAML/JSON with every magic number in the pipeline,
  hashed into the run manifest (`run_summary.json` carries
  `config_hash`).

### 2. Leak firewall (posture, not pretense)

If the answer leaked - or is publicly inferable - say so. Do not
pretend you never saw it; define what the firewall *does* cover.

- **Allowed:** knowing the suspected answer exists; documenting where
  the leak came from (leaderboard forensics, a participant's public
  Space, community discussion).
- **Not allowed:** leaked values entering scoring code, config, or
  thresholds; using the leaked answer to choose parameters.
- **Required:** every post-freeze code/config change logged in a
  decisions ledger with rationale and alternatives rejected. If a fix
  changes the emitted artifact, say which numbers moved.

### 3. Negative controls (must stay silent)

Run the identical pipeline on a case that should produce *nothing* -
a different individual's genome, or the patient VCF with the answer
region masked. Zero emission is the expected result; anything else
means the funnel fires on noise.

- Ours: `results/t1_control/` (0 emitted is the gate), plus an
  artifact-locus mask applied genome-wide so technical-artifact genes
  cannot inflate the ranking.
- Template: at least one control case in CI; "emitted = 0" asserted
  by an automated gate, not eyeballed.

### 4. Positive controls (must recover)

Spike a *known* pair into a clean background and confirm the pipeline
recovers it at rank 1 - separately for each evidence layer you claim.
If you add a stage (masking, phenotype scoring, phasing), re-run the
spike.

- Ours: `results/t1_spike/` (synthetic compound-het recovers rank 1),
  plus a real ClinVar pair on an HG002 background.
- Template: spike VCFs contain no patient data by construction, so
  they are safe to commit, share, and demo publicly.

### 5. Oracle verification of the deliverable (before upload)

Copy the official scorer into your repo (or reimplement it against
its own spec) and score your exact submission bytes locally. Then
attack it: a mutation battery that flips each field, swaps delimiters,
changes contig conventions - every mutation should score 0. If a
mangled CSV scores >0, you found a scorer quirk *before* the server
did.

- Ours: vendored `hackathon-app/evaluation.py`, a 19-fixture mutation
  audit + 60-fixture CSV-contract battery; the local score equalled
  the official server score (100.0 / 1.000) on first upload.
- Byte details that actually bit people: `chr`-prefixed contigs vs
  bare numbers, UTF-8 no-BOM, LF endings, exact column names,
  `epcr in (0,1]`, `proband_id` literal.

## Supporting practices

| Practice | Ours | Why |
|----------|------|-----|
| Decisions ledger | `docs/decisions.md` - one row per non-obvious choice: rationale + alternatives rejected | Post-hoc questions are answered by the log, not memory |
| Retention doctrine | `data/RETENTION.md` + `results/RETENTION.md` - KEEP/DELETE tag on every artifact before deletion day | Prevents "keep everything" drift and accidental patient-data persistence |
| Runtime/cost log | `docs/runtime_log.md` - wall-clock + $ per stage | Reproducibility reviewers ask; have it |
| Artifact-derived report | `tools/make_report.py` generates the report from run artifacts - no hand-typed statistics | A number in the report either traces to a file or does not get written |
| Honest fragility | ablation matrix published including the drops that kill the call | Overclaiming is the most common judge-visible failure |
| Aggregate-only sharing | named-variant findings + counts in docs; genotype-scale dumps never leave the compute volume | Compliance + privacy in one rule |

## Adoption checklist for a new team

- [ ] Write the config; commit it; *then* request the data
- [ ] Document the leak posture (what you know, where from, what the
      firewall covers) before the first run
- [ ] Build the scorer oracle + mutation battery before building the
      pipeline - it defines the contract everything else satisfies
- [ ] Wire the negative control into CI so silence is asserted, not
      remembered
- [ ] Log every post-freeze change the day it happens
- [ ] Generate the report from artifacts; ban hand-typed statistics
- [ ] Dry-run the scorer on the exact upload bytes before spending a
      submission slot
- [ ] Tag every artifact KEEP/DELETE on the day it is created

---

*This work was made possible through the Hackathon, organized by Sage
Bionetworks in partnership with the MVA Society, Hugging Face, and
BEACON (The Benchmarking, Evaluation, and Assessment Consortium for
Science), with prize sponsorship from AWS and Anthropic. We are deeply
grateful to the child and their family who generously contributed their
data and their story to advance research into this rare disease. We
acknowledge their trust in making this Hackathon possible.*
