# Public-release audit

scrub commit: `20c8b3f`; 32 scrubbed tokens (19 history-only, 13 still present at HEAD, 0 scrubbed-then-readded)

## HISTORY-ONLY tokens (19 found)
Identifiers removed by the scrub commit that still live in earlier commits - the public-history question this audit exists to answer.

- `00...(5ch sha:9ff56fb4)` at 8236d1f:docs/report.md:3; 8236d1f:nikhilpise_track1_report.md:3
- `Di...(9ch sha:283cf9cd)` at 265b686:docs/DEEP_DIVE.md:15
- `Ge...(6ch sha:9e8c5571)` at 265b686:docs/DEEP_DIVE.md:13; 265b686:docs/DEEP_DIVE.md:14
- `Ge...(7ch sha:de48268a)` at 265b686:docs/DEEP_DIVE.md:14
- `Gr...(5ch sha:bd846adf)` at 265b686:docs/DEEP_DIVE.md:15
- `Ho...(8ch sha:dbb92786)` at 265b686:docs/DEEP_DIVE.md:15
- `MV...(4ch sha:be8c5f2b)` at 265b686:docs/DEEP_DIVE.md:16
- `Na...(9ch sha:594017a4)` at 265b686:docs/DEEP_DIVE.md:16; 265b686:docs/DEEP_DIVE.md:17
- `Or...(6ch sha:34bbf6e4)` at 265b686:docs/DEEP_DIVE.md:15
- `Re...(10ch sha:726830ec)` at 265b686:docs/DEEP_DIVE.md:5; 265b686:docs/DEEP_DIVE.md:14
- `St...(6ch sha:b4541099)` at 265b686:docs/DEEP_DIVE.md:15
- `Tr...(7ch sha:db607d21)` at 265b686:docs/DEEP_DIVE.md:16
- `ar...(7ch sha:565cecd7)` at 265b686:docs/DEEP_DIVE.md:14
- `fa...(7ch sha:d62fbe8f)` at 265b686:docs/DEEP_DIVE.md:5
- `li...(6ch sha:0a49cae4)` at 265b686:docs/DEEP_DIVE.md:17
- `li...(21ch sha:f18c57c4)` at 265b686:docs/DEEP_DIVE.md:16
- `re...(9ch sha:38b85837)` at 265b686:docs/DEEP_DIVE.md:16
- `sy...(11ch sha:a06f7aac)` at 265b686:docs/DEEP_DIVE.md:5; 265b686:docs/DEEP_DIVE.md:14; 265b686:docs/DEEP_DIVE.md:344
- `tw...(9ch sha:8530fde7)` at 265b686:docs/DEEP_DIVE.md:16

## HEAD-PRESENT tokens (13)
Scrubbed strings that exist at HEAD - accepted identifiers (e.g. dataset accessions kept where reproduction requires them); review and confirm.

- `20...(4ch sha:445cd2fd)`
- `GO...(4ch sha:7816fcba)`
- `Ra...(4ch sha:cce370d2)`
- `WG...(13ch sha:548c8f2f)`
- `ch...(5ch sha:0e93069c)`
- `fe...(7ch sha:4b7615dc)`
- `fi...(5ch sha:e0996a37)`
- `fo...(5ch sha:2739bb26)`
- `fo...(7ch sha:ef33f63d)`
- `mv...(14ch sha:12562e6d)`
- `re...(7ch sha:f1655af9)`
- `rh...(16ch sha:17fdeff5)`
- `th...(4ch sha:6f8f8e9f)`

## Scrubbed-then-reintroduced (0)
Tokens removed by the scrub that re-appeared in later commits' added lines - either prose coincidence or a re-leak; review.


## Generic sweeps (5 hits)
- email in HEAD: `MVAHackathon2026@synapse.org`
- email in HEAD: `RarediseaserealkidMVAhackathon2026@synapse.org`
- email in history: `MVAHackathon2026@synapse.org`
- email in history: `RarediseaserealkidMVAhackathon2026@synapse.org`
- synapse_id in history: `syn...(11ch)`

## Blobs > 1 MB in history (0)

## Remediation options for HISTORY-ONLY findings

1. **Accept** - the dataset is gated-public and the identifier class is already disclosed by the dataset itself; document the decision in docs/decisions.md.
2. **Rewrite** - `git filter-repo --replace-text` on the token list, force-push (invalidates every commit hash cited across docs/decisions/llm_log - those citations must be re-mapped or footnoted).
3. **Fresh repo** - new repo, single clean squash commit (loses all audit-trail history - weakest option for a repo whose value IS the trail).
