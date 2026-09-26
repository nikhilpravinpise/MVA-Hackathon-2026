"""Compare Arm A (Exomiser TSV_GENE) vs Arm B (funnel result.json) rankings.

    python tools/compare_arms.py \
        --armb results/real_spike_run/result.json \
        --arma env/exomiser/PROBAND01-PASS_ONLY-exomiser.genes.tsv \
        --truth env/real_spike/truth.json --out results/arm_concordance.json

The plan's cross-method metric (section 5, 'Arm concordance'): overlap of
the two arms' top-20 gene lists + the truth gene's rank in each. Both arms
are answer-blind to the same VCF/HPO inputs, so agreement is orthogonal
evidence - a gene ranked high by only one arm is a method artifact, not a
shared signal.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def armb_genes(result_path: Path) -> list[str]:
    """Arm B ranked gene order (first-appearance order of ranked hyps)."""
    res = json.loads(result_path.read_text(encoding="utf-8"))
    genes: list[str] = []
    for h in res.get("ranked", []):
        g = h.get("gene")
        if g and g not in genes:
            genes.append(g)
    return genes


def arma_genes(tsv_path: Path) -> list[str]:
    """Exomiser TSV_GENE order (already score-sorted desc; keep file order).

    Header-aware: GENE_SYMBOL / EXOMISER_GENE_SCORE column names are the
    14.x output contract - fail loudly on drift rather than mis-parse.
    """
    with open(tsv_path, newline="", encoding="utf-8") as f:
        rd = csv.reader(f, delimiter="\t")
        try:
            header = next(rd)
        except StopIteration:
            raise ValueError(f"{tsv_path}: empty file - no header row")
        try:
            gi = header.index("GENE_SYMBOL")
        except ValueError:
            raise ValueError(
                f"{tsv_path}: no GENE_SYMBOL column (header {header!r}) - "
                "Exomiser output schema changed")
        if any(h.startswith("EXOMISER_VARIANT") for h in header):
            # variants.tsv also carries GENE_SYMBOL - gene order derived
            # from a variant-level file is plausible-but-wrong ranks
            raise ValueError(
                f"{tsv_path}: looks like a variants.tsv "
                "(EXOMISER_VARIANT_* columns) - pass the genes.tsv")
        genes: list[str] = []
        for row in rd:
            if len(row) > gi and row[gi] and row[gi] not in genes:
                genes.append(row[gi])
    return genes


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--armb", required=True, help="funnel result.json")
    ap.add_argument("--arma", required=True, help="Exomiser genes.tsv")
    ap.add_argument("--truth", default=None,
                    help="truth.json - reports the truth gene's rank per arm")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)

    b = armb_genes(Path(args.armb))
    a = arma_genes(Path(args.arma))
    top_b, top_a = set(b[:args.top]), set(a[:args.top])
    overlap = sorted(top_b & top_a)

    truth_gene = None
    if args.truth:
        t = json.loads(Path(args.truth).read_text(encoding="utf-8"))
        truth_gene = t.get("gene")

    def rank_of(gene_list, gene):
        return (gene_list.index(gene) + 1) if gene in gene_list else None

    summary = {
        "arm_a_file": str(args.arma),
        "arm_b_file": str(args.armb),
        "n_arm_a_genes": len(a),
        "n_arm_b_genes": len(b),
        "top_n": args.top,
        f"top{args.top}_overlap": overlap,
        f"top{args.top}_overlap_n": len(overlap),
        "truth_gene": truth_gene,
        "truth_rank_arm_b": rank_of(b, truth_gene) if truth_gene else None,
        "truth_rank_arm_a": rank_of(a, truth_gene) if truth_gene else None,
    }
    js = json.dumps(summary, indent=1)
    print(js)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(js + "\n", encoding="utf-8")
        print(f"wrote {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
