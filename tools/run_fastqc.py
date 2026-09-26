"""CLI: FASTQ-side QC for the proband run (plan.md Phase 1, FASTQ block).

    python tools/run_fastqc.py --fastq-dir data/fastqs --out results/fastqc

fastp/FastQC are not guaranteed on this box, so this module carries its own
checks:

(a) ``parse_fastp_json`` - the preferred path: pull run metrics out of a
    fastp ``.json`` report if one was produced;
(b) ``parse_fastq_stats`` - a pure-Python FASTQ streamer fallback computing
    n_reads, mean read length, GC fraction and the phred+33 Q30 fraction
    (.gz-aware via magic bytes);
(c) ``compare_to_expectations`` - score measured metrics against the leaked
    run metrics (~404M read pairs, Q30 ~93.5%, GC ~41%, dup ~8.4%, ~35x
    coverage). plan.md Phase 1 treats those numbers as *expectations*, not
    truth, so each check returns pass/fail/missing plus a note rather than
    a bare bool.

The CLI scans ``--fastq-dir`` for ``*.fastq[.gz]`` / ``*.fq[.gz]`` and for
fastp-style ``*.json`` reports (anything with a ``summary.before_filtering``
block), aggregates, compares, and writes ``fastqc_report.json`` +
``fastqc_summary.md`` into ``--out``. Deterministic: sorted filenames, no
timestamps. Until the ~85 GB download lands, an empty scan dir produces a
``no_inputs`` report and a zero exit - that is the expected pre-access state,
not a failure.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import re
import sys
from pathlib import Path

#: Leaked / participant-reported run metrics (plan.md Phase 1; deep dive).
#: ``tolerance`` is the fractional +- bound applied to each expected value
#: (Gate 1: "FASTQ read counts within 20% of expectation").
EXPECTED_RUN = {
    "read_pairs": {"expected": 404_000_000, "tolerance": 0.20,
                   "unit": "pairs"},
    "q30_rate": {"expected": 0.935, "tolerance": 0.20, "unit": "fraction"},
    "gc_content": {"expected": 0.41, "tolerance": 0.20, "unit": "fraction"},
    "duplication_rate": {"expected": 0.084, "tolerance": 0.20,
                         "unit": "fraction"},
    "coverage_x": {"expected": 35.0, "tolerance": 0.20, "unit": "x"},
}

#: Genome-size divisor for the coverage back-of-envelope (GRCh38-ish).
_GENOME_SIZE = 3.1e9

_FASTQ_RE = re.compile(r"\.(fastq|fq)(\.gz)?$", re.IGNORECASE)
_R1_RE = re.compile(r"([_.]r1[_.]|_1\.f(ast)?q)", re.IGNORECASE)
_R2_RE = re.compile(r"([_.]r2[_.]|_2\.f(ast)?q)", re.IGNORECASE)


# ---------------------------------------------------------------------------
# (a) fastp report parsing
# ---------------------------------------------------------------------------

def parse_fastp_json(path) -> dict:
    """Pull the EDA metrics out of a fastp JSON report.

    Uses ``summary.before_filtering`` (the raw-run truth) plus
    ``duplication.rate``; the after-filtering block is carried through for
    context. fastp counts each mate in ``total_reads``, so for paired-end
    data (detected via ``read2_mean_length`` > 0) the report's reads are
    halved into ``read_pairs`` here - documented on the ``paired_end`` flag.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "summary" not in data:
        raise ValueError(f"{path}: not a fastp report (no 'summary' block)")
    summ = data.get("summary") or {}
    before = summ.get("before_filtering") or {}
    after = summ.get("after_filtering") or {}
    dup = (data.get("duplication") or {}).get("rate")
    paired = bool(before.get("read2_mean_length"))
    total_reads = before.get("total_reads")
    out = {
        "source": "fastp",
        "path": str(path),
        "paired_end": paired,
        "total_reads": total_reads,
        "read_pairs": (total_reads // 2) if (paired and total_reads)
        else total_reads,
        "total_bases": before.get("total_bases"),
        "q30_rate": before.get("q30_rate"),
        "q30_bases": before.get("q30_bases"),
        "gc_content": before.get("gc_content"),
        "duplication_rate": dup,
        "read1_mean_length": before.get("read1_mean_length"),
        "read2_mean_length": before.get("read2_mean_length"),
        "after_filtering": {
            "total_reads": after.get("total_reads"),
            "total_bases": after.get("total_bases"),
            "q30_rate": after.get("q30_rate"),
            "gc_content": after.get("gc_content"),
        },
    }
    return out


# ---------------------------------------------------------------------------
# (b) pure-Python FASTQ streamer fallback
# ---------------------------------------------------------------------------

def _open_maybe_gz(path) -> io.TextIOBase:
    p = Path(path)
    with open(p, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8",
                                errors="replace")
    return open(p, encoding="utf-8", errors="replace")


def parse_fastq_stats(path) -> dict:
    """Stream a FASTQ (plain or .gz) and compute basic QC metrics.

    Returns n_reads, total_bases, mean_read_len, gc_fraction (over A/C/G/T
    bases only - Ns excluded from the denominator) and q30_fraction over
    phred+33 quality chars (Q>=30 <=> ASCII >= '?'). FASTQ technically allows
    sequence and quality strings to wrap across lines, so the parser reads
    sequence lines up to the '+' marker then quality lines until the quality
    length matches the sequence. It cannot measure duplication - that stays
    ``missing`` for :func:`compare_to_expectations`. A quality block shorter
    than its sequence (a truncated last record) is counted in
    ``n_truncated``, not as a complete read.
    """
    n_reads = 0
    n_truncated = 0
    total_bases = 0
    gc = acgt = 0
    q30 = qchars = 0
    with _open_maybe_gz(path) as fh:
        while True:
            name = fh.readline()
            if not name:
                break
            if not name.startswith("@"):
                raise ValueError(
                    f"{path}: malformed FASTQ - expected '@' header, got "
                    f"{name[:60]!r}")
            seq_parts: list[str] = []
            line = fh.readline()
            while line and not line.startswith("+"):
                seq_parts.append(line.strip())
                line = fh.readline()
            seq = "".join(seq_parts)
            qlen = 0
            while qlen < len(seq):
                qline = fh.readline()
                if not qline:
                    break
                qs = qline.rstrip("\r\n")
                qlen += len(qs)
                qchars += len(qs)
                for ch in qs:
                    if ch >= "?":  # phred+33 >= 30
                        q30 += 1
            if qlen < len(seq):
                # truncated tail record - count it separately rather than
                # as a complete read (a cut file must not look healthy)
                n_truncated += 1
                break
            n_reads += 1
            total_bases += len(seq)
            for b in seq:
                if b in "GC":
                    gc += 1
                    acgt += 1
                elif b in "AT":
                    acgt += 1
    return {
        "source": "fastq_stream",
        "path": str(path),
        "n_reads": n_reads,
        "n_truncated": n_truncated,
        "total_bases": total_bases,
        "mean_read_len": (total_bases / n_reads) if n_reads else None,
        "gc_fraction": (gc / acgt) if acgt else None,
        "q30_fraction": (q30 / qchars) if qchars else None,
    }


# ---------------------------------------------------------------------------
# (c) compare against the leaked run-metric expectations
# ---------------------------------------------------------------------------

def compare_to_expectations(stats: dict, expected: dict | None = None) -> dict:
    """Score measured metrics against ``EXPECTED_RUN`` (+-tolerance each).

    Accepts either parser's output; key aliases are resolved
    (``q30_fraction`` -> ``q30_rate``, ``gc_fraction`` -> ``gc_content``,
    ``dup_rate`` -> ``duplication_rate``). ``read_pairs`` comes from the
    explicit key, else ``total_reads`` (halved when ``paired_end`` is set);
    ``coverage_x`` falls back to ``total_bases / 3.1e9``.

    Each metric reports ``pass`` / ``fail`` / ``missing`` + a note. Missing
    means not measurable from the input (e.g. duplication from raw FASTQ) -
    absent evidence is not evidence of failure and does not flip
    ``all_pass``; ``all_pass`` requires every *measured* metric within
    tolerance and at least one metric measured.
    """
    expected = expected or EXPECTED_RUN
    notes: list[str] = []

    def first(*keys):
        for k in keys:
            v = stats.get(k)
            if v is not None:
                return v
        return None

    read_pairs = stats.get("read_pairs")
    if read_pairs is None and stats.get("total_reads") is not None:
        tr = stats["total_reads"]
        if stats.get("paired_end"):
            read_pairs = tr / 2
            notes.append(
                "read_pairs = total_reads/2 (paired-end: each mate counted)")
        else:
            read_pairs = tr
            notes.append(
                "read_pairs taken as total_reads; if data is paired-end and "
                "both mates were counted, halve this")

    coverage = stats.get("coverage_x")
    if coverage is None and stats.get("total_bases"):
        coverage = stats["total_bases"] / _GENOME_SIZE
        notes.append("coverage_x = total_bases / 3.1e9 (approx)")

    measured = {
        "read_pairs": read_pairs,
        "q30_rate": first("q30_rate", "q30_fraction"),
        "gc_content": first("gc_content", "gc_fraction"),
        "duplication_rate": first("duplication_rate", "dup_rate"),
        "coverage_x": coverage,
    }
    checks: dict[str, dict] = {}
    n_meas = 0
    all_pass = True
    for metric, spec in expected.items():
        v = measured.get(metric)
        e, tol = spec["expected"], spec["tolerance"]
        if v is None:
            checks[metric] = {
                "status": "missing", "value": None, "expected": e,
                "tolerance": tol, "note": "not measured from this input"}
            continue
        dev = abs(v - e) / e if e else 0.0
        ok = dev <= tol
        n_meas += 1
        all_pass = all_pass and ok
        checks[metric] = {
            "status": "pass" if ok else "fail",
            "value": v,
            "expected": e,
            "tolerance": tol,
            "deviation_frac": round(dev, 6),
            "note": (f"within +-{tol:.0%} of expected {e}" if ok else
                     f"OUT of +-{tol:.0%} tolerance: {v} vs expected {e}"),
        }
    if n_meas == 0:
        all_pass = False
        notes.append("no comparable metrics present in input")
    return {"checks": checks, "all_pass": bool(all_pass),
            "n_measured": n_meas, "notes": notes}


# ---------------------------------------------------------------------------
# aggregation helpers + CLI
# ---------------------------------------------------------------------------

def _aggregate_fastp(reports: list[dict]) -> dict:
    """Pool per-report fastp stats; rate metrics weighted by total_bases."""
    tot_reads = sum(r.get("total_reads") or 0 for r in reports)
    tot_pairs = sum(r.get("read_pairs") or 0 for r in reports)
    tot_bases = sum(r.get("total_bases") or 0 for r in reports)

    def wavg(key):
        if not tot_bases:
            return None
        num = sum((r.get(key) or 0.0) * (r.get("total_bases") or 0)
                  for r in reports)
        return num / tot_bases

    dups = [r["duplication_rate"] for r in reports
            if r.get("duplication_rate") is not None]
    return {
        "n_reports": len(reports),
        "total_reads": tot_reads or None,
        "read_pairs": tot_pairs or None,
        "total_bases": tot_bases or None,
        "q30_rate": wavg("q30_rate"),
        "gc_content": wavg("gc_content"),
        "duplication_rate": (sum(dups) / len(dups)) if dups else None,
        "coverage_x": (tot_bases / _GENOME_SIZE) if tot_bases else None,
        "paired_end": any(r.get("paired_end") for r in reports),
    }


def _aggregate_fastqs(paths: list[Path]) -> dict:
    """Stream every FASTQ and pool; rates weighted by per-file bases."""
    per = [parse_fastq_stats(p) for p in paths]
    n_reads = sum(s["n_reads"] for s in per)
    n_trunc = sum(s.get("n_truncated") or 0 for s in per)
    bases = sum(s["total_bases"] for s in per)

    def wavg(key):
        if not bases:
            return None
        return sum((s.get(key) or 0.0) * s["total_bases"]
                   for s in per) / bases

    r1_reads = sum(s["n_reads"] for s, p in zip(per, paths)
                   if _R1_RE.search(p.name))
    r2_present = any(_R2_RE.search(p.name) for p in paths)
    if r1_reads and r2_present:
        read_pairs = r1_reads
    elif not r2_present:
        read_pairs = n_reads  # single-end: one read == one fragment
    else:
        read_pairs = None
    return {
        "n_files": len(paths),
        "files": [str(p) for p in paths],
        "n_reads": n_reads or None,
        "n_truncated": n_trunc or None,
        "read_pairs": read_pairs,
        "total_bases": bases or None,
        "mean_read_len": (bases / n_reads) if n_reads else None,
        "q30_rate": wavg("q30_fraction"),
        "gc_content": wavg("gc_fraction"),
        "coverage_x": (bases / _GENOME_SIZE) if bases else None,
        "paired_end": r2_present,
    }


def _render_summary(report: dict) -> str:
    L = ["# FASTQ QC summary", ""]
    L.append(f"Scanned dir: `{report['scanned_dir']}` - mode: "
             f"`{report['mode']}` - status: `{report['status']}`")
    L.append("")
    comp = report.get("comparison")
    stats = report.get("stats")
    if stats:
        L.append("## Measured stats")
        L.append("")
        L.append("| metric | value |")
        L.append("|---|---|")
        for k in sorted(stats):
            v = stats[k]
            if isinstance(v, float):
                v = f"{v:.4f}"
            if isinstance(v, list):
                v = f"{len(v)} entries"
            L.append(f"| {k} | {v} |")
        L.append("")
    if comp:
        L.append("## Comparison to leaked run expectations (+-20%)")
        L.append("")
        L.append("| metric | status | value | expected | note |")
        L.append("|---|---|---|---|---|")
        for m, c in comp["checks"].items():
            L.append(f"| {m} | {c['status']} | {c.get('value')} | "
                     f"{c['expected']} | {c['note']} |")
        L.append("")
        L.append(f"all_pass: **{comp['all_pass']}** "
                 f"({comp['n_measured']} metrics measured)")
        for n in comp["notes"]:
            L.append(f"- {n}")
        L.append("")
    if report.get("note"):
        L.append(f"note: {report['note']}")
        L.append("")
    return "\n".join(L)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="FASTQ QC vs leaked run expectations (plan.md Phase 1)")
    ap.add_argument("--fastq-dir", required=True,
                    help="dir holding *.fastq[.gz] / *.fq[.gz] and/or "
                         "fastp *.json reports")
    ap.add_argument("--out", required=True,
                    help="output dir for fastqc_report.json + "
                         "fastqc_summary.md")
    args = ap.parse_args(argv)

    d = Path(args.fastq_dir)
    if not d.is_dir():
        print(f"ERROR: fastq dir not found: {d}", file=sys.stderr)
        return 2
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    fastqs = sorted(p for p in d.iterdir() if _FASTQ_RE.search(p.name))
    fastp_stats = []
    for j in sorted(d.glob("*.json")):
        try:
            s = parse_fastp_json(j)
        except Exception:
            # a file that LOOKS like a fastp report but is corrupt is a
            # failed input, not a skippable non-fastp json (audit M3: a
            # truncated download would otherwise green-light as no_inputs)
            head = j.read_text(errors="replace")[:2048]
            if "summary" in head or "before_filtering" in head \
                    or "after_filtering" in head:
                print(f"ERROR: {j.name} looks like a fastp report but is "
                      "unreadable/corrupt - failing the gate", file=sys.stderr)
                return 2
            continue  # unrelated json - skip, do not fail the scan
        if s.get("total_reads"):
            fastp_stats.append(s)

    report = {"scanned_dir": str(d), "n_fastq_files": len(fastqs),
              "fastp_reports": [s["path"] for s in fastp_stats]}
    if fastp_stats:
        stats = _aggregate_fastp(fastp_stats)
        report["mode"] = "fastp_json"
    elif fastqs:
        try:
            stats = _aggregate_fastqs(fastqs)
        except ValueError as e:
            print(f"ERROR: {e}", file=sys.stderr)
            return 2
        report["mode"] = "fastq_stream"
    else:
        stats = None
        report["mode"] = "no_inputs"
        report["note"] = ("no FASTQ files or fastp JSON reports found - "
                          "expected state until the ~85 GB download lands")

    if stats is not None:
        report["stats"] = stats
        report["comparison"] = compare_to_expectations(stats)
        report["status"] = "ok"
    else:
        report["status"] = "no_inputs"

    (out_dir / "fastqc_report.json").write_text(
        json.dumps(report, indent=1, sort_keys=True) + "\n",
        encoding="utf-8")
    (out_dir / "fastqc_summary.md").write_text(
        _render_summary(report), encoding="utf-8", newline="")

    all_pass = True
    if stats is not None:
        comp = report["comparison"]
        all_pass = comp["all_pass"]
        if stats.get("n_truncated"):
            # a truncated FASTQ (cut download) is not a healthy run
            all_pass = False
            comp["notes"].append(
                f"{stats['n_truncated']} truncated record(s) - file cut "
                "short; re-download")
        print(f"mode={report['mode']} all_pass={comp['all_pass']} "
              f"measured={comp['n_measured']}")
        for m, c in comp["checks"].items():
            print(f"  {m:18s} {c['status']:7s} value={c.get('value')} "
                  f"expected={c['expected']}")
    else:
        print(report["note"])
    print(f"wrote {out_dir / 'fastqc_report.json'} and "
          f"{out_dir / 'fastqc_summary.md'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
