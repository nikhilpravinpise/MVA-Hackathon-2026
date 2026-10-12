LANE L3b - Reconcile the engine ranking with the curated dossiers into one frozen portfolio decision. Report file: docs/track2/agent_reports/L3b.md.
Owned paths: docs/track2/evidence/portfolio.json, docs/track2/evidence/dossiers/*.json, docs/track2/candidates.md, docs/track2/abstract.md, docs/track2/agent_reports/L3b.md.
Do NOT touch src/track2/, config/track2.yaml, candidates.json or benchmark.json - lane L2b is editing those concurrently.

Read first: docs/track2_plan.md section 4 (schemas), docs/track2/agent_reports/L2.md and L3.md and L5.md, docs/track2/evidence/mechanism.json, your own dossiers, docs/track2/evidence/prism.json and esm.json, and the rendered draft docs/track2_report.md (sections 4 and 5 are what you are filling).

The report generator (tools/make_track2_report.py, do not edit) reads docs/track2/evidence/portfolio.json with this schema:

{"schema": "t2.portfolio/1", "decided": "<date>", "decided_by": "<one line: which artifacts were reconciled>",
 "ranking_rule": "<2-4 sentences: the explicit, auditable rule by which rank is assigned, and why engine placement does not decide it>",
 "screen": null,
 "ranked": [{"rank": 1, "label": "<drug or pair> - <mechanism in 6 words>", "dossier": "<basename of the dossier json, no extension>",
             "grade": "<evidence grade, copy from your own evidence-grade table>",
             "engine_drugs": ["<drug names exactly as the engine would list them>"],
             "why": "<4-8 sentences, every factual claim carrying a PMID: or DOI: that is already resolved in that dossier's citations map; this is hypothesis-generation prose for a research audience, not clinical advice>",
             "falsifier": "<2-4 sentences: what observation would refute this candidate, and the decisive experiment with its go/no-go threshold from testability.json>"}, ...],
 "adjuncts": [{"label": "...", "why": "<1-3 sentences with cites>"}, ...]}

Rules for the decision:
1. Rank by distance from the evidence to a BubR1-insufficient human system, pediatric feasibility (labeled pediatric use and the risks you already recorded against this child's phenotype), and how cheaply the lead can be falsified - state that rule in `ranking_rule`. Engine placement is REPORTED by the generator (it looks each `engine_drugs` entry up in candidates.json itself), so do not hand-type ranks.
2. Keep the leads and adjuncts consistent with your candidates.md section 2; if integrating the engine, PRISM and ESM evidence changes your order, change it and say so in L3b.md with the reason.
3. Use the new computational evidence where it is relevant and state its direction honestly: ESM-2 650M scores N1002K at the 88th percentile of deleteriousness among gnomAD BUB1B missense (docs/track2/evidence/esm.json; the 150M run in esm_150m.json puts it mid-distribution - report the disagreement), and PRISM found NO FDR-significant aneuploidy-selective launched drug and does not contain metformin, chloroquine or hydroxychloroquine at all, so no PRISM claim may be made for those three.
4. Every `why` and `falsifier` sentence that asserts a fact needs a cite that is already in the matching dossier's `citations` map (the citation gate checks title/year against the registries). If you need a new paper, resolve it live (esummary + abstract) and add it to that dossier's citations map.
5. Framing in every string: hypothesis for laboratory testing, not medical advice, and no dosing recommendations - label facts only, which already live in the dossiers' `pediatric` blocks.
6. Also write docs/track2/abstract.md: a standalone <= 500-word method abstract (the methods form asks for it; the report links to it) covering approach, the engine + benchmark numbers, the portfolio, strengths and limitations. Count the words and state the count at the end of the file.
7. Set "screen": null (the generator recomputes the literature-screen flow from candidates.md itself).

Verify before finishing: `C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe tools/make_track2_report.py` renders with no PENDING left in sections 5.2-5.4, then `C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe tools/verify_citations.py` passes, then `C:/Dev/MVA-Hackathon-2026/.venv/Scripts/python.exe -m pytest tests/test_t2_evidence.py tests/test_make_track2_report.py -q` passes. Report the rendered word count and the final ranked order in L3b.md.
