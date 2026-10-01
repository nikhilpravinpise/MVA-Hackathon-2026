#!/usr/bin/env python3
"""Split a gnomAD joint-sites slice VCF into exomes/genomes AF-only VCFs
whose INFO fields carry contract names for VEP --custom emission.

Slice rows hold fields like AF_exomes / AF_exomes_nfe / AF_genomes_nfe /
nhomalt_joint. VEP --custom emits '<short>_<field>'; to land the funnel's
gnomADe_AF / gnomADe_NFE_AF contract we rename INFO fields to AF, AFR_AF,
AMI_AF, AMR_AF, ASJ_AF, EAS_AF, FIN_AF, MID_AF, NFE_AF, OTH_AF, SAS_AF.

usage: gnomad_split.py <slice.vcf.gz> e|g   (writes to stdout)

'e' emits the exomes file, 'g' the genomes file. Both share the slice's
contig header so coordinates match the patient VCF (bare contigs)."""
from __future__ import annotations

import gzip
import sys

POPS = ["AFR", "AMI", "AMR", "ASJ", "EAS", "FIN", "MID", "NFE",
        "OTH", "SAS"]


def main() -> None:
    src, side = sys.argv[1], sys.argv[2]
    src_field = "AF_exomes" if side == "e" else "AF_genomes"
    pops_src = {"afr": "AFR", "ami": "AMI", "amr": "AMR", "asj": "ASJ",
                "eas": "EAS", "fin": "FIN", "mid": "MID", "nfe": "NFE",
                "remaining": "OTH", "sas": "SAS"}
    # INFO rename: src -> emitted field name
    ren = {src_field: "AF"}
    for src_pop, out_pop in pops_src.items():
        ren[f"{src_field}_{src_pop}"] = f"{out_pop}_AF"

    out = sys.stdout
    # fresh INFO header block for the emitted field names
    defs = [
        f'##INFO=<ID={f},Number=A,Type=Float,Description="AF">'
        for f in ["AF"] + [f"{p}_AF" for p in POPS]
    ]
    wrote_defs = False
    with gzip.open(src, "rt", errors="replace") as fh:
        for line in fh:
            if line.startswith("##INFO"):
                if not wrote_defs:
                    for d in defs:
                        out.write(d + "\n")
                    wrote_defs = True
                continue  # drop slice's own INFO defs
            if line.startswith("#"):
                out.write(line)
                continue
            f = line.rstrip("\n").split("\t", 8)
            if len(f) < 8:
                continue
            info = {}
            for tok in f[7].split(";"):
                k, _, v = tok.partition("=")
                if k in ren:
                    info[ren[k]] = v
            f[7] = ";".join(f"{k}={v}" for k, v in info.items()) if info else "."
            out.write("\t".join(f[:7]) + "\t" + f[7] + "\n")


if __name__ == "__main__":
    main()
