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

REQUIRED ONE-TIME DOWNLOADS (~110 GB total, plan.md section 3)
----------------------------------------------------------------
* VEP 116 GRCh38 cache: homo_sapiens_vep_116_GRCh38.tar.gz
  (Ensembl FTP; unpacked under --cache-dir so that
  <cache-dir>/homo_sapiens/116_GRCh38/ exists). Includes gnomAD v4.1
  exome+genome AFs (--af_gnomade/--af_gnomadg are inside --everything) and
  the ClinVar snapshot behind --clin_sig.
* CADD v1.7 GRCh38 whole-genome SNVs + gnomAD4 InDels + .tbi
  (https://cadd.gs.washington.edu/download - direct HTTPS links,
  non-commercial use covered)
* AlphaMissense hg38 TSV + .tbi
  (storage.googleapis.com/dm_alphamissense - public)
* SpliceAI masked snv VCF + .tbi
  (ftp.ensembl.org .../variation_plugins/ - public)
* REVEL v1.3 CSV zip (zenodo.org/record/7072866 - public); convert with
  tools/revel_to_vcf.py -> env/vep_ann/revel_grch38.vcf.gz(+tbi)
* OPTIONAL: dbNSFP 5.x VEP-ready GRCh38 + .tbi (dbnsfp.org - academic
  registration; adds REVEL/LOEUF/phyloP coverage in one file if obtained)
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
    --plugin CADD,snv,indel    -> CADD_PHRED, CADD_RAW   (all variant classes)
    --plugin AlphaMissense     -> am_pathogenicity -> AlphaMissense_score
                                  am_class -> AlphaMissense_class   (renames)
    --plugin SpliceAI,snv=...  -> SpliceAI_pred_DS_AG/AL/DG/DL  (exact match)
    --custom revel...,REVEL,.. -> REVEL_REVEL -> REVEL            (rename)
    --plugin dbNSFP,...,fields (OPTIONAL - only if file present):
        REVEL_score->REVEL  AlphaMissense_pred->AlphaMissense_class
        gnomAD_LOEUF->LOEUF  phyloP470way_mammal->phyloP
Absent plugins emit no columns - the funnel treats missing fields as
'annotator absent', a documented degraded tier (LOEUF/phyloP only ship
via dbNSFP; REVEL via custom file; pass-1 config notes this).

POST-ANNOTATION NAME RECONCILE (required)
-----------------------------------------
Plugin/custom emitted names differ from contract names; after VEP edit the
CSQ Format: header line in place (values unchanged - positional rename):

    am_pathogenicity->AlphaMissense_score  am_class->AlphaMissense_class
    REVEL_REVEL->REVEL
    (if dbNSFP present:) REVEL_score->REVEL  AlphaMissense_pred->..._class
    gnomAD_LOEUF->LOEUF  phyloP470way_mammal->phyloP

e.g. `zcat out.vcf.gz | head -200 | grep 'ID=CSQ'`, rewrite those tokens in
place, keep every other field name. A checksum of the before/after header
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
AM_FILE = "AlphaMissense_hg38.tsv.gz"
SPLICEAI_SNV = "spliceai_scores.masked.snv.grch38.vcf.gz"
REVEL_VCF = "revel_grch38.vcf.gz"

# emitted-name -> contract-name header renames (see module docstring).
# Names emitted by a plugin that is absent simply never appear in the CSQ
# header - renaming a missing token is a no-op.
HEADER_RENAMES = {
    "am_pathogenicity": "AlphaMissense_score",
    "am_class": "AlphaMissense_class",
    "REVEL_REVEL": "REVEL",
    "REVELSRC_REVEL": "REVEL",
    "REVEL_score": "REVEL",
    "AlphaMissense_pred": "AlphaMissense_class",
    "gnomAD_LOEUF": "LOEUF",
    "phyloP470way_mammal": "phyloP",
}


def _custom_annots(ann: Path) -> tuple[list[str], list[str]]:
    """--custom args for AF/ClinVar sources built for cache-free mode.
    Contract names are produced directly: the slice files carry renamed
    INFO fields so '<short>_<field>' lands as 'gnomADe_NFE_AF' etc."""
    args, missing = [], []
    specs = [
        ("gnomade_genic.vcf.gz", "gnomADe",
         "AF,AFR_AF,AMI_AF,AMR_AF,ASJ_AF,EAS_AF,FIN_AF,MID_AF,NFE_AF,"
         "OTH_AF,SAS_AF", "gnomADe_* (exome AFs)"),
        ("gnomadg_genic.vcf.gz", "gnomADg",
         "AF,AFR_AF,AMI_AF,AMR_AF,ASJ_AF,EAS_AF,FIN_AF,MID_AF,NFE_AF,"
         "OTH_AF,SAS_AF", "gnomADg_* (genome AFs)"),
        ("clinvar_sig.vcf.gz", "CLIN", "SIG", "CLIN_SIG"),
    ]
    for fname, short, fields, label in specs:
        if (ann / fname).exists() and (ann / (fname + ".tbi")).exists():
            args += ["--custom",
                     f"/ann/{fname},{short},vcf,exact,0,{fields}"]
        else:
            missing.append(label)
    return args, missing


def _ann_plugins(ann: Path) -> tuple[list[str], list[str]]:
    """Plugin/--custom args for every annotation file actually present.
    Returns (plugin_args, missing_notes) - missing files degrade to an
    'annotator absent' note instead of failing; the funnel emits with
    whatever evidence layers exist."""
    args, missing = [], []
    cadd = [ann / f for f in CADD_FILES]
    if all(p.exists() and p.with_name(p.name + ".tbi").exists()
           for p in cadd):
        args += ["--plugin", "CADD," + ",".join(f"/ann/{f}" for f in CADD_FILES)]
    else:
        missing.append("CADD (SNV+InDels+tbi)")
    if (ann / AM_FILE).exists() and (ann / (AM_FILE + ".tbi")).exists():
        args += ["--plugin", f"AlphaMissense,file=/ann/{AM_FILE}"]
    else:
        missing.append("AlphaMissense")
    if (ann / SPLICEAI_SNV).exists() \
            and (ann / (SPLICEAI_SNV + ".tbi")).exists():
        args += ["--plugin", f"SpliceAI,snv=/ann/{SPLICEAI_SNV}"]
    else:
        missing.append("SpliceAI")
    if (ann / REVEL_VCF).exists() \
            and (ann / (REVEL_VCF + ".tbi")).exists():
        # short name REVELSRC avoids the REVEL/REVEL_REVEL column-name
        # collision: VEP emits <short> (matched variant id) plus
        # <short>_<field>; REVELSRC_REVEL renames to contract 'REVEL'.
        args += ["--custom",
                 f"/ann/{REVEL_VCF},REVELSRC,vcf,exact,0,REVEL"]
    else:
        missing.append("REVEL")
    if (ann / DBNSFP_FILE).exists() \
            and (ann / (DBNSFP_FILE + ".tbi")).exists():
        args += ["--plugin",
                 f"dbNSFP,consequence=ALL,/ann/{DBNSFP_FILE},"
                 + ",".join(DBNSFP_FIELDS)]
    else:
        missing.append("dbNSFP (REVEL/LOEUF/phyloP fallback source)")
    return args, missing


def _docker_path(p: Path) -> str:
    """Host path in the form Docker Desktop accepts inside -v (C:/x/y)."""
    return str(p.resolve()).replace("\\", "/")


def build_command(args) -> list[str]:
    vcf = Path(args.vcf).resolve()
    out = Path(args.out).resolve()
    ann = Path(args.ann_dir).resolve()
    plugin_args, missing = _ann_plugins(ann)
    mounts = [f"{_docker_path(vcf.parent)}:/data",
              f"{_docker_path(ann)}:/ann"]
    if args.gtf:
        # Cache-free mode: transcript model from GTF, sequence from FASTA;
        # both must live in the same host dir (mounted at /refdir).
        if not args.fasta:
            print("ERROR: --gtf mode needs --fasta (bare-contig reference)",
                  file=sys.stderr)
            raise SystemExit(2)
        refdir = Path(args.fasta).resolve().parent
        gtfdir = Path(args.gtf).resolve().parent
        if refdir != gtfdir:
            print("ERROR: --gtf and --fasta must sit in one host dir "
                  "(mounted as /refdir)", file=sys.stderr)
            raise SystemExit(2)
        mounts.append(f"{_docker_path(refdir)}:/refdir")
        core = [
            "--gtf", f"/refdir/{Path(args.gtf).resolve().name}",
            "--fasta", f"/refdir/{Path(args.fasta).resolve().name}",
            "--hgvs", "--protein", "--symbol", "--biotype",
            "--numbers", "--canonical", "--total_length",
            "--distance", "5000",
        ]
        custom_args, cmiss = _custom_annots(ann)
        plugin_args += custom_args
        missing += cmiss
    else:
        mounts.append(
            f"{_docker_path(Path(args.cache_dir))}:/opt/vep/.vep")
        core = [
            "--offline", "--cache", "--dir_cache", "/opt/vep/.vep",
            "--species", "homo_sapiens", "--assembly", args.assembly,
            "--everything",
        ]
    if missing:
        print("annotator(s) absent - degraded tier: " + "; ".join(missing),
              file=sys.stderr)
    return [
        "docker", "run", "--rm",
        *sum((["-v", m] for m in mounts), []),
        args.image,
        "vep",
        "-i", f"/data/{vcf.name}",
        "-o", f"/data/{out.name}",
        "--vcf", "--compress_output", "bgzip",
        "--fork", str(args.forks),
        "--no_stats",
        *core, *plugin_args,
    ]


def reconcile_csq_header(vcf_path: Path) -> None:
    """Rewrite the CSQ 'Format:' token list in a bgzipped VCF header,
    mapping VEP-emitted names to contract names via HEADER_RENAMES.
    Positional rename only - data untouched. Writes in place via a
    sibling temp file; on failure the original stays put."""
    import gzip
    tmp = vcf_path.with_suffix(".reconciled.vcf.gz")
    changed = False
    with gzip.open(vcf_path, "rt", errors="replace") as fi, \
            gzip.open(tmp, "wt", newline="") as fo:
        for line in fi:
            if line.startswith("##INFO=<ID=CSQ") and "Format:" in line:
                head, _, fmt_tail = line.partition("Format:")
                fields = fmt_tail.rstrip('">\n').split("|")
                new = [HEADER_RENAMES.get(f, f) for f in fields]
                if new != fields:
                    line = head + "Format:" + "|".join(new) + '">\n'
                    changed = True
            fo.write(line)
    if changed:
        tmp.replace(vcf_path)
        print("CSQ header reconciled to contract field names")
    else:
        tmp.unlink()
        print("WARNING: no CSQ Format header found to reconcile",
              file=sys.stderr)


def check_prereqs(args) -> list[str]:
    problems = []
    if shutil.which("docker") is None:
        problems.append("docker not on PATH")
    if not Path(args.vcf).exists():
        problems.append(f"input VCF missing: {args.vcf}")
    if not args.gtf:
        cache = Path(args.cache_dir)
        if not (cache / "homo_sapiens").is_dir():
            problems.append(f"no unpacked VEP cache under "
                            f"{cache}/homo_sapiens/")
    ann = Path(args.ann_dir)
    _, missing = _ann_plugins(ann)
    if len(missing) >= 5:
        problems.append(f"no annotation sources present under {ann} - "
                        "VEP would emit bare consequences only")
    return problems


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="VEP 116 annotation runner")
    ap.add_argument("--vcf", required=True, help="input (bgzipped) VCF")
    ap.add_argument("--out", required=True, help="output annotated VCF path")
    ap.add_argument("--cache-dir", default=None,
                    help="host dir holding the unpacked VEP cache "
                         "(not needed in --gtf mode)")
    ap.add_argument("--ann-dir", default=None,
                    help="host dir with dbNSFP/CADD files (default: <cache-dir>/vep_ann)")
    ap.add_argument("--assembly", default="GRCh38")
    ap.add_argument("--gtf", default=None,
                    help="cache-free mode: transcript model from this GTF "
                         "gz (bare contigs, same dir as --fasta)")
    ap.add_argument("--fasta", default=None,
                    help="bare-contig reference fasta for --gtf mode")
    ap.add_argument("--forks", type=int, default=16)
    ap.add_argument("--image", default=DEFAULT_IMAGE)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the command only; do not run")
    args = ap.parse_args(argv)
    if not args.gtf and not args.cache_dir:
        print("ERROR: cache mode needs --cache-dir (or pass --gtf/--fasta "
              "for cache-free mode)", file=sys.stderr)
        return 2
    if args.ann_dir is None:
        args.ann_dir = str((Path(args.cache_dir) if args.cache_dir
                            else Path(args.vcf).resolve().parent)
                           / "vep_ann")
    if args.forks < 1:
        print("ERROR: --forks must be >= 1", file=sys.stderr)
        return 2

    cmd = build_command(args)
    print("VEP 116 annotation command:")
    print(" ".join(cmd))
    print("\nRequired downloads (see module docstring):")
    print("  - VEP cache homo_sapiens_vep_116_GRCh38 unpacked under "
          f"{args.cache_dir}")
    print(f"  - {args.ann_dir}: CADD + AlphaMissense + SpliceAI + REVEL "
          "(+ optional dbNSFP), each with .tbi")
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
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        reconcile_csq_header(Path(args.out))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
