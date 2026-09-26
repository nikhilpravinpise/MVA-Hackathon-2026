"""Adversarial harness: byte-level and mutation tests over src/submit.py.

Two layers:

1. BYTE-LEVEL - raw bytes through the vendored oracle inside a
   ``python -X utf8`` subprocess, matching the Linux server's UTF-8 locale
   (this host's default cp1252 would silently decode bytes the server
   rejects). Replicates tools/audit_scorer_fixtures.py::run_bytes with the
   conftest chr1 stand-in GT.

2. MUTATION BATTERY - the real e2e check (plan.md 2.2): build a golden
   submission from a pipeline-shaped ``ranked`` list via submit.build_rows /
   submit.submission_bytes, corrupt it one way at a time, and require every
   corruption to CHANGE the score or RAISE. Mutations that legitimately
   change nothing are pinned as DOCUMENTED no-ops in ``NOOP_MUTATIONS`` -
   they assert identical output, which is itself a scorer-semantics test.

Falsification: a red mutation case means either the writer produced
something corruptible in a way the spec says must fail loudly, or oracle
semantics drifted; a red no-op case means a scorer pathway we documented
as inert (notes, finding_type, sub-threshold rows) no longer is.
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from conftest import GT, score_csv_text, vrow
from src import submit

pytestmark = pytest.mark.gate

REPO = Path(__file__).resolve().parents[1]
SCORER_DIR = REPO / "scorer"

BASELINE = (100.0, 1.0, 1, None)  # rank_points, f_max, full_rank, partial_rank


# ---------------------------------------------------------------------------
# Golden fixture: pipeline-shaped input -> byte-exact submission
# ---------------------------------------------------------------------------

def golden_ranked() -> list[dict]:
    """Synthetic ``run_pipeline`` result['ranked'] lookalike.

    True pair = conftest V1+V2 (bare '1' contigs - exercises
    to_submission_chrom normalization). Runner-ups are junk vs GT.
    Rank 4 is emitted=False - must NOT reach the file.
    """
    return [
        {"rank": 1, "gene": "ALPHG", "model": "compound_het", "score": 0.92,
         "epcr": 0.95, "emitted": True, "in_trans": "trans",
         "variants": [{"chrom": "1", "pos": 1234567, "ref": "A", "alt": "G"},
                      {"chrom": "1", "pos": 7654321, "ref": "C", "alt": "T"}]},
        {"rank": 2, "gene": "BRAVG", "model": "hom_alt", "score": 0.81,
         "epcr": 0.40, "emitted": True, "in_trans": "",
         "variants": [{"chrom": "2", "pos": 2000000, "ref": "G", "alt": "A"}]},
        {"rank": 3, "gene": "CHARL", "model": "dominant_het", "score": 0.74,
         "epcr": 0.30, "emitted": True, "in_trans": "",
         "variants": [{"chrom": "2", "pos": 2001000, "ref": "G", "alt": "A"}]},
        {"rank": 4, "gene": "DELTG", "model": "compound_het", "score": 0.60,
         "epcr": 0.20, "emitted": False, "in_trans": "unknown",
         "variants": [{"chrom": "7", "pos": 3000000, "ref": "T", "alt": "C"},
                      {"chrom": "7", "pos": 3001000, "ref": "A", "alt": "G"}]},
    ]


def golden_sf() -> list[dict]:
    """Secondary-findings rows (hypothesis-shaped). Second entry's epcr is
    above the cap on purpose - build_rows must clamp it."""
    return [
        {"variants": [{"chrom": "7", "pos": 3000000, "ref": "T", "alt": "C"}],
         "epcr": 0.30, "notes": "ACMG SF v3.3 gene; pathogenic stop"},
        {"variants": [{"chrom": "12", "pos": 4000000, "ref": "A", "alt": "G"}],
         "epcr": 0.45, "notes": "SF finding; epcr clamped to cap"},
    ]


def golden_text() -> str:
    return golden_bytes().decode("utf-8")


def golden_bytes() -> bytes:
    rows = submit.build_rows(golden_ranked(), sf_rows=golden_sf())
    return submit.submission_bytes(rows)


def _score_any(payload):
    """Score a mutated submission through the app path. ``str`` goes via
    conftest's app-emulating scorer; ``bytes`` go through
    submit.validate_submission_bytes (raw bytes -> temp file -> oracle)."""
    if isinstance(payload, bytes):
        return submit.validate_submission_bytes(payload, GT)
    return score_csv_text(payload, gt=GT)


# ---------------------------------------------------------------------------
# Byte-level: oracle inside `python -X utf8` (server locale)
# ---------------------------------------------------------------------------

_ORACLE_SNIPPET = (
    "import sys; sys.path.insert(0, sys.argv[1]);"
    "import evaluation as ev;"
    "GT=frozenset([('chr1',1234567,'A','G'),('chr1',7654321,'C','T')]);"
    "subs=ev.load_submission(sys.argv[2]);"
    "pid=next(iter(subs)) if subs else 'EMPTY';"
    "print('REJ:'+pid) if pid!='PROBAND01' else None;"
    "r=ev.score_proband(pid,subs[pid],GT) if pid=='PROBAND01' else None;"
    "print(f'SCORE:{r.rank_points}:{r.f_max:.3f}:{r.full_match_rank}:"
    "{r.partial_match_rank}') if r else None"
)


def run_oracle_subprocess(content: bytes) -> subprocess.CompletedProcess:
    """Write raw bytes to a temp CSV and run the vendored oracle under
    ``python -X utf8`` - the server's UTF-8 locale, so encoding behavior
    reflects production, not this host's cp1252 default."""
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        return subprocess.run(
            [sys.executable, "-X", "utf8", "-c", _ORACLE_SNIPPET,
             str(SCORER_DIR), path],
            capture_output=True, text=True, timeout=60)
    finally:
        Path(path).unlink(missing_ok=True)


def test_golden_bytes_clean_under_utf8_locale():
    """The exact upload bytes score 100/1.000 on the oracle under a UTF-8
    locale - the GATE-5 pre-upload check."""
    out = run_oracle_subprocess(golden_bytes())
    assert out.returncode == 0, out.stderr
    assert "SCORE:100.0:1.000:1:None" in out.stdout


def test_utf8_bom_rejected_under_utf8_locale():
    """A BOM turns header col 1 into '\\ufeffproband_id' -> KeyError.
    Falsification: if this ever parsed, the BOM footgun would be imaginary."""
    out = run_oracle_subprocess(b"\xef\xbb\xbf" + golden_bytes())
    assert out.returncode != 0
    assert "KeyError" in out.stderr


def test_cp1252_only_byte_rejected_under_utf8_locale():
    """0xE9 in notes is valid cp1252 (decodes silently on this host) but
    invalid UTF-8 -> UnicodeDecodeError on the server. Writer-side ASCII
    cleaning exists because of exactly this divergence."""
    data = golden_text().replace("pathogenic stop", "caf\u00e9 stop")
    out = run_oracle_subprocess(data.encode("cp1252"))
    assert out.returncode != 0
    assert "UnicodeDecodeError" in out.stderr


def test_writer_bytes_clean(tmp_path):
    """submission_bytes output: no BOM, pure ASCII, parses to the expected
    score through the oracle on the exact bytes."""
    rows = submit.build_rows(golden_ranked(), sf_rows=golden_sf())
    data = submit.submission_bytes(rows)
    assert not data.startswith(b"\xef\xbb\xbf")
    data.decode("ascii")  # raises if any byte > 127
    assert b"\r\n" not in data  # LF newlines
    res = submit.validate_submission_bytes(data, GT)
    assert (res.rank_points, res.f_max, res.full_match_rank,
            res.partial_match_rank) == BASELINE
    # write_submission round-trips the identical bytes through disk.
    p = tmp_path / "team_armb-funnel.csv"
    returned = submit.write_submission(p, golden_ranked(),
                                       sf_rows=golden_sf())
    assert p.read_bytes() == returned == data


# ---------------------------------------------------------------------------
# Mutation battery: every corruption must change the score or raise
# ---------------------------------------------------------------------------

def _map_col(line: str, idx: int, fn) -> str:
    cols = line.split(",")
    if cols[idx]:
        cols[idx] = fn(cols[idx])
    return ",".join(cols)


def _mut_pair_row(text: str, *col_fns) -> str:
    """Apply (col_idx, fn) pairs to data row 1 (the GT pair row)."""
    lines = text.splitlines()
    for idx, fn in col_fns:
        lines[1] = _map_col(lines[1], idx, fn)
    return "\n".join(lines) + "\n"


def m_chr_upper(t):
    """chr1 -> CHR1 in the pair row (case-sensitivity trap)."""
    return _mut_pair_row(t, (1, str.upper), (5, str.upper))


def m_no_prefix(t):
    """chr1 -> 1 in the pair row (coordinate-convention trap)."""
    strip = lambda v: v[3:] if v.startswith("chr") else v
    return _mut_pair_row(t, (1, strip), (5, strip))


def m_pos_plus1(t):
    """pos+1 on every variant field of the pair row."""
    return _mut_pair_row(t, (2, lambda v: str(int(v) + 1)),
                         (6, lambda v: str(int(v) + 1)))


def m_swap_ref_alt(t):
    """Swap ref/alt on both variants of the pair row."""
    lines = t.splitlines()
    c = lines[1].split(",")
    c[3], c[4] = c[4], c[3]
    c[7], c[8] = c[8], c[7]
    lines[1] = ",".join(c)
    return "\n".join(lines) + "\n"


def m_epcr_zero(t):
    return _mut_pair_row(t, (9, lambda v: "0"))


def m_epcr_over(t):
    return _mut_pair_row(t, (9, lambda v: "1.0001"))


def m_epcr_nan(t):
    return _mut_pair_row(t, (9, lambda v: "nan"))


def m_11_rows(t):
    """Append junk rows until the file holds 11 data rows."""
    lines = t.splitlines()
    i = 0
    while len(lines) - 1 < 11:
        lines.append(vrow(("chr3", 5000000 + i, "G", "A"), epcr="0.10"))
        i += 1
    return "\n".join(lines) + "\n"


def m_ft_bogus(t):
    return _mut_pair_row(t, (10, lambda v: "bogus"))


def m_pid_lower(t):
    """First row's proband_id -> 'proband01': first proband group is no
    longer PROBAND01, so the app path rejects the whole file."""
    return _mut_pair_row(t, (0, lambda v: "proband01"))


def m_bom(t):
    return b"\xef\xbb\xbf" + t.encode("utf-8")


def m_comma_line(t):
    """A ',,,,,,,,,,,' line is not blank: parses to empty fields -> ValueError."""
    return t + ",,,,,,,,,,,\n"


def m_secondary_epcr_high(t):
    """Push both secondary rows up to the pair's epcr (0.95): they join the
    F-max union at the top threshold and dilute F - rank points survive
    because the pair still sits first among the ties."""
    lines = t.splitlines()
    for i in range(1, len(lines)):
        cols = lines[i].split(",")
        if cols[10] == "secondary":
            cols[9] = "0.95"
            lines[i] = ",".join(cols)
    return "\n".join(lines) + "\n"


MUTATIONS = [
    ("chrom upper CHR", m_chr_upper, ("SCORE", 0.0, 0.0, None, None)),
    ("chrom prefix dropped", m_no_prefix, ("SCORE", 0.0, 0.0, None, None)),
    ("pos +1 all variants", m_pos_plus1, ("SCORE", 0.0, 0.0, None, None)),
    ("ref/alt swap", m_swap_ref_alt, ("SCORE", 0.0, 0.0, None, None)),
    ("epcr=0", m_epcr_zero, ("EXC", "ValueError")),
    ("epcr=1.0001", m_epcr_over, ("EXC", "ValueError")),
    ("epcr=nan", m_epcr_nan, ("EXC", "ValueError")),
    ("11 rows", m_11_rows, ("EXC", "ValueError")),
    ("finding_type=bogus", m_ft_bogus, ("EXC", "ValueError")),
    ("proband_id lowercase", m_pid_lower, ("EXC", "ValueError")),
    ("BOM prepended", m_bom, ("EXC", "KeyError")),
    ("comma-only line", m_comma_line, ("EXC", "ValueError")),
    ("secondary epcr->0.95", m_secondary_epcr_high,
     ("SCORE", 100.0, 0.667, 1, None)),
]

_EXC_TYPES = {"ValueError": ValueError, "KeyError": KeyError}


@pytest.mark.parametrize("name,mut,expected", MUTATIONS,
                         ids=[c[0] for c in MUTATIONS])
def test_mutation_changes_score_or_raises(name, mut, expected):
    """plan.md 2.2 mutation check on the golden submission. Falsification:
    a corruption that leaves the score untouched and is NOT on the
    documented no-op list means a scorer pathway we failed to model."""
    text = golden_text()
    mutated = mut(text)
    if expected[0] == "EXC":
        with pytest.raises(_EXC_TYPES[expected[1]]):
            _score_any(mutated)
    else:
        res = _score_any(mutated)
        got = (res.rank_points, round(res.f_max, 3), res.full_match_rank,
               res.partial_match_rank)
        assert got != BASELINE, f"mutation {name!r} changed nothing"
        assert got == expected[1:]


# ---------------------------------------------------------------------------
# DOCUMENTED no-op mutations: corruptions the oracle provably ignores.
# These assert IDENTICAL output - if one ever diverges, a scorer pathway we
# documented as inert has changed. This list is the explicit "allowed
# no-op" register required by plan.md 2.2.
# ---------------------------------------------------------------------------

def n_notes_rewrite(t):
    """notes is informational only - never read by the scorer."""
    lines = t.splitlines()
    cols = lines[1].split(",")
    cols[11] = "completely different note text"
    lines[1] = ",".join(cols)
    return "\n".join(lines) + "\n"


def n_blank_line(t):
    """Fully blank lines are skipped by csv.DictReader."""
    return t + "\n"


def n_ft_secondary_on_pair(t):
    """finding_type is informational only - does not affect the score."""
    return _mut_pair_row(t, (10, lambda v: "secondary"))


def n_swap_runnerups(t):
    """Reordering rows still yields the same ranks - the oracle re-sorts by
    epcr descending, so file order only matters within an epcr tie."""
    lines = t.splitlines()
    lines[2], lines[3] = lines[3], lines[2]
    return "\n".join(lines) + "\n"


def n_corrupt_runnerup(t):
    """Corrupting a sub-threshold row is invisible: the variant was not in
    GT before or after, so fp/fn counts are unchanged at every threshold."""
    lines = t.splitlines()
    cols = lines[2].split(",")
    cols[1] = cols[1].upper()      # chr2 -> CHR2 on the rank-2 runner-up
    cols[2] = str(int(cols[2]) + 1)
    lines[2] = ",".join(cols)
    return "\n".join(lines) + "\n"


def n_secondary_epcr_lower(t):
    """Lowering a secondary epcr (0.30 -> 0.10) keeps it below the pair's
    threshold; every F-max sweep set and every rank is unchanged."""
    lines = t.splitlines()
    for i in range(1, len(lines)):
        cols = lines[i].split(",")
        if cols[10] == "secondary":
            cols[9] = "0.10"
            lines[i] = ",".join(cols)
    return "\n".join(lines) + "\n"


NOOP_MUTATIONS = [
    ("notes rewrite", n_notes_rewrite),
    ("blank line appended", n_blank_line),
    ("pair finding_type->secondary", n_ft_secondary_on_pair),
    ("runner-up order swap", n_swap_runnerups),
    ("runner-up variant corrupted", n_corrupt_runnerup),
    ("secondary epcr lowered", n_secondary_epcr_lower),
]


@pytest.mark.parametrize("name,mut", NOOP_MUTATIONS,
                         ids=[c[0] for c in NOOP_MUTATIONS])
def test_documented_noop_mutations(name, mut):
    """Mutations the oracle provably ignores must stay provably ignored."""
    res = _score_any(mut(golden_text()))
    assert (res.rank_points, round(res.f_max, 3), res.full_match_rank,
            res.partial_match_rank) == BASELINE


# ---------------------------------------------------------------------------
# build_rows / submission_bytes writer-side invariants
# ---------------------------------------------------------------------------

def test_build_rows_ordering():
    """Row-contract invariants on the golden input. Falsification: catches
    epcr ties/inversions, secondary-cap breaches, >10 rows, a missing pair
    variant in row 1, or an unprefixed chrom."""
    rows = submit.build_rows(golden_ranked(), sf_rows=golden_sf())
    epcrs = [float(r["epcr"]) for r in rows]
    assert all(b < a for a, b in zip(epcrs, epcrs[1:])), epcrs
    sec = [r for r in rows if r["finding_type"] == "secondary"]
    assert len(sec) == 2
    assert all(float(r["epcr"]) <= 0.30 for r in sec)
    assert len(rows) <= 10
    # emitted=False hypothesis must not reach the file
    prim = [r for r in rows if r["finding_type"] == "primary"]
    assert len(prim) == 3
    # row 1 = the pair, both variants, chr-prefixed
    r1 = rows[0]
    assert (r1["chrom_1"], int(r1["pos_1"]), r1["ref_1"], r1["alt_1"]) == \
        ("chr1", 1234567, "A", "G")
    assert (r1["chrom_2"], int(r1["pos_2"]), r1["ref_2"], r1["alt_2"]) == \
        ("chr1", 7654321, "C", "T")
    for r in rows:
        assert r["chrom_1"].startswith("chr")
        assert not r["chrom_2"] or r["chrom_2"].startswith("chr")


def test_build_rows_caps_and_nudges():
    """Falsification: the 10-row cap must drop from the bottom and equal
    epcrs must come out strictly decreasing (never a silent tie)."""
    many = [{"rank": i + 1, "gene": f"G{i}", "model": "dominant_het",
             "score": 0.9, "epcr": 0.50, "emitted": True, "in_trans": "",
             "variants": [{"chrom": "3", "pos": 1000 + i, "ref": "A",
                           "alt": "G"}]}
            for i in range(15)]
    sf = [{"variants": [{"chrom": "7", "pos": 1, "ref": "T", "alt": "C"}],
           "epcr": 0.99, "notes": "over-cap secondary"}]
    rows = submit.build_rows(many, sf_rows=sf)
    assert len(rows) == 10                       # 15 emitted + 1 sf -> 10
    assert all(r["finding_type"] == "primary" for r in rows)  # sf dropped
    epcrs = [float(r["epcr"]) for r in rows]
    assert all(b < a for a, b in zip(epcrs, epcrs[1:]))
    assert all(0 < e <= 1 for e in epcrs)

    # secondary survives under the cap path and is clamped, then nudged
    rows = submit.build_rows(golden_ranked()[:1], sf_rows=golden_sf())
    sec = [r for r in rows if r["finding_type"] == "secondary"]
    assert [float(r["epcr"]) for r in sec] == [0.30, 0.30 - submit.EPSILON]


def test_writer_notes_and_nonascii():
    """Commas in notes survive via csv quoting; non-ASCII is stripped from
    notes but raises anywhere else. Falsification: a quoting slip would
    shift columns and break parsing; an ASCII slip could ship a byte the
    server cannot decode."""
    sf = [{"variants": [{"chrom": "7", "pos": 1, "ref": "T", "alt": "C"}],
           "epcr": 0.30, "notes": "BRCA2-like, caf\u00e9 evidence"}]
    rows = submit.build_rows(golden_ranked()[:1], sf_rows=sf)
    data = submit.submission_bytes(rows)
    assert b"\xe9" not in data and "caf\u00e9".encode() not in data
    res = submit.validate_submission_bytes(data, GT)
    assert res.rank_points == 100.0 and res.f_max == 1.0

    bad = submit.build_rows(golden_ranked()[:1])
    bad[0]["chrom_1"] = "chr\u00e9"
    with pytest.raises(UnicodeEncodeError):
        submit.submission_bytes(bad)
