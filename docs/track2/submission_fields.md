---
title: Submission fields
nav_order: 12
parent: Track 2
---
# Track 2 submit form - exact values to paste

Verified against the live form (`hackathon-app/tabs/submit_track2.py`,
re-diffed 2026-10-12 in `docs/track2/rules_refresh.md`). Five inputs; two
are optional. Open the Space in **Chrome** (Safari had OAuth/websocket
trouble, deep dive section 3) and sign in with the HF account that owns
the Track 1 entry (`@T0X1N`).

| Field | Paste exactly | Why |
|---|---|---|
| Team / Display Name *(optional)* | `nikhilpise` | Same grouping string as Track 1 (`docs/team.md`); the public announcement uses it |
| GitHub repo URL **(required)** | `https://github.com/nikhilpravinpise/MVA-Hackathon-2026` | Must start with `https://github.com/` or the form rejects it (`submit_track2.py:85-88`) |
| Pitch video URL **(required)** | the YouTube or Vimeo link for `video/out/pitch.mp4` | Empty is rejected (`submit_track2.py:90-92`). Unlisted is fine; check it plays **logged out** |
| Report file **(required)** | `nikhilpise_track2_report.md` | Only `.pdf` and `.md` are accepted (`submit_track2.py:97-99`); the filename carries the username as the instructions ask |
| Notes for judges *(optional)* | the block below | Free text, 3 lines in the box |

## Notes-for-judges text

```
Everything in the report is generated from the evidence files in
docs/track2/evidence/ - no number is hand-typed, and every citation is
resolved live against PubMed/Crossref/DataCite and retraction-checked
(tools/verify_citations.py, 136/136 green). The repurposing engine is
gene-agnostic and we report its blind retrospective benchmark on nine
unrelated genes (recall@10 = 0.56) including the structural misses, plus
the 37 approved drugs a cited mechanism-direction layer excludes as
harmful in a checkpoint-deficient child - listed with the rank they would
have had, not quietly dropped. Phase (in trans) was never observed in
Track 1 and the report says so wherever it matters. One command rebuilds
report, figures and video: see README.
```

## Pre-flight (run before each of the two uploads)

```sh
python tools/verify_citations.py --refresh      # 0 unresolved, 0 retracted
python -m pytest tests -q                       # whole suite green
python tools/make_track2_report.py --upload     # rebuilds the upload copy
python tools/check_discussions.py --since 2026-10-12   # rule drift
.venv-video/Scripts/python.exe video/build.py   # <= 180 s, prints duration
python tools/public_release_check.py            # no identifiers / secrets
```

- [ ] Report opens in a Markdown viewer with tables intact
- [ ] Video link plays in a logged-out browser window
- [ ] Repo is reachable at the URL above (private is allowed **during**
      the hackathon; it must be public at close or the panel cannot judge)
- [ ] The acknowledgement block is present verbatim at the end of the
      report (rules "Citation and Acknowledgement")

## Submission discipline

Three submissions are allowed and **only the latest is reviewed**
(`config.py: MAX_TRACK2_SUBMISSIONS = 3`, FAQ). One designated submitter
per team.

| When | What | Why |
|---|---|---|
| **Oct 20** | Full insurance submission | A Space outage on deadline day costs more than a quota slot |
| **Oct 23** | Final submission - this is the judged one | Leaves a spare slot and a clear day before close |
| Oct 24 23:59 UTC | Deadline | Do not plan to use it |

After each upload, record the confirmation (submission number and
timestamp) in `docs/decisions.md`.
