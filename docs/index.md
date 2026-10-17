---
title: Home
nav_order: 1
---

# MVA Hackathon 2026 - documentation

One child's genome -> a verified causal call -> a ranked, testable
approved-drug portfolio, plus the open engine that produced it.

| | Track 1 - variant prioritization | Track 2 - drug repurposing |
|---|---|---|
| Result | **100.0 / 1.000** on the official scorer, rank 1 | **recall@10 = 0.56** blind on 9 genes; 4-lead portfolio |
| Read it | [Track 1 report](report.md) | [Track 2 report](track2_report.md) |

## The short tour

1. **[Track 2 report](track2_report.md)** - the judged artifact, generated
   entirely from committed evidence JSON.
2. **[How the portfolio was chosen](track2/candidates.md)** - lead dossiers,
   the rejected table, the literature screen log.
3. **[The engine](track2/engine.md)** - gene-agnostic repurposing pipeline
   with a blind retrospective benchmark.
4. **[Mechanism](track2/mechanism.md)** - per-allele read on L737Ter and
   N1002K, and the pathway from there to mosaic aneuploidy.
5. **[Rubric self-assessment](track2/rubric_self_assessment.md)** and the
   two hostile reviews: [red team 1](track2/redteam.md),
   [red team 2](track2/redteam2.md).
6. **[For families](track2/FAMILY_SUMMARY.md)** - the plain-language
   summary, and [Understanding MVA](FAMILY_EXPLAINER.md).
7. **[The full map](README.md)** - every document, organized by audience.

## Verify it yourself

```sh
python -m pip install -r requirements.txt
python -m pytest tests -q                                  # 568 tests
python tools/verify_citations.py --offline --coverage-strict
python tools/audit_freshness.py
```

The full suite replays on a bare clone - patient data is never committed,
and every check above runs in CI on each push to `main`.
