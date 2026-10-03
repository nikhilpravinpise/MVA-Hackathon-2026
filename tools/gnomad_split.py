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


def _info_id(line: str) -> str | None:
    # '##INFO=<ID=AF_exomes_nfe,Number=A,...>' -> 'AF_exomes_nfe'
    if not line.startswith("##INFO=<ID="):
        return None
    rest = line[len("##INFO=<ID="):]
    return rest.split(",", 1)[0].split(">", 1)[0]


def main() -> None:
    src, side = sys.argv[1], sys.argv[2]
    suf = "exomes" if side == "e" else "genomes"
    pops_src = {"afr": "AFR", "ami": "AMI", "amr": "AMR", "asj": "ASJ",
                "eas": "EAS", "fin": "FIN", "mid": "MID", "nfe": "NFE",
                "remaining": "OTH", "sas": "SAS"}
    # INFO rename: src -> emitted field name. Sites files name fields
    # AF / AF_<pop>; joint files name them AF_exomes / AF_exomes_<pop>
    # (resp. AF_genomes_*). Build a merged map for whichever is present;
    # absent keys are no-ops. The _XX/_XY sex-bucketed fields are dropped
    # (not in the contract).
    ren = {"AF": "AF", f"AF_{suf}": "AF"}
    for src_pop, out_pop in pops_src.items():
        ren[f"AF_{src_pop}"] = f"{out_pop}_AF"
        ren[f"AF_{suf}_{src_pop}"] = f"{out_pop}_AF"
    info_ids: set[str] = set()
    ren_fixed = False

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
                iid = _info_id(line)
                if iid is not None:
                    info_ids.add(iid)
                if not wrote_defs:
                    for d in defs:
                        out.write(d + "\n")
                    wrote_defs = True
                continue  # drop slice's own INFO defs
            if line.startswith("##contig=<ID=chr"):
                line = line.replace("ID=chr", "ID=", 1)
            if line.startswith("#"):
                out.write(line)
                continue
            f = line.rstrip("\n").split("\t", 8)
            if len(f) < 8:
                continue
            if f[0].startswith("chr"):
                f[0] = f[0][3:]
            if not ren_fixed:
                # Joint detection: a file defining ANY AF_exomes_* or
                # AF_genomes_* field is a joint file, and every bare
                # AF / AF_<pop> token in it is the JOINT frequency -
                # never a subset one. Drop ALL bare mappings so a joint
                # AF can never land in a subset-labeled contract field
                # (a genomes-only row would otherwise emit joint AF as
                # gnomADe_AF; a genomes-only FILE would do the same
                # under the opposite side). Sites files define only
                # bare names, so nothing is dropped there.
                ren_fixed = True
                if any(i.startswith("AF_exomes")
                       or i.startswith("AF_genomes") for i in info_ids):
                    ren.pop("AF", None)
                    for sp in pops_src:
                        ren.pop(f"AF_{sp}", None)
            info = {}
            for tok in f[7].split(";"):
                k, _, v = tok.partition("=")
                if k in ren:
                    info[ren[k]] = v
            f[7] = ";".join(f"{k}={v}" for k, v in info.items()) if info else "."
            out.write("\t".join(f[:7]) + "\t" + f[7] + "\n")


if __name__ == "__main__":
    main()
