LANE L16 - Close the 28 uncovered claims, regenerate the evidence on L15's engine, re-render everything green. Report file: docs/track2/agent_reports/L16.md.
Owned paths: everything the previous lanes owned EXCEPT the review records. Specifically yours: docs/track2/evidence/ (all), docs/track2/compute.md, docs/track2/mechanism.md, docs/track2/candidates.md, docs/track2/engine.md, docs/track2_report_template.md, docs/track2_report.md, nikhilpise_track2_report.md, docs/track2/abstract.md, docs/track2/FAMILY_SUMMARY.md, tools/make_track2_report.py, tools/t2_mechanism.py, tools/t2_prism.py, tools/t2_esm.py, tests/ (all), video/, docs/track2/agent_reports/L16.md.
Do NOT touch: docs/track2/redteam.md, docs/track2/redteam2.md, docs/track2/rubric_self_assessment.md, docs/track2/agent_reports/L9-L15.md (the review record), tools/verify_citations.py or src/track2/ (L15's hardened checks - treat them as the specification, do not relax either to make a check pass).

No other lane is running. You own the whole package. Read first: docs/track2/agent_reports/L15.md (sections "Strict-gate result" and "Expected candidates.json delta") and L14.md ("Open issues").

1. **Regenerate the engine evidence on L15's engine.** Exactly as lane L12 did it, and with the same discipline: run `--mode replay` to a temp path FIRST to prove every request is already cached (fixtures are committed; L15 recorded the new `_exists_` queries), and confirm `git status` shows no new untracked fixture files after the record run. Then:
   `python tools/run_track2.py --mode record --cache-dir tests/fixtures/track2/engine/mva` and the `--benchmark` equivalent.
   Verify the result against L15's pinned delta in `tests/test_track2_engine.py` (35 records: 3 to labeled, 2 to pediatric_text_only, 13 to unknown, 8 label re-picks, 11 clip-only, etoposide phosphate's boxed warning). Every change must be inside those tables and nothing else may move; the comparison tests should flip to strict equality once the regenerated file carries an L15 marker. Report anything the tables did not predict.
2. **Close all 28 uncovered claims** (L15 enumerated them: 2 in the report, 11 in compute.md, 9 in mechanism.md, 6 in candidates.md). Each is a real claim. Give each one its source: a resolved PMID/DOI for a literature statement, or a `[repo:...]` pointer where the number comes from one of our artifacts. Two need generator-side fixes rather than prose edits:
   - the per-allele "736-aa product, 29.9% lost" row: make `allele_table()`'s `loss()` output carry the transcript or an artifact ref;
   - the dasatinib label-section risk bullet: `_has_source()` currently accepts the bare words "label section" as a source. That is too loose - require a concrete identifier (a set_id, a registry id, a PMID/DOI, a [repo:] path) and let the generator append the real `[repo:openFDA label <set_id>]` marker. Check this change does not silently un-source other bullets; fix any it exposes.
   Do not add a reference that does not actually support the sentence. If a claim cannot be sourced, rewrite the claim.
3. **New pediatric tier in the reader-facing surfaces.** The flag now has four states and `unknown` is new. Make sure the report's engine table, the shortlist and any prose that mentions pediatric labelling read correctly with `unknown` present (the generator's `_ped()` map needs an entry), and that `docs/track2/engine.md`'s semantics section matches what ships.
4. **Re-render and verify, in order, all green:**
   - `python tools/make_track2_report.py --upload`
   - `python tools/verify_citations.py --coverage-strict` -> PASS, 0 uncovered
   - `python -m pytest tests -q` -> 0 failed
   - `python tools/make_track2_pdf.py` (system python)
   - `.venv-video/Scripts/python.exe video/build.py` -> <= 180 s (only if a number spoken in the video changed; say whether it did)
5. **Final consistency sweep.** The package has been edited by eight lanes. Re-read the report end to end against the evidence files for any remaining internal contradiction, stale count or claim that regeneration has invalidated - the pediatric flag counts, the "96 approved / 89 distinct actives" figures, the test count line, the uncovered-claims line, and the engine-table cells most likely to have moved. Fix what you find.

Report: the regeneration delta vs the pinned tables, every uncovered claim closed and how, the final four verification outputs verbatim, and anything you changed in the report prose as a result of the regeneration.
