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

| Date | Provider / product | Plan / tier | Model | Data-handling terms | What data was exposed |
|---|---|---|---|---|---|
| 2026-09-26 | Cognition Devin CLI | Commercial product | SWE-2 Max | Verify no-training clause before any patient-data prompts | NONE - no patient data on disk this session; all fixtures synthetic; public reference corpora (HPO) download + repo code/docs only |

## Guidance per tier (plan.md 2.3)

- **Allowed:** commercial/API products with no-training terms for any
  code/docs/methods work; public-data pipelines.
- **Gate:** before ANY prompt could touch patient-derived data (should never
  happen by design), the specific plan's no-training clause must be verified
  and cited here.
- **Prohibited:** pasting proband VCF/BAM content, genotypes, or variant
  blocks into any prompt; consumer tiers whose terms cannot be verified.
