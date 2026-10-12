"""Tests for tools/verify_citations.py - the Track 2 citation gate.

Fully network-free: every API payload is a recorded fixture under
tests/fixtures/track2/citations/ (real esummary / Crossref responses captured
2026-10-12 via the tool's own URL builders). FixtureClient fails loudly on any
URL that was not recorded, so a live request can never slip into the suite.

Fixture ids (chosen on-domain where possible):
    PMID:15475955  Hanks et al. 2004 - biallelic BUB1B -> MVA (clean)
    PMID:22048312  Baker et al. 2011 - p16 senescent-cell clearance (clean)
    PMID:23602569  p21 in BubR1 progeroid mice (clean; linked to PMC3785294)
    PMID:9500320   Wakefield 1998 Lancet - Retracted Publication
    PMID:99999999  nonexistent (esummary returns an error record)
    PMC:3785294    PMC copy of PMID:23602569; PMC:99999999 nonexistent
    DOI:10.1038/nature10600                 Baker 2011 (clean)
    DOI:10.1016/s0140-6736(97)11096-0       Wakefield (retracted)
    DOI:10.9999/definitely.not.real         404
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import verify_citations as vc  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "track2" / "citations"

HANKS = "Constitutional aneuploidy and cancer predisposition caused by " \
        "biallelic mutations in BUB1B."


class FixtureClient(vc.HttpClient):
    """HttpClient that replays recorded {url -> response} fixtures.

    Exact URL match wins. For NCBI esummary URLs not recorded verbatim the
    response is SYNTHESIZED by filtering a recorded batch from the same db
    down to the requested ids - deterministic, and faithful because esummary
    records are keyed by uid. A request whose ids were never recorded, or
    any non-esummary URL outside the map, raises AssertionError instead of
    touching the network.
    """

    def __init__(self, *names: str):
        super().__init__(min_interval=0)
        self._map: dict[str, tuple[int, dict | None]] = {}
        self._esummary: dict[str, dict] = {}  # db -> uid -> record
        for f in sorted(FIXTURES.glob("*.json")):
            if names and f.stem not in names:
                continue
            rec = json.loads(f.read_text(encoding="utf-8"))
            self._map[rec["url"]] = (rec["status"], rec["response"])
            body = rec["response"] or {}
            result = body.get("result") or {}
            m = re.search(r"[?&]db=(\w+)", rec["url"])
            if m and result.get("uids") is not None:
                db = self._esummary.setdefault(m.group(1), {})
                for uid in result["uids"]:
                    db[uid] = result[uid]

    def get_json(self, url: str):  # noqa: D102 - replay, never fetch
        self.requests.append(url)
        if url in self._map:
            status, body = self._map[url]
            return body if status == 200 else None
        m = re.search(r"[?&]db=(\w+)", url)
        ids = re.search(r"[?&]id=([0-9,]+)", url)
        if m and ids and m.group(1) in self._esummary:
            db = self._esummary[m.group(1)]
            want = ids.group(1).split(",")
            missing = [u for u in want if u not in db]
            assert not missing, (
                f"esummary ids never recorded for db={m.group(1)}: "
                f"{missing}")
            result = {u: db[u] for u in want}
            result["uids"] = want
            return {"header": {"type": "esummary", "version": "0.3"},
                    "result": result}
        raise AssertionError(
            f"unrecorded URL (would hit the network): {url}")


def _write(tmp_path: Path, name: str, text: str) -> Path:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def _run(files, tmp_path, client, **kw):
    return vc.run(files, cache_path=tmp_path / "citation_cache.json",
                  client=client,
                  refresh=kw.pop("refresh", False),
                  offline=kw.pop("offline", False),
                  coverage_strict=kw.pop("coverage_strict", False), **kw)


# ---------------------------------------------------------------------------
# pattern extraction
# ---------------------------------------------------------------------------
def test_pattern_extraction():
    """Every citation syntax in the spec maps to its canonical form."""
    text = "\n".join([
        "Hanks PMID:15475955; pmid 22048312; PMID# 23602569",
        "see https://pubmed.ncbi.nlm.nih.gov/15475955/ and PMCID:PMC3785294",
        "bare PMC3785294 and doi:10.1038/nature10600",
        "link https://doi.org/10.1016/S0140-6736(97)11096-0 end",
    ])
    canons = {r.canon for r in vc.scan_text_for_citations(text, "x.md")}
    assert {"PMID:15475955", "PMID:22048312", "PMID:23602569",
            "PMC:3785294", "DOI:10.1038/nature10600",
            "DOI:10.1016/s0140-6736(97)11096-0"} <= canons


def test_doi_trailing_punct_stripped():
    """A DOI inside punctuation/markdown must not carry trailing junk."""
    text = "drug (10.1038/nature10600).\nother [x](https://doi.org/10.1038/nature10600)"
    canons = {r.canon for r in vc.scan_text_for_citations(text, "x.md")}
    assert "DOI:10.1038/nature10600" in canons
    assert all(")" not in c for c in canons if c.startswith("DOI:"))


# ---------------------------------------------------------------------------
# resolution against fixtures
# ---------------------------------------------------------------------------
def test_pubmed_resolution_fields():
    """esummary records parse into title/year/retracted correctly."""
    client = FixtureClient()
    res = vc.resolve_ids(
        ["PMID:15475955", "PMID:22048312", "PMID:23602569",
         "PMID:9500320", "PMID:99999999"], client)
    assert res["PMID:15475955"]["title"] == HANKS
    assert res["PMID:15475955"]["year"] == 2004
    assert not res["PMID:15475955"]["retracted"]
    assert res["PMID:22048312"]["year"] == 2011
    assert res["PMID:9500320"]["retracted"], "Wakefield must flag retracted"
    assert not res["PMID:99999999"]["found"], "nonexistent id must not resolve"


def test_doi_resolution_fields():
    """Crossref records parse; retraction detected via updated-by + title."""
    client = FixtureClient()
    res = vc.resolve_ids(
        ["DOI:10.1038/nature10600",
         "DOI:10.1016/s0140-6736(97)11096-0",
         "DOI:10.9999/definitely.not.real"], client)
    good = res["DOI:10.1038/nature10600"]
    assert good["found"] and good["year"] == 2011 and not good["retracted"]
    assert res["DOI:10.1016/s0140-6736(97)11096-0"]["retracted"]
    assert not res["DOI:10.9999/definitely.not.real"]["found"]


def test_pmc_inherits_pmid_retraction():
    """A PMC id resolves via db=pmc and pulls retraction state from its pmid."""
    client = FixtureClient()
    res = vc.resolve_ids(["PMC:3785294", "PMC:99999999"], client)
    rec = res["PMC:3785294"]
    assert rec["found"] and "BubR1" in rec["title"]
    assert rec["pmid"] == "23602569" and not rec["retracted"]
    assert not res["PMC:99999999"]["found"]
    # the linked pmid fetch is a real (recorded) second request
    assert any("db=pubmed" in u for u in client.requests)


# ---------------------------------------------------------------------------
# expectation (title/year) checks
# ---------------------------------------------------------------------------
def test_jaccard_threshold():
    """Fuzzy title matching: reordering passes, a different paper fails."""
    a = "Constitutional aneuploidy and cancer predisposition caused by " \
        "biallelic mutations in BUB1B"
    assert vc.title_jaccard(a, HANKS) >= 0.8
    shuffled = "Biallelic mutations in BUB1B caused constitutional " \
               "aneuploidy and cancer predisposition"
    assert vc.title_jaccard(a, shuffled) >= 0.8
    assert vc.title_jaccard(a, "A completely unrelated paper title") < 0.8


def test_expectation_ok_and_mismatch(tmp_path):
    """Evidence JSON cite maps: right title+year passes, wrong ones fail."""
    ok_json = _write(tmp_path, "evidence.json", json.dumps({
        "cites": {"PMID:15475955": {"title": HANKS, "year": 2004}}}))
    bad_json = _write(tmp_path, "bad.json", json.dumps({
        "cites": {"PMID:15475955": {
            "title": "An unrelated title about electrochemistry",
            "year": 1999}}}))
    client = FixtureClient()
    rep, code = _run([ok_json], tmp_path, client)
    assert code == 0, rep["failures"]
    rep, code = _run([bad_json], tmp_path, client)
    assert code == 1
    cit = rep["citations"]["PMID:15475955"]
    assert cit["status"] == "mismatch"
    assert any("jaccard" in p for p in cit["problems"])
    assert any("year" in p for p in cit["problems"])


# ---------------------------------------------------------------------------
# end-to-end gate
# ---------------------------------------------------------------------------
def test_gate_pass_fail_and_cache_replay(tmp_path):
    """Clean doc passes with code 0, writes the cache, and an --offline
    re-run replays it with ZERO http requests."""
    md = _write(tmp_path, "mechanism.md",
                "Biallelic BUB1B mutations cause mosaic variegated aneuploidy "
                "(PMID:15475955).\n\nSenescent-cell clearance delays ageing "
                "phenotypes in mice (PMID:22048312).\n")
    client = FixtureClient()
    rep, code = _run([md], tmp_path, client)
    assert code == 0
    assert rep["counts"]["citations"] == 2
    assert (tmp_path / "citation_cache.json").exists()

    # second run, offline: every id must come from the written cache; a
    # fresh client asserts zero requests leave the gate
    rep2, code2 = _run([md], tmp_path, FixtureClient(), offline=True)
    assert code2 == 0
    assert rep2["counts"]["http_requests"] == 0


def test_gate_fails_on_retracted_and_unresolved(tmp_path):
    """A retracted citation and an unresolvable id each fail the gate."""
    bad = _write(tmp_path, "claims.md",
                 "Vaccines cause autism (PMID:9500320).\n\n"
                 "Ghosts exist (PMID:99999999).\n")
    rep, code = _run([bad], tmp_path, FixtureClient())
    assert code == 1
    assert rep["citations"]["PMID:9500320"]["status"] == "retracted"
    assert rep["citations"]["PMID:99999999"]["status"] == "unresolved"


def test_offline_uncached_id_fails(tmp_path):
    """--offline with an empty cache cannot verify anything -> unresolved."""
    md = _write(tmp_path, "x.md", "Claim (PMID:15475955).\n")
    rep, code = _run([md], tmp_path, FixtureClient(), offline=True)
    assert code == 1
    assert rep["citations"]["PMID:15475955"]["status"] == "unresolved"
    assert rep["counts"]["http_requests"] == 0


# ---------------------------------------------------------------------------
# coverage detector
# ---------------------------------------------------------------------------
COVERAGE_MD = """# Report

Dasatinib reduces senescent cell burden in progeroid mice.

Dasatinib reduces senescent cell burden in progeroid mice (PMID:22048312).

The approved dose is 100 mg once daily.

The approved dose is 100 mg once daily [repo:docs/track2/evidence/x.json].

| drug | effect |
|---|---|
| sirolimus | increases autophagic flux |
| sirolimus | increases autophagic flux (PMID:23602569) |

```python
x = "reduces increases causes"  # code never triggers
```
"""


def test_coverage_detector(tmp_path):
    """Claims with a number+unit or mechanism verb but no citation/[repo:]
    are listed; cited twins and code fences are not."""
    md = _write(tmp_path, "report.md", COVERAGE_MD)
    uncovered = vc.coverage_scan(md, "report.md")
    sents = [u["sentence"] for u in uncovered]
    assert any("Dasatinib reduces" in s and "PMID" not in s for s in sents)
    assert any("100 mg" in s and "repo:" not in s for s in sents)
    assert any("autophagic flux" in s and "PMID" not in s for s in sents)
    assert sum("PMID" in s for s in sents) == 0
    assert sum("repo:" in s for s in sents) == 0
    assert not any("code never" in s for s in sents)
    assert len(uncovered) == 3


def test_coverage_strict_flag(tmp_path):
    """Uncovered claims only fail the gate under --coverage-strict."""
    md = _write(tmp_path, "report.md",
                "Dasatinib reduces senescent cell burden (PMID:22048312).\n\n"
                "The dose is 100 mg daily.\n")
    rep, code = _run([md], tmp_path, FixtureClient())
    assert code == 0 and rep["counts"]["uncovered_claims"] == 1
    rep, code = _run([md], tmp_path, FixtureClient(), coverage_strict=True)
    assert code == 1 and rep["counts"]["uncovered_claims"] == 1


def test_coverage_skip_sets(tmp_path):
    """Intelligence docs and agent_* dirs are not report prose."""
    assert not vc.is_coverage_target(
        REPO / "docs" / "track2" / "rules_refresh.md")
    assert not vc.is_coverage_target(
        REPO / "docs" / "track2" / "agent_prompts" / "L4_rigor.md")
    assert not vc.is_coverage_target(
        REPO / "docs" / "track2" / "agent_reports" / "L4.md")
    assert vc.is_coverage_target(REPO / "docs" / "track2" / "mechanism.md")
    assert vc.is_coverage_target(REPO / "nikhilpise_track2_report.md")


def test_cli_end_to_end(tmp_path, capsys):
    """The CLI wiring: exit code, human summary, JSON report."""
    md = _write(tmp_path, "claims.md",
                "Senescent-cell clearance delays ageing (PMID:22048312).\n")
    cache = tmp_path / "cache.json"
    out = tmp_path / "report.json"
    import tools.verify_citations  # noqa: F401 (already imported as vc)
    # main() uses the real HttpClient; run the gate body via run() above is
    # covered - here we check arg plumbing with a fixture-patched client.
    orig = vc.HttpClient
    vc.HttpClient = FixtureClient
    try:
        code = vc.main([str(md), "--cache", str(cache),
                        "--json", str(out)])
    finally:
        vc.HttpClient = orig
    assert code == 0
    rep = json.loads(out.read_text(encoding="utf-8"))
    assert rep["schema"] == vc.REPORT_SCHEMA and rep["ok"]
    assert "PASS" in capsys.readouterr().out
