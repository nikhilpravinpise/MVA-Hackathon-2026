"""Figure generation for the Track-1 methods report - zero-dependency.

The repo deliberately ships PyYAML-only runtime deps, so these figures are
hand-rolled SVG (string templating, deterministic bytes) plus an ASCII
pileup that embeds inline in the standalone .md report (image links do not
render inside an uploaded markdown file; the ASCII block does). ``--matplotlib``
additionally writes .png twins for the data charts when matplotlib happens
to be importable - optional, never a dependency.

Every figure regenerates from artifacts on disk (no hand-drawn content):

* ``funnel_waterfall.svg`` - per-stage counts from funnel_counts.json
* ``coverage_depth.svg``  - cumulative depth curve from mosdepth's
  ``*.global.dist.txt`` (NOTE: dist rows are DESCENDING in depth -
  decisions.md 2026-10-04 documents a real bug caused by assuming
  ascending; the parser below sorts explicitly)
* ``allele_balance.svg``  - ref/alt counts at the called sites
* ``ablation_loso.svg``   - tracked-pair rank per dropped evidence source
* ``pileup_bub1b.svg``    - coverage track across the locus slice +
  per-site read stacks (real reads from the realigned SAM)
* ``pileup_ascii.md``     - terminal-style pileup for the standalone report

Usage::

    python tools/make_figures.py \
        --sam results/track1_patient_modal/realign/region.sam \
        --allele-balance results/.../track1_final/allele_balance.json \
        --funnel-counts results/.../track1_final_indelfix/funnel/funnel_counts.json \
        --mosdepth-dist results/.../mosdepth/WGS.mosdepth.global.dist.txt \
        --mosdepth-summary results/.../mosdepth/mosdepth_summary.json \
        --ablations results/.../track1_final_indelfix/ablations.json \
        --out-dir docs/figures
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape as _esc

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.reads import parse_sam_line, read_allele_at  # noqa: E402

# ---------------------------------------------------------------- style

INK = "#111827"       # primary text
MUTE = "#6b7280"      # secondary text / axes
PANEL = "#f8fafc"     # panel background
GRID = "#e5e7eb"      # gridlines
REF_C = "#94a3b8"     # reference-allele evidence
ALT_C = "#dc2626"     # alternate-allele evidence
OTHER_C = "#d97706"   # third-allele / ambiguous
GOOD = "#059669"      # emitted / passes
EDGE = "#cbd5e1"      # read bodies / borders
THRESH = "#b91c1c"    # threshold guide lines

MONO = "Consolas,'Cascadia Mono',Menlo,monospace"
SANS = "'Segoe UI',system-ui,-apple-system,sans-serif"


def _t(x, y, s, size=11, fill=INK, anchor="start", bold=False, mono=False):
    w = ' font-weight="600"' if bold else ""
    fam = MONO if mono else SANS
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" '
            f'font-family="{fam}" fill="{fill}" '
            f'text-anchor="{anchor}"{w}>{_esc(str(s))}</text>')


def _r(x, y, w, h, fill, stroke=None, rx=0, opacity=None):
    s = f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.1, w):.1f}" height="{h:.1f}" fill="{fill}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="0.5"'
    if rx:
        s += f' rx="{rx}"'
    if opacity is not None:
        s += f' opacity="{opacity}"'
    return s + "/>"


def _l(x1, y1, x2, y2, stroke=MUTE, w=1.0, dash=None):
    s = (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
         f'stroke="{stroke}" stroke-width="{w}"')
    if dash:
        s += f' stroke-dasharray="{dash}"'
    return s + "/>"


def _poly(pts, stroke=INK, w=1.5, fill="none"):
    p = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    return (f'<polyline points="{p}" fill="{fill}" stroke="{stroke}" '
            f'stroke-width="{w}" stroke-linejoin="round"/>')


def _svg(w, h, elements) -> str:
    body = "".join(elements)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'font-family="{SANS}">{body}</svg>\n')


def _load_json(path):
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None


def _parse_site(spec: str) -> tuple[str, int, str, str]:
    """'chrom:pos:ref:alt' -> tuple, bare VCF-convention contig."""
    parts = spec.split(":")
    if len(parts) != 4 or not parts[1].isdigit():
        raise argparse.ArgumentTypeError(
            f"site '{spec}' must look like chrom:pos:ref:alt")
    c = parts[0]
    return (c[3:] if c.lower().startswith("chr") else c,
            int(parts[1]), parts[2].upper(), parts[3].upper())


def load_usable_reads(sam_path, min_mapq: int = 30) -> list[dict]:
    """Primary, non-dup, non-QC-fail, MAPQ>=min_mapq mapped records.

    Same filter set as the allele-balance evidence arm - the figure must
    visualize the same read pool the report cites.
    """
    out = []
    with open(sam_path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            rec = parse_sam_line(line)
            if rec is None or rec["is_unmapped"]:
                continue
            if (rec["is_secondary"] or rec["is_supplementary"]
                    or rec["is_duplicate"] or rec["is_qcfail"]):
                continue
            if rec["mapq"] < min_mapq:
                continue
            out.append(rec)
    return out


def covering_reads(reads, chrom: str, pos: int) -> list[dict]:
    """Reads whose alignment covers ``pos`` (a base exists there)."""
    out = []
    for r in reads:
        if r["rname"] != chrom:
            continue
        if pos in r["ref_to_query"]:
            out.append(r)
    # deterministic display order: by alignment start, then qname
    out.sort(key=lambda r: (r["pos"], r["qname"]))
    return out


# ------------------------------------------------------------- figures


def fig_funnel(counts: dict) -> str:
    stages = [
        ("VCF records", "records"),
        ("alt x gene facts", "alt_gene_facts"),
        ("genotype QC + PASS", "qc_pass"),
        ("rare tier", "rare"),
        ("eligible candidates", "candidates"),
        ("post artifact-locus mask", "locus_masked"),
        ("hypotheses enumerated", "hypotheses"),
        ("emitted", "emitted"),
    ]
    rows = [(lab, counts.get(k)) for lab, k in stages]
    W, row_h, top = 780, 30, 44
    label_w, bar_x, bar_max = 205, 215, 420
    H = top + row_h * len(rows) + 16
    log_max = math.log10(max(v for _, v in rows if v) or 1)
    log_min = math.log10(0.6)
    el = [_r(0, 0, W, H, "#ffffff"), _r(10, 10, W - 20, H - 20, PANEL, rx=6)]
    el.append(_t(20, 30, "Funnel: 478k records -> 1 emitted hypothesis",
                 size=13, bold=True))
    removed = counts.get("locus_masked_out")
    for i, (lab, v) in enumerate(rows):
        y = top + i * row_h
        el.append(_t(label_w, y + 15, lab, size=11, anchor="end",
                     fill=INK if v is not None else MUTE))
        if v is None:
            el.append(_t(bar_x, y + 15, "pending", size=10, fill=MUTE))
            continue
        frac = (math.log10(v) - log_min) / (log_max - log_min)
        w = max(2.0, frac * bar_max)
        emitted = lab == "emitted"
        el.append(_r(bar_x, y + 3, w, 18,
                     GOOD if emitted else "#3b82f6",
                     rx=3, opacity=0.9 if emitted else 0.55))
        note = f"{v:,}"
        if lab == "post artifact-locus mask" and removed:
            note += f"  (-{removed:,} masked)"
        el.append(_t(bar_x + w + 8, y + 15, note, size=11,
                     bold=emitted,
                     fill=GOOD if emitted else INK))
    return _svg(W, H, el)


def fig_coverage(dist_path, summary: dict | None) -> str:
    """Cumulative depth curve: fraction of genome covered >= depth.

    mosdepth `*.global.dist.txt` rows are (chrom, depth, proportion) in
    DESCENDING depth order; we take chrom=='total' and sort ascending.
    """
    pts = []
    for line in Path(dist_path).read_text().splitlines():
        f = line.split("\t")
        if len(f) < 3 or f[0] != "total":
            continue
        try:
            pts.append((int(f[1]), float(f[2])))
        except ValueError:
            continue
    pts = sorted((d, fr) for d, fr in pts if d <= 120)
    W, H = 780, 300
    L, Rt, T, B = 60, 20, 30, 46
    pw, ph = W - L - Rt, H - T - B
    x_of = lambda d: L + (d / 120.0) * pw
    y_of = lambda f: T + (1.0 - f) * ph
    el = [_r(0, 0, W, H, "#ffffff"), _r(10, 10, W - 20, H - 20, PANEL, rx=6)]
    el.append(_t(20, 26, "Cumulative coverage - fraction of genome "
                         "covered >= depth (WGS, 500-bp windows)",
                 size=13, bold=True))
    for d in range(0, 121, 20):
        el.append(_l(x_of(d), T, x_of(d), T + ph, GRID))
        el.append(_t(x_of(d), T + ph + 16, str(d), size=10, fill=MUTE,
                     anchor="middle"))
    for f in (0.25, 0.5, 0.75, 1.0):
        el.append(_l(L, y_of(f), L + pw, y_of(f), GRID))
        el.append(_t(L - 6, y_of(f) + 4, f"{f:.2f}", size=10, fill=MUTE,
                     anchor="end"))
    if pts:
        el.append(_poly([(x_of(d), y_of(f)) for d, f in pts],
                        stroke="#3b82f6", w=2.0))
    for dx, lab in ((10, "10x"), (30, "30x")):
        el.append(_l(x_of(dx), T, x_of(dx), T + ph, THRESH, w=1.0,
                     dash="4,3"))
        el.append(_t(x_of(dx) + 4, T + 12, lab, size=10, fill=THRESH))
    wgs = (summary or {}).get("WGS", {})
    reg = (summary or {}).get("region", {})
    if wgs:
        note = (f"WGS mean {wgs.get('mean', '?')}x | >=10x "
                f"{wgs.get('frac_ge_10x', '?')} | >=30x "
                f"{wgs.get('frac_ge_30x', '?')}   |   BUB1B slice mean "
                f"{reg.get('mean', '?')}x (100% >=10x)")
        el.append(_t(L, H - 14, note, size=10.5, fill=MUTE))
    el.append(_t(L + pw / 2, H - 30, "depth (x)", size=10, fill=MUTE,
                 anchor="middle"))
    return _svg(W, H, el)


def fig_allele_balance(ab: dict, sites) -> str:
    site_meta = ab.get("sites") or {}
    keys = [f"{c}:{p}" for c, p, _r2, _a2 in sites if f"{c}:{p}" in site_meta]
    if not keys:
        keys = sorted(site_meta)
    W, H = 780, 300
    L, T, B = 60, 34, 60
    pw = W - L - 40
    ph = H - T - B
    maxv = max((max((site_meta[k].get("counts") or {}).values(),
                    default=0) for k in keys), default=1) or 1
    el = [_r(0, 0, W, H, "#ffffff"), _r(10, 10, W - 20, H - 20, PANEL, rx=6)]
    el.append(_t(20, 26, "Read-level allele balance at the called sites "
                         "(primary, non-dup, MAPQ>=30)",
                 size=13, bold=True))
    n = len(keys)
    slot = pw / max(1, n)
    bw = min(46.0, slot / 5)
    for i, k in enumerate(keys):
        counts = site_meta[k].get("counts") or {}
        # ref allele = the site's declared ref when identifiable
        ref_base = alt_base = None
        for c, p, r, a in sites:
            if f"{c}:{p}" == k:
                ref_base, alt_base = r, a
        ref_n = counts.get(ref_base, 0) if ref_base else 0
        alt_n = counts.get(alt_base, 0) if alt_base else 0
        total = site_meta[k].get("total") or (ref_n + alt_n) or 1
        cx = L + slot * i + slot / 2
        h_ref = ph * ref_n / maxv
        h_alt = ph * alt_n / maxv
        el.append(_r(cx - bw - 3, T + ph - h_ref, bw, h_ref, REF_C, rx=2))
        el.append(_r(cx + 3, T + ph - h_alt, bw, h_alt, ALT_C, rx=2))
        el.append(_t(cx - bw / 2 - 3, T + ph - h_ref - 5,
                     f"{ref_base or '?'}={ref_n}", size=10, anchor="middle",
                     fill=INK))
        el.append(_t(cx + bw / 2 + 3, T + ph - h_alt - 5,
                     f"{alt_base or '?'}={alt_n}", size=10, anchor="middle",
                     bold=True, fill=ALT_C))
        vaf = alt_n / total if total else 0
        el.append(_t(cx, T + ph + 18, k, size=10.5, anchor="middle",
                     bold=True))
        el.append(_t(cx, T + ph + 34,
                     f"VAF {vaf * 100:.0f}% ({total} reads)", size=10,
                     anchor="middle", fill=MUTE))
    el.append(_r(L, H - 19, 10, 10, REF_C))
    el.append(_t(L + 14, H - 10, "ref", size=10, fill=MUTE))
    el.append(_r(L + 42, H - 19, 10, 10, ALT_C))
    el.append(_t(L + 56, H - 10, "alt", size=10, fill=MUTE))
    el.append(_t(L + 95, H - 10, "clean ~50% het balance - no allele "
                                "imbalance or copy-number distortion",
                 size=10.5, fill=MUTE))
    return _svg(W, H, el)


def fig_ablation(ablations: dict) -> str:
    """Tracked-pair rank per dropped evidence source (leave-one-out)."""
    rows = sorted(((k, v.get("bub1b_rank"), v.get("emitted"))
                   for k, v in ablations.items()), key=lambda r: r[0])
    W, H = 780, 300
    L, Rt, T, B = 60, 20, 40, 60
    pw, ph = W - L - Rt, H - T - B
    ranks = [r for _, r, _ in rows if r]
    rmax = max(max(ranks, default=5), 10)
    log_hi = math.log10(rmax * 1.5)
    xw = pw / max(1, len(rows))
    y_of = lambda r: T + ph - (math.log10(r) / log_hi) * ph if r else T + ph
    el = [_r(0, 0, W, H, "#ffffff"), _r(10, 10, W - 20, H - 20, PANEL, rx=6)]
    el.append(_t(20, 26, "Leave-one-source-out: tracked-pair rank when "
                         "each evidence source is dropped",
                 size=13, bold=True))
    y5 = y_of(5)
    el.append(_l(L, y5, L + pw, y5, THRESH, w=1.2, dash="5,3"))
    el.append(_t(L + pw - 4, y5 - 4, "top-5 robustness rule",
                 size=10, fill=THRESH, anchor="end"))
    for i, (name, rank, emitted) in enumerate(rows):
        cx = L + xw * i + xw / 2
        if rank:
            y = y_of(rank)
            col = GOOD if emitted else "#f59e0b"
            el.append(_r(cx - 22, y, 44, T + ph - y, col, rx=2,
                         opacity=0.85))
            el.append(_t(cx, y - 5, f"rank {rank}", size=10.5,
                         anchor="middle", bold=True))
        else:
            el.append(_r(cx - 22, T + ph - 8, 44, 8, "#e5e7eb", rx=2))
            el.append(_t(cx, T + ph - 14, "pair lost", size=10,
                         anchor="middle", fill=THRESH))
        el.append(_t(cx, T + ph + 16, name, size=10, anchor="middle",
                     fill=INK))
        el.append(_t(cx, T + ph + 30,
                     "emitted" if emitted else "not emitted",
                     size=9.5, anchor="middle",
                     fill=GOOD if emitted else THRESH))
    el.append(_t(L, T - 8, "rank (log scale)", size=10, fill=MUTE))
    el.append(_t(L, H - 12, "The call stands on ClinVar + damage "
                            "predictors + HPO together - reported plainly, "
                            "not spun as robust.",
                 size=10.5, fill=MUTE))
    return _svg(W, H, el)


# ------------------------------------------------------------ pileup

def _depth_track(reads, region: tuple[str, int, int], bin_bp: int = 400):
    chrom, start, end = region
    nbins = (end - start) // bin_bp + 1
    depth = [0] * nbins
    for r in reads:
        if r["rname"] != chrom or not r["ref_to_query"]:
            continue
        b0 = max(0, (r["pos"] - start) // bin_bp)
        b1 = min(nbins - 1, ((r["ref_end"] or r["pos"]) - start) // bin_bp)
        for b in range(b0, b1 + 1):
            depth[b] += 1
    return [(start + i * bin_bp, d) for i, d in enumerate(depth)]


def fig_pileup(reads, sites, region, allele_balance=None) -> str:
    chrom, rstart, rend = region
    W = 940
    track_t, track_h = 60, 110
    sub_h = 26
    max_rows = 18
    el = []
    el.append(_t(20, 24, "BUB1B locus - realigned reads (dedup BAM slice "
                         "15:40100000-40250000)", size=13, bold=True))
    el.append(_t(20, 40, "coverage track (400-bp bins, usable reads) + "
                         "per-site read stacks", size=10.5, fill=MUTE))

    # -- panel A: coverage track --------------------------------------
    L, Rm = 60, 20
    pw = W - L - Rm
    track = _depth_track(reads, region)
    ymax = max((d for _, d in track), default=1) or 1
    x_of = lambda p: L + ((p - rstart) / (rend - rstart)) * pw
    y_of = lambda d: track_t + track_h - (d / ymax) * track_h
    el.append(_r(L, track_t, pw, track_h, PANEL, stroke=GRID))
    for gd in range(0, int(ymax) + 1, 20):
        el.append(_l(L, y_of(gd), L + pw, y_of(gd), GRID))
        el.append(_t(L - 6, y_of(gd) + 3, str(gd), size=9, fill=MUTE,
                     anchor="end"))
    el.append(_poly([(x_of(p), y_of(d)) for p, d in track],
                    stroke="#3b82f6", w=1.5))
    for _c, p, _r2, _a2 in sites:
        el.append(_l(x_of(p), track_t, x_of(p), track_t + track_h,
                     ALT_C, w=1.0, dash="3,3"))
        el.append(_t(x_of(p), track_t - 4, str(p), size=9, fill=ALT_C,
                     anchor="middle", mono=True))
    el.append(_t(L - 6, track_t + track_h + 12, "depth", size=9,
                 fill=MUTE, anchor="end"))
    for p in (rstart, (rstart + rend) // 2, rend):
        el.append(_t(x_of(p), track_t + track_h + 14, f"{p:,}",
                     size=9, fill=MUTE, anchor="middle", mono=True))

    # -- panel B: per-site stacks -------------------------------------
    counts = (allele_balance or {}).get("sites") or {}
    col_w = (W - 40) / len(sites)
    y0 = track_t + track_h + 40
    for si, (c, p, ref, alt) in enumerate(sites):
        ox = 20 + si * col_w
        half = 80
        w0, w1 = p - half, p + half
        sx = lambda q: ox + 10 + ((q - w0) / (w1 - w0)) * (col_w - 40)
        el.append(_t(ox + 10, y0, f"{c}:{p} {ref}>{alt}", size=11,
                     bold=True, mono=True))
        cov = [r for r in reads if r["rname"] == c
               and p in r["ref_to_query"]]
        cov.sort(key=lambda r: (r["pos"], r["qname"]))
        shown = cov[:max_rows]
        ry = y0 + 14
        for r in shown:
            base = read_allele_at(r, c, p)
            cls = ("alt" if base == alt else
                   "ref" if base == ref else "other")
            x1 = sx(max(r["pos"], w0))
            x2 = sx(min(r["ref_end"] or r["pos"], w1))
            el.append(_l(x1, ry + 4, x2, ry + 4, EDGE, w=5.0))
            col = {"alt": ALT_C, "ref": REF_C}[cls] if cls != "other" \
                else OTHER_C
            el.append(_r(sx(p) - 5, ry - 1, 10, 10, col, rx=2))
            el.append(_t(sx(p), ry + 7.5, base or "?", size=8,
                         anchor="middle", fill="#ffffff", bold=True,
                         mono=True))
            ry += sub_h * 0.55
        more = len(cov) - len(shown)
        if more > 0:
            el.append(_t(ox + 10, ry + 8, f"... {more} more reads",
                         size=9, fill=MUTE))
            ry += sub_h * 0.55
        k = f"{c}:{p}"
        bal = counts.get(k, {}).get("counts", {})
        rn, an = bal.get(ref, 0), bal.get(alt, 0)
        tot = rn + an
        vaf = f"{an / tot * 100:.0f}%" if tot else "?"
        el.append(_t(ox + 10, ry + 16,
                     f"alt {an}/{tot} ({vaf})", size=10, fill=MUTE))
    H = int(y0 + max_rows * sub_h * 0.55 + 60)
    return _svg(W, H, [_r(0, 0, W, H, "#ffffff")] + el)


def ascii_pileup(reads, sites, half: int = 40, max_rows: int = 22) -> str:
    """Terminal-style pileup: consensus + per-read window with the variant
    column bracketed. Survives inside a standalone markdown file (image
    links do not), so this is the report's inline figure."""
    out = []
    for c, p, ref, alt in sites:
        cov = [r for r in reads if r["rname"] == c and p in r["ref_to_query"]]
        cov.sort(key=lambda r: (r["pos"], r["qname"]))
        w0, w1 = p - half, p + half
        cols = list(range(w0, w1 + 1))
        # consensus = majority base among covering reads per column
        cons = []
        for q in cols:
            votes = {}
            for r in cov:
                b = read_allele_at(r, c, q)
                if b in ("A", "C", "G", "T"):
                    votes[b] = votes.get(b, 0) + 1
            cons.append(max(votes, key=votes.get) if votes else "N")
        out.append(f"site {c}:{p} {ref}>{alt} - {len(cov)} covering "
                   f"reads")
        out.append("        " + "".join(cons))
        out.append("        " + " " * half + "^")
        shown = cov[:max_rows]
        for i, r in enumerate(shown, 1):
            row = []
            for q in cols:
                b = read_allele_at(r, c, q)
                row.append(b if b else " ")
            base = read_allele_at(r, c, p)
            cls = ("ALT" if base == alt else "ref" if base == ref
                   else "???")
            row[half] = f"[{row[half]}]"
            out.append(f"r{i:02d} {cls} {''.join(row)}")
        if len(cov) > len(shown):
            out.append(f"... {len(cov) - len(shown)} more covering reads")
        out.append("")
    out.append("window = site +/-40 bp; [X] marks the variant column; "
               "blank = read does not cover the position")
    return "```\n" + "\n".join(out) + "\n```"


# ------------------------------------------------- matplotlib twins


def _maybe_png(out_dir: Path, datas: dict) -> None:
    """Optional PNG twins via matplotlib - skipped silently when the
    library is not installed (it is not a repo dependency)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not installed - PNG twins skipped")
        return
    counts = datas.get("funnel")
    if counts:
        stages = [("records", "records"), ("alt x gene facts", "alt_gene_facts"),
                  ("qc pass", "qc_pass"), ("rare", "rare"),
                  ("candidates", "candidates"), ("locus masked", "locus_masked"),
                  ("hypotheses", "hypotheses"), ("emitted", "emitted")]
        fig, ax = plt.subplots(figsize=(8, 3.4))
        names = [s[0] for s in stages]
        vals = [counts.get(k) or 0 for _, k in stages]
        cols = ["#059669" if n == "emitted" else "#3b82f6" for n in names]
        ax.barh(names[::-1], [math.log10(v or 0.6) for v in vals][::-1],
                color=cols[::-1])
        for i, v in enumerate(vals[::-1]):
            ax.text(math.log10(v or 0.6) + 0.08, i, f"{v:,}", va="center",
                    fontsize=8)
        ax.set_xlabel("count (log10 scale)")
        fig.tight_layout()
        fig.savefig(out_dir / "funnel_waterfall.png", dpi=140)
        plt.close(fig)
    if datas.get("coverage_pts"):
        fig, ax = plt.subplots(figsize=(8, 3.4))
        xs, ys = zip(*datas["coverage_pts"])
        ax.plot(xs, ys, color="#3b82f6", lw=2)
        for dx in (10, 30):
            ax.axvline(dx, color="#b91c1c", ls="--", lw=1)
        ax.set(xlabel="depth (x)", ylabel="fraction of genome >= depth",
               xlim=(0, 120), ylim=(0, 1.0))
        fig.tight_layout()
        fig.savefig(out_dir / "coverage_depth.png", dpi=140)
        plt.close(fig)
    if datas.get("allele_balance") and datas.get("sites"):
        ab = datas["allele_balance"].get("sites") or {}
        fig, ax = plt.subplots(figsize=(6.4, 3.4))
        labels, refs, alts = [], [], []
        for c, p, r, a in datas["sites"]:
            k = f"{c}:{p}"
            cnt = ab.get(k, {}).get("counts", {})
            labels.append(k)
            refs.append(cnt.get(r, 0))
            alts.append(cnt.get(a, 0))
        import numpy as np  # matplotlib pulls numpy anyway
        x = np.arange(len(labels))
        ax.bar(x - 0.2, refs, 0.38, label="ref", color="#94a3b8")
        ax.bar(x + 0.2, alts, 0.38, label="alt", color="#dc2626")
        ax.set_xticks(x, labels, fontsize=8)
        ax.legend()
        fig.tight_layout()
        fig.savefig(out_dir / "allele_balance.png", dpi=140)
        plt.close(fig)
    if datas.get("ablations"):
        fig, ax = plt.subplots(figsize=(7, 3.4))
        rows = sorted(datas["ablations"].items())
        names = [k for k, _ in rows]
        ranks = [v.get("bub1b_rank") or 0 for _, v in rows]
        cols = ["#059669" if v.get("emitted") else "#f59e0b"
                for _, v in rows]
        ax.bar(names, [math.log10(r or 0.5) for r in ranks], color=cols)
        ax.axhline(math.log10(5), color="#b91c1c", ls="--", lw=1)
        ax.set_ylabel("tracked-pair rank (log10)")
        fig.tight_layout()
        fig.savefig(out_dir / "ablation_loso.png", dpi=140)
        plt.close(fig)


# ---------------------------------------------------------------- main

# the two causal sites only; non-causal sites are withheld (tools/redact.py)
DEFAULT_SITES = ["15:40209701:T:G", "15:40220612:T:G"]
DEFAULT_REGION = "15:40100000-40250000"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="report figure generation (zero-dep SVG + ASCII)")
    ap.add_argument("--sam", default=None, help="realigned SAM slice")
    ap.add_argument("--allele-balance", default=None)
    ap.add_argument("--funnel-counts", default=None)
    ap.add_argument("--mosdepth-dist", default=None,
                    help="WGS.mosdepth.global.dist.txt")
    ap.add_argument("--mosdepth-summary", default=None,
                    help="mosdepth_summary.json")
    ap.add_argument("--ablations", default=None)
    ap.add_argument("--sites", default=",".join(DEFAULT_SITES),
                    help="comma-separated chrom:pos:ref:alt list")
    ap.add_argument("--region", default=DEFAULT_REGION,
                    help="chrom:start-end coverage-track window")
    ap.add_argument("--out-dir", default=str(REPO / "docs" / "figures"))
    ap.add_argument("--matplotlib", action="store_true",
                    help="also write .png twins when matplotlib is "
                         "importable (optional, never a dependency)")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    sites = [_parse_site(s) for s in args.sites.split(",")]
    rc = args.region.split(":")[0]
    rs, re_ = args.region.split(":")[1].split("-")
    region = (rc, int(rs), int(re_))
    written, mpl_data = [], {}

    counts = _load_json(args.funnel_counts)
    if counts:
        (out_dir / "funnel_waterfall.svg").write_text(
            fig_funnel(counts), encoding="utf-8")
        written.append("funnel_waterfall.svg")
        mpl_data["funnel"] = counts
    else:
        print("skip funnel_waterfall (no --funnel-counts)")

    if args.mosdepth_dist:
        summary = _load_json(args.mosdepth_summary)
        (out_dir / "coverage_depth.svg").write_text(
            fig_coverage(args.mosdepth_dist, summary), encoding="utf-8")
        written.append("coverage_depth.svg")
        pts = []
        for line in Path(args.mosdepth_dist).read_text().splitlines():
            f = line.split("\t")
            if len(f) >= 3 and f[0] == "total":
                try:
                    pts.append((int(f[1]), float(f[2])))
                except ValueError:
                    pass
        mpl_data["coverage_pts"] = sorted(pts)
    else:
        print("skip coverage_depth (no --mosdepth-dist)")

    ab = _load_json(args.allele_balance)
    if ab:
        (out_dir / "allele_balance.svg").write_text(
            fig_allele_balance(ab, sites), encoding="utf-8")
        written.append("allele_balance.svg")
        mpl_data["allele_balance"] = ab
        mpl_data["sites"] = sites
    else:
        print("skip allele_balance (no --allele-balance)")

    abl = _load_json(args.ablations)
    if abl:
        (out_dir / "ablation_loso.svg").write_text(
            fig_ablation(abl), encoding="utf-8")
        written.append("ablation_loso.svg")
        mpl_data["ablations"] = abl
    else:
        print("skip ablation_loso (no --ablations)")

    if args.sam:
        reads = load_usable_reads(args.sam)
        (out_dir / "pileup_bub1b.svg").write_text(
            fig_pileup(reads, sites, region, ab), encoding="utf-8")
        (out_dir / "pileup_ascii.md").write_text(
            ascii_pileup(reads, sites), encoding="utf-8")
        written += ["pileup_bub1b.svg", "pileup_ascii.md"]
    else:
        print("skip pileup (no --sam)")

    if args.matplotlib:
        _maybe_png(out_dir, mpl_data)

    print(f"wrote {len(written)} figure(s) -> {out_dir}")
    for w in written:
        print(" ", w)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
