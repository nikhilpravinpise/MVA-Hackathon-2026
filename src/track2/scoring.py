"""Transparent scoring: weighted sum of normalized evidence channels.

Every channel is normalized to [0, 1]; the score is a plain weighted sum
(weights live in config).  A channel whose source failed or had no data
contributes 0 with its weight kept in the denominator - the engine never
inflates a drug just because a source was unreachable.

Channels:
    target_overlap       |T ∩ M| / |T|   (T = drug's known gene targets)
    network_proximity    z mapped piecewise: z <= z_full -> 1; >= z_zero -> 0
    signature_reversal   best reverser -log10(p)/cap for a matched pert name
    interaction_evidence min(1, #module genes with a DGIdb interaction / 2)
    literature           min(1, DGIdb publication count / 3)
"""
from __future__ import annotations

CHANNELS = ("target_overlap", "network_proximity", "signature_reversal",
            "interaction_evidence", "literature")


def channel_target_overlap(targets: list[str], module: set[str]) -> float:
    if not targets:
        return 0.0
    hit = sum(1 for t in targets if t in module)
    return hit / len(targets)


def channel_proximity(z: float | None, z_full: float, z_zero: float) -> float:
    if z is None:
        return 0.0
    if z <= z_full:
        return 1.0
    if z >= z_zero:
        return 0.0
    return (z_zero - z) / (z_zero - z_full)


def channel_reversal(best_logp: float | None, cap: float) -> float:
    if best_logp is None:
        return 0.0
    return min(1.0, max(0.0, best_logp) / cap)


def channel_interactions(n_module_hits: int) -> float:
    return min(1.0, n_module_hits / 2.0)


def channel_literature(n_pmid: int) -> float:
    return min(1.0, n_pmid / 3.0)


def score_candidate(channels: dict, weights: dict) -> float:
    """Weighted sum; weights are used as given (missing channel = 0)."""
    s = sum(w * max(0.0, min(1.0, channels.get(k, 0.0)))
            for k, w in weights.items())
    return round(s, 4)


def tier(score: float, channels: dict, cfg_tiers: dict,
         t1_min_channels: int) -> str:
    nonzero = sum(1 for k in CHANNELS if channels.get(k, 0.0) > 0)
    if score >= cfg_tiers["T1"] and nonzero >= t1_min_channels:
        return "T1"
    if score >= cfg_tiers["T2"]:
        return "T2"
    return "T3"
