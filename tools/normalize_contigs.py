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
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.vcf import to_submission_chrom  # noqa: E402

# Structured-header ID attribute: position-independent, quote-tolerant
# ('ID=' need not be the first attribute, values may be quoted, keys are
# case-insensitive in VCF spec). A candidate is a real attribute iff an
# even number of '"' precedes it - an 'ID=' inside a quoted value (e.g.
# a description field) must not be rewritten. A ##contig line whose ID
# cannot be extracted while data rows still get rewritten would leave
# the file header/data-inconsistent - warn loudly instead.
_CONTIG_ID = re.compile(r'\bID=("?)([^,">]+)\1', re.IGNORECASE)


def _contig_id_span(line: str) -> tuple[int, int] | None:
    for m in _CONTIG_ID.finditer(line):
        if line[:m.start()].count('"') % 2 == 0:
            return m.start(2), m.end(2)
    return None


def normalize(src: Path, dst: Path) -> int:
    n = 0
    with open(src, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        raise SystemExit(f"{src} is gzip-compressed - decompress first "
                         "(bgzip tools expect htslib paths, not this writer)")
    with open(src, encoding="utf-8", errors="replace") as fi, \
            open(dst, "w", encoding="utf-8", newline="\n") as fo:
        for line in fi:
            if line.startswith("##contig=<"):
                span = _contig_id_span(line)
                if span:
                    fo.write(line[:span[0]]
                             + to_submission_chrom(line[span[0]:span[1]])
                             + line[span[1]:])
                else:
                    print(f"WARNING: unparseable ##contig line passed "
                          f"through unchanged: {line.rstrip()!r}",
                          file=sys.stderr)
                    fo.write(line)
            elif line.startswith("#"):
                fo.write(line)
            else:
                c = line.split("\t", 1)
                if len(c) < 2:
                    raise SystemExit(
                        f"{src}: malformed data line (no TAB separator): "
                        f"{line.rstrip()!r} - is this really a VCF?")
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
