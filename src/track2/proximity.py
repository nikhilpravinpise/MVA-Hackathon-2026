"""Network proximity on the STRING graph (Guney et al. 2016, PMID 26831545).

Given the disease module M and a drug's target set T:

    d_c(T, M) = (1/|T|) * sum_{t in T} min_{s in M} dist(t, s)

dist() is the unweighted shortest path on the routing universe U (edges with
STRING combined score >= threshold).  A target outside U, or unreachable,
scores ``unreachable_distance`` - a conservative bound, never 0.

Significance is a z-score against ``n_random`` degree-matched random target
sets drawn with a FIXED seed: for each real target t, a random node is drawn
from the same degree bin (log2 degree classes).  z < 0 means the drug sits
closer to the module than chance; more negative = closer.

Implementation: a single multi-source BFS from all module members precomputes
distance-to-module for every node once per case; drug evaluation and all
random resamples are then O(1) lookups.

Determinism: random.Random(seed); edge set sorted; no wall-clock anywhere.
"""
from __future__ import annotations

import random
from collections import deque


def build_universe(module: set[str], partner_map: dict[str, list[str]],
                   cap: int = 450) -> set[str]:
    """Routing universe = module genes + their STRING neighbours.

    ``partner_map`` maps a module gene to its partner symbols (already
    score-filtered upstream).  Nodes are added in sorted order up to ``cap``
    for deterministic truncation.
    """
    u = set(module)
    for g in sorted(partner_map):
        for n in sorted(partner_map[g]):
            u.add(n)
            if len(u) >= cap:
                return u
    return u


def adjacency(edges: list[dict], universe: set[str]) -> dict[str, set[str]]:
    adj = {n: set() for n in universe}
    for e in edges:
        a, b = e["a"], e["b"]
        if a in universe and b in universe:
            adj[a].add(b)
            adj[b].add(a)
    return adj


class DistanceIndex:
    """Precomputed shortest distance from every node to the module.

    One multi-source BFS from all module members; ``dist`` maps node ->
    distance, nodes outside the universe map implicitly to ``unreachable``.
    """

    def __init__(self, adj: dict[str, set[str]], module: set[str],
                 unreachable: int):
        self.unreachable = unreachable
        self.dist: dict[str, int] = {}
        q = deque()
        for m in sorted(module):
            if m in adj:
                self.dist[m] = 0
                q.append(m)
        while q:
            cur = q.popleft()
            d = self.dist[cur] + 1
            if d > unreachable:
                break
            for nxt in adj[cur]:
                if nxt not in self.dist:
                    self.dist[nxt] = d
                    q.append(nxt)

    def to_module(self, node: str) -> int:
        return self.dist.get(node, self.unreachable)


def closest_distance(index: DistanceIndex, targets: list[str]) -> float:
    """Guney 'closest' measure: mean min distance of each target to M."""
    if not targets:
        return float(index.unreachable)
    return sum(index.to_module(t) for t in targets) / len(targets)


def _degree_bins(adj: dict[str, set[str]]) -> dict[int, list[str]]:
    """Log2 degree classes for degree-matched random sampling."""
    bins: dict[int, list[str]] = {}
    for n, nbrs in adj.items():
        d = len(nbrs)
        b = d.bit_length() - 1 if d else 0   # 0,1,2-3,4-7,8-15,...
        bins.setdefault(b, []).append(n)
    for b in bins:
        bins[b].sort()
    return bins


def proximity_zscore(adj: dict[str, set[str]], module: set[str],
                     targets: list[str], n_random: int, seed: int,
                     unreachable: int) -> dict:
    """z-score of closest_distance vs degree-matched random target sets."""
    index = DistanceIndex(adj, module, unreachable)
    d = closest_distance(index, targets)
    bins = _degree_bins(adj)

    def deg(n):
        nb = adj.get(n, set())
        return len(nb).bit_length() - 1 if nb else 0

    rng = random.Random(seed)
    samples = []
    nodes = sorted(adj)
    for _ in range(n_random):
        rtargets = []
        for t in targets:
            b = deg(t)
            pool = bins.get(b, nodes)
            rtargets.append(rng.choice(pool))
        samples.append(closest_distance(index, rtargets))
    mean = sum(samples) / len(samples)
    var = sum((x - mean) ** 2 for x in samples) / len(samples)
    sd = var ** 0.5
    z = 0.0 if sd == 0 else (d - mean) / sd
    return {"distance": round(d, 4), "z": round(z, 4),
            "random_mean": round(mean, 4), "random_sd": round(sd, 4),
            "n_random": n_random, "seed": seed}
