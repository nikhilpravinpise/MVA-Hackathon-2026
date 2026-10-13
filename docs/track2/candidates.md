---
title: Candidate dossiers
nav_order: 5
parent: Track 2
---
# Track 2 candidate dossiers - curated literature layer (lane L3)

Generated 2026-10-12. This is the curated-literature complement to the engine's
`candidates.json` (lane L2). Every citation below was resolved live through
NCBI E-utilities (esummary + efetch abstract) on 2026-10-12; approval status
was checked live against ChEMBL `max_phase` and openFDA labels. No claim is
cited from memory. Framing throughout: **hypothesis generation for research
testing, not medical advice.**

Disease frame (Track 1): biallelic BUB1B - p.Leu737Ter (null) + p.Asn1002Lys
(hypomorph) - the characteristic MVA1 genotype (one null + one hypomorphic
allele; PMID:15475955). Mechanistic chain per plan section 1: reduced BubR1 ->
weak spindle assembly checkpoint -> mosaic aneuploidy -> (a) p16/p21 senescence
and growth failure, (b) clonal cancer predisposition, (c) progeroid decline.

## 1. Systematic screen (PRISMA-style)

Search executed 2026-10-12 on PubMed via esearch/efetch (sorted by relevance,
top ~15 per query screened on title+abstract). Inclusion rules: approved drug
(ChEMBL max_phase 4 + openFDA label) OR direct mechanistic evidence on
BubR1/SAC/aneuploid-cell biology that maps to an approved agent; supplements
demoted to adjuncts per plan section 0.

| # | Query (verbatim) | Retrieved | Screened | Included (role) |
|---|---|---|---|---|
| 1 | `mosaic variegated aneuploidy BUB1B` | 37 | 15 | MVA background/mechanism cites (15475955, 31738183, 23300461, 31053147, 31184400, 21190457, 39169218) |
| 2 | `BubR1 AND (drug OR compound OR treatment)` | 291 | 15 | p16-clearance anchor (22048312); rest were cancer-biology off-topic |
| 3 | `aneuploidy selective compound` | 94 | 15 | Axis-C anchor (21315436), SAC-vulnerability (33505028) |
| 4 | `BUB1B hypomorph rescue` | 0 | - | none (recorded as null) |
| 5 | `senolytic BubR1` / `senolytic AND BubR1` | 0 | - | none (recorded as null) |
| 6 | `SIRT2 BubR1 NAD` | 6 | 6 | Axis-A anchor (24825348), confirmer/caveat (38009412, 25285631, 39490401) |
| 7 | `mosaic variegated aneuploidy treatment` | 23 | 15 | HSCT case (31053147), RMS-chemo case (31184400); no drug treatment papers exist |
| 8 | `BubR1 hypomorphic mice senescence` | 11 | 11 | senescence mechanism (18516091, 22048312-adjacent) |
| 9 | `BubR1 p16 Ink4a clearance` | 1 | 1 | senolysis anchor (22048312) |
| 10 | `aneuploid cell selective killing drug` | 7 | 7 | tetraploid-elimination (24516128), mebendazole surface (rejected) |
| 11 | `dasatinib quercetin senolytic` | 342 | 15 | senolytic pair evidence (25754370, 31542391, 30616998) |
| 12 | `rapamycin aneuploidy chromosome instability` | 9 | 9 | rapamycin genome-stability caveat (37931001) |
| 13 | `metformin aneuploidy senescence` | 1 | 1 | off-topic (monkey aging) |
| 14 | `chloroquine aneuploid cells` | 6 | 6 | chloroquine selectivity (21315436) |
| 15 | `nicotinamide riboside premature aging DNA damage` | 3 | 3 | NAD-premature-aging context (41436848-adjacent) |
| 16 | `aspirin colorectal cancer prevention randomized` | 392 | 15 | CAPP2 (32534647) |
| 17 | `C elegans san-1 spindle checkpoint MAD3` | 5 | 5 | worm orthologs (18248670, 29046436, 19109417) |
| 18 | `C elegans bub-3 spindle checkpoint` | 9 | 9 | worm orthologs (as above) |
| 19 | `BubR1 insufficient premature aging mice` | 1 | 1 | p16 effector (18516091) |
| 20 | `BubR1 MVA mutation mouse lifespan` | 2 | 2 | MVA mouse (23300461, 31738183) |
| 21 | `dasatinib quercetin senescent cells clinical trial` | 24 | 10 | human senolytic pilots (31542391, 30616998) |
| 22 | `rapamycin senescence associated secretory phenotype` | 135 | 10 | senomorphic mechanism (26147250, 26280535) |
| 23 | `metformin senescent cells SASP` | 52 | 10 | senomorphic mechanism (23521863) |
| 24 | `Hanks constitutional aneuploidy BUB1B cancer predisposition` | 4 | 4 | discovery paper (15475955) |
| 25 | `Villarroya-Beltri mosaic variegated aneuploidy` | 2 | 2 | MVA review (39169218) |
| 26 | `Walsh cancer screening surveillance genomic instability children` | 1 | 1 | surveillance recs (39264246) |
| 27 | `TRIP13 Wilms tumor chromosome missegregation` | 2 | 2 | MVA2 generality (28553959) |
| 28 | `MAD1L1 germline aneuploidy tumor susceptibility` | 1 | 1 | MVA generality (36322655) |
| 29 | `Foulkes homozygous BUB1B gastrointestinal neoplasia` | 1 | 1 | BUB1B cancer (21190457) |
| 30 | `Brown high-throughput tracking phenotyping drug repurposing C elegans` | 2 | 2 | worm platform (39773880, 41013606) |
| 31 | `Bohr NAD supplementation premature aging DNA damage` | 1 | 1 | NAD review (41436848) |
| 32 | `growth hormone treatment cancer risk second neoplasm childhood` | 27 | 8 | GH rejection (16822820, 15144231) |
| 33 | `KIF18A aneuploidy selective vulnerability` | 2 | 2 | SAC-inhibitor rejection (33505028) |
| 34 | `Zhu Achilles heel senescent cells dasatinib quercetin` | 1 | 1 | senolytic discovery (25754370) |
| 35 | `aspirin Lynch syndrome CAPP2 randomized` | 16 | 8 | CAPP2 (32534647) |
| 36 | `metformin micronucleus chromosomal instability` | 1 | 1 | metformin genotoxicity caveat (35568294) |
| 37 | `rapamycin Hutchinson Gilford progeria` | 37 | 8 | progeria precedent (22170152) |
| 38 | `Moiseeva metformin senescence-associated secretory phenotype` | 1 | 1 | metformin SASP (23521863) |
| 39 | `Thompson Compton aneuploid p53 proliferation` | 1 | 1 | p53 rejection (20123995) |
| 40 | `TAME APC/C inhibitor mitosis` | 8 | 6 | APC/C rejection (22366722) |
| 41 | `mebendazole microtubule inhibitor aneuploidy` | 4 | 4 | mebendazole rejection (7739397) |
| 42 | `nicotinamide sirtuin inhibitor end product` | 11 | 8 | nicotinamide paradox (12297502) |
| 43 | `nicotinamide inhibition sirtuin accelerated aging Bitterman` | 1 | 1 | (same, 12297502) |
| 44 | `premature chromatid separation rhabdomyosarcoma` | 4 | 4 | MVA cancer cases (31184400, 31081598, 11746029) |
| 45 | `Increased expression BubR1 protects aneuploidy cancer healthy lifespan` | 1 | 1 | BubR1-OE protective proof (23242215) |
| 46 | `Franz everolimus subependymal giant cell astrocytoma EXIST-1` | 8 | 6 | pediatric mTOR precedent (23158522) |
| 47 | `autophagy inhibition cancer chloroquine` | 26 | 8 | autophagy-inhibition support (23461901, 34830283) |
| 48 | `BubR1 overexpression extends lifespan reduces cancer` | 0 | - | recorded null |
| 49 | `BubR1 transgenic overexpression aging aneuploidy` | 0 | - | recorded null |
| 50 | `san-1 mdf-1 C elegans lifespan` / `mdf-1 mdf-2 ... aneuploidy` | 0 | - | recorded nulls |
| 51 | (screened from query-2 hit list, no separate query) | - | 1 | BubR1 background review (25964054) |

**Flow** (recomputed from the table above by `tools/make_track2_report.py`;
hit counts are per query and not de-duplicated across queries): 50 queries
returned 1,614 hits -> 264 title/abstract screenings -> 51 distinct papers
resolved and carried into dossiers, the programs
file and the rejection table (row 51 screened one extra paper from query 2's
hit list without a new query). Per-candidate approval checks are recorded in
the dossiers and rejection table: 8 openFDA label set_ids and 18 distinct
ChEMBL molecule ids. No MVA-specific drug-treatment paper
exists in the literature (queries 4-5, 7 confirm) - every dossier is therefore
explicitly mechanistic extrapolation, stated as such.

## 2. Ranked shortlist

| Rank | Candidate | Axis | Why | Key caveat |
|---|---|---|---|---|
| 1 | **dasatinib + quercetin** (D+Q, senolytic) | B | Anchored in the literal disease model: clearing p16+ senescent cells rescued the BubR1-hypomorph mouse phenotype (PMID:22048312); the only candidate class with human senescent-burden-reduction evidence (PMID:31542391). Approved drug (dasatinib, CHEMBL5416410 ph4, pediatric label >=1y Ph+ CML/ALL) + supplement adjunct (quercetin). | Label warns of pediatric growth retardation/osteopenia - in a child already failing to thrive. Senescence is also tumour-suppressive. |
| 2 | **everolimus** (senomorphic mTOR) | B | Best regulatory path: approved in children >=1y (TSC-SEGA) and >=2y (TSC seizures) inside a tumour-predisposition syndrome, with label-reported absence of growth/puberty harm over a median 4.1 years of pediatric exposure (openFDA set_id 01f7b5fb; the EXIST-1 primary trial it builds on is PMID:23158522). Direct senomorphic mechanism (PMID:26147250) + genotype hook: mTORC1 hyperactivity tracks MVA-mouse sarcopenia (PMID:31738183). | Immunosuppression in a cancer-predisposed child; infection rates higher <6y; renal monitoring (nephrocalcinosis). |
| 3 | **niacin / nicotinamide** (approved NAD+ precursors) | A | Only Axis-A candidate - aims to raise residual BubR1 output rather than manage damage: NAD+/SIRT2 raises BubR1 in vivo and extended lifespan specifically in BubR1-hypomorphs (PMID:24825348; BubR1-conditional benefit confirmed PMID:38009412). Approved forms (CHEMBL573/1140 ph4). Fits the MVA Society supplements program direction. | The anchor used NMN - a supplement; extrapolation to niacin/nicotinamide is indirect. Nicotinamide itself inhibits sirtuins (PMID:12297502) - form choice is unresolved. No pediatric approval. |
| 4 | **hydroxychloroquine** (+chloroquine) | C | Only candidate with direct aneuploidy-selective kill data (PMID:21315436); the mosaic fibroblast test is decisive and cheap. Approved (CHEMBL1535 ph4). | Selectivity shown in cell lines only; irreversible retinal toxicity with cumulative dose; autophagy is double-edged in a checkpoint-defective child. |

**Adjuncts (not standalone):** sirolimus (backup mTOR agent - same mechanism
as everolimus but no pediatric approval <13y and a malignancy boxed warning;
dossier kept shortlist-verdict for completeness, deferred behind everolimus);
metformin (senomorphic fallback if mTOR
immunosuppression is disqualifying; dose-window caveat PMID:35568294); aspirin
(long-horizon interception, tetraploid-elimination mechanism PMID:24516128 +
CAPP2 precedent PMID:32534647; Reye's/bleeding caution); quercetin (only
within D+Q); NR/NMN (supplements program, Axis-A adjunct); structured cancer
surveillance per AACR genomic-instability recommendations (PMID:39264246) -
the non-drug intervention most defensible today.

## 3. Evidence-grade table

| Candidate | Approval (live check) | Mechanism in disease model | Preclinical | Human | Grade |
|---|---|---|---|---|---|
| D+Q | dasatinib ph4 + ped label; quercetin adjunct | direct: BubR1-H/H senolysis rescued phenotype (PMID:22048312) | strong | senescent-cell clearance in humans (PMID:31542391), feasibility in IPF (PMID:30616998) | moderate+ |
| everolimus | ph4, pediatric TSC indications | indirect: mTORC1 hyperactivity in MVA mice (PMID:31738183) | moderate (SASP mechanism PMID:26147250) | pediatric TSC RCT (PMID:23158522, different disease) | moderate |
| niacin/nicotinamide | ph4 (lipid/vitamin indications) | direct-ish: NAD/SIRT2 raises BubR1, rescues hypomorph lifespan (PMID:24825348, PMID:38009412) | moderate | NAD reviews in progeroid/DNA-repair disease (PMID:41436848; not MVA) | moderate- |
| HCQ/CQ | ph4 | indirect: aneuploidy-selective kill (PMID:21315436, non-MVA cells) | moderate | none for this purpose | low-moderate |
| metformin | ph4, pediatric T2DM >=10y | indirect: SASP suppression (PMID:23521863); AICAR analogy (PMID:21315436) | weak-moderate | none relevant | low-moderate |
| aspirin | ph4 (OTC) | indirect: tetraploid elimination (PMID:24516128) | moderate | CAPP2 RCT, different syndrome+endpoint (PMID:32534647) | low-moderate |

"Grade" here is an honesty label for evidence distance to the MVA use-case,
not clinical readiness: nothing above low-moderate, because no MVA-specific
drug study exists at all.

## 4. Safety synthesis (child-specific)

| Drug | Label pediatric status (label record cited in dossier) | Dominant risk for THIS phenotype |
|---|---|---|
| dasatinib | approved >=1y Ph+ CML/ALL [repo:docs/track2/evidence/dossiers/dasatinib.json] | growth retardation/osteopenia (label 5.10) stacked on short stature/FTT; myelosuppression/bleeding |
| sirolimus | NOT established <13y; BOXED WARNING malignancy [repo:docs/track2/evidence/dossiers/sirolimus.json] | immunosuppression + lymphoma/malignancy risk vs cancer predisposition; renal decline vs nephrocalcinosis |
| everolimus | approved >=1y TSC-SEGA, >=2y TSC seizures [repo:docs/track2/evidence/dossiers/everolimus.json] | infections (esp. <6y), renal failure monitoring, metabolic; same class immunosuppression minus boxed warning |
| metformin | approved >=10y T2DM [repo:docs/track2/evidence/dossiers/metformin.json] | lactic-acidosis boxed warning gated by renal function (nephrocalcinosis); B12 loss vs FTT; in-vitro SAC/genotoxic signal at mM doses (PMID:35568294) |
| HCQ/CQ | pediatric only for malaria >=31kg [repo:docs/track2/evidence/dossiers/hydroxychloroquine.json] | cumulative irreversible retinal toxicity; cardiomyopathy/QT; renal phospholipidosis |
| niacin | not established in children [repo:docs/track2/evidence/dossiers/nicotinamide.json] | hepatotoxicity/hyperglycaemia/hyperuricaemia at pharmacologic doses; sirtuin-inhibition paradox for nicotinamide |
| aspirin | no pediatric chronic use; Reye's warning [repo:docs/track2/evidence/dossiers/aspirin.json] | Reye's syndrome, GI bleeding, antiplatelet interactions |

Cross-cutting: the AACR workshop update notes genomic-instability disorders can
show exquisite sensitivity to radiation/chemotherapy (PMID:39264246) - any
genotoxic or SAC-perturbing exposure (including mM-range metformin,
benzimidazoles) deserves extra caution.

## 5. Testability summary (see testability.json)

Decisive, cheapest first: **patient-fibroblast panel** (T1, 2-6 weeks, internal
euploid control; thresholds per
[repo:docs/track2/evidence/testability.json]). Per-lead critical experiment:
- D+Q: does intermittent exposure cut p16/SA-beta-gal burden without raising
  aneuploidy? GO >=50% senescent-fraction reduction
  [repo:docs/track2/evidence/testability.json].
- everolimus: does p-S6/SASP fall without proliferation loss? GO >=30% SASP, <20% proliferation slowdown [repo:docs/track2/evidence/testability.json].
- niacin/nicotinamide: does BubR1 protein rise (Axis-A PD marker)? GO >=1.3x - a niacin-vs-nicotinamide head-to-head resolves the form question [repo:docs/track2/evidence/testability.json].
- HCQ: does the aneuploid fraction fall preferentially (the PMID:21315436
  mechanism on the child's own cells)? GO >=2-fold selective depletion
  [repo:docs/track2/evidence/testability.json].
Universal NO-GO: any candidate raising aneuploidy rate/micronuclei on patient
cells is out regardless of other benefits. Worm program (san-1/bub-3) gives
cheap whole-organism confirmation; scRNA-seq quantifies signature reversal.

## 6. What would make us wrong

- **D+Q**: We are wrong if the INK-ATTAC rescue (PMID:22048312) depended on genetic targeting
  rather than cell removal (i.e., pharmacologic senolysis fails to reproduce
  it in BubR1-defective cells), if the child's senescent compartment is
  protective (holding aneuploid clones arrested; PMID:20123995) so clearing
  it accelerates neoplasia, or if dasatinib's SRC/BCR-ABL pharmacology at senolytic pulses
  harms a growth-restricted child more than the model predicts. Falsifier:
  patient fibroblasts show no senescent-burden reduction, or cleared cells are
  replaced by aneuploid expansion
  [repo:docs/track2/evidence/portfolio.json].
- **Everolimus**: We are wrong if mTORC1 hyperactivity in MVA mice is
  downstream noise rather than driver (the JCI correlation is associational;
  PMID:31738183),
  if SASP suppression frees aneuploid clones from their secretory
  neighbourhood-watch, or if chronic immunosuppression raises net cancer risk
  faster than senescence suppression lowers it. Falsifier: fibroblasts show
  SASP down but aneuploidy up, or no mTORC1 signature on patient scRNA-seq
  [repo:docs/track2/evidence/portfolio.json].
- **Niacin/nicotinamide**: We are wrong if the K668-deacetylation axis does
  not rescue THIS hypomorph (Asn1002Lys may destabilise BubR1 by a route NAD
  cannot reach - e.g., folding, not acetylation), if approved-form
  pharmacology differs from NMN (nicotinamide inhibits sirtuins,
  PMID:12297502), or if raising BubR1 protein does not restore checkpoint
  function (protein level vs function gap). Falsifier: no BubR1-protein or
  nocodazole-response change on patient cells after NAD-precursor exposure.
- **HCQ**: We are wrong if aneuploidy selectivity was a cell-line artefact
  (Tang used engineered trisomies, not mosaic SAC-defective cells;
  PMID:21315436), if chronic
  autophagy blockade harms normal tissues needing proteostasis, or if the
  mosaic test shows no differential killing. Falsifier: fibroblast mosaic
  assay shows equal euploid/aneuploid toxicity
  [repo:docs/track2/evidence/portfolio.json].

## 7. Global limitations (honest)

1. No MVA-specific drug-treatment literature exists; all dossiers are
   mechanistic extrapolation. We say so in every verdict.
2. The patient's N1002K hypomorph may not behave like the mouse H or L1002P
   alleles; allelic effects drive phenotypic heterogeneity (PMID:31738183).
3. Phase is unknown (Track 1): if variants are in cis, the model changes.
4. Pediatric evidence for senolytic/senomorphic use is nonexistent; every
   pediatric claim above is label fact or analogy, flagged as such.
5. The worm model species/assay is inferred, not confirmed (see
   mva_programs.json).
6. Cost tiers are order-of-magnitude estimates for planning, not quotes.
7. The engine's `pediatric_flag` in candidates.json is a label-derived
   lookup hint, not a clinical assessment: it scans the matched
   single-ingredient label's `pediatric_use`, indications and dosage
   sections for an affirmative pediatric age/weight statement, keeping
   the winning sentence in `pediatric_flag_evidence`. A previous engine
   version read only `pediatric_use` of whichever record a name resolved
   to and showed false `none` for 'dasatinib anhydrous' (the >=1y
   indication sits in Indications and Usage) and 'metformin' (the name
   resolved to the ZITUVIMET combination label); the regenerated file
   shows `labeled_pediatric_indication` for both. Labels silent on
   pediatrics now read `unknown` rather than `none`, which is reserved
   for an explicit label denial. The dossier pediatric
   blocks above, each tied to a recorded set_id, are authoritative
   [repo:docs/track2/evidence/dossiers/].

## Citations

| PMID | Title (resolved) | Year |
|---|---|---|
| PMID:15475955 | Constitutional aneuploidy and cancer predisposition caused by biallelic mutations in BUB1B (Nat Genet) | 2004 |
| PMID:11746029 | Cancer-prone syndrome of mosaic variegated aneuploidy and total premature chromatid separation: report of five infants (Am J Med Genet) | 2001 |
| PMID:21190457 | Homozygous BUB1B mutation and susceptibility to gastrointestinal neoplasia (N Engl J Med) | 2010 |
| PMID:31184400 | Rhabdomyosarcoma with premature chromatid separation-mosaic variegated aneuploidy syndrome: Reduced-intensity chemotherapy (Pediatr Int; no abstract on file - title-level cite) | 2019 |
| PMID:31081598 | Long-term remission of bilateral Wilms tumors that developed from premature separation of chromatids/mosaic variegated aneuploidy syndrome (Pediatr Blood Cancer) | 2019 |
| PMID:28553959 | Biallelic TRIP13 mutations predispose to Wilms tumor and chromosome missegregation (Nat Genet) | 2017 |
| PMID:36322655 | Biallelic germline mutations in MAD1L1 induce a syndrome of aneuploidy with high tumor susceptibility (Sci Adv) | 2022 |
| PMID:39169218 | Mosaic variegated aneuploidy in development, ageing and cancer (Nat Rev Genet) | 2024 |
| PMID:25964054 | BubR1 kinase: protection against aneuploidy and premature aging (Trends Mol Med) | 2015 |
| PMID:39264246 | Update on Recommendations for Cancer Screening and Surveillance in Children with Genomic Instability Disorders (Clin Cancer Res) | 2024 |
| PMID:23300461 | Reduced life- and healthspan in mice carrying a mono-allelic BubR1 MVA mutation (PLoS Genet) | 2012 |
| PMID:31738183 | BubR1 allelic effects drive phenotypic heterogeneity in mosaic-variegated aneuploidy progeria syndrome (J Clin Invest) | 2020 |
| PMID:23242215 | Increased expression of BubR1 protects against aneuploidy and cancer and extends healthy lifespan (Nat Cell Biol) | 2013 |
| PMID:18516091 | Opposing roles for p16Ink4a and p19Arf in senescence and ageing caused by BubR1 insufficiency (Nat Cell Biol) | 2008 |
| PMID:22048312 | Clearance of p16Ink4a-positive senescent cells delays ageing-associated disorders (Nature) | 2011 |
| PMID:25754370 | The Achilles' heel of senescent cells: from transcriptome to senolytic drugs (Aging Cell) | 2015 |
| PMID:30616998 | Senolytics in idiopathic pulmonary fibrosis: Results from a first-in-human, open-label, pilot study (EBioMedicine) | 2019 |
| PMID:31542391 | Senolytics decrease senescent cells in humans: Preliminary report ... Dasatinib plus Quercetin ... diabetic kidney disease (EBioMedicine) | 2019 |
| PMID:26147250 | MTOR regulates the pro-tumorigenic senescence-associated secretory phenotype by promoting IL1A translation (Nat Cell Biol) | 2015 |
| PMID:26280535 | mTOR regulates MAPKAPK2 translation to control the senescence-associated secretory phenotype (Nat Cell Biol) | 2015 |
| PMID:22170152 | Rapamycin activates autophagy in Hutchinson-Gilford progeria syndrome (Autophagy) | 2012 |
| PMID:23158522 | Efficacy and safety of everolimus for subependymal giant cell astrocytomas associated with tuberous sclerosis complex (EXIST-1) (Lancet) | 2013 |
| PMID:37931001 | Genome instability footprint under rapamycin and hydroxyurea treatments (PLoS Genet) | 2023 |
| PMID:23521863 | Metformin inhibits the senescence-associated secretory phenotype by interfering with IKK/NF-kB activation (Aging Cell) | 2013 |
| PMID:35568294 | High-dose metformin induces a low-glucose dependent genotoxic stress (Food Chem Toxicol) | 2022 |
| PMID:21315436 | Identification of aneuploidy-selective antiproliferation compounds (Cell) | 2011 |
| PMID:33505028 | Aneuploidy renders cancer cells vulnerable to mitotic checkpoint inhibition (Nature) | 2021 |
| PMID:23461901 | Autophagy inhibition sensitizes colon cancer cells to antiangiogenic and cytotoxic therapy (Clin Cancer Res) | 2013 |
| PMID:34830283 | Clinical Translation of Combined MAPK and Autophagy Inhibition in RAS Mutant Cancer (Int J Mol Sci) | 2021 |
| PMID:24516128 | Resveratrol and aspirin eliminate tetraploid cells for anticancer chemoprevention (Proc Natl Acad Sci U S A) | 2014 |
| PMID:32534647 | Cancer prevention with aspirin in hereditary colorectal cancer (Lynch syndrome) ... CAPP2 (Lancet) | 2020 |
| PMID:24825348 | SIRT2 induces the checkpoint kinase BubR1 to increase lifespan (EMBO J) | 2014 |
| PMID:38009412 | SIRT2 transgenic over-expression does not impact lifespan in mice (Aging Cell) | 2023 |
| PMID:39490401 | BubR1 and SIRT2: Insights into aneuploidy, aging, and cancer (Semin Cancer Biol) | 2024 |
| PMID:25285631 | Deacetylation of the mitotic checkpoint protein BubR1 at lysine 250 by SIRT2 ... (Biochem Biophys Res Commun) | 2014 |
| PMID:41436848 | Promising Results With NAD Supplementation in Rare Diseases With Premature Aging and DNA Damage (Aging Cell) | 2026 |
| PMID:12297502 | Inhibition of silencing and accelerated aging by nicotinamide ... (J Biol Chem) | 2002 |
| PMID:20123995 | Proliferation of aneuploid human cells is limited by a p53-dependent mechanism (J Cell Biol) | 2010 |
| PMID:22366722 | An APC/C inhibitor stabilizes cyclin B1 by prematurely terminating ubiquitination (Nat Chem Biol) | 2012 |
| PMID:7739397 | Clastogenic and aneugenic effects of three benzimidazole derivatives in the in vitro micronucleus test (Mutagenesis) | 1995 |
| PMID:25672491 | Selective Sirt2 inhibition by ligand-induced rearrangement of the active site (Nat Commun) | 2015 |
| PMID:16822820 | Growth hormone treatment and risk of second neoplasms in the childhood cancer survivor (J Clin Endocrinol Metab) | 2006 |
| PMID:15144231 | Cancer risk following growth hormone use in childhood: implications for current practice (Drug Saf) | 2004 |
| PMID:32738133 | Influence of growth hormone therapy on the occurrence of a second neoplasm in survivors of childhood cancer (Eur J Endocrinol; counter-evidence to GH harm) | 2020 |
| PMID:31053147 | Hematopoietic stem cell transplantation in a patient with type 1 mosaic variegated aneuploidy syndrome (Orphanet J Rare Dis) | 2019 |
| PMID:18248670 | Genetic analysis of the spindle checkpoint genes san-1, mdf-2, bub-3 and the CENP-F homologues hcp-1 and hcp-2 in Caenorhabditis elegans (Cell Div) | 2008 |
| PMID:19109417 | Systematic analysis in Caenorhabditis elegans reveals that the spindle checkpoint is composed of two largely independent branches (Mol Biol Cell) | 2009 |
| PMID:18936247 | SPDL-1 functions as a kinetochore receptor for MDF-1 in Caenorhabditis elegans (J Cell Biol) | 2008 |
| PMID:29046436 | Caenorhabditis elegans BUB-3 and SAN-1/MAD3 Spindle Assembly Checkpoint Components Are Required for Genome Stability ... (G3) | 2017 |
| PMID:39773880 | High-throughput tracking enables systematic phenotyping and drug repurposing in C. elegans disease models (eLife) | 2025 |
| PMID:41013606 | High-throughput behavioural phenotyping of 25 C. elegans disease models including patient-specific mutations (BMC Biol) | 2025 |
