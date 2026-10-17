# Track 1 completion audit - 2026-10-04

> **Resolution status (2026-10-05):** all four blockers below were closed
> on 2026-10-04 - the leaderboard upload verified server-side (100.0 rank
> points / 1.000 F-max, full match rank 1, row 139), `main` was pushed to
> origin, the GenAI disclosure + no-training record completed
> (`docs/llm_log.md`), and the report's factual errors were fixed
> (answer-aware framing, post-freeze config-change log, firewall wording).
> This file remains verbatim as the point-in-time audit record; current
> state lives in `docs/status.md` and `docs/track1_closeout.md`.

Scope: everything the hackathon requires for a Track 1 submission (CSV +
GitHub URL + methods report, scored automatically and then judged "for
scientific rigor and depth of understanding"), checked against the repo's own
completion claims (`docs/status.md`, `docs/rubric_self_assessment.md`,
`docs/submission_checklist.md`, `docs/report.md`) and against the artifacts on
disk. Every finding below was re-derived on 2026-10-03/04 (UTC/IST) with the
commands listed in the appendix. Nothing here relies only on the docs' own
claims.

## Bottom line

**Engineering status: done, and it holds up.** The CSV is byte-valid, the
vendored scorer still matches the live Space exactly, all 334 tests pass
(+8/8 on the real patient VCF), the 60-fixture scorer audit passes, the report
can be regenerated from artifacts, and the masked-run acceptance gates hold.

**Track 1 is NOT complete.** Four items block a complete submission:

1. Nothing has been uploaded, so the leaderboard score is unverified. The
   "100.0 / 1.000" in the docs comes from a stand-in ground truth that *is*
   our own prediction, which makes it circular (details in B1).
2. The code that produced the submission is not on GitHub: `main` is 24
   commits ahead of `origin/main`.
3. The GenAI disclosure, the only *required* field on the methods form, is
   incomplete. The no-training check the project set for itself was never
   recorded as done.
4. The methods report has several statements that are **factually wrong as
   written** (leak firewall, "frozen" config hash, "fully automated", data
   sources), plus one real pipeline bug (indels are silently dropped). Most
   teams sit at 100/1.000 and ties are broken by earliest submission, so the
   write-up is the only place left to stand out. These issues therefore cost
   more than any score issue would.

Recommended order of work is at the end (section 6).

---

## 1. Requirement scorecard

| # | Track 1 requirement (source) | Status | Evidence / gap |
|---|---|---|---|
| R1 | Gated data access + attestation (rules.py:36) | DONE | All 11 files hash-verified (`docs/data_audit_2026-10-03.md` s.1). Verbatim attestation text not archived (status.md external #3) |
| R2 | Predictions CSV, GRCh38, chr-prefixed, <=10 rows, epcr in (0,1], finding_type (submit_track1.py:37-61) | DONE | `nikhilpise_answer-blind-funnel.csv` is 198 B, ASCII, no BOM, LF, 1 row, sha256 `9e80a9fc...f186`. Byte-identical to `results/track1_patient_modal/track1_final/submission.csv` |
| R3 | CSV filename includes username + method (submit_track1.py:63-68) | DONE | `nikhilpise_answer-blind-funnel.csv` |
| R4 | Report `.pdf`/`.md`, username in filename (submit_track1.py:72-85) | PARTIAL | `docs/report.md` exists. The planned `nikhilpise_track1_report.md` (team.md:47) is not staged. Content issues are in section 3 |
| R5 | GitHub URL `https://github.com/...` (submit_track1.py:140) | PARTIAL | Repo exists (private, which is allowed until close). **24 local commits unpushed.** `origin/main` has none of the Modal/mask/evidence-arm code that produced the CSV |
| R6 | Repo public after close, reproducible code (submit_track1.py:89-97, faq.py:67) | NOT YET | Due after Oct 24. Needs a privacy scrub first (M3). Patient-report build command undocumented (M6) |
| R7 | GenAI disclosure: provider + plan/tier + *setting* (xlsx Q "(required)", discussion #2) | **INCOMPLETE** | Report s.10 omits the data-handling setting. llm_log never records verified no-training/retention terms (B4) |
| R8 | Methods form: 13 Track 1 prompts (xlsx sharedStrings 2-12, 21, 23) | PARTIAL | `report_map.md` maps all 13, but the report does not answer them as a Q&A and several answers are inaccurate (H1-H3, H5) |
| R9 | Display name consistent (utils.py grouping) | DONE | `nikhilpise` locked in `docs/team.md` |
| R10 | Submit + leaderboard verify (quota 6) | **NOT DONE** | Upload has not happened |
| R11 | Deadline Oct 24 23:59 UTC | OK | Live upstream timeline re-checked 2026-10-04: close unchanged. Judging extended to Dec 17, winners Dec 18 (vendored copy predates this) |
| R12 | Data deletion within 30 days of close + email (rules.py:60-65) | PLANNED | `docs/deletion_runbook.md` exists. Executes post-close (~Nov 23) |

---

## 2. Blockers (must clear before / at upload)

### B1. Leaderboard score is unverified, and the local "100/1.0" is circular

`status.md:109` and the rubric cite "rank_points=100.0, f_max=1.0 (BUB1B
stand-in GT)". The stand-in ground truth is our own predicted pair, so that
check proves the bytes are valid. It says nothing about whether the answer is
correct. I re-scored the exact upload bytes with the vendored oracle under the
three hypotheses the repo itself considers live (DEEP_DIVE s.9c-9d):

| Assumed ground truth | rank_points | f_max | match |
|---|---|---|---|
| {40209701 T>G, 40220612 T>G} (our pair, leading hypothesis) | 100.0 | 1.000 | full @1 |
| {40209701 T>G, [withheld] A>G} | 50.0 | 0.500 | partial @1 |
| {[withheld] A>G, 40220612 T>G} | 50.0 | 0.500 | partial @1 |

The public forensics favour our pair: 116 entries at 100/1.0, plus a 50/0.5
entry whose pair matches the "one T>G + the A>G" signature. That is still
inference, not verification. **Action:** upload once, read the leaderboard
within ~5 min, and record the row in decisions.md + RETENTION (per checklist).
If the result is partial, the alternative pairs above are the fallbacks for
the remaining 5 quota slots.

### B2. The submitted code is not on GitHub

`git status -sb` shows `main...origin/main [ahead 24]`. `origin/main` stops at
`d2e2338` (2026-09-26). So `tools/modal_app.py`, `src/loci.py`, the
`artifact_loci` config, the evidence arms and every patient-run doc are local
only. **Action:** push (or PR + merge) before uploading, so the URL in the
submission points at the code that produced the CSV. Pushing was not done
here (not requested).

### B3. Report file not staged under the planned name

`team.md:47` plans `nikhilpise_track1_report.md`; that file does not exist.
Trivial to fix, but do it after the report fixes in section 3.

### B4. GenAI disclosure (the one required form field) is incomplete

- Report s.10 says only "Cognition Devin CLI (SWE-2 Max)". The organizers'
  ruling (discussion #2, cfsuver 2026-08-26) requires **provider, plan/tier,
  and the relevant setting**. Two conditions must also hold: (a) no training
  on inputs/outputs and no rights taken; (b) retention limited in time and
  purpose. Their example: "Anthropic API, Claude Sonnet, commercial terms, no
  training on customer content".
- `docs/llm_log.md` has a "Data-handling terms" column. Every row says "Verify
  no-training clause..." or "No-training clause check required". **None
  records that the check was done.** The log's own gate (llm_log.md:41-43)
  says the clause must be verified and cited *before* any prompt touches
  patient-derived data. Rows from 2026-10-01 onward show that patient-derived
  findings were already in prompts: named BUB1B variants, coordinates,
  genotype strings, AFs.
- The underlying model provider(s) behind Devin are not named. The
  organizers' caution (b) also applies: credit or grant programs can override
  account defaults.
- This audit session also read patient-derived findings (top-ranked
  hypotheses, gnomAD AFs, AD counts), so it needs its own llm_log row.

**Action (operator-only):** confirm your actual Cognition/Devin plan's
no-training and retention terms. Quote or cite them in llm_log, add this
session's row, and rewrite report s.10 as one line in the organizers' format.
I cannot verify your account's terms from here.

---

## 3. High - judged-write-up credibility and scientific rigor

### H1. The "Leak firewall" statement in the report is false as written

Report s.11 (generated by `tools/make_report.py:814`): "no leaked-Space
coordinates/genes/values in code, tests, configs, or this report". Counter-
evidence in the repo:

- `tools/run_fastqc.py:37` hard-codes "Leaked / participant-reported run
  metrics". Report s.2b prints them as the `expected` column and labels them
  "leaked-run expectations" / "leaked prior" (report.md:92, 94).
- `tools/modal_app.py:84` hard-codes `BUB1B_PAIR` coordinates. The pipeline
  derived these after observing its own output, which is defensible, but they
  are coordinates in code.
- `config/pipeline.yaml:115` names BUB1B (`lof_mechanism_genes`).
- `docs/plan.md` s.1.3 and `docs/DEEP_DIVE.md` s.9 record that the leading
  pair was known from the leak and leaderboard forensics *before* the
  pipeline was built.

Once the repo is public, a judge who reads the README ("answer-blind"), then
plan.md s.1.3, then report s.11 sees a direct contradiction. **Fix:** replace
the absolute claim with an accurate one. For example: "answer-aware build
under a firewall. The candidate pair was publicly inferable before analysis
(plan.md s.1.3); thresholds were frozen pre-data; no leaked value enters
scoring; the FASTQ QC expectations are participant-reported metrics, used only
as a sample-identity sanity check." Rename "leaked" to "participant-reported"
in the QC table.

### H2. "Frozen pre-analysis" config hash is not the frozen config

Report s.1 and s.11 present config sha256 `0286865c373b` as "frozen
pre-analysis". That is the hash of the *current* config, which includes the
post-freeze `artifact_loci` block (decisions.md row dated 2026-10-04,
pipeline.yaml:129-137). **Fix:** report the frozen-commit hash (2e8e3a5 /
`frozen_at: 2026-09-22`) and the run hash side by side, and list the
post-freeze decisions.md rows by name.

### H3. Section 5 "automated output, no hand curation" conflicts with the mask decision

The xlsx asks: "automated output ... or ... downstream manual review and
curation?" Report s.5 answers that it is automated and that "No variant was
added, removed, or re-ordered by hand". But:

- The extended-MHC mask was a human decision, made after seeing the patient
  output (all emitted run-2 rows were MHC-region hypotheses). It turned the run-2 CSV
  (BUB1B at row 4, epcr 0.0637) into the final CSV (BUB1B sole row).
- decisions.md:18 lists among rejected alternatives "accept the ~25-pt score
  (unacceptable vs the frozen first-upload goal)". In other words, the stated
  motivation includes the leaderboard score.
- "Direction-neutral" (decisions.md, rubric, pipeline.yaml:134) is
  misleading. The mask cannot raise any *score*, but it raises *ranks*, and
  rank is what gets scored.

The decision itself is defensible: MHC artifacts are a well-known class, and
Exomiser converges on the same locus. The problem is the answer to the form
question. **Fix:** describe the mask in s.5 as a post-observation manual
curation step, report the run-2 vs final CSV side by side, and drop or qualify
"direction-neutral".

### H4. Pipeline bug: virtually every indel loses its annotation (silently)

`src/vcf.py:185` `csq_for_alt` requires `CSQ Allele == ALT` exactly. VEP
`--vcf` output trims the shared leading base for indels (e.g. REF `G` ALT `GC`
gets CSQ Allele `C`). Measured on `data/WGS_exon.vep.vcf.gz`, first 200,000
records: **34,389 of 34,552 indels (99.5%) have no matching CSQ allele**, and
0 SNVs are affected. The patient EDA counter even flagged it:
`n_csq_allele_unmatched = 2,056,309` in
`track1_final/eda_report.json` (the comment at `src/vcf_qc.py:171-173` warns
this "would silently lose every gene assignment"), but nothing acted on it.

Consequence: frameshift, inframe and splice-region indels never get a
gene/consequence, so they can never reach a hypothesis. This does not change
the current answer (both variants are SNVs). It does contradict the
"genome-wide, case-agnostic" claim and the scalability story. Tests miss it
because the synthetic fixtures (`src/synth.py`) write untrimmed alleles.
**Fix:** match on VEP's minimal allele (strip the shared prefix) or add
`--allele_number` and match on `ALLELE_NUM`. Add a trimmed-allele regression
test. Then either rerun or disclose it as a limitation.

### H5. Data-sources section over-claims

Report s.6 lists "REVEL/dbNSFP 5.3.1, ... LOEUF, phyloP, gnomAD v4.1". The
patient CSQ header has 57 fields with **no dbNSFP, LOEUF or phyloP fields**,
and gnomAD is **exomes only** (`gnomADe_*`). The VEP command is at
`tools/modal_app.py:201-229`. runtime_log 2026-10-02 records that the dbNSFP
registration was rejected and REVEL came from Zenodo instead. In addition,
SpliceAI's `indel=` parameter points at the SNV file (modal_app.py:220-221),
so indels never get SpliceAI scores. The synthetic fixtures *do* carry
LOEUF/phyloP, so validation ran on a richer annotation set than production.
**Fix:** list exactly the sources in the CSQ header, with versions.

### H6. The ranking model puts 4 likely-artifact singletons above the true pair, and the report never says so

`track1_final/funnel/result_head.json` ranks 1-4 and 6-8 are `hom_alt`
"LoF" calls (MDM2, NF1, MAD2L2, KIF1B, VHL, ARG1, DGCR6). They share these
traits:

- damage_votes 0
- "absent" from an exome-only gnomAD
- mostly on non-canonical or non-coding transcripts (`c.-602+2C>T`,
  `c.-691-1G>A`, `n.187-2A>G`, `n.306+1G>C`)

BUB1B is rank 5 (score 0.7159). Only `singleton_emit_floor` keeps those rows
out of the CSV, which is why the sole primary row carries epcr 0.1324. The
`CANONICAL` field is in the CSQ but unused in `src/` (no transcript filter).
A judge comparing the "Pathogenic" headline with a 13% epcr will ask about
this. **Fix:** at minimum, add a report paragraph explaining rank 5, the
singleton floor and the epcr. Better, run a disclosed canonical/MANE-only
sensitivity arm.

### H7. Robustness claims overstate the patient-level evidence

- The plan's own rule (plan.md:91-93): the pair "must remain top-5 in every
  ablation or we report the fragility honestly". Patient results: clinvar 6,
  damage_predictors 125, hpo 120, gnomad 2, phasing 5. **That fails the rule
  on 3 of 5 drops.** The abstract (make_report.py:832) says "held rank <=125
  under every leave-one-source-out ablation", which is spin.
- The phasing ablation means nothing on this sample: there is no phase
  evidence, so its rank equals the baseline.
- "Robust across grid: True" (s.3b) was measured on the **synthetic** corpus.
  On the patient, the nonsense allele's popmax is gnomADe NFE **9.98e-05**,
  0.2% below `af_max` 1e-4. At the grid's 1e-5 setting it fails the rarity
  tier and the pair cannot form. **Fix:** say all of this plainly in s.3a/3b
  and s.12, ideally with a patient-corpus grid.

### H8. The report lacks the "depth of understanding" content judges score

Missing from `docs/report.md`:

- the 8 HPO terms and their names (already listed in data_audit s.1.3)
- phenotype-to-MVA1 reasoning
- BUB1B/BubR1 biology and the known null + hypomorph MVA1 genotype pattern,
  with literature
- the **Exomiser patient result** (BUB1B AR rank 1, 0.9819, OMIM:257300; the
  report only says "top-20 overlap 1")
- read-level allele balance at the sites (data_audit s.4)

The abstract (s.12) never mentions the patient call, the orthogonal arms or
Modal. There are no figures (the plan's "in-trans evidence figure" is a
table). **Fix:** add a findings/interpretation section, add the Exomiser
result, rewrite the abstract around the actual patient result, and add a
"Methods form answers" section that quotes the 13 xlsx prompts verbatim.

---

## 4. Medium

| ID | Finding | Evidence | Fix |
|---|---|---|---|
| M1 | ACMG headline "Combined call: Pathogenic (11 pts)" adds points across two alleles, which is not ACMG/AMP practice. The caveat is there, but the headline invites clinician criticism. The missense PP3 fires with REVEL 0.472 (< ClinGen-calibrated 0.644), so it presumably rests on AlphaMissense 0.92, which is not stated. PVS1 is only possible via an allowlist containing just BUB1B | report s.8; acmg_report.json; pipeline.yaml:114-115 | Report per-allele classes; drop the summed label or call it "ranking aggregate"; state the PP3 source |
| M2 | PGT/PID contradiction: report says "present: True/True", status.md:77 says "patient VCF carries no PGT/PID". Truth: header declares them, 770,458 records phased (raw VCF) / 66,743 (exon slice), and neither BUB1B site has them | eda_report.json `n_phased_gt`; data_audit s.1.1, s.5.2 | One accurate sentence in report s.2/s.4 |
| M3 | Public-repo privacy. `data_audit` s.1.3 has narrative clinical details beyond HPO (gestational age, birth weight, parental miscarriages); s.1.2 has instrument/run/index barcodes. `DEEP_DIVE` s.9 republishes leak-derived VAFs and names the leaking Space. Rules forbid re-identifying detail (rules.py:148-150) | docs/data_audit_2026-10-03.md, docs/DEEP_DIVE.md | Scrub/redact before the repo goes public |
| M4 | Sex-check numbers mixed: report s.2 shows exon-slice EDA (X-het 12.9%, 569 Y calls), limitation 9 says "~7%" (full-VCF EDA) | eda_report.json vs runtime_log 2026-10-01 | State which input each number comes from |
| M5 | Runtime/cost: report s.9 lists the same funnel as 2340 s and 3291 s, and gives no $ figure, although the form asks for cost and runtime_log has "est. <$5 total" | report s.9; runtime_log:22 | One row per job, plus the total $ estimate |
| M6 | Reproducibility: no documented command for the patient report. `make report` renders the **synthetic** t1_spike run into `docs/report.md` and would overwrite the patient report. I reconstructed the command (appendix); the output matches the committed report except the timestamp and two arg-dependent strings | Makefile:31-45 | Add a `report-patient` target / README line |
| M7 | Presentation: raw floats (Ti/Tv `2.0883825992133036`, coverage `51.51723564387097`); "all_pass: **False**" in FASTQ QC reads as a failure; "INFO AF semantics: ambiguous" unexplained | report s.2, s.2b | Round values; lead with the disposition |
| M8 | Arm concordance "top-20 overlap 1" is shown without context (4,694 vs 49,418 genes ranked) | arm_concordance.json | Explain what low overlap does and does not mean |
| M9 | CSV notes say only "BUB1B compound_het stop_gained+missense_variant", with no HGVS (c.2210T>G p.Leu737Ter / c.3006T>G p.Asn1002Lys) | submission.csv | Optional: richer `notes` (scorer ignores it; reviewers read it) |

## 5. Low / hygiene

- `status.md:136` still says the gnomad ablation is "pending". It has landed
  (rank 2). The header line "Only the leaderboard upload remains" is
  inaccurate given B2-B4.
- `rubric_self_assessment.md:42` cites a "2026-10-04 singleton_emit_floor
  row"; the correction row is dated 2026-10-03. Rubric:71 "byte-identical
  reruns": det1/det2 are identical **only after removing `runtime_sec`**
  (verified). README:47 states this correctly.
- pyflakes: `tools/make_report.py:824` f-string without placeholders; unused
  `conftest.REPO` import in `tests/test_funnel.py:11` and
  `tests/test_loci.py:15`. No linter is configured in the repo.
- `tests/test_data_integrity.py:384` skip message "patient VCF not on disk
  yet" is stale (the VCF is on disk; the gate passes with `MVA_REAL_VCF` set).
- `src/prioritize.py:44` and `pipeline.yaml:99-101` say singletons are
  "dominant_het/x_linked". The code (`prioritize.py:55`) treats any
  hypothesis with <2 variants, including `hom_alt`, as a singleton. Fix the
  comment.
- Vendored `hackathon-app/` is 2 upstream commits behind (timeline + typo).
  `evaluation.py`, `submit_track1.py`, `utils.py`, `config.py` and
  `groundtruth.py` are byte-identical to live upstream (verified via curl).
- The final CSV sits untracked at repo root. Consider committing a KEEP copy
  (CC-BY deliverable) under e.g. `submissions/`.
- README:14 "290+ tests" is out of date (335 collected).

---

## 6. Independently verified (no action needed)

- **CSV contract**: 1 row, `PROBAND01`, `chr15`, pair in one row, epcr 0.1324
  in (0,1], `primary`, ASCII/LF/no-BOM. The scorer gives full match at rank 1
  under the leading hypothesis.
- **Oracle parity**: `scorer/evaluation.py` == `hackathon-app/evaluation.py`
  == live upstream.
- **Tests**: 334 passed, 1 skipped (real-VCF gate); with `MVA_REAL_VCF` set,
  `test_data_integrity.py` 8/8 passed (93 s).
- **Scorer audit**: "ALL 60 FIXTURES VERIFIED". Citation checker: 17 line
  citations + 13 section refs + 21 file refs pass.
- **Masked-run gates**: emitted=1, csv_rows=1, 0 HLA rows, funnel arithmetic
  289,725 + 6,353 = 296,078, no monotonicity violations.
- **Evidence arms present and consistent with the report**: DeepVariant 1.9.0
  (both sites 0/1 PASS, GQ 42/35), manta+cnvpytor (0 calls at BUB1B), mosdepth
  (WGS 42.08x, locus 45.26x), fastp x4, off-slice [intronic site withheld] evaluation, read-
  level phasing (0 spanning / 75 partial, `unknown`).
- **Report regeneration**: the reconstructed `make_report.py` invocation
  reproduces `docs/report.md` (3 diff lines, all explained above).
- **Retention**: `.gitignore` contains `data/`, `results/`, `env/` and root
  genomic files. Only the 3 RETENTION manifests are tracked from those trees.

---

## 7. Recommended order of work

1. **Report truthfulness pass** (H1, H2, H3, H5, H7, M1, M2, M4, M5, M7).
   Every item is a text change in `tools/make_report.py` + regenerate. Highest
   return for the judged half.
2. **Report depth pass** (H8, H6 paragraph, M8): findings/interpretation
   section, Exomiser result, HPO list, explain rank 5 / epcr 0.13, an abstract
   about the patient, and a verbatim Q&A for the 13 form prompts.
3. **GenAI disclosure** (B4): you verify the terms, then update llm_log rows
   and the report line.
4. **Indel bug** (H4): fix + regression test. Then decide whether to rerun on
   Modal or disclose. A rerun does not change this answer, but it does fix the
   scalability claim.
5. Fix the docs drift and hygiene items (section 5) and add a `make
   report-patient` target (M6).
6. **Push** (B2) and stage `nikhilpise_track1_report.md` (B3).
7. **Upload once, verify the leaderboard** (B1), and log it in decisions.md +
   RETENTION.
8. Before the repo goes public after Oct 24: privacy scrub (M3), then flip
   visibility. Deletion runbook + confirmation email within 30 days.

---

## Appendix - commands run for this audit

```sh
.venv/Scripts/python.exe -m pytest tests -q                      # 334 passed, 1 skipped
MVA_REAL_VCF=data/WGS_EX2312012_HGWCNDSX7.vcf.gz \
  .venv/Scripts/python.exe -m pytest tests/test_data_integrity.py -q   # 8 passed
.venv/Scripts/python.exe tools/audit_scorer_fixtures.py          # ALL 60 FIXTURES VERIFIED
.venv/Scripts/python.exe tools/check_citations.py                # ALL CHECKS PASS
.venv/Scripts/python.exe -m pyflakes src tools tests scorer      # 3 warnings
cmp nikhilpise_answer-blind-funnel.csv results/track1_patient_modal/track1_final/submission.csv
cmp scorer/evaluation.py hackathon-app/evaluation.py
curl <Space>/raw/main/{evaluation.py,tabs/submit_track1.py,utils.py,config.py,groundtruth.py}  # all identical
git status -sb                                                   # ahead 24
gh repo view --json visibility                                   # PRIVATE

# patient report reconstruction (undocumented in repo):
F=results/track1_patient_modal/track1_final
python tools/make_report.py --run-dir $F/funnel \
  --spike-dir results/t1_spike/funnel --spike-truth results/spike_case/truth.json \
  --eda $F/eda_report.json --sensitivity results/sensitivity.json \
  --ablations $F/ablations.json --phasing $F/phasing_report.json \
  --sf $F/sf_findings.json --acmg $F/acmg_report.json \
  --runlog results/track1_patient_modal/runlog.json \
  --control-dir results/t1_control/funnel --real-spike-dir results/real_spike_run \
  --real-spike-build env/real_spike/BUILD_REPORT.json \
  --real-spike-truth env/real_spike/truth.json \
  --arm-concordance $F/arm_concordance.json \
  --mosdepth $F/mosdepth/mosdepth_summary.json \
  --deepvariant $F/deepvariant/dv_findings.json --cnv $F/cnv/summary.json \
  --fastq-qc $F/fastq_qc/aggregate/fastqc_report.json \
  --offslice $F/offslice_eval.json --run-where Modal --team nikhilpise --model-n 1 \
  --data-status "PATIENT RUN COMPLETE - ..." --out <tmp>
```

Ad-hoc probes (not committed): oracle re-scoring under 3 ground-truth
hypotheses; CSQ-allele match rate per indel/SNV over the first 200k records
of `data/WGS_exon.vep.vcf.gz`; gnomADe per-population AFs at the two sites;
det1/det2 diff with `runtime_sec` removed; top-8 of `result_head.json`.
