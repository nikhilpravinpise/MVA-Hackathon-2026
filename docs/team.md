# Team / display_name decision record

**Status:** OPEN - must be decided before the first submission.

```
DISPLAY_NAME: <TBD - set before first submission>
```

## The contract (verified against the app source)

The leaderboard groups submissions by the `display_name` string attached to
the Hugging Face account that submits - it keeps the best `(rank_points,
f_max)` per display_name and sorts ties by earliest `submitted_at`
(`hackathon-app/utils.py:180-202`, cited in plan.md section 1.1).

Consequences of getting this wrong:

- **Exact-string grouping.** `display_name` is matched verbatim. Two different
  strings = two separate leaderboard entries; the team loses its pooled
  best-score identity.
- **Mixed/absent names split the team.** Plan.md Phase 0 documents the prior
  incident (deep dive section 3, Fernandosr85): inconsistent team naming
  produced duplicate leaderboard entries for one team.
- **Quota pooling depends on it.** Each HF user has 6 Track-1 submissions;
  teammates' quota only group under a SINGLE identical team name.
- **Track 2.** One designated submitter per team (FAQ, plan.md 1.1); the same
  display_name convention applies there.

## Rules for use

1. The chosen string is written above in the `DISPLAY_NAME:` line and
   committed BEFORE the first submission (Gate 0 / Gate 5 checklist).
2. Every team member sets their HF `display_name` to that exact string -
   byte-identical: same case, same spacing, no trailing whitespace.
3. Submission CSV filenames follow `<team>_<method-descriptor>.csv`
   (plan.md Phase 5); the server-visible `model{N}_<filename>` leaderboard
   column derives from it - keep it descriptive but stable.
4. If a rename is ever needed, record it here with date + reason AND in
   docs/decisions.md; rename only between submissions, never with quota in
   flight.

## Decision log for this record

| Date | Event | Notes |
|---|---|---|
| 2026-09-26 | File created, display_name open | Phase-0 scaffolding; decision required before Gate 5 |
