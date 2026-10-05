"""Tests for tools/make_figures.py - zero-dependency report figures.

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch. Fixtures use synth_sam's contig-7 sites, never real-case
coordinates (firewall doctrine).
"""
from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src import synth_sam  # noqa: E402
from tools import make_figures as mf  # noqa: E402

pytestmark = pytest.mark.gate


def _wellformed(svg_text: str):
    """Parse + return the root; raises on malformed XML."""
    root = ET.fromstring(svg_text)
    assert root.tag.endswith("svg")
    return root


def test_fig_funnel_svg_wellformed_and_counts():
    """Falsification: a silent stage-key rename in funnel_counts.json
    would render empty bars - the stage names and counts must appear."""
    counts = {"records": 478174, "alt_gene_facts": 923952,
              "qc_pass": 848012, "rare": 373547, "candidates": 373545,
              "locus_masked": 366214, "locus_masked_out": 7331,
              "hypotheses": 2025791, "emitted": 1}
    svg = mf.fig_funnel(counts)
    _wellformed(svg)
    assert "478,174" in svg
    assert "2,025,791" in svg
    assert "-7,331" in svg  # the mask's disclosed removal count


def test_fig_funnel_deterministic():
    """Falsification: nondeterministic rendering (dict order, timestamps)
    would dirty git diffs on every rerun - bytes must be stable."""
    counts = {"records": 10, "alt_gene_facts": 20, "qc_pass": 18,
              "rare": 15, "candidates": 14, "locus_masked": 12,
              "hypotheses": 30, "emitted": 1}
    assert mf.fig_funnel(counts) == mf.fig_funnel(counts)


def test_fig_coverage_parses_descending_dist(tmp_path):
    """Falsification: mosdepth's dist file is DESCENDING in depth - the
    bug documented in decisions.md. The parser must sort ascending, so a
    descending fixture must still yield a sane curve."""
    dist = tmp_path / "x.mosdepth.global.dist.txt"
    dist.write_text("total\t30\t0.85\ntotal\t10\t0.94\ntotal\t1\t0.99\n"
                    "total\t0\t1.00\n1\t2\t0.5\n")  # chrom rows ignored
    svg = mf.fig_coverage(dist, {"WGS": {"mean": 42.0, "frac_ge_10x": 0.94,
                                        "frac_ge_30x": 0.85},
                                 "region": {"mean": 45.0}})
    _wellformed(svg)
    assert "10x" in svg and "30x" in svg
    assert "42.0" in svg


def test_fig_allele_balance_svg(tmp_path):
    """Falsification: a sites-key drift in allele_balance.json must not
    produce an empty chart - site labels and counts render."""
    ab = {"sites": {"7:1000": {"counts": {"A": 20, "T": 18}, "total": 38},
                    "7:1120": {"counts": {"G": 22, "C": 21}, "total": 43}}}
    sites = [("7", 1000, "A", "T"), ("7", 1120, "G", "C")]
    svg = mf.fig_allele_balance(ab, sites)
    _wellformed(svg)
    assert "7:1000" in svg and "VAF" in svg


def test_fig_ablation_svg():
    """Falsification: the honest-fragility figure must surface the real
    bub1b_rank values, incl. a 'pair lost' row when rank is null."""
    abl = {"clinvar": {"bub1b_rank": 9, "emitted": 1},
           "hpo": {"bub1b_rank": None, "emitted": 0}}
    svg = mf.fig_ablation(abl)
    _wellformed(svg)
    assert "rank 9" in svg
    assert "pair lost" in svg
    assert "top-5" in svg


def test_pileup_svg_and_ascii_on_synth_sam(tmp_path):
    """Falsification: the figure must show the planted alt allele - a
    CIGAR mis-parse (the reads.py class of bug) yields zero covering
    reads and an empty stack."""
    sites, templates = synth_sam.trans_case()
    sam = tmp_path / "t.sam"
    synth_sam.write_sam(sam, templates)
    reads = mf.load_usable_reads(sam, min_mapq=30)
    cov = mf.covering_reads(reads, "7", 1000)
    assert len(cov) > 0

    svg = mf.fig_pileup(reads, sites, ("7", 800, 2000))
    _wellformed(svg)
    assert "7:1000" in svg

    ascii_out = mf.ascii_pileup(reads, sites, half=20, max_rows=10)
    assert "site 7:1000 A>T" in ascii_out
    assert "[T]" in ascii_out  # planted alt allele shown bracketed
    assert "[A]" in ascii_out  # ref reads shown too
    assert "^" in ascii_out


def test_ascii_pileup_caps_rows_and_marks_excess(tmp_path):
    """Falsification: with more covering reads than max_rows the block
    must truncate AND report the remainder - silently dropping reads
    would misstate the evidence depth."""
    sites, templates = synth_sam.trans_case()
    sam = tmp_path / "t.sam"
    synth_sam.write_sam(sam, templates)
    reads = mf.load_usable_reads(sam, min_mapq=30)
    txt = mf.ascii_pileup(reads, sites, half=10, max_rows=3)
    assert "more covering reads" in txt


def test_load_usable_reads_filters(tmp_path):
    """Falsification: the figure must honor the same filters the report
    cites (primary, non-dup, MAPQ>=30) - unfiltered reads would inflate
    the pileup vs the reported counts."""
    sites, templates = synth_sam.trans_case()
    sam = tmp_path / "t.sam"
    synth_sam.write_sam(sam, templates)
    all_r = mf.load_usable_reads(sam, min_mapq=0)
    filt = mf.load_usable_reads(sam, min_mapq=30)
    assert len(filt) <= len(all_r)
    assert all(not r["is_duplicate"] for r in filt)


def test_main_end_to_end(tmp_path):
    """Falsification: wiring must actually write files - a silent arg
    name drift would produce 'wrote 0 figures' while the report embeds
    pending-notes."""
    sites, templates = synth_sam.trans_case()
    sam = tmp_path / "t.sam"
    synth_sam.write_sam(sam, templates)
    counts = tmp_path / "f.json"
    counts.write_text(json.dumps({"records": 2, "emitted": 1}))
    out = tmp_path / "figs"
    rc = mf.main(["--sam", str(sam), "--funnel-counts", str(counts),
                  "--sites", "7:1000:A:T,7:1120:G:C",
                  "--region", "7:800-2000",
                  "--out-dir", str(out)])
    assert rc == 0
    assert (out / "funnel_waterfall.svg").is_file()
    assert (out / "pileup_bub1b.svg").is_file()
    assert (out / "pileup_ascii.md").is_file()
    for f in ("funnel_waterfall.svg", "pileup_bub1b.svg"):
        _wellformed((out / f).read_text())


def test_main_missing_inputs_writes_nothing(tmp_path):
    """Falsification: no artifacts -> no figures (not crashes, not empty
    SVGs that would embed as blank images in the report)."""
    out = tmp_path / "figs"
    rc = mf.main(["--out-dir", str(out)])
    assert rc == 0
    assert not list(out.glob("*.svg"))
