# Submission artifacts

Upload-ready Track 1 CSVs. Every file below was written by
`src/submit.py`'s byte-contract writer and verified against the vendored
official scorer (`scorer/evaluation.py`) on the stand-in ground truth:
**100.0 rank points / F-max 1.000 / full match at rank 1** for each.

| File | Role | Pairs with | Contents |
|---|---|---|---|
| `model1_nikhilpise_answer-blind-funnel.csv` | **as-submitted** archive (uploaded 2026-10-04 07:30 UTC; leaderboard row `model1_nikhilpise_answer-blind-funnel.csv`) | `nikhilpise_track1_report.md` | BUB1B pair, epcr 0.0749 - the file that scored 100/1.000 server-side |
| `nikhilpise_answer-blind-funnel-v2.csv` | model2 candidate - same method, hardened notes | `nikhilpise_track1_report.md` | identical pair + epcr; notes add HGVS (`c.2210T>G p.Leu737Ter + c.3006T>G p.Asn1002Lys`) |
| `nikhilpise_exomiser-arm.csv` | model2 candidate - independent second method | `docs/report_model2.md` | pair in one row built from Exomiser 14.0.0 output by `tools/make_arm_a_csv.py`; epcr = Exomiser combined score 0.9819 |

Which (if any) model2 option to upload is the operator's call -
`docs/submission_checklist.md` has the tradeoffs. A resubmission cannot
damage the existing entry: equal scores keep the earlier timestamp, and
the worst case is a cosmetic display flip between equal-score rows.
