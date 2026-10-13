# Public-release audit

scrub commit: `20c8b3f`; 32 scrubbed tokens (10 history-only, 22 still present at HEAD, 0 scrubbed-then-readded)

## HISTORY-ONLY tokens (10 found)
Identifiers removed by the scrub commit that still live in earlier commits - the public-history question this audit exists to answer.

- `00...(5ch sha:9ff56fb4)` at 8236d1f:docs/report.md:3; 8236d1f:nikhilpise_track1_report.md:3
- `Ge...(6ch sha:9e8c5571)` at 265b686:docs/DEEP_DIVE.md:13; 265b686:docs/DEEP_DIVE.md:14
- `Ge...(7ch sha:de48268a)` at 265b686:docs/DEEP_DIVE.md:14
- `Na...(9ch sha:594017a4)` at 265b686:docs/DEEP_DIVE.md:16; 265b686:docs/DEEP_DIVE.md:17
- `Or...(6ch sha:34bbf6e4)` at 265b686:docs/DEEP_DIVE.md:15
- `Re...(10ch sha:726830ec)` at 265b686:docs/DEEP_DIVE.md:5; 265b686:docs/DEEP_DIVE.md:14
- `li...(6ch sha:0a49cae4)` at 265b686:docs/DEEP_DIVE.md:17
- `li...(21ch sha:f18c57c4)` at 265b686:docs/DEEP_DIVE.md:16
- `sy...(11ch sha:a06f7aac)` at 265b686:docs/DEEP_DIVE.md:5; 265b686:docs/DEEP_DIVE.md:14; 265b686:docs/DEEP_DIVE.md:344
- `tw...(9ch sha:8530fde7)` at 265b686:docs/DEEP_DIVE.md:16

## HEAD-PRESENT tokens (22)
Scrubbed strings that exist at HEAD - accepted identifiers (e.g. dataset accessions kept where reproduction requires them); review and confirm.

- `20...(4ch sha:445cd2fd)`
- `Di...(9ch sha:283cf9cd)`
- `GO...(4ch sha:7816fcba)`
- `Gr...(5ch sha:bd846adf)`
- `Ho...(8ch sha:dbb92786)`
- `MV...(4ch sha:be8c5f2b)`
- `Ra...(4ch sha:cce370d2)`
- `St...(6ch sha:b4541099)`
- `Tr...(7ch sha:db607d21)`
- `WG...(13ch sha:548c8f2f)`
- `ar...(7ch sha:565cecd7)`
- `ch...(5ch sha:0e93069c)`
- `fa...(7ch sha:d62fbe8f)`
- `fe...(7ch sha:4b7615dc)`
- `fi...(5ch sha:e0996a37)`
- `fo...(5ch sha:2739bb26)`
- `fo...(7ch sha:ef33f63d)`
- `mv...(14ch sha:12562e6d)`
- `re...(7ch sha:f1655af9)`
- `re...(9ch sha:38b85837)`
- `rh...(16ch sha:17fdeff5)`
- `th...(4ch sha:6f8f8e9f)`

## Scrubbed-then-reintroduced (0)
Tokens removed by the scrub that re-appeared in later commits' added lines - either prose coincidence or a re-leak; review.


## Generic sweeps (31 hits)
- email in HEAD: `MVAHackathon2026@synapse.org`
- email in HEAD: `RarediseaserealkidMVAhackathon2026@synapse.org`
- email in HEAD: `angelika@mit.edu`
- email in HEAD: `ben.lehner@crg.eu`
- email in HEAD: `d.macarthur@garvan.org`
- email in HEAD: `david_sinclair@hms.harvard`
- email in HEAD: `fran.supek@irbbarcelona.org`
- email in HEAD: `konradk@broadinstitute.org`
- email in HEAD: `marco.milan@irbbarcelona.org`
- email in HEAD: `nganem@bu.edu`
- email in HEAD: `sabine.elowe@crchuq.ulaval`
- email in HEAD: `shinya@hiroshima-u.ac`
- email in HEAD: `ste@mit.edu`
- email in HEAD: `ubendavid@tauex.tau`
- home_path in HEAD: `C:\Users\Nikhil`
- email in history: `MVAHackathon2026@synapse.org`
- email in history: `RarediseaserealkidMVAhackathon2026@synapse.org`
- email in history: `angelika@mit.edu`
- email in history: `ben.lehner@crg.eu`
- email in history: `d.macarthur@garvan.org`
- email in history: `david_sinclair@hms.harvard`
- email in history: `fran.supek@irbbarcelona.org`
- email in history: `konradk@broadinstitute.org`
- email in history: `marco.milan@irbbarcelona.org`
- email in history: `nganem@bu.edu`
- email in history: `sabine.elowe@crchuq.ulaval`
- email in history: `shinya@hiroshima-u.ac`
- email in history: `ste@mit.edu`
- email in history: `ubendavid@tauex.tau`
- home_path in history: `C:\Users\Nikhil`
- synapse_id in history: `syn...(11ch)`

## Blobs > 1 MB in history (0)

## Remediation options for HISTORY-ONLY findings

1. **Accept** - the dataset is gated-public and the identifier class is already disclosed by the dataset itself; document the decision in docs/decisions.md.
2. **Rewrite** - `git filter-repo --replace-text` on the token list, force-push (invalidates every commit hash cited across docs/decisions/llm_log - those citations must be re-mapped or footnoted).
3. **Fresh repo** - new repo, single clean squash commit (loses all audit-trail history - weakest option for a repo whose value IS the trail).
