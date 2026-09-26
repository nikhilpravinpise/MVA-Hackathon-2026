"""Threshold sensitivity grid (plan.md section 5 - NOT tuning).

Reruns the funnel over the frozen config's af_grid x damage-vote cutoffs and
reports the true pair's rank at each grid point. Robust across the grid =
not overfit; fragile = reported honestly in the write-up.

    python tools/run_sensitivity.py --vcf V --hpo-terms J --obo O --hpoa H \
        --gene2disease G --truth results/spike_case/truth.json \
        --out results/sensitivity.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.config import load_config  # noqa: E402
from src.pipeline import run_pipeline  # noqa: E402


def pair_rank(ranked: list[dict], truth_pair: list[dict]) -> int | None:
    from src.vcf import from_submission_chrom as _norm
    want = sorted((_norm(str(v["chrom"])), v["pos"], v["ref"], v["alt"])
                  for v in truth_pair)
    for h in ranked:
        got = sorted((v["chrom"], v["pos"], v["ref"], v["alt"])
                     for v in h["variants"])
        if h["model"] == "compound_het" and got == want:
            return h["rank"]
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--vcf", required=True)
    ap.add_argument("--hpo-terms", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--obo", default=None)
    ap.add_argument("--hpoa", default=None)
    ap.add_argument("--gene2disease", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args(argv)

    hpo_raw = json.loads(Path(args.hpo_terms).read_text())
    hpo = hpo_raw["hpo_terms"] if isinstance(hpo_raw, dict) else list(hpo_raw)
    truth_file = Path(args.truth)
    if not truth_file.exists():
        print(f"ERROR: truth file {args.truth} not found - the sensitivity "
              "grid needs a known-answer case (a negative-control case has "
              "no planted pair to rank)", file=sys.stderr)
        return 2
    truth = json.loads(truth_file.read_text())
    if not truth.get("pair"):
        print(f"ERROR: {args.truth} has no 'pair' - nothing to rank-track "
              "across the grid", file=sys.stderr)
        return 2
    cfg = load_config()

    grid = []
    for af in cfg["rarity"]["af_grid"]:
        for votes in (1, 2, 3):
            c = load_config()
            c["rarity"]["af_max"] = af
            c["consequence"]["min_votes"] = votes
            res = run_pipeline(args.vcf, hpo, obo_path=args.obo,
                               hpoa_path=args.hpoa, g2d_path=args.gene2disease,
                               cfg=c)
            rank = pair_rank(res["ranked"], truth["pair"])
            grid.append({"af_max": af, "min_votes": votes,
                         "pair_rank": rank,
                         "emitted": res["funnel"]["emitted"]})
            print(f"af_max={af:g} min_votes={votes} -> pair rank {rank} "
                  f"(emitted {res['funnel']['emitted']})")

    out = {"vcf": args.vcf, "truth_pair": truth["pair"], "grid": grid,
           "robust": all(g["pair_rank"] is not None and g["pair_rank"] <= 5
                        for g in grid)}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))
    print("robust across grid:", out["robust"])
    return 0 if out["robust"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
