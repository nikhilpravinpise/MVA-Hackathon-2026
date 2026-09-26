"""CLI: clinical docx -> HPO term list JSON (plan.md Phase 1, first task).

    python tools/extract_hpo.py \
        --docx data/Challenge_Clinical_Phenotype_1.docx \
        --out results/hpo_terms.json

Wraps ``src.pheno.extract_hpo_from_docx`` and writes the phenopacket-style
record consumed downstream (Exomiser/LIRICAL inputs and the funnel's
phenotype tier):

    {"proband_id": "PROBAND01", "hpo_terms": ["HP:0000118", ...],
     "source": "<docx filename>"}

Exits nonzero with a clear stderr message on a missing/invalid docx or an
empty term list - an empty HPO list must fail loudly at the gate, not
propagate into a zero-phenotype pipeline run (Gate-1 falsification).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.pheno import extract_hpo_from_docx  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Extract HPO terms from the clinical phenotype docx")
    ap.add_argument("--docx", required=True, help="path to the .docx file")
    ap.add_argument("--out", default="results/hpo_terms.json",
                    help="output JSON path (default: results/hpo_terms.json)")
    ap.add_argument("--proband", default="PROBAND01",
                    help="proband_id written into the JSON record")
    args = ap.parse_args(argv)

    try:
        terms = extract_hpo_from_docx(args.docx)
    except FileNotFoundError:
        print(f"ERROR: docx not found: {args.docx}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"ERROR: cannot parse {args.docx} as a .docx "
              f"({type(exc).__name__}: {exc})", file=sys.stderr)
        return 2

    if not terms:
        print(f"ERROR: no HP:NNNNNNN terms found in {args.docx} - "
              "refusing to write an empty HPO list", file=sys.stderr)
        return 3

    payload = {
        "proband_id": args.proband,
        "hpo_terms": terms,
        "source": Path(args.docx).name,
    }
    out = Path(args.out)
    if out.is_dir():
        print(f"ERROR: --out is a directory: {out}", file=sys.stderr)
        return 2
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {len(terms)} HPO terms -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
