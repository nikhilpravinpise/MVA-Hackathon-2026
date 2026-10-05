"""Build a Track-1 submission CSV from the Arm-A (Exomiser) run.

The funnel CSV carries model1; this tool produces the independent-model
candidate for a possible ``model2`` entry - same byte-level contract
(``src/submit.py`` writer), derived from Exomiser's own output, never
hand-assembled. The Exomiser variants TSV marks causal variants with
``CONTRIBUTING_VARIANT=1`` per (rank, gene, MOI) block; we take the
rank-1 block's contributing variants verbatim and emit one row.

epcr for the Arm-A row is the gene's ``EXOMISER_GENE_COMBINED_SCORE``
clamped into (0, 1] - a published-engine score, not our rank map. With a
single row the oracle's rank is 1 regardless of epcr magnitude; the value
is informational.

Usage::

    python tools/make_arm_a_csv.py \
        --variants results/exomiser_patient/WGS_EX2312012-PASS_ONLY.variants.tsv \
        --out submissions/nikhilpise_exomiser-arm.csv \
        --expect results/track1_patient_modal/track1_final_indelfix/funnel/result_head.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.submit import submission_bytes  # noqa: E402


def _hyp_to_row(variants: list[tuple], epcr: float, notes: str) -> dict:
    """Build one submission row dict through the same normalization the
    writer applies (chrom->chrN, allele upper, notes ASCII-cleaned)."""
    (c1, p1, r1, a1), (c2, p2, r2, a2) = variants
    return {
        "proband_id": "PROBAND01",
        "chrom_1": c1 if str(c1).lower().startswith("chr")
                   else f"chr{c1}",
        "pos_1": int(p1), "ref_1": r1.upper(), "alt_1": a1.upper(),
        "chrom_2": c2 if str(c2).lower().startswith("chr")
                   else f"chr{c2}",
        "pos_2": int(p2), "ref_2": r2.upper(), "alt_2": a2.upper(),
        "epcr": float(epcr),
        "finding_type": "primary",
        "notes": notes.encode("ascii", "ignore").decode("ascii"),
    }


def _hgvs_short(hgvs: str) -> str:
    """'BUB1B:ENST00000287598.11:c.2210T>G:p.(Leu737*)' -> 'c.2210T>G
    p.(Leu737*)' (transcript-id parts dropped, protein kept verbatim)."""
    if not hgvs:
        return ""
    parts = hgvs.split(":")
    return " ".join(p for p in parts if p.startswith(("c.", "p.")))


def contributing_variants(tsv_path) -> dict:
    """Group CONTRIBUTING_VARIANT=1 rows by Exomiser rank.

    Returns {rank: {"gene": sym, "moi": moi, "score": combined,
    "variants": [(contig,start,ref,alt),...], "hgvs": [str,...]}}.
    A variant can appear under several (rank, MOI) blocks - each block is
    a distinct model hypothesis, so keys stay per-rank.
    """
    blocks: dict[int, dict] = {}
    with open(tsv_path, newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row.get("CONTRIBUTING_VARIANT") != "1":
                continue
            try:
                rank = int(row["#RANK"])
            except (KeyError, ValueError):
                continue
            b = blocks.setdefault(rank, {
                "gene": row.get("GENE_SYMBOL", ""),
                "moi": row.get("MOI", ""),
                "score": row.get("EXOMISER_GENE_COMBINED_SCORE", ""),
                "variants": [], "hgvs": [], "disease": "",
            })
            v = (row["CONTIG"], int(row["START"]), row["REF"], row["ALT"])
            if v not in b["variants"]:
                b["variants"].append(v)
                b["hgvs"].append(row.get("HGVS", ""))
            if row.get("EXOMISER_ACMG_DISEASE_NAME"):
                b["disease"] = row["EXOMISER_ACMG_DISEASE_NAME"]
            if row.get("EXOMISER_ACMG_DISEASE_ID"):
                b["disease_id"] = row["EXOMISER_ACMG_DISEASE_ID"]
    return blocks


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Arm-A (Exomiser) submission CSV builder")
    ap.add_argument("--variants", required=True,
                    help="Exomiser *.variants.tsv")
    ap.add_argument("--rank", type=int, default=1,
                    help="Exomiser rank block to submit (default 1)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--expect", default=None,
                    help="optional result.json/result_head.json whose "
                         "emitted pair must match the derived variants "
                         "(cross-arm sanity check)")
    args = ap.parse_args(argv)

    blocks = contributing_variants(args.variants)
    block = blocks.get(args.rank)
    if block is None:
        print(f"ERROR: no contributing variants at rank {args.rank} in "
              f"{args.variants} (ranks present: {sorted(blocks)})",
              file=sys.stderr)
        return 2
    if len(block["variants"]) != 2:
        print(f"ERROR: expected exactly 2 contributing variants at rank "
              f"{args.rank}, got {len(block['variants'])} - refusing to "
              "guess a row shape", file=sys.stderr)
        return 2
    try:
        score = float(block["score"])
    except (TypeError, ValueError):
        score = 0.5
    epcr = min(max(score, 1e-4), 1.0)

    if args.expect:
        exp = json.loads(Path(args.expect).read_text(encoding="utf-8"))
        got = sorted((str(c), int(p), r, a) for c, p, r, a
                     in block["variants"])
        want = None
        for h in exp.get("ranked", []):
            if h.get("emitted") and len(h.get("variants", [])) == 2:
                want = sorted((str(v["chrom"]), int(v["pos"]),
                               v["ref"], v["alt"])
                              for v in h["variants"])
                break
        if want and got != want:
            print(f"ERROR: Arm-A rank-{args.rank} variants {got} do not "
                  f"match the emitted pair {want} in {args.expect}",
                  file=sys.stderr)
            return 3

    hgvs = " + ".join(_hgvs_short(h) for h in block["hgvs"])
    notes = (f"{block['gene']}_{block['moi']} Exomiser 14.0.0 "
             f"rank{args.rank} combined {score:.4g}"
             + (f" {block.get('disease_id')}" if block.get("disease_id")
                else "")
             + (f" {hgvs}" if hgvs else ""))
    row = _hyp_to_row(block["variants"], epcr, notes)
    data = submission_bytes([row])
    Path(args.out).write_bytes(data)
    print(f"wrote {args.out}")
    print(data.decode(), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
