"""Audit battery: recompute every expected score/error in docs/plan.md section 6
against the vendored scorer (hackathon-app/evaluation.py).

Purpose
-------
docs/plan.md section 6 is a test *specification*. This script is the executable
proof that each documented expected value is what the real scorer actually
produces. Re-run it whenever evaluation.py is re-vendored or the table is
edited.

    python tools/audit_scorer_fixtures.py          # exits 0 if all pass

Note on GT: the ground-truth frozenset below is a STAND-IN pair, not the real
answer key. Scorer mechanics (rank tiers, F-max union semantics, parsing
contracts) are independent of which variants are true - any frozenset
exercises the same code paths. The real answer is decided by the pipeline,
never by this file.
"""
import os
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "hackathon-app"))
import evaluation as ev  # noqa: E402

GT = frozenset([("chr9", 90000001, "A", "G"), ("chr9", 90000002, "C", "T")])
V1 = ("chr9", 90000001, "A", "G")
V2 = ("chr9", 90000002, "C", "T")
HEADER = "proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes"


def run(rows_csv, header=HEADER):
    """Emulate the app path: load_submission -> first-proband check -> score_proband."""
    with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as f:
        f.write(header + "\n")
        for r in rows_csv:
            f.write(r + "\n")
        path = f.name
    try:
        subs = ev.load_submission(path)
        if not subs:
            return ("APP_REJECT", "No valid rows found in the CSV.")
        pid = next(iter(subs))
        if pid != "PROBAND01":
            return ("APP_REJECT", f"Unknown proband_id '{pid}'. Only PROBAND01 is accepted.")
        r = ev.score_proband(pid, subs[pid], GT)
        return ("SCORE", r.rank_points, round(r.f_max, 3), r.full_match_rank, r.partial_match_rank)
    except Exception as e:
        return ("EXC", type(e).__name__, str(e)[:90])
    finally:
        os.unlink(path)


def row(pid, c1, p1, r1, a1, c2="", p2="", r2="", a2="", epcr="0.95", ft="primary", notes=""):
    return ",".join([pid, c1, p1, r1, a1, c2, p2, r2, a2, epcr, ft, notes])


def vrow(v, epcr="0.95", pid="PROBAND01", ft="primary"):
    return row(pid, v[0], str(v[1]), v[2], v[3], epcr=epcr, ft=ft)


def prow(v1, v2, epcr="0.95", pid="PROBAND01"):
    return row(pid, v1[0], str(v1[1]), v1[2], v1[3], v2[0], str(v2[1]), v2[2], v2[3], epcr=epcr)


def _pair_line():
    return prow(V1, V2, "0.95")


J = [("chr1", 1000000 + i, "A", "C") for i in range(1, 12)]

# (name, rows, expected-tuple | "EXC:Type" | ("APP_REJECT", msg), header_override)
tests = [
    ("perfect pair", [prow(V1, V2, "0.95")], ("SCORE", 100.0, 1.0, 1, None), None),
    ("chr-prefix wrong", [prow(("CHR9", 90000001, "A", "G"), ("CHR9", 90000002, "C", "T"))], ("SCORE", 0.0, 0.0, None, None), None),
    ("no prefix", [prow(("9", 90000001, "A", "G"), ("9", 90000002, "C", "T"))], ("SCORE", 0.0, 0.0, None, None), None),
    ("pos off-by-one single", [vrow(("chr9", 90000011, "A", "G"))], ("SCORE", 0.0, 0.0, None, None), None),
    ("pos off-by-one paired", [prow(("chr9", 90000011, "A", "G"), V2)], ("SCORE", 50.0, 0.5, None, 1), None),
    ("ref/alt swap single", [vrow(("chr9", 90000001, "G", "A"))], ("SCORE", 0.0, 0.0, None, None), None),
    ("one true variant", [prow(V1, J[0])], ("SCORE", 50.0, 0.5, None, 1), None),
    ("pair split rows", [vrow(V1, "0.95"), vrow(V2, "0.94")], ("SCORE", 50.0, 1.0, None, 1), None),
    ("Remek A", [vrow(J[0]), vrow(J[1]), vrow(J[2]), prow(V1, V2, "0.90")], ("SCORE", 25.0, 0.571, 4, None), None),
    ("Remek B", [vrow(J[0], "0.96"), vrow(V1, "0.95"), prow(V2, J[1], "0.90"), vrow(J[2], "0.90")], ("SCORE", 25.0, 0.571, None, 2), None),
    ("split-pair ordering", [vrow(V1, "0.95"), vrow(V2, "0.94"), vrow(J[0], "0.30"), vrow(J[1], "0.20")], ("SCORE", 50.0, 1.0, None, 1), None),
    ("degenerate pair", [prow(V1, V1)], ("SCORE", 50.0, 0.667, None, 1), None),
    ("whitespace chrom", [prow((" chr9 ", 90000001, " A ", " G "), (" chr9 ", 90000002, " C ", " T "))], ("SCORE", 100.0, 1.0, 1, None), None),
    ("missing chrom_1", [row("PROBAND01", "", "", "", "", epcr="0.95")], "EXC:ValueError", None),
    ("non-integer pos", [row("PROBAND01", "chr9", "abc", "A", "G")], "EXC:ValueError", None),
    ("epcr nan", [vrow(V1, "nan")], "EXC:ValueError", None),
    ("epcr inf", [vrow(V1, "inf")], "EXC:ValueError", None),
    ("epcr=1.0", [prow(V1, V2, "1.0")], ("SCORE", 100.0, 1.0, 1, None), None),
    ("renamed header", [prow(V1, V2)], "EXC:KeyError", "proband_id,chrom1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr"),
    ("minimal header true", ["PROBAND01,chr9,90000001,A,G,0.95"], ("SCORE", 50.0, 0.667, None, 1),
     "proband_id,chrom_1,pos_1,ref_1,alt_1,epcr"),
    ("minimal header junk", ["PROBAND01,chr1,1000001,A,C,0.95"], ("SCORE", 0.0, 0.0, None, None),
     "proband_id,chrom_1,pos_1,ref_1,alt_1,epcr"),
    ("epcr col absent", ["PROBAND01,chr9,90000001,A,G"], "EXC:KeyError",
     "proband_id,chrom_1,pos_1,ref_1,alt_1"),
    ("header-only", [], ("APP_REJECT", "No valid rows found in the CSV."), None),
    ("FAKE01 first", [vrow(J[0], pid="FAKE01"), prow(V1, V2)],
     ("APP_REJECT", "Unknown proband_id 'FAKE01'. Only PROBAND01 is accepted."), None),
    ("FAKE01 after", [prow(V1, V2), vrow(J[0], "0.30", pid="FAKE01")], ("SCORE", 100.0, 1.0, 1, None), None),
    ("F-max dilution first", [prow(V1, V2)] + [vrow(j) for j in J[:5]], ("SCORE", 100.0, 0.444, 1, None), None),
    ("F-max dilution last", [vrow(j) for j in J[:5]] + [prow(V1, V2)], ("SCORE", 10.0, 0.444, 6, None), None),
    ("junk below top", [prow(V1, V2)] + [vrow(j, "0.30") for j in J[:9]], ("SCORE", 100.0, 1.0, 1, None), None),
    ("epcr=0", [vrow(V1, "0")], "EXC:ValueError", None),
    ("epcr=1.0001", [vrow(V1, "1.0001")], "EXC:ValueError", None),
    ("epcr=-0.5", [vrow(V1, "-0.5")], "EXC:ValueError", None),
    ("10 rows ok", [prow(V1, V2)] + [vrow(j, f"{0.9 - i * 0.01:.2f}") for i, j in enumerate(J[:9])], ("SCORE", 100.0, 1.0, 1, None), None),
    ("11 rows", [vrow(j, f"{0.9 - i * 0.01:.2f}") for i, j in enumerate(J[:11])], "EXC:ValueError", None),
    ("finding_type=X", [vrow(V1, ft="bogus")], "EXC:ValueError", None),
    ("SECONDARY upper", [vrow(V1, ft="SECONDARY")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("blank chrom_2", [row("PROBAND01", "chr9", "90000001", "A", "G", "", "", "", "")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("unsorted input", [vrow(J[0], "0.99"), prow(V1, V2, "0.50")], ("SCORE", 50.0, 0.8, 2, None), None),
    ("proband!=PROBAND01", [vrow(V1, pid="FAKE01")],
     ("APP_REJECT", "Unknown proband_id 'FAKE01'. Only PROBAND01 is accepted."), None),
    # boundary cases beyond the section-6 table
    ("epcr empty str", [vrow(V1, "")], "EXC:ValueError", None),
    ("epcr ws-padded", [vrow(V1, " 0.95 ")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("proband ws-padded", [vrow(V1, pid=" PROBAND01 ")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("FAKE01 after, 11 FAKE rows", [prow(V1, V2)] + [vrow(j, "0.30", pid="FAKE01") for j in J[:11]], "EXC:ValueError", None),
    ("finding_type empty", [vrow(V1, ft="")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("ref_1/alt_1 empty", [row("PROBAND01", "chr9", "90000001", "", "")], ("SCORE", 0.0, 0.0, None, None), None),
    ("pos ws-padded", [row("PROBAND01", "chr9", " 90000001 ", "A", "G")], ("SCORE", 50.0, 0.667, None, 1), None),
    # file-level / byte-level edge cases (verified against evaluation.py parse path)
    ("finding_type padded", [vrow(V1, ft=" SECONDARY ")], ("SCORE", 50.0, 0.667, None, 1), None),
    ("chrom_1 ws-only", [row("PROBAND01", " ", "90000001", "A", "G")], ("SCORE", 0.0, 0.0, None, None), None),
    ("pos=-1", [row("PROBAND01", "chr9", "-1", "A", "G")], ("SCORE", 0.0, 0.0, None, None), None),
    ("chrom_2 set pos_2 blank", [row("PROBAND01", "chr9", "90000001", "A", "G", "chr9", "", "C", "T")],
     ("SCORE", 50.0, 0.667, None, 1), None),
    ("proband01 lowercase", [vrow(V1, pid="proband01")],
     ("APP_REJECT", "Unknown proband_id 'proband01'. Only PROBAND01 is accepted."), None),
    ("trailing comma-only line", [prow(V1, V2), ",,,,,,,,,,,"], "EXC:ValueError", None),
    ("extra column", [prow(V1, V2) + ",foo"], ("SCORE", 100.0, 1.0, 1, None),
     "proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes,extra_col"),
    ("shuffled columns", ["PROBAND01,90000001,chr9,G,A,90000002,chr9,T,C,0.95,primary,"],
     ("SCORE", 100.0, 1.0, 1, None),
     "proband_id,pos_1,chrom_1,alt_1,ref_1,pos_2,chrom_2,alt_2,ref_2,epcr,finding_type,notes"),
    ("CRLF endings", ["PROBAND01,chr9,90000001,A,G,chr9,90000002,C,T,0.95,primary,\r"], ("SCORE", 100.0, 1.0, 1, None), None),
    ("blank trailing line", [prow(V1, V2), ""], ("SCORE", 100.0, 1.0, 1, None), None),
]

# Byte-level fixtures - written raw, not through the text harness
BYTE_TESTS = [
    ("UTF-8 BOM prefix", b"\xef\xbb\xbf" + (HEADER + "\n" + _pair_line() + "\n").encode("utf-8"),
     "EXC:KeyError"),
    ("cp1252-only byte in notes",
     (HEADER + "\n" + _pair_line() + "caf\xe9 note\n").encode("cp1252"),
     "EXC:UnicodeDecodeError"),
]

def run_bytes(content):
    """Byte-level harness: write raw bytes, then run the VENDORED oracle in a
    `python -X utf8` subprocess - matching the Linux server's UTF-8 locale so
    encoding behavior reflects production, not this host's cp1252 default."""
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(content)
        path = f.name
    code = (
        "import sys; sys.path.insert(0, sys.argv[1]);"
        "import evaluation as ev;"
        "GT=frozenset([('chr9',90000001,'A','G'),('chr9',90000002,'C','T')]);"
        "subs=ev.load_submission(sys.argv[2]);"
        "pid=next(iter(subs)) if subs else 'EMPTY';"
        "print('REJ:'+pid) if pid!='PROBAND01' else None;"
        "r=ev.score_proband(pid,subs[pid],GT) if pid=='PROBAND01' else None;"
        "print(f'SCORE:{r.rank_points}:{r.f_max:.3f}:{r.full_match_rank}:{r.partial_match_rank}') if r else None"
    )
    import subprocess
    try:
        out = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code, str(REPO / "hackathon-app"), path],
            capture_output=True, text=True, timeout=60)
        line = (out.stdout.strip().splitlines() or [""])[-1]
        if out.returncode != 0 or line.startswith("Traceback"):
            err = (out.stderr.strip().splitlines() or ["?"])[-1]
            return ("EXC", err.split(":")[0].strip(), err[:90])
        if line.startswith("REJ:"):
            return ("APP_REJECT", f"Unknown proband_id '{line[4:]}'. Only PROBAND01 is accepted.")
        if line.startswith("SCORE:"):
            _, rp, fm, fr, pr = line.split(":")
            return ("SCORE", float(rp), round(float(fm), 3),
                    int(fr) if fr != "None" else None, int(pr) if pr != "None" else None)
        return ("EXC", "UnexpectedOutput", (out.stdout + out.stderr)[:90])
    except Exception as e:
        return ("EXC", type(e).__name__, str(e)[:90])
    finally:
        os.unlink(path)


fails = []
for name, rows, exp, hdr in tests:
    got = run(rows, header=hdr) if hdr else run(rows)
    if isinstance(exp, str) and exp.startswith("EXC:"):
        ok = got[0] == "EXC" and exp[4:] == got[1]
    elif exp[0] == "APP_REJECT":
        ok = got[0] == "APP_REJECT" and got[1] == exp[1]
    else:
        ok = (got[0] == "SCORE" and got[1] == exp[1] and abs(got[2] - exp[2]) < 0.001
              and got[3] == exp[3] and got[4] == exp[4])
    if not ok:
        fails.append((name, exp, got))
    print(("OK  " if ok else "FAIL"), f"{name:34s}", "exp:", exp, " got:", got)

for name, content, exp in BYTE_TESTS:
    got = run_bytes(content)
    ok = isinstance(exp, str) and exp.startswith("EXC:") and got[0] == "EXC" and exp[4:] == got[1]
    if not ok:
        fails.append((name, exp, got))
    print(("OK  " if ok else "FAIL"), f"{name:34s}", "exp:", exp, " got:", got)

if fails:
    print("\nFAILURES:", fails)
    sys.exit(1)
print(f"\nALL {len(tests) + len(BYTE_TESTS)} FIXTURES VERIFIED against vendored evaluation.py")
