# Track 2 method abstract - a repurposing portfolio for BUB1B mosaic variegated aneuploidy

We built a testable, approved-drug repurposing portfolio for one child's
published BUB1B mosaic variegated aneuploidy (MVA1) genotype - p.Leu737Ter
(predicted null) plus p.Asn1002Lys (hypomorph), the characteristic MVA1
pairing (PMID:15475955) - and the open engine that produced it. Per-allele
mechanism was characterized from public data (NMD prediction, domain
mapping, missense predictors, AlphaFold context, population frequency,
ClinVar, and a protein language-model score), yielding three therapeutic
axes: residual-allele rescue, senescent-cell damage mitigation, and
aneuploid-cell vulnerability with cancer interception.

A gene-agnostic engine expands a STRING disease module, pulls drug-target
evidence from Open Targets, ChEMBL and DGIdb, keeps only approved medicines
(ChEMBL max_phase 4, not withdrawn, openFDA label present), scores network
proximity, and queries LINCS L1000 signature reversal. On BUB1B it collected
482 drug names and ranked 96 approved candidates
[repo:docs/track2/evidence/candidates.json]. Run blind on 9 genes whose
genotype-to-drug answer is established and declared in the frozen config the
engine reads, the identical pipeline recovered the known drug at
recall@1/5/10/25 of 0.00/0.33/0.56/0.56 (0.00/0.33/0.44/0.56 before the
mechanism-direction layer, which removed an opposed drug ranked above one
known answer) - an honest floor, since every miss was a drug acting outside
the disease module [repo:docs/track2/evidence/benchmark.json]. Two independent
computational checks tempered the literature: our PRISM 19Q4 re-analysis of
588 launched compounds found no FDR-significant aneuploidy-selective
approved drug (minimum q = 0.069) [repo:docs/track2/evidence/prism.json],
and ESM-2 placed p.Asn1002Lys at the 88th (650M) versus 48th (150M)
deleteriousness percentile among gnomAD BUB1B missense - a model-size
disagreement we report rather than hide
[repo:docs/track2/evidence/esm.json].

A logged systematic screen (50 PubMed queries, 51 resolved papers) produced
per-drug dossiers in which every claim is machine-resolved against PubMed
or Crossref, with approval status and pediatric label facts taken from live
ChEMBL and openFDA responses [repo:docs/track2/candidates.md]. Reconciling
the engine with the dossiers froze a four-lead portfolio: (1) dasatinib +
quercetin, anchored by senolysis rescue in the BubR1-hypomorph mouse itself
(PMID:22048312) plus human senescent-cell clearance (PMID:31542391);
(2) everolimus, a senomorphic with pediatric TSC approvals and an MVA-mouse
mTORC1 hook (PMID:23158522, PMID:31738183); (3) niacin/nicotinamide, the
only axis-A candidate, via NAD+/SIRT2 stabilisation of residual BubR1
(PMID:24825348); (4) hydroxychloroquine, the only candidate with direct
aneuploidy-selective evidence (PMID:21315436). Each lead carries a
falsifying experiment on patient fibroblasts with an explicit go/no-go
threshold, mapped to the MVA Society's four funded programs
[repo:docs/track2/evidence/testability.json].

Strengths: approval status checked by code rather than memory, a citation
gate with 100% coverage as the bar [repo:tools/verify_citations.py], a
retrospective benchmark, and testability mapped onto funded programs.
Limitations: no MVA-specific drug study exists, so every candidate is
mechanistic extrapolation; phase is unknown; the engine is structurally
blind to mechanisms outside the disease module; cancer cell-line
pharmacogenomics is not a child's tissue; and pediatric label facts bound,
but do not settle, safety. This is a hypothesis-generation method for
laboratory follow-up, not medical advice.

Word count: 451 (body only; excludes the heading and the [repo:...] artifact markers, which are pointers rather than prose. The form's limit is 500.)
