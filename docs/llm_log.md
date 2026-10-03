# GenAI / LLM use disclosure log

Required by plan.md section 2.3 (compliance doctrine): commercial/API-tier
LLM use only, no-training terms, with a running log so the methods-xlsx
required GenAI-disclosure question writes itself (question marked
"(required)" in `methods_description_form.xlsx`; organizer resolution in
discussion #21 - consumer tier acceptable only if terms are verifiable,
API/commercial recommended otherwise).

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
| 2026-10-02/03 | Cognition Devin CLI | Commercial product | SWE-2 Max | No-training clause check required for patient-derived prompts | FINDINGS-SCALE ONLY - annotation-stack assembly + Modal migration + repo audit: public annotation sources (CADD/AlphaMissense/SpliceAI/REVEL/ClinVar/gnomAD) fetched and reshaped; named BUB1B locus coordinates (chr15:40209701/40220612) referenced for phasing/orchestration specs per retention 2.3; no proband VCF/BAM blocks pasted |

## Guidance per tier (plan.md 2.3)

- **Allowed:** commercial/API products with no-training terms for any
  code/docs/methods work; public-data pipelines.
- **Gate:** before ANY prompt could touch patient-derived data (should never
  happen by design), the specific plan's no-training clause must be verified
  and cited here.
- **Prohibited:** pasting proband VCF/BAM content, genotypes, or variant
  blocks into any prompt; consumer tiers whose terms cannot be verified.
