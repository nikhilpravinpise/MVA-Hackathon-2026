# Rescue, Remove, Intercept: a testable, approved-drug repurposing portfolio for BUB1B mosaic variegated aneuploidy - and the open engine that built it

- **Team:** nikhilpise - MVA Hackathon 2026, Track 2 (Drug Repurposing)
- **Repository:** https://github.com/nikhilpravinpise/MVA-Hackathon-2026 (all code, configs, evidence files and tests)
- **Report generated:** {{GENERATED}} by `tools/make_track2_report.py` from `docs/track2/evidence/` - no number in this report is hand-typed.

> **This is a hypothesis-generation document for research follow-up, not medical advice.** Every candidate below is an existing approved medicine proposed for laboratory testing first; none should be given to any child on the strength of this report.

## For the family and patient advocates (plain language)

The child's genome carries two changes in a gene called *BUB1B*. This gene makes a protein, BubR1, that acts like a quality-control inspector during cell division: it holds the process until every chromosome is properly attached, so each new cell gets the right number. One of the child's copies is predicted to make no protein at all; the other makes a protein that is probably present but weaker or less stable. With too little working BubR1, some cells end up with the wrong number of chromosomes - this is "mosaic variegated aneuploidy" (MVA).

We asked three questions, each of which points to medicines that already exist:

1. **Rescue** - can we help the one weaker copy work better or last longer?
2. **Remove** - can we clear or quiet the damaged, worn-out ("senescent") cells that wrong chromosome numbers leave behind?
3. **Intercept** - can we make life harder for cells with the wrong chromosome numbers, and watch closely for cancer early?

For each idea we checked, by computer, that the medicine is really approved; we read the children's prescribing label; we listed what could go wrong for *this* child; and we designed the cheapest laboratory experiment - mostly on skin cells (fibroblasts) the MVA Society's labs already grow - that would tell us quickly whether the idea is worth pursuing or should be dropped.

## 1. Summary

- **Mechanism.** Allele 1 (c.2210T>G, p.Leu737Ter) is a predicted null: the stop codon sits far upstream of the last exon junction, so the transcript is predicted to undergo nonsense-mediated decay. Allele 2 (c.3006T>G, p.Asn1002Lys) is a predicted hypomorph in the kinase-like domain. This null + hypomorph pairing is the characteristic MVA1 genotype{{CITE_HANKS}}. Phase (in trans) is **inferred, not observed** (section 2.3).
- **Therapeutic logic.** Because one allele is null, the missense allele is the child's only source of BubR1, and BubR1 dosage is known to be tractable in vivo{{CITE_DOSAGE}}. That makes *residual-allele rescue* (axis A) the most disease-specific idea, with senescent-cell clearance (axis B, anchored in the BubR1-hypomorph mouse){{CITE_P16}} and aneuploid-cell vulnerability plus cancer interception (axis C) as complementary axes.
- **Method.** A deterministic, gene-agnostic engine ranks approved drugs from public evidence (section 4), a curated, machine-verified literature layer adds mechanism and pediatric-label evidence (section 5), and the two are reconciled in a frozen portfolio decision (`docs/track2/evidence/portfolio.json`).
- **Rigor receipts.** Approval status is checked by code, never from memory; every citation is resolved against PubMed/Crossref/DataCite and checked for retraction; the engine is benchmarked retrospectively on independent genotype-to-drug successes declared before the run (section 4.2); everything reruns from recorded fixtures.
- **Impact.** Every candidate maps to an assay in one of the MVA Society's four funded research programs, with an explicit go/no-go threshold (section 7). The decisive first experiment is a T1-cost fibroblast panel.

## 2. Variant mechanism

### 2.1 Per-allele evidence

{{ALLELE_TABLE}}

### 2.2 Pathway: from genotype to phenotype

{{PATHWAY_TABLE}}

### 2.3 What we do not know (stated before any drug is discussed)

{{UNCERTAINTIES}}

## 3. From mechanism to therapeutic axes

{{THERAPEUTIC_AXES}}

**What the mechanism rules out** (these shaped the rejected table in section 6):

{{CONTRAINDICATIONS}}

## 4. Method: the open repurposing engine

### 4.1 How candidates are generated

The engine (`src/track2/`, `tools/run_track2.py`, frozen `config/track2.yaml`) is gene-agnostic: given a disease gene, its seed module and an axis map, it (1) expands the module on STRING, (2) pulls drug-target evidence from Open Targets, ChEMBL and DGIdb, (3) keeps only approved medicines (ChEMBL max_phase 4, not withdrawn, with an openFDA label), (4) scores network proximity between drug targets and the disease module against degree-matched random sets, (5) queries transcriptomic signature reversal on LINCS L1000 (SigCom LINCS), and (6) reports every evidence channel's contribution to a transparent weighted score and tier. Every API response is cached and replayed, so the ranking is byte-reproducible offline. Design details, source versions and limitations: [repo:docs/track2/engine.md].

{{ENGINE_SECTION}}

### 4.2 Does the engine find known answers? (retrospective benchmark)

{{BENCHMARK_SECTION}}

### 4.3 Independent computational evidence

**Aneuploidy pharmacogenomics (PRISM repurposing screen x cell-line aneuploidy).** Highly aneuploid cancer cells have distinct drug vulnerabilities{{CITE_COHEN}}; we asked which *approved* drugs preferentially inhibit more-aneuploid cell lines, controlling for lineage.

{{PRISM_SECTION}}

**Protein language-model effect of p.Asn1002Lys (ESM-2 masked-marginal score, calibrated on BUB1B ClinVar/gnomAD missense).**

{{ESM_SECTION}}

## 5. The candidate portfolio

### 5.1 Systematic literature screen

{{SCREEN_SECTION}}

### 5.2 Ranked shortlist

{{SHORTLIST_TABLE}}

"Evidence grade" is an honesty label for the distance between the evidence and this child's use case, not clinical readiness: no MVA-specific drug-treatment study exists, so nothing is graded higher than moderate.

### 5.3 Lead candidates in detail

{{LEAD_SECTIONS}}

### 5.4 Adjuncts and the non-drug recommendation

{{ADJUNCTS}}

## 6. Considered and rejected

{{REJECTED_TABLE}}

## 7. Testability: mapped to the MVA Society's funded research programs

The four programs and what each can measure are taken verbatim from the Society's research pages ([repo:docs/track2/evidence/mva_programs.json]). Each cell gives the readout, the go/no-go threshold, cost tier and time to result.

{{TESTABILITY_SECTION}}

## 8. Scalability

- **Any gene, one command.** The engine takes a gene, its seed module and an axis map; nothing in `src/track2/` is BUB1B-specific ([repo:docs/track2/engine.md]). The same run applies directly to the other MVA genes (CEP57, TRIP13, MAD1L1) seeded in the config.
- **Measured, not claimed.** The retrospective benchmark (section 4.2) is the scalability receipt: it runs the identical pipeline on unrelated diseases with known approved repurposings.
- **Offline and reproducible.** Every external response is recorded; `pytest` replays them with zero network.
- **Reusable rigor layer.** `tools/verify_citations.py` is a standalone citation gate any team can drop into a report pipeline.

## 9. Rigor and reproducibility

- {{CITATION_GATE}}
- {{TEST_COUNT}}; run with `python -m pytest tests/test_t2_*.py tests/test_track2_*.py tests/test_verify_citations.py`.
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

**11. GenAI disclosure (required).** {{GENAI_LINE}}

## Acknowledgement

*This work was made possible through the Hackathon, organized by Sage Bionetworks in partnership with the MVA Society, Hugging Face, and BEACON (The Benchmarking, Evaluation, and Assessment Consortium for Science), with prize sponsorship from AWS and Anthropic. We are deeply grateful to the child and their family who generously contributed their data and their story to advance research into this rare disease. We acknowledge their trust in making this Hackathon possible.*

## References

{{REFERENCES}}
