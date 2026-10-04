# MVA Hackathon 2026 - one-command reproduction.
# Python lives in .venv; override with PY=python3 if needed.
PY := .venv/Scripts/python.exe

.PHONY: test gate refs spike control report report-patient track1 citations audit all

## full test suite (skips slow / missing-corpus tests gracefully)
test:
	$(PY) -m pytest tests -v

## GATE battery only - run before any upload
gate:
	$(PY) -m pytest tests -v -m gate

## download public HPO corpus into env/corpus
refs:
	$(PY) tools/fetch_refs.py
	$(PY) tools/genes_to_disease_json.py

## build the synthetic stand-in cases
spike:
	$(PY) -c "import sys; sys.path.insert(0,'.'); from src import synth; synth.spike_in_case('results/spike_case'); print('spike_case built')"
control:
	$(PY) -c "import sys; sys.path.insert(0,'.'); from src import synth; synth.control_case('results/control_case'); print('control_case built')"

## run the whole Track-1 driver on the spike case
track1: spike
	$(PY) tools/run_track1.py --case results/spike_case --out results/t1_spike

## regenerate the methods report from results/ (no hand-typed stats)
report:
	$(PY) tools/make_report.py --run-dir results/t1_spike/funnel \
	  --truth results/spike_case/truth.json \
	  --sensitivity results/sensitivity.json \
	  --ablations results/t1_spike/ablations.json \
	  --phasing results/t1_spike/phasing_report.json \
	  --sf results/t1_spike/sf_findings.json \
	  --acmg results/t1_spike/acmg_report.json \
	  --eda results/t1_spike/eda_report.json \
	  --control-dir results/t1_control/funnel \
	  --real-spike-dir results/real_spike_run \
	  --real-spike-build env/real_spike/BUILD_REPORT.json \
	  --real-spike-truth env/real_spike/truth.json \
	  --out docs/report.md

## regenerate the methods report from the PATIENT run artifacts.
## NOTE: `make report` targets the synthetic spike run - use this target
## for the submission report so the patient numbers are what lands in
## docs/report.md.
report-patient:
	$(PY) tools/make_report.py \
	  --run-dir results/track1_patient_modal/track1_final_indelfix/funnel \
	  --eda results/track1_patient_modal/track1_final_indelfix/eda_report.json \
	  --eda-raw results/eda_patient/eda_report.json \
	  --hpo-terms data/case/hpo_terms.json \
	  --arm-a-genes results/exomiser_patient/WGS_EX2312012-PASS_ONLY.genes.tsv \
	  --allele-balance results/track1_patient_modal/track1_final/allele_balance.json \
	  --prior-run-dir results/track1_patient_modal_run2 \
	  --sensitivity results/sensitivity.json \
	  --ablations results/track1_patient_modal/track1_final_indelfix/ablations.json \
	  --phasing results/track1_patient_modal/track1_final_indelfix/phasing_report.json \
	  --sf results/track1_patient_modal/track1_final_indelfix/sf_findings.json \
	  --acmg results/track1_patient_modal/track1_final_indelfix/acmg_report.json \
	  --runlog results/track1_patient_modal/runlog.json \
	  --control-dir results/t1_control/funnel \
	  --spike-dir results/t1_spike/funnel \
	  --spike-truth results/spike_case/truth.json \
	  --real-spike-dir results/real_spike_run \
	  --real-spike-build env/real_spike/BUILD_REPORT.json \
	  --real-spike-truth env/real_spike/truth.json \
	  --arm-concordance results/track1_patient_modal/track1_final_indelfix/arm_concordance.json \
	  --arm-a-control env/exomiser/control/PROBAND01-PASS_ONLY.genes.tsv \
	  --mosdepth results/track1_patient_modal/track1_final/mosdepth/mosdepth_summary.json \
	  --deepvariant results/track1_patient_modal/track1_final/deepvariant/dv_findings.json \
	  --cnv results/track1_patient_modal/track1_final/cnv/summary.json \
	  --fastq-qc results/track1_patient_modal/track1_final/fastq_qc/aggregate/fastqc_report.json \
	  --offslice results/track1_patient_modal/track1_final/offslice_eval.json \
	  --run-where Modal \
	  --team nikhilpise \
	  --data-status "PATIENT RUN (PROBAND01, challenge proband) - funnel/ablation numbers below regenerate from results/track1_patient_modal/track1_final_indelfix (VEP-indel CSQ-matching fix); orthogonal evidence arms (mosdepth/DeepVariant/CNV/FASTQ-QC/allele-balance/offslice) cite track1_final, whose inputs are unaffected by the fix; external-validation sections cite the synthetic/real-spike harnesses." \
	  --out docs/report.md

## scorer-fixture audit battery (60 fixtures vs vendored oracle)
audit:
	$(PY) tools/audit_scorer_fixtures.py

## plan citation checker
citations:
	$(PY) tools/check_citations.py

## everything this target chain builds: cases -> track1 -> report -> tests.
## Sensitivity grid (results/sensitivity.json) and the real-spike external
## validation (env/real_spike/) are not produced by any target here - run
## tools/run_sensitivity.py / tools/build_real_spike.py first, or those
## report sections stay "Pending dataset access".
all: spike control track1 report test
	@echo "done: see docs/report.md and results/t1_spike/run_summary.json"
