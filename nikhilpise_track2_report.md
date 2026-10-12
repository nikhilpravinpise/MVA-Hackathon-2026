# Rescue, Remove, Intercept: a testable, approved-drug repurposing portfolio for BUB1B mosaic variegated aneuploidy - and the open engine that built it

- **Team:** nikhilpise - MVA Hackathon 2026, Track 2 (Drug Repurposing)
- **Repository:** https://github.com/nikhilpravinpise/MVA-Hackathon-2026 (all code, configs, evidence files and tests)
- **Report generated:** 2026-10-13 from commit `97ea2b7` by `tools/make_track2_report.py` from `docs/track2/evidence/` - no number in this report is hand-typed.

> **This is a hypothesis-generation document for research follow-up, not medical advice.** Every candidate below is an existing approved medicine proposed for laboratory testing first; none should be given to any child on the strength of this report.

## For the family and patient advocates (plain language)

The child's genome carries two changes in a gene called *BUB1B*. This gene makes a protein, BubR1, that acts like a quality-control inspector during cell division: it holds the process until every chromosome is properly attached, so each new cell gets the right number. One of the child's copies is predicted to make no protein at all; the other makes a protein that is probably present but weaker or less stable. With too little working BubR1, some cells end up with the wrong number of chromosomes - this is "mosaic variegated aneuploidy" (MVA). One honest gap sits underneath that sentence: the data we had could not show that the two changes sit on *different* copies rather than the same one. Everything below assumes they are on different copies, because that is the pattern this condition almost always takes, but it was not observed in this child (section 2.3).

We asked three questions, each of which points to medicines that already exist:

1. **Rescue** - can we help the one weaker copy work better or last longer?
2. **Remove** - can we clear or quiet the damaged, worn-out ("senescent") cells that wrong chromosome numbers leave behind?
3. **Intercept** - can we make life harder for cells with the wrong chromosome numbers, and watch closely for cancer early?

For each idea we checked, by computer, that the medicine is really approved; we read the children's prescribing label; we listed what could go wrong for *this* child; and we designed the cheapest laboratory experiment - mostly on skin cells (fibroblasts) the MVA Society's labs already grow - that would tell us quickly whether the idea is worth pursuing or should be dropped.

## 1. Summary

- **Mechanism.** Allele 1 (c.2210T>G, p.Leu737Ter) is a predicted null: the stop codon sits far upstream of the last exon junction, so the transcript is predicted to undergo nonsense-mediated decay. Allele 2 (c.3006T>G, p.Asn1002Lys) is a predicted hypomorph in the kinase-like domain. This null + hypomorph pairing is the characteristic MVA1 genotype ([PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/)). Phase (in trans) is **inferred, not observed** (section 2.3).
- **Therapeutic logic.** Because one allele is null, the missense allele is the child's only source of BubR1, and BubR1 dosage is known to be tractable in vivo ([PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/); [PMID:23242215](https://pubmed.ncbi.nlm.nih.gov/23242215/)). That makes *residual-allele rescue* (axis A) the most disease-specific idea, with senescent-cell clearance (axis B, anchored in the BubR1-hypomorph mouse) ([PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/)) and aneuploid-cell vulnerability plus cancer interception (axis C) as complementary axes.
- **Method.** A deterministic, gene-agnostic engine ranks approved drugs from public evidence (section 4), a curated, machine-verified literature layer adds mechanism and pediatric-label evidence (section 5), and the two are reconciled in a frozen portfolio decision (`docs/track2/evidence/portfolio.json`).
- **Rigor receipts.** Approval status is checked by code, never from memory; every citation is resolved against PubMed/Crossref/DataCite and checked for retraction; the engine is benchmarked retrospectively on independent genotype-to-drug successes declared before the run (section 4.2); everything reruns from recorded fixtures.
- **Impact.** Every candidate maps to an assay in one of the MVA Society's four funded research programs, with an explicit go/no-go threshold (section 7). The decisive first experiment is a T1-cost fibroblast panel.

## 2. Variant mechanism

### 2.1 Per-allele evidence

| | Allele 1 | Allele 2 |
|---|---|---|
| Genomic (GRCh38) | chr15:40209701 T>G | chr15:40220612 T>G |
| cDNA / protein (NM_001211.6) | c.2210T>G p.Leu737Ter | c.3006T>G p.Asn1002Lys |
| Consequence (VEP) | stop_gained | missense_variant |
| Exon | 17/23 | 23/23 |
| NMD (50-55 nt rule) | predicted NMD (PTC 748 nt upstream of last exon-exon junction) | escapes NMD (missense allele - no premature termination codon introduced) |
| Protein consequence | 736-aa product, 29.9% lost incl. kinase-like domain | full-length protein |
| CADD phred / phyloP | 36 / 4.189 | 24.5 / 5.115 |
| AlphaMissense | n/a (truncating) | 0.9229 (likely_pathogenic) |
| REVEL / SIFT / PolyPhen | - / - / - | 0.472 / 0.01 / 0.997 |
| AlphaFold context | - | pLDDT 91.06; 27 residues within 8 A; contact number at the 53.7th percentile of the domain |
| gnomAD v4 exomes | 115/1461846 (AF 7.9e-05; hom 0) | 1/1461878 (AF 6.8e-07; hom 0) |
| gnomAD v4 genomes | 5/152174 (AF 3.3e-05; hom 0) | absent |
| ClinVar | Pathogenic/Likely pathogenic - criteria provided, multiple submitters, no conflicts (VCV000533901.9) | No ClinVar entry for c.3006T>G itself; same amino-acid change via c.3006T>A is VUS VCV004600147 (single submitter). |
| Interpretation | null (predicted loss-of-function via NMD) | hypomorphic missense (predicted: unstable pseudokinase-domain product) |

Sources: Ensembl REST VEP + transcript model, UniProt O60566, AlphaFold DB v6, gnomAD v4 GraphQL, ClinVar E-utilities - raw responses replayed from `tests/fixtures/track2/mechanism/` [repo:tools/t2_mechanism.py] ([DOI:10.1093/nar/gkab1049](https://doi.org/10.1093/nar/gkab1049)).

### 2.2 Pathway: from genotype to phenotype

| Step | Claim | Evidence | Sources |
|---|---|---|---|
| genotype | p.Leu737Ter allele: transcript predicted NMD-degraded (PTC ~750 nt upstream of last junction); any escaped product lacks the kinase-like domain. p.Asn1002Lys allele: full-length protein with a destabilising substitution in the pseudokinase domain. | rule-based prediction + human class analogy | [PMID:9644970](https://pubmed.ncbi.nlm.nih.gov/9644970/); [PMID:27618451](https://pubmed.ncbi.nlm.nih.gov/27618451/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/); [PMID:33207204](https://pubmed.ncbi.nlm.nih.gov/33207204/) |
| protein dosage | Cellular BubR1 abundance falls towards a single partially-functional allele's output; >50% loss of BubR1 expression/activity is sufficient for the PCS/MVA phenotype. | human (patient cells) | [PMID:16411201](https://pubmed.ncbi.nlm.nih.gov/16411201/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/) |
| checkpoint + attachment | Low BubR1 weakens the spindle-assembly checkpoint and reduces KARD-dependent PP2A-B56 recruitment that corrects kinetochore-microtubule attachment errors. | human cells + cell biology | [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/); [PMID:23079597](https://pubmed.ncbi.nlm.nih.gov/23079597/); [PMID:23345399](https://pubmed.ncbi.nlm.nih.gov/23345399/) |
| mis-segregation -> aneuploidy | Uncorrected errors produce constitutional mosaic gains and losses of whole chromosomes - the defining feature of MVA1. | human | [PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/) |
| cellular response | Aneuploid daughter cells arrest via p53/p21, acquire proteotoxic stress and senescence programmes (p16 effector), and signal for immune clearance. | cell + mouse | [PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/); [PMID:28633018](https://pubmed.ncbi.nlm.nih.gov/28633018/); [PMID:34216545](https://pubmed.ncbi.nlm.nih.gov/34216545/); [PMID:18516091](https://pubmed.ncbi.nlm.nih.gov/18516091/) |
| organism outcomes | Chronic aneuploidy plus senescence yields growth failure and progeroid decline, while rare escaping aneuploid clones drive childhood cancer (rhabdomyosarcoma, Wilms; adult GI cancers on milder genotypes). | human + mouse | [PMID:15208629](https://pubmed.ncbi.nlm.nih.gov/15208629/); [PMID:23300461](https://pubmed.ncbi.nlm.nih.gov/23300461/); [PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/); [PMID:31081598](https://pubmed.ncbi.nlm.nih.gov/31081598/); [PMID:21190457](https://pubmed.ncbi.nlm.nih.gov/21190457/) |

### 2.3 What we do not know (stated before any drug is discussed)

- Phase is UNKNOWN in this child (0 spanning reads in Track 1). In-trans configuration is inferred from the MVA1 genotype pattern (null + hypomorph) and phenotype fit, not observed. Resolution: parental testing, targeted long-range PCR or long-read phasing. ([PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/))
- p.Asn1002Lys residual function is unmeasured. Assays that would quantify it: patient-fibroblast BubR1 western blot (abundance), nocodazole-arrest timing (SAC competency), k-fibre stability / cold-stable microtubule assay, aneuploidy rate by FISH or single-cell DNA-seq. ([PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/); [PMID:16411201](https://pubmed.ncbi.nlm.nih.gov/16411201/))
- NMD for p.Leu737Ter is a positional prediction, not a measured decay rate; NMD efficiency varies and rare escape could yield a 736-aa fragment of uncertain activity. ([PMID:27618451](https://pubmed.ncbi.nlm.nih.gov/27618451/); [PMID:31659324](https://pubmed.ncbi.nlm.nih.gov/31659324/))
- Predictor agreement is strong but not unanimous: REVEL 0.472 is below usual supporting thresholds and the ClinVar record for the same amino-acid change (c.3006T>A) is a single-submitter VUS. ([PMID:29165669](https://pubmed.ncbi.nlm.nih.gov/29165669/))

## 3. From mechanism to therapeutic axes

- **residual-allele rescue** - The missense allele is the only functional copy; raising its abundance/stability is disease-modifying. BubR1 levels are druggable: SIRT2/NAD+ maintains BubR1 (NMN or SIRT2 upregulation raises BubR1 in vivo), K250 acetylation blocks BubR1 degradation, and transgenic BubR1 overexpression corrects checkpoint defects, aneuploidy, tumorigenesis and progeroid decline. ([PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/); [PMID:19407811](https://pubmed.ncbi.nlm.nih.gov/19407811/); [PMID:23242215](https://pubmed.ncbi.nlm.nih.gov/23242215/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/))
- **damage mitigation** - Senescent-cell burden is a downstream driver of the growth/progeroid phenotype and is modifiable: p16 clearance in BubR1 progeroid mice delayed and attenuated tissue dysfunction. ([PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/); [PMID:18516091](https://pubmed.ncbi.nlm.nih.gov/18516091/); [PMID:23602569](https://pubmed.ncbi.nlm.nih.gov/23602569/))
- **aneuploid-clone control** - Surviving aneuploid cells are the cancer substrate; immune clearance of complex karyotypes is part of natural control, and aneuploid tumour cells carry selective vulnerabilities (SAC dependency, KIF18A) relevant if malignancy arises. ([PMID:28633018](https://pubmed.ncbi.nlm.nih.gov/28633018/); [PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/); [PMID:33505027](https://pubmed.ncbi.nlm.nih.gov/33505027/))
- **cancer surveillance** - Mechanism predicts childhood embryonal rhabdomyosarcoma and Wilms tumour risk plus later GI neoplasia - regular surveillance is mechanism-justified independent of any drug choice. ([PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/); [PMID:31081598](https://pubmed.ncbi.nlm.nih.gov/31081598/); [PMID:21190457](https://pubmed.ncbi.nlm.nih.gov/21190457/))

**What the mechanism rules out** (these shaped the rejected table in section 6):

- **SAC/MPS1/KIF18A inhibitors** - Systemic weakening of an already-insufficient checkpoint increases mis-segregation and aneuploid-clone supply. Nuance: aneuploid CANCER cells are selectively killed by these agents - relevant to treating an established tumour, contraindicated as prophylaxis. ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/); [PMID:33505027](https://pubmed.ncbi.nlm.nih.gov/33505027/); [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/))
- **p53 suppression** - p53/p21 is the brake limiting propagation of aneuploid cells and protecting muscle/fat in BubR1-insufficient mice; lifting it expands aneuploid clones. ([PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/); [PMID:23602569](https://pubmed.ncbi.nlm.nih.gov/23602569/))
- **growth hormone (for short stature)** - Guidance flags GH use in chromosomal-breakage / DNA-repair disorders for caution because of malignancy risk; in a constitutional-aneuploidy cancer-predisposition syndrome, accelerating clone expansion is mechanistically counterproductive. Counter-evidence: a large survivor cohort found no significant second-neoplasm increase, so this is precautionary. ([PMID:30500870](https://pubmed.ncbi.nlm.nih.gov/30500870/); [PMID:32738133](https://pubmed.ncbi.nlm.nih.gov/32738133/); [PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/))
- **antimitotic agents producing aneuploidy** - Chronic spindle poisons / aneugens add mis-segregation on top of a constitutionally weak checkpoint - the opposite direction of the therapeutic goal. ([PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/); [PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/))

## 4. Method: the open repurposing engine

### 4.1 How candidates are generated

The engine (`src/track2/`, `tools/run_track2.py`, frozen `config/track2.yaml`) is gene-agnostic: given a disease gene, its seed module and an axis map, it (1) expands the module on STRING, (2) pulls drug-target evidence from Open Targets, ChEMBL and DGIdb, (3) keeps only approved medicines (ChEMBL max_phase 4, not withdrawn, with an openFDA label), (4) scores network proximity between drug targets and the disease module against degree-matched random sets, (5) queries transcriptomic signature reversal on LINCS L1000 (SigCom LINCS), and (6) reports every evidence channel's contribution to a transparent weighted score and tier. Every API response is cached and replayed, so the ranking is byte-reproducible offline. Design details, source versions and limitations: [repo:docs/track2/engine.md].

**Funnel (MVA run, config sha `f4b0cca2092b`).** Disease module: 71 genes (seeds + STRING neighbours of BUB1B at score >= 700). 108 Open Targets clinical rows and 1403 DGIdb interactions -> 482 distinct drug names -> approval gate: 96 approved, 115 not phase 4, 6 withdrawn, 252 unresolvable names (investigational codes or non-drug entities, counted rather than guessed; 13 further names resolved onto a ChEMBL id another candidate already held). LINCS L1000 reversal: status `ok`, 100 reversers on `l1000_cp` [repo:docs/track2/evidence/candidates.json]. The mechanism-direction layer then removed **37 mechanism-opposed** approved drugs (genotoxic, aneugenic, antimitotic or checkpoint-weakening - section 3) from the ranking; they are listed, not hidden, in the evidence file.

| Rank | Drug | Module targets | Axis | Direction | Tier | Score | Pediatric label |
|---|---|---|---|---|---|---|---|
| 1 | palbociclib | CDKN2A, NEK2, PRKAA1 | B | neutral | T1 | 0.594 | none |
| 2 | sirolimus | CDKN2A, MTOR, PRKAA1 | B | aligned | T1 | 0.505 | labeled pediatric indication |
| 3 | glycerin | CDKN1A | B | neutral | T1 | 0.494 | none |
| 4 | methenamine | CDKN1A | B | neutral | T1 | 0.494 | none |
| 5 | octocrylene | BIRC5 | none | neutral | T1 | 0.494 | none |
| 6 | omacetaxine mepesuccinate | BIRC5 | none | neutral | T1 | 0.494 | none |
| 7 | pentetic acid | CDKN1A | B | neutral | T1 | 0.494 | labeled pediatric indication |
| 8 | phenylbutanoic acid | CDKN1A | B | neutral | T1 | 0.494 | none |
| 9 | abemaciclib | CDKN2A, TP53 | B | neutral | T1 | 0.489 | none |
| 10 | gefitinib | SIRT2 | A | neutral | T1 | 0.469 | none |
| 11 | clotrimazole | CDK1 | none | neutral | T1 | 0.452 | none |
| 12 | everolimus | CDKN2A, MTOR | B | aligned | T1 | 0.450 | labeled pediatric indication |
| 13 | flutamide | BIRC5, CDKN1A | B | neutral | T2 | 0.417 | none |
| 14 | tamoxifen | CCNA2, TP53 | B | neutral | T2 | 0.417 | none |
| 15 | celecoxib | CDKN1A | B | neutral | T2 | 0.411 | labeled pediatric indication |
| 16 | lapatinib | BIRC5 | none | neutral | T2 | 0.355 | none |
| 17 | levothyroxine | PRKAA1 | B | neutral | T2 | 0.353 | labeled pediatric indication |
| 18 | erlotinib | BIRC5 | none | neutral | T2 | 0.329 | none |
| 19 | dabrafenib | CDKN2A | B | neutral | T2 | 0.325 | labeled pediatric indication |
| 20 | vemurafenib | CDKN2A | B | neutral | T2 | 0.325 | none |

Top mechanism-opposed exclusions (would-be rank, rule): doxorubicin (#1, opp_dna_damaging, opp_topoisomerase_poison); epirubicin (#2, opp_topoisomerase_poison); temozolomide (#3, opp_dna_damaging); cyclophosphamide anhydrous (#4, opp_dna_damaging); mitomycin (#5, opp_dna_damaging); pixantrone (#6, opp_dna_damaging, opp_topoisomerase_poison); cantharidin (#7, opp_pp2a_inhibitor); daunorubicin (#8, opp_dna_damaging, opp_topoisomerase_poison). The 96 approved entries include 7 salt or ester forms of an active already counted (daunorubicin hydrochloride, dexrazoxane hydrochloride, doxorubicin hydrochloride, etoposide phosphate, idarubicin hydrochloride, metformin hydrochloride, mitoxantrone hydrochloride), so the distinct active count is 89.

The engine ranks *evidence density*, not suitability for this child: databases over-represent oncology, so the curated layer (section 5) and the pediatric facts decide the portfolio. What the engine does establish is twofold: it independently reaches the mTOR axis (sirolimus and everolimus are its top mechanism-aligned hits) without being told to, and it produces the exclusion receipt - the named list of approved drugs that the mechanism forbids here, which is the part a hand-written shortlist cannot show. Two of the four leads lie outside its reach entirely (section 5.2), which is the measured limit of target-network repurposing, not a result we hide. Full output incl. every evidence channel: [repo:docs/track2/evidence/candidates.json].

### 4.2 Does the engine find known answers? (retrospective benchmark)

The identical pipeline, run blind on 9 genes whose approved repurposed or targeted drug is established (the truth list is declared in `config/track2.yaml`, which the engine reads at run time and whose hash it records in the output; the drug is never seeded). **recall@1 / @5 / @10 / @25 = 0.00 / 0.33 / 0.56 / 0.56** (frozen pre-direction-layer run: 0.00 / 0.33 / 0.44 / 0.56) [repo:docs/track2/evidence/benchmark.json].

| Disease gene | Disease | Known approved drug(s): rank in engine output | Evidence for the known pair |
|---|---|---|---|
| TSC2 | tuberous sclerosis complex / sporadic LAM | everolimus: #3; sirolimus: #4 | [PMID:21047224](https://pubmed.ncbi.nlm.nih.gov/21047224/); [PMID:21410393](https://pubmed.ncbi.nlm.nih.gov/21410393/) |
| PIK3CA | PIK3CA-related overgrowth spectrum | alpelisib: #2 | [PMID:29899452](https://pubmed.ncbi.nlm.nih.gov/29899452/) |
| FBN1 | Marfan syndrome | losartan: not collected | [PMID:25405392](https://pubmed.ncbi.nlm.nih.gov/25405392/) |
| KCNJ11 | KCNJ11 neonatal diabetes | glibenclamide: #10 | [PMID:16885550](https://pubmed.ncbi.nlm.nih.gov/16885550/) |
| CFTR | cystic fibrosis (G551D) | ivacaftor: #6 | [PMID:22047557](https://pubmed.ncbi.nlm.nih.gov/22047557/) |
| SCN1A | Dravet syndrome | fenfluramine: not collected | [PMID:31862249](https://pubmed.ncbi.nlm.nih.gov/31862249/) |
| ACVR1 | fibrodysplasia ossificans progressiva | palovarotene: not collected | [PMID:36583535](https://pubmed.ncbi.nlm.nih.gov/36583535/) |
| CACNA1A | episodic ataxia type 2 | acetazolamide: not collected | [PMID:22158718](https://pubmed.ncbi.nlm.nih.gov/22158718/); [PMID:39174244](https://pubmed.ncbi.nlm.nih.gov/39174244/) |
| GLA | Fabry disease | migalastat: #2 | [PMID:27834756](https://pubmed.ncbi.nlm.nih.gov/27834756/) |

**Reading it honestly.** Every miss is structural: the known drug acts on a target outside the disease gene's interaction module (for example losartan acts on the angiotensin receptor, not on FBN1's partners), so a target-overlap engine never collects it. Recall is therefore a floor on what network-seeded repurposing can do, and it is why this report pairs the engine with a mechanism-led literature layer rather than trusting either alone.

### 4.3 Independent computational evidence

**Aneuploidy pharmacogenomics (PRISM repurposing screen x cell-line aneuploidy).** Highly aneuploid cancer cells have distinct drug vulnerabilities ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/)); we asked which *approved* drugs preferentially inhibit more-aneuploid cell lines, controlling for lineage.

Model: AUC ~ feature + C(primary_tissue), OLS with absorbed lineage fixed effects (FWL); beta < 0 = cell lines with more of the feature are more sensitive to the drug; q = Benjamini-Hochberg over tested compounds. 588 launched compounds tested (of 1498) ([DOI:10.1038/s43018-019-0018-6](https://doi.org/10.1038/s43018-019-0018-6); [DOI:10.1038/s41586-020-03114-6](https://doi.org/10.1038/s41586-020-03114-6)). **Validation:** our per-drug statistics reproduce the published PRISM-aneuploidy analysis (Spearman rho = 0.72, sign concordance 80%, n = 1442 drugs). **Result:** no launched drug is aneuploidy-selective after FDR correction (minimum q = 0.069); the top directional hits are listed only as hypothesis-generating:

| Launched drug (Broad annotation) | MOA | beta (AUC ~ aneuploidy, lineage-adjusted) | p | q (BH) | lines |
|---|---|---|---|---|---|
| ingenol-mebutate | PKC activator | -0.0041 | 0.1 | 0.59 | 436 |
| lomefloxacin | bacterial DNA gyrase inhibitor | -0.0031 | 0.0029 | 0.21 | 236 |
| alogliptin | dipeptidyl peptidase inhibitor | -0.0031 | 0.044 | 0.48 | 356 |
| sufentanil | opioid receptor modulator | -0.0030 | 0.015 | 0.36 | 378 |
| methscopolamine | acetylcholine receptor antagonist | -0.0029 | 0.073 | 0.54 | 415 |
| tiludronate | bone resorption inhibitor, osteoclast inhibitor | -0.0026 | 0.08 | 0.55 | 389 |
| tropisetron | serotonin receptor antagonist | -0.0025 | 0.066 | 0.52 | 400 |
| leucovorin | folate receptor ligand | -0.0025 | 0.12 | 0.63 | 376 |

Two findings shape the portfolio: mitotic/checkpoint drugs are mostly *aneuploid-resistant* in this short-exposure screen (supporting their place in the rejected table), and metformin, chloroquine and hydroxychloroquine are absent from the screen, so no PRISM claim is made for them. Full results and controls: [repo:docs/track2/evidence/prism.json].

**Protein language-model effect of p.Asn1002Lys (ESM-2 masked-marginal score, calibrated on BUB1B ClinVar/gnomAD missense).**

| Model (run) | LLR p.Asn1002Lys | More damaging than ... of gnomAD BUB1B missense | ... of benign panel | AUC common vs ultra-rare gnomAD | AUC benign vs nonsense proxy |
|---|---|---|---|---|---|
| esm2_t33_650M_UR50D (L4, [repo:docs/track2/evidence/esm.json]) | -5.81 | 88% | 97% | 0.59 | 1.00 |
| esm2_t30_150M_UR50D (cpu, [repo:docs/track2/evidence/esm_150m.json]) | -0.37 | 48% | 61% | 0.50 | 1.00 |

Masked-marginal log-likelihood ratios over 1319 scored variants (1273 gnomAD v4 BUB1B missense as background; the query itself, seen once in gnomAD, is excluded from it). Only 1 classified pathogenic BUB1B missense exists in ClinVar, so a missense-only pathogenicity AUC cannot be estimated. The larger model places p.Asn1002Lys among the most constrained substitutions in the protein while the smaller one scores it mid-distribution; we cite the larger model, which also separates the gnomAD frequency classes better, and report both. A conservation score does not measure residual function: a strongly constrained residue is compatible with a hypomorphic, partially functional product.

## 5. The candidate portfolio

### 5.1 Systematic literature screen

50 PubMed queries, logged verbatim with hit counts and screening decisions, returned 1,614 hits (per query, not de-duplicated) -> 264 title/abstract screenings -> 51 distinct papers carried into the dossiers, the programs file and the rejected table. Inclusion rule: an approved medicine (ChEMBL max_phase 4 + openFDA label) or direct mechanistic evidence on BubR1 / SAC / aneuploid-cell biology that maps to one. Supplements were demoted to adjuncts. No MVA-specific drug-treatment paper exists, so every dossier is explicitly mechanistic extrapolation. Query log: [repo:docs/track2/candidates.md].

### 5.2 Ranked shortlist

| Rank | Candidate | Axis | Approval (checked by code) | Pediatric label | Evidence grade | Engine placement |
|---|---|---|---|---|---|---|
| 1 | **dasatinib + quercetin - senolytic clearance of p16+ cells** | B - senescence / damage mitigation | ChEMBL max_phase 4, first approval 2006; openFDA set_id `02b04c6f` | Pediatric patients 1 year of age and older: Ph+ CML in chronic phase; newly diagnosed Ph+ ALL in combination with chemotherapy (quoted label fact). | moderate+ | dasatinib anhydrous #43/59 |
| 2 | **everolimus - senomorphic SASP dampening via mTORC1 inhibition** | B - senescence / damage mitigation | ChEMBL max_phase 4, first approval 2009; openFDA set_id `01f7b5fb` | TSC-associated SEGA requiring intervention: patients >=1 year. Adjunctive treatment of TSC-associated partial-onset seizures: >=2 years (oral suspension). ... | moderate | everolimus #12/59 |
| 3 | **niacin / nicotinamide - NAD+/SIRT2 stabilisation of residual BubR1** | A - residual-BubR1 rescue | ChEMBL max_phase 4, first approval -; openFDA set_id `bf287412` | None. Label states verbatim: 'Pediatric Use - Safety and effectiveness in children and adolescents have not been established.' (quoted label fact) | moderate- | niacin: not in module; nicotinamide: not in module |
| 4 | **hydroxychloroquine - aneuploidy-selective autophagy blockade, interception** | C - aneuploid-cell vulnerability / cancer interception | ChEMBL max_phase 4, first approval 1955; openFDA set_id `04139607` | Established in pediatric patients only for malaria treatment and prophylaxis, and only >=31 kg because tablets cannot be divided; NOT established for ... | low-moderate | hydroxychloroquine: not in module; chloroquine: not in module |

"Evidence grade" is an honesty label for the distance between the evidence and this child's use case, not clinical readiness: no MVA-specific drug-treatment study exists, so nothing is graded higher than moderate.

### 5.3 Lead candidates in detail

### 1. dasatinib + quercetin - senolytic clearance of p16+ cells

*Why it is here:* BubR1 insufficiency drives p16Ink4a-positive senescence in muscle and fat, and clearing p16-positive senescent cells in the BubR1-hypomorph mouse both delayed and attenuated the progeroid phenotype - the only anchor experiment run in the literal disease model ([PMID:18516091](https://pubmed.ncbi.nlm.nih.gov/18516091/), [PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/)). Dasatinib + quercetin is the canonical pharmacologic senolytic pair, with dasatinib clearing senescent human fat-cell progenitors and quercetin clearing senescent endothelial cells in preclinical work ([PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/)). It is also the only candidate class with human evidence of senescent-burden reduction, from a 9-patient diabetic-kidney-disease pilot of a 3-day intermittent course ([PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/)), with feasibility-level data from a 14-patient IPF pilot ([PMID:30616998](https://pubmed.ncbi.nlm.nih.gov/30616998/)). The MVA genotype-to-phenotype chain runs through exactly this senescent compartment ([PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/), [PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/)). In our PRISM 19Q4 re-analysis dasatinib showed a directional, non-significant association toward preferential activity in low-BUB1B and more-aneuploid lines - hypothesis-level corroboration only, not a rank driver [repo:docs/track2/evidence/prism.json]. The counter-consideration is real: senescence is also tumour-suppressive and aneuploid-cell proliferation is p53-limited, so clearing the compartment could free protective arrested cells as well as harmful ones ([PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/)). Dasatinib's pediatric label (>=1y Ph+ CML/ALL) carries a growth-retardation and osteopenia warning that sits badly on a child with short stature and failure to thrive, which is why this is a test-first lead and not a treatment suggestion.

*Evidence:*

- [mechanism, direct] BubR1 insufficiency drives p16Ink4a-positive cellular senescence in skeletal muscle and adipose tissue; genetic p16Ink4a inactivation attenuates senescence and premature ageing in BubR1-insufficient mice. ([PMID:18516091](https://pubmed.ncbi.nlm.nih.gov/18516091/))
- [preclinical, direct] In BubR1-hypomorphic progeroid mice, drug-inducible clearance of p16Ink4a-positive senescent cells delayed onset of age-related pathology in adipose tissue, skeletal muscle and eye, and attenuated established disease when started late in life - the direct causal evidence that senolysis modifies the BubR1-insufficiency phenotype. ([PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/))
- [preclinical, direct] Dasatinib + quercetin is the canonical senolytic pair: dasatinib clears senescent human fat-cell progenitors, quercetin clears senescent endothelial cells, and the combination reduced senescent-cell burden and extended healthspan in aged, irradiated and progeroid (Ercc1-/delta) mice. ([PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/))
- [clinical, direct] First human evidence that D+Q lowers senescent-cell burden: in a 9-patient open-label diabetic-kidney-disease pilot, 3 days of D 100 mg + Q 1000 mg reduced adipose p16/p21-expressing cells, SA-beta-gal activity and circulating SASP factors (IL-1a, IL-6, MMP-9/12) within 11 days. ([PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/))
- [clinical, indirect] In a first-in-human open-label pilot in idiopathic pulmonary fibrosis (n=14), intermittent D+Q was feasible and improved physical-function measures; pulmonary function and reported health were unchanged - feasibility-level evidence, not efficacy proof. ([PMID:30616998](https://pubmed.ncbi.nlm.nih.gov/30616998/))
- [mechanism, indirect] MVA1 disease mechanism is chronic chromosome missegregation producing mosaic aneuploidy; aneuploid and damaged cells enter p53/p21- and p16-driven senescence, linking the BubR1 genotype to the senescent-cell burden that D+Q targets (MVA review; genotype-phenotype chain). ([PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/); [PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/))
- [safety, indirect] Counter-consideration: senescence is also a tumour-suppressive response, and aneuploid-cell proliferation is limited by a p53-dependent mechanism; indiscriminate removal of the senescent compartment in a cancer-predisposition syndrome could remove both harmful and protective arrested cells. Net direction in this genotype is untested. ([PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/); [PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/))

*Pediatric label facts* (openFDA drug/label set_id 02b04c6f-4ea5-4fcb-bf6d-2631d5ab31e4 (effective 2026-03-05); dasatinib tablets): Pediatric patients 1 year of age and older: Ph+ CML in chronic phase; newly diagnosed Ph+ ALL in combination with chemotherapy (quoted label fact). Boxed warning: None on this label.

*Risks specific to this child's phenotype:*

- Label section 5.10 'Effects on Growth and Development in Pediatric Patients': epiphyses delayed fusion, osteopenia, growth retardation and gynecomastia reported; label advises monitoring bone growth and development. Directly relevant to a child with short stature and failure to thrive.
- Myelosuppression (severe thrombocytopenia, neutropenia, anaemia) and bleeding; dasatinib also inhibits platelet function - additive bleeding risk with any antiplatelet adjunct. [repo:openFDA label 02b04c6f]
- Fluid retention incl. pleural effusions; pulmonary arterial hypertension; QT prolongation; severe dermatologic reactions; tumour lysis syndrome; embryo-fetal toxicity. [repo:openFDA label 02b04c6f]
- Hypothesis framing: senolytic regimens are intermittent 'hit-and-run' (3-day cycles in the human pilots), which limits total exposure relative to continuous oncology dosing - but no pediatric senolytic dosing exists; any use here is untested. [repo:openFDA label 02b04c6f]

*What would make us wrong:* We are wrong if the BubR1-hypomorph rescue depended on the INK-ATTAC genetic circuit rather than on senescent-cell removal per se, or if this child's senescent compartment is protective - holding aneuploid clones arrested - so clearing it accelerates neoplasia ([PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/), [PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/)). Decisive experiment (T1, 2-4 weeks): intermittent D+Q exposure of patient fibroblasts; GO on >=50% reduction of the senescent-marker fraction with no rise in aneuploidy rate or euploid cytotoxicity, NO-GO on nonselective toxicity or aneuploid expansion after clearance (testability.json).

### 2. everolimus - senomorphic SASP dampening via mTORC1 inhibition

*Why it is here:* mTORC1 inhibition is senomorphic rather than senolytic: it blunts the senescence-associated secretory phenotype at the translational level through IL1A and MAPKAPK2, dampening senescent-cell paracrine damage without killing the cells ([PMID:26147250](https://pubmed.ncbi.nlm.nih.gov/26147250/), [PMID:26280535](https://pubmed.ncbi.nlm.nih.gov/26280535/)). The genotype-specific hook is direct: in monoallelic BubR1-mutant mice modelling MVA, predisposition to sarcopenia tracked mTORC1 hyperactivity ([PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/)). Everolimus carries the strongest pediatric regulatory footing of any candidate - approved for TSC-associated SEGA from age 1 and TSC-associated seizures from age 2 inside a tumour-predisposition syndrome - and the label reports no adverse impact on growth or pubertal development across 115 pediatric patients with a median 4.1 years of exposure (openFDA set_id 01f7b5fb; the EXIST-1 primary trial it builds on is [PMID:23158522](https://pubmed.ncbi.nlm.nih.gov/23158522/)). The same label reports markedly higher infection rates under age 6, and class-level immunosuppression is a real concern in a cancer-predisposed child (openFDA set_id 01f7b5fb). Our PRISM re-analysis found no aneuploidy-selective signal for everolimus, which is coherent rather than damning: it is proposed as a senomorphic, not as an aneuploid-cell-selective agent [repo:docs/track2/evidence/prism.json]. It is preferred over sirolimus - the engine's top mechanism-aligned hit - on pediatric feasibility alone: sirolimus has no pediatric approval under 13 and a malignancy boxed warning, where everolimus has labeled pediatric indications in a cancer-predisposition syndrome.

*Evidence:*

- [mechanism, indirect] Same senomorphic mechanism as sirolimus: mTORC1 inhibition blunts the pro-inflammatory SASP via translational control of IL1A and MAPKAPK2, dampening senescent-cell paracrine damage without killing the cells. ([PMID:26147250](https://pubmed.ncbi.nlm.nih.gov/26147250/); [PMID:26280535](https://pubmed.ncbi.nlm.nih.gov/26280535/))
- [clinical, analogy] Pediatric tumour-predisposition precedent: in the phase 3 EXIST-1 trial, everolimus produced significant SEGA volume reductions versus placebo in children/adults with tuberous sclerosis complex - proof that chronic mTOR inhibition is tolerated and effective in a paediatric cancer-predisposition population. ([PMID:23158522](https://pubmed.ncbi.nlm.nih.gov/23158522/))
- [clinical, analogy] Label-reported pediatric tolerability (openFDA set_id 01f7b5fb; the EXIST-1 primary trial is [PMID:23158522](https://pubmed.ncbi.nlm.nih.gov/23158522/), whose own exposure was ~1 year): in EXIST-1/Study 2485 open-label follow-up (115 pediatric patients, median 4.1 years exposure), everolimus did not appear to adversely impact growth and pubertal development - the key reassurance for use in a growth-restricted child, tempered by higher infection rates in patients <6 years (96% any infection, 35% serious infection). ([PMID:23158522](https://pubmed.ncbi.nlm.nih.gov/23158522/))
- [preclinical, direct] Genotype-specific hook shared with sirolimus: mTORC1 hyperactivity correlates with sarcopenia predisposition in monoallelic BubR1-mutant MVA mice. ([PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/))
- [safety, indirect] Counter-consideration: as with all mTOR inhibitors, immunosuppression reduces tumour immune surveillance; everolimus additionally carries renal-failure and metabolic warnings relevant to a child with nephrocalcinosis, and label advises completing childhood vaccinations before starting treatment. ([PMID:26147250](https://pubmed.ncbi.nlm.nih.gov/26147250/))

*Pediatric label facts* (openFDA drug/label set_id 01f7b5fb-be0d-4adf-acd2-6899018de966 (effective 2025-09-05); everolimus tablets and tablets for oral suspension): TSC-associated SEGA requiring intervention: patients >=1 year. Adjunctive treatment of TSC-associated partial-onset seizures: >=2 years (oral suspension). (Quoted label facts.) Boxed warning: None on this label.

*Risks specific to this child's phenotype:*

- Infections, including serious infections, at higher frequency under age 6 (label: 96% any infection vs 67% in >=6y; 35% serious vs 7%) - immunosuppression concern in a cancer-predisposed child. [repo:openFDA label 01f7b5fb]
- Non-infectious pneumonitis, stomatitis, renal failure (monitor renal function - nephrocalcinosis phenotype), hyperglycaemia/hyperlipidaemia, myelosuppression, impaired wound healing, radiation sensitisation, embryo-fetal toxicity, live-vaccine avoidance. [repo:openFDA label 01f7b5fb]
- No boxed warning on this oncology label, unlike sirolimus's transplant boxed warning - but the same class-level immunosuppression applies. [repo:openFDA label 01f7b5fb]

*What would make us wrong:* We are wrong if the mTORC1 hyperactivity seen in the MVA-mouse model is downstream noise rather than driver - the association is correlational ([PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/)) - or if SASP suppression frees aneuploid clones from their secretory neighbourhood-watch while immunosuppression raises net cancer risk faster than senescence control lowers it. Decisive experiment (T1, 2-4 weeks): everolimus on patient fibroblasts; GO on >=30% SASP reduction with stable aneuploidy and <20% proliferation slowdown, NO-GO on cytostasis or any aneuploidy rise (testability.json).

### 3. niacin / nicotinamide - NAD+/SIRT2 stabilisation of residual BubR1

*Why it is here:* This is the only Axis-A candidate: it aims to raise output of the residual hypomorphic allele rather than manage downstream damage - mechanistically the most disease-modifying idea, because raising BubR1 abundance in mice preserves genomic integrity, corrects checkpoint and attachment defects, reduces tumorigenesis and extends healthy lifespan ([PMID:23242215](https://pubmed.ncbi.nlm.nih.gov/23242215/)). The anchor: NAD+/SIRT2 maintains BubR1, and NMN or SIRT2 overexpression raised BubR1 abundance in vivo, with SIRT2 overexpression extending lifespan specifically in BubR1-hypomorphic animals ([PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/)) - a benefit independently shown to be conditional on low BubR1 rather than a general-longevity effect ([PMID:38009412](https://pubmed.ncbi.nlm.nih.gov/38009412/)). The direction is sharpened from both sides: selective SIRT2 inhibition destabilises BubR1 protein in cells ([PMID:25672491](https://pubmed.ncbi.nlm.nih.gov/25672491/)). The 650M ESM-2 masked-marginal run scores the child's p.Asn1002Lys at the 88th percentile of deleteriousness among gnomAD BUB1B missense - consistent with a constrained, function-impaired residual allele worth rescuing - but the 150M run scores it mid-distribution, so this is supporting rather than deciding evidence [repo:docs/track2/evidence/esm.json] [repo:docs/track2/evidence/esm_150m.json]. The honest pharmacology caveat: nicotinamide is both an NAD+ precursor and a sirtuin end-product inhibitor, so the wrong form could blunt the axis it is meant to fuel, while niacin raises NAD+ without that product inhibition ([PMID:12297502](https://pubmed.ncbi.nlm.nih.gov/12297502/), [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/)). SIRT2 regulation of BubR1 is also site- and context-specific - K250 deacetylation promotes timely BubR1 degradation at mitotic exit - so 'more SIRT2 activity' is not linearly 'more BubR1' ([PMID:25285631](https://pubmed.ncbi.nlm.nih.gov/25285631/)). Approved forms exist (niacin, niacinamide) but neither has a pediatric indication, and the anchor experiment used NMN - a supplement - so the approved-form evidence is extrapolated ([PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/)).

*Evidence:*

- [mechanism, direct] Axis-A anchor: the age-related decline of BubR1 protein is driven by declining NAD+ and loss of SIRT2-mediated deacetylation of BubR1 lysine-668 (opposed by CBP acetylation); in mice, SIRT2 overexpression OR treatment with the NAD+ precursor NMN increased BubR1 abundance in vivo, and SIRT2 overexpression extended median lifespan specifically in BubR1-hypomorphic (H/H) animals. ([PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/); [PMID:25672491](https://pubmed.ncbi.nlm.nih.gov/25672491/))
- [preclinical, direct] Raising BubR1 abundance is itself disease-modifying in models: sustained high BubR1 expression in mice preserves genomic integrity, corrects checkpoint and microtubule-kinetochore attachment defects, reduces tumorigenesis even with oncogenic Ras, and extends healthy lifespan - the proof that increasing residual BubR1 output compensates a defective checkpoint. ([PMID:23242215](https://pubmed.ncbi.nlm.nih.gov/23242215/))
- [preclinical, direct] Independent lab confirmation with honest bound: SIRT2 overexpression rescues health and lifespan in the BubR1-hypomorph model via improved BubR1 protein stability, but the same overexpression in wild-type mice had NO effect on health or lifespan - i.e. the SIRT2 benefit appears conditional on BubR1 under-expression, which is exactly the MVA1 situation (null + hypomorph alleles) but offers no general-longevity claim. ([PMID:38009412](https://pubmed.ncbi.nlm.nih.gov/38009412/))
- [clinical, analogy] Class-level clinical plausibility: NAD+ supplementation shows benefit in several premature-ageing and DNA-repair-deficiency diseases where PARP hyperactivation depletes NAD+, with a favourable safety profile - a review-level support for NAD restoration in rare progeroid/genome-instability disease, though MVA itself was not studied. ([PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/))
- [mechanism, direct] Critical pharmacology caveat: nicotinamide is BOTH an NAD+ precursor AND an end-product inhibitor of sirtuin deacetylases (established for yeast Sir2 and human SIRT1) - so high-dose nicotinamide could theoretically inhibit the very SIRT2-BubR1 axis it is meant to fuel. Nicotinic acid (niacin) raises NAD+ via the Preiss-Handler pathway without product inhibition of sirtuins; the choice of form is therefore mechanistically non-trivial. ([PMID:12297502](https://pubmed.ncbi.nlm.nih.gov/12297502/); [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/))
- [mechanism, indirect] Mechanistic nuance: SIRT2 also deacetylates BubR1 at K250 during prometaphase, where deacetylation promotes timely APC/C-mediated BubR1 degradation at mitotic exit; SIRT2 regulation of BubR1 is site- and context-specific, so 'more SIRT2 activity' does not linearly equal 'more BubR1'. ([PMID:25285631](https://pubmed.ncbi.nlm.nih.gov/25285631/))

*Pediatric label facts* (openFDA drug/label set_id bf287412-160b-403f-8eb4-57f29a475902 (effective 2021-12-23); NIACOR (nicotinic acid)): None. Label states verbatim: 'Pediatric Use - Safety and effectiveness in children and adolescents have not been established.' (quoted label fact) Boxed warning: None.

*Risks specific to this child's phenotype:*

- Niacin at lipid-lowering doses: flushing, hepatotoxicity (label contraindicates significant/unexplained hepatic dysfunction), hyperglycaemia, hyperuricaemia, GI/peptic-ulcer caution - the approved-dose adverse profile is adult-derived. [repo:openFDA label bf287412]
- Nutritional-dose nicotinamide/niacin (vitamin-level) has a wide safety margin in children, but the NAD-restoration hypothesis may require pharmacologic doses - an open question. [repo:openFDA label bf287412]
- Form-choice risk (claim c5): pharmacologic nicotinamide could inhibit sirtuins; the safe-form question is unresolved, not a detail. [repo:openFDA label bf287412]
- No reproductive-age considerations for the child directly; family context includes recurrent spontaneous abortion - niacin pregnancy safety is not established at pharmacologic doses. [repo:openFDA label bf287412]

*What would make us wrong:* We are wrong if the NAD+/SIRT2 deacetylation axis does not reach this particular hypomorph - Asn1002Lys may destabilise BubR1 by a route NAD+ cannot touch - or if approved-form pharmacology differs materially from NMN, since nicotinamide itself inhibits sirtuins ([PMID:12297502](https://pubmed.ncbi.nlm.nih.gov/12297502/), [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/)). Decisive experiment (T1, 2-4 weeks): niacin versus nicotinamide head-to-head on patient fibroblasts; GO on >=1.3-fold BubR1 protein rise with no aneuploidy increase - the same readout resolves the form question (testability.json).

### 4. hydroxychloroquine - aneuploidy-selective autophagy blockade, interception

*Why it is here:* This is the only candidate with direct aneuploidy-selective antiproliferative evidence: a phenotypic screen identified chloroquine - alongside AICAR and 17-AAG - as selectively antiproliferative to aneuploid versus euploid cells, the proposed mechanism being exploitation of the proteotoxic and metabolic stress state aneuploid cells depend on ([PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/)). Autophagy inhibition is an active cancer strategy more broadly: chloroquine-class agents sensitise tumours to cytotoxic and antiangiogenic therapy, and combined MAPK-plus-autophagy blockade is in clinical translation ([PMID:23461901](https://pubmed.ncbi.nlm.nih.gov/23461901/), [PMID:34830283](https://pubmed.ncbi.nlm.nih.gov/34830283/)). The MVA hypothesis is interception: lifelong production of new aneuploid cells is the cancer substrate, so preferentially impairing aneuploid-cell proliferation could trim the compartment that seeds the predisposition ([PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/)). Chloroquine and hydroxychloroquine are absent from the PRISM 19Q4 screen, so no pharmacogenomic claim can be made for them in either direction [repo:docs/track2/evidence/prism.json]. The counter-considerations are serious: the selectivity data are cell-line and short-term; aneuploid cancer cells show complex, time-dependent responses to checkpoint perturbation rather than simple vulnerability ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/)); and chronic autophagy blockade touches every tissue that needs proteostasis. Its pediatric label covers only malaria above 31 kg, and irreversible retinal toxicity accumulates with the chronic exposure an interception strategy would require - label facts that cap the rank despite this portfolio's cleanest falsifier.

*Evidence:*

- [preclinical, direct] Direct aneuploidy-selective evidence: a phenotypic screen identified chloroquine - alongside AICAR and 17-AAG - as selectively antiproliferative to aneuploid versus euploid cells; autophagy inhibition is proposed to exploit the proteotoxic/metabolic stress state that aneuploid cells depend on. ([PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/))
- [preclinical, indirect] Autophagy inhibition is an active cancer-therapy strategy: chloroquine-class agents sensitise tumour cells to cytotoxic and antiangiogenic therapy, and combined MAPK + autophagy blockade is under clinical translation in RAS-mutant cancers - supporting plausibility of the autophagy-dependence angle in aneuploid clones. ([PMID:23461901](https://pubmed.ncbi.nlm.nih.gov/23461901/); [PMID:34830283](https://pubmed.ncbi.nlm.nih.gov/34830283/))
- [mechanism, indirect] Disease link: MVA1 mosaicism means a lifelong stream of new aneuploid cells; a drug class that preferentially impairs aneuploid-cell proliferation could, in principle, trim the aneuploid compartment that seeds the cancer-predisposition phenotype. This is the Axis-C interception hypothesis - plausible, untested in MVA. ([PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/); [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/))
- [safety, indirect] Counter-considerations: (i) the selective-kill data are cell-line/short-term; chronic systemic autophagy inhibition affects all tissues including those needing autophagy for quality control in a checkpoint-defective child; (ii) aneuploid cancer cells show complex, time-dependent responses to checkpoint/stress perturbation - not simple vulnerability; (iii) no study has tested CQ/HCQ in a BubR1/MVA model. ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/); [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/))

*Pediatric label facts* (openFDA drug/label set_id 04139607-f7c0-4fe1-a210-ffa5af347d56 (effective 2025-10-09); hydroxychloroquine sulfate tablets): Established in pediatric patients only for malaria treatment and prophylaxis, and only >=31 kg because tablets cannot be divided; NOT established for RA/discoid lupus/SLE in children (quoted label fact). Chloroquine label (set_id 06c69e2b-211b-4746-9f3a-f86d36520570) provides weight-based pediatric malaria dosing. Boxed warning: None on this label.

*Risks specific to this child's phenotype:*

- Retinal toxicity: label warns of irreversible retinal damage related to CUMULATIVE dose and duration, recommending baseline and ongoing retinal exams - the dominant concern for any chronic chemopreventive use in a young child. [repo:openFDA label 04139607]
- Cardiomyopathy and ventricular arrhythmias incl. QT prolongation (fatal cases reported); serious skin reactions (SJS/TEN/DRESS); hematologic toxicity (myelosuppression); renal toxicity/phospholipidosis - relevant given nephrocalcinosis phenotype. [repo:openFDA label 04139607]
- Chronic daily dosing for interception would exceed the cumulative exposure pattern the retinal-toxicity warning is anchored to; any use would need ophthalmologic surveillance from baseline. [repo:openFDA label 04139607]

*What would make us wrong:* We are wrong if the aneuploidy selectivity is a cell-line artefact - the founding screen used engineered trisomic backgrounds, not mosaic SAC-defective cells ([PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/)) - or if chronic autophagy blockade harms quality-control-dependent tissues more than it trims aneuploid clones ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/)). Decisive experiment (T1-T2, 3-6 weeks): CQ/HCQ on the patient's mosaic fibroblasts, which carry an internal euploid control; GO on >=2-fold preferential depletion of the aneuploid fraction, NO-GO on equal euploid and aneuploid toxicity (testability.json).


### 5.4 Adjuncts and the non-drug recommendation

- **sirolimus (backup mTOR senomorphic)** - Same senomorphic mechanism and the same MVA-mouse mTORC1 hook as everolimus ([PMID:26147250](https://pubmed.ncbi.nlm.nih.gov/26147250/), [PMID:26280535](https://pubmed.ncbi.nlm.nih.gov/26280535/), [PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/)), and the engine's top mechanism-aligned candidate - #2 of the 59 that survive the direction layer, #21 of 96 before it, with several evidence-dense but mechanism-neutral entries (palbociclib, glycerin, methenamine) ranked above it [repo:docs/track2/evidence/candidates.json]. It sits behind everolimus on pediatric feasibility alone: its boxed warning names infection and malignancy, and it has no pediatric approval under 13.
- **metformin (senomorphic fallback)** - Fallback if mTOR immunosuppression is disqualifying: it blunts the SASP through IKK/NF-kB ([PMID:23521863](https://pubmed.ncbi.nlm.nih.gov/23521863/)) and has a pediatric type-2-diabetes label from age 10, but its aneuploidy angle is AICAR analogy only ([PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/)) and millimolar-range exposure can itself deregulate BUBR1/MAD2 and induce micronuclei ([PMID:35568294](https://pubmed.ncbi.nlm.nih.gov/35568294/)). The lactic-acidosis boxed warning makes renal function (nephrocalcinosis) the gating safety check; it is absent from the PRISM screen, so no pharmacogenomic claim [repo:docs/track2/evidence/prism.json].
- **aspirin (long-horizon interception adjunct)** - Aspirin selectively eliminated tetraploid cells - the metastable precursor state to aneuploidy - in a chemoprevention screen ([PMID:24516128](https://pubmed.ncbi.nlm.nih.gov/24516128/)), and CAPP2 provides RCT-grade precedent for chemoprevention in a hereditary syndrome, though the benefit was colorectal-cancer-specific in Lynch syndrome ([PMID:32534647](https://pubmed.ncbi.nlm.nih.gov/32534647/)). Chronic pediatric use collides with the label's Reye's-syndrome warning, so it remains a research question carried by the fibroblast tetraploid-pruning assay, not a recommendation.
- **quercetin (only within D+Q)** - The senolytic pair's second half: dasatinib and quercetin clear complementary senescent-cell types ([PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/)), and the human senescent-burden evidence is for the combination ([PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/)). It is a supplement, not an approved drug, so it cannot anchor a candidate alone under the approved-only rule.
- **NR / NMN (Axis-A supplement adjuncts)** - NMN is the actual NAD+ precursor that raised BubR1 abundance and extended lifespan in BubR1-hypomorphic mice ([PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/)), with supportive review-level evidence for NAD supplementation in premature-aging and DNA-repair disease ([PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/)). Neither form is a market-approved drug, so they belong to the MVA Society supplements program rather than the drug leads.
- **structured cancer surveillance (non-drug)** - The most defensible intervention today is not a drug at all: mechanism-guided surveillance for the embryonal tumour spectrum of BUB1B-MVA, following the AACR workshop recommendations for children with genomic-instability disorders ([PMID:39264246](https://pubmed.ncbi.nlm.nih.gov/39264246/)). This recommendation stands independently of every drug hypothesis in the portfolio.

## 6. Considered and rejected

| Considered | Category | Why rejected | Sources |
|---|---|---|---|
| recombinant human growth hormone (somatropin) | contraindicated-by-phenotype | Tempting target for the child's short stature/failure-to-thrive phenotype, but it treats a symptom while stimulating proliferation in a cancer-predisposition syndrome. The evidence is honestly mixed: an earlier Childhood Cancer Survivor Study analysis found GH-treated survivors had an elevated second-neoplasm rate ratio of 2.15 (95% CI 1.3-3.5), whereas a later French CCS cohort (196 GH-treated, ~26y follow-up) found no significant SN increase (non-brain cancer RR 0.7; non-significant meningioma trend with duration). In a child whose mosaic aneuploid clones are under relaxed surveillance, with no GH-safety data specific to genomic-instability syndromes, the precautionary position is to reject: GH's anabolic/mitogenic + IGF-1 anti-apoptotic action is mechanistically pointed at the wrong lever, and benefit (height) is cosmetic relative to the stakes. Stated plainly: the rejection rests on precaution plus mechanism, not on proven harm. | [PMID:15144231](https://pubmed.ncbi.nlm.nih.gov/15144231/); [PMID:16822820](https://pubmed.ncbi.nlm.nih.gov/16822820/); [PMID:32738133](https://pubmed.ncbi.nlm.nih.gov/32738133/); [PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/) |
| navitoclax (ABT-263) | not-approved | Potent BCL-2/BCL-xL senolytic - mechanistically the most direct senolytic after D+Q - but fails the hard rule: market-approved medications only. Additionally causes dose-limiting thrombocytopenia (BCL-xL in platelets), undesirable in a child. | [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/) |
| quercetin (alone) | supplement-adjunct | Not a market-approved drug. Retained only as the adjunct half of the D+Q senolytic pair whose human pilot data exist; it cannot anchor a candidate on its own under the approved-only rule. | [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/); [PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/) |
| fisetin | supplement | Flavonoid senolytic in trials, but not a market-approved medication; excluded by the approved-only rule. Could appear in the MVA Society supplements program outside the drug dossier set. | [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/) |
| nicotinamide riboside / nicotinamide mononucleotide (NR/NMN) | supplement-adjunct | NMN is literally the NAD+ precursor that raised BubR1 abundance in the anchor study - mechanistically the most direct Axis-A agent - but neither form is a market-approved drug. Approved NAD precursors (niacin, niacinamide) carry the dossier instead; NR/NMN remain adjuncts fitting the MVA Society supplements program. | [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/); [PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/) |
| resveratrol | supplement | Co-headliner of the tetraploid-elimination screen (with aspirin) but a supplement, not a medication; also has poor bioavailability. Aspirin carries the dossier for this mechanism. | [PMID:24516128](https://pubmed.ncbi.nlm.nih.gov/24516128/) |
| MPS1 (TTK) inhibitors (e.g. reversine-class), Aurora kinase inhibitors, KIF18A inhibitors | mechanism-opposed | These drugs exist to weaken or exploit the spindle assembly checkpoint and spindle mechanics in cancer. Aneuploid cancer cells are indeed selectively vulnerable to SAC/KIF18A perturbation (Nature 2021: synthetic-lethal aneuploidy-SAC interaction) - but that is a tumour-killing strategy. In an MVA child the residual SAC in NORMAL mosaic cells is what limits new aneuploidy; systemic SAC inhibition would accelerate mis-segregation in every dividing tissue - pharmacologically recreating the disease mechanism. Rejected for preventive/chronic use; the vulnerability may matter later only if a frank malignancy is being treated by oncologists. | [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/); [PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/) |
| p53-pathway inhibition (e.g. pifithrin-class; no approved selective agent) | mechanism-opposed | Proposed by naive reasoning as 'relieve the growth arrest' for failure-to-thrive, but p53 is the brake that limits proliferation of aneuploid cells; disabling it removes the main tumour-suppressive barrier in a syndrome whose cancers emerge from aneuploid clones. Direction is pro-oncogenic - the opposite of the goal. | [PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/); [PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/) |
| antimitotic agents (taxanes, vinca alkaloids, benzimidazole anthelmintics incl. mebendazole) | mechanism-opposed | Spindle-poisons cause chromosome mis-segregation - the exact lesion MVA already produces. Benzimidazoles specifically show aneugenic activity in micronucleus assays. Mebendazole surfaced in the systematic screen (aneuploid-selective killing query) but is rejected on this mechanism. | [PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/); [PMID:7739397](https://pubmed.ncbi.nlm.nih.gov/7739397/) |
| HSP90 inhibitors (17-AAG/tanespimycin and class) | not-approved + class-risk | 17-AAG was one of the three aneuploidy-selective compounds in the founding screen (proteotoxic-stress angle) - but the class never reached approval (development abandoned on toxicity/efficacy), and chaperone inhibition destabilises client kinases broadly. Excluded on the approved-only rule; the selectivity rationale is covered by chloroquine in the HCQ dossier. | [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/) |
| AICAR (5-aminoimidazole-4-carboxamide ribonucleotide) | not-approved | The energy-stress hit in the aneuploidy-selective screen (p53-dependent apoptosis in trisomic MEFs) - mechanistically appealing, but not market-approved. Metformin is the nearest approved energy-stress/AMPK agent and carries the analogy in its dossier. | [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/) |
| APC/C inhibitors (TAME, proTAME) | not-approved + mechanism-opposed | BubR1 restrains APC/C; an APC/C inhibitor sits downstream of the defect and would mimic/amplify checkpoint failure rather than rescue it. Also not approved. | [PMID:22366722](https://pubmed.ncbi.nlm.nih.gov/22366722/) |
| direct SIRT2 activators | not-approved | Pharmacologically the cleanest Axis-A lever (stabilise BubR1 via K668 deacetylation) but no approved agent exists; the feasible proxy is NAD+ repletion (niacin/nicotinamide dossier). Selective SIRT2 INHIBITORS exist but point the wrong way for this disease: the tool compound SirReal2 destabilises BubR1 protein in cells - direct evidence that SIRT2 inhibition (not activation) depletes the checkpoint protein this child already lacks. | [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/); [PMID:25672491](https://pubmed.ncbi.nlm.nih.gov/25672491/); [PMID:38009412](https://pubmed.ncbi.nlm.nih.gov/38009412/) |
| hydroxyurea | mechanism-opposed | Surfaced in the systematic screen. In yeast mutation-accumulation lines it elevated mutation rates broadly with a particularly high occurrence of aneuploidy - the precise phenotype to avoid in MVA. | [PMID:37931001](https://pubmed.ncbi.nlm.nih.gov/37931001/) |
| hematopoietic stem cell transplantation (HSCT) | not-a-drug + adverse-case-evidence | Considered because it could replace a compartment that accumulates aneuploid clones (e.g. marrow). The only published MVA1 HSCT case (11-year-old, MDS with monosomy 7): TCRab/CD19-depleted RIC transplant engrafted but was followed by day +47 graft rejection, prolonged pancytopenia and fatal sepsis (death day +156). Does not address aneuploidy in non-hematopoietic tissues; single-case evidence is adverse. | [PMID:31053147](https://pubmed.ncbi.nlm.nih.gov/31053147/) |
| INK-ATTAC-style inducible senescent-cell ablation (transgenic) | not-a-drug | This is the actual intervention that rescued the BubR1-hypomorph mouse phenotype in Nature 2011 - the scientific anchor for the whole Axis-B hypothesis - listed here explicitly so the record is honest that the anchor intervention is a gene circuit, not a drug. Dasatinib+quercetin is its pharmacologic approximation. | [PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/); [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/) |

## 7. Testability: mapped to the MVA Society's funded research programs

The four programs and what each can measure are taken verbatim from the Society's research pages ([repo:docs/track2/evidence/mva_programs.json]). Each cell gives the readout, the go/no-go threshold, cost tier and time to result.

| Candidate | Worm repurposing screen | Patient fibroblasts | Multi-patient scRNA-seq | Supplements & cell health |
|---|---|---|---|---|
| **dasatinib + quercetin** [repo:testability.json] | embryonic/larval viability, him rate, growth, behavioural tracking; GO: informational only (T1, 2-3 weeks) | SA-beta-gal/p16/p21+ fraction, SASP cytokine panel (IL-6, IL-8, IL-1a), aneuploidy rate (interphase FISH / scDNA-seq), micronuclei; GO: GO if >=50% reduction in senescent-marker fraction with no rise in aneuploidy rate or cytotoxicity to euploid cells; NO-GO if nonselective toxicity (T1, 2-4 weeks) | senescence/SASP module scores; p16 program; GO: GO if SASP modules significantly reduced vs untreated (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **sirolimus** [repo:testability.json] | lifespan, growth, embryonic viability; GO: informational (T1, 3-6 weeks (lifespan assays are slow)) | SASP cytokines, p-S6 (pharmacodynamic), aneuploidy rate, BubR1 protein, growth rate; GO: GO if SASP down >=30% with stable aneuploidy rate and no growth suppression; NO-GO on aneuploidy rise or cytostasis (a growth-retarded child cannot take a growth-suppressing drug) (T1, 2-4 weeks) | HALLMARK_MTORC1_SIGNALING, SASP modules; GO: GO if mTORC1 module significantly reduced (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **everolimus** [repo:testability.json] | lifespan, growth, viability; GO: informational (T1, 3-6 weeks) | SASP cytokines, p-S6, aneuploidy rate, proliferation index, BubR1 level; GO: GO if SASP down >=30%, stable aneuploidy, <20% proliferation slowdown; NO-GO on cytostasis (T1, 2-4 weeks) | mTORC1/SASP modules; GO: GO on significant reduction (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **metformin** [repo:testability.json] | viability, growth, him rate, lifespan; GO: informational (T1, 3-6 weeks) | SASP cytokines (IKK/NF-kB axis per PMID:23521863), micronuclei, aneuploidy rate, p-AMPK, BUBR1/MAD2 expression (per PMID:35568294 caveat); GO: GO if a dose window exists with SASP down AND no micronucleus increase; NO-GO if micronuclei rise within/near clinical exposure (the Lyu 2022 caveat is the whole experiment) (T1, 2-4 weeks) | NF-kB/SASP modules; GO: secondary (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **hydroxychloroquine / chloroquine** [repo:testability.json] | viability, him rate, growth; GO: informational (T1, 2-3 weeks) | fraction of aneuploid vs euploid cells before/after (FISH or scDNA-seq), viability, autophagy markers; GO: GO if aneuploid-fraction reduction >=2-fold preferential vs euploid; NO-GO if no selectivity or broad toxicity (T1-T2, 3-6 weeks) | aneuploid-signature cell fraction; autophagy/proteotoxic modules; GO: GO on aneuploid-signature depletion (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **niacin / nicotinamide (approved NAD+ precursors)** [repo:testability.json] | viability, him rate, growth, lifespan; GO: GO on viability/him improvement (T1, 3-6 weeks) | BubR1 protein level (western/IF), NAD+ level, mitotic timing under nocodazole, aneuploidy rate; GO: GO if BubR1 protein up measurably (e.g. >=1.3-fold) with no aneuploidy rise; head-to-head niacin vs nicotinamide resolves the form question (T1, 2-4 weeks) | progeroid/stress modules; GO: secondary (T2, 6-8 weeks) | cell stability endpoints; GO: program-defined (T1, program-dependent) |
| **aspirin** [repo:testability.json] | viability, him rate; GO: informational (T1, 2-3 weeks) | tetraploid/aneuploid fraction trajectory (FISH/scDNA-seq), apoptosis markers; GO: GO on >=1.5-fold euploid enrichment vs vehicle (T1, 3-5 weeks) | aneuploid-signature fraction; GO: secondary (T2, 6-8 weeks) | -; GO: - (n/a, -) |

Cost tiers - T0: in-silico / literature only, T1: < $5k (bench assays, standard reagents), T2: $5k-50k (sequencing, screens, animal work), T3: > $50k.

**Fibroblast core readouts:**

- aneuploidy rate (interphase FISH panel / scDNA-seq / micronucleus index) - the disease-defining readout; the mosaic culture gives an internal euploid control
- BubR1 protein level (Axis-A pharmacodynamic)
- mitotic timing under nocodazole challenge (functional SAC strength)
- SA-beta-gal / p16 / p21 senescent fraction + SASP cytokines (Axis-B pharmacodynamic)

**Decision logic** [repo:docs/track2/evidence/testability.json]: Fibroblast assays are the decisive tier (T1 cost, disease-relevant cells, internal euploid control, 2-6 weeks). Worm assays are cheap whole-organism confirmation. scRNA-seq quantifies signature reversal. The supplements program is the natural home for NAD-precursor adjuncts. Any candidate showing an INCREASE in aneuploidy rate or micronuclei on patient cells is an automatic NO-GO regardless of other benefits.

## 8. Scalability

- **Any gene, one command.** The engine takes a gene, its seed module and an axis map; nothing in `src/track2/` is BUB1B-specific ([repo:docs/track2/engine.md]). The same run applies directly to the other MVA genes (CEP57, TRIP13, MAD1L1) seeded in the config.
- **Measured, not claimed.** The retrospective benchmark (section 4.2) is the scalability receipt: it runs the identical pipeline on unrelated diseases with known approved repurposings.
- **Offline and reproducible.** Every external response is recorded; `pytest` replays them with zero network.
- **Reusable rigor layer.** `tools/verify_citations.py` is a standalone citation gate any team can drop into a report pipeline.

## 9. Rigor and reproducibility

- `tools/verify_citations.py --offline` over the whole Track 2 tree: **136 distinct citations, 0 unresolved, 0 retracted, 0 title/year mismatches, 30 uncovered claim sentences** (exit 0, 0 network requests).
- 132 Track 2 tests (network-free, recorded fixtures); run with `python -m pytest tests/test_t2_*.py tests/test_track2_*.py tests/test_verify_citations.py`.
- Approval, pediatric-label and boxed-warning facts come from live ChEMBL and openFDA responses recorded in each dossier (`docs/track2/evidence/dossiers/`).
- Decision freeze: benchmark truth and seed genes were committed in `config/track2.yaml` before the engine was run (git history).
- Rebuild this report: `python tools/make_track2_report.py --upload`.

## 10. Limitations

1. **Phase is unknown.** If the two variants were in cis, the null + hypomorph model and axis A would not apply as stated.
2. **N-of-1, no patient-cell data yet.** Every candidate is a mechanistic extrapolation; section 7 is the plan to replace extrapolation with measurement.
3. **The missense allele's residual function is unmeasured.** Axis A assumes the Asn1002Lys protein retains partial function; a fibroblast BubR1 western and nocodazole-arrest assay resolve this first.
4. **Database bias.** Drug-target resources over-represent oncology and well-studied targets; BubR1 itself has no approved direct modulator, so axis A works through upstream regulators.
5. **Cell-line pharmacogenomics is not a child's tissue.** PRISM associations come from cancer lines and are associations, not mechanisms.
6. **Approved is not safe for this child.** Pediatric label facts are quoted, not extrapolated into dosing; the risks are listed per candidate.

## 11. Methods-form answers (Track 2 template, all questions)

**1. Team name** - nikhilpise.

**2. Please describe your approach in detail (how you went from variant/mechanism to candidate medication(s)).** Per-allele mechanism characterization from public data (section 2) defined three therapeutic axes (section 3). Candidates were generated by the engine (section 4) and by a logged systematic literature screen (section 5.1), filtered to approved medicines by code, reconciled into one frozen portfolio, and each lead mapped to a falsifiable experiment (section 7).

**3. Was candidate identification automated, or primarily manual literature review and expert curation?** Hybrid, stated plainly: automated engine ranking from public drug-target databases, plus a curated literature layer built by LLM agents under a hard rule that every claim is resolved against PubMed before inclusion, then reviewed and integrated by the team.

**4. Please describe any manual literature review or expert curation in detail.** Section 5.1 (query log with hit counts and screening decisions), the dossiers in `docs/track2/evidence/dossiers/`, and the citation gate in section 9.

**5. Public only, or proprietary data too?** Solely publicly available databases and literature.

**6. Public data sources.** Open Targets Platform, ChEMBL, DGIdb, STRING, SigCom LINCS (L1000), DepMap PRISM repurposing screen, openFDA drug labels, PubMed/NCBI E-utilities, Crossref, DataCite, UniProt, Ensembl, gnomAD v4, ClinVar, AlphaFold DB, AlphaMissense, OMIM (MVA1 257300), HPO, MVA Society research pages. Versions and access dates are recorded in the evidence files and `docs/track2/engine.md`.

**7. Proprietary data sources.** None.

**8. How did you characterize the variant's mechanism?** Section 2: NMD prediction from the MANE transcript's exon structure, UniProt domain mapping, missense predictors and conservation, AlphaFold structural context, population frequency, ClinVar, a protein language-model score, and the published BUB1B genotype-phenotype literature; phase stated as an assumption.

**9. Time or effort.** About two weeks of part-time work for the analysis and write-up on top of the Track 1 pipeline; the engine reruns in minutes from cache. Compute: a few dollars of Modal credit (`docs/runtime_log.md`).

**10. Method abstract (up to 500 words).** See section 1 (summary), section 8 (scalability) and section 10 (limitations); a standalone 500-word abstract is in `docs/track2/abstract.md`.

**11. GenAI disclosure (required).** Two commercial GenAI products were used (operator-confirmed settings, 2026-10-12): (1) **Cognition Devin Pro**, model SWE-2 Max, Data Controls training opt-out enabled (no training, zero data retention with model providers) - five headless lane agents (mechanism, engine, dossiers, rigor tooling, compute); (2) **Anthropic Claude Code, Claude Pro/Max consumer plan** (Claude Opus 5.5), model-training opt-out enabled, no feedback ever given - lead/orchestrator, integration, report generation, review. Both settings follow the organizers' 2026-09-28 guidance (discussion #2). Only the two published BUB1B variants and the 8 published HPO terms entered any prompt; no patient file was opened in Track 2. Every literature claim an agent produced was machine-resolved against PubMed/Crossref/DataCite before inclusion (section 9). Per-session ledger: `docs/llm_log.md`.

## Acknowledgement

*This work was made possible through the Hackathon, organized by Sage Bionetworks in partnership with the MVA Society, Hugging Face, and BEACON (The Benchmarking, Evaluation, and Assessment Consortium for Science), with prize sponsorship from AWS and Anthropic. We are deeply grateful to the child and their family who generously contributed their data and their story to advance research into this rare disease. We acknowledge their trust in making this Hackathon possible.*

## References

| # | Identifier | Title (as registered) | Year |
|---|---|---|---|
| 1 | [PMID:15475955](https://pubmed.ncbi.nlm.nih.gov/15475955/) | Constitutional aneuploidy and cancer predisposition caused by biallelic mutations in BUB1B. | 2004 |
| 2 | [PMID:20516114](https://pubmed.ncbi.nlm.nih.gov/20516114/) | Molecular causes for BUBR1 dysfunction in the human cancer predisposition syndrome mosaic variegated aneuploidy. | 2010 |
| 3 | [PMID:24825348](https://pubmed.ncbi.nlm.nih.gov/24825348/) | SIRT2 induces the checkpoint kinase BubR1 to increase lifespan. | 2014 |
| 4 | [PMID:23242215](https://pubmed.ncbi.nlm.nih.gov/23242215/) | Increased expression of BubR1 protects against aneuploidy and cancer and extends healthy lifespan. | 2013 |
| 5 | [PMID:22048312](https://pubmed.ncbi.nlm.nih.gov/22048312/) | Clearance of p16Ink4a-positive senescent cells delays ageing-associated disorders. | 2011 |
| 6 | [PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/) | Aneuploidy renders cancer cells vulnerable to mitotic checkpoint inhibition. | 2021 |
| 7 | [DOI:10.1093/nar/gkab1049](https://doi.org/10.1093/nar/gkab1049) | Ensembl 2022 | 2021 |
| 8 | [PMID:9644970](https://pubmed.ncbi.nlm.nih.gov/9644970/) | A rule for termination-codon position within intron-containing genes: when nonsense affects RNA abundance. | 1998 |
| 9 | [PMID:27618451](https://pubmed.ncbi.nlm.nih.gov/27618451/) | The rules and impact of nonsense-mediated mRNA decay in human cancers. | 2016 |
| 10 | [PMID:33207204](https://pubmed.ncbi.nlm.nih.gov/33207204/) | BUBR1 Pseudokinase Domain Promotes Kinetochore PP2A-B56 Recruitment, Spindle Checkpoint Silencing, and Chromosome Alignment. | 2020 |
| 11 | [PMID:16411201](https://pubmed.ncbi.nlm.nih.gov/16411201/) | Monoallelic BUB1B mutations and defective mitotic-spindle checkpoint in seven families with premature chromatid separation (PCS) syndrome. | 2006 |
| 12 | [PMID:23079597](https://pubmed.ncbi.nlm.nih.gov/23079597/) | Integration of kinase and phosphatase activities by BUBR1 ensures formation of stable kinetochore-microtubule attachments. | 2012 |
| 13 | [PMID:23345399](https://pubmed.ncbi.nlm.nih.gov/23345399/) | Direct binding between BubR1 and B56-PP2A phosphatase complexes regulate mitotic progression. | 2013 |
| 14 | [PMID:20123995](https://pubmed.ncbi.nlm.nih.gov/20123995/) | Proliferation of aneuploid human cells is limited by a p53-dependent mechanism. | 2010 |
| 15 | [PMID:28633018](https://pubmed.ncbi.nlm.nih.gov/28633018/) | Chromosome Mis-segregation Generates Cell-Cycle-Arrested Cells with Complex Karyotypes that Are Eliminated by the Immune System. | 2017 |
| 16 | [PMID:34216545](https://pubmed.ncbi.nlm.nih.gov/34216545/) | Proteostasis failure and mitochondrial dysfunction leads to aneuploidy-induced senescence. | 2021 |
| 17 | [PMID:18516091](https://pubmed.ncbi.nlm.nih.gov/18516091/) | Opposing roles for p16Ink4a and p19Arf in senescence and ageing caused by BubR1 insufficiency. | 2008 |
| 18 | [PMID:15208629](https://pubmed.ncbi.nlm.nih.gov/15208629/) | BubR1 insufficiency causes early onset of aging-associated phenotypes and infertility in mice. | 2004 |
| 19 | [PMID:23300461](https://pubmed.ncbi.nlm.nih.gov/23300461/) | Reduced life- and healthspan in mice carrying a mono-allelic BubR1 MVA mutation. | 2012 |
| 20 | [PMID:31081598](https://pubmed.ncbi.nlm.nih.gov/31081598/) | Long-term remission of bilateral Wilms tumors that developed from premature separation of chromatids/mosaic variegated aneuploidy syndrome due to bilateral nephrectomy and peritoneal dialysis. | 2019 |
| 21 | [PMID:21190457](https://pubmed.ncbi.nlm.nih.gov/21190457/) | Homozygous BUB1B mutation and susceptibility to gastrointestinal neoplasia. | 2010 |
| 22 | [PMID:31659324](https://pubmed.ncbi.nlm.nih.gov/31659324/) | The impact of nonsense-mediated mRNA decay on genetic disease, gene editing and cancer immunotherapy. | 2019 |
| 23 | [PMID:29165669](https://pubmed.ncbi.nlm.nih.gov/29165669/) | ClinVar: improving access to variant interpretations and supporting evidence. | 2018 |
| 24 | [PMID:19407811](https://pubmed.ncbi.nlm.nih.gov/19407811/) | BubR1 acetylation at prometaphase is required for modulating APC/C activity and timing of mitosis. | 2009 |
| 25 | [PMID:23602569](https://pubmed.ncbi.nlm.nih.gov/23602569/) | p21 both attenuates and drives senescence and aging in BubR1 progeroid mice. | 2013 |
| 26 | [PMID:33505027](https://pubmed.ncbi.nlm.nih.gov/33505027/) | Whole-genome doubling confers unique genetic vulnerabilities on tumour cells. | 2021 |
| 27 | [PMID:30500870](https://pubmed.ncbi.nlm.nih.gov/30500870/) | Growth Hormone's Links to Cancer. | 2019 |
| 28 | [PMID:32738133](https://pubmed.ncbi.nlm.nih.gov/32738133/) | Influence of growth hormone therapy on the occurrence of a second neoplasm in survivors of childhood cancer. | 2020 |
| 29 | [PMID:21047224](https://pubmed.ncbi.nlm.nih.gov/21047224/) | Everolimus for subependymal giant-cell astrocytomas in tuberous sclerosis. | 2010 |
| 30 | [PMID:21410393](https://pubmed.ncbi.nlm.nih.gov/21410393/) | Efficacy and safety of sirolimus in lymphangioleiomyomatosis. | 2011 |
| 31 | [PMID:29899452](https://pubmed.ncbi.nlm.nih.gov/29899452/) | Targeted therapy in patients with PIK3CA-related overgrowth syndrome. | 2018 |
| 32 | [PMID:25405392](https://pubmed.ncbi.nlm.nih.gov/25405392/) | Atenolol versus losartan in children and young adults with Marfan's syndrome. | 2014 |
| 33 | [PMID:16885550](https://pubmed.ncbi.nlm.nih.gov/16885550/) | Switching from insulin to oral sulfonylureas in patients with diabetes due to Kir6.2 mutations. | 2006 |
| 34 | [PMID:22047557](https://pubmed.ncbi.nlm.nih.gov/22047557/) | A CFTR potentiator in patients with cystic fibrosis and the G551D mutation. | 2011 |
| 35 | [PMID:31862249](https://pubmed.ncbi.nlm.nih.gov/31862249/) | Fenfluramine hydrochloride for the treatment of seizures in Dravet syndrome: a randomised, double-blind, placebo-controlled trial. | 2019 |
| 36 | [PMID:36583535](https://pubmed.ncbi.nlm.nih.gov/36583535/) | Reduction of New Heterotopic Ossification (HO) in the Open-Label, Phase 3 MOVE Trial of Palovarotene for Fibrodysplasia Ossificans Progressiva (FOP). | 2023 |
| 37 | [PMID:22158718](https://pubmed.ncbi.nlm.nih.gov/22158718/) | Use of acetazolamide in sulfonamide-allergic patients with neurologic channelopathies. | 2012 |
| 38 | [PMID:39174244](https://pubmed.ncbi.nlm.nih.gov/39174244/) | The episodic ataxias. | 2024 |
| 39 | [PMID:27834756](https://pubmed.ncbi.nlm.nih.gov/27834756/) | Oral pharmacological chaperone migalastat compared with enzyme replacement therapy in Fabry disease: 18-month results from the randomised phase III ATTRACT study. | 2017 |
| 40 | [DOI:10.1038/s43018-019-0018-6](https://doi.org/10.1038/s43018-019-0018-6) | Discovering the anticancer potential of non-oncology drugs by systematic viability profiling | 2020 |
| 41 | [DOI:10.1038/s41586-020-03114-6](https://doi.org/10.1038/s41586-020-03114-6) | Aneuploidy renders cancer cells vulnerable to mitotic checkpoint inhibition | 2021 |
| 42 | [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/) | The Achilles' heel of senescent cells: from transcriptome to senolytic drugs. | 2015 |
| 43 | [PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/) | Senolytics decrease senescent cells in humans: Preliminary report from a clinical trial of Dasatinib plus Quercetin in individuals with diabetic kidney disease. | 2019 |
| 44 | [PMID:30616998](https://pubmed.ncbi.nlm.nih.gov/30616998/) | Senolytics in idiopathic pulmonary fibrosis: Results from a first-in-human, open-label, pilot study. | 2019 |
| 45 | [PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/) | Mosaic variegated aneuploidy in development, ageing and cancer. | 2024 |
| 46 | [PMID:31738183](https://pubmed.ncbi.nlm.nih.gov/31738183/) | BubR1 allelic effects drive phenotypic heterogeneity in mosaic-variegated aneuploidy progeria syndrome. | 2020 |
| 47 | [PMID:26147250](https://pubmed.ncbi.nlm.nih.gov/26147250/) | MTOR regulates the pro-tumorigenic senescence-associated secretory phenotype by promoting IL1A translation. | 2015 |
| 48 | [PMID:26280535](https://pubmed.ncbi.nlm.nih.gov/26280535/) | mTOR regulates MAPKAPK2 translation to control the senescence-associated secretory phenotype. | 2015 |
| 49 | [PMID:23158522](https://pubmed.ncbi.nlm.nih.gov/23158522/) | Efficacy and safety of everolimus for subependymal giant cell astrocytomas associated with tuberous sclerosis complex (EXIST-1): a multicentre, randomised, placebo-controlled phase 3 trial. | 2013 |
| 50 | [PMID:38009412](https://pubmed.ncbi.nlm.nih.gov/38009412/) | SIRT2 transgenic over-expression does not impact lifespan in mice. | 2023 |
| 51 | [PMID:25672491](https://pubmed.ncbi.nlm.nih.gov/25672491/) | Selective Sirt2 inhibition by ligand-induced rearrangement of the active site. | 2015 |
| 52 | [PMID:12297502](https://pubmed.ncbi.nlm.nih.gov/12297502/) | Inhibition of silencing and accelerated aging by nicotinamide, a putative negative regulator of yeast sir2 and human SIRT1. | 2002 |
| 53 | [PMID:25285631](https://pubmed.ncbi.nlm.nih.gov/25285631/) | Deacetylation of the mitotic checkpoint protein BubR1 at lysine 250 by SIRT2 and subsequent effects on BubR1 degradation during the prometaphase/anaphase transition. | 2014 |
| 54 | [PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/) | Promising Results With NAD Supplementation in Rare Diseases With Premature Aging and DNA Damage. | 2026 |
| 55 | [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/) | Identification of aneuploidy-selective antiproliferation compounds. | 2011 |
| 56 | [PMID:23461901](https://pubmed.ncbi.nlm.nih.gov/23461901/) | Autophagy inhibition sensitizes colon cancer cells to antiangiogenic and cytotoxic therapy. | 2013 |
| 57 | [PMID:34830283](https://pubmed.ncbi.nlm.nih.gov/34830283/) | Clinical Translation of Combined MAPK and Autophagy Inhibition in RAS Mutant Cancer. | 2021 |
| 58 | [PMID:23521863](https://pubmed.ncbi.nlm.nih.gov/23521863/) | Metformin inhibits the senescence-associated secretory phenotype by interfering with IKK/NF-κB activation. | 2013 |
| 59 | [PMID:35568294](https://pubmed.ncbi.nlm.nih.gov/35568294/) | High-dose metformin induces a low-glucose dependent genotoxic stress. | 2022 |
| 60 | [PMID:24516128](https://pubmed.ncbi.nlm.nih.gov/24516128/) | Resveratrol and aspirin eliminate tetraploid cells for anticancer chemoprevention. | 2014 |
| 61 | [PMID:32534647](https://pubmed.ncbi.nlm.nih.gov/32534647/) | Cancer prevention with aspirin in hereditary colorectal cancer (Lynch syndrome), 10-year follow-up and registry-based 20-year data in the CAPP2 study: a double-blind, randomised, placebo-controlled trial. | 2020 |
| 62 | [PMID:39264246](https://pubmed.ncbi.nlm.nih.gov/39264246/) | Update on Recommendations for Cancer Screening and Surveillance in Children with Genomic Instability Disorders. | 2024 |
| 63 | [PMID:15144231](https://pubmed.ncbi.nlm.nih.gov/15144231/) | Cancer risk following growth hormone use in childhood: implications for current practice. | 2004 |
| 64 | [PMID:16822820](https://pubmed.ncbi.nlm.nih.gov/16822820/) | Growth hormone treatment and risk of second neoplasms in the childhood cancer survivor. | 2006 |
| 65 | [PMID:7739397](https://pubmed.ncbi.nlm.nih.gov/7739397/) | Clastogenic and aneugenic effects of three benzimidazole derivatives in the in vitro micronucleus test using human lymphocytes. | 1995 |
| 66 | [PMID:22366722](https://pubmed.ncbi.nlm.nih.gov/22366722/) | An APC/C inhibitor stabilizes cyclin B1 by prematurely terminating ubiquitination. | 2012 |
| 67 | [PMID:37931001](https://pubmed.ncbi.nlm.nih.gov/37931001/) | Genome instability footprint under rapamycin and hydroxyurea treatments. | 2023 |
| 68 | [PMID:31053147](https://pubmed.ncbi.nlm.nih.gov/31053147/) | Hematopoietic stem cell transplantation in a patient with type 1 mosaic variegated aneuploidy syndrome. | 2019 |
