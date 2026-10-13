# Security Policy

## Scope

This is a research/competition repository: data pipelines, report generators
and a vendored copy of the official hackathon scorer. It does not run as a
service and holds no credentials.

## What must never be committed

- Patient data: `data/`, `results/` and `env/` are gitignored by design;
  only `RETENTION.md` manifests are tracked. `tools/public_release_check.py`
  scans HEAD + full history for leaked identifiers and secrets-class tokens
  before the repo is made public.
- API tokens, HF tokens, `.env` files, `*.pem`, `*.key` (all gitignored).

## Supported versions

Only `main` is maintained; tagged releases (`track1-submitted`,
`track2-submission`) are frozen records of what was submitted.

## Reporting a vulnerability

Open a GitHub issue describing the problem. If the report involves a leaked
identifier or secret, do not paste the token itself - describe where it
lives and its shape, and it will be rotated and history-scrubbed if needed.
