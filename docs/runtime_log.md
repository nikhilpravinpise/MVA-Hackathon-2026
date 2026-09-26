# Runtime / cost log

Feeds the methods-xlsx question asking for an estimate of run time and cost
(plan.md section 3). One row per job/session: what ran, where, wall-time,
peak RAM when known, and $ cost. Local machine per plan.md section 3: Ryzen
7-class 8C/16T, 24 GB RAM, RTX 5050 Laptop (8 GB), Docker Desktop + WSL2.

| Date | Job | Where | Wall-time | Peak RAM | Cost | Notes |
|---|---|---|---|---|---|---|
| 2026-09-26 | Local dev session: pytest suite, reference-corpus fetch (HPO ~67 MB total), tool scaffolding dry-runs | local | seconds-scale (pytest); <2 min downloads | <2 GB | $0 | No patient data touched; public corpora only |
