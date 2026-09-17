# MVA Hackathon 2026 — Execution Plan

**Status date:** 2026-09-17 · **Deadline:** 2026-10-24 23:59 UTC (T-minus ~37 days) · **Winners:** ~Nov 25
**Ground truth sources:** `docs/DEEP_DIVE.md`, vendored app source in `hackathon-app/`, live leaderboard
(pulled 2026-09-17: **122 rows, 116 at 100.0/1.000** — tie-break is earliest submission, so Track 1 rank is
locked; differentiation is the methods write-up + Track 2).

This plan is written against the *actual scorer source* (`hackathon-app/evaluation.py`,
`tabs/submit_track1.py`, `tabs/submit_track2.py`, `utils.py`, `groundtruth.py`), not assumptions.
Every load-bearing claim is tagged `[verified: <source>]` or `[assumption: <why>]`.

---

## 1. What winning actually requires

### 1.1 The scoring math (verified from `hackathon-app/evaluation.py`)

- Ground truth = `frozenset` of exactly **2 variants** — a compound-heterozygous pair
  (`evaluation.py` docstring; loaded from private `gold_standard_track1.json` via `groundtruth.py:52-62`,
  format `{proband: {"primary_variants": [{chrom,pos,ref,alt}]}}`).
- **Full match** = ONE ROW containing BOTH true variants (chrom/pos/ref/alt exact).
  `_parse_variant` (`evaluation.py:71-74`) does `chrom.strip()` (no uppercase), `int(pos)`,
  `ref/alt.strip().upper()` → `chr15` matches GT, `CHR15` and `15` do **not**.
- Rows sorted by `epcr` desc, ties by file order (`evaluation.py:107`). Rank points: r1=100, ≤3=50,
  ≤5=25, ≤10=10 (`evaluation.py:43-48`). Partial (a row with exactly one true variant) = half tier
  (`evaluation.py:154-157`).
- **F-max** is computed at the *individual-variant* level: at each unique epcr threshold t, predicted set =
  union of variants in rows with `epcr ≥ t` (`evaluation.py:162-186`). F=1.0 requires a threshold where the
  predicted set is exactly the two true variants (tp=2, fp=0, fn=0).
  **Consequence:** any junk row *at or above* the pair's epcr destroys F=1.0. Junk rows *below* it are free.
- Max 10 rows **per proband** (`evaluation.py:104-105`); `epcr ∈ (0,1]` — `nan`/`inf` also rejected;
  `finding_type ∈ {primary, secondary}` (lowercased before check, `evaluation.py:94-99`);
  `notes` ignored by scorer. `proband_id` must be `PROBAND01` (`submit_track1.py:119-124`).
- **Multi-proband footgun [verified empirically]:** `load_submission` groups rows by `proband_id` and
  the app scores ONLY the first proband group encountered (`submit_track1.py:118-119`). A stray
  non-`PROBAND01` row placed *first* gets the whole submission rejected; the same row placed *after*
  your real rows is silently ignored. One proband per file, always.
- Server-side filename becomes `model{N}_{filename}` where N = your per-user submission count
  (`submit_track1.py:167,192`) — that string shows in the leaderboard "Model" column, so the filename
  itself is write-up surface. Name it like a methods summary.
- Leaderboard groups by `display_name`, keeps best `(rank_points, f_max)`, sorts ties by earliest
  `submitted_at` (`utils.py:180-202`). All 6 quota are per-HF-user; teammates' quotas group under an
  identical team name.
- Every submission REQUIRES GitHub URL starting `https://github.com/` + report `.pdf`/`.md` + CSV
  (`submit_track1.py:140-156`). No probe submissions possible.
- Track 2: max 3 submissions, **only the latest is reviewed** (`submit_track2.py:22-24`); requires report +
  GitHub URL + video URL + optional judge notes. One designated submitter per team (FAQ).

### 1.2 Where the marginal win is

116 teams already hold 100/1.000; earliest-submission tie-break is intentional code behavior (commit
1112710, per deep dive §9e). We cannot buy rank with speed. The organizers have stated twice that the
methods write-up "counts just as much" and "Track 2 is where the biggest unmet need still lives"
(deep dive §6). Therefore:

- **Track 1 goal:** 100/1.000 on submission #1, with a write-up that demonstrably beat every other
  methods report on rigor: answer-blind pipeline, read-level in-trans proof, secondary-findings scan,
  honest ablations, runtime/cost table.
- **Track 2 goal:** win the panel. Rubric: Scientific Rigor 35% / Impact 25% / Innovation 25% /
  Scalability 15% (`about.py:147-199`, `rules.py:75-81`). Market-approved drugs only (deep dive §4).
- **Innovation/Community award ($2k+$2k):** patient/community-facing artifact is cheap extra surface.

### 1.3 The answer we are NOT allowed to assume

Leaderboard forensics + the leaked participant Space point to a **BUB1B compound-het pair in trans**;
leading hypothesis {chr15:40,209,701 T>G (p.Leu737Ter, nonsense) + chr15:40,220,612 T>G (missense)} on
MANE Select ENST00000287598.11 / NM_001211.6 [verified: Ensembl 115, ClinGen], alternate involves
40,216,470 A>G (deep intronic). **This is intelligence, not ground truth.** The leaked Space contains
LLM-fabricated claims (deep dive §9a). Rule: the pipeline output is the submission; forensics only set
expectations for sanity checks. If our verified VCF analysis disagrees with the leak, the VCF wins.

---

## 2. Doctrine — the rules every phase obeys

### 2.1 Answer-blind protocol (our honest substitute for "no overfitting")

There is no train/test split in an N-of-1 problem. The equivalent overfitting hazard is tuning the
pipeline to the publicly-inferable answer — which produces a submission that proves nothing and a
write-up judges will see through. Countermeasures, all machine-enforced:

1. **Decision freeze.** The triage funnel configuration (thresholds, weights, gene panels) is committed
   to git *before* the proband VCF is queried for the final call. Post-freeze changes require a logged
   justification in `docs/decisions.md` with timestamp + reason.
2. **External validation set.** The complete pipeline must recover the known answer on ≥2 *other* cases
   before we trust it on the proband: (a) a public genome (GIAB HG002) run end-to-end for caller/QC
   benchmarking; (b) a synthetic proband — ClinVar pathogenic compound-het pair spiked into a public
   VCF with realistic allele fractions and a matching HPO set — recovered blind. This is the real
   "held-out test set."
3. **Ablation / leave-one-source-out.** Each data source (gnomAD AF, CADD/AlphaMissense, ClinVar, HPO
   scoring, phasing) is dropped in turn; the final pair must remain top-5 in every ablation or we report
   the fragility honestly. A pipeline that only works with all knobs on is overfit to this case.
4. **Negative controls.** The pipeline must NOT implicate a pair in: a spike-in-free public VCF with an
   unrelated HPO set, and common noise genes (TTN, MUC16, etc. — genes famous for spurious rare-LoF hits).
   A funnel that "finds" a causal pair everywhere finds nothing.
5. **Firewall on the leak.** No variant coordinates, gene names, or values from the leaked Space enter
   code, tests, configs, or the report. The report's provenance section states this explicitly —
   it is a rigor *flex*, not a confession.

### 2.2 Test doctrine — tests must be able to fail

Every test in `tests/` has a stated **falsification condition** — the concrete bug it would catch. Any
test that cannot name its falsification condition gets deleted or rewritten. We run **mutation checks**
on the harness itself: deliberately corrupt a known-good submission (flip `chr15`→`CHR15`, `chr15`→`15`,
pos±1, ref/alt swap, epcr 0, 11 rows) and assert the local scorer *changes the score or raises*. If a
corruption doesn't change the result, we learned something real about the scorer — file it.

The official `evaluation.py` is vendored into the repo as the **scoring oracle** — we never reimplement
scoring logic. Local score = official score by construction. *(License check at vendor time; it's the
hackathon's own scoring code published in the public Space — attribute and link.)*

### 2.3 Compliance doctrine (deletion-day is part of the plan, not an afterthought)

- Patient data lives only in `data/` (gitignored, single root, never committed, never in logs/prompts).
- Every derived artifact gets a keep/delete tag at creation: **KEEP** = ranked variant list, HPO terms,
  gene/pathway rankings, mechanism analysis, drug candidates, code, report, leaderboard entry.
  **DELETE** (within 30 days of close) = VCF/BAM/FASTQ copies, indices, genotype-scale tables, notebook
  state containing genotypes, prompts/logs with pasted variant blocks, fine-tuned models on raw genome.
- Publication rule: a handful of *named* variants in the report = a finding; genome-scale genotype
  tables = prohibited derived data (deep dive §9a — the leaked Space crossed this line).
- LLM use: commercial/API tier only, no-training terms; a running `docs/llm_log.md` records
  provider/tier/data-handling per session so the required GenAI disclosure writes itself
  (methods xlsx Q: "(required)" — verified in `methods_description_form.xlsx` shared strings).
- No recontact of family/MVA Society; no resharing data; WCG IRB protocol #20252010 governs.

---

## 3. Compute & environment budget

Local machine [verified: this host via WMI + `nvidia-smi`, 2026-09-17]: Ryzen 7 260 (8C/16T), 24 GB RAM,
RTX 5050 Laptop GPU (8 GB), ~750 GB free on C:, Docker Desktop (engine 29.6) + WSL2, Python 3.12 venv
with `huggingface_hub`+`hf_transfer`.

| Job | Where | Estimate | Notes |
|---|---|---|---|
| Download VCF+docx (~330 MB) | local | minutes | first; FASTQs (~85 GB) download in background via `hf_transfer` |
| Download FASTQs (~85 GB) | local | ~30-60 min at 25-50 MB/s | 100-150 GB free required — we have it |
| VCF QC (bcftools stats, mosdepth on VCF) | local | minutes | |
| VEP 116 offline annotation, ~5M variants | local Docker/WSL | 4-12 h | cache ~20-30 GB; two-pass: prefilter → annotate candidates |
| Exomiser genome mode | local JVM | hours; -Xmx12-16G, `PASS_ONLY` fallback to 4 GB [verified: Exomiser docs] | data dir ~50-100 GB |
| bwa-mem2 realign 404M read pairs | local 16T **or** cloud spot | ~12-24 h local; ~3-4 h on 64-vCPU spot (~few $) | decision point after download; both paths scripted |
| Annotation DBs (VEP cache, dbNSFP 5.3.1, gnomAD v4.1, ClinVar, Exomiser data, ref fasta) | local disk | ~60-100 GB total, one-time downloads | fits comfortably in ~750 GB free |
| DeepVariant 1.10 WGS | cloud spot or overnight local | ~2 h on 96 vCPU [verified: DV metrics]; ~10-14 h on 16T | `--regions` for locus-only runs in minutes |
| DeepVariant BUB1B locus only | local | <1 h | the cheap high-value run |
| CNV/SV calling (Manta/CNVpytor) on our BAM | local | hours | differentiator: VCF is SNV/indel only |

Fallback cloud: AWS spot (aligns with sponsor), one `c6i.16xlarge`-class box for alignment+calling.
Total expected spend: **< $50**. Every job's runtime+RAM+cost logged into `docs/runtime_log.md` —
the methods form explicitly asks for it (xlsx Q: "estimate of run time and cost").

Repo layout:

```
plan.md  docs/  hackathon-app/(reference)  src/{vcf_qc,triage,genes,pheno,prioritize,phasing,submit,track2}
scorer/evaluation.py (vendored oracle)  tests/  data/ (GITIGNORED — patient data)  results/  env/
```

`data/` and `results/` carry a `RETENTION.md` manifest listing every file + keep/delete tag.

---

## 4. Phase plan — each phase ends at a hard gate

A gate passes only when every criterion is verified by a named test/command/notebook cell. No
self-attestation. "Done" means the gate script is green.

### Phase 0 — Access, identity, scaffolding (critical path)

- [ ] HF account; request gated dataset access (form: institution-any, ~12 attestations; approval is
      the long pole — **submit today**). Register with a valid email; each member registers individually.
- [ ] Decide ONE exact `display_name` string; record in `docs/team.md`. Mixed/absent team names create
      duplicate leaderboard entries (deep dive §3 — happened to Fernandosr85).
- [ ] Create GitHub repo (private OK until Oct 24); push scaffold + this plan; first commit = clean
      baseline.
- [ ] Download VCF + .tbi + docx immediately upon approval; queue FASTQs in background.
- [ ] Vendor `hackathon-app/evaluation.py` → `scorer/`; `tests/test_oracle_parity.py` asserts it
      imports and scores the template CSV deterministically.
- [ ] `docs/llm_log.md`, `docs/decisions.md`, `docs/runtime_log.md`, `data/RETENTION.md` initialized.
- [ ] Discussions-watch: re-read all community threads; subscribe/check every ~3 days for organizer
      guidance changes (quotas and rules have already changed once — deep dive §4).

**GATE 0:** dataset access granted; VCF+tbi+docx on disk with sha256 recorded; repo scaffold committed;
oracle vendored and parity test green; `git status` clean.
*Falsification: if any artifact is missing or the oracle test is red, nothing downstream starts.*

### Phase 1 — Data audit / EDA (judge the data before trusting it)

- [ ] Parse `Challenge_Clinical_Phenotype_1.docx` → HPO term list → `results/hpo_terms.json`
      (phenopacket-style record for reuse by Exomiser/LIRICAL).
- [ ] VCF header forensics — confirm, don't assume [deep dive §2, participant-reported]: caller
      (Sentieon 202308.02 + GATK VariantFiltration), reference build string, **contigs lack `chr`
      prefix** (silent-empty tabix trap), PGT/PID FORMAT fields present, INFO `AF` = within-sample
      fraction AN=2 (NOT population frequency).
- [ ] `bcftools stats`: total variants, SNV/indel split, Ti/Tv (~2.0 expected for WGS [assumption:
      standard human WGS]), het/hom, singleton/known-vs-novel via dbSNP ID presence, per-contig counts,
      QUAL/FILTER distribution.
- [ ] Variant-count sanity vs expectation (~4-5M for WGS); flag anomalies.
- [ ] On FASTQs (when landed): `fastp`/`fastqc` all 8 files → verify against leaked run metrics
      (~404M pairs, Q30~93.5%, GC~41%, dup~8.4%, ~35× — treat as *expectations*, not truth).
- [ ] Contamination/sex-check: verify reported sex consistency from chrX/chrY coverage/het pattern —
      cheap QC that catches sample swaps.
- [ ] EDA outputs written to `results/eda/` and summarized in the report — this section alone
      demonstrates more data literacy than most submissions.

**GATE 1:** `tests/test_data_integrity.py` green — asserts: contig set has no `chr` prefix; PGT/PID in
FORMAT; variant count in [3M, 7M] (WGS expectation, adjust bounds after EDA with justification logged);
Ti/Tv in [1.9, 2.1]; all FILTER values enumerated; HPO list non-empty and all codes match `HP:\d{7}`;
FASTQ read counts within 20% of expectation (when available).
*Falsification: any assertion red = stop and explain the anomaly in `docs/decisions.md` before proceeding.*

### Phase 2 — The prioritization model (the thing judges grade)

Design: a transparent, deterministic, auditable ranking pipeline — the actual state of the art for
N-of-1 diagnostics (Exomiser-class), not a trained black box. Two arms that must *agree*:

**Arm A — standard:** Exomiser (genome mode, GRCh38, local data dir) on VCF + HPO → ranked genes/variants.
**Arm B — custom funnel** (this is the innovation surface):

1. **Prefilter:** PASS variants → annotate with VEP 116 offline [verified: Ensembl releases] + plugins:
   gnomAD v4.1 AFs, ClinVar, CADD, AlphaMissense, REVEL/MetaRNN via dbNSFP 5.3.1, SpliceAI (precomputed
   scores via dbNSFP/VEP plugin), LOEUF/constraint, phyloP.
2. **Rarity tier:** pop-max AF across gnomAD exomes+genomes; "absent" treated separately from "present-but-
   rare" (absence is stronger for recessive LoF). Thresholds frozen pre-analysis (e.g. ≤1e-4, and a
   sensitivity grid in §5).
3. **Consequence tier:** predicted LoF (nonsense/frameshift/canonical-splice/high-SpliceAI), damaging
   missense (ensemble of predictors, not one), other.
4. **Inheritance aggregation** (`genes.py`): per-gene grouping → enumerate recessive genotypes:
   homozygous alt, and **all compound-het pairs** (het_A × het_B in same gene); plus dominant/de-novo
   and X-linked models for completeness. Output = ranked *genotype hypotheses*, not variants —
   matches the submission format exactly (pair in one row).
5. **Phenotype scoring** (`pheno.py`): HPO semantic similarity (resnik/lin over the HPO DAG via
   `pyhpo` or Exomiser's phenodigm), plus gene→disease prior from OMIM/Orphanet/PanelApp.
6. **Rank:** combine variant-damage + gene-phenotype + inheritance-fit into epcr; epcr is a *ranking
   artifact*, calibrated only by ordering — document that.

- [ ] Both arms run on the synthetic spike-in proband FIRST (external validation, §2.1.2).
- [ ] Then both arms run on proband; compare top-20 gene lists (concordance metric in §5).
- [ ] Splice check on every near-splice candidate (SpliceAI Δ-score) — the leaked list contains a deep
      intronic A>G; the pipeline must evaluate it on evidence, not ignore it.
- [ ] CNV/SV arm on our re-aligned BAM (Phase 4) feeds back here — a deletion allele would change the
      compound-het story; check it before finalizing.

**GATE 2:** spike-in proband: true pair recovered at rank ≤3 by Arm B and gene in Exomiser top-10;
negative-control VCF: no pair above the noise floor; funnel monotonicity test green (each stage output ⊆
input, counts logged); all thresholds present in committed config; `test_funnel.py` green.
*Falsification: pipeline fails on the synthetic case = the funnel is wrong, fix before touching proband
results.*

### Phase 3 — Phasing & read-level validation (the differentiator most teams skip)

cis/trans is the documented community blocker (deep dive §7, discussion #22). Without trio data:

- [ ] Fetch the matching reference: GRCh38 no-alt analysis set (GIAB/NCBI FTP per deep dive §2, ~3 GB);
      record MD5/checksum; note the header variant (`plus_hs38d1`, `no_chr`) — verify chromosome naming
      matches before aligning (BAM must use the same no-`chr` convention as the VCF for comparison).
- [ ] Parse PGT/PID read-backed phasing fields → local phase sets; chain the two candidate alleles
      through intervening heterozygotes (candidates are ~4-11 kb apart — beyond read length but inside
      phase blocks; paired-end insert size + PID chains + LD via common hets is the honest mechanism).
- [ ] Re-align: bwa-mem2 → sorted BAM (full genome, or minimally all BUB1B-region reads + a 10% genome
      sample for coverage stats). `samtools view` the locus; IGV/screenshot reads supporting each allele;
      show no read/pair carries both alts = in-trans evidence; check for a shared read carrying ref at
      both = further support.
- [ ] DeepVariant 1.10 `--regions` chr15 BUB1B locus → independent recall of both variants + GT concordance
      vs the Sentieon VCF (a second caller agreeing = orthogonal evidence; report concordance metric).
- [ ] `mosdepth` coverage at locus + genome-wide (~35× expected); flag any low-coverage confounders.
- [ ] WhatsHap/`whatshap phase` on the region BAM as a second, tool-based phase call agreeing with PGT/PID.
- [ ] Optional depth run (if timeline allows): full-genome DeepVariant + CNV (CNVpytor/Manta) → powers
      submission #2 ("de novo recall" method) and the CNV screen for Phase 2.

**GATE 3:** `test_phasing.py` green — PGT/PID parsed for both candidate sites; phase-block chain
documented; ≥2 independent phasing evidences agree on trans (PGT/PID chain + WhatsHap); read-level
figure generated from our own BAM (not the shipped VCF); DeepVariant recalls both variants.
*Falsification: if evidence supports cis, the pair is biologically implausible for recessive disease —
re-rank and say so in the report (that finding alone is publishable rigor).*

### Phase 4 — Secondary findings & the clinical layer

- [ ] Scan all **84 ACMG SF v3.3** genes [verified: GIM June 2025 — note deep dive says v3.2; v3.3 is
      current and adds ABCD1/CYP27A1/PLN] for reportable P/LP variants → `finding_type=secondary` rows
      with `notes` rationale.
- [ ] ACMG/AMP classify the primary pair (PVS1/PM3/PP3/PP4 etc.) — the write-up needs the criteria math.
- [ ] Handle the disclosure-ethics question (deep dive §5, discussion #20) with a written position —
      judges include patient advocates; thoughtfulness here is scored, silence is not.

**GATE 4:** SF gene list version stated + scan output file exists; every secondary row has a `notes`
justification; primary pair carries full ACMG criteria table in the report.

### Phase 5 — Submission engineering & the adversarial harness

- [ ] `submit.py` builds the CSV: row 1 = the pair, `chr`-prefixed, highest epcr (0.95); secondary
      rows below at strictly lower epcr; ≤10 rows.
- [ ] `tests/test_csv_contract.py` + `tests/test_adversarial.py` run the vendored oracle over a fixture
      battery (see §6). Required outcome on our real CSV: **rank_points 100.0, f_max 1.000, full match
      at rank 1** — locally, before upload.
- [ ] Dry-run the upload form checklist: report file `.pdf`/`.md`, GitHub URL, exact `display_name`,
      filename pattern `<team>_<method-descriptor>.csv` (it becomes leaderboard-visible `model{N}_...`).
- [ ] Submit ONCE. Verify leaderboard row within ~5 min (cache TTL 60 s [verified: `utils.py:30`]).
      Hold remaining 5 quota for the second method / corrections.

**GATE 5:** local oracle gives 100.0/1.000 on the exact bytes uploaded; every adversarial fixture
behaves as specified; leaderboard shows the expected entry under the exact team name.

### Phase 6 — Track 1 write-up (submitted WITH the CSV)

Answers every methods-xlsx question (13 T1 questions verified from `methods_description_form.xlsx`
shared strings), including required GenAI disclosure. Contents: pipeline diagram; funnel table
(counts per stage); external-validation results (spike-in + public genome); ablation table; in-trans
evidence figure; ACMG classification; secondary-findings handling; runtime/cost log; strengths AND
limitations (500-word abstract asks for both); provenance/firewall statement; data-handling compliance
note. PDF + .md.

**GATE 6:** every xlsx question maps to a report section (checklist in `docs/report_map.md`); all numbers
in the report are regenerated by `make report` from `results/` (no hand-typed stats — reproducibility is
the flex).

### Phase 7 — Track 2 (the actual battleground) — panel-judged, rubric-mapped

Mechanism spine: biallelic BUB1B → reduced/dysfunctional BUBR1 → weakened spindle assembly checkpoint →
mosaic aneuploidy → (a) cancer predisposition via chromosomal instability, (b) progeroid features via
senescent-cell accumulation (van Deursen BubR1-hypomorph work; he speaks at the MVA conference Sep 17 —
watch for proceedings). Ground in the MVA Society publications canon (deep dive §9f).

- [ ] **Variant-mechanism characterization FIRST** (required by submit tab text): LoF vs GoF per allele —
      nonsense = LoF allele; missense = hypomorph vs LoF evidence (conservation, domain, AlphaMissense,
      published BUB1B genotype-phenotype: canonical MVA1 = LoF + hypomorphic missense, biallelic
      truncating usually embryonic-lethal — deep dive §9d).
- [ ] **Systematic candidate generation** (not vibes): BUB1B/SAC/aneuploidy/senescence pathway →
      DrugBank, ChEMBL, OpenTargets, DrugCentral, STITCH/STRING, Repurposing-focused DBs → filter to
      **market-approved only** (combinations allowed if justified) → evidence-tiered shortlist.
- [ ] Candidate classes to evaluate honestly — including a *considered-and-rejected* table (rigor signal):
      senolytics (dasatinib+quercetin, fisetin, navitoclax-class — pediatric safety caveat front and
      center); senomorphics/mTOR (rapamycin); aneuploid-cell selective vulnerability (proteotoxic/energy
      stress: HSP90 inhibition, autophagy/AMPK axis); cancer interception/surveillance strategy given
      prior rhabdomyosarcoma.
- [ ] **Testability matrix:** map each shortlisted candidate to the MVA Society's funded C. elegans
      MVA repurposing screen (deep dive §7) — readout, feasibility, expected effect. Aligning to their
      existing pipeline is a direct Impact+Scalability play.
- [ ] Pediatric dosing/safety section; explicit "hypothesis, not medical advice" framing.
- [ ] Report + 3-min video (script→record→caption; video is judged too) + judge notes field.
- [ ] Mock-judge: score our own draft against the 35/25/25/15 rubric with evidence-per-claim; every
      factual claim carries a primary-source citation; red-team pass by reading as a skeptical clinician.
- [ ] Submit **once, last** (only the latest of 3 is reviewed) — after mock judging, before deadline.

**GATE 7:** each rubric criterion (35/25/25/15) has a written self-assessment ≥ 85% with justification;
100% citation coverage on factual claims (script checks every quantitative/mechanistic sentence has a
reference); scope check passes (all candidates market-approved); methods-xlsx T2 questions all answered
incl. GenAI disclosure; video ≤ 3:00, uploaded, link verified; submitted as the final entry.

### Phase 8 — Close-out & the award surface

- [ ] Public repo checklist: README (what/why/reproduce), LICENSE, env lockfiles, one-command demo that
      runs the pipeline on PUBLIC data (HG002 or synthetic — never patient data), `docs/` with methods.
- [ ] Community/innovation artifact: family-facing plain-language explainer of the findings + the open
      N-of-1 pipeline as a reusable tool (this is the $2k+$2k award play).
- [ ] Post-Oct-24 runbook: repo public; delete all `data/` + derived genotype-scale files everywhere
      (local, cloud, caches, notebook state, prompt logs); email confirmation to
      RarediseaserealkidMVAhackathon2026@synapse.org — if it bounces (unregistered-sender rejection
      documented in discussion #15), post the attempt in Discussions.

**GATE 8:** repo public-ready; deletion runbook executed and logged; confirmation email sent/logged.

---

## 5. Metrics — multiple, defined, and honest

| Metric | Type | Definition / target |
|---|---|---|
| Rank points | Official | 100 required (= pair full-match at rank 1) |
| F-max | Official | 1.000 required (a threshold exists where predicted set = exactly the 2 true variants) |
| Funnel recall@k | Internal | fraction of true/spiked variants surviving each stage; target: pair survives to rank ≤3 |
| Spike-in recall | External validation | synthetic proband: pair recovered top-3, 2/2 replicates |
| Negative-control specificity | Internal | no implicated pair on control VCF + unrelated HPO |
| Ablation delta-rank | Robustness | rank of final pair when each data source dropped; must stay ≤5 |
| Arm concordance | Cross-method | overlap of Arm A (Exomiser) and Arm B top-20 gene lists; report the number |
| Caller concordance | Validation | DeepVariant-vs-Sentieon het-call agreement at locus + GIAB hap.py precision/recall if full-genome run |
| Phasing evidence | Validation | ≥2 independent lines agree on trans |
| Coverage/QC | QC | ~35× mean, per-chromosome uniformity, dup rate vs expectation |
| Track 2 rubric | Panel proxy | mock-score per criterion with citation coverage; ≥85% before submit |
| Compliance | Binary | zero genotype-scale data outside `data/`; llm_log complete; deletion runbook ready |

Threshold **sensitivity grid** (not tuning): rerun funnel over AF cutoffs {1e-5, 1e-4, 1e-3} ×
damage-score cutoffs; report the pair's rank across the grid. Robust to the grid = not overfit;
fragile = reported honestly.

---

## 6. Test specification (falsification conditions stated)

`tests/` — pytest; oracle = vendored `evaluation.py`. Every fixture asserts a *specific* score or error.

| Test | Fixture | Expected | Falsifies / catches |
|---|---|---|---|
| perfect pair | row1=GT pair, epcr .95 | 100 / 1.000 | oracle wiring broken |
| chr-prefix wrong | `CHR15` vs `chr15` | 0.0 / 0.000 | case-sensitivity trap |
| no prefix | `15` vs `chr15` | 0.0 / 0.000 | coordinate-convention trap |
| pos off-by-one, single | {v1 pos+1} alone | 0.0 / 0.000 | coordinate exactness |
| pos off-by-one, paired | {v1pos+1, v2} | 50 pts / 0.500 | partial credit survives one corrupted allele — exactness tests must use single-variant rows |
| ref/alt swap, single | {v1 swapped} alone | 0.0 / 0.000 | allele exactness |
| one true variant | row={v1,junk} | 50 pts / 0.500 | partial-credit path |
| pair split across rows | {v1}@0.95, {v2}@0.94, nothing else | 50 pts but **F=1.0** | union-at-threshold semantics: F-max ignores row structure; only rank points need the pair in ONE row — the Remek failure mode, and why clean unions still can't save you |
| Remek reproduction A | junk×3 @0.95, pair @0.90 | 25 pts / 0.571 | exact replay of the leaderboard's 25/0.571 signature: full match at rank 4 + union of 5 variants at t=0.90 (tp2/fp3) |
| Remek reproduction B | junk@0.96; {v1}@0.95; {v2,j1}@0.90; {j2}@0.90 | 25 pts / 0.571 | same signature via never-paired rows — proves we understand the scorer, not just the format |
| split-pair ordering | {v1}@0.95, {v2}@0.94, clean rows below | 50 pts, F=1.0 | junk BELOW the completing threshold can't hurt F — only junk at-or-above does |
| degenerate pair | row={v1, v1} (same variant twice) | 50 pts / 0.667 | frozenset collapses duplicates → 1-variant row → partial only |
| whitespace chrom | ` chr15 ` (spaces) | matches GT (strip only) | documents `.strip()`-but-no-uppercase asymmetry |
| missing chrom_1 | blank primary | ValueError | required-field enforcement |
| non-integer pos | `pos="abc"` | error raised | `int(pos)` contract |
| epcr nan/inf | `nan`, `inf` | ValueError | range check catches non-finite |
| epcr=1.0 | — | 100 / 1.000 | upper bound inclusive |
| renamed header | `chrom1` not `chrom_1` | KeyError | exact column-name contract |
| minimal header | only proband_id,chrom_1,pos_1,ref_1,alt_1,epcr | parses (50/0.667 when the single variant is a true one; a junk singleton parses too but scores 0/0) | `*_2`,`finding_type`,`notes` are optional (`.get` defaults) but `epcr` is required — its absence is KeyError |
| header-only CSV | no data rows | app rejects: "No valid rows" | empty submission contract |
| extra proband rows | FAKE01 row before PROBAND01 | whole file rejected | app scores only first proband group — footgun |
| extra proband rows after | FAKE01 row after real rows | silently ignored | per-proband grouping + 10-row cap |
| F-max dilution | pair listed first, then 5 junk ALL @0.95 | 100 pts but F<1.0 | epcr-structure rule; pair must be first among the tied rows (file-order tie-break, `evaluation.py:107`) - listed last it would sit at rank 6 → only 10 pts |
| junk below top epcr | pair@0.95 + 9 junk@0.3 | 100 / 1.000 | our real CSV shape |
| epcr=0, 1.0001, -x | — | ValueError | range check (0,1] |
| 11 rows | — | ValueError | row cap |
| `finding_type=X` | invalid | ValueError | enum check |
| `SECONDARY` uppercase | — | accepted (lowercased) | normalization |
| blank chrom_2 fields | — | parses, 1-variant row | optional-field handling |
| unsorted input | low-epcr pair listed last | still scored by epcr | sort behavior |
| proband_id≠PROBAND01 | — | app-level reject | proband check |
| GT-wiring guard | monkeypatched GT | known scores | we're testing our fixtures, not the real key |
| funnel monotonic | stage outputs | counts non-increasing, ⊆ | funnel bugs |
| spike-in e2e | synthetic VCF→pipeline | pair top-3 | pipeline actually works |
| negative control | control VCF | no call | hallucinated-pair check |
| determinism | rerun | identical outputs | hidden nondeterminism |
| CSV writer | submit.py output | byte-valid for oracle | writer/scorer contract |

E2E gate: `pytest -m gate` runs the whole battery + builds the real CSV + asserts 100/1.000 locally
before any upload. Mutation check: corrupt each field of the real CSV one at a time — every corruption
must change the score or raise. One that doesn't = a scorer insight to document.

---

## 7. Risks & pivots

| Risk | Likelihood | Mitigation |
|---|---|---|
| Dataset access delayed | Medium | Gate-0 today; build ENTIRE harness on public stand-ins (HG002 + synthetic VCF + synthetic docx) so approval unblocks only the final rerun, not the work |
| VCF contradicts leak/forensics | Low-Med | Trust the pipeline (that IS the plan); report divergence honestly — even more differentiation |
| In-trans evidence weak (phase-block break) | Low-Med | Report evidence strength honestly; epcr reflects confidence; still best available call |
| Local RAM/CPU limits (24 GB/16T) | Medium | `PASS_ONLY` Exomiser; targeted DV; cloud spot for alignment (<$50); WSL2 for Linux-only tools |
| SpliceAI local scoring unavailable | Low | dbNSFP precomputed scores / alternative splice predictors; document substitution |
| Second track-1 submission unneeded | — | Spend a slot only on a genuinely different method (de novo recall) or a real correction |
| Track 2 scope creep (investigational drugs) | Medium | hard filter: market-approved only; combos allowed if justified [verified: deep dive §4] |
| Team-name/duplicate-entry bug | Low | identical `display_name` everywhere; single Track-2 submitter |
| Email bounce at deletion | Known | post attempt in Discussions per discussion #15 |

Kill criteria: if verified-VCF analysis shows no plausible recessive mechanism in BUB1B or any gene, we
submit the pipeline's top answer anyway (with confidence stated) — the write-up's rigor is invariant.

---

## 8. Timeline (37 days, deadline Oct 24 23:59 UTC)

| Window | Work |
|---|---|
| Sep 17-20 | Phase 0 (access request OUT today) + Phase 1 on stand-ins; harness + oracle + tests built |
| Sep 20-27 | Phase 2 both arms on spike-in + proband (when access lands); Phase 3 phasing + realignment |
| Sep 27-Oct 1 | Gates 2-4 green → **Track 1 submission #1** (~Oct 1); methods report v1 |
| Oct 1-15 | Track 2 mechanism→drug pipeline, evidence tiers, testability matrix; report draft; video |
| Oct 15-20 | Optional Track-1 method #2 (de novo recall); mock judging; report hardening; community artifact |
| Oct 20-24 | Final Track 2 submit (latest-only rule); repo public-ready; verify leaderboard; buffer |
| Oct 24+ | Repo public; deletion runbook; confirmation email; embargo rules observed |

Community check-in every ~3 days: discussions, rules changes, organizer announcements.

---

## 9. Verified-facts register (claim → source)

- Scoring semantics, row cap, epcr range, chrom case sensitivity, sort order → `hackathon-app/evaluation.py`;
  **every expected score in §6 re-verified by executing the vendored scorer on fixture CSVs** (2026-09-17),
  including both Remek-signature reproductions and the multi-proband footgun
- Submission requirements (GitHub/report/CSV), `model{N}_` naming, PROBAND01 check → `tabs/submit_track1.py`
- Track 2 latest-only rule, video requirement → `tabs/submit_track2.py`, `tabs/faq.py`
- Best-per-team grouping + earliest-tie-break sort → `utils.py:180-202`
- GT format + dataset names → `groundtruth.py`, `config.py`
- Methods xlsx question inventory incl. required GenAI disclosure → `static/templates/methods_description_form.xlsx`
- Judging rubric 35/25/25/15, timeline, prizes → `tabs/about.py`, `tabs/rules.py`
- Leaderboard live state (122 rows / 116 perfect) → Gradio API pull, 2026-09-17
- Host specs → WMI/CIM + `nvidia-smi` on this machine, 2026-09-17: Ryzen 7 260 (8C/16T), 24 GB RAM,
  **RTX 5050 *Laptop* GPU with 8 GB** (corrected from "4 GB"), ~750 GB free, Docker engine 29.6.2 via the
  `docker-desktop` WSL2 distro, `.venv` Python 3.12.13 with `huggingface_hub` 1.31 + `hf_transfer`
- VEP 116 current, plugins incl. AlphaMissense/SpliceAI/dbNSFP 5.3.1 → Ensembl release notes
- DeepVariant v1.10.0, ~2h WGS @96 vCPU, `--regions` support → github.com/google/deepvariant
- Exomiser genome-mode ~12-16 GB RAM, `PASS_ONLY` fallback, ~50-100 GB data → exomiser.readthedocs.io
- ACMG SF **v3.3** current (84 genes; June 2025) → GIM 2025;101454 — supersedes deep dive's "v3.2"
- BUB1B MANE Select ENST00000287598.11 / NM_001211.6 → Ensembl 115 / ClinGen
- Dataset contents, GRCh38 confirmation, PGT/PID, AF semantics, deletion/email rules, leaked-data
  forensics, Track-2 scope, community intel → `docs/DEEP_DIVE.md` (participant-reported items flagged)

**Open assumptions flagged for verification on first data touch:** exact VCF header strings, variant
count, Ti/Tv, coverage, the true pair's identity (pipeline decides), whether PGT/PID chains the two
candidate sites into one phase block.
