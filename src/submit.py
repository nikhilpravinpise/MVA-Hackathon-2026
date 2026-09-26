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
        return (str(v["chrom"]), int(v["pos"]), str(v["ref"]), str(v["alt"]))
    c, p, r, a = v
    return (str(c), int(p), str(r), str(a))


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
        "epcr": float(h.get("epcr", 0.5)),
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
      nudged down by :data:`EPSILON`, clamped > 0) and into ``(0, 1]``.

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
        if r["epcr"] > sec_cap:
            r["epcr"] = sec_cap
        rows.append(r)

    rows = rows[:max_rows]

    prev = None
    for r in rows:
        e = float(r["epcr"])
        if not (0.0 < e <= 1.0):
            e = min(max(e, EPSILON), 1.0)
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
    if str(r.get("chrom_2", "")).strip() and str(r.get("pos_2", "")).strip():
        int(str(r.get("pos_2")).strip())
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
    assert len(rows) <= 10, "submission exceeds the 10-row cap"
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
        return sys.modules["evaluation"]
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

    Falsification: if ``submission_bytes`` output ever fails this check
    against the expected GT, the writer/oracle contract is broken - do not
    upload.
    """
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
