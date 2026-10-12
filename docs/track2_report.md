# Rescue, Remove, Intercept: a testable, approved-drug repurposing portfolio for BUB1B mosaic variegated aneuploidy - and the open engine that built it

**Team:** nikhilpise - MVA Hackathon 2026, Track 2 (Drug Repurposing)
**Repository:** https://github.com/nikhilpravinpise/MVA-Hackathon-2026 (all code, configs, evidence files and tests)
**Report generated:** 2026-10-12 from commit `641fb3e` by `tools/make_track2_report.py` from `docs/track2/evidence/` - no number in this report is hand-typed.

> **This is a hypothesis-generation document for research follow-up, not medical advice.** Every candidate below is an existing approved medicine proposed for laboratory testing first; none should be given to any child on the strength of this report.

## For the family and patient advocates (plain language)

The child's genome carries two changes in a gene called *BUB1B*. This gene makes a protein, BubR1, that acts like a quality-control inspector during cell division: it holds the process until every chromosome is properly attached, so each new cell gets the right number. One of the child's copies is predicted to make no protein at all; the other makes a protein that is probably present but weaker or less stable. With too little working BubR1, some cells end up with the wrong number of chromosomes - this is "mosaic variegated aneuploidy" (MVA).

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

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

### 4.2 Does the engine find known answers? (retrospective benchmark)

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

### 4.3 Independent computational evidence

**Aneuploidy pharmacogenomics (PRISM repurposing screen x cell-line aneuploidy).** Highly aneuploid cancer cells have distinct drug vulnerabilities ([PMID:33505028](https://pubmed.ncbi.nlm.nih.gov/33505028/)); we asked which *approved* drugs preferentially inhibit more-aneuploid cell lines, controlling for lineage.

| Drug | MOA | beta (sensitivity ~ aneuploidy) | q (BH) | n lines |
|---|---|---|---|---|

Full table and positive controls: [repo:docs/track2/evidence/prism.json].

**Protein language-model effect of p.Asn1002Lys (ESM-2 masked-marginal score, calibrated on BUB1B ClinVar/gnomAD missense).**

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

## 5. The candidate portfolio

### 5.1 Systematic literature screen

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

### 5.2 Ranked shortlist

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

"Evidence grade" is an honesty label for the distance between the evidence and this child's use case, not clinical readiness: no MVA-specific drug-treatment study exists, so nothing is graded higher than moderate.

### 5.3 Lead candidates in detail

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

### 5.4 Adjuncts and the non-drug recommendation

> *PENDING - input artifact not yet produced; this section fills on regeneration.*

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
| **dasatinib + quercetin** | embryonic/larval viability, him rate, growth, behavioural tracking; GO: informational only (T1, 2-3 weeks) | SA-beta-gal/p16/p21+ fraction, SASP cytokine panel (IL-6, IL-8, IL-1a), aneuploidy rate (interphase FISH / scDNA-seq), micronuclei; GO: GO if >=50% reduction in senescent-marker fraction with no rise in aneuploidy rate or cytotoxicity to euploid cells; NO-GO if nonselective toxicity (T1, 2-4 weeks) | senescence/SASP module scores; p16 program; GO: GO if SASP modules significantly reduced vs untreated (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **sirolimus** | lifespan, growth, embryonic viability; GO: informational (T1, 3-6 weeks (lifespan assays are slow)) | SASP cytokines, p-S6 (pharmacodynamic), aneuploidy rate, BubR1 protein, growth rate; GO: GO if SASP down >=30% with stable aneuploidy rate and no growth suppression; NO-GO on aneuploidy rise or cytostasis (a growth-retarded child cannot take a growth-suppressing drug) (T1, 2-4 weeks) | HALLMARK_MTORC1_SIGNALING, SASP modules; GO: GO if mTORC1 module significantly reduced (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **everolimus** | lifespan, growth, viability; GO: informational (T1, 3-6 weeks) | SASP cytokines, p-S6, aneuploidy rate, proliferation index, BubR1 level; GO: GO if SASP down >=30%, stable aneuploidy, <20% proliferation slowdown; NO-GO on cytostasis (T1, 2-4 weeks) | mTORC1/SASP modules; GO: GO on significant reduction (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **metformin** | viability, growth, him rate, lifespan; GO: informational (T1, 3-6 weeks) | SASP cytokines (IKK/NF-kB axis per PMID:23521863), micronuclei, aneuploidy rate, p-AMPK, BUBR1/MAD2 expression (per PMID:35568294 caveat); GO: GO if a dose window exists with SASP down AND no micronucleus increase; NO-GO if micronuclei rise within/near clinical exposure (the Lyu 2022 caveat is the whole experiment) (T1, 2-4 weeks) | NF-kB/SASP modules; GO: secondary (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **hydroxychloroquine / chloroquine** | viability, him rate, growth; GO: informational (T1, 2-3 weeks) | fraction of aneuploid vs euploid cells before/after (FISH or scDNA-seq), viability, autophagy markers; GO: GO if aneuploid-fraction reduction >=2-fold preferential vs euploid; NO-GO if no selectivity or broad toxicity (T1-T2, 3-6 weeks) | aneuploid-signature cell fraction; autophagy/proteotoxic modules; GO: GO on aneuploid-signature depletion (T2, 6-8 weeks) | -; GO: - (n/a, -) |
| **niacin / nicotinamide (approved NAD+ precursors)** | viability, him rate, growth, lifespan; GO: GO on viability/him improvement (T1, 3-6 weeks) | BubR1 protein level (western/IF), NAD+ level, mitotic timing under nocodazole, aneuploidy rate; GO: GO if BubR1 protein up measurably (e.g. >=1.3-fold) with no aneuploidy rise; head-to-head niacin vs nicotinamide resolves the form question (T1, 2-4 weeks) | progeroid/stress modules; GO: secondary (T2, 6-8 weeks) | cell stability endpoints; GO: program-defined (T1, program-dependent) |
| **aspirin** | viability, him rate; GO: informational (T1, 2-3 weeks) | tetraploid/aneuploid fraction trajectory (FISH/scDNA-seq), apoptosis markers; GO: GO on >=1.5-fold euploid enrichment vs vehicle (T1, 3-5 weeks) | aneuploid-signature fraction; GO: secondary (T2, 6-8 weeks) | -; GO: - (n/a, -) |

Cost tiers - T0: in-silico / literature only, T1: < $5k (bench assays, standard reagents), T2: $5k-50k (sequencing, screens, animal work), T3: > $50k.

**Fibroblast core readouts:**

- aneuploidy rate (interphase FISH panel / scDNA-seq / micronucleus index) - the disease-defining readout; the mosaic culture gives an internal euploid control
- BubR1 protein level (Axis-A pharmacodynamic)
- mitotic timing under nocodazole challenge (functional SAC strength)
- SA-beta-gal / p16 / p21 senescent fraction + SASP cytokines (Axis-B pharmacodynamic)

**Decision logic:** Fibroblast assays are the decisive tier (T1 cost, disease-relevant cells, internal euploid control, 2-6 weeks). Worm assays are cheap whole-organism confirmation. scRNA-seq quantifies signature reversal. The supplements program is the natural home for NAD-precursor adjuncts. Any candidate showing an INCREASE in aneuploidy rate or micronuclei on patient cells is an automatic NO-GO regardless of other benefits.

## 8. Scalability

- **Any gene, one command.** The engine takes a gene, its seed module and an axis map; nothing in `src/track2/` is BUB1B-specific ([repo:docs/track2/engine.md]). The same run applies directly to the other MVA genes (CEP57, TRIP13, MAD1L1) seeded in the config.
- **Measured, not claimed.** The retrospective benchmark (section 4.2) is the scalability receipt: it runs the identical pipeline on unrelated diseases with known approved repurposings.
- **Offline and reproducible.** Every external response is recorded; `pytest` replays them with zero network.
- **Reusable rigor layer.** `tools/verify_citations.py` is a standalone citation gate any team can drop into a report pipeline.

## 9. Rigor and reproducibility

- `tools/verify_citations.py --offline` over the whole Track 2 tree: **116 distinct citations, 0 unresolved, 0 retracted, 0 title/year mismatches, 18 uncovered claim sentences** (exit 0, 0 network requests).
- 79 Track 2 tests (network-free, recorded fixtures); run with `python -m pytest tests/test_t2_*.py tests/test_track2_*.py tests/test_verify_citations.py`.
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
| 29 | [PMID:15144231](https://pubmed.ncbi.nlm.nih.gov/15144231/) | Cancer risk following growth hormone use in childhood: implications for current practice. | 2004 |
| 30 | [PMID:16822820](https://pubmed.ncbi.nlm.nih.gov/16822820/) | Growth hormone treatment and risk of second neoplasms in the childhood cancer survivor. | 2006 |
| 31 | [PMID:39169218](https://pubmed.ncbi.nlm.nih.gov/39169218/) | Mosaic variegated aneuploidy in development, ageing and cancer. | 2024 |
| 32 | [PMID:25754370](https://pubmed.ncbi.nlm.nih.gov/25754370/) | The Achilles' heel of senescent cells: from transcriptome to senolytic drugs. | 2015 |
| 33 | [PMID:31542391](https://pubmed.ncbi.nlm.nih.gov/31542391/) | Senolytics decrease senescent cells in humans: Preliminary report from a clinical trial of Dasatinib plus Quercetin in individuals with diabetic kidney disease. | 2019 |
| 34 | [PMID:41436848](https://pubmed.ncbi.nlm.nih.gov/41436848/) | Promising Results With NAD Supplementation in Rare Diseases With Premature Aging and DNA Damage. | 2026 |
| 35 | [PMID:24516128](https://pubmed.ncbi.nlm.nih.gov/24516128/) | Resveratrol and aspirin eliminate tetraploid cells for anticancer chemoprevention. | 2014 |
| 36 | [PMID:21315436](https://pubmed.ncbi.nlm.nih.gov/21315436/) | Identification of aneuploidy-selective antiproliferation compounds. | 2011 |
| 37 | [PMID:7739397](https://pubmed.ncbi.nlm.nih.gov/7739397/) | Clastogenic and aneugenic effects of three benzimidazole derivatives in the in vitro micronucleus test using human lymphocytes. | 1995 |
| 38 | [PMID:22366722](https://pubmed.ncbi.nlm.nih.gov/22366722/) | An APC/C inhibitor stabilizes cyclin B1 by prematurely terminating ubiquitination. | 2012 |
| 39 | [PMID:25672491](https://pubmed.ncbi.nlm.nih.gov/25672491/) | Selective Sirt2 inhibition by ligand-induced rearrangement of the active site. | 2015 |
| 40 | [PMID:38009412](https://pubmed.ncbi.nlm.nih.gov/38009412/) | SIRT2 transgenic over-expression does not impact lifespan in mice. | 2023 |
| 41 | [PMID:37931001](https://pubmed.ncbi.nlm.nih.gov/37931001/) | Genome instability footprint under rapamycin and hydroxyurea treatments. | 2023 |
| 42 | [PMID:31053147](https://pubmed.ncbi.nlm.nih.gov/31053147/) | Hematopoietic stem cell transplantation in a patient with type 1 mosaic variegated aneuploidy syndrome. | 2019 |
| 43 | [PMID:23521863](https://pubmed.ncbi.nlm.nih.gov/23521863/) | Metformin inhibits the senescence-associated secretory phenotype by interfering with IKK/NF-κB activation. | 2013 |
| 44 | [PMID:35568294](https://pubmed.ncbi.nlm.nih.gov/35568294/) | High-dose metformin induces a low-glucose dependent genotoxic stress. | 2022 |
