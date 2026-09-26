# MVA Hackathon 2026 - one-command reproduction.
# Python lives in .venv; override with PY=python3 if needed.
PY := .venv/Scripts/python.exe

.PHONY: test gate refs spike control report track1 citations audit clean

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
	  --real-spike-dir results/real_spike_run \
	  --real-spike-build env/real_spike/BUILD_REPORT.json \
	  --real-spike-truth env/real_spike/truth.json \
	  --out docs/report.md

## scorer-fixture audit battery (57 fixtures vs vendored oracle)
audit:
	$(PY) tools/audit_scorer_fixtures.py

## plan citation checker
citations:
	$(PY) tools/check_citations.py

## everything: cases -> track1 -> sensitivity -> report -> tests
all: spike control track1 report test
	@echo "done: see docs/report.md and results/t1_spike/run_summary.json"
