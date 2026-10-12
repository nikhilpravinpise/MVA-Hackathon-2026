"""Replay-mode engine tests - fully network-free.

Replays the recorded fixtures under tests/fixtures/track2/engine/ and
checks (a) the engine reproduces the committed evidence JSON and
(b) two runs are byte-identical once timestamps are stripped
(determinism).  If fixtures are absent these tests skip - they are not
meant to hit the network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from src.track2 import benchmark, engine, httpcache, t2config  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "track2" / "engine"
MVA_CACHE = FIX / "mva"
BENCH_CACHE = FIX / "benchmark"
CANDIDATES = REPO / "docs" / "track2" / "evidence" / "candidates.json"
BENCHMARK_JSON = REPO / "docs" / "track2" / "evidence" / "benchmark.json"


def _cfg():
    return t2config.load_config()


def _mva_case(cfg):
    return {
        "name": cfg["case"]["name"], "disease": cfg["case"]["disease"],
        "disease_gene": cfg["case"]["disease_gene"],
        "hpo_terms": cfg["case"].get("hpo_terms", []),
        "variants": cfg["case"].get("variants", []),
        "seed_genes": cfg["seed_genes"], "run_lincs": True,
    }


def _strip_volatile(d):
    d = json.loads(json.dumps(d))
    d.pop("generated_at", None)
    d.pop("config_sha", None)
    return d


fixtures_present = pytest.mark.skipif(
    not MVA_CACHE.exists() or not any(MVA_CACHE.glob("*.json")),
    reason="engine fixtures not recorded")


@fixtures_present
def test_mva_replay_is_deterministic():
    cfg = _cfg()
    r1 = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                              mode="replay"),
                         cfg, _mva_case(cfg))
    r2 = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                              mode="replay"),
                         cfg, _mva_case(cfg))
    assert _strip_volatile(r1) == _strip_volatile(r2)


@fixtures_present
@pytest.mark.skipif(not CANDIDATES.exists(), reason="evidence not generated")
def test_mva_replay_matches_committed_evidence():
    cfg = _cfg()
    r = engine.run_case(httpcache.CachedHttp(cache_dir=MVA_CACHE,
                                             mode="replay"),
                        cfg, _mva_case(cfg))
    committed = json.loads(CANDIDATES.read_text(encoding="utf-8"))
    assert _strip_volatile(r) == _strip_volatile(committed)


bench_fixtures = pytest.mark.skipif(
    not BENCH_CACHE.exists() or not any(BENCH_CACHE.glob("*.json")),
    reason="benchmark fixtures not recorded")


@bench_fixtures
def test_benchmark_replay_runs_and_recovers():
    cfg = _cfg()
    out = benchmark.run_benchmark(
        httpcache.CachedHttp(cache_dir=BENCH_CACHE, mode="replay"), cfg)
    assert out["n_cases"] == len(cfg["benchmark"]["cases"])
    assert 0.0 <= out["recall_at_10"] <= 1.0
    # the best-documented positive control must be recovered
    tsc2 = next(c for c in out["cases"] if c["gene"] == "TSC2")
    ranks = [k["rank"] for k in tsc2["known_drugs"] if k["found"]]
    assert ranks and min(ranks) <= 10


@bench_fixtures
@pytest.mark.skipif(not BENCHMARK_JSON.exists(),
                    reason="evidence not generated")
def test_benchmark_replay_matches_committed_evidence():
    cfg = _cfg()
    out = benchmark.run_benchmark(
        httpcache.CachedHttp(cache_dir=BENCH_CACHE, mode="replay"), cfg)
    committed = json.loads(BENCHMARK_JSON.read_text(encoding="utf-8"))
    assert _strip_volatile(out) == _strip_volatile(committed)
