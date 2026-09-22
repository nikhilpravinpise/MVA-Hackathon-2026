"""Shared test scaffolding for the MVA Hackathon Track 1 suite.

Ground truth used here is a STAND-IN pair (chr1 synthetic coordinates), not
the real answer key and not anything from the leaked Space - scorer mechanics
are independent of which variants are true (plan.md section 2.1.5 firewall).
"""
from __future__ import annotations

import csv
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "scorer", REPO / "hackathon-app"):
    s = str(p)
    if s not in sys.path:
        sys.path.insert(0, s)

import evaluation as oracle  # noqa: E402  (vendored scorer oracle)

# Stand-in ground truth: clearly synthetic coordinates, firewall-clean.
GT = frozenset([("chr1", 1234567, "A", "G"), ("chr1", 7654321, "C", "T")])
V1 = ("chr1", 1234567, "A", "G")
V2 = ("chr1", 7654321, "C", "T")
JUNK = [("chr2", 2000000 + i * 1000, "G", "A") for i in range(12)]

HEADER = ("proband_id,chrom_1,pos_1,ref_1,alt_1,"
          "chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes")


def row(pid="PROBAND01", c1="", p1="", r1="", a1="",
        c2="", p2="", r2="", a2="", epcr="0.95", ft="primary", notes=""):
    return ",".join(str(x) for x in
                    (pid, c1, p1, r1, a1, c2, p2, r2, a2, epcr, ft, notes))


def vrow(v, epcr="0.95", pid="PROBAND01", ft="primary"):
    return row(pid, v[0], str(v[1]), v[2], v[3], epcr=epcr, ft=ft)


def prow(v1, v2, epcr="0.95", pid="PROBAND01"):
    return row(pid, v1[0], str(v1[1]), v1[2], v1[3],
               v2[0], str(v2[1]), v2[2], v2[3], epcr=epcr)


def score_csv_text(text: str, gt=GT, emulate_app: bool = True):
    """Run the vendored oracle over CSV text the way submit_track1.py does:
    load -> first proband group -> PROBAND01 check -> score_proband.

    Returns a ScoreResult. Raises whatever the oracle raises.
    """
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False,
                                     newline="", encoding="utf-8") as f:
        f.write(text)
        path = f.name
    try:
        subs = oracle.load_submission(path)
        if emulate_app:
            if not subs:
                raise ValueError("No valid rows found in the CSV.")
            pid = next(iter(subs))
            if pid != "PROBAND01":
                raise ValueError(
                    f"Unknown proband_id '{pid}'. Only PROBAND01 is accepted.")
            return oracle.score_proband(pid, subs[pid], gt)
        pid = next(iter(subs))
        return oracle.score_proband(pid, subs[pid], gt)
    finally:
        Path(path).unlink(missing_ok=True)


def score_rows(rows, gt=GT, header=HEADER):
    return score_csv_text(header + "\n" + "\n".join(rows) + "\n", gt=gt)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


@pytest.fixture
def oracle_module():
    return oracle
