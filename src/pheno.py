"""Phenotype layer: HPO extraction, ontology DAG, semantic similarity.

Three responsibilities:

1. ``extract_hpo_from_docx`` - pull ``HP:nnnnnnn`` terms (plus a phenotype
   table if present) out of the challenge's ``Challenge_Clinical_Phenotype_1.docx``
   without third-party deps (docx is a zip of XML).

2. ``OboOntology`` - a minimal OBO parser (``id:``, ``name:``, ``is_a:``,
   ``is_obsolete:``) that yields ancestor sets and depths. Works on the real
   ``hp.obo`` download or on small fixtures.

3. ``resnik`` / ``best_match_average`` - the HPO semantic similarity used by
   the funnel's phenotype tier (plan.md Phase 2.5). Information content is
   computed from a supplied annotation corpus (disease->HPO sets, e.g. the
   ``phenotype.hpoa`` file), so IC values are self-consistent with the exact
   annotation release in use rather than hard-coded.
"""
from __future__ import annotations

import math
import re
import zipfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

# \b anchors the match to a token boundary - "CHIP:0000118"/"XHP:..." would
# otherwise donate a false HP:0000118 term (audit LOW-8)
HPO_RE = re.compile(r"\bHP:\d{7}(?!\d)")

_W_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract_hpo_from_docx(path: str | Path) -> list[str]:
    """Extract HPO term IDs from a .docx file, in document order, deduplicated.

    Raises FileNotFoundError / ValueError on unreadable input. Only the codes
    are returned - labels require an ontology lookup (``OboOntology.name``).
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    terms: list[str] = []
    with zipfile.ZipFile(p) as z:
        names = z.namelist()
        if "word/document.xml" not in names:
            raise ValueError(f"{p}: not a docx (no word/document.xml)")
        # document body first, then headers/footers/footnotes/comments -
        # a term written in a table footer must not be missed
        parts = (["word/document.xml"]
                 + sorted(n for n in names if re.fullmatch(
                     r"word/(header|footer|footnotes|endnotes|comments)"
                     r"\d*\.xml", n)))
        for part in parts:
            try:
                root = ET.fromstring(z.read(part))
            except ET.ParseError:
                continue
            for para in root.iter(_W_NS + "p"):
                text = "".join(t.text or "" for t in para.iter(_W_NS + "t"))
                terms.extend(HPO_RE.findall(text))
    seen: set[str] = set()
    return [t for t in terms if not (t in seen or seen.add(t))]


@dataclass
class OboOntology:
    """HPO-style OBO graph: parents/children/name maps over ``is_a`` edges.

    ``alt_id`` and ``replaced_by`` terms are remapped to their primary id:
    a clinical docx written against an older HPO release must still match
    the current ontology instead of silently dropping the term."""

    name: dict[str, str] = field(default_factory=dict)
    parents: dict[str, list[str]] = field(default_factory=dict)
    obsolete: set[str] = field(default_factory=set)
    alt2primary: dict[str, str] = field(default_factory=dict)
    _ancestors: dict[str, set[str]] = field(default_factory=dict, repr=False)

    @classmethod
    def parse(cls, path: str | Path) -> "OboOntology":
        ont = cls()
        in_term = False
        # buffer per [Term] block: field order inside a term is not
        # guaranteed (id: need not precede name:/is_a: in every release),
        # so collect the whole block then emit it
        buf: dict[str, list[str] | bool] = {}

        def flush():
            tid = (buf.get("id") or [None])[0]
            if not tid:
                return
            for n in buf.get("name", []):
                ont.name[tid] = n
            for p in buf.get("is_a", []):
                ont.parents.setdefault(tid, []).append(p)
            if buf.get("is_obsolete"):
                ont.obsolete.add(tid)
            for a in buf.get("alt_id", []):
                ont.alt2primary[a] = tid
            for r in buf.get("replaced_by", []):
                ont.alt2primary[tid] = r  # obsolete -> replacement id

        for raw in Path(path).read_text(encoding="utf-8",
                                        errors="replace").splitlines():
            line = raw.strip()
            if line == "[Term]":
                flush()
                buf, in_term = {}, True
                continue
            if line.startswith("["):
                flush()
                buf, in_term = {}, False
                continue
            if not in_term or not line:
                continue
            k, _, v = line.partition(": ")
            v = v.strip()
            if k == "id":
                buf.setdefault("id", []).append(v)
            elif k == "name":
                buf.setdefault("name", []).append(v)
            elif k == "is_a":
                buf.setdefault("is_a", []).append(v.split("!")[0].strip())
            elif k == "alt_id":
                buf.setdefault("alt_id", []).append(v)
            elif k == "replaced_by":
                buf.setdefault("replaced_by", []).append(v.split()[0])
            elif k == "consider":
                buf.setdefault("replaced_by", []).append(v.split()[0])
            elif line == "is_obsolete: true":
                buf["is_obsolete"] = True
        flush()
        return ont

    @classmethod
    def from_edges(cls, edges: dict[str, list[str]],
                   names: dict[str, str] | None = None) -> "OboOntology":
        """Build from a {child: [parents]} mapping (fixtures/tests)."""
        return cls(name=names or {}, parents=dict(edges))

    def primary(self, term: str) -> str:
        """Remap alt_ids / replaced_by ids to their primary term id."""
        return self.alt2primary.get(term, term)

    def ancestors(self, term: str) -> set[str]:
        """All ancestors of ``term`` INCLUDING the term itself (memoized)."""
        term = self.primary(term)
        if term in self._ancestors:
            return self._ancestors[term]
        anc: set[str] = set()
        stack = [term]
        while stack:
            t = stack.pop()
            if t in anc:
                continue
            anc.add(t)
            stack.extend(self.parents.get(t, ()))
        self._ancestors[term] = anc
        return anc

    def valid(self, term: str) -> bool:
        term = self.primary(term)
        # an obsolete term with no replacement is not usable evidence
        if term in self.obsolete:
            return False
        return term in self.name or term in self.parents


@dataclass
class InformationContent:
    """IC(t) = -log(freq(t)/N) over an annotation corpus of term sets.

    Annotations propagate to ancestors before counting: a term's frequency is
    the number of entities annotated to it or any descendant. ``total`` is the
    number of entities in the corpus.
    """

    freq: dict[str, int] = field(default_factory=dict)
    total: int = 0

    @classmethod
    def from_annotations(cls, annotations: list[set[str]],
                         ont: OboOntology) -> "InformationContent":
        freq: dict[str, int] = {}
        for terms in annotations:
            closure: set[str] = set()
            for t in terms:
                closure |= ont.ancestors(t)
            for t in closure:
                freq[t] = freq.get(t, 0) + 1
        return cls(freq=freq, total=len(annotations))

    def ic(self, term: str) -> float:
        if self.total == 0:
            return 0.0
        f = self.freq.get(term, 0)
        if f == 0:
            return 0.0
        return -math.log(f / self.total)

    def max_ic(self) -> float:
        """IC of the rarest observed term (self-similarity normalization)."""
        if not self.freq:
            return 0.0
        return -math.log(min(self.freq.values()) / self.total)


def resnik(ont: OboOntology, ic: InformationContent, t1: str, t2: str) -> float:
    """Resnik similarity = IC of the most informative common ancestor."""
    if t1 == t2 and ic.freq.get(t1):
        return ic.ic(t1)
    common = ont.ancestors(t1) & ont.ancestors(t2)
    if not common:
        return 0.0
    return max(ic.ic(t) for t in common)


def best_match_average(ont: OboOntology, ic: InformationContent,
                       set_a: set[str], set_b: set[str],
                       ic_floor: float = 0.0) -> float:
    """Symmetric best-match-average of Resnik, normalized to [0,1].

    score = mean over each term in A of max Resnik(t, B)  (and vice versa),
    divided by the mean self-similarity ceiling so a perfect match -> 1.0.

    ``ic_floor`` drops terms whose own IC is below the floor - terms too
    common to carry phenotyping signal (e.g. 'Seizures' at IC~0) do not
    inflate the match average.
    """
    # sort before summing - set iteration order varies with PYTHONHASHSEED
    # and float addition is order-sensitive at the last ulp; pinning the
    # order keeps cross-process scores bit-identical
    a = sorted(t for t in set_a
               if ont.valid(t) and ic.ic(t) >= ic_floor)
    b = sorted(t for t in set_b
               if ont.valid(t) and ic.ic(t) >= ic_floor)
    if not a or not b:
        return 0.0

    def avg_best(x: list[str], y: list[str]) -> float:
        return sum(max(resnik(ont, ic, t, u) for u in y) for t in x) / len(x)

    sim = 0.5 * (avg_best(a, b) + avg_best(b, a))
    # normalize by the query set's OWN self-similarity ceiling (mean IC of
    # its terms) rather than the corpus-global max IC: a perfect match on
    # common-phenotype terms should still approach 1.0 - otherwise genes
    # for common-phenotype diseases can never reach the PP4 cutoff.
    ceil_a = avg_best(a, a)
    ceil_b = avg_best(b, b)
    ceil = 0.5 * (ceil_a + ceil_b)
    return min(1.0, sim / ceil) if ceil > 0 else 0.0


def load_hpoa(path: str | Path) -> dict[str, set[str]]:
    """Parse a phenotype.hpoa-style file -> {disease_id: set(HPO terms)}.

    Supports the canonical ``phenotype.hpoa`` layout (tab-separated,
    ``database_id, disease_name, qualifier, hpo_id, ...``, ``#`` comments)
    and a simple two-column ``disease_id<TAB>HP:xxxxxxx`` form. Negative
    (NOT/qualifier) annotations are dropped.
    """
    out: dict[str, set[str]] = {}
    for raw in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        if not raw or raw.startswith("#"):
            continue
        cols = raw.split("\t")
        # canonical .hpoa layout: database_id in col 0, hpo_id
        # (HP:nnnnnnn) in col 3
        if len(cols) >= 4 and HPO_RE.fullmatch(cols[3] or ""):
            if cols[2].strip().upper() == "NOT":
                continue
            # hpoa 'aspect' column (idx 9): P=phenotype, I=inheritance,
            # C=clinical course - only phenotype rows belong in the term
            # set ('HP:0000007 Autosomal recessive inheritance' etc would
            # otherwise pollute every AR disease's profile)
            if len(cols) > 9 and cols[9].strip().upper() in ("I", "C"):
                continue
            out.setdefault(cols[0], set()).add(cols[3])
        elif len(cols) >= 2 and HPO_RE.fullmatch(cols[1] or ""):
            out.setdefault(cols[0], set()).add(cols[1])
    return out


def gene_disease_map(path: str | Path) -> dict[str, list[str]]:
    """Load a {gene: [disease_id,...]} JSON map (e.g. genes_to_disease-derived)."""
    import json

    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: gene->disease map must be a JSON object")
    out: dict[str, list[str]] = {}
    for g, v in raw.items():
        if not isinstance(v, (list, tuple)):
            raise ValueError(
                f"{path}: value for gene {g!r} is {type(v).__name__}, "
                "not a list - list(v) on a string would produce a bogus "
                "disease id per character")
        bad = [d for d in v if not isinstance(d, str)]
        if bad:
            raise ValueError(
                f"{path}: non-string disease ids for gene {g!r}: "
                f"{bad!r} - they would silently match nothing downstream")
        out[g] = list(v)
    return out


def gene_hpo_terms(gene: str, gene2disease: dict[str, list[str]],
                   disease2hpo: dict[str, set[str]]) -> set[str]:
    """Union of HPO terms across all diseases mapped to ``gene``."""
    out: set[str] = set()
    for d in gene2disease.get(gene, ()):
        out |= disease2hpo.get(d, set())
    return out
