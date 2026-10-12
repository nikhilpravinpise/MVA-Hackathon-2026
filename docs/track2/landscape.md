# Track 2 landscape - what competitors are publicly doing

Compiled 2026-10-12 by lane L4. Sources: HF API (`spaces?search=`,
`models?search=`, `datasets?search=`, org listing), GitHub `gh search repos`
+ per-repo README/file-tree reads (read-only), PubMed esearch/esummary for
prior art. Everything below is from *public* artifacts - mostly repos teams
chose to make public early (against the rules' private-during-challenge
option), or committed submission artifacts. We summarize approaches to
differentiate; nothing is copied.

## 0. TL;DR

- ~30 public GitHub repos reference the hackathon; **~8 show substantive
  Track 2 work**. HF Spaces search shows no competitor demo Spaces - the
  only MVA space is the official one (127 likes); `search=bub1b` returns 0.
- The field converges on the same biology we did: **the null + hypomorph
  asymmetry is the therapeutic opening** (readthrough or rescue of
  p.Leu737Ter; stabilise residual p.Asn1002Lys-BubR1), plus downstream
  damage control (senolytics, mTOR, proteostasis/autophagy).
- Convergent candidates across teams: **ataluren/amlexanox/other
  readthrough, NAD+/SIRT2 (NMN, NR, niacin), arimoclomol, sirolimus/
  everolimus, metformin, dasatinib**. Our three-axis portfolio overlaps;
  differentiation must come from *method and rigor*, not candidate novelty.
- Two teams took honest-negative stances ("no drug survives the
  patient-specific filters") and argue it as the rigorous answer. Our
  considered-and-rejected table must be at least that unflinching.
- Nobody, in what is public, does: (a) a retrospective recall@k benchmark
  on other genotypes, (b) pediatric label filtering *by code* across
  ChEMBL/DrugCentral/openFDA, (c) a citation-resolution gate, (d) mapping
  to the MVA Society's four funded programs. Those remain our differentiators.

## 1. Where competitors are visible

| Surface | Result |
|---|---|
| HF Spaces (`mva`, `bub1b`, `rare-disease`, `mva-hackathon`, `hackathon-2026`) | Only `SageBio/rare-disease-real-kid-mva-hackathon-2026`; no competitor Spaces or demos |
| HF datasets (`mva`) | Only `SageBio/mva-hackathon-2026-data` (gated) |
| GitHub repos | ~30 named `mva-hackathon-2026`/`mva-hackathon`; ~8 with real T2 content (below) |
| Discussions | No team has posted a T2 method publicly; #6 is a team-formation thread (3 comments) |

## 2. The visible Track 2 approaches

### texdata (`tfius/mva-hackathon-2026`) - knowledge graph + "more BubR1"
Most polished public package. Track 1 100/100. T2:
- **Finding:** BUB1B has 464 edges in PrimeKG and **zero drug edges** (same
  for BUB1, BUB3, CEP57, TRIP13); OptimusKG reproduces the gap - "BubR1 is
  undrugged". TxGNN zero-shot ranks paclitaxel/vinblastine - mechanistically
  contraindicated retrievals they report as a negative control for naive
  graph pipelines.
- **Candidates:** six proposals converging on *more BubR1* - NAD+/SIRT2
  cofactor supply, CBP/p300 inhibition (reduce destabilising acetylation),
  PTC readthrough, genomic correction; plus contraindications and a
  validation plan (`reports/track2-mechanism-and-repurposing.md`).
- **Style:** three independent adversarial reviews logged; they corrected a
  factual error (claimed K668 deleted on the null allele) and flagged that
  vincristine (a contraindication) is also backbone RMS chemotherapy.

### Ryukijano - mutation-specific "stabilise-and-de-stress stack" + LINCS firewall
Submitted T2 report (`submissions/Ryukijano_track2_report.md`, revised
2026-09-04). Track 1 100/100.
- **Upstream:** UGA readthrough - ataluren (with a genuinely careful
  regulatory audit: EMA conditional auth NOT renewed Mar 2025, FDA NDA
  withdrawn Feb 2026, MHRA licence under active review) and **amlexanox**
  (dual PTC readthrough + NMD inhibition; approved only as topical paste).
- **Downstream:** glycerol phenylbutyrate (Ravicti), arimoclomol (Miplyffa;
  FDA-approved Sep 2024 w/ miglustat >=2y; EMA refused Meplyffa Jul 2026),
  metformin + rilmenidine (approved autophagy inducers).
- **LINCS screen:** L2S2 `pairedEnrich` + L1000CDS2 over 9 MVA/hypomorph
  contrast signatures -> 676 drugs through a 5-stage firewall
  (regulatory/pediatric/anti-target/directionality/provenance):
  **ACCEPT=0, WEAK=2 (sirolimus, dasatinib - both MIXED direction)**.
  Explicitly reports that the sirolimus reverse signal is not robust to
  gene-list size, and that rapamycin is itself aneugenic (Bonatti 1998).
- **Rules-aware:** supplements (NMN, NR, trehalose, spermidine, MitoQ,
  quercetin) demoted to comparators; ELX-02 in a future-research tier.

### ciberpty (`cpu-16/mva-hackathon-2026`) - honest negative, pre-registered
Spanish-language lab notebook, exceptionally adversarial to itself.
- **Stance:** "we recommend no drug today" - metformin fails a PK argument,
  bortezomib fails a patient-specific safety filter; the defended product
  is a *prepared* answer for a new-tumour scenario plus a falsifying
  experiment.
- **Method:** DepMap 24Q4 PRISM + CRISPR vs computed aneuploidy score
  (2,420 lines): the aneuploidy-proteasome link is significantly *weaker*
  in solid lineages (interaction p=0.026), ploidy adds nothing - used to
  weaken their own argument.
- Seven pre-registrations; aneuploidy-burden-by-WGS endpoint *withdrawn*
  after showing variegated mixtures are non-identifiable; fibroblast assay
  power analysis driven down to 0.167 at n=3.

### Samistus1234 (`Samistus1234/mva-hackathon`) - measurement-first
- Assesses the same three axes we did and reports that **none survives this
  patient**: NAD+/SIRT2 (tumours are NAD+-avid), senolytics (dasatinib's
  labelled paediatric harm is growth retardation - the presenting
  complaint; senescence can be tumour-suppressive in RMS), proteostasis
  (arimoclomol's generic mechanism failed in its two tested diseases).
- Concludes the rate-limiting step is **measurement, not drug choice**;
  proposes two patient-cell experiments designed to refute their own
  hypotheses; recommends a purpose-built BUBR1 stabiliser programme
  (migalastat/ETI as modality precedents, deucravacitinib as proof
  pseudokinase pockets are druggable). Ships `repurpose.py`
  mechanism-hop tool.

### bralewild - single contrarian candidate
- Pipeline (`pipeline/track2/t2_01..t2_06`): target network -> drug
  evidence -> mechanism filter -> readthrough branch -> positive control
  -> signature repurposing.
- **Candidate: escin (beta-aescin) alone** - a marketed (German
  Commission E / EMA traditional-use) triterpene with HTS evidence of PTC
  readthrough in CFTR primary cells.
- Notable mechanism: an automated **HPO-conflict screen** demotes
  gentamicin/amikacin (nephrotoxic vs HP:0000121 nephrocalcinosis) and
  amlexanox (TBK1/IKKe immunosuppression vs HP:0002859 rhabdomyosarcoma;
  also no marketed product anywhere anymore).

### mikerecognex / doyleywoods (`MikeRecognex/mva-hackathon-2026`) - mechanism-first honest-negative
- De-identified report (alleles redacted to CANDIDATE-01/03 on
  re-identification grounds - a stricter privacy posture than ours).
- Finding: **evidential strength and pharmacological availability run in
  opposite directions** across 16 enumerated axes: senolysis has the
  strongest evidence (Baker 2011 genetic model) but no approved senolytic
  drug; mTORC1 is the only overlap axis (paediatric-experienced agents,
  weak correlative evidence); symptomatic management has abundant agents
  and no mechanism.

### JoseVelasco2026 - AI-synthesis-led
- Consensus "Deep Search" report (~100 papers synthesised): leads with
  **HSP90 inhibition** (pimitespib/TAS-116 - approved only in Japan for
  GIST) for aneuploidy proteotoxic vulnerability; WEE1 inhibition
  (investigational only - would not satisfy the approved-only rule as a
  primary); senolytics ranked less direct. Also ran AlphaFold pLDDT
  structural comparison of N1002K vs WT.
- Caveat: the visible doc leans on investigational oncology agents; how the
  submitted report reconciles the approved-only rule is not visible.

### HLEOT - engine skeleton
`src/mva_track2/` package (analysis/evidence/sources) + `config/track2.yaml`
+ tests; approach not visible in README form.

## 3. Candidate convergence map

| Candidate | Teams proposing it (publicly) | Axis |
|---|---|---|
| Ataluren / other PTC readthrough (amlexanox, escin, gentamicin, azithromycin) | texdata, Ryukijano, Marxist-Leninist, bralewild | null-allele rescue |
| NAD+/SIRT2 (NMN, NR, niacin) | texdata, Ryukijano (comparator only), Marxist-Leninist, Samistus1234 (rejected) | residual-BubR1 abundance |
| Arimoclomol / proteostasis (Ravicti, HSP90i) | Marxist-Leninist, Ryukijano, Samistus1234 (rejected), JoseVelasco2026 | missense stabilisation |
| mTOR (sirolimus/everolimus) | Marxist-Leninist, Ryukijano (WEAK/MIXED), mikerecognex (overlap axis) | downstream stress |
| Autophagy inducers (metformin, rilmenidine) | Ryukijano | downstream stress |
| Senolytics (dasatinib, navitoclax-class) | Ryukijano (WEAK adjunct), Samistus1234 (rejected), mikerecognex (evidence-rich/unavailable), JoseVelasco2026 | damage removal |
| HSP90i / WEE1i | JoseVelasco2026 | aneuploidy vulnerability |

`Marxist-Leninist/mva-hackathon-2026` (public since Aug) runs the same
allele-resolved framing: azithromycin first-screen readthrough (UGA-A
context), arimoclomol for the missense, prescription niacin as an approved
NAD precursor, sirolimus citing a "2026 fly model" drug-level rescue in a
SAC-loss MVA-like microcephaly model (**that paper is not on PubMed as of
2026-10-12 - preprint claim; do not cite without resolving it**).

## 4. Published prior art (PubMed, resolved 2026-10-12)

- No published MVA drug-treatment or repurposing study exists - the query
  space returns only clinical case reports (e.g. RMS in PCS-MVA
  PMID:31184400). White space is real, which also means *no prior validated
  answer*; the benchmark must therefore use other genes' successes.
- Anchor literature every serious team relies on (also ours):
  - Hanks 2004 Nat Genet - biallelic BUB1B causes MVA: **PMID:15475955**
  - Baker 2004 Nat Genet - BubR1-insufficiency progeroid mouse:
    **PMID:15208629**
  - Baker 2011 Nature - p16+ senescent-cell clearance delays ageing
    phenotypes: **PMID:22048312**
  - Baker 2013 Cell Rep - p21 in BubR1 progeroid mice: **PMID:23602569**
  - SIRT2-BubR1 axis: **PMID:24825348** (SIRT2 induces BubR1, lifespan),
    **PMID:25285631** (SIRT2 deacetylates BubR1 **at K250**, 2014)
- Watch item for L1: two competitor reports assert the SIRT2-regulated
  BubR1 acetylation site is **K668**; the resolved 2014 paper says **K250**.
  K668 is the *mitotic-phosphorylation-regulated* acetylation site in some
  later papers - verify from primary sources before we name a residue.

## 5. How we differentiate (and where the bar actually is)

| Their strength | Our counter |
|---|---|
| Regulatory precision (Ryukijano's ataluren/arimoclomol audit) | Approval status **by code** against ChEMBL `max_phase`, DrugCentral approvals, openFDA labels - reproducible, not hand-checked |
| Honest negatives (ciberpty, mikerecognex, Samistus1234) | A considered-and-rejected table argued as hard as the shortlist (GH contraindication, SAC/MPS1/KIF18A inhibitors as anti-targets, p53 suppression, navitoclax) + explicit limitations |
| KG/screens as negative controls (texdata, Ryukijano LINCS firewall) | Multi-modal engine with the same honesty: PRISM aneuploidy pharmacogenomics + L1000 reversal scored *and reported even when null*, plus the retrospective recall@k benchmark nobody else shows |
| Measurement-first programs (Samistus1234, ciberpty) | Testability matrix against the MVA Society's four funded programs with concrete readouts and go/no-go thresholds - fundable experiments, not just a drug list |
| De-identification (mikerecognex) | `public_release_check.py` gate; only published facts in outputs |
| Allele-resolved framing (Marxist-Leninist, Ryukijano, bralewild) | Same framing + the "residual-allele rescue" thesis quantified per allele (NMD prediction, stability evidence, LM effect score) |

**Watch-outs:**
1. `escin`/readthrough claims and the "fly model" sirolimus paper are
   attractive-but-thin evidence classes; if our engine shortlists a
   readthrough agent, the expected-effect-size caveat (single-digit
   percent rescue in cell assays) must be in the report.
2. Several teams already burned through the obvious axes; the judges will
   see near-identical candidate lists. The differentiators are the
   benchmark number, the code-verified approval gate, the citation gate,
   and the funded-program testability map.
3. Ryukijano's LINCS result (no clean reverse signature; sirolimus MIXED)
   is public evidence that signature-reversal on MVA signatures is weak -
   if our own L1000 pass comes back null, report it as they did; it costs
   nothing and reads as rigor.
