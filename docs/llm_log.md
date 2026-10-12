# GenAI / LLM use disclosure log

Required by plan.md section 2.3 (compliance doctrine): commercial-tier LLM
use only, with the plan's data-handling terms verified and recorded
honestly, plus a running log so the methods-xlsx required GenAI-disclosure
question writes itself (question marked "(required)" in
`methods_description_form.xlsx`; organizer resolution in discussion #21 -
consumer tier acceptable only if terms are verifiable, API/commercial
recommended otherwise).

Rule: **no patient data, no proband genotypes, and no variant-level detail
ever enters an LLM prompt** (deletion doctrine: prompts/logs containing
pasted variant blocks are DELETE-class artifacts). Every session that uses a
generative tool gets one row.

Coverage note: this ledger begins 2026-09-26 (the audit/verification
sessions). Earlier repo artifacts dated 2026-09-15/17/18 (deep-dive rounds,
plan status dates) pre-date the ledger - they were produced under the same
no-patient-data rule but are not itemized here; if a session is added for
that work it will cite the same rule.

| Date | Provider / product | Plan / tier | Model | Data-handling terms | What data was exposed |
|---|---|---|---|---|---|
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - no patient data on disk this session; all fixtures synthetic; public reference corpora (HPO) download + repo code/docs only |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - audit/verification loop session: code review, edge-case tests, doc fixes; repo code/docs + public corpora only, zero patient-derived content |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - audit round 3: scorer-parity subprocess, exomiser YAML schema, run_track1/vcf.c edge fixes, report-literal derivation; repo code/docs + public corpora only, zero patient-derived content |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - audit round 4: coverage-driven branch tests, scoring-math fixes (mean damage, singleton floor, PM3/PVS1 corrections, gnomAD-coverage flag), dead-config wiring; repo code/docs + public corpora only |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - audit round 5: adversarial wrong-answer hunt (1 subagent) + own probes: ablation-tier drift fix, rare-count fix, gene-split dedup fix, AF cross-transcript merge, UCSC contig mapping, CSQ separator guards; repo code/docs + public corpora only |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - Arm A execution: Exomiser 14.0.0 + 2406 bundles fetched (public Monarch CDN), analysis YAML rewritten to shipped schema, real-spike + synthetic runs, compare_arms concordance tooling; repo code + public data only, zero patient-derived content |
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - audit round 6: fresh-eyes hostile audit of session-2 new code (fetch_big, compare_arms, normalize_contigs, run_exomiser, run_track1 + make_report new blocks); 6 bugs fixed + 15 regression pins; repo code/docs + public corpora only |
| 2026-10-01 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - patient pipeline ran locally: HPO extraction (8 terms), EDA aggregates (5.01M records, Ti/Tv 1.94), funnel 0-emit on unannotated VCF, Exomiser genome run. Two named variant records (BUB1B p.Leu737*/p.Asn1002Lys) + QC genotype strings appeared in tool output = named-variant findings per retention 2.3, NOT genotype-scale dumps; no proband VCF/BAM blocks pasted |
| 2026-10-02 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - annotation-stack assembly (public CADD/AlphaMissense/SpliceAI/REVEL/ClinVar downloads, gnomAD slicing), fetch_big bug fix, FASTQ integrity checks. No patient-derived content in prompts; public annotation engineering only |
| 2026-10-03 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - Modal migration (tools/modal_app.py, volume setup, remote VEP/realign/funnel), data_audit doc, retention manifests. Named-variant findings (BUB1B pair coordinates, phasing counts) appeared in tool output per retention 2.3; no proband VCF/BAM blocks pasted; patient compute ran on Modal volume, not in prompts |
| 2026-10-04 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - full-repo audit (~20 fixes: sys import, dead code, gnomAD joint-AF bug, atomic shell outputs, gitignore containment), Phase-0 hygiene (stale-pull archive, ~25 GB reclaim, colltmp volume cleanup), artifact_loci feature (src/loci.py + pipeline stage + 33 tests), decisions.md post-freeze rows. Named-variant findings scale only; zero proband genotype blocks in prompts |
| 2026-10-02/03 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - annotation-stack assembly + Modal migration + repo audit: public annotation sources (CADD/AlphaMissense/SpliceAI/REVEL/ClinVar/gnomAD) fetched and reshaped; named BUB1B locus coordinates (chr15:40209701/40220612) referenced for phasing/orchestration specs per retention 2.3; no proband VCF/BAM blocks pasted |
| 2026-10-04 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - masked Modal rerun + evidence fleet execution (run_main/ablations/merge/phasing/mosdepth/fastp/deepvariant/cnv/slim on track1_final), acceptance-gate verification, artifact pulls, mosdepth-summary bug fix, nonpreemptible gnomad retry, docs sync (status/runtime_log/decisions/RETENTION). Aggregate findings (funnel counts, ablation ranks, coverage stats, named BUB1B coordinates) in tool output per retention 2.3; zero proband VCF/BAM/genotype blocks in prompts - all patient-scale compute stayed on the Modal volume |

| 2026-10-04 | Cognition Devin CLI | Devin Pro (operator-stated plan) | SWE-2 Max | Verified published terms (docs.devin.ai/admin/security): Pro default = Cognition MAY use customer data for model training unless the account opts out via Data Controls (opt-out also enables zero data retention with model providers); account opt-out state NOT asserted - default stated | FINDINGS-SCALE ONLY - audit-implementation session: indel CSQ allele-matching fix (src/vcf.py csq_for_alt/vep_allele + tests), report truthfulness/depth pass (tools/make_report.py + template), report-patient Make target, hygiene fixes, Modal indel-fix rerun orchestration (track1_final_indelfix). Named BUB1B coordinates/HGVS in tool output per retention 2.3; zero proband VCF/BAM/genotype blocks in prompts |
| 2026-10-04 | Cognition Devin CLI | Devin Pro (operator-stated plan) | SWE-2 Max | same verified-terms wording as row above | FINDINGS-SCALE ONLY - audit-implementation continuation: indel-fix run completion (gnomad ablation ~3.2h + merge + slim), artifact pull, docs/report.md regeneration from track1_final_indelfix (rank 7, epcr 0.0749), submission CSV + nikhilpise_track1_report.md staging, local-oracle re-verification (100.0/1.000/rank 1), close-out docs (status/runtime_log/RETENTION/report_map/rubric/checklist), commits 8236d1f + 0e864d9 pushed to origin/main. Named-variant findings scale only; zero proband VCF/BAM/genotype blocks in prompts |

## Guidance per tier (plan.md 2.3)

- **Allowed:** commercial/API products with verifiable data-handling terms
  for any code/docs/methods work; public-data pipelines.
- **Devin Pro terms (verified 2026-10-04, docs.devin.ai/admin/security):**
  by default Cognition may use customer data for model training; a paid
  account can opt out on the Data Controls settings page, after which data
  is not used for training and zero data retention is enabled with model
  providers. **Operator confirmed 2026-10-12: the Data Controls training
  opt-out was ON for the account across all sessions** (rows dated before
  2026-10-12 state the default because the opt-out was not yet asserted in
  writing; the 2026-10-12 confirmation supersedes that wording). The
  no-patient-data-in-prompts rule remains the load-bearing control.
- **Claude Code (Anthropic), Claude Pro/Max consumer plan:** operator
  confirmed 2026-10-12 that model-training opt-out is ON and no feedback
  (thumbs up/down) was ever given, matching the organizers' 2026-09-28
  guidance (discussion #2). Used in the post-submission close-out/audit
  phase.
- **Gate:** before ANY prompt could touch patient-derived data (should never
  happen by design), the specific plan's no-training clause must be verified
  and cited here.
- **Prohibited:** pasting proband VCF/BAM content, genotypes, or variant
  blocks into any prompt; consumer tiers whose terms cannot be verified.
| 2026-10-04 | Cognition Devin CLI | Devin Pro (operator-stated plan) | SWE-2 Max | same verified-terms wording as row above | ZERO patient data - compliance/community docs only: verbatim HF gated-access attestation archived from public API cardData (docs/attestation_hf_gated_access.md), family-facing MVA explainer (docs/FAMILY_EXPLAINER.md), reusable answer-blind protocol template (docs/ANSWER_BLIND_PROTOCOL.md), deletion-runbook mailbox reconciliation, status.md blocker 3 closed. No patient data touched; artifacts are public-source text + repo methodology |
| 2026-10-05 | Cognition Devin CLI | Devin Pro (operator-stated plan) | SWE-2 Max | same verified-terms wording as above | Post-submission hardening tooling only: tools/make_figures.py (SVG+ASCII figures from results/ artifacts), report_template.md/make_report.py embeds, tools/make_arm_a_csv.py + submissions/ candidates, docs sync. No proband VCF/BAM content in prompts. Incidental disclosure, recorded per the ledger's own doctrine: during figure-tool inspection, ~20 lines of results/track1_patient_modal/realign/region.sam read records (BUB1B-locus 150-bp reads) were echoed to the terminal/context; locus-scoped, no clinical identifiers; the file itself never left disk |
| 2026-10-05 | Cognition Devin CLI | Devin Pro (operator-stated plan) | SWE-2 Max | same verified-terms wording as above | Freshness/close-out tooling: tools/audit_freshness.py + tests/test_freshness.py pins, public_release_check.py + check_discussions.py (runtime-derived token scans - no identifiers in source), resolution banners on 4 dated docs, track1_closeout.md, deletion_email_draft.md, sweep fixes (README/checklist/RETENTION/plan.md). No proband VCF/BAM content in prompts; release-checker previews are sha-truncated by design |
| 2026-10-12 | Anthropic Claude Code | Claude Pro/Max consumer plan (operator-stated; training opt-out ON, no feedback given) | Claude Sonnet 5.5 | Organizer guidance 2026-09-28 (discussion #2): consumer tier permitted with training opt-out + no feedback | FINDINGS-SCALE ONLY - Track-1 final audit: freshness/test/discussion checks, live leaderboard read-back, compliance review. Individual genotype/QC record strings for the two causal sites and a few other VCF records appeared in tool output during a PGT/PID verification (disclosed in report section 10); no bulk genotype blocks, BAM or FASTQ content |
| 2026-10-12 | Cognition Devin CLI | Devin Pro (operator-confirmed Data Controls training opt-out ON) | SWE-2 Max | Opt-out ON per operator 2026-10-12: no training, zero data retention | Supersedes the "opt-out not asserted" wording on all earlier Devin rows; no new session |
| 2026-10-12 | Cognition Devin CLI (3 headless agents) | Devin Pro (operator-confirmed Data Controls training opt-out ON) | SWE-2 Max | Opt-out ON per operator 2026-10-12: no training, zero data retention | FINDINGS-SCALE ONLY - three read-only adversarial audit agents (raw evidence, leakage/logic, report truth) over existing artifacts; instructed to print aggregates only. Agent A printed the genotype/QC record lines of the two causal sites only (disclosed). No proband bulk genotype blocks, BAM or FASTQ content; public gene/variant lookups only |
| 2026-10-12 | Cognition Devin CLI (1 headless agent) | Devin Pro (operator-confirmed Data Controls training opt-out ON) | SWE-2 Max | Opt-out ON per operator 2026-10-12: no training, zero data retention | ZERO patient data - code/doc hygiene only (form-answer key matching in make_report.py, hpoa column comment, retention note, ledger corrections, data_audit population count); agent was forbidden from opening data/, results/ or env/ content |
| 2026-10-12 | Anthropic Claude Code (lead + 5 parallel subagents, Track 2 lanes L1-L5) | Claude Pro/Max consumer plan (operator-stated; training opt-out ON, no feedback given) | Claude Opus 5.5 | Organizer guidance 2026-09-28 (discussion #2): consumer tier permitted with training opt-out + no feedback | NAMED-VARIANT ONLY - Track 2 build: public drug/target/literature APIs (Open Targets, ChEMBL, DGIdb, STRING, openFDA, SigCom LINCS, NCBI E-utilities, Crossref, UniProt, Ensembl, gnomAD, AlphaFold DB, DepMap/PRISM). Only the two published BUB1B variants and the 8 published HPO terms entered prompts; agents were forbidden from opening data/, results/ or env/. Devin SWE-2 Max headless agents were requested by the operator but the launch was blocked by the harness permission classifier, so the lanes ran as Claude subagents |
