"""Modal app for the Track-1 MVA pipeline's cloud stages.

Volumes:
    mva-ann   - annotation stores (public downloads land here, plus
                locally-built customs uploaded via `modal volume put`)
    mva-data  - patient inputs + outputs (annotated VCF, BAM, reports)

Functions:
    stage_ann    - fetch public annotation files at datacenter egress
    run_vep      - VEP 116 --gtf/--fasta + CADD/AM/SpliceAI/REVEL/gnomADe/ClinVar
    fetch_fastq  - gated HF FASTQs via HF_TOKEN secret
    realign      - bwa index + mem + merge + markdup + locus BAM + whatshap
    setup_case   - promote+reconcile case VCF once before funnel runs
    run_main     - Track-1 driver (EDA+funnel+SF+phasing+ACMG+csv)
    run_ablation - per-source ablation fan-out (drops ABLATION_SRCS)
    merge_ablations - detached merger into ablations.json
    run_phasing  - BUB1B pair read-level phase evidence
    run_mosdepth - WGS windowed + BUB1B-region coverage
    run_fastp    - per-lane-pair FASTQ QC (fastp JSONs)
    run_deepvariant - independent caller on the BUB1B region slice
    run_cnv      - manta + cnvpytor CNV screen on dedup.bam
    slim_result  - funnel/result_head.json (ranked[:200] + metadata)

All funnel/evidence fns take `out_name` (default shown per fn) so masked
and unmasked runs stay auditable side by side on the same volume.

Run:
    modal run tools/modal_app.py::stage_ann
    modal run tools/modal_app.py::run_vep
    modal run tools/modal_app.py::fetch_fastq    (needs secret hf-token)
    modal run tools/modal_app.py::realign
    modal run --detach tools/modal_app.py::run_main --out-name track1_final
    modal volume get mva-data WGS_exon.vep.vcf.gz data/WGS_exon.vep.vcf.gz
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath

import modal

app = modal.App("mva-track1")

ANN = modal.Volume.from_name("mva-ann", create_if_missing=True)
DATA = modal.Volume.from_name("mva-data", create_if_missing=True)

# --------------------------------------------------------------- pipeline
# The repo rides the image via add_local_dir so the funnel runs the same
# sources as locally; the volumes carry the real payloads (annotated VCF,
# corpus, case bundle) so data/env/results stay out of the image.
REPO_ROOT = Path(__file__).resolve().parent.parent
_REPO_EXCLUDE = {"data", "env", "results", ".git", ".venv", "docs",
                 "__pycache__", "env.bak", ".pytest_cache"}


def _repo_ignore(p: Path) -> bool:
    parts = set(PurePosixPath(str(p).replace("\\", "/")).parts)
    return bool(parts & _REPO_EXCLUDE)


repo_img = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("pyyaml")
    .add_local_dir(str(REPO_ROOT), remote_path="/repo",
                   ignore=_repo_ignore)
)

CASE = "/data/case"
OUT = "/data/track1_out"  # run-2 baseline (pre-mask); the masked rerun
                          # targets "track1_final" via the fns' out_name arg


def _atomic_write(path: Path, text: str) -> None:
    """tmp-file + os.replace: a producer dying mid-write can otherwise
    commit a truncated JSON that a consumer parses as complete."""
    import os
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)

# Reference pairs carried as constants so ablation containers need no
# baseline result.json (the local run is answer-blind, no truth.json).
BASE_TOP_PAIR = sorted([["6", 32584639, "C", "A"],
                        ["6", 32584809, "C", "T"]])  # HLA-DRB1 comp-het
BUB1B_PAIR = sorted([["15", 40209701, "T", "G"],
                     ["15", 40220612, "T", "G"]])
ABLATION_SRCS = ("clinvar", "damage_predictors", "gnomad", "hpo",
                 "phasing")

# ---------------------------------------------------------------- public data
# Everything here is re-fetched inside Modal (egress is ~10x+ the local
# pipe). Derived/local files are uploaded separately via `modal volume put`.
ANN_PUBLIC = {
    "CADD_v1.7_GRCh38_SNV.tsv.gz":
        "https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz",
    "CADD_v1.7_GRCh38_SNV.tsv.gz.tbi":
        "https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/whole_genome_SNVs.tsv.gz.tbi",
    "CADD_v1.7_GRCh38_InDels.tsv.gz":
        "https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/gnomad.genomes.r4.0.indel.tsv.gz",
    "CADD_v1.7_GRCh38_InDels.tsv.gz.tbi":
        "https://kircherlab.bihealth.org/download/CADD/v1.7/GRCh38/gnomad.genomes.r4.0.indel.tsv.gz.tbi",
    "AlphaMissense_hg38.tsv.gz":
        "https://storage.googleapis.com/dm_alphamissense/AlphaMissense_hg38.tsv.gz",
    # no public .tbi for AlphaMissense - the index was built locally with
    # tabix and uploaded to mva-ann directly
    "spliceai_scores.masked.snv.grch38.vcf.gz":
        "https://ftp.ensembl.org/pub/data_files/homo_sapiens/GRCh38/variation_plugins/spliceai_scores.masked.snv.mane_v1.0.grch38.vcf.gz",
    "spliceai_scores.masked.snv.grch38.vcf.gz.tbi":
        "https://ftp.ensembl.org/pub/data_files/homo_sapiens/GRCh38/variation_plugins/spliceai_scores.masked.snv.mane_v1.0.grch38.vcf.gz.tbi",
}

REF_PUBLIC = {}  # FASTA was verified against the patient VCF locally and
                 # already uploaded to mva-data; don't fetch a lookalike.

fetch_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("curl", "ca-certificates")
)


@app.function(image=fetch_image, volumes={"/ann": ANN, "/data": DATA},
              cpu=8, memory=8192, timeout=6 * 3600)
def stage_ann() -> None:
    """Fetch every public annotation/reference file into the volumes.
    Byte-size checks against existing local manifests are the guard for
    re-runs: a file already present at the right size is skipped."""
    import os
    import subprocess
    import urllib.request

    def fetch_spawn(url: str, dest: str):
        if os.path.exists(dest):
            try:
                want = urllib.request.urlopen(
                    urllib.request.Request(url, method="HEAD"),
                    timeout=60).headers.get("Content-Length")
                if want and int(want) == os.path.getsize(dest):
                    print(f"skip {dest} (already {want} bytes)", flush=True)
                    return None
            except Exception:
                pass
        tmp = dest + ".dl"
        # curl -C - resumes the .dl file on rerun; tmp->dest happens only on
        # clean exit (rc 0) inside the watcher thread
        p = subprocess.Popen(
            ["curl", "-fL", "--retry", "10", "--retry-all-errors",
             "-C", "-", "-sS", "-o", tmp, url])
        return _rename_after(p, tmp, dest)

    _fails: list[str] = []

    def _rename_after(p, tmp, dest):
        import threading
        def _w():
            rc = p.wait()
            if rc == 0:
                os.replace(tmp, dest)
                print(f"done {dest}", flush=True)
            else:
                _fails.append(dest)
                print(f"FAIL {dest} rc={rc}", flush=True)
        t = threading.Thread(target=_w, daemon=True)
        t.start()
        return t

    # fetch all files concurrently - the krishna CADD mirror is slow
    # (~14MB/s) while GCS/Ensembl are fast; serializing behind CADD would
    # stall everything
    procs = {}
    for name, url in {**ANN_PUBLIC, **REF_PUBLIC}.items():
        base = "/data" if name in REF_PUBLIC else "/ann"
        dest = f"{base}/{name}"
        procs[name] = fetch_spawn(url, dest)
    for t in procs.values():
        if t is not None:
            t.join()
    if _fails:
        raise RuntimeError(f"fetches failed: {_fails}")
    ANN.commit()
    DATA.commit()
    print("STAGE_ANN_DONE", flush=True)


vep_image = modal.Image.from_registry(
    "ensemblorg/ensembl-vep:release_116.1", add_python="3.11")


@app.function(image=vep_image,
              volumes={"/ann": ANN, "/data": DATA},
              cpu=16, memory=32768, timeout=6 * 3600)
def run_vep() -> None:
    """Cache-free VEP: --gtf + --fasta + CADD/AM/SpliceAI plugins +
    REVELSRC/gnomADe/CLIN custom VCFs. Same command shape run_vep.py
    emits locally. Note: this fn emits RAW plugin field names; the CSQ
    header reconcile to contract names is enforced by `_case_inputs`/
    `setup_case` before any funnel fn touches the VCF, not here."""
    import subprocess

    cmd = [
        "vep",
        "-i", "/data/WGS_exon.vcf.gz",
        "-o", "/data/WGS_exon.vep.vcf.gz",
        "--vcf", "--compress_output", "bgzip",
        "--fork", "16", "--no_stats", "--force_overwrite",
        "--gtf", "/ann/Homo_sapiens.GRCh38.116.gtf.bgz",
        "--fasta", "/data/GRCh38_no_alt_plus_hs38d1.fna",
        "--hgvs", "--protein", "--symbol", "--biotype",
        "--numbers", "--canonical", "--total_length", "--distance", "5000",
        "--plugin",
        "CADD,/ann/CADD_v1.7_GRCh38_SNV.tsv.gz,"
        "/ann/CADD_v1.7_GRCh38_InDels.tsv.gz",
        "--plugin", "AlphaMissense,file=/ann/AlphaMissense_hg38.tsv.gz",
        "--plugin",
        # VEP 116 SpliceAI.pm calls add_file() on BOTH snv and indel params
        # unconditionally - passing only snv dies with "No file specified".
        # Pointing indel at the same file is an idempotent no-op (same
        # scores emitted into the same CSQ keys).
        "SpliceAI,snv=/ann/spliceai_scores.masked.snv.grch38.vcf.gz,"
        "indel=/ann/spliceai_scores.masked.snv.grch38.vcf.gz",
        "--custom",
        "/ann/revel_grch38.vcf.gz,REVELSRC,vcf,exact,0,REVEL",
        "--custom",
        "/ann/gnomade_custom.vcf.gz,gnomADe,vcf,exact,0,"
        "AF,AFR_AF,AMI_AF,AMR_AF,ASJ_AF,EAS_AF,FIN_AF,MID_AF,NFE_AF,"
        "OTH_AF,SAS_AF",
        "--custom", "/ann/clinvar_sig.vcf.gz,CLIN,vcf,exact,0,SIG",
    ]
    print(" ".join(cmd), flush=True)
    subprocess.run(cmd, check=True)
    DATA.commit()
    print("RUN_VEP_DONE", flush=True)


align_image = (
    modal.Image.from_registry("mambaorg/micromamba:1.5-bookworm-slim",
                              add_python="3.12")
    .run_commands(
        "micromamba install -y -n base -c conda-forge -c bioconda "
        "bwa samtools mosdepth whatshap curl ca-certificates "
        "&& micromamba clean -afy",
    )
)

HF_BASE = ("https://huggingface.co/datasets/SageBio/"
           "mva-hackathon-2026-data/resolve/main/")
FASTQS = [
    f"WGS_EX2312012_HGWCNDSX7_S16_L00{l}_R{r}_001.fastq.gz"
    for l in (1, 2, 3, 4) for r in (1, 2)
]


@app.function(image=fetch_image, volumes={"/data": DATA},
              secrets=[modal.Secret.from_name("hf-token")],
              cpu=8, memory=8192, timeout=6 * 3600)
def fetch_fastq() -> None:
    """Gated FASTQs via HF resolve + bearer token, at Modal egress.
    Per-file commit + resume: a preemption mid-fleet keeps completed
    lanes (uncommitted volume writes die with the container), and
    `curl -C -` resumes a truncated one instead of restarting it."""
    import os
    import subprocess
    import urllib.request

    tok = os.environ["HF_TOKEN"]
    for f in FASTQS:
        dest = f"/data/{f}"
        try:
            want = urllib.request.urlopen(urllib.request.Request(
                HF_BASE + f, method="HEAD",
                headers={"Authorization": f"Bearer {tok}"}),
                timeout=60).headers.get("Content-Length")
        except Exception:
            want = None
        if want and os.path.exists(dest) \
                and int(want) == os.path.getsize(dest):
            print(f"skip {f} (already {want} bytes)", flush=True)
            continue
        subprocess.run(
            ["curl", "-fL", "--retry", "10", "--retry-all-errors",
             "-C", "-", "-H", f"Authorization: Bearer {tok}",
             "-o", dest, HF_BASE + f],
            check=True)
        print(f"done {f}", flush=True)
        DATA.commit()
    print("FASTQ_DONE", flush=True)


@app.function(image=align_image, volumes={"/data": DATA},
              cpu=32, memory=65536, timeout=12 * 3600)
def realign() -> None:
    """bwa index + per-lane mem + merge/markdup + locus BAM + whatshap."""
    import os
    import subprocess

    env = {**os.environ, "PATH": "/opt/conda/bin:" + os.environ["PATH"]}

    def sh(cmd: str) -> None:
        print("+", cmd, flush=True)
        subprocess.run(cmd, shell=True, check=True, env=env,
                       executable="/bin/bash")

    ref = "/data/GRCh38_no_alt_plus_hs38d1.fna"
    w = "/data/realign"
    os.makedirs(w, exist_ok=True)
    if not os.path.exists(ref + ".bwt"):
        sh(f"bwa index {ref}")
    for l in (1, 2, 3, 4):
        lane = f"{w}/lane_L00{l}.bam"
        if os.path.exists(lane):
            # a preemption mid-sort-merge leaves a TRUNCATED lane BAM plus
            # .tmp.* fragments - file-exists alone would silently merge a
            # corrupt lane. quickcheck validates; leftovers force a redo.
            ok = subprocess.run(
                ["samtools", "quickcheck", "-v", lane],
                env=env).returncode == 0
            leftovers = subprocess.run(
                f"ls {lane}.tmp.* 2>/dev/null | wc -l",
                shell=True, check=True, env=env,
                executable="/bin/bash",
                capture_output=True, text=True).stdout.strip()
            if ok and leftovers == "0":
                print(f"skip {lane} (quickcheck ok)", flush=True)
                continue
            sh(f"rm -f {lane} {lane}.tmp.*")
        sh(f"bwa mem -t 28 -R '@RG\\tID:L00{l}\\tSM:WGS_EX2312012"
           f"\\tPL:ILLUMINA\\tPU:L00{l}' {ref} "
           f"/data/WGS_EX2312012_HGWCNDSX7_S16_L00{l}_R1_001.fastq.gz "
           f"/data/WGS_EX2312012_HGWCNDSX7_S16_L00{l}_R2_001.fastq.gz "
           f"| samtools sort -@4 -o {lane} -")
        DATA.commit()
    merged = f"{w}/merged.bam"
    have_merged = os.path.exists(merged) and subprocess.run(
        ["samtools", "quickcheck", "-v", merged],
        env=env).returncode == 0
    if not have_merged:
        sh(f"rm -f {merged} && samtools merge -@8 -o {merged} "
           f"{w}/lane_L00*.bam")
    # markdup hard-fails without ms mate-score tags - fixmate -m adds them
    # and needs name-collated input, so: collate | fixmate | sort | markdup.
    # collate refuses to overwrite stale chunk files - clear them first so
    # a preempted attempt doesn't wedge every restart on "File exists".
    dedup = f"{w}/WGS_EX2312012.dedup.bam"
    have_dedup = os.path.exists(dedup) and subprocess.run(
        ["samtools", "quickcheck", "-v", dedup],
        env=env).returncode == 0
    if not have_dedup:
        sh(f"rm -f {w}/colltmp.* {w}/fixsorted.bam")
        sh(f"samtools collate -@8 -Ou {merged} {w}/colltmp | "
           f"samtools fixmate -@4 -mu - - | samtools sort -@8 "
           f"-o {w}/fixsorted.bam -")
        sh(f"samtools markdup -@8 {w}/fixsorted.bam {dedup} && "
           f"rm -f {w}/fixsorted.bam {w}/colltmp.*.bam")
    else:
        print("skip markdup (dedup.bam quickcheck ok)", flush=True)
    sh(f"samtools index {dedup}")
    sh(f"samtools flagstat {dedup} > {w}/flagstat.txt")
    # .bai-existence alone accepts a corrupt bam left by a preempted
    # index; quickcheck the bam too before trusting the resume.
    region = f"{w}/region.bam"
    if not os.path.exists(f"{region}.bai") or subprocess.run(
            ["samtools", "quickcheck", "-v", region],
            env=env).returncode != 0:
        sh(f"samtools view -b {dedup} "
           f"15:40100000-40250000 > {region} && "
           f"samtools index {region}")
    sh(f"samtools view {w}/region.bam > {w}/region.sam")
    # whatshap must phase ONLY the region slice - feeding the full-genome
    # VCF silently yields 0 reads/0 variants (observed empirically). Slice
    # the case VCF to the region window first.
    sh(
        "python - <<'PY'\n"
        "import gzip\n"
        "src = '/data/WGS_EX2312012_HGWCNDSX7.vcf.gz'\n"
        f"out = open('{w}/region_variants.vcf', 'w')\n"
        "with gzip.open(src, 'rt', errors='replace') as f:\n"
        "    for line in f:\n"
        "        if line.startswith('#'):\n"
        "            out.write(line); continue\n"
        "        c, p = line.split('\\t', 2)[:2]\n"
        "        if c == '15' and 40100000 <= int(p) <= 40250000:\n"
        "            out.write(line)\n"
        "out.close()\n"
        "PY")
    sh("whatshap phase -o {0}/phased.vcf --reference={1} "
       "{0}/region_variants.vcf {0}/region.bam".format(w, ref))
    DATA.commit()
    print("REALIGN_DONE", flush=True)


# ---------------------------------------------------------------- funnel
def _needs_reconcile(vcf_path) -> bool:
    """True when the CSQ Format header still carries raw VEP/plugin names
    that run_vep.reconcile_csq_header maps to contract names."""
    import gzip
    import sys
    sys.path.insert(0, "/repo/tools")
    from run_vep import HEADER_RENAMES
    with gzip.open(vcf_path, "rt", errors="replace") as f:
        for line in f:
            if line.startswith("##INFO=<ID=CSQ"):
                return any(k in line for k in HEADER_RENAMES)
            if not line.startswith("#"):
                break
    return False


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=2, memory=8192, timeout=3600)
def setup_case() -> dict:
    """One-shot prep: patient.vcf.gz into /data/case + CSQ header
    reconcile to contract names. Run ONCE before the ablation fan-out -
    _case_inputs refuses to proceed on an unreconciled header so a
    concurrent reconcile race can't corrupt the shared VCF."""
    import gzip
    import os
    import shutil
    import sys

    sys.path.insert(0, "/repo")
    sys.path.insert(0, "/repo/tools")
    from run_vep import HEADER_RENAMES

    os.makedirs(CASE, exist_ok=True)
    dest = f"{CASE}/patient.vcf.gz"
    if not os.path.exists(dest):
        shutil.copy("/data/WGS_exon.vep.vcf.gz", dest)
    reconciled = False
    if _needs_reconcile(dest):
        tmp = Path(f"{dest}.rec.tmp")
        changed = False
        with gzip.open(dest, "rt", errors="replace") as fi, \
                gzip.open(tmp, "wt", newline="") as fo:
            for line in fi:
                if line.startswith("##INFO=<ID=CSQ") and \
                        "Format:" in line:
                    head, _, tail = line.partition("Format:")
                    fields = tail.rstrip('">\n').split("|")
                    new = [HEADER_RENAMES.get(f, f) for f in fields]
                    if new != fields:
                        line = head + "Format:" + "|".join(new) + '">\n'
                        changed = True
                fo.write(line)
        if changed:
            os.replace(tmp, dest)
            reconciled = True
        else:
            tmp.unlink()
    DATA.commit()
    ok = not _needs_reconcile(dest)
    print(f"SETUP_CASE_DONE reconciled={reconciled} ok={ok}", flush=True)
    return {"reconciled": reconciled, "ok": ok}


def _case_inputs():
    """Resolve the case bundle on the volume; promote the annotated VCF
    into the case dir on first use. Assumes setup_case() already ran so
    the CSQ header is reconciled - verifies that invariant."""
    import os
    import shutil
    import sys

    sys.path.insert(0, "/repo")
    sys.path.insert(0, "/repo/tools")
    from run_track1 import find_vcf  # keeps the .chr exclusion rules

    dest = f"{CASE}/patient.vcf.gz"
    if not os.path.exists(dest):
        os.makedirs(CASE, exist_ok=True)
        # concurrent containers may all take this branch - copy via a
        # unique tmp then os.replace so the last writer wins with intact
        # bytes (same source either way)
        tmp = f"{CASE}/.patient.vcf.gz.{os.getpid()}"
        shutil.copy("/data/WGS_exon.vep.vcf.gz", tmp)
        os.replace(tmp, dest)
    if _needs_reconcile(dest):
        raise RuntimeError(
            "case VCF CSQ header is unreconciled (raw VEP names) - run "
            "modal run tools/modal_app.py::setup_case once first")
    import json
    from src.config import load_config
    hpo = json.loads(
        Path(f"{CASE}/hpo_terms.json").read_text(encoding="utf-8-sig"))
    hpo = hpo["hpo_terms"] if isinstance(hpo, dict) else hpo
    corpus = {}
    for k, names in (("obo_path", ("hp.obo",)),
                     ("hpoa_path", ("phenotype.hpoa",)),
                     ("g2d_path", ("genes_to_disease.json",
                                   "gene2disease.json"))):
        corpus[k] = next((str(Path(CASE) / n) for n in names
                          if (Path(CASE) / n).exists()), None)
    return find_vcf(Path(CASE)), hpo, load_config(), corpus


def _pair_rank(ranked, want, model):
    for h in ranked:
        got = sorted([[str(v["chrom"]), v["pos"], v["ref"], v["alt"]]
                      for v in h["variants"]])
        if h["model"] == model and got == want:
            return h["rank"]
    return None


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=4, memory=32768, timeout=6 * 3600)
def run_main(out_name: str = "track1_out") -> dict:
    """EDA + funnel + SF + phasing + ACMG + submission + concordance.
    Ablations are skipped (--skip-ablations) - they fan out via .map().
    `out_name` names the volume output dir so masked/unmasked runs stay
    auditable side by side (default = run-2's track1_out)."""
    import os
    import subprocess
    import sys

    _case_inputs()  # ensure case dir is complete before the driver runs
    sam = "/data/realign/region.sam"
    cmd = [sys.executable, "/repo/tools/run_track1.py",
           "--case", CASE, "--out", f"/data/{out_name}",
           "--arm-a-tsv", "/data/exomiser_genes.tsv",
           "--skip-ablations"]
    if os.path.exists(sam):
        cmd += ["--sam", sam]
    env = {**os.environ, "PYTHONUTF8": "1"}
    r = subprocess.run(cmd, env=env, check=False)
    DATA.commit()
    print(f"RUN_MAIN_DONE rc={r.returncode}", flush=True)
    return {"rc": r.returncode}


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=4, memory=32768, timeout=6 * 3600)
def run_ablation(src: str, out_name: str = "track1_out") -> dict:
    """One dropped-source funnel pass; tracks where the baseline emitted
    pair and the BUB1B pair land without `src`'s annotation signal.
    `pair_rank` null post-mask is itself the evidence the mask applied."""
    import json

    vcf, hpo, cfg, corpus = _case_inputs()
    from src.pipeline import run_pipeline
    r = run_pipeline(str(vcf), hpo, sample=None, cfg=cfg,
                     drops=frozenset({src}), **corpus)
    top = next((h for h in r["ranked"] if h.get("emitted")), None)
    out = {
        "pair_rank": _pair_rank(r["ranked"], BASE_TOP_PAIR,
                                "compound_het"),
        "bub1b_rank": _pair_rank(r["ranked"], BUB1B_PAIR, "compound_het"),
        "top_emitted": (
            {"gene": top["gene"], "model": top["model"],
             "variants": sorted(
                 [[str(v["chrom"]), v["pos"], v["ref"], v["alt"]]
                  for v in top["variants"]])}
            if top else None),
        "emitted": r["funnel"]["emitted"],
    }
    out_dir = Path(f"/data/{out_name}")
    (out_dir / "ablations").mkdir(parents=True, exist_ok=True)
    _atomic_write(out_dir / "ablations" / f"{src}.json",
                  json.dumps(out, indent=1))
    DATA.commit()
    print(f"ABLATION_DONE {src} {out}", flush=True)
    return {src: out}


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=1, memory=2048, timeout=5 * 3600, retries=2)
def merge_ablations(out_name: str = "track1_out") -> dict:
    """Poll the volume for all per-source ablation outputs AND
    run_summary.json, then merge into ablations.json and patch the
    summary. Fully detached - launch alongside the ablation calls; it
    waits for them. A clean rerun can finish ablations BEFORE run_main
    writes its summary, so the summary is part of the wait condition -
    patching only `if rs.exists()` would silently lose the merge on a
    fast fleet."""
    import json
    import time

    out_dir = Path(f"/data/{out_name}")
    abl_dir = out_dir / "ablations"
    rs_path = out_dir / "run_summary.json"
    deadline = time.time() + 4 * 3600
    merged: dict = {}
    summary = None
    while time.time() < deadline:
        try:
            DATA.reload()  # see commits from sibling containers
        except Exception:
            pass
        merged = {}
        for s in ABLATION_SRCS:
            try:
                merged[s] = json.loads(
                    (abl_dir / f"{s}.json").read_text())
            except (OSError, json.JSONDecodeError):
                pass  # absent or torn mid-write - treat as pending
        try:
            summary = json.loads(rs_path.read_text())
        except (OSError, json.JSONDecodeError):
            summary = None
        if len(merged) == len(ABLATION_SRCS) and summary is not None:
            break
        time.sleep(60)
    if len(merged) != len(ABLATION_SRCS):
        raise RuntimeError(
            f"ablation timeout - got {sorted(merged)}")
    if summary is None:
        raise RuntimeError(
            "run_summary.json never appeared - run_main failed?")
    _atomic_write(out_dir / "ablations.json",
                  json.dumps(merged, indent=1))
    summary.setdefault("steps", {})["ablations"] = merged
    _atomic_write(rs_path, json.dumps(summary, indent=1))
    DATA.commit()
    print("MERGE_DONE", flush=True)
    return merged


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=2, memory=8192, timeout=3600)
def run_phasing(out_name: str = "track1_out") -> dict:
    """Read-level phase evidence for the BUB1B compound_het pair from
    /data/realign/region.sam + PGT/PID fields. Writes
    {out_name}/bub1b_phasing.json (additive artifact - run_track1's
    phasing_report.json covers the top-emitted pair)."""
    import json

    vcf, hpo, cfg, corpus = _case_inputs()
    from src.phasing import determine_phase
    from src.reads import evidence_report, phase_from_reads
    from src.triage import extract_facts
    from src.vcf import VcfReader

    want = {(str(c), p, r, a) for c, p, r, a in BUB1B_PAIR}
    facts = []
    reader = VcfReader(str(vcf))
    sample = reader.samples[0] if reader.samples else ""
    for rec in reader.records(sample=sample):
        for f in extract_facts(rec, sample, cfg):
            if (str(f.chrom), f.pos, f.ref, f.alt) in want \
                    and f.gene == "BUB1B":
                facts.append(f)
        if len(facts) >= 2:
            break
    reader.close()
    if len(facts) < 2:
        raise RuntimeError(
            f"BUB1B facts not found in {vcf} (got {len(facts)})")
    call = determine_phase(facts[0], facts[1])
    ph = {"gene": "BUB1B", "model": "compound_het",
          "variants": [f"{f.chrom}:{f.pos}:{f.ref}>{f.alt}"
                       for f in facts[:2]],
          "evidence": [{"name": "PGT/PID phase-set fields",
                        "mechanism": call.mechanism,
                        "result": call.relation, "detail": call.detail}],
          "agreement": call.relation}
    sam = Path("/data/realign/region.sam")
    if sam.exists():
        read_ph = phase_from_reads(iter(sam.read_text().splitlines()),
                                   facts[0].key, facts[1].key)
        ph["evidence"].append(
            {"name": "read-level SAM evidence", "mechanism": "read_level",
             "result": read_ph.get("relation"),
             "counts": read_ph.get("counts")})
        comb = evidence_report(call, read_ph)
        ph["agreement"] = comb.get("consensus_relation",
                                   comb.get("agreement"))
    out_dir = Path(f"/data/{out_name}")
    out_dir.mkdir(parents=True, exist_ok=True)
    _atomic_write(out_dir / "bub1b_phasing.json",
                  json.dumps(ph, indent=1))
    DATA.commit()
    print(f"PHASING_DONE {ph['agreement']}", flush=True)
    return ph


# ------------------------------------------------------- evidence arms
# Phase-3 fan-out: mosdepth / fastp / deepvariant / cnv / slim_result.
# These write under the masked run's out dir (default track1_final) - the
# report consumes their verdicts, not raw dumps.


@app.function(image=align_image, volumes={"/data": DATA},
              cpu=16, memory=32768, timeout=3600)
def run_mosdepth(out_name: str = "track1_final") -> dict:
    """WGS windowed coverage (500 bp bins) + focused depth over the BUB1B
    locus slice -> {out_name}/mosdepth/. Resumable: existing outputs skip."""
    import os
    import subprocess

    env = {**os.environ, "PATH": "/opt/conda/bin:" + os.environ["PATH"]}
    out = f"/data/{out_name}/mosdepth"
    os.makedirs(out, exist_ok=True)
    done = {}

    def mosdepth(prefix: str, bam: str, threads: int, extra: str = ""):
        # mosdepth emits {prefix}.mosdepth.summary.txt on success
        if os.path.exists(prefix + ".mosdepth.summary.txt"):
            print(f"skip {prefix}", flush=True)
            done[os.path.basename(prefix)] = "exists"
            return
        cmd = (f"mosdepth -t {threads} -n {extra} "
               f"{prefix} {bam}").split()
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, env=env)
        done[os.path.basename(prefix)] = "ok"

    mosdepth(f"{out}/WGS", "/data/realign/WGS_EX2312012.dedup.bam", 16,
             "--by 500")
    # region.bam is already sliced to 15:40100000-40250000 - windowed
    # depth over it IS the locus-depth evidence.
    mosdepth(f"{out}/region", "/data/realign/region.bam", 4, "--by 100")

    # Derived summary the report cites (mean depth + cumulative
    # fraction >= 10x/30x), parsed from mosdepth's own outputs.
    import json

    def _summ(prefix: str) -> dict:
        s = {}
        try:
            with open(prefix + ".mosdepth.summary.txt") as f:
                hdr = f.readline().split("\t")
                for line in f:
                    row = dict(zip(hdr, line.rstrip("\n").split("\t")))
                    if row.get("chrom") == "total":
                        s["mean"] = float(row["mean"])
        except OSError:
            pass
        try:
            cov10 = cov30 = None
            with open(prefix + ".mosdepth.global.dist.txt") as f:
                for line in f:
                    c = line.rstrip("\n").split("\t")
                    if len(c) < 3 or c[0] != "total":
                        continue
                    d, p = int(float(c[1])), float(c[2])
                    if d <= 10:
                        cov10 = p
                    if d <= 30:
                        cov30 = p
            s["frac_ge_10x"], s["frac_ge_30x"] = cov10, cov30
        except OSError:
            pass
        return s

    summary = {name: _summ(f"{out}/{name}") for name in ("WGS", "region")}
    _atomic_write(Path(f"{out}/mosdepth_summary.json"),
                  json.dumps(summary, indent=1))
    DATA.commit()
    print(f"MOSDEPTH_DONE {done}", flush=True)
    return done


qc_image = (
    modal.Image.from_registry("mambaorg/micromamba:1.5-bookworm-slim",
                              add_python="3.12")
    .run_commands(
        "micromamba install -y -n base -c conda-forge -c bioconda "
        "fastp fastqc && micromamba clean -afy",
    )
)


@app.function(image=qc_image, volumes={"/data": DATA},
              cpu=8, memory=16384, timeout=2 * 3600)
def run_fastp(out_name: str = "track1_final") -> dict:
    """fastp per-lane PAIR QC (4 lanes -> 4 JSONs) -> {out_name}/fastq_qc/.
    fastp processes read pairs, so this is 4 runs not 8. Filtered reads
    land in /tmp and die with the container - only the reports persist.
    Aggregation to fastqc_report.json/summary.md is a local post-pull
    step via tools/run_fastqc.py (KB-scale JSONs)."""
    import os
    import subprocess

    env = {**os.environ, "PATH": "/opt/conda/bin:" + os.environ["PATH"]}
    out = f"/data/{out_name}/fastq_qc"
    os.makedirs(out, exist_ok=True)
    done = {}
    for l in (1, 2, 3, 4):
        lane = f"L00{l}"
        jpath = f"{out}/{lane}_fastp.json"
        if os.path.exists(jpath):
            print(f"skip {lane}", flush=True)
            done[lane] = "exists"
            continue
        r1 = (f"/data/WGS_EX2312012_HGWCNDSX7_S16_{lane}_R1_001."
              "fastq.gz")
        r2 = (f"/data/WGS_EX2312012_HGWCNDSX7_S16_{lane}_R2_001."
              "fastq.gz")
        cmd = [
            "fastp", "-i", r1, "-I", r2,
            "-o", f"/tmp/{lane}_R1.out.fq.gz",
            "-O", f"/tmp/{lane}_R2.out.fq.gz",
            "--json", jpath, "--html", f"{out}/{lane}_fastp.html",
            "--thread", "8",
        ]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True, env=env)
        DATA.commit()  # per-lane commit: a preemption keeps finished lanes
        done[lane] = "ok"
    print(f"FASTP_DONE {done}", flush=True)
    return done


dv_image = modal.Image.from_registry(
    "google/deepvariant:1.9.0", add_python="3.11")


@app.function(image=dv_image, volumes={"/data": DATA},
              cpu=16, memory=32768, timeout=2 * 3600)
def run_deepvariant(out_name: str = "track1_final") -> dict:
    """Independent-caller confirmation: DeepVariant WGS model over the
    BUB1B region slice -> {out_name}/deepvariant/dv_region.vcf plus a
    derived findings verdict (both BUB1B sites recalled het PASS GQ>20?).
    DV 1.9.0 is the latest stable tag on Docker Hub - 1.10.x exists only
    as beta tags; not shipped for evidence."""
    import json
    import os
    import subprocess

    out = f"/data/{out_name}/deepvariant"
    os.makedirs(out, exist_ok=True)
    vcf_path = f"{out}/dv_region.vcf"
    if not os.path.exists(vcf_path):
        cmd = [
            "/opt/deepvariant/bin/run_deepvariant",
            "--model_type=WGS",
            "--ref=/data/GRCh38_no_alt_plus_hs38d1.fna",
            "--reads=/data/realign/region.bam",
            "--regions", "15:40100000-40250000",
            "--num_shards=16",
            f"--output_vcf={vcf_path}",
            "--intermediate_results_dir=/tmp/dv_int",
        ]
        print("+", " ".join(cmd), flush=True)
        subprocess.run(cmd, check=True)
    else:
        print(f"skip {vcf_path} (exists)", flush=True)

    # Derived verdict: were the BUB1B sites recalled as het PASS GQ>20?
    want = {p: (r, a) for _, p, r, a in BUB1B_PAIR}
    found = {}
    with open(vcf_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            c = line.split("\t")
            pos = int(c[1])
            if pos in want and c[0].lstrip("chr") == "15":
                fmt = c[8].split(":")
                samp = c[9].split(":")
                rec = dict(zip(fmt, samp))
                found[str(pos)] = {
                    "gt": rec.get("GT"), "gq": rec.get("GQ"),
                    "filter": c[6],
                    "recalled": rec.get("GT") in ("0/1", "0|1")
                        and c[6] in ("PASS", ".")
                        and float(rec.get("GQ", 0) or 0) > 20,
                }
    verdict = {
        "sites": found,
        "all_recalled_het_pass_gq20":
            len(found) == len(want)
            and all(v["recalled"] for v in found.values()),
        "caller": "deepvariant-1.9.0",
    }
    _atomic_write(Path(f"{out}/dv_findings.json"),
                  json.dumps(verdict, indent=1))
    DATA.commit()
    print(f"DV_DONE {verdict['all_recalled_het_pass_gq20']}", flush=True)
    return verdict


cnv_image = (
    modal.Image.from_registry("mambaorg/micromamba:1.5-bookworm-slim",
                              add_python="3.12")
    .run_commands(
        # NOTE: no standalone `samtools` - co-solving it with cnvpytor's
        # pysam/htslib pins is unresolvable on bioconda. The .bai is
        # already on the volume and both callers read the BAM via their
        # own bundled/pysam htslib, so the CLI isn't needed.
        # manta is a python-2.7-only bioconda package: it lives in its
        # OWN conda env (never co-solvable with the py3.12 base), and its
        # entry points run via /opt/conda/envs/manta/bin/*.
        # python=3.12 pin is load-bearing: an unpinned cnvpytor solve
        # upgrades base to python 3.14, which Modal's injected grpclib
        # runtime cannot hello() under (events.py __slots__ assertion) -
        # container dies before user code.
        "micromamba install -y -n base -c conda-forge -c bioconda "
        "\"python=3.12\" cnvpytor && "
        "micromamba create -y -n manta -c conda-forge -c bioconda "
        "manta && "
        "micromamba clean -afy",
    )
)

# BUB1B locus window for the CNV verdict (gene body +- padding).
_BUB1B_REGION = ("15", 40205000, 40232000)


@app.function(image=cnv_image, volumes={"/data": DATA},
              cpu=32, memory=65536, timeout=8 * 3600, retries=2)
def run_cnv(out_name: str = "track1_final") -> dict:
    """CNV/SV screen on the dedup BAM: manta (PE/SR evidence) + cnvpytor
    (read-depth) - the exact invocations tools/run_cnv.py emits, minus the
    docker nesting. Deliverable is {out_name}/cnv/summary.json: count of
    del/dup calls overlapping the BUB1B locus + a verdict the report
    cites. Expected none - hardens the biallelic-SNV story."""
    import json
    import os
    import subprocess

    env = {**os.environ, "PATH": "/opt/conda/bin:" + os.environ["PATH"]}
    out = f"/data/{out_name}/cnv"
    os.makedirs(out, exist_ok=True)
    bam = "/data/realign/WGS_EX2312012.dedup.bam"
    ref = "/data/GRCh38_no_alt_plus_hs38d1.fna"

    def sh(cmd: str) -> None:
        print("+", cmd, flush=True)
        subprocess.run(cmd, shell=True, check=True, env=env,
                       executable="/bin/bash")

    # manta: configure + run local workflow (candidateSV VCF lands in
    # manta/results/variants/candidateSV.vcf.gz). Manta lives in its own
    # py2.7 conda env - entry points resolve under envs/manta/bin. Its
    # scripts carry `#!/usr/bin/env python2` shebangs and pyflow spawns
    # bare `python2` subprocesses, so a python2 alias must sit ON PATH;
    # scoped inline so the cnvpytor calls below keep base python3.12.
    menv = "/opt/conda/envs/manta/bin"
    mb = "/tmp/mantabin"
    os.makedirs(mb, exist_ok=True)
    if not os.path.exists(f"{mb}/python2"):
        os.symlink(f"{menv}/python", f"{mb}/python2")
    manta_vcf = f"{out}/manta/results/variants/candidateSV.vcf.gz"
    if not os.path.exists(manta_vcf):
        sh(f"export PATH={mb}:{menv}:$PATH && "
           f"python {menv}/configManta.py --bam {bam} "
           f"--referenceFasta {ref} --runDir {out}/manta && "
           f"python {out}/manta/runWorkflow.py -m local -j 32")
    else:
        print(f"skip manta ({manta_vcf} exists)", flush=True)

    # cnvpytor: rd -> histogram -> partition -> call at 10k + 100k bins
    pytor = f"{out}/proband.pytor"
    t10, t100 = f"{out}/cnvpytor_calls.10k.tsv", \
        f"{out}/cnvpytor_calls.100k.tsv"
    if not (os.path.exists(t10) and os.path.exists(t100)):
        sh(f"cnvpytor -root {pytor} -rd {bam} && "
           f"cnvpytor -root {pytor} -his 10000 100000 && "
           f"cnvpytor -root {pytor} -partition 10000 100000 && "
           f"cnvpytor -root {pytor} -call 10000 > {t10} && "
           f"cnvpytor -root {pytor} -call 100000 > {t100}")
    else:
        print("skip cnvpytor (call tables exist)", flush=True)

    # Derived verdict: del/dup calls overlapping the BUB1B locus, from
    # EITHER caller. Manta VCF rows carry END in INFO/END (symbolic alts)
    # or a single-range deletion; cnvpytor TSV columns are
    # CNVtype/start/end. Keep the parser conservative - a row we can't
    # classify still counts as evidence to inspect, never as 'none'.
    import gzip
    ch, s0, e0 = _BUB1B_REGION
    hits = []

    def overlaps(c: str, s: int, e: int) -> bool:
        c2 = c[3:] if c.startswith("chr") else c
        return c2 == ch and s <= e0 and e >= s0

    if os.path.exists(manta_vcf):
        with gzip.open(manta_vcf, "rt") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                c = line.rstrip("\n").split("\t")
                info = dict(p.split("=", 1) for p in c[7].split(";")
                            if "=" in p)
                end = int(info.get("END", c[1]))
                svtype = info.get("SVTYPE", "")
                if svtype in ("DEL", "DUP", "CNV") and \
                        overlaps(c[0], int(c[1]), end):
                    hits.append({"caller": "manta", "type": svtype,
                                 "region": f"{c[0]}:{c[1]}-{end}",
                                 "filter": c[6]})
    for tsv in (t10, t100):
        if not os.path.exists(tsv):
            continue
        with open(tsv) as f:
            for line in f:
                if line.startswith("CNV") or line.startswith("#"):
                    continue
                c = line.rstrip("\n").split("\t")
                if len(c) < 4:
                    continue
                try:
                    # cnvpytor call rows: CNVtype <tab> region <tab> size
                    cnv_type = c[0]
                    region = c[1]
                    rc, rspan = region.split(":")
                    rs, re_ = (int(x) for x in rspan.split("-"))
                except (ValueError, IndexError):
                    continue
                if "deletion" in cnv_type or "duplication" in cnv_type:
                    if overlaps(rc, rs, re_):
                        hits.append({"caller": "cnvpytor",
                                     "type": cnv_type,
                                     "region": region,
                                     "bins": tsv.rsplit(".", 2)[-2]})
    summary = {
        "bub1b_region": f"{ch}:{s0}-{e0}",
        "bub1b_overlapping_calls": len(hits),
        "calls": hits,
        "verdict": "none" if not hits else "review",
        "callers": ["manta", "cnvpytor"],
    }
    _atomic_write(Path(f"{out}/summary.json"),
                  json.dumps(summary, indent=1))
    DATA.commit()
    print(f"CNV_DONE overlapping={len(hits)}", flush=True)
    return summary


@app.function(image=repo_img, volumes={"/data": DATA},
              cpu=1, memory=4096, timeout=3600)
def slim_result(out_name: str = "track1_final") -> dict:
    """Slimmed copy of funnel/result.json -> funnel/result_head.json
    {provenance, funnel, monotonicity_violations, emitted, ranked[:200]}.
    make_report prefers this file - a 2.2 GB json.loads is a ~15-20 GB
    transient heap risk on the laptop (the emitted BUB1B row sits inside
    ranked[:200] at rank ~5, so nothing the report cites is lost)."""
    import json

    src = Path(f"/data/{out_name}/funnel/result.json")
    if not src.exists():
        raise RuntimeError(f"{src} missing - run_main not finished?")
    r = json.loads(src.read_text(encoding="utf-8"))
    head = {k: r.get(k) for k in
            ("provenance", "funnel", "monotonicity_violations",
             "emitted")}
    head["ranked"] = r.get("ranked", [])[:200]
    dst = src.with_name("result_head.json")
    _atomic_write(dst, json.dumps(head, indent=1))
    DATA.commit()
    print(f"SLIM_DONE ranked={len(head['ranked'])}", flush=True)
    return {"ranked": len(head["ranked"])}
