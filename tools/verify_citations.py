"""Citation gate for Track 2 (track2_plan.md GATE 7: 100% citation coverage).

Scans markdown / JSON artifacts for literature identifiers, resolves each one
against NCBI E-utilities (esummary) and Crossref, and fails the gate on any id
that does not resolve, resolves to a retracted record, or disagrees with the
title/year recorded next to it in an evidence JSON. A markdown coverage pass
also flags scientific-looking claims that carry neither a literature citation
nor an explicit ``[repo:path]`` artifact reference.

    python tools/verify_citations.py                    # default scan set
    python tools/verify_citations.py docs/track2/candidates.md
    python tools/verify_citations.py --refresh          # re-pull all, rewrite cache
    python tools/verify_citations.py --coverage-strict  # uncovered claims fail too
    python tools/verify_citations.py --json out.json    # machine-readable report

Identifiers detected (canonical forms used throughout):
    PMID:<digits>   from ``PMID:123``, ``pmid 123``, pubmed.ncbi.nlm.nih.gov/123
    DOI:<doi>       from ``10.xxxx/...``, ``doi:10.x``, ``https://doi.org/10.x``
    PMC:<digits>    from ``PMCID:PMC123``, bare ``PMC1234567``

Resolution:
    * PubMed ids   -> esummary db=pubmed, batched up to 200 ids/request,
                      <=3 requests/second (NCBI unauthenticated etiquette).
    * PMC ids      -> esummary db=pmc; the linked pmid from ``articleids`` is
                      then resolved via db=pubmed so retraction state is
                      inherited from the PubMed record.
    * DOIs         -> api.crossref.org/works/<doi>.
    * Retracted    -> PubMed pubtype in RETRACTION_TYPES, or Crossref
                      ``updated-by``/``update-to`` entry of type ``retraction``,
                      or a title beginning ``RETRACTED:``.
    * Results are cached in docs/track2/citation_cache.json (committed) so
      re-runs are deterministic; ``--refresh`` re-pulls everything;
      ``--offline`` never touches the network (uncached id = unresolved).

Expected-title check: in JSON files, a dict entry keyed ``"PMID:x"`` /
``"DOI:x"`` / ``"PMC:x"`` whose value has ``title`` and/or ``year`` is an
assertion. Resolved title must fuzzy-match (normalized token Jaccard >= 0.8)
and the year must equal the resolved publication year.

Coverage check: applied to "report-type" markdown - every scanned .md except
files under agent_prompts/ or agent_reports/ and the intelligence docs in
COVERAGE_SKIP (internal notes, not submission prose). A paragraph, list item or
table row containing a number+unit, a percentage, or a mechanism verb
(inhibits/activates/reduces/increases/causes/binds/rescues, any tense) must
contain >=1 citation or ``[repo:...]`` reference. Uncovered claims are always
listed and become fatal under ``--coverage-strict``.

Exit codes: 0 clean; 1 any unresolved/retracted/mismatched id (or uncovered
claims with --coverage-strict); 2 usage / IO error. Stdlib only.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CACHE = REPO / "docs" / "track2" / "citation_cache.json"
CACHE_SCHEMA = "t2.citation_cache/1"
REPORT_SCHEMA = "t2.citation_check/1"

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
CROSSREF = "https://api.crossref.org/works/"
# Dataset DOIs (figshare, Zenodo, Dryad) are registered with DataCite, not
# Crossref; they are resolved there when Crossref has no record.
DATACITE = "https://api.datacite.org/dois/"
BATCH_SIZE = 200
MIN_INTERVAL = 0.34  # seconds between HTTP calls -> <= 3 req/s
HTTP_TIMEOUT = 30
USER_AGENT = "mva-hackathon-2026-track2/1.0 (citation verification)"

JACCARD_MIN = 0.8
RETRACTION_TYPES = {"Retracted Publication", "Retracted and Republished Article",
                    "Withdrawn Publication"}
RETRACTION_TITLE_PREFIXES = ("retracted:", "retraction:")

# Files that are intelligence/process notes rather than report prose - the
# coverage check does not apply to them.
# Intelligence notes (no scientific claims of our own), and the
# plain-language family pieces, which deliberately carry no inline
# citations - they are written for readers without a literature habit and
# point at the report, which is where every claim is sourced.
COVERAGE_SKIP_BASENAMES = {"rules_refresh.md", "landscape.md",
                           "form_map.md", "family_summary.md",
                           "status.md", "submission_fields.md",
                           # internal review notes about this package,
                           # like the agent_reports they sit beside
                           "redteam.md", "rubric_self_assessment.md",
                           # byte-identical build artifact of
                           # docs/track2_report.md (pinned by
                           # tests/test_make_track2_report.py): scanning
                           # both would count every sentence twice
                           "nikhilpise_track2_report.md"}
COVERAGE_SKIP_DIRS = {"agent_prompts", "agent_reports"}

# ---------------------------------------------------------------------------
# citation patterns
# ---------------------------------------------------------------------------
_PMID_PAT = re.compile(
    r"\bPMID\s*[:#]?\s*(\d{3,9})\b"
    r"|pubmed\.ncbi\.nlm\.nih\.gov/(\d{3,9})"
    r"|ncbi\.nlm\.nih\.gov/pubmed/(\d{3,9})",
    re.IGNORECASE)
_PMC_PAT = re.compile(
    r"\bPMCID\s*[:=]?\s*PMC?(\d{3,9})\b"
    r"|\bPMC(\d{5,9})\b"
    r"|pmc/articles/PMC(\d{3,9})",
    re.IGNORECASE)
_DOI_PAT = re.compile(r"\b(10\.\d{4,9}/[^\s\"'<>\]\},;]+)")
_EXPECT_KEY_PAT = re.compile(r"^(PMID|PMCID|PMC|DOI)\s*:\s*(.+)$", re.I)
_REPO_REF_PAT = re.compile(r"\[repo:[^\]]+\]")

_MECH_VERBS = re.compile(
    r"\b(?:inhibits?|inhibited|activates?|activated|reduces?|reduced"
    r"|increases?|increased|causes?|caused|binds?|bound|rescues?|rescued)\b",
    re.IGNORECASE)
_NUM_UNIT = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:mg|kg|g|mcg|µg|ug|ml|µl|ul|l|nM|µM|uM|mM|mmol|mol|%"
    r"|percent(?:age)?|fold|x\b|bp|kb|Mb|Gb|aa|amino acids?"
    r"|years?|yrs?|months?|weeks?|days?|hours?|hrs?|minutes?|mins?|seconds?"
    r"|patients?|participants?|subjects?|children|infants?|cases?|controls?"
    r"|variants?|alleles?|genes?|drugs?|medications?|compounds?|doses?"
    r"|cohorts?|trials?|studies|cell lines?|clones?|tumou?rs?)\b",
    re.IGNORECASE)
_CODE_SPAN = re.compile(r"`[^`]*`")
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def canonical_pmid(digits: str) -> str:
    return f"PMID:{int(digits)}"


def canonical_pmc(digits: str) -> str:
    return f"PMC:{int(digits)}"


def canonical_doi(doi: str) -> str:
    # A DOI written inside a markdown code span keeps its closing backtick
    # in the match, which would make a real DOI look unresolvable.
    doi = doi.strip().rstrip(".,;:)]}'\"`").lower()
    for pre in ("doi:", "https://doi.org/", "http://doi.org/",
                "https://dx.doi.org/", "http://dx.doi.org/", "doi.org/"):
        if doi.startswith(pre):
            doi = doi[len(pre):]
    return f"DOI:{doi}"


def cite_kind(canon: str) -> str:
    return canon.split(":", 1)[0].upper()


@dataclass
class RawCitation:
    canon: str
    file: str
    line: int
    context: str


def scan_text_for_citations(text: str, fname: str) -> list[RawCitation]:
    """All literature ids mentioned in a file's text, deduped per line."""
    out: list[RawCitation] = []
    for ln, line in enumerate(text.splitlines(), 1):
        seen_on_line: set[str] = set()
        ctx = line.strip()[:160]
        for m in _PMID_PAT.finditer(line):
            digits = next(g for g in m.groups() if g)
            c = canonical_pmid(digits)
            if c not in seen_on_line:
                seen_on_line.add(c)
                out.append(RawCitation(c, fname, ln, ctx))
        for m in _PMC_PAT.finditer(line):
            digits = next(g for g in m.groups() if g)
            c = canonical_pmc(digits)
            if c not in seen_on_line:
                seen_on_line.add(c)
                out.append(RawCitation(c, fname, ln, ctx))
        for m in _DOI_PAT.finditer(line):
            c = canonical_doi(m.group(1))
            if c not in seen_on_line:
                seen_on_line.add(c)
                out.append(RawCitation(c, fname, ln, ctx))
    return out


def iter_expectations(path: Path) -> list[tuple[str, dict, str]]:
    """``{"PMID:x": {"title": ..., "year": ...}}`` maps inside a JSON file.

    Returns (canonical_id, expected_dict, dotted_json_path) triples.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    found: list[tuple[str, dict, str]] = []

    def walk(obj, trail):
        if isinstance(obj, dict):
            for k, v in obj.items():
                m = _EXPECT_KEY_PAT.match(k) if isinstance(k, str) else None
                if m and isinstance(v, dict) and ("title" in v or "year" in v):
                    kind = m.group(1).upper()
                    raw = m.group(2).strip()
                    if kind == "PMID":
                        canon = canonical_pmid(raw)
                    elif kind in ("PMC", "PMCID"):
                        canon = canonical_pmc(raw.lstrip("PMCpmc"))
                    else:
                        canon = canonical_doi(raw)
                    found.append((canon, v, f"{trail}.{k}" if trail else k))
                walk(v, f"{trail}.{k}" if trail else str(k))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{trail}[{i}]")

    walk(data, path.name)
    return found


# ---------------------------------------------------------------------------
# resolution
# ---------------------------------------------------------------------------
class HttpClient:
    """Polite urllib client - <=3 requests/second, shared across endpoints."""

    def __init__(self, min_interval: float = MIN_INTERVAL):
        self.min_interval = min_interval
        self._last = 0.0
        self.requests: list[str] = []

    def get_json(self, url: str) -> dict | None:
        """Parsed JSON body, or None on HTTP error / timeout / bad JSON."""
        wait = self.min_interval - (time.monotonic() - self._last)
        if wait > 0:
            time.sleep(wait)
        self._last = time.monotonic()
        self.requests.append(url)
        req = urllib.request.Request(
            url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError,
                json.JSONDecodeError, TimeoutError, OSError):
            return None


def esummary_url(db: str, ids: list[str]) -> str:
    """Deterministic esummary URL (ids sorted) - stable fixture keys."""
    return (f"{EUTILS}?db={db}&retmode=json&id={','.join(sorted(ids))}")


def crossref_url(doi: str) -> str:
    return CROSSREF + urllib.parse.quote(doi, safe="")


def datacite_url(doi: str) -> str:
    return DATACITE + urllib.parse.quote(doi, safe="")


def _parse_datacite(payload: dict | None) -> dict | None:
    """DataCite JSON:API record -> resolved-entry dict, or None."""
    attrs = ((payload or {}).get("data") or {}).get("attributes") or {}
    titles = [t.get("title") for t in attrs.get("titles") or [] if t.get("title")]
    if not titles:
        return None
    rtype = (attrs.get("types") or {}).get("resourceTypeGeneral")
    return {
        "found": True,
        "title": titles[0].strip(),
        "year": attrs.get("publicationYear"),
        "pubtypes": [rtype] if rtype else [],
        "retracted": titles[0].lower().startswith(RETRACTION_TITLE_PREFIXES),
        "via": "datacite",
    }


def _year_from_pubdate(pubdate: str | None) -> int | None:
    m = re.search(r"\b(19|20)\d{2}\b", pubdate or "")
    return int(m.group(0)) if m else None


def _parse_esummary_records(payload: dict | None,
                            uid_field: str = "uids") -> dict[str, dict]:
    """uid -> normalized record. Records carrying an `error` are not found."""
    out: dict[str, dict] = {}
    result = (payload or {}).get("result") or {}
    for uid in result.get(uid_field, []):
        rec = result.get(uid) or {}
        if rec.get("error") or not rec.get("title"):
            out[uid] = {"found": False}
            continue
        pubtypes = rec.get("pubtype") or []
        out[uid] = {
            "found": True,
            "title": rec.get("title", "").strip(),
            "year": _year_from_pubdate(rec.get("pubdate")),
            "pubtypes": pubtypes,
            "retracted": any(p in RETRACTION_TYPES for p in pubtypes),
            "articleids": rec.get("articleids") or [],
        }
    return out


def _resolve_pubmed(pmids: list[str], client: HttpClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for i in range(0, len(pmids), BATCH_SIZE):
        chunk = pmids[i:i + BATCH_SIZE]
        payload = client.get_json(esummary_url("pubmed", chunk))
        recs = _parse_esummary_records(payload)
        for p in chunk:
            r = recs.get(p, {"found": False})
            r["via"] = "esummary:pubmed"
            r.pop("articleids", None)
            out[p] = r
    return out


def _resolve_pmc(pmcids: list[str], client: HttpClient,
                 resolved_pubmed: dict[str, dict]) -> dict[str, dict]:
    """PMC record via esummary db=pmc; retraction inherited from its pmid."""
    out: dict[str, dict] = {}
    linked_pmids: dict[str, str] = {}
    for i in range(0, len(pmcids), BATCH_SIZE):
        chunk = pmcids[i:i + BATCH_SIZE]
        payload = client.get_json(esummary_url("pmc", chunk))
        recs = _parse_esummary_records(payload)
        for p in chunk:
            r = recs.get(p, {"found": False})
            r["via"] = "esummary:pmc"
            pmid = next((a["value"] for a in r.get("articleids", [])
                         if a.get("idtype") == "pmid"), None)
            if pmid:
                linked_pmids[p] = pmid
            r["pmid"] = pmid
            r["retracted"] = False  # pmc records carry no pubtype
            r.pop("articleids", None)
            out[p] = r
    extra = [pmid for pmid in linked_pmids.values()
             if pmid not in resolved_pubmed]
    if extra:
        resolved_pubmed.update(_resolve_pubmed(extra, client))
    for p, pmid in linked_pmids.items():
        prec = resolved_pubmed.get(pmid) or {}
        if prec.get("retracted"):
            out[p]["retracted"] = True
        out[p]["pmid_title"] = prec.get("title")
    return out


def _resolve_dois(dois: list[str], client: HttpClient) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for doi in dois:
        payload = client.get_json(crossref_url(doi))
        msg = (payload or {}).get("message") or {}
        titles = msg.get("title") or []
        title = titles[0].strip() if titles else None
        if not title:
            dc = _parse_datacite(client.get_json(datacite_url(doi)))
            out[doi] = dc or {"found": False, "via": "crossref+datacite"}
            continue
        updates = (msg.get("updated-by") or []) + (msg.get("update-to") or [])
        retracted = (any(u.get("type") == "retraction" for u in updates)
                     or title.lower().startswith(RETRACTION_TITLE_PREFIXES))
        out[doi] = {
            "found": True,
            "title": title,
            "year": (msg.get("issued", {}).get("date-parts") or [[None]])[0][0],
            "pubtypes": [msg.get("type")] if msg.get("type") else [],
            "retracted": retracted,
            "via": "crossref",
        }
    return out


def resolve_ids(cit_ids: list[str], client: HttpClient) -> dict[str, dict]:
    """canonical id -> resolved record (found/title/year/retracted/via)."""
    pmids = sorted({c.split(":", 1)[1] for c in cit_ids
                    if c.startswith("PMID:")})
    pmcids = sorted({c.split(":", 1)[1] for c in cit_ids
                     if c.startswith("PMC:")})
    dois = sorted({c.split(":", 1)[1] for c in cit_ids
                   if c.startswith("DOI:")})
    resolved: dict[str, dict] = {}
    pubmed = _resolve_pubmed(pmids, client) if pmids else {}
    resolved.update({f"PMID:{k}": v for k, v in pubmed.items()})
    if pmcids:
        resolved.update({f"PMC:{k}": v for k, v in
                         _resolve_pmc(pmcids, client, pubmed).items()})
    if dois:
        resolved.update({f"DOI:{k}": v for k, v in
                         _resolve_dois(dois, client).items()})
    return resolved


# ---------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------
def _norm_tokens(title: str) -> set[str]:
    return {t for t in re.split(r"[^a-z0-9]+", title.lower()) if t}


def title_jaccard(a: str, b: str) -> float:
    ta, tb = _norm_tokens(a), _norm_tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def check_expectation(expected: dict, resolved: dict) -> list[str]:
    """Mismatch reasons between an expected title/year and the resolution."""
    problems = []
    exp_title = expected.get("title")
    if exp_title:
        j = title_jaccard(exp_title, resolved.get("title") or "")
        if j < JACCARD_MIN:
            problems.append(f"title jaccard {j:.2f} < {JACCARD_MIN} "
                            f"(expected {exp_title!r}, got "
                            f"{resolved.get('title')!r})")
    exp_year = expected.get("year")
    if exp_year is not None:
        if str(exp_year) != str(resolved.get("year")):
            problems.append(f"year {exp_year} != resolved "
                            f"{resolved.get('year')}")
    return problems


# ---------------------------------------------------------------------------
# markdown coverage
# ---------------------------------------------------------------------------
def _strip_code(text: str) -> str:
    return _CODE_SPAN.sub(" ", text)


# Regulator / database identifiers are first-party sources: an openFDA
# label set_id, a ChEMBL molecule id with its approval phase, a ClinVar
# accession or a gnomAD dataset tag each name where the fact came from as
# precisely as a PMID does.
_DB_SOURCE_PAT = re.compile(
    r"(set_id\s*[`:]?\s*[0-9a-f]{8}"          # openFDA label
    r"|CHEMBL\d+|max_phase\s*\d"               # ChEMBL
    r"|VCV\d{6,}"                              # ClinVar accession
    r"|gnomAD\s*v?4"                            # gnomAD release
    r"|ENST\d{11}|NM_\d+\.\d+"                 # transcript identity
    r"|AlphaFold|UniProt\s*O60566)", re.I)


def _has_citation(unit: str) -> bool:
    return bool(_PMID_PAT.search(unit) or _DOI_PAT.search(unit)
                or _PMC_PAT.search(unit) or _REPO_REF_PAT.search(unit)
                or _DB_SOURCE_PAT.search(unit))


_OPERATIONAL = re.compile(
    r"\b\d[\d,]*(?:\.\d+)?\s*"
    r"(?:[KMGT]i?B|bytes?|min(?:ute)?s?|s(?:ec(?:ond)?s?)?|h(?:ou)?rs?"
    r"|ms|vCPU|CPUs?|GPUs?|workers?|lines?|rows?|files?|tests?|commits?)\b"
    r"|\$\s*\d|\b\d+\s*(?:MB|GB)\b", re.I)


def _is_operational(sentence: str) -> bool:
    """True when every numeric trigger in the sentence is an engineering
    measurement (size, runtime, cost, worker count) and nothing in it
    asserts a mechanism."""
    if _MECH_VERBS.search(sentence):
        return False
    nums = _NUM_UNIT.findall(sentence)
    if not nums:
        return bool(_OPERATIONAL.search(sentence))
    stripped = _OPERATIONAL.sub(" ", sentence)
    return not _NUM_UNIT.search(stripped)


def _trigger_sentences(unit: str) -> list[str]:
    """Sentences in `unit` carrying a number+unit / % / mechanism verb."""
    clean = _strip_code(unit)
    hits = [s for s in _SENTENCE_SPLIT.split(clean)
            if (_NUM_UNIT.search(s) or _MECH_VERBS.search(s))
            and not s.rstrip().endswith("?")    # a question asserts nothing
            and not _is_operational(s)]         # runtimes/sizes/costs are ours
    if (not hits and not clean.rstrip().endswith(("?", ".", "!"))
            and (_NUM_UNIT.search(clean) or _MECH_VERBS.search(clean))):
        hits = [clean]  # single-line fragment without terminal punctuation
    return hits


def coverage_scan(path: Path, rel: str) -> list[dict]:
    """Uncovered scientific claims in one markdown file.

    Claim units = paragraphs, list items, table rows. Fenced code, headings,
    separators and html comments never generate units.
    """
    uncovered: list[dict] = []
    in_fence = False
    para: list[str] = []
    para_start = 0

    def flush_para(end_line: int):
        if not para:
            return
        text = " ".join(para).strip()
        if text and _trigger_sentences(text) and not _has_citation(text):
            for s in _trigger_sentences(text):
                uncovered.append({"file": rel, "line": para_start,
                                  "unit": "paragraph", "sentence": s.strip()})
        para.clear()

    lines = path.read_text(encoding="utf-8").splitlines()
    for idx, raw in enumerate(lines, 1):
        line = raw.rstrip()
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            flush_para(idx)
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not stripped:
            flush_para(idx)
            continue
        if stripped.startswith("#") or stripped.startswith("<!--"):
            flush_para(idx)
            continue
        if stripped.startswith("|"):  # table row - one claim unit each
            flush_para(idx)
            if re.fullmatch(r"\|[\s\-:|]+\|", stripped):
                continue  # separator row
            if (_trigger_sentences(stripped) and not _has_citation(stripped)):
                for s in _trigger_sentences(stripped):
                    uncovered.append({"file": rel, "line": idx,
                                      "unit": "table_row",
                                      "sentence": s.strip()})
            continue
        m = re.match(r"^(\s*(?:[-*+]|\d+\.)\s+)(.*)$", line)
        if m:  # list item - one claim unit each
            flush_para(idx)
            body = m.group(2).strip()
            if body and _trigger_sentences(body) and not _has_citation(body):
                for s in _trigger_sentences(body):
                    uncovered.append({"file": rel, "line": idx,
                                      "unit": "list_item",
                                      "sentence": s.strip()})
            continue
        if not para:
            para_start = idx
        para.append(stripped)
    flush_para(len(lines))
    return uncovered


def is_coverage_target(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    return (path.suffix.lower() == ".md"
            and path.name.lower() not in COVERAGE_SKIP_BASENAMES
            and not parts & COVERAGE_SKIP_DIRS)


# ---------------------------------------------------------------------------
# file selection + cache
# ---------------------------------------------------------------------------
def default_scan_files() -> list[Path]:
    files = set()
    t2 = REPO / "docs" / "track2"
    if t2.is_dir():
        for pat in ("**/*.md", "**/*.json"):
            files.update(p for p in t2.glob(pat) if p.is_file())
    for name in ("docs/track2_report.md", "nikhilpise_track2_report.md"):
        p = REPO / name
        if p.is_file():
            files.add(p)
    files.discard(DEFAULT_CACHE)
    return sorted(files)


def expand_paths(paths: list[str]) -> list[Path]:
    out: set[Path] = set()
    for raw in paths:
        p = Path(raw)
        if any(ch in raw for ch in "*?["):
            out.update(Path(g) for g in glob.glob(raw, recursive=True))
        elif p.is_dir():
            out.update(f for f in p.rglob("*")
                       if f.suffix.lower() in (".md", ".json"))
        elif p.is_file():
            out.add(p)
        else:
            raise FileNotFoundError(raw)
    return sorted(out)


def load_cache(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict) and isinstance(data.get("entries"), dict):
            return data["entries"]
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_cache(path: Path, entries: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schema": CACHE_SCHEMA,
               "note": "resolved-citation cache for tools/verify_citations.py; "
                       "rebuilt with --refresh, replayed with --offline",
               "entries": {k: entries[k] for k in sorted(entries)}}
    path.write_text(json.dumps(payload, indent=1, sort_keys=False)
                    + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def run(files: list[Path], *, cache_path: Path, refresh: bool, offline: bool,
        coverage_strict: bool, client: HttpClient | None = None
        ) -> tuple[dict, int]:
    """Whole gate; returns (report_dict, exit_code). Seams for tests: the
    cache_path and the HTTP client are injectable."""
    cache_entries = {} if refresh else load_cache(cache_path)
    client = client or HttpClient()
    today = time.strftime("%Y-%m-%d")

    raw: list[RawCitation] = []
    expectations: dict[str, list[dict]] = {}
    uncovered: list[dict] = []
    cache_resolved = cache_path.resolve()
    for f in files:
        if f.resolve() == cache_resolved:
            continue  # the cache is not evidence; never scan it
        rel = str(f.relative_to(REPO)).replace("\\", "/") \
            if f.is_relative_to(REPO) else str(f)
        try:
            text = f.read_text(encoding="utf-8")
        except OSError:
            continue
        raw += scan_text_for_citations(text, rel)
        if f.suffix.lower() == ".json":
            for canon, exp, trail in iter_expectations(f):
                expectations.setdefault(canon, []).append(
                    {**exp, "file": rel, "path": trail})
        if is_coverage_target(f):
            uncovered += coverage_scan(f, rel)

    locations: dict[str, list[dict]] = {}
    for rc in raw:
        locations.setdefault(rc.canon, []).append(
            {"file": rc.file, "line": rc.line, "context": rc.context})

    need = sorted(set(locations) | set(expectations))
    to_fetch = [c for c in need
                if c not in cache_entries or "found" not in cache_entries[c]]
    if to_fetch and not offline:
        resolved = resolve_ids(to_fetch, client)
        for canon, rec in resolved.items():
            entry = {k: v for k, v in rec.items()}
            entry["resolved_at"] = today
            cache_entries[canon] = entry
        save_cache(cache_path, cache_entries)
    elif refresh and not to_fetch:
        save_cache(cache_path, cache_entries)

    citations: dict[str, dict] = {}
    failures: list[dict] = []
    for canon in need:
        rec = cache_entries.get(canon, {"found": False})
        status = "ok"
        problems: list[str] = []
        if not rec.get("found"):
            status = "unresolved"
            problems.append("id did not resolve"
                            + (" (offline, not cached)" if offline else ""))
        elif rec.get("retracted"):
            status = "retracted"
            problems.append("record marked retracted at source")
        for exp in expectations.get(canon, []):
            if rec.get("found"):
                for p in check_expectation(exp, rec):
                    problems.append(f"{exp['file']}:{exp['path']}: {p}")
        if problems and status == "ok" and any("jaccard" in p or "year" in p
                                               for p in problems):
            status = "mismatch"
        entry = {
            "status": status,
            "title": rec.get("title"),
            "year": rec.get("year"),
            "retracted": bool(rec.get("retracted")),
            "via": rec.get("via"),
            "locations": locations.get(canon, []),
            "expected": [
                {k: v for k, v in e.items() if k != "file"}
                | {"file": e["file"]}
                for e in expectations.get(canon, [])],
            "problems": problems,
        }
        if rec.get("pmid"):
            entry["pmid"] = rec["pmid"]
        citations[canon] = entry
        for p in problems:
            failures.append({"citation": canon, "problem": p,
                             "status": status})

    ok = not failures and not (coverage_strict and uncovered)
    report = {
        "schema": REPORT_SCHEMA,
        "generated": today,
        "files_scanned": [str(f) for f in files],
        "counts": {
            "citations": len(citations),
            "ok": sum(1 for c in citations.values()
                      if c["status"] == "ok"),
            "unresolved": sum(1 for c in citations.values()
                              if c["status"] == "unresolved"),
            "retracted": sum(1 for c in citations.values()
                             if c["status"] == "retracted"),
            "mismatch": sum(1 for c in citations.values()
                            if c["status"] == "mismatch"),
            "uncovered_claims": len(uncovered),
            "http_requests": len(getattr(client, "requests", [])),
        },
        "citations": citations,
        "uncovered": uncovered,
        "failures": failures,
        "ok": ok,
    }
    code = 0 if ok else 1
    return report, code


def _human_summary(report: dict, code: int) -> str:
    c = report["counts"]
    lines = [
        "========== CITATION GATE ==========",
        f"files scanned      : {len(report['files_scanned'])}",
        f"citations found    : {c['citations']} "
        f"(ok {c['ok']}, unresolved {c['unresolved']}, "
        f"retracted {c['retracted']}, mismatch {c['mismatch']})",
        f"uncovered claims   : {c['uncovered_claims']}",
        f"http requests      : {c['http_requests']}",
    ]
    if report["failures"]:
        lines.append("\n---------- FAILURES ----------")
        for f_ in report["failures"]:
            locs = report["citations"][f_["citation"]]["locations"]
            at = locs[0] if locs else {}
            lines.append(f"  {f_['citation']:24s} [{f_['status']}] "
                         f"{f_['problem']}"
                         + (f"  (first seen {at.get('file')}:{at.get('line')})"
                            if at else ""))
    if report["uncovered"]:
        lines.append("\n---------- UNCOVERED CLAIMS ----------")
        for u in report["uncovered"][:60]:
            lines.append(f"  {u['file']}:{u['line']} [{u['unit']}] "
                         f"{u['sentence'][:150]}")
        if len(report["uncovered"]) > 60:
            lines.append(f"  ... and {len(report['uncovered']) - 60} more")
    lines.append("\n========== RESULT ==========")
    lines.append("PASS" if code == 0 else "FAIL")
    return "\n".join(lines)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*",
                    help="files/dirs/globs to scan (default: docs/track2/** "
                         "+ the two report files)")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE),
                    help="citation cache path (default docs/track2/"
                         "citation_cache.json)")
    ap.add_argument("--refresh", action="store_true",
                    help="re-resolve every id and rewrite the cache")
    ap.add_argument("--offline", action="store_true",
                    help="resolve from cache only; uncached ids fail")
    ap.add_argument("--coverage-strict", action="store_true",
                    help="uncovered claims fail the gate")
    ap.add_argument("--json", dest="json_out", default=None,
                    help="also write the machine-readable report here")
    ap.add_argument("--quiet", action="store_true",
                    help="suppress the human summary")
    args = ap.parse_args(argv)
    if args.offline and args.refresh:
        print("error: --offline and --refresh are mutually exclusive",
              file=sys.stderr)
        return 2

    try:
        files = expand_paths(args.paths) if args.paths \
            else default_scan_files()
    except FileNotFoundError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    if not files:
        print("error: nothing to scan", file=sys.stderr)
        return 2

    report, code = run(files, cache_path=Path(args.cache),
                       refresh=args.refresh, offline=args.offline,
                       coverage_strict=args.coverage_strict)
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(report, indent=1) + "\n", encoding="utf-8")
    if not args.quiet:
        print(_human_summary(report, code))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
