"""tests for tools/gnomad_split.py - the slice -> VEP-custom rename.

Bug pinned: on a JOINT sites slice, a variant with no exome/genome subset
AF still carries the bare joint `AF` token. Renaming bare `AF` -> `AF`
emitted the JOINT frequency into the gnomADe_AF contract field, so a
genomes-only row fabricated exome rarity evidence. The fix reads the
input's own INFO header: wherever AF_<suf>(_<pop>) is defined, the bare
name is the joint field and the mapping is dropped.
"""
from __future__ import annotations

import contextlib
import gzip
import io
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
import gnomad_split  # noqa: E402

HDR_JOINT = """\
##fileformat=VCFv4.2
##INFO=<ID=AF,Number=A,Type=Float,Description="joint">
##INFO=<ID=AF_exomes,Number=A,Type=Float,Description="ex">
##INFO=<ID=AF_exomes_nfe,Number=A,Type=Float,Description="ex nfe">
##INFO=<ID=AF_genomes,Number=A,Type=Float,Description="gx">
##contig=<ID=chr1,length=1000>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""

HDR_SITES = """\
##fileformat=VCFv4.2
##INFO=<ID=AF,Number=A,Type=Float,Description="sites af">
##INFO=<ID=AF_nfe,Number=A,Type=Float,Description="sites nfe">
##contig=<ID=chr1,length=1000>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""


def _run(tmp_path: Path, header: str, rows: list[str],
         side: str) -> list[str]:
    src = tmp_path / "slice.vcf.gz"
    with gzip.open(src, "wt") as fh:
        fh.write(header + "".join(r + "\n" for r in rows))
    buf = io.StringIO()
    argv = sys.argv
    sys.argv = ["gnomad_split.py", str(src), side]
    try:
        with contextlib.redirect_stdout(buf):
            gnomad_split.main()
    finally:
        sys.argv = argv
    return [ln for ln in buf.getvalue().splitlines()
            if ln and not ln.startswith("#")]


def _info(row: str) -> str:
    return row.split("\t")[7]


def test_joint_genomes_only_row_drops_joint_af(tmp_path: Path) -> None:
    """A row carrying only the bare joint AF must emit INFO '.', not the
    joint frequency dressed as an exome AF."""
    rows = _run(tmp_path, HDR_JOINT,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.4"], "e")
    assert _info(rows[0]) == "."


def test_joint_exome_af_beats_joint_af(tmp_path: Path) -> None:
    """When both tokens are present, AF_exomes is the value emitted."""
    rows = _run(tmp_path, HDR_JOINT,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.4;AF_exomes=0.001;"
                 "AF_exomes_nfe=0.002"], "e")
    assert _info(rows[0]) == "AF=0.001;NFE_AF=0.002"


def test_sites_file_bare_names_pass_through(tmp_path: Path) -> None:
    """An exomes-sites file defines only bare names - kept verbatim."""
    rows = _run(tmp_path, HDR_SITES,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.001;AF_nfe=0.002"], "e")
    assert _info(rows[0]) == "AF=0.001;NFE_AF=0.002"


def test_sites_file_genomes_side_also_works(tmp_path: Path) -> None:
    """genomes-sites files use the same bare names - side g must emit."""
    rows = _run(tmp_path, HDR_SITES,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.003;AF_nfe=0.004"], "g")
    assert _info(rows[0]) == "AF=0.003;NFE_AF=0.004"


def test_contig_and_chrom_chr_stripped(tmp_path: Path) -> None:
    rows = _run(tmp_path, HDR_SITES,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.001"], "e")
    assert rows[0].startswith("1\t100\t")


HDR_GENOMES_ONLY_JOINT = """\
##fileformat=VCFv4.2
##INFO=<ID=AF,Number=A,Type=Float,Description="joint">
##INFO=<ID=AF_genomes,Number=A,Type=Float,Description="gx">
##contig=<ID=chr1,length=1000>
#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO
"""


def test_genomes_only_joint_under_e_drops_joint_af(tmp_path: Path) -> None:
    """Cross-side hole: a file defining AF_genomes but no AF_exomes is a
    joint file - under 'e' its bare AF token is the JOINT freq and must
    not emit into the exome contract field."""
    rows = _run(tmp_path, HDR_GENOMES_ONLY_JOINT,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.4;AF_genomes=0.3"], "e")
    assert _info(rows[0]) == "."


def test_genomes_only_joint_under_g_emits_genomes(tmp_path: Path) -> None:
    rows = _run(tmp_path, HDR_GENOMES_ONLY_JOINT,
                ["chr1\t100\t.\tA\tG\t.\t.\tAF=0.4;AF_genomes=0.3"], "g")
    assert _info(rows[0]) == "AF=0.3"
