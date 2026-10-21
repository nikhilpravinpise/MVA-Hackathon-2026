---
title: Repo launch checklist
nav_order: 17
---
# Repo launch checklist - going public (executed 2026-10-21)

> **Done 2026-10-21:** the repo is public, Pages is live at
> <https://nikhilpravinpise.github.io/MVA-Hackathon-2026/>, and the
> homepage points there. The flip happened earlier than the planned Oct 24
> close at the operator's direction, so the Track 1 answer and the
> pre-redaction commit history were public before the leaderboard closed.
> Step 3 (social preview) and step 5 (Zenodo DOI) remain.

The repo was furnished private; these are the operator steps used for the
public flip. The original plan was to flip on the close date, not earlier:
the FAQ allows a private repo while the hackathon runs, organizers asked
another team (thread #20) to stay private pending IRB guidance on
incidental findings, and `docs/track1_closeout.md` (A8) fixed the flip at
close. The repo contains the Track 1 answer (the BUB1B variants and the
submitted CSV), so the planned flip was after the leaderboard closed. The
operator chose to flip on 2026-10-21 instead; that override and its risk
are recorded in `docs/decisions.md`. Everything here is a one-shot command
or click; nothing below touches code. Re-run the citation gate + suite
first if more than a day has passed since the last green run.

```sh
python -m pytest tests -q
python tools/audit_freshness.py
python tools/verify_citations.py --offline --coverage-strict
python tools/public_release_check.py   # re-scan history before flipping
```

## 1. Flip visibility (done 2026-10-21)

A7 is resolved (both non-causal loci were redacted on 2026-10-17). Re-check
thread #20 and the rest of the Space (`python tools/check_discussions.py
--since 2026-10-12`) immediately before the flip.

```sh
gh repo edit nikhilpravinpise/MVA-Hackathon-2026 \
  --visibility public --accept-visibility-change-consequences
```

The public-release audit already documents the accepted history-only
identifiers (`docs/public_release_audit.md`); this command publishes what
that audit reviewed.

## 2. Activate the docs site (Pages) - done 2026-10-21

```sh
gh api repos/nikhilpravinpise/MVA-Hackathon-2026/pages \
  -X POST -F "source[branch]=main" -F "source[path]=/docs"
gh api repos/nikhilpravinpise/MVA-Hackathon-2026/pages/builds/latest \
  --jq .status    # wait for "built"
```

Then swap the homepage from the Space to the site:

```sh
gh repo edit nikhilpravinpise/MVA-Hackathon-2026 \
  --homepage "https://nikhilpravinpise.github.io/MVA-Hackathon-2026/"
```

Spot-check: the landing page, `track2/engine.html`, `track2/STATUS.html`,
and a figure in `report.html` all render.

## 3. Social preview (web UI only - no API)

Repo > Settings > General > Social preview > upload
`docs/assets/social.png` (1280x640, generated from the video title slide).

## 4. Video upload (done 2026-10-21)

`pitch.mp4` is on YouTube as **unlisted**:

<https://youtu.be/YD2dIVnmMME>

It was checked in a logged-out Incognito window. The URL is in
`docs/track2/submission_fields.md` and the `README.md` Start-here section.
If the video is ever replaced, re-check it logged out and update both.

## 5. Zenodo DOI (optional but planned)

Zenodo only hooks public repos, so do this after the flip:

1. zenodo.org > Account > GitHub - OAuth link, then toggle this repo on.
2. Cut the versioned release (the webhook mints the DOI on release):

   ```sh
   git tag -a v1.0.0 -m "Hackathon submission state"
   git push origin v1.0.0
   gh release create v1.0.0 --title "v1.0.0 - hackathon submission"
   ```

3. Add the DOI badge to `README.md` and a `doi:` field in `CITATION.cff`.

## 6. Submission (done before the flip)

**Submission 1 accepted 2026-10-21** (`nikhilpise` / `@T0X1N`). Only the
latest entry is reviewed, so this is the judged submission unless a later
one replaces it. Follow `docs/track2/submission_fields.md`; all five form
values are paste-ready there.

## Oct 23 - optional final check (before this flip)

Do **not** re-submit an identical package. Use the spare slot only if a
real change lands before close, and run the pre-flight block in
`submission_fields.md` first:

```sh
python tools/check_discussions.py --since 2026-10-21   # rule drift check
```

## Later (post-deadline)

- Modal: wipe volume `mva-t2-cache` per `docs/deletion_runbook.md`
  (kept for now - holds the ESM inputs/outputs).
- Worktrees `.claude/worktrees/track2` and `track1-final-audit` can be
  removed once the video is safely on YouTube + the release
  (`git worktree remove`).
