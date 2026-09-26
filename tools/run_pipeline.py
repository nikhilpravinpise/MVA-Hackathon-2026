"""CLI: run the Arm-B funnel on any annotated VCF + phenotype corpus.

    python tools/run_pipeline.py \
        --vcf results/spike_case/spike_proband.vcf \
        --hpo-terms results/spike_case/hpo_terms.json \
        --obo results/spike_case/hp.obo \
        --hpoa results/spike_case/phenotype.hpoa \
        --gene2disease results/spike_case/genes_to_disease.json \
        --out results/run_spike

    --drop gnomad --drop hpo     # leave-one-source-out ablation runs
    --af-max 1e-3                # sensitivity-grid override (config unchanged)

All outputs land under --out (result.json, funnel_counts.json,
hypotheses.tsv). Deterministic: identical inputs give byte-identical outputs.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.config import load_config  # noqa: E402
from src.pipeline import ABLATION_SOURCES, run_pipeline  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Arm-B triage funnel")
    ap.add_argument("--vcf", required=True)
    ap.add_argument("--hpo-terms", required=True,
                    help="JSON with an 'hpo_terms' list (or a bare list)")
    ap.add_argument("--obo", default=None)
    ap.add_argument("--hpoa", default=None)
    ap.add_argument("--gene2disease", default=None)
    ap.add_argument("--sample", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--drop", action="append", default=[],
                    choices=sorted(ABLATION_SOURCES),
                    help="ablate an evidence source (repeatable)")
    ap.add_argument("--af-max", type=float, default=None,
                    help="sensitivity override for rarity.af_max")
    args = ap.parse_args(argv)

    try:
        hpo_raw = json.loads(
            Path(args.hpo_terms).read_text(encoding="utf-8-sig"))
        hpo = hpo_raw["hpo_terms"] if isinstance(hpo_raw, dict) \
            else list(hpo_raw)
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as e:
        print(f"ERROR: cannot read --hpo-terms {args.hpo_terms} "
              f"({type(e).__name__}: {e})", file=sys.stderr)
        return 2
    if not hpo or not all(isinstance(t, str) for t in hpo):
        print("ERROR: --hpo-terms parsed to an empty/non-string term list",
              file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    if args.af_max is not None:
        cfg["rarity"]["af_max"] = args.af_max

    result = run_pipeline(
        args.vcf, hpo, obo_path=args.obo, hpoa_path=args.hpoa,
        g2d_path=args.gene2disease, cfg=cfg, cfg_path=args.config,
        sample=args.sample, drops=frozenset(args.drop), out_dir=args.out)

    ranked = result["ranked"]
    print(f"funnel: {result['funnel']}")
    print(f"monotonicity: {'OK' if not result['monotonicity_violations'] else result['monotonicity_violations']}")
    for h in ranked[:10]:
        print(f"  #{h['rank']:2d} {h['gene']:10s} {h['model']:13s} "
              f"score={h['score']:.3f} epcr={h['epcr']:.3f} "
              f"trans={h['in_trans']} emitted={h['emitted']} "
              f"{' + '.join(f'{v['chrom']}:{v['pos']}' for v in h['variants'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
