"""PRISM 19Q4 aneuploidy overlay (reported channel only, weight 0).

Joins each approved candidate onto lane L5's pharmacogenomic association
(``docs/track2/evidence/prism.json``): drug AUC vs cell-line aneuploidy
score, OLS with lineage fixed effects.  beta < 0 = cell lines with MORE
aneuploidy are MORE sensitive to the drug; q = BH FDR over the 1498
compounds screened.

It is deliberately a *reported* channel: the screen found no
FDR-significant launched drug, so it must not drive ranking (weight 0 in
the score - see config ``prism.weight`` and docs/track2/engine.md).

Match strategy: normalised drug name (case/salt/punctuation-insensitive,
LINCS alias map applied) -> PRISM ``name``; a candidate absent from the
screen is reported as ``not_in_screen``, never as a zero result.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

_SOURCE = "prism_repurposing_19q4_aneuploidy"
_INDEX_CACHE: dict[str, dict] = {}


def _norm_name(name: str) -> str:
    """Lowercase, strip salts/parentheticals and non-alnum (index key)."""
    n = (name or "").strip().lower()
    n = re.sub(r"\s*[-(][^)]*\)?\s*$", "", n)      # "-(+/-)", "(salt)"
    n = re.sub(r"\s+(hydrochloride|sulfate|sodium|mesylate|maleate|"
               r"tartrate|fumarate|phosphate|citrate|acetate|"
               r"anhydrous)\b.*$", "", n)
    n = re.sub(r"[^a-z0-9]+", "", n)
    return n


def load_index(cfg):
    """Read the prism evidence file -> ({norm_name: row}, meta).

    Returns ({}, meta) when disabled/missing - overlay degrades cleanly
    the same way the LINCS channel does.  Index is cached per resolved
    file path so benchmark cases do not re-parse the file.
    """
    pcfg = cfg.get("prism") or {}
    meta = {"source": _SOURCE, "enabled": bool(pcfg.get("enabled", True)),
            "weight": pcfg.get("weight", 0.0)}
    if not pcfg.get("enabled", True):
        meta["status"] = "disabled"
        return {}, meta
    path = Path(pcfg.get("file") or
                "docs/track2/evidence/prism.json")
    repo = Path(__file__).resolve().parents[2]
    if not path.is_absolute():
        path = repo / path
    # Evidence files are published: record the repo-relative path so the
    # committed JSON is identical on any machine (an absolute path would
    # leak the author's layout and break strict replay comparison).
    try:
        shown = path.resolve().relative_to(repo).as_posix()
    except ValueError:
        shown = str(path)  # file outside the repo (custom cfg)
    key = str(path)
    if key in _INDEX_CACHE:
        return _INDEX_CACHE[key], {**meta, "status": "ok",
                                   "file": shown,
                                   "n_rows": _INDEX_CACHE[key]["_n_rows"]}
    if not path.exists():
        meta["status"] = "missing_file"
        return {}, meta
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = (data.get("aneuploidy") or {}).get("all_results") or []
    index = {"_n_rows": len(rows)}
    for r in rows:
        nm = _norm_name(r.get("name"))
        if nm and nm not in index:
            index[nm] = r
    _INDEX_CACHE[key] = index
    return index, {**meta, "status": "ok", "file": shown,
                   "n_rows": len(rows)}


def lookup(index, names):
    """First PRISM row matching any of the candidate's names."""
    for n in names or []:
        r = index.get(_norm_name(n))
        if r is not None:
            return r
    return None


def annotate(index, names):
    """-> evidence.prism_aneuploidy payload for one candidate."""
    if not index:
        return {"beta": None, "q": None, "n_lines": None,
                "status": "unavailable"}
    r = lookup(index, names)
    if r is None:
        return {"beta": None, "q": None, "n_lines": None,
                "status": "not_in_screen"}
    return {"beta": r.get("beta"), "q": r.get("q"),
            "n_lines": r.get("n_lines"),
            "prism_name": r.get("name"),
            "screen": r.get("_screen") or "aneuploidy",
            "status": "screened"}
