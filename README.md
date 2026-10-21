# MVA Hackathon 2026 - variant prioritization + drug repurposing

[![ci](https://github.com/nikhilpravinpise/MVA-Hackathon-2026/actions/workflows/ci.yml/badge.svg)](https://github.com/nikhilpravinpise/MVA-Hackathon-2026/actions/workflows/ci.yml)
[![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue)](requirements.txt)
[![release](https://img.shields.io/github/v/release/nikhilpravinpise/MVA-Hackathon-2026)](https://github.com/nikhilpravinpise/MVA-Hackathon-2026/releases)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23529208.svg)](https://doi.org/10.5281/zenodo.23529208)
[![competition space](https://img.shields.io/badge/competition-MVA%20Hackathon%202026-blueviolet)](https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026)

![Rescue, Remove, Intercept - a testable approved-drug portfolio for BUB1B
mosaic variegated aneuploidy, and the open engine that built it](docs/assets/title.png)

One child's genome -> a verified causal call -> a ranked, testable
approved-drug portfolio, plus the open engine that produced it. Every
number in both reports is regenerated from committed artifacts, every
citation is resolved live and retraction-checked, and the whole suite
(575 tests) replays on a bare clone with no patient data.

## Results at a glance

| | Track 1 - variant prioritization | Track 2 - drug repurposing |
|---|---|---|
| Deliverable | Submission CSV + report | 4-lead tested portfolio + ~10,800-word report + 179 s pitch video |
| Headline | **100.0 / 1.000** on the vendored official scorer, rank 1, verified on the public leaderboard | **recall@10 = 0.56** on a blind 9-gene benchmark run from the same code |
| Honesty | No leaked variant used as truth; answer-blind funnel | 37 mechanism-opposed drugs excluded *and listed*; engine misses named, not hidden |
| Verification | 60-fixture oracle battery; deterministic reruns | 137/137 citations resolve live, retraction-checked; strict gate: 0 uncovered claims |
| Patient data | Never leaves `data/` (gitignored, retention-manifested) | none used |

## Start here (judges)

- **Track 2 report** (the judged artifact): [`nikhilpise_track2_report.md`](nikhilpise_track2_report.md)
- **3-minute pitch video** (YouTube, unlisted): <https://youtu.be/YD2dIVnmMME>
- **PDF + captions + video file**: the [`track2-submission` release](https://github.com/nikhilpravinpise/MVA-Hackathon-2026/releases/tag/track2-submission)
- **Plain-language summary for families**: [`docs/track2/FAMILY_SUMMARY.md`](docs/track2/FAMILY_SUMMARY.md)
- **How the portfolio was chosen**: [`docs/track2/candidates.md`](docs/track2/candidates.md) + [`docs/track2/engine.md`](docs/track2/engine.md)
- **Scored against the official rubric**: [`docs/track2/rubric_self_assessment.md`](docs/track2/rubric_self_assessment.md) (two hostile red-team passes: [`redteam.md`](docs/track2/redteam.md), [`redteam2.md`](docs/track2/redteam2.md))
- **Track 1 report**: [`nikhilpise_track1_report.md`](nikhilpise_track1_report.md); submitted bytes: [`nikhilpise_answer-blind-funnel.csv`](nikhilpise_answer-blind-funnel.csv)
- **Everything else**: [`docs/README.md`](docs/README.md) - the full documentation map

## Contents

- [Layout](#layout)
- [Reproduce (stand-in harness - zero patient data)](#reproduce-stand-in-harness---zero-patient-data)
- [Scoring contract (verified, not assumed)](#scoring-contract-verified-not-assumed)
- [Track 2 - drug repurposing](#track-2---drug-repurposing)
- [Verification](#verification)
- [Acknowledgement](#acknowledgement)

## Layout

| Path | What |
|---|---|
| `src/` | funnel modules (vcf, triage, genes, pheno, prioritize, phasing, reads, sf_scan, acmg, submit, vcf_qc, synth) |
| `tests/` | oracle parity, CSV contract, adversarial bytes, funnel unit, e2e gates, freshness pins, plus the Track-2 suites (mechanism, engine, direction layer, PRISM/ESM, citation gate, report + PDF generators, video builder) - 540+ tests |
| `tools/` | runners: audit_scorer_fixtures, audit_freshness, check_citations, check_discussions, fetch_public_vcfs, fetch_refs, fetch_big, genes_to_disease_json, normalize_contigs, run_pipeline, run_track1, run_sensitivity, make_report, make_figures, make_arm_a_csv, public_release_check, run_eda, extract_hpo, run_fastqc, run_phasing, run_vep, run_exomiser, compare_arms, run_realign, run_cnv, build_real_spike, revel_to_vcf, gnomad_split, modal_app |
| `scorer/` | vendored `evaluation.py` - the official scorer oracle (see `scorer/NOTICE.md`) |
| `config/` | frozen `pipeline.yaml` + `acmg_sf_v33.json` |
| `docs/` | plan.md (source of truth), status.md (phase-by-phase compliance map), report.md (regenerated), report_map.md, report_model2.md (Arm-A model report), figures/ (report SVGs + ASCII pileup, generated), decisions/team/llm/runtime logs, disclosure position, attestation_hf_gated_access.md (verbatim gating form), FAMILY_EXPLAINER.md + ANSWER_BLIND_PROTOCOL.md (community/award artifacts) - see `docs/README.md` for the full map |
| `submissions/` | upload-ready CSVs (as-submitted model1 copy + model2 candidates), each oracle-verified |
| `data/` `results/` | patient data + outputs - gitignored; `RETENTION.md` manifests tracked |
| `env/` | downloaded public corpora (gitignored, re-fetchable) |

## Reproduce (stand-in harness - zero patient data)

```sh
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Linux/macOS: .venv/bin/python
.venv/Scripts/python.exe -m pytest tests -q   # the suite
make refs        # download hp.obo + phenotype.hpoa + genes_to_phenotype
make spike control    # build synthetic proband + negative control
make track1      # EDA -> funnel -> SF -> phasing -> CSV -> oracle score
make report      # regenerate docs/report.md from results/ (synthetic run)
make figures     # regenerate docs/figures/*.svg + pileup_ascii.md
make report-patient  # regenerate docs/report.md from the PATIENT artifacts
                     # (results/track1_patient_modal/track1_final_indelfix
                     # funnel + track1_final orthogonal arms) - the
                     # submission report; `make report` alone renders the
                     # synthetic spike run instead
make report-upload   # figures + report-patient + the repo-root upload
                     # copy nikhilpise_track1_report.md (figure links
                     # prefixed docs/figures/ for root-relative paths)
make audit       # 60-fixture scorer audit battery
make freshness   # doc-vs-artifact staleness audit (audit_freshness.py)
make gate        # gate-critical tests only
make citations   # docs/plan.md citation checker
make all         # refs -> cases -> track1 -> report end to end
```

`tools/run_track1.py --case <dir>` runs the identical flow on the patient
bundle once gated access lands (`data/`); everything below is already
green on synthetic + public stand-ins:

- synthetic spike-in: compound-het pair recovered **rank 1**, in-trans
- negative control: **0 hypotheses** emitted (no hallucinated calls)
- real external validation: real ClinVar pair on HG002 background,
  REST-VEP annotated (cache-backed) -> **rank 1**
- submission bytes -> vendored oracle: **100.0 / 1.000**, rank 1
- determinism: identical artifacts on rerun (except `runtime_sec` wall-clock provenance)

## Scoring contract (verified, not assumed)

The scorer sorts rows by epcr desc; full match = BOTH true variants in ONE
row; chrom is case-sensitive (`chr15` yes, `CHR15`/`15` no); epcr in (0,1];
<=10 rows; `finding_type` in {primary, secondary}; BOM or comma-only lines
fail the file. `src/submit.py` satisfies all of it; the test suite replays
60 adversarial fixtures plus a mutation audit through the vendored oracle.

Patient data never leaves `data/`; no variant from any leaked Space is used
as ground truth - the pipeline output is the submission.

## Track 2 - drug repurposing

From the Track 1 genotype to a testable, approved-drug portfolio: a
gene-agnostic engine (`src/track2/`) expands a STRING disease module, pulls
drug-target evidence from Open Targets/ChEMBL/DGIdb, keeps approved
medicines only (ChEMBL max_phase 4, not withdrawn), scores network
proximity and LINCS L1000 signature reversal, applies a cited
mechanism-direction layer, and writes committed evidence JSON that the
report, citation gate and tests all read. A retrospective benchmark on
genes with known approved repurposings is run blind from the same code.

| Path | What |
|---|---|
| `src/track2/` | engine (`engine.py`, `sources.py`, `httpcache.py`), scoring (`scoring.py`, `proximity.py`), safety layer (`direction.py`), PRISM (`prism.py`), benchmark (`benchmark.py`), config (`t2config.py`) |
| `tools/` | `run_track2.py`, `t2_mechanism.py`, `t2_prism.py`, `make_track2_report.py`, `verify_citations.py`, `make_track2_pdf.py` |
| `docs/track2/` | `engine.md` design doc, `mechanism.md`, `candidates.md` screen log, `submission_fields.md`, `abstract.md`, `FAMILY_SUMMARY.md`, `evidence/` committed JSON (candidates, benchmark, dossiers, portfolio, testability, prism, esm) |
| `docs/track2_report.md` | the generated report (template `docs/track2_report_template.md`; upload copy `nikhilpise_track2_report.md`) |
| `video/` | 3-minute pitch builder (`scenes.yaml` + `build.py` -> `out/pitch.mp4`) |

```sh
make track2            # engine run + benchmark (replay mode; --mode live re-pulls)
make track2-report     # regenerate docs/track2_report.md + upload copy
make track2-citations  # citation gate over the Track-2 tree (0 unresolved)
make track2-pdf        # nikhilpise_track2_report.pdf - needs system python with
                       # `pip install markdown-it-py playwright` and Chrome
make track2-video      # needs .venv-video (edge-tts + playwright + pyyaml),
                       # ffmpeg and Chrome - see video/README.md
make track2-all        # report -> citations -> tests, in order
```

## Verification

CI (`.github/workflows/ci.yml`) runs the suite on Ubuntu + Windows against
Python 3.12 and 3.13, plus a gates job that replays the citation cache in
strict coverage mode, runs the doc-vs-artifact freshness audit, and tripwires
on committed secrets. Locally, the same gates are:

```sh
python tools/audit_freshness.py                       # 0 FAIL
python tools/verify_citations.py --offline --coverage-strict
python tools/public_release_check.py                  # secrets scan over history
python -m pytest tests -q                             # the suite
```

## Acknowledgement

*This work was made possible through the Hackathon, organized by Sage
Bionetworks in partnership with the MVA Society, Hugging Face, and
BEACON (The Benchmarking, Evaluation, and Assessment Consortium for
Science), with prize sponsorship from AWS and Anthropic. We are deeply
grateful to the child and their family who generously contributed their
data and their story to advance research into this rare disease. We
acknowledge their trust in making this Hackathon possible.*

## License

[MIT](LICENSE)
