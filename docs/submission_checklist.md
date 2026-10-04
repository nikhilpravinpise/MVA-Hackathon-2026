# Phase-5 dry-run checklist - upload-form contract

Verified against `hackathon-app/tabs/submit_track1.py` and
`docs/plan.md` section 1.1. Run before EVERY upload; a failed line = do
not submit.

## Fields

| Field | Requirement | Source |
|---|---|---|
| GitHub repo URL | must start with `https://github.com/` | submit_track1.py:140-156 |
| Report file | `.pdf` or `.md` - we upload `docs/report.md` (`.md` is accepted; pandoc-built PDF optional, not required) | same |
| CSV | `results/.../submission.csv` built by `src/submit.py` | same |
| display_name | EXACT string in `docs/team.md` (grouping key - a typo forks the leaderboard entry) | utils.py:180-202 |
| model filename | becomes `model{N}_{filename}` server-side; the "Model" column on the leaderboard shows it - name it like a methods summary: `<team>_<method-descriptor>.csv` | submit_track1.py:167,192 |

## CSV byte contract (all enforced by tests)

- [ ] `pytest -m gate` green (includes oracle parity + adversarial battery)
- [ ] `python tools/audit_scorer_fixtures.py` -> "ALL 60 FIXTURES VERIFIED"
- [ ] local oracle on the exact upload bytes: `rank_points=100.0`,
      `f_max=1.000`, `full_match_rank=1` - run:
      `python -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'scorer'); from src.submit import validate_submission_bytes; import pathlib; ..."` (or use tests/test_e2e_gate.py which does this)
- [ ] UTF-8 **no BOM** (`head -c3` != `EF BB BF`); ASCII-clean bytes
- [ ] <= 10 rows, all `proband_id=PROBAND01`, `finding_type` in {primary,secondary}
- [ ] `chr`-prefixed contigs; epcr in (0,1], strictly decreasing; row 1 =
      the top-emitted hypothesis at its rank-mapped epcr (a pair's epcr
      reflects its RANK, not its CSV position - on the stand-in run the
      rank-1 pair shows 0.95; the indel-fix run's rank-7 pair emits 0.0749)
- [ ] no `,,,,,,,,,,,` comma-only lines; no Excel export path (programmatic only)

## Submission discipline

- [x] Submit ONCE for method 1. DONE 2026-10-04 07:30 UTC - leaderboard
      row 139 `nikhilpise (@T0X1N)`, 100.0 / 1.000, full match rank 1,
      `model1_nikhilpise_answer-blind-funnel.csv`. Remaining 5 quota held
      for method 2 (de-novo recall) or a real correction - never probes.
- [ ] Track 2 (later): only the latest of 3 is reviewed - one designated
      submitter, submit last before deadline.
- [x] After submit: record the leaderboard row + model filename in
      `docs/decisions.md` and `results/RETENTION.md` (KEEP tag).
      DONE - both updated, same commit.
