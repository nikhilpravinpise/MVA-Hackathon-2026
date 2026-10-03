# MVA Hackathon 2026 - Track 1 pipeline

An answer-blind, deterministic N-of-1 variant-prioritization funnel for the
Mosaic Variegated Aneuploidy hackathon: genotype QC -> gnomAD rarity tier ->
consequence/damage ensemble -> per-gene inheritance hypotheses (compound-het,
hom-alt, dominant, X-linked) -> HPO phenotype scoring -> rank-mapped epcr ->
submission CSV validated against the vendored official scorer.

## Layout

| Path | What |
|---|---|
| `src/` | funnel modules (vcf, triage, genes, pheno, prioritize, phasing, reads, sf_scan, acmg, submit, vcf_qc, synth) |
| `tests/` | oracle parity, CSV contract, adversarial bytes, funnel unit, e2e gates (290+ tests and counting) |
| `tools/` | runners: audit_scorer_fixtures, check_citations, fetch_public_vcfs, fetch_refs, fetch_big, genes_to_disease_json, normalize_contigs, run_pipeline, run_track1, run_sensitivity, make_report, run_eda, extract_hpo, run_fastqc, run_phasing, run_vep, run_exomiser, compare_arms, run_realign, run_cnv, build_real_spike, revel_to_vcf, gnomad_split, modal_app |
| `scorer/` | vendored `evaluation.py` - the official scorer oracle (see `scorer/NOTICE.md`) |
| `config/` | frozen `pipeline.yaml` + `acmg_sf_v33.json` |
| `docs/` | plan.md (source of truth), status.md (phase-by-phase compliance map), report.md (regenerated), report_map.md, decisions/team/llm/runtime logs, disclosure position |
| `data/` `results/` | patient data + outputs - gitignored; `RETENTION.md` manifests tracked |
| `env/` | downloaded public corpora (gitignored, re-fetchable) |

## Reproduce (stand-in harness - zero patient data)

```sh
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -m pytest tests -q   # the suite
make refs        # download hp.obo + phenotype.hpoa + genes_to_phenotype
make spike control    # build synthetic proband + negative control
make track1      # EDA -> funnel -> SF -> phasing -> CSV -> oracle score
make report      # regenerate docs/report.md from results/
make audit       # 60-fixture scorer audit battery
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
