"""Section-6 contract battery: the fixture table from docs/plan.md, ported to
pytest and executed against the vendored scoring oracle (scorer/evaluation.py)
via tests/conftest.py helpers - the same load -> first-proband -> score path
the web app uses (hackathon-app/tabs/submit_track1.py::_score_csv_bytes).

Ground truth is the conftest chr1 STAND-IN pair (firewall-safe; plan.md 2.1.5):
scorer mechanics - rank tiers, F-max union-at-threshold semantics, parsing
contract - are independent of which variants are true, so every expected
value carries over from the audit battery verbatim.

Falsification: every case asserts ONE specific score tuple or exception type;
a change in oracle semantics (or in our understanding of it) turns exactly
the affected row red. Encoding/byte-level cases (UTF-8 BOM, cp1252-only
bytes) live in tests/test_adversarial.py where the oracle runs in a
``python -X utf8`` subprocess matching the server's locale.
"""
from __future__ import annotations

import pytest

from conftest import (HEADER, JUNK, V1, V2, prow, row, score_rows, vrow)

pytestmark = pytest.mark.gate

J = JUNK  # junk variants - never intersect GT

# Expected-tuple forms:
#   ("SCORE", rank_points, f_max, full_match_rank, partial_match_rank)
#   ("EXC", "ValueError"|"KeyError")    - oracle/app path raises
#   ("APP_REJECT", "<regex>")           - app-level ValueError before scoring
#
# (name, rows, expected, header_override)
CASES = [
    # --- full match + rank tiers ---
    ("perfect pair", [prow(V1, V2, "0.95")], ("SCORE", 100.0, 1.0, 1, None), None),
    ("chr-prefix wrong", [prow(("CHR1", 1234567, "A", "G"), ("CHR1", 7654321, "C", "T"))],
     ("SCORE", 0.0, 0.0, None, None), None),
    ("no prefix", [prow(("1", 1234567, "A", "G"), ("1", 7654321, "C", "T"))],
     ("SCORE", 0.0, 0.0, None, None), None),
    ("pos off-by-one single", [vrow(("chr1", 1234568, "A", "G"))],
     ("SCORE", 0.0, 0.0, None, None), None),
    ("pos off-by-one paired", [prow(("chr1", 1234568, "A", "G"), V2)],
     ("SCORE", 50.0, 0.5, None, 1), None),
    ("ref/alt swap single", [vrow(("chr1", 1234567, "G", "A"))],
     ("SCORE", 0.0, 0.0, None, None), None),
    ("one true variant", [prow(V1, J[0])], ("SCORE", 50.0, 0.5, None, 1), None),
    # 50 pts but F=1.0: union-at-threshold ignores row structure - the
    # Remek failure mode, and why clean unions still cannot save you.
    ("pair split rows", [vrow(V1, "0.95"), vrow(V2, "0.94")],
     ("SCORE", 50.0, 1.0, None, 1), None),
    # Remek reproductions: the leaderboard's 25/0.571 signature, twice.
    ("Remek A", [vrow(J[0]), vrow(J[1]), vrow(J[2]), prow(V1, V2, "0.90")],
     ("SCORE", 25.0, 0.571, 4, None), None),
    ("Remek B", [vrow(J[0], "0.96"), vrow(V1, "0.95"), prow(V2, J[1], "0.90"),
                 vrow(J[2], "0.90")],
     ("SCORE", 25.0, 0.571, None, 2), None),
    # Junk BELOW the completing threshold cannot hurt F - only at-or-above.
    ("split-pair ordering", [vrow(V1, "0.95"), vrow(V2, "0.94"),
                             vrow(J[0], "0.30"), vrow(J[1], "0.20")],
     ("SCORE", 50.0, 1.0, None, 1), None),
    # frozenset collapses the duplicated variant -> 1-variant row -> partial.
    ("degenerate pair", [prow(V1, V1)], ("SCORE", 50.0, 0.667, None, 1), None),
    # .strip() but no .upper() on chrom: whitespace tolerated, case is not.
    ("whitespace chrom", [prow((" chr1 ", 1234567, " A ", " G "),
                               (" chr1 ", 7654321, "C", "T"))],
     ("SCORE", 100.0, 1.0, 1, None), None),
    # --- required fields / parse failures ---
    ("missing chrom_1", [row("PROBAND01", "", "", "", "", epcr="0.95")],
     ("EXC", "ValueError"), None),
    ("non-integer pos", [row("PROBAND01", "chr1", "abc", "A", "G")],
     ("EXC", "ValueError"), None),
    # --- epcr range contract (0,1] ---
    ("epcr nan", [vrow(V1, "nan")], ("EXC", "ValueError"), None),
    ("epcr inf", [vrow(V1, "inf")], ("EXC", "ValueError"), None),
    ("epcr=0", [vrow(V1, "0")], ("EXC", "ValueError"), None),
    ("epcr=1.0001", [vrow(V1, "1.0001")], ("EXC", "ValueError"), None),
    ("epcr=-0.5", [vrow(V1, "-0.5")], ("EXC", "ValueError"), None),
    ("epcr=1.0", [prow(V1, V2, "1.0")], ("SCORE", 100.0, 1.0, 1, None), None),
    ("epcr empty str", [vrow(V1, "")], ("EXC", "ValueError"), None),
    ("epcr ws-padded", [vrow(V1, " 0.95 ")], ("SCORE", 50.0, 0.667, None, 1), None),
    # --- header contract ---
    ("renamed header", [prow(V1, V2)], ("EXC", "KeyError"),
     "proband_id,chrom1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr"),
    ("minimal header true", ["PROBAND01,chr1,1234567,A,G,0.95"],
     ("SCORE", 50.0, 0.667, None, 1),
     "proband_id,chrom_1,pos_1,ref_1,alt_1,epcr"),
    ("minimal header junk", ["PROBAND01,chr2,2000000,G,A,0.95"],
     ("SCORE", 0.0, 0.0, None, None),
     "proband_id,chrom_1,pos_1,ref_1,alt_1,epcr"),
    ("epcr col absent", ["PROBAND01,chr1,1234567,A,G"], ("EXC", "KeyError"),
     "proband_id,chrom_1,pos_1,ref_1,alt_1"),
    ("extra column", [prow(V1, V2) + ",foo"], ("SCORE", 100.0, 1.0, 1, None),
     HEADER + ",extra_col"),
    ("shuffled columns", ["PROBAND01,1234567,chr1,G,A,7654321,chr1,T,C,0.95,primary,"],
     ("SCORE", 100.0, 1.0, 1, None),
     "proband_id,pos_1,chrom_1,alt_1,ref_1,pos_2,chrom_2,alt_2,ref_2,epcr,finding_type,notes"),
    # --- empty / multi-proband footguns ---
    ("header-only", [], ("APP_REJECT", "No valid rows found"), None),
    ("FAKE01 first", [vrow(J[0], pid="FAKE01"), prow(V1, V2)],
     ("APP_REJECT", "Unknown proband_id 'FAKE01'"), None),
    # Stray second proband group AFTER the real rows is silently ignored.
    ("FAKE01 after", [prow(V1, V2), vrow(J[0], "0.30", pid="FAKE01")],
     ("SCORE", 100.0, 1.0, 1, None), None),
    # ...but the >10 cap applies per proband group, ignored or not.
    ("FAKE01 after, 11 FAKE rows",
     [prow(V1, V2)] + [vrow(j, "0.30", pid="FAKE01") for j in J[:11]],
     ("EXC", "ValueError"), None),
    ("proband!=PROBAND01", [vrow(V1, pid="FAKE01")],
     ("APP_REJECT", "Unknown proband_id 'FAKE01'"), None),
    ("proband01 lowercase", [vrow(V1, pid="proband01")],
     ("APP_REJECT", "Unknown proband_id 'proband01'"), None),
    ("proband ws-padded", [vrow(V1, pid=" PROBAND01 ")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    # --- F-max epcr-structure rules ---
    ("F-max dilution first", [prow(V1, V2)] + [vrow(j) for j in J[:5]],
     ("SCORE", 100.0, 0.444, 1, None), None),
    ("F-max dilution last", [vrow(j) for j in J[:5]] + [prow(V1, V2)],
     ("SCORE", 10.0, 0.444, 6, None), None),
    ("junk below top", [prow(V1, V2)] + [vrow(j, "0.30") for j in J[:9]],
     ("SCORE", 100.0, 1.0, 1, None), None),
    # --- row cap ---
    ("10 rows ok", [prow(V1, V2)]
     + [vrow(j, f"{0.9 - i * 0.01:.2f}") for i, j in enumerate(J[:9])],
     ("SCORE", 100.0, 1.0, 1, None), None),
    ("11 rows", [vrow(j, f"{0.9 - i * 0.01:.2f}") for i, j in enumerate(J[:11])],
     ("EXC", "ValueError"), None),
    # --- finding_type enum (lowercased after strip; empty defaults primary) ---
    ("finding_type=X", [vrow(V1, ft="bogus")], ("EXC", "ValueError"), None),
    ("SECONDARY upper", [vrow(V1, ft="SECONDARY")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    ("finding_type empty", [vrow(V1, ft="")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("finding_type padded", [vrow(V1, ft=" SECONDARY ")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    # --- optional *_2 fields / silent non-matches ---
    ("blank chrom_2", [row("PROBAND01", "chr1", "1234567", "A", "G",
                           "", "", "", "")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    ("chrom_2 set pos_2 blank", [row("PROBAND01", "chr1", "1234567", "A", "G",
                                    "chr1", "", "C", "T")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    # Empty alleles still yield a real (non-matching) variant - not an error.
    ("ref_1/alt_1 empty", [row("PROBAND01", "chr1", "1234567", "", "")],
     ("SCORE", 0.0, 0.0, None, None), None),
    ("pos ws-padded", [row("PROBAND01", "chr1", " 1234567 ", "A", "G")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    # "not chrom" is checked BEFORE .strip(): whitespace-only != blank.
    ("chrom_1 ws-only", [row("PROBAND01", " ", "1234567", "A", "G")],
     ("SCORE", 0.0, 0.0, None, None), None),
    # No position range check exists - negative parses, silently scores 0.
    ("pos=-1", [row("PROBAND01", "chr1", "-1", "A", "G")],
     ("SCORE", 0.0, 0.0, None, None), None),
    # --- sort / line-ending tolerance ---
    # The docstring warns about unsorted files; the code just sorts silently.
    ("unsorted input", [vrow(J[0], "0.99"), prow(V1, V2, "0.50")],
     ("SCORE", 50.0, 0.8, 2, None), None),
    ("CRLF endings", [prow(V1, V2) + "\r"], ("SCORE", 100.0, 1.0, 1, None), None),
    ("blank trailing line", [prow(V1, V2), ""], ("SCORE", 100.0, 1.0, 1, None), None),
    # Only FULLY blank lines are skipped: a comma-only line parses to empty
    # fields -> v1 None -> ValueError -> whole file rejected.
    ("trailing comma-only line", [prow(V1, V2), ",,,,,,,,,,,"],
     ("EXC", "ValueError"), None),
]

_EXC_TYPES = {"ValueError": ValueError, "KeyError": KeyError}


@pytest.mark.parametrize(
    "name,rows,expected,hdr", CASES, ids=[c[0] for c in CASES])
def test_csv_contract(name, rows, expected, hdr):
    """Each fixture asserts one documented oracle behavior (plan.md sec.6).
    Falsification: the expected tuple/error IS the contract - a red case
    means scorer semantics drifted from what the plan documents."""
    header = hdr or HEADER
    if expected[0] == "SCORE":
        res = score_rows(rows, header=header)
        assert res.rank_points == expected[1]
        assert abs(res.f_max - expected[2]) < 1e-3
        assert res.full_match_rank == expected[3]
        assert res.partial_match_rank == expected[4]
    elif expected[0] == "APP_REJECT":
        with pytest.raises(ValueError, match=expected[1]):
            score_rows(rows, header=header)
    else:
        with pytest.raises(_EXC_TYPES[expected[1]]):
            score_rows(rows, header=header)
