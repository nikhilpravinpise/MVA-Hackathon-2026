"""CLI: cis/trans evidence report for a pair of candidate variants.

Combines the two orthogonal phasing evidence lines from plan.md Phase 3:

1. PGT/PID read-backed phasing already in the VCF (src/phasing.determine_phase
   on the sites' VariantFacts), and
2. read-level evidence from a SAM slice (src/reads.phase_from_reads):
   in-trans = no molecule carries both alt alleles.

Usage::

    python tools/run_phasing.py \
        --vcf results/spike_case/spike_proband.vcf \
        --site1 7:1000000 --site2 7:1004000 \
        --sam locus.sam --sample PROBAND01 --out results/phasing

For real BAM input this tool does NOT decode BAM or invoke samtools -
export a SAM slice first (the BAM must share the VCF contig convention;
challenge data uses bare contigs, '15' not 'chr15')::

    samtools view -O SAM region.bam 15:40200000-40230000 > locus.sam

--bam/--ref are accepted for pipeline plumbing but exit with that
instruction. Output: <out>/phasing_report.json with both evidence lines
and the agreement flag.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.config import load_config  # noqa: E402
from src.phasing import determine_phase  # noqa: E402
from src.reads import evidence_report, phase_from_reads  # noqa: E402
from src.triage import extract_facts  # noqa: E402
from src.vcf import VcfReader, from_submission_chrom  # noqa: E402

BAM_HELP = (
    "BAM input is not decoded in-repo and samtools is never invoked here. "
    "Export a SAM slice first, e.g.: "
    "samtools view -O SAM region.bam CHROM:START-END > locus.sam "
    "then re-run with --sam locus.sam")


def _parse_site(spec: str) -> tuple[str, int]:
    """'chrom:pos' -> (VCF-convention chrom, 1-based pos). 'chr' prefixes
    are normalized to the bare contigs the challenge VCF uses."""
    chrom_s, sep, pos_s = spec.rpartition(":")
    if not sep or not pos_s.isdigit():
        raise argparse.ArgumentTypeError(
            f"site '{spec}' must look like chrom:pos (e.g. 15:40209701)")
    return (from_submission_chrom(chrom_s), int(pos_s))


def _fact_for_site(rec, sample: str, cfg: dict):
    """VariantFacts for a site's first ALT (biallelic assumption - the
    compound-het context this tool serves; multi-allelic sites are noted
    in the report via 'alt')."""
    facts = extract_facts(rec, sample, cfg)
    alt = rec.alts[0]
    for f in facts:
        if f.alt == alt and f.gene:
            return f
    for f in facts:
        if f.alt == alt:
            return f
    return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="cis/trans phasing evidence report for a variant pair",
        epilog="BAM note: " + BAM_HELP)
    ap.add_argument("--vcf", required=True)
    ap.add_argument("--site1", required=True, type=_parse_site,
                    help="chrom:pos (chr prefix optional, stripped)")
    ap.add_argument("--site2", required=True, type=_parse_site)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--sam", default=None,
                     help="SAM text slice covering both sites "
                          "(samtools view -O SAM output)")
    src.add_argument("--bam", default=None,
                     help="accepted but not decoded - export to SAM first")
    ap.add_argument("--ref", default=None,
                    help="reference fasta (only meaningful alongside "
                         "--bam; see BAM note)")
    ap.add_argument("--sample", default=None,
                    help="sample name (default: first sample in VCF)")
    ap.add_argument("--config", default=None,
                    help="pipeline.yaml path (default: frozen config)")
    ap.add_argument("--min-support", type=int, default=3,
                    help="min spanning templates per haplotype class")
    ap.add_argument("--out", required=True,
                    help="output dir; gets phasing_report.json")
    args = ap.parse_args(argv)

    site1, site2 = args.site1, args.site2

    # --bam/--ref: accepted but never decoded - the operator exports SAM.
    if args.bam or (args.ref and not args.sam):
        chrom, pos = site1
        hint_bam = args.bam or "region.bam"
        hint_region = f"{chrom}:{max(1, pos - 5000)}-{site2[1] + 5000}"
        print("ERROR: --bam/--ref were supplied but this tool reads SAM "
              "text, not BAM. Export the locus first:\n"
              f"  samtools view -O SAM {hint_bam} {hint_region} > locus.sam\n"
              "  then re-run with --sam locus.sam", file=sys.stderr)
        return 2

    cfg = load_config(args.config)
    reader = VcfReader(args.vcf)
    sample = args.sample or (reader.samples[0] if reader.samples else "")
    want = {site1, site2}
    found = {}
    try:
        for rec in reader.records(sample=sample):
            key = (rec.chrom, rec.pos)
            if key in want and key not in found:
                found[key] = rec
            if len(found) == len(want):
                break
    finally:
        reader.close()
    missing = want - set(found)
    if missing:
        print(f"ERROR: site(s) not in VCF: "
              f"{sorted(f'{c}:{p}' for c, p in missing)}", file=sys.stderr)
        return 2
    if site1 == site2:
        print("ERROR: --site1 and --site2 are the same position",
              file=sys.stderr)
        return 2

    rec1, rec2 = found[site1], found[site2]
    vf1 = _fact_for_site(rec1, sample, cfg)
    vf2 = _fact_for_site(rec2, sample, cfg)
    if vf1 is None or vf2 is None:
        print("ERROR: could not build VariantFacts for a site "
              "(missing ALT?)", file=sys.stderr)
        return 2

    vcf_call = determine_phase(vf1, vf2)

    read_phase = None
    if args.sam:
        v1 = (rec1.chrom, rec1.pos, rec1.ref, rec1.alts[0])
        v2 = (rec2.chrom, rec2.pos, rec2.ref, rec2.alts[0])
        with open(args.sam, encoding="utf-8") as fh:
            read_phase = phase_from_reads(
                fh, v1, v2, min_support=args.min_support)

    rep = evidence_report(vcf_call, read_phase)

    report = {
        "sites": [
            {"chrom": rec1.chrom, "pos": rec1.pos, "ref": rec1.ref,
             "alt": rec1.alts[0], "pgt": vf1.pgt, "pid": vf1.pid},
            {"chrom": rec2.chrom, "pos": rec2.pos, "ref": rec2.ref,
             "alt": rec2.alts[0], "pgt": vf2.pgt, "pid": vf2.pid},
        ],
        "sample": sample,
        "vcf_phase": rep["vcf_phase"],
        "read_phase": rep["read_phase"],
        "agreement": rep["agreement"],
        "consensus_relation": rep["consensus_relation"],
        "provenance": {
            "vcf": str(args.vcf), "sam": args.sam,
            "tool": "tools/run_phasing.py",
            "note": "PGT/PID from VCF + read-level haplotype classes "
                    "from SAM; no BAM decoding in-repo",
        },
    }
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "phasing_report.json"
    out_path.write_text(json.dumps(report, indent=1) + "\n",
                        encoding="utf-8")

    print(f"sites: {rec1.chrom}:{rec1.pos} x {rec2.chrom}:{rec2.pos} "
          f"(sample={sample})")
    print(f"  vcf_phase : {rep['vcf_phase']['relation']} "
          f"({rep['vcf_phase']['mechanism']}) - {rep['vcf_phase']['detail']}")
    print(f"  read_phase: {rep['read_phase']['relation']} "
          f"({rep['read_phase']['mechanism']}) "
          f"{rep['read_phase'].get('counts', '')}")
    print(f"  agreement : {rep['agreement']} "
          f"(consensus={rep['consensus_relation']})")
    print(f"  wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
