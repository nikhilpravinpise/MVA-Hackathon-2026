"""Tests for tools/make_arm_a_csv.py - the Exomiser-arm model2 CSV.

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch. Coordinates are firewall-clean contig-7 fixtures; the
oracle check uses a matching synthetic ground truth.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "tests"))

from tools import make_arm_a_csv as ma  # noqa: E402
from src.submit import validate_submission_bytes  # noqa: E402

pytestmark = pytest.mark.gate

V1 = ("7", 1000, "A", "T")
V2 = ("7", 1120, "G", "C")
GT = frozenset([("chr7", 1000, "A", "T"), ("chr7", 1120, "G", "C")])

_HEADER = (
    "#RANK\tID\tGENE_SYMBOL\tMOI\tEXOMISER_GENE_COMBINED_SCORE\t"
    "EXOMISER_VARIANT_SCORE\tCONTRIBUTING_VARIANT\tCONTIG\tSTART\tEND\t"
    "REF\tALT\tHGVS\tEXOMISER_ACMG_DISEASE_ID\tEXOMISER_ACMG_DISEASE_NAME\n"
)


def _tsv(path, contributing=2):
    """Minimal Exomiser variants.tsv: rank-1 AR block with the fixture
    pair, a non-contributing row, and a rank-2 block."""
    rows = [
        "1\t7-1000-A-T_AR\tGENEX\tAR\t0.98\t1.0\t1\t7\t1000\t1000\tA\tT\t"
        "GENEX:ENST:c.1A>T:p.(Ter1)\tOMIM:1\tFake disease 1\n",
        "1\t7-1120-G-C_AR\tGENEX\tAR\t0.98\t0.9\t1\t7\t1120\t1120\tG\tC\t"
        "GENEX:ENST:c.2G>C:p.(Ala2)\tOMIM:1\tFake disease 1\n",
        "1\t7-5000-A-G_AR\tGENEX\tAR\t0.98\t0.0\t0\t7\t5000\t5000\tA\tG\t"
        "GENEX:ENST:c.3A>G:p.(=)\t\t\n",
        "2\t7-7000-C-T_AD\tOTHER\tAD\t0.50\t0.5\t1\t7\t7000\t7000\tC\tT\t"
        "OTHER:ENST:c.4C>T:p.(Gly5)\t\t\n",
    ]
    if contributing == 1:
        rows[1] = rows[1].replace("\t1\t", "\t0\t", 1)
    path.write_text(_HEADER + "".join(rows))
    return path


def test_contributing_variants_groups_rank_block(tmp_path):
    """Falsification: CONTRIBUTING_VARIANT=0 rows must not leak into the
    row - an intergenic non-contributor in the same gene block would add
    a phantom FP to the submitted pair."""
    tsv = _tsv(tmp_path / "v.tsv")
    blocks = ma.contributing_variants(tsv)
    assert set(blocks) == {1, 2}
    b1 = blocks[1]
    assert b1["gene"] == "GENEX" and b1["moi"] == "AR"
    assert len(b1["variants"]) == 2
    assert (("7", 1000, "A", "T") in b1["variants"]
            and ("7", 1120, "G", "C") in b1["variants"])


def test_main_writes_oracle_verified_csv(tmp_path):
    """Falsification: the emitted bytes must satisfy the scorer's byte
    contract and score a full match - a hand-assembled CSV could pass a
    lint yet miss chrom-case or column rules."""
    tsv = _tsv(tmp_path / "v.tsv")
    out = tmp_path / "arm_a.csv"
    rc = ma.main(["--variants", str(tsv), "--out", str(out)])
    assert rc == 0
    data = out.read_bytes()
    assert data.startswith(b"proband_id,")
    res = validate_submission_bytes(data, GT)
    assert res.rank_points == 100.0
    assert res.f_max == 1.0
    assert res.full_match_rank == 1


def test_main_expect_mismatch_refuses(tmp_path):
    """Falsification: --expect exists so a drift between Arm-A's output
    and the funnel's emitted pair can't silently ship a CSV describing
    a different hypothesis."""
    tsv = _tsv(tmp_path / "v.tsv")
    exp = tmp_path / "result.json"
    exp.write_text(json.dumps({"ranked": [
        {"emitted": True,
         "variants": [{"chrom": "7", "pos": 9, "ref": "A", "alt": "T"},
                      {"chrom": "7", "pos": 8, "ref": "G", "alt": "C"}]}]}))
    rc = ma.main(["--variants", str(tsv), "--out",
                  str(tmp_path / "x.csv"), "--expect", str(exp)])
    assert rc == 3


def test_main_expect_match_passes(tmp_path):
    """Sanity: a matching emitted pair clears the cross-arm check."""
    tsv = _tsv(tmp_path / "v.tsv")
    exp = tmp_path / "result.json"
    exp.write_text(json.dumps({"ranked": [
        {"emitted": True,
         "variants": [{"chrom": "7", "pos": 1000, "ref": "A", "alt": "T"},
                      {"chrom": "7", "pos": 1120, "ref": "G",
                       "alt": "C"}]}]}))
    rc = ma.main(["--variants", str(tsv), "--out",
                  str(tmp_path / "x.csv"), "--expect", str(exp)])
    assert rc == 0


def test_main_refuses_non_pair_block(tmp_path):
    """Falsification: a rank block with a single contributing variant
    would emit a half-filled pair row - the tool must refuse rather than
    guess a row shape."""
    tsv = _tsv(tmp_path / "v.tsv", contributing=1)
    rc = ma.main(["--variants", str(tsv), "--out",
                  str(tmp_path / "x.csv")])
    assert rc == 2


def test_notes_carry_gene_moi_hgvs(tmp_path):
    """Falsification: notes is the only reviewer-visible free text - an
    empty or gene-less notes field wastes it."""
    tsv = _tsv(tmp_path / "v.tsv")
    out = tmp_path / "arm_a.csv"
    ma.main(["--variants", str(tsv), "--out", str(out)])
    body = out.read_text()
    assert "GENEX_AR" in body and "c.1A>T" in body and "0.98" in body
