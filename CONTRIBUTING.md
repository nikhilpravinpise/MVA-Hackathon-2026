# Contributing

This repository is a competition artifact for the MVA Hackathon 2026
(Track 1 + Track 2). It is primarily maintained by one author, but issues
and pull requests are welcome - especially corrections, reproducibility
reports, and literature pointers for the repurposing portfolio.

## Ground rules

- **No patient data, ever.** `data/`, `results/` and `env/` are gitignored
  by design; the tracked `RETENTION.md` manifests describe what exists.
  Never commit variants, FASTQs, BAMs or VCFs. The whole suite runs on
  synthetic + public stand-ins.
- **No hand-typed numbers in reports.** Both reports are generated from
  committed artifacts (`tools/make_report.py`, `tools/make_track2_report.py`).
  If a figure needs to change, change the evidence and regenerate.
- **Claims carry sources.** `tools/verify_citations.py` resolves every
  PMID/DOI live and enforces that claim sentences are sourced
  (`--coverage-strict`). First-party identifiers (ChEMBL ids, openFDA
  `set_id`s, ClinVar accessions) count as sources.
- **No em dashes** in tracked docs (plain `-`); the suite pins this.
- Run before sending a PR:

  ```sh
  python -m pytest tests -q
  python tools/audit_freshness.py
  python tools/verify_citations.py --offline --coverage-strict
  ```

## Setup

```sh
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt   # Windows
# .venv/bin/python -m pip install -r requirements.txt         # Linux/macOS
.venv/Scripts/python.exe -m pytest tests -q
```

Optional extras (not needed for the suite): `markdown-it-py` +
`playwright` + Chrome for `make track2-pdf`; `edge-tts` + `ffmpeg` for
`make track2-video`; a Modal account for the GPU ESM-2 lane
(`tools/modal_track2.py`).

## Commit conventions

History reads like a logbook - short imperative subject, lanes/tests
named, e.g. `track2 L11: pediatric-flag root fix (...)`. No attribution
trailers.
