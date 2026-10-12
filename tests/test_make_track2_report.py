"""Pins for tools/make_track2_report.py - the Track 2 report renderer."""
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import make_track2_report as mr  # noqa: E402


def test_refs_links_and_order():
    r = mr.Refs({"PMID:1": {"title": "A", "year": 2001}})
    assert r.link("PMID:1") == "[PMID:1](https://pubmed.ncbi.nlm.nih.gov/1/)"
    assert r.link("DOI:10.1/x") == "[DOI:10.1/x](https://doi.org/10.1/x)"
    assert r.bare(["PMID:1", None]) == r.link("PMID:1")
    assert r.cites([]) == ""
    assert r.order == ["PMID:1", "DOI:10.1/x"]
    table = r.table()
    assert "| 1 | [PMID:1]" in table and "| A | 2001 |" in table
    assert "not in cache" in table  # DOI absent from cache is flagged, not invented


def test_linkify_keeps_closing_paren_intact():
    r = mr.Refs({})
    out = r.linkify("see (PMID:42; DOI:10.5/ab)")
    assert out.endswith("(https://doi.org/10.5/ab))")


def _allele(cdna, records):
    return {"hgvs_genomic": "chr1:1 A>T", "cdna": cdna, "protein": "p.X1Y",
            "vep": {"consequence_terms": ["missense_variant"]}, "exon": {"index": 1, "of": 2},
            "clinvar": {"records": records}, "clinvar_note": "no exact record"}


def test_clinvar_row_uses_exact_cdna_record_only():
    """A position search returns other alleles at the site; the table must
    never show a neighbouring allele's classification as this variant's."""
    other = {"title": "NM_1(G):c.3006T>C (p.Asn1002=)", "classification": "Likely benign",
             "review_status": "single", "accession": "VCV1"}
    exact = {"title": "NM_1(G):c.10A>T (p.X)", "classification": "Pathogenic",
             "review_status": "multi", "accession": "VCV2"}
    m = {"alleles": [_allele("c.3006T>G", [other]), _allele("c.10A>T", [other, exact])]}
    table = mr.allele_table(m, mr.Refs({}))
    row = next(line for line in table.splitlines() if line.startswith("| ClinVar"))
    assert "Likely benign" not in row
    assert "no exact record" in row and "Pathogenic - multi (VCV2)" in row


def test_screen_counts_recomputed_from_log(tmp_path):
    md = tmp_path / "c.md"
    md.write_text("# t\n\n## 1. Systematic screen\n\n| # | Query | Retrieved | Screened | Included |\n"
                  "|---|---|---|---|---|\n| 1 | `a` | 10 | 5 | PMID:1 |\n| 2 | `b` | 0 | - | none |\n"
                  "| 3 | (from 1) | - | 1 | PMID:2 |\n\n## 2. Ranked\n\n| 1 | **x** | B | y | z |\n",
                  encoding="utf-8")
    assert mr.screen_counts(md) == {"queries": 2, "hits": 10, "screened": 6, "papers": 2}


def test_missing_inputs_render_pending():
    r = mr.Refs({})
    for fn in (mr.engine_section, mr.benchmark_section, mr.prism_section, mr.esm_section,
               mr.rejected_table, mr.testability_section):
        assert fn(None, r) == mr.PENDING
    assert mr.allele_table(None, r) == mr.PENDING


def test_fill_rejects_unfilled_placeholders():
    import pytest
    with pytest.raises(SystemExit):
        mr.fill("{{A}} {{B}}", {"A": "x"})
    assert mr.fill("{{A}} {{REFERENCES}}", {"A": "x"}) == "x {{REFERENCES}}"


def test_committed_report_is_current_and_clean():
    """The committed docs/track2_report.md has no em dash, no unfilled
    placeholder, and carries the mandated acknowledgement + disclosure."""
    text = (REPO / "docs" / "track2_report.md").read_text(encoding="utf-8")
    assert "—" not in text
    assert "{{" not in text
    assert "made possible through the Hackathon, organized by Sage Bionetworks" in text
    assert "Cognition Devin Pro" in text and "Claude Pro/Max" in text
    assert "not medical advice" in text


def test_upload_copy_is_byte_identical_to_the_report():
    """`--upload` writes the same bytes to the repo root; the citation
    gate skips the copy from its coverage scan on that promise."""
    a = REPO / "docs" / "track2_report.md"
    b = REPO / "nikhilpise_track2_report.md"
    if not b.exists():
        import pytest
        pytest.skip("upload copy not built (make track2-report)")
    assert a.read_bytes() == b.read_bytes()


def test_report_has_no_uncovered_claims():
    """GATE 7: every claim sentence in the submitted report carries a
    citation or names the artifact/registry it came from."""
    import subprocess
    out = subprocess.run(
        [sys.executable, str(REPO / "tools" / "verify_citations.py"), "--offline",
         "--coverage-strict", "--quiet", str(REPO / "docs" / "track2_report.md")],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr
