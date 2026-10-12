"""Track 2 repurposing engine driver.

    python tools/run_track2.py                       # MVA case, live
    python tools/run_track2.py --benchmark           # retrospective benchmark
    python tools/run_track2.py --mode record --cache-dir tests/fixtures/track2/engine/cache
    python tools/run_track2.py --mode replay --cache-dir tests/fixtures/track2/engine/cache
    python tools/run_track2.py --trim-cache tests/fixtures/track2/engine/cache

Modes: ``live`` fetches only, ``record`` fetches and writes every raw
response to the cache dir, ``replay`` never touches the network - it
re-serves identical requests byte-for-byte (tests are network-free).

Outputs:
    docs/track2/evidence/candidates.json   (MVA case)
    docs/track2/evidence/benchmark.json    (--benchmark)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.track2 import benchmark, engine, httpcache, sources, t2config  # noqa: E402

EVIDENCE = REPO / "docs" / "track2" / "evidence"


def _write(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size:,} bytes)")


def mva_case(cfg) -> dict:
    """Case spec for the MVA proband: seeds + axes from the frozen config."""
    return {
        "name": cfg["case"]["name"],
        "disease": cfg["case"]["disease"],
        "disease_gene": cfg["case"]["disease_gene"],
        "hpo_terms": cfg["case"].get("hpo_terms", []),
        "variants": cfg["case"].get("variants", []),
        "seed_genes": cfg["seed_genes"],
        "run_lincs": True,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", default=str(t2config.DEFAULT_CONFIG))
    ap.add_argument("--benchmark", action="store_true",
                    help="run the frozen benchmark cases instead of the MVA case")
    ap.add_argument("--mode", choices=["live", "record", "replay"],
                    default="live")
    ap.add_argument("--cache-dir", default=None,
                    help="cache dir for record/replay modes")
    ap.add_argument("--out", default=None, help="output JSON path")
    ap.add_argument("--trim-cache", metavar="DIR", default=None,
                    help="trim recorded fixture bodies to used fields, then exit")
    ap.add_argument("--string-version", action="store_true",
                    help="print STRING api version and exit")
    args = ap.parse_args(argv)

    if args.trim_cache:
        rep = httpcache.trim_cache(args.trim_cache)
        print(json.dumps(rep, indent=2))
        return 0

    if args.mode in ("record", "replay") and not args.cache_dir:
        ap.error(f"--mode {args.mode} requires --cache-dir")
    cfg = t2config.load_config(args.config)
    http = httpcache.CachedHttp(cache_dir=args.cache_dir, mode=args.mode)

    if args.string_version:
        ver, _ = sources.string_version(http, cfg["endpoints"]["string"])
        print("STRING version:", ver)
        return 0

    config_sha = t2config.config_dict_hash(cfg)

    if args.benchmark:
        out = benchmark.run_benchmark(http, cfg)
        out["config_sha"] = config_sha
        path = Path(args.out) if args.out else EVIDENCE / "benchmark.json"
        _write(out, path)
        print(f"benchmark: {out['n_cases']} cases, "
              f"recall@1/5/10 = {out['recall_at_1']}/"
              f"{out['recall_at_5']}/{out['recall_at_10']}")
        return 0

    res = engine.run_case(http, cfg, mva_case(cfg))
    res["config_sha"] = config_sha
    path = Path(args.out) if args.out else EVIDENCE / "candidates.json"
    _write(res, path)
    tiers = {}
    for c in res["candidates"]:
        tiers[c["tier"]] = tiers.get(c["tier"], 0) + 1
    print(f"candidates: {len(res['candidates'])} approved | tiers {tiers} | "
          f"module {res['module']['n']} genes | "
          f"lincs {res['lincs']['status']} | "
          f"direction: {res['direction']['n_aligned']} aligned, "
          f"{res['direction']['n_neutral']} neutral, "
          f"{res['direction']['n_opposed_excluded']} mechanism-opposed "
          f"excluded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
