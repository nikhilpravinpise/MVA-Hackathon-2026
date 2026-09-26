"""Write a chr-prefixed copy of a VCF for chr-contig tools (Arm A).

    python tools/normalize_contigs.py IN.vcf OUT.vcf

The funnel works on the challenge VCF's bare contigs ('12') and emits
chr-prefixed contigs only at submission time. Arm-A tools (Exomiser's
hg38 bundle, IGV, DeepVariant) want 'chr12' - this writes the derived
copy deterministically: contig header IDs + column 1 through
``src.vcf.to_submission_chrom`` (the same map used for the submission
CSV, so 23->chrX / 25->chrM / chr-prefixed inputs pass through).

The copy is a DERIVED artifact - regenerate it whenever the source VCF
changes. ``tools/run_track1.find_vcf`` excludes ``*.chr.vcf`` from case
inputs by convention; name the output accordingly.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.vcf import to_submission_chrom  # noqa: E402


def normalize(src: Path, dst: Path) -> int:
    n = 0
    with open(src, encoding="utf-8", errors="replace") as fi, \
            open(dst, "w", encoding="utf-8", newline="\n") as fo:
        for line in fi:
            if line.startswith("##contig=<ID="):
                inner = line.split("ID=", 1)[1].split(",", 1)
                fo.write(line.replace("ID=" + inner[0],
                                      "ID=" + to_submission_chrom(inner[0]),
                                      1))
            elif line.startswith("#"):
                fo.write(line)
            else:
                c = line.split("\t", 1)
                fo.write(to_submission_chrom(c[0]) + "\t" + c[1])
                n += 1
    return n


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src")
    ap.add_argument("dst")
    args = ap.parse_args(argv)
    src, dst = Path(args.src), Path(args.dst)
    if not src.exists():
        raise SystemExit(f"{src} not found")
    if dst.name != "chr.vcf" and not dst.name.endswith(".chr.vcf"):
        print(f"note: {dst.name} lacks the .chr.vcf convention - "
              "run_track1.find_vcf will treat it as a case input",
              file=sys.stderr)
    n = normalize(src, dst)
    print(f"wrote {dst} ({n} variant lines, chr-prefixed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
