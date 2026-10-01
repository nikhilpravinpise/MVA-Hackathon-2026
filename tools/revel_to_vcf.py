"""Convert REVEL v1.3 CSV (Zenodo 7072866) to a tabix-ready VCF for VEP
--custom annotation.

    python tools/revel_to_vcf.py revel-v1.3_all_chromosomes.zip > revel.vcf
    sort -k1,1 -k2,2n revel.vcf | bgzip > revel_grch38.vcf.gz
    tabix -p vcf revel_grch38.vcf.gz

Input CSV columns: chr,hg19_pos,grch38_pos,ref,alt,aaref,aaalt,REVEL,
Ensembl_transcriptid. Rows lacking a GRCh38 position are dropped (the
pipeline runs hg38-only). Output rows carry INFO/REVEL=<score>; VEP
--custom emits them as CSQ token REVEL_REVEL (renamed to REVEL by the
run_vep.py header-reconcile step).
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import zipfile


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="REVEL CSV -> hg38 VCF stream")
    ap.add_argument("zip", help="revel-v1.3_all_chromosomes.zip")
    args = ap.parse_args(argv)

    zf = zipfile.ZipFile(args.zip)
    # members ship without a .csv suffix (e.g. 'revel_with_transcript_ids')
    names = [n for n in zf.namelist() if not n.endswith("/")]
    if not names:
        print(f"ERROR: no data member inside {args.zip}", file=sys.stderr)
        return 2

    sys.stdout.reconfigure(newline="")  # VCF must stay LF on Windows
    out = sys.stdout
    out.write("##fileformat=VCFv4.2\n")
    out.write('##INFO=<ID=REVEL,Number=1,Type=Float,'
              'Description="REVEL v1.3 score">\n')
    out.write("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\n")
    kept = dropped = 0
    for name in names:
        with zf.open(name) as raw:
            text = io.TextIOWrapper(raw, encoding="utf-8", newline="")
            for row in csv.reader(text):
                if not row or not row[0] or row[0] == "chr":
                    continue
                # chr, hg19_pos, grch38_pos, ref, alt, aaref, aaalt,
                # REVEL, Ensembl_transcriptid
                chrom, g38, ref, alt, score = row[0], row[2], row[3], \
                    row[4], row[7]
                if not g38 or g38 == ".":
                    dropped += 1
                    continue
                chrom = chrom[3:] if chrom.startswith("chr") else chrom
                out.write(f"{chrom}\t{g38}\t.\t{ref}\t{alt}\t.\t.\t"
                          f"REVEL={score}\n")
                kept += 1
    print(f"revel_to_vcf: kept {kept}, dropped {dropped} (no GRCh38 pos)",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
