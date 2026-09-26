"""Tests for tools/make_report.py - GATE 6 (regenerated numbers, no
hand-typed stats).

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools.make_report import runtime_section, submission_summary
import pytest

pytestmark = pytest.mark.gate


def _hyp(chrom, pos=1000, ref="A", alt="T", gene="GENEX", model="dominant_het"):
    return {"gene": gene, "model": model, "score": 0.9, "variant_damage": 1.0,
            "pheno_score": 0.7, "inheritance_score": 0.5, "epcr": 0.95,
            "in_trans": "unknown", "emitted": True,
            "variants": [{"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}]}


def test_submission_summary_no_double_chr_prefix_on_chr_contig():
    """Falsification: a source VCF using chr-prefixed contigs must render
    'chr7:...' in the headline call, not 'chrchr7:...' - the exact
    double-prefix bug the reinvented (rather than reused)
    to_submission_chrom logic produced."""
    result = {"ranked": [_hyp("chr7", pos=140453136)]}
    summary = submission_summary(result, truth=None)
    assert "chrchr7" not in summary
    assert "chr7:140453136" in summary


def test_submission_summary_normalizes_bare_contig():
    """Falsification: a bare contig ('15', the challenge VCF convention)
    must still be normalized to 'chr15' in the report, matching
    to_submission_chrom used everywhere else in the writer."""
    result = {"ranked": [_hyp("15", pos=40000001)]}
    summary = submission_summary(result, truth=None)
    assert "chr15:40000001" in summary


def test_runtime_section_fixture_count_matches_test_module():
    """Falsification: GATE 6 forbids hand-typed stats in the report; a
    literal '57' would silently drift from the real adversarial-battery
    size the moment a fixture is added or removed. The rendered count
    must equal the actual MUTATIONS+NOOP_MUTATIONS size in
    tests/test_adversarial.py, and no bogus fixed 'seconds' duration may
    be rendered for a job that was never timed."""
    sys.path.insert(0, str(REPO / "tests"))
    import test_adversarial as ta
    expected_n = len(ta.MUTATIONS) + len(ta.NOOP_MUTATIONS)

    section = runtime_section(None, {"runtime_sec": 1.23})
    assert f"{expected_n}-fixture" in section
    assert "seconds |" not in section
