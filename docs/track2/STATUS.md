---
title: Status / resume ledger
nav_order: 1
parent: Track 2
---
# Track 2 - where we are

Build complete and merged to `main` (PR #4, lanes L1-L16); refreshed
2026-10-21. Submissions close **2026-10-24 23:59 UTC**; judging now runs to Dec 17 and winners are announced Dec 18
(discussion #26, `docs/track2/rules_refresh.md`).

## Done

| Piece | State |
|---|---|
| Plan, constraints, calendar | `docs/track2_plan.md` |
| Variant mechanism (per allele, pathway, uncertainties) | `docs/track2/evidence/mechanism.json` + `mechanism.md`, `tools/t2_mechanism.py` |
| Repurposing engine + blind benchmark | `src/track2/`, `config/track2.yaml`, `docs/track2/evidence/candidates.json`, `benchmark.json`, `docs/track2/engine.md` |
| Mechanism-direction layer (37 opposed drugs excluded, listed) | `src/track2/direction.py` |
| Drug dossiers, rejected table, testability matrix | `docs/track2/evidence/dossiers/`, `rejected.json`, `testability.json` |
| Frozen portfolio decision + 458-word abstract | `docs/track2/evidence/portfolio.json`, `docs/track2/abstract.md` |
| PRISM x aneuploidy, ESM-2 variant effect, Modal app | `docs/track2/evidence/prism.json`, `esm.json`, `esm_150m.json`, `tools/modal_track2.py`, `docs/track2/compute.md` |
| Citation gate (137/137 resolve, retraction-checked, 0 uncovered claims) | `tools/verify_citations.py`, `docs/track2/citation_cache.json` |
| Rules refresh, competitor landscape, methods-form map | `docs/track2/rules_refresh.md`, `landscape.md`, `form_map.md` |
| Report generated from evidence only (~10,780 words) | `tools/make_track2_report.py`, `docs/track2_report_template.md`, `docs/track2_report.md` |
| 3-minute pitch video (179.4 s rendered) | `video/` (`out/` is gitignored - rebuild with `video/build.py`) |
| Tests | 575 collected (572 pass, 3 skip: patient VCF, PDF, video); green in a fresh clone |
| Red team | L9 and L13 reviews closed through L14/L15/L16 (R1 approval-gate wording fixed in report, abstract and video script); `redteam.md`, `redteam2.md`, `rubric_self_assessment.md` |
| Release | `track2-submission` GitHub release holds the upload `.md`, the PDF, `pitch.mp4` and `pitch.srt` (byte-identical to the repo upload copy) |
| Pitch video | <https://youtu.be/YD2dIVnmMME> - unlisted, uploaded 2026-10-21; verified playing in an Incognito window |
| Rules re-check (2026-10-21) | 5 organizer threads since Oct 12; no Track 2 rule change and the submission form is unchanged. The deletion-confirmation address is now `cnb@sagebase.org` |

## Next, in order (operator steps only)

1. **Insurance submission (now, if the Oct 20 slot was not used).** The repo
   stays private - the FAQ allows this while the hackathon runs. Paste the
   five values from `submission_fields.md` and log the confirmation in
   `docs/decisions.md`.
2. **Oct 23:** run the pre-flight block in `submission_fields.md`, then the
   final submission. Only the latest of 3 is reviewed.
3. **Oct 24 (before 23:59 UTC):** flip the repo public, then Pages, Zenodo
   release, social preview - `docs/repo_launch.md`.
4. **By Nov 23:** send the deletion email (now to `cnb@sagebase.org` plus the
   attested mailbox) and wipe the data - `docs/deletion_runbook.md`.

## Open items worth knowing

- **Coverage gate is closed.** `tools/verify_citations.py
  --coverage-strict` reports 0 uncovered claim sentences across the
  Track 2 tree (as of L16, 2026-10-13); every claim carries a resolved
  PMID/DOI or a `[repo:]` pointer to its artifact.
- **Engine noise is documented, not fixed.** Some high-ranked entries are
  database artefacts (glycerin, methenamine); the curated portfolio, not
  the engine table, proposes the candidates.
- **Modal:** profile `track2` -> workspace `nikhilpise69`, public data
  only, one L4 GPU run spent so far. Volume `mva-t2-cache` holds the ESM
  inputs and outputs; wipe it in the deletion runbook for hygiene.
- **`.venv-t2` and `.venv-video`** are local, gitignored build venvs.
