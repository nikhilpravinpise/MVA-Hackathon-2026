"""Convert env/corpus/genes_to_phenotype.txt into the JSON maps the funnel reads.

    python tools/genes_to_disease_json.py
    python tools/genes_to_disease_json.py --in env/corpus/genes_to_phenotype.txt \
        --corpus env/corpus

Outputs (into --corpus, default env/corpus/):

    gene_to_hpo.json     {SYMBOL: ["HP:0000007", ...]}   - deduped, sorted
    gene2disease.json    {SYMBOL: ["OMIM:243400", ...]}  - deduped, sorted

Input format: the HPO ``genes_to_phenotype.txt`` release file. Current
releases carry a 6-column header ``ncbi_gene_id gene_symbol hpo_id hpo_name
frequency disease_id``; older releases use a 9-column layout (extra
frequency-hpo / source columns) with ``disease_id`` LAST. This converter maps
columns by header name when a header line is present and falls back to the
positional convention otherwise, so either release parses.

The gene2disease map is what src/pheno.gene_disease_map() loads and what
src/pheno.gene_hpo_terms() joins against the phenotype.hpoa-derived
{disease_id: set(HPO)} map. disease_id values must therefore match the
phenotype.hpoa database_id convention (``OMIM:nnnnnn``, ``ORPHA:nnnn``,
``DECIPHER:nn``); rows with missing/'-'/' ' disease ids are skipped for the
disease map but still counted for the gene->HPO map.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "env" / "corpus"
HPO_RE = re.compile(r"HP:\d{7}")

# canonical column names across release layouts
COL_GENE_ID = "ncbi_gene_id"
COL_SYMBOL = "gene_symbol"
COL_HPO = "hpo_id"
COL_DISEASE = "disease_id"


def _resolve_columns(header_fields: list[str] | None,
                     ncols: int) -> dict[str, int]:
    """Return column indices for symbol / hpo_id / disease_id."""
    if header_fields:
        h = {name: i for i, name in enumerate(header_fields)}
        if COL_SYMBOL in h and COL_HPO in h:
            return {
                "symbol": h[COL_SYMBOL],
                "hpo": h[COL_HPO],
                "disease": h.get(COL_DISEASE, ncols - 1),
            }
    # positional fallback: 0 ncbi_id, 1 symbol, 2 hpo, 3 hpo_name,
    # disease id is always the LAST column in every known layout
    return {"symbol": 1, "hpo": 2, "disease": ncols - 1}


def convert(txt_path: Path) -> tuple[dict[str, list[str]], dict[str, list[str]],
                                     dict[str, int]]:
    gene2hpo: dict[str, set[str]] = {}
    gene2dis: dict[str, set[str]] = {}
    stats = {"rows": 0, "skipped": 0, "no_disease": 0}
    header: list[str] | None = None

    for raw in txt_path.read_text(encoding="utf-8",
                                  errors="replace").splitlines():
        if not raw or raw.startswith("#"):
            continue
        cols = raw.split("\t")
        if header is None and COL_GENE_ID in cols[0].lower():
            header = [c.strip().lower() for c in cols]
            continue
        idx = _resolve_columns(header, len(cols))
        if len(cols) <= max(idx["symbol"], idx["hpo"]):
            stats["skipped"] += 1
            continue
        symbol = cols[idx["symbol"]].strip()
        hpo = cols[idx["hpo"]].strip()
        if not symbol or not HPO_RE.fullmatch(hpo):
            stats["skipped"] += 1
            continue
        stats["rows"] += 1
        gene2hpo.setdefault(symbol, set()).add(hpo)
        if idx["disease"] < len(cols):
            dis = cols[idx["disease"]].strip()
            if dis and dis not in ("-", "."):
                gene2dis.setdefault(symbol, set()).add(dis)
            else:
                stats["no_disease"] += 1
        else:
            stats["no_disease"] += 1

    return ({g: sorted(v) for g, v in sorted(gene2hpo.items())},
            {g: sorted(v) for g, v in sorted(gene2dis.items())},
            stats)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="genes_to_phenotype.txt -> gene_to_hpo.json + gene2disease.json")
    ap.add_argument("--in", dest="src", default=str(CORPUS / "genes_to_phenotype.txt"))
    ap.add_argument("--corpus", default=str(CORPUS))
    args = ap.parse_args(argv)

    src = Path(args.src)
    if not src.exists():
        raise SystemExit(f"missing {src} - run tools/fetch_refs.py first")
    corpus = Path(args.corpus)
    corpus.mkdir(parents=True, exist_ok=True)

    gene2hpo, gene2dis, stats = convert(src)

    (corpus / "gene_to_hpo.json").write_text(
        json.dumps(gene2hpo, indent=1) + "\n", encoding="utf-8")
    (corpus / "gene2disease.json").write_text(
        json.dumps(gene2dis, indent=1) + "\n", encoding="utf-8")

    print("genes_to_disease_json summary")
    print(f"  input rows parsed : {stats['rows']:,} (+{stats['skipped']} skipped)")
    print(f"  genes with HPO    : {len(gene2hpo):,}  -> {corpus / 'gene_to_hpo.json'}")
    print(f"  genes with disease: {len(gene2dis):,}  -> {corpus / 'gene2disease.json'}"
          f"  ({stats['no_disease']:,} rows had no disease_id)")
    n_hpo = sum(len(v) for v in gene2hpo.values())
    n_dis = sum(len(v) for v in gene2dis.values())
    print(f"  unique gene->HPO edges     : {n_hpo:,}")
    print(f"  unique gene->disease edges : {n_dis:,}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
