"""Track 1 submission CSV writer - the byte-exact upload contract.

Contract (verified against the vendored oracle ``scorer/evaluation.py`` and
the upload path ``hackathon-app/tabs/submit_track1.py``):

* Header::
      proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes
* Encoding: UTF-8 **without** BOM. A BOM turns the first header name into
  ``\\ufeffproband_id`` -> ``KeyError`` -> whole file rejected, so the writer
  encodes ``utf-8`` (never ``utf-8-sig``). Notes are ASCII-cleaned up front:
  a stray cp1252-only byte such as 0xE9 raises ``UnicodeDecodeError`` under
  the server's UTF-8 locale, so non-ASCII can never reach the file.
* Newlines: LF (the oracle also parses CRLF; LF chosen for deterministic
  bytes and clean diffs/hexdumps).
* One row per emitted hypothesis; total rows <= ``submission.max_rows`` (10).
* ``epcr`` strictly decreasing down the file. Ties are legal (the oracle
  breaks them by file order) but a strictly decreasing column removes all
  file-order dependence - see :data:`EPSILON`.
* ``finding_type``: ``primary`` for emitted hypotheses; ``secondary`` for
  secondary-findings rows, whose epcr is clamped to
  ``submission.secondary_epcr_cap`` (0.30). Secondary rows must stay below
  the causal pair's epcr: any variant at-or-above the top threshold enters
  the F-max union there and would destroy F=1.0 (plan.md section 6: junk
  *below* the pair's epcr is free, junk at-or-above is fatal).

Falsification: if this module ever emits a BOM, a non-ASCII byte outside
notes, a non-decreasing or out-of-range epcr column, an 11th row, or a
secondary row above the cap, ``tests/test_csv_contract.py`` and
``tests/test_adversarial.py`` go red.
"""
from __future__ import annotations

import csv
import io
import math
import re
import sys
import tempfile
from pathlib import Path

from .config import load_config
from .vcf import to_submission_chrom

REPO = Path(__file__).resolve().parents[1]

HEADER_FIELDS = (
    "proband_id", "chrom_1", "pos_1", "ref_1", "alt_1",
    "chrom_2", "pos_2", "ref_2", "alt_2",
    "epcr", "finding_type", "notes",
)

# Documented nudge applied when two rows would carry equal epcr: the later
# row is pushed down by EPSILON (clamped > 0). With <= 10 rows the total
# downward drift is < 1e-3, so a capped secondary can never reach 0 and
# ranks never depend on the oracle's file-order tie-break.
EPSILON = 1e-4

_FINDING_TYPES = ("primary", "secondary")


def _variant_tuple(v) -> tuple[str, int, str, str]:
    """Normalize one variant: ``{chrom,pos,ref,alt}`` dict or 4-tuple."""
    if isinstance(v, dict):
        c, p, r, a = v["chrom"], v["pos"], v["ref"], v["alt"]
    else:
        c, p, r, a = v
    # an empty/whitespace chrom normalizes to the ghost contig 'chr' /
    # 'chrNone' - a guaranteed non-matching FP at every F-max threshold
    if not str(c).strip():
        raise ValueError(f"variant has empty chrom: {v!r}")
    pi = int(p)
    if float(p) != pi:
        raise ValueError(f"non-integral pos {p!r} - int() would silently "
                         "shift the coordinate")
    return (str(c).strip(), pi, str(r), str(a))


def _clean_notes(value) -> str:
    """ASCII-only, single-line notes.

    A newline inside notes would split a CSV row; non-ASCII bytes would risk
    a decode failure on the server. Commas are left intact - the csv writer
    quotes them correctly and ``csv.DictReader`` reads them back.
    """
    if value is None:
        return ""
    s = str(value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", s).strip()


def _hypothesis_row(h: dict, proband_id: str, finding_type: str) -> dict:
    """One hypothesis dict -> one submission row dict (pre-epcr-fixup).

    Accepts pipeline ``ranked`` entries (keys: variants[{chrom,pos,ref,alt}],
    epcr, gene, model, notes) and the same shape for secondary findings.
    A 2-variant hypothesis fills the ``*_2`` columns; a 1-variant hypothesis
    leaves them empty.
    """
    variants = [_variant_tuple(v) for v in (h.get("variants") or [])]
    if not variants:
        raise ValueError("hypothesis has no variants; nothing to submit")
    if len(variants) > 2:
        # The format has room for exactly two variants per row; a tri-allelic
        # hypothesis is truncated to its first two variants, deterministically.
        variants = variants[:2]
    if h.get("epcr") is not None:
        epcr = float(h["epcr"])
    elif finding_type == "secondary":
        epcr = 0.5  # pre-cap placeholder; the cap clamp decides the value
    else:
        raise ValueError("primary hypothesis missing epcr - an upstream "
                         "ranking bug, not a value to invent")
    c1, p1, r1, a1 = variants[0]
    row = {
        "proband_id": proband_id,
        "chrom_1": to_submission_chrom(c1),
        "pos_1": p1,
        "ref_1": r1.strip().upper(),
        "alt_1": a1.strip().upper(),
        "chrom_2": "",
        "pos_2": "",
        "ref_2": "",
        "alt_2": "",
        "epcr": epcr,
        "finding_type": finding_type,
        "notes": _clean_notes(
            h.get("notes") or f"{h.get('gene', '')} {h.get('model', '')}"),
    }
    if len(variants) == 2:
        c2, p2, r2, a2 = variants[1]
        row.update({
            "chrom_2": to_submission_chrom(c2),
            "pos_2": p2,
            "ref_2": r2.strip().upper(),
            "alt_2": a2.strip().upper(),
        })
    return row


def build_rows(ranked: list[dict], sf_rows: list[dict] | None = None,
               cfg: dict | None = None) -> list[dict]:
    """Convert pipeline-ranked hypotheses into submission row dicts.

    * Row 1 = top emitted hypothesis (2-variant pair fills ``*_2`` columns;
      single-variant hypothesis leaves them empty).
    * Subsequent ``emitted`` hypotheses become further ``primary`` rows in
      rank order; non-emitted hypotheses are dropped.
    * ``sf_rows`` (hypothesis-shaped dicts, optional ``epcr``/``notes``) are
      appended as ``finding_type='secondary'`` with epcr clamped to
      ``submission.secondary_epcr_cap``.
    * Total rows capped at ``submission.max_rows`` (10) - overflow drops
      rows from the bottom, i.e. secondary findings first.
    * epcr is then forced strictly decreasing top-to-bottom (ties are
      nudged down by :data:`EPSILON`, clamped > 0); any row whose epcr is
      non-finite or outside ``(0, 1]`` raises ``ValueError`` instead of
      being silently clamped - that range violation is an upstream ranking
      bug, not a value to paper over.

    Falsification: if emitted ordering, the secondary cap, the 10-row cap,
    or strictly-decreasing epcr are violated, ``test_build_rows_ordering``
    fails.
    """
    cfg = cfg or load_config()
    sub = cfg.get("submission", {})
    proband_id = str(sub.get("proband_id", "PROBAND01"))
    max_rows = int(sub.get("max_rows", 10))
    sec_cap = float(sub.get("secondary_epcr_cap", 0.30))

    emitted = [h for h in (ranked or []) if h.get("emitted")]
    emitted.sort(key=lambda h: h.get("rank", 1 << 30))

    rows = [_hypothesis_row(h, proband_id, "primary") for h in emitted]
    for sf in (sf_rows or []):
        r = _hypothesis_row(sf, proband_id, "secondary")
        e = r["epcr"]
        # validate BEFORE the cap clamp: inf/>1/0/negative must not
        # silently become 0.30 (nan: 0<x comparisons are False -> raises)
        if not (0.0 < e <= 1.0):
            raise ValueError(
                f"secondary epcr {e!r} out of range (0,1] - an upstream "
                "bug, not a value to clamp")
        if e > sec_cap:
            r["epcr"] = sec_cap
        rows.append(r)

    rows = rows[:max_rows]

    prev = None
    for r in rows:
        e = float(r["epcr"])
        if not math.isfinite(e) or not (0.0 < e <= 1.0):
            raise ValueError(
                f"epcr {e!r} out of range (0,1] for row {r!r} - an "
                "upstream ranking bug, not a value to silently clamp")
        if prev is not None and e >= prev:
            e = prev - EPSILON
            if e <= 0.0:
                e = prev / 2.0
        r["epcr"] = e
        prev = e
    return rows


def _csv_cell(field: str, value) -> str:
    """Render one cell. Raises on non-ASCII outside ``notes`` (a writer bug
    must never reach the upload bytes)."""
    if value is None:
        s = ""
    elif field == "epcr":
        s = f"{float(value):.6g}"
    elif field in ("pos_1", "pos_2") and str(value) != "":
        s = str(int(str(value).strip()))
    else:
        s = str(value)
    if field == "notes":
        s = s.encode("ascii", "ignore").decode("ascii")
    s.encode("ascii", "strict")
    return s


def _validate_row(r: dict) -> None:
    """Writer-side mirror of the oracle's *parse* contract (not scoring):
    catch an unparseable row now, before it can be uploaded."""
    if not str(r.get("proband_id", "")).strip():
        raise ValueError("row missing proband_id")
    if not str(r.get("chrom_1", "")).strip():
        raise ValueError("row missing chrom_1")
    int(str(r.get("pos_1", "")).strip())  # oracle does int(pos_1)
    # alleles are mandatory content: empty ref/alt parses into a variant
    # that can only be an FP at every threshold
    if not str(r.get("ref_1", "")).strip() \
            or not str(r.get("alt_1", "")).strip():
        raise ValueError("row has empty ref_1/alt_1")
    c2_raw, p2_raw = str(r.get("chrom_2", "")), str(r.get("pos_2", ""))
    c2, p2 = c2_raw.strip(), p2_raw.strip()
    # whitespace-only fields: truthy raw but empty after strip - the
    # oracle checks raw truthiness, so it would reject the whole file
    # while we accept it; fail here instead
    if (c2_raw and not c2) or (p2_raw and not p2):
        raise ValueError(
            f"second variant fields are whitespace-only "
            f"(chrom_2={c2_raw!r}, pos_2={p2_raw!r})")
    if bool(c2) != bool(p2):
        # half-filled second variant either degrades the row to a single
        # variant in the oracle's parser (empty chrom_2) or, for a
        # whitespace-only chrom_2, becomes a ghost unmatched variant that
        # adds an FP at every F-max threshold - catch both here
        raise ValueError(
            f"second variant half-filled (chrom_2={c2!r}, pos_2={p2!r})")
    if c2:
        int(p2)
    e = float(r.get("epcr"))
    if not (0.0 < e <= 1.0):
        raise ValueError(f"epcr {e} out of range (0,1]")
    ft = str(r.get("finding_type") or "primary").strip().lower()
    if ft not in _FINDING_TYPES:
        raise ValueError(f"finding_type {ft!r} not in {_FINDING_TYPES}")


def submission_bytes(rows: list[dict]) -> bytes:
    """Produce the EXACT upload bytes for ``rows``.

    UTF-8 without BOM, the fixed 12-column header, LF newlines, ASCII-safe.
    The ``notes`` field is ASCII-cleaned (commas survive via csv quoting);
    any other non-ASCII field raises ``UnicodeEncodeError`` rather than
    shipping a file the server-side UTF-8 parser would reject.
    """
    if len(rows) > 10:
        # explicit raise, not assert - this contract must hold under -O
        raise ValueError(f"submission exceeds the 10-row cap ({len(rows)})")
    if not rows:
        # a header-only file is a guaranteed server-side reject that an
        # operator could upload by mistake - refuse to emit it
        raise ValueError("no data rows - an empty submission can never "
                         "score; refusing to emit a header-only CSV")
    for r in rows:
        _validate_row(r)
    buf = io.StringIO(newline="")
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(HEADER_FIELDS)
    for r in rows:
        w.writerow([_csv_cell(f, r.get(f, "")) for f in HEADER_FIELDS])
    return buf.getvalue().encode("utf-8")


def write_submission(path, ranked: list[dict],
                     sf_rows: list[dict] | None = None,
                     cfg: dict | None = None) -> bytes:
    """Build rows, write ``path``, and return the bytes written."""
    rows = build_rows(ranked, sf_rows=sf_rows, cfg=cfg)
    data = submission_bytes(rows)
    Path(path).write_bytes(data)
    return data


def _load_oracle():
    """Import the vendored scorer (``scorer/evaluation.py``).

    The oracle is never reimplemented - local score = official score by
    construction. Under pytest, conftest has already imported it; standalone
    use inserts ``scorer/`` on ``sys.path`` (same pattern as conftest).
    """
    if "evaluation" in sys.modules:
        m = sys.modules["evaluation"]
        # under pytest, conftest may have bound the hackathon-app copy
        # instead of scorer/ - identical bytes today, but a one-sided
        # re-vendor would silently test a stale oracle
        got = getattr(m, "__file__", "") or ""
        if str(REPO / "scorer").replace("\\", "/").lower() in \
                got.replace("\\", "/").lower():
            return m
        del sys.modules["evaluation"]
    scorer_dir = str(REPO / "scorer")
    if scorer_dir not in sys.path:
        sys.path.insert(0, scorer_dir)
    import evaluation as oracle  # vendored scoring oracle
    return oracle


def validate_submission_bytes(data: bytes, ground_truth):
    """Dev-time check: score the exact upload bytes through the vendored
    oracle exactly like the app does
    (``_score_csv_bytes``: temp file -> ``load_submission`` -> first proband
    group -> PROBAND01 check -> ``score_proband``).

    ``ground_truth``: frozenset of ``(chrom, pos, ref, alt)`` variants for
    PROBAND01 (e.g. ``conftest.GT`` or the spike-in truth). Returns the
    oracle's ``ScoreResult``; raises whatever the oracle/app path raises.

    Encoding fidelity: ``load_submission`` opens the file without an
    ``encoding`` arg, so in-process it decodes under the HOST locale
    (cp1252 on Windows) while the Linux server decodes UTF-8. Pure-ASCII
    bytes decode identically under both so the in-process path is exact;
    non-ASCII input is scored in a ``python -X utf8`` subprocess matching
    the server's locale, so a hand-edited CSV can't false-pass locally.

    Falsification: if ``submission_bytes`` output ever fails this check
    against the expected GT, the writer/oracle contract is broken - do not
    upload.
    """
    if data.isascii():
        return _validate_in_process(data, ground_truth)
    return _validate_utf8_subprocess(data, ground_truth)


def _validate_in_process(data: bytes, ground_truth):
    oracle = _load_oracle()
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        subs = oracle.load_submission(path)
        if not subs:
            raise ValueError("No valid rows found in the CSV.")
        pid = next(iter(subs))
        if pid != "PROBAND01":
            raise ValueError(
                f"Unknown proband_id '{pid}'. Only PROBAND01 is accepted.")
        return oracle.score_proband(pid, subs[pid], ground_truth)
    finally:
        Path(path).unlink(missing_ok=True)


def _validate_utf8_subprocess(data: bytes, ground_truth):
    """Score non-ASCII bytes under the server's UTF-8 locale.

    Spawns ``python -X utf8`` (same pattern as tools/audit_scorer_fixtures.py)
    so host-locale decoding can't diverge from what the app sees.
    """
    import json as _json
    import subprocess
    code = (
        "import sys,json;sys.path.insert(0,sys.argv[1]);"
        "import evaluation as ev;"
        "subs=ev.load_submission(sys.argv[2]);"
        "pid=next(iter(subs)) if subs else 'EMPTY';"
        "print('REJ:'+pid) if pid!='PROBAND01' else None;"
        "gt=frozenset(tuple(v) for v in json.loads(sys.argv[3]));"
        "r=ev.score_proband(pid,subs[pid],gt) if pid=='PROBAND01' else None;"
        "print('SCORE:'+json.dumps({'proband_id':r.proband_id,"
        "'rank_points':r.rank_points,'f_max':r.f_max,"
        "'full_match_rank':r.full_match_rank,'partial_match_rank':r.partial_match_rank,"
        "'f_max_threshold':r.f_max_threshold,'n_predictions_at_f_max':r.n_predictions_at_f_max})) if r else None"
    )
    with tempfile.NamedTemporaryFile("wb", suffix=".csv", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        gt_json = _json.dumps([list(v) for v in sorted(
            ground_truth, key=lambda v: (v[0], v[1]))])
        out = subprocess.run(
            [sys.executable, "-X", "utf8", "-c", code,
             str(REPO / "scorer"), path, gt_json],
            capture_output=True, timeout=60,
            # child writes UTF-8 under -X utf8; decode it the same way -
            # cp1252 would mojibake or crash on non-ASCII error text
            encoding="utf-8", errors="replace")
        line = (out.stdout.strip().splitlines() or [""])[-1]
        if out.returncode != 0:
            err = (out.stderr.strip().splitlines() or ["?"])[-1]
            # preserve the oracle's exception TYPE (the app surfaces them
            # verbatim) rather than collapsing everything to ValueError
            name, _, msg = err.partition(":")
            exc_map = {
                "KeyError": KeyError, "ValueError": ValueError,
                "TypeError": TypeError, "AttributeError": AttributeError,
                "UnicodeDecodeError": UnicodeDecodeError,
                "IndexError": IndexError,
            }
            cls = exc_map.get(name.strip())
            if cls is UnicodeDecodeError:
                # UnicodeDecodeError's ctor takes 5 args, not a message -
                # reconstruct it so callers see the real type
                raise UnicodeDecodeError(
                    "utf-8", data, 0, len(data), msg.strip())
            if cls is not None:
                raise cls(msg.strip().strip("'\""))
            raise ValueError(
                "oracle raised under UTF-8 server semantics: " + err)
        if line.startswith("REJ:"):
            pid = line[4:]
            if pid == "EMPTY":
                raise ValueError("No valid rows found in the CSV.")
            raise ValueError(
                f"Unknown proband_id '{pid}'. Only PROBAND01 is accepted.")
        if line.startswith("SCORE:"):
            oracle = _load_oracle()
            return oracle.ScoreResult(**_json.loads(line[6:]))
        raise ValueError("unexpected oracle output: "
                         + (out.stdout + out.stderr)[:200])
    finally:
        Path(path).unlink(missing_ok=True)
