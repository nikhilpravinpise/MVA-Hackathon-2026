# Track 2 - where we are

Paused 2026-10-12 23:21 IST on branch `worktree-track2`
(worktree `.claude/worktrees/track2`). Submissions close **2026-10-24
23:59 UTC**; judging now runs to Dec 17 and winners are announced Dec 18
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
| Tests | 550 passing, 10 skipped; green in a fresh clone |

## Next, in order

1. **Red team.** `bash tools/t2_launch_devin.sh L9` - the hostile review
   (`docs/track2/agent_prompts/L9_redteam.md`) was launched and stopped
   when work paused; it had written nothing yet. It produces
   `docs/track2/redteam.md` + `rubric_self_assessment.md` (GATE 7 asks for
   >= 85% per criterion). Work its findings before anything else.
2. **Upload copy + PDF.** `python tools/make_track2_report.py --upload`
   writes `nikhilpise_track2_report.md` (the form takes `.md` or `.pdf`;
   a PDF render is optional polish).
3. **Submission fields.** Write `docs/track2/submission_fields.md` (team
   name, GitHub URL, video URL, judge notes) so the operator pastes
   rather than composes.
4. **Operator actions.** Upload `video/out/pitch.mp4` to YouTube or Vimeo
   and check the link logged out; then submit on the Space.
5. **Re-run the rules refresh** on Oct 19 and Oct 23 (commands inside
   `rules_refresh.md`) in case anything changes before the deadline.
6. **Submit twice:** a complete insurance entry on **Oct 20**, the final
   on **Oct 23**. Only the latest of 3 is reviewed, so the last upload is
   the one judged.

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
