"""Emit / execute the VEP 116 offline annotation command for the challenge VCF.

    python tools/run_vep.py --vcf data/WGS.vcf.gz --out data/WGS.vep.vcf.gz \
        --cache-dir D:/vep_cache --ann-dir D:/vep_ann --dry-run
    python tools/run_vep.py --vcf data/WGS.vcf.gz --out data/WGS.vep.vcf.gz \
        --cache-dir D:/vep_cache --ann-dir D:/vep_ann          # runs docker

Command template (what --dry-run prints; --forks/--image are parameterized):

    docker run --rm -v CACHE:/opt/vep/.vep -v VCFDIR:/data -v ANN:/ann \
      ensemblorg/ensembl-vep:release_116.1 \
      vep --offline --cache --dir_cache /opt/vep/.vep \
          --species homo_sapiens --assembly GRCh38 \
          -i /data/<in> -o /data/<out> --vcf --compress_output bgzip \
          --fork 16 --everything --no_stats \
          --plugin CADD,/ann/CADD_v1.7_GRCh38_SNV.tsv.gz,/ann/CADD_v1.7_GRCh38_InDels.tsv.gz \
          --plugin dbNSFP,'consequence=ALL',/ann/dbNSFP5.3.1_grch38.gz,<fields>

REQUIRED ONE-TIME DOWNLOADS (~60-90 GB total, plan.md section 3)
----------------------------------------------------------------
* VEP 116 GRCh38 cache: homo_sapiens_vep_116_GRCh38.tar.gz
  (Ensembl FTP; unpacked under --cache-dir so that
  <cache-dir>/homo_sapiens/116_GRCh38/ exists). Includes gnomAD v4.1
  exome+genome AFs (--af_gnomade/--af_gnomadg are inside --everything) and
  the ClinVar snapshot behind --clin_sig.
* dbNSFP 5.3.1 VEP-ready GRCh38 + .tbi  (https://www.dbnsfp.org/download)
* CADD v1.7 GRCh38 whole-genome SNVs + InDels + .tbi
  (https://cadd.gs.washington.edu/download - free registration)
* Optional: fresher ClinVar VCF via --custom (see below) if the cache's
  bundled snapshot is stale at run time.

ANNOTATION CONTRACT (must match src/synth.py CSQ_FIELDS)
--------------------------------------------------------
The funnel (src/triage.py) reads CSQ fields by NAME from the output VCF's
`##INFO=<ID=CSQ,...Format: A|B|C` header. Mapping used here:

    --everything               -> Consequence/IMPACT/SYMBOL/Gene/Feature/
                                  HGVSc/HGVSp/Existing_variation/CLIN_SIG/
                                  SIFT/PolyPhen + gnomADe_* & gnomADg_* AFs
                                  (gnomAD v4.1, 9 subpops each + pooled)
    --plugin CADD,snv,indel    -> CADD_PHRED, CADD_RAW   (all variant classes,
                                  incl. splice/indel - dbNSFP cannot cover
                                  non-coding/indels)
    --plugin dbNSFP,...,fields -> emits the REQUESTED column names verbatim:
        REVEL_score          -> contract name REVEL        (rename)
        AlphaMissense_score  -> AlphaMissense_score        (matches)
        AlphaMissense_pred   -> AlphaMissense_class        (rename)
        SpliceAI_pred_DS_AG/AL/DG/DL                       (match)
        gnomAD_LOEUF         -> contract name LOEUF        (rename)
        phyloP470way_mammal  -> contract name phyloP       (rename)

`consequence=ALL` on the dbNSFP plugin is load-bearing: by default the plugin
only annotates missense/stop-lost/stop-gained/start-lost SO terms, which would
leave splice-region and deep-intronic candidates without SpliceAI scores.

POST-ANNOTATION NAME RECONCILE (required)
-----------------------------------------
dbNSFP emits raw column names; four differ from the contract. After VEP, edit
the CSQ Format: header line in the output VCF (values unchanged - positional
rename only):

    REVEL_score->REVEL  AlphaMissense_pred->AlphaMissense_class
    gnomAD_LOEUF->LOEUF  phyloP470way_mammal->phyloP

e.g. `zcat out.vcf.gz | head -200 | grep 'ID=CSQ'`, rewrite those four tokens
in place, keep every other field name. A checksum of the before/after header
line goes into docs/decisions.md when this runs for real.
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DEFAULT_IMAGE = "ensemblorg/ensembl-vep:release_116.1"
DBNSFP_FIELDS = [
    "REVEL_score",
    "AlphaMissense_score",
    "AlphaMissense_pred",
    "SpliceAI_pred_DS_AG", "SpliceAI_pred_DS_AL",
    "SpliceAI_pred_DS_DG", "SpliceAI_pred_DS_DL",
    "gnomAD_LOEUF",
    "phyloP470way_mammal",
]
CADD_FILES = ["CADD_v1.7_GRCh38_SNV.tsv.gz",
              "CADD_v1.7_GRCh38_InDels.tsv.gz"]
DBNSFP_FILE = "dbNSFP5.3.1_grch38.gz"

# emitted-name -> contract-name header renames (see module docstring)
HEADER_RENAMES = {
    "REVEL_score": "REVEL",
    "AlphaMissense_pred": "AlphaMissense_class",
    "gnomAD_LOEUF": "LOEUF",
    "phyloP470way_mammal": "phyloP",
}


def _docker_path(p: Path) -> str:
    """Host path in the form Docker Desktop accepts inside -v (C:/x/y)."""
    return str(p.resolve()).replace("\\", "/")


def build_command(args) -> list[str]:
    vcf = Path(args.vcf).resolve()
    out = Path(args.out).resolve()
    cache = Path(args.cache_dir).resolve()
    ann = Path(args.ann_dir).resolve()
    cadd = ",".join(f"/ann/{f}" for f in CADD_FILES)
    dbnsfp = (f"dbNSFP,consequence=ALL,/ann/{DBNSFP_FILE},"
              + ",".join(DBNSFP_FIELDS))
    return [
        "docker", "run", "--rm",
        "-v", f"{_docker_path(cache)}:/opt/vep/.vep",
        "-v", f"{_docker_path(vcf.parent)}:/data",
        "-v", f"{_docker_path(ann)}:/ann",
        args.image,
        "vep", "--offline", "--cache", "--dir_cache", "/opt/vep/.vep",
        "--species", "homo_sapiens", "--assembly", args.assembly,
        "-i", f"/data/{vcf.name}",
        "-o", f"/data/{out.name}",
        "--vcf", "--compress_output", "bgzip",
        "--fork", str(args.forks),
        "--everything", "--no_stats",
        "--plugin", f"CADD,{cadd}",
        "--plugin", dbnsfp,
    ]


def check_prereqs(args) -> list[str]:
    problems = []
    if shutil.which("docker") is None:
        problems.append("docker not on PATH")
    if not Path(args.vcf).exists():
        problems.append(f"input VCF missing: {args.vcf}")
    cache = Path(args.cache_dir)
    if not (cache / "homo_sapiens").is_dir():
        problems.append(f"no unpacked VEP cache under {cache}/homo_sapiens/")
    ann = Path(args.ann_dir)
    for f in [*CADD_FILES, DBNSFP_FILE]:
        if not (ann / f).exists():
            problems.append(f"annotation file missing: {ann / f}")
        if not (ann / (f + ".tbi")).exists():
            problems.append(f"tabix index missing: {ann / (f + '.tbi')}")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VEP 116 annotation runner")
    ap.add_argument("--vcf", required=True, help="input (bgzipped) VCF")
    ap.add_argument("--out", required=True, help="output annotated VCF path")
    ap.add_argument("--cache-dir", required=True,
                    help="host dir holding the unpacked VEP cache")
    ap.add_argument("--ann-dir", default=None,
                    help="host dir with dbNSFP/CADD files (default: <cache-dir>/vep_ann)")
    ap.add_argument("--assembly", default="GRCh38")
    ap.add_argument("--forks", type=int, default=16)
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command only; do not run")
    args = ap.parse_args(argv)
    if args.ann_dir is None:
        args.ann_dir = str(Path(args.cache_dir) / "vep_ann")
    if args.forks < 1:
        print("ERROR: --forks must be >= 1", file=sys.stderr)
        return 2

    cmd = build_command(args)
    print("VEP 116 annotation command:")
    print(" ".join(cmd))
    print("\nRequired downloads (see module docstring):")
    print("  - VEP cache homo_sapiens_vep_116_GRCh38 unpacked under "
          f"{args.cache_dir}")
    print(f"  - {args.ann_dir}: {DBNSFP_FILE} + {', '.join(CADD_FILES)} (+.tbi)")
    print("\nPost-step: rename CSQ header tokens "
          + ", ".join(f"{k}->{v}" for k, v in HEADER_RENAMES.items()))
    if args.dry_run:
        return 0

    problems = check_prereqs(args)
    if problems:
        for p in problems:
            print(f"PREREQ FAIL: {p}", file=sys.stderr)
        return 2
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    print("running...", flush=True)
    return subprocess.run(cmd).returncode


if __name__ == "__main__":
    raise SystemExit(main())
