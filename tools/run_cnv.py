"""CNV/SV arm - command generator (plan.md Phase 2 bullet + Phase 3 depth run).

The shipped VCF is SNV/indel-only; a heterozygous deletion allele would
change the compound-het story (del x SNV = biallelic). We therefore plan a
CNV screen on our re-aligned BAM as a secondary arm - it cannot change the
primary call without evidence, but a confirmatory result hardens the claim.

Like ``run_realign.py`` this tool does NOT execute bioinformatics
binaries in-repo; it emits the exact commands to run locally or on the
compute decision recorded in ``docs/decisions.md`` (Modal public-stand-in /
AWS spot for proband jobs pending the attestation read). Patient BAMs never
leave the local machine.

    python tools/run_cnv.py --bam results/realign/proband.bam --ref env/ref/GRCh38_no_alt.fa --out results/cnv/ --write-script
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def commands(bam: Path, ref: Path, out: Path, threads: int) -> list[str]:
    out_s = str(out)
    return [
        "mkdir -p " + out_s,
        # Manta needs a BAM index; emit it rather than assuming one exists
        "samtools index " + str(bam) + " 2>/dev/null || true",
        # Manta - germline SV/del/dup/ins/inv calling, docker
        "mkdir -p " + out_s + "/manta",
        "docker run --rm -v $(pwd):/work "
        "quay.io/biocontainers/manta:1.6.0--h9ee0642_2 "
        "configManta.py --bam /work/" + str(bam) +
        " --referenceFasta /work/" + str(ref) +
        " --runDir /work/" + out_s + "/manta",
        out_s + "/manta/runWorkflow.py -m local -j " + str(threads),
        # CNVpytor - read-depth CNV (complementary to Manta's PE/SR evidence)
        "docker run --rm -v $(pwd):/work "
        "quay.io/biocontainers/cnvpytor:1.3.1--py310h58d44f5_0 "
        "bash -c 'cnvpytor -root /work/" + out_s + "/proband.pytor "
        "-rd /work/" + str(bam) + " && cnvpytor -root "
        "/work/" + out_s + "/proband.pytor -his 10000 100000 "
        "&& cnvpytor -root /work/" + out_s + "/proband.pytor "
        "-partition 10000 100000 && cnvpytor -root /work/" + out_s +
        "/proband.pytor -call 10000 > /work/" + out_s +
        "/cnvpytor_calls.10k.tsv && cnvpytor -root /work/" + out_s +
        "/proband.pytor -call 100000 > /work/" + out_s +
        "/cnvpytor_calls.100k.tsv'",
        # Focused locus review: union the callers' hits at candidate loci
        "echo 'Intersect Manta + CNVpytor calls at each emitted "
        "hypothesis locus; a confirmed deletion allele = re-check the "
        "compound-het model before finalizing (plan Phase 2)'",
    ]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="CNV/SV screen command generator (no binaries in-repo)")
    ap.add_argument("--bam", required=True, help="re-aligned sorted BAM")
    ap.add_argument("--ref", required=True,
                    help="GRCh38 no-alt reference FASTA used for the BAM")
    ap.add_argument("--out", required=True, help="output dir for CNV calls")
    ap.add_argument("--threads", type=int, default=16)
    ap.add_argument("--write-script", action="store_true",
                    help="write a runnable shell script alongside printing")
    args = ap.parse_args(argv)

    if args.threads < 1:
        print("ERROR: --threads must be >= 1", file=sys.stderr)
        return 2
    # POSIX-normalize but keep RELATIVE - the emitted docker commands mount
    # $(pwd):/work, so absolute host paths would resolve outside the mount
    bam = Path(str(args.bam).replace("\\", "/"))
    ref = Path(str(args.ref).replace("\\", "/"))
    out = Path(str(args.out).replace("\\", "/"))
    if bam.is_absolute() or ref.is_absolute() or out.is_absolute():
        print("ERROR: --bam/--ref/--out must be relative paths under the "
              "mount root (the emitted script mounts $(pwd):/work - run it "
              "from the directory containing these paths)", file=sys.stderr)
        return 2
    cmds = commands(bam, ref, out, args.threads)
    print("# CNV/SV screen - review commands before executing")
    for c in cmds:
        print(c)
    if args.write_script:
        out.mkdir(parents=True, exist_ok=True)
        script = out / "run_cnv.sh"
        script.write_text("#!/usr/bin/env bash\nset -euo pipefail\n" +
                          "\n".join(cmds) + "\n")
        print(f"# wrote {script}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
