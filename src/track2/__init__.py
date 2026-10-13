"""Track 2 - deterministic mechanism-to-approved-drug repurposing engine.

Pipeline: seed genes -> STRING disease module -> drug candidates (Open
Targets + DGIdb) -> approved-only filter (ChEMBL gate, openFDA/DrugCentral
cross-check) -> STRING network proximity -> LINCS signature reversal ->
transparent weighted score + tiers -> docs/track2/evidence/candidates.json.

Every external call goes through a single caching HTTP layer so a live run
is recorded verbatim and replayed offline for tests (no network, byte-level
determinism).
"""
