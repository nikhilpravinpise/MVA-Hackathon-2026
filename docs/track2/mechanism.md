# Track 2 - Variant mechanism characterization (lane L1)

Quantified per-allele mechanism for the proband's biallelic `BUB1B`
genotype. **Every number in this document is produced by
`tools/t2_mechanism.py`** from live public APIs (Ensembl REST, Ensembl VEP,
UniProt, gnomAD GraphQL, ClinVar E-utilities, AlphaFold DB, NCBI
E-utilities, Crossref) and written to
`docs/track2/evidence/mechanism.json` (schema `t2.mechanism/1`). Raw API
responses are recorded under `tests/fixtures/track2/mechanism/`; the whole
analysis replays offline via `python tools/t2_mechanism.py --replay`.
Citations are resolved live (esummary/Crossref) - unresolved identifiers
fail the build rather than slip through.

Genotype under consideration (already published in the Track 1 report):
`chr15:40209701 T>G` (c.2210T>G, p.Leu737Ter) + `chr15:40220612 T>G`
(c.3006T>G, p.Asn1002Lys) on MANE transcript ENST00000287598.11 /
NM_001211.6, protein UniProt O60566 (1050 aa).

## 1. Allele A - p.Leu737Ter: predicted null (loss of function)

**Exon location.** The variant sits in exon 17 of 23 (ENSE00001029409,
chr15:40209635-40209775) of the 23-exon canonical transcript. VEP
consequence on MANE: `stop_gained`, codons `tTa>tGa`, CDS 2210,
protein 737 (HIGH impact).

**NMD prediction.** The premature termination codon (codon 737, first
nucleotide at spliced-transcript offset 2361) lies **748 nt upstream of
the last exon-exon junction** (junction at spliced offset 3109 between
exons 22 and 23), with six downstream junctions. The canonical rule -
PTCs >50-55 nt upstream of the terminal exon-exon junction trigger
nonsense-mediated decay (PMID:9644970; PMID:27618451) - therefore
predicts **degradation of the mutant mRNA by NMD**: a null allele at the
expression level, matching the NMD-confirmed truncating alleles reported
in PCS/MVA patients (PMID:16411201).

**If any transcript escapes NMD**, the product retains only residues
1-736: **314 residues lost (29.9% of the 1050-aa protein)** including the
entire C-terminal kinase-like domain (UniProt 766-1050), the 772-780
binding region, active-site residue 882, and the PLK1-regulated
phosphoacceptors T792 and T1008 - while N-terminal CDC20-interaction
elements (KEN boxes, TPR, KNL1-binding 152-185, D-box 224-232), the K250
acetylation site, caspase sites 579/610 and the KARD phospho-region
(S670/S676) are retained (PMID:23079597; PMID:23345399; DOI gkae1010
UniProt). Such a fragment could bind CDC20 but could not support the
pseudokinase-domain functions (kinetochore PP2A-B56 recruitment,
checkpoint silencing, alignment; PMID:33207204).

**Population / clinical databases.** gnomAD v4: exomes 115/1,461,846
alleles (AF 7.9e-5), genomes 5/152,174 (AF 3.3e-5), no homozygotes -
ultra-rare, compatible with a deleterious germline allele (PMID:32461654).
ClinVar VCV000533901 records exactly this variant (NM_001211.6:c.2210T>G)
as **Pathogenic/Likely pathogenic** for *Mosaic variegated aneuploidy
syndrome 1* (OMIM:257300), multiple submitters, no conflicts
(PMID:29165669).

## 2. Allele B - p.Asn1002Lys: predicted hypomorph (destabilising missense)

**Exon location.** Exon 23 of 23 - the last exon (ENSE00001948417). A
nonsense allele here would escape NMD; as a missense substitution the
transcript is stable and a full-length protein is produced.

**Domain context.** Residue 1002 lies inside the C-terminal
kinase-like/pseudokinase domain (UniProt 766-1050), six residues from
PLK1 phosphosite T1008. Vertebrate BUBR1 is an unusual pseudokinase:
the catalytic triad is retained but catalysis is dispensable for
segregation, while ATP-interacting residues are required for
conformational stability (PMID:22698286). The pseudokinase domain itself
is needed for KARD phosphorylation and PP2A-B56 recruitment, checkpoint
silencing and chromosome alignment (PMID:33207204) - so a lesion here
attacks the *attachment-error-correction* arm, not a catalytic centre.

**Predictor ensemble (VEP, MANE transcript):**

| Predictor | Value | Call |
|---|---|---|
| AlphaMissense | 0.9229 | likely_pathogenic (PMID:37733863) |
| SIFT | 0.01 | deleterious |
| PolyPhen-2 | 0.997 | probably_damaging |
| REVEL | 0.472 | moderate - below common 0.5-0.75 support thresholds |
| CADD | raw 4.167, phred 24.5 | ~top 1% genome-wide |
| phyloP (470-way mammalian) | 5.115 | strongly constrained residue |

The ensemble is honestly stated: direction is consistently deleterious,
but REVEL is middling and the exact-missense ClinVar record is thin (see
uncertainties).

**Structural context (AlphaFold DB v6 model, parsed locally).** pLDDT at
N1002 = 91.06 (high confidence). The residue has 27 residues within 8 A
(all-atom) / 8 by CA - a contact number at the 53.7th percentile of the
pseudokinase domain, i.e. a **partially packed surface site** on the
C-lobe near the C-terminus. Introducing a charged Lys here plausibly
perturbs local packing rather than ablating a binding hot-spot -
consistent with the *instability* mechanism below, not a clean catalytic
knockout (DOI gkad1011 AlphaFold DB).

**Mechanistic class.** Suijkerbuijk et al. showed that MVA missense
alleles in or near the kinase domain characteristically produce
**high-turnover, unstable protein**; combined with absent transcript from
the truncating partner allele, total BUBR1 abundance collapses
(PMID:20516114). N1002K fits this class exactly. >50% reduction of
BubR1 expression/activity is sufficient for the PCS/MVA phenotype
(PMID:16411201), so the genotype predicts BubR1 output from effectively a
single, partially unstable allele.

**Population / clinical databases.** gnomAD v4: exomes **1/1,461,878**
alleles (AF 6.8e-7), absent from genomes. ClinVar holds **no record for
c.3006T>G itself**; the identical protein change via c.3006T>A
(VCV004600147) is a single-submitter **VUS**. The allele is effectively
novel - consistent with the expectation that such alleles arise and are
selected against rather than circulating (PMID:32461654; PMID:29165669).

## 3. Genotype interpretation

The pair is the **canonical MVA1 pattern: one null + one hypomorphic
allele**. In published biallelic cases a missense always pairs with a
truncating allele; completely truncating genotypes are effectively unseen
(lethal), and even single-allele carriers show mitotic defects and reduced
lifespan in mouse models (PMID:15475955; PMID:20516114; PMID:23300461).
UniProt's own curated MVA1 variants (550, 814, 844, 909, 921, 1012) are
all missense recorded "heterozygous compound with nonsense mutation"
(PMID:15475955). The proband fits this exactly, and the phenotype
constellation (constitutional aneuploidy -> cancer predisposition,
growth failure, recurrent miscarriage) fits the disease mechanism
(PMID:15475955).

**Phase caveat (stated plainly).** Phase is **UNKNOWN** - Track 1 found 0
spanning reads. The in-trans configuration is *inferred* from the MVA1
genotype pattern plus phenotype fit, not observed. It would be resolved
by parental testing or long-read/long-range phasing. If the variants were
in-cis, the remaining allele would be wild-type and the mechanistic model
below would not apply - this is the single most consequential open
question and is carried as uncertainty `u1` in mechanism.json.

## 4. Pathway chain (each arrow evidence-graded)

| Step | Claim | Evidence |
|---|---|---|
| genotype -> dosage | NMD-null + unstable missense leaves BubR1 output at roughly one partially-functional allele; >50% loss suffices for disease | human cells (PMID:16411201, 20516114) |
| dosage -> checkpoint/attachment | Low BubR1 weakens the spindle-assembly checkpoint and KARD-dependent PP2A-B56 recruitment that corrects attachment errors | human cells + cell biology (PMID:20516114, 23079597, 23345399) |
| -> mis-segregation | Uncorrected errors produce constitutional mosaic whole-chromosome gains/losses (MVA definition) | human (PMID:15475955, 20516114) |
| -> cellular response | Aneuploid daughters arrest via p53/p21, acquire proteotoxic stress and p16-effector senescence, flag for immune clearance | cell + fly + mouse (PMID:20123995, 28633018, 34216545, 18516091) |
| -> organism outcomes | Chronic aneuploidy + senescence -> growth failure, skeletal-muscle wasting, progeroid decline; rare escaping clones -> childhood cancer (rhabdomyosarcoma, Wilms; adult GI on milder genotypes) | human + mouse (PMID:15208629, 23300461, 15475955, 31081598, 21190457) |

Notable nuance held in the JSON: p53/p21 is not merely a brake - in
BubR1-insufficient mice it actively protects muscle and fat from
p16-mediated progenitor senescence (PMID:23602569), which sharpens the
contraindication below.

## 5. Therapeutic implications (feeding lanes L2/L3)

1. **Residual-allele rescue** [repo:docs/track2/evidence/mechanism.json] -
   the missense allele is the only functional
   copy; raising its abundance/stability is disease-modifying. BubR1 is
   pharmacologically tractable: SIRT2 maintains BubR1 (K668
   deacetylation; falls with age-related NAD+ decline; NMN or SIRT2
   upregulation raises BubR1 in vivo - PMID:24825348), K250 acetylation
   by PCAF blocks ubiquitin-dependent BubR1 degradation (PMID:19407811),
   and transgenic BubR1 overexpression corrects checkpoint and attachment
   defects, suppresses aneuploidy and tumorigenesis, extends healthspan
   (PMID:23242215). Since kinase-domain MVA missense products are
   unstable (PMID:20516114), proteostasis/stability interventions target
   the precise deficit.
2. **Damage mitigation (senescence)** - clearing p16+ senescent cells in
   BubR1 progeroid mice delayed and attenuated tissue dysfunction,
   including skeletal muscle and fat (PMID:22048312, 18516091).
3. **Aneuploid-clone control** - natural immune clearance of complex
   karyotypes (PMID:28633018); if malignancy emerges, aneuploid tumour
   cells carry selective vulnerabilities (SAC dependency, KIF18A;
   PMID:33505028, 33505027).
4. **Cancer surveillance** - mechanism predicts embryonal
   rhabdomyosarcoma and Wilms tumour risk plus later GI neoplasia;
   surveillance is justified regardless of drug choice (PMID:15475955,
   31081598, 21190457).

## 6. Mechanism-derived contraindications

- **SAC/MPS1/KIF18A inhibitors** - systemic checkpoint weakening adds
  mis-segregation on an already-weak checkpoint. Nuance: the same class
  selectively kills aneuploid *cancer* cells - a therapeutic option if a
  tumour is established, contraindicated prophylactically
  (PMID:33505028, 33505027, 20516114).
- **p53 suppression** - removes the brake on aneuploid-clone propagation
  and the protective effect on muscle/fat (PMID:20123995, 23602569).
- **Growth hormone for short stature** - guidance flags caution in
  chromosomal-breakage/DNA-repair syndromes owing to malignancy risk;
  counter-evidence: a later French childhood-cancer-survivor cohort (196
  GH-treated, ~26 y follow-up) found no significant second-neoplasm
  increase on GH, where the larger CCSS analysis did report an elevated
  rate ratio, so this is precautionary and the evidence is mixed, stated
  as such (PMID:30500870, 32738133, 16822820).
- **Antimitotic/aneugen exposures** - chronic mis-segregation inducers
  run opposite to the therapeutic goal (PMID:20516114, 15475955).

## 7. Uncertainties carried forward

- `u1` phase unknown; in-trans inferred, not observed (resolve: parental
  testing, long reads).
- `u2` N1002K residual function unmeasured; assays: patient-fibroblast
  BubR1 western, nocodazole-arrest timing for SAC competency, k-fibre
  stability, aneuploidy rate by FISH/scDNA-seq.
- `u3` NMD is a positional prediction, not a measured decay rate; rare
  escape would yield a 736-aa fragment of uncertain activity
  (PMID:31659324).
- `u4` predictor agreement is strong but not unanimous (REVEL 0.472;
  the c.3006T>A ClinVar record is a single-submitter VUS).

## Provenance

- Tool: `tools/t2_mechanism.py` (`--replay` regenerates mechanism.json
  from recorded fixtures, zero network).
- Tests: `tests/test_t2_mechanism.py` (25 tests: synthetic NMD layouts
  incl. edge cases and the -strand/single-exon/boundary cases, feature
  mapping, PDB parsing and contact analysis, schema and citation gates,
  replay-vs-written parity).
- Fixtures: `tests/fixtures/track2/mechanism/` (raw API payloads).
