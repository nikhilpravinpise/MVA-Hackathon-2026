"""Pins for tools/make_track2_pdf.py (markdown -> print-ready HTML).

The Chrome print step needs a browser, so it runs in `make track2-pdf`,
not here; these cover the conversion and the refusal paths."""
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import make_track2_pdf as mp  # noqa: E402

# markdown-it-py is a test dependency (installed via requirements.txt);
# playwright remains the optional extra for the Chrome print step, so the
# base venv stays dependency-light (same doctrine as matplotlib in
# tools/make_figures.py).
pytest.importorskip("markdown_it", reason="markdown-it-py not installed "
                    "(pip install markdown-it-py)")


def test_repo_markers_become_code_not_links():
    """[repo:path] is an artifact pointer; a PDF reader must not see it as
    a broken link."""
    html = mp.to_html("see [repo:docs/track2/evidence/prism.json] for the table")
    assert "<code>docs/track2/evidence/prism.json</code>" in html
    assert "[repo:" not in html


def test_tables_and_links_survive():
    html = mp.to_html("| a | b |\n|---|---|\n| 1 | [x](https://e.test) |\n")
    assert "<table>" in html and "<th>a</th>" in html
    assert '<a href="https://e.test">x</a>' in html


def test_print_css_keeps_tables_and_headings_together():
    html = mp.to_html("# t")
    for rule in ("@page", "thead { display: table-header-group; }",
                 "tr { break-inside: avoid; }", "break-after: avoid"):
        assert rule in html


def test_missing_source_is_refused(tmp_path):
    with pytest.raises(SystemExit, match="missing"):
        mp.main(["--src", str(tmp_path / "nope.md"), "--out", str(tmp_path / "o.pdf")])


def test_unrendered_report_is_refused(tmp_path):
    """A PENDING section or an unfilled placeholder must never reach a PDF
    that gets uploaded."""
    for bad in ("# t\n\n{{SECTION}}\n", "# t\n\nPENDING - not yet produced\n"):
        src = tmp_path / "r.md"
        src.write_text(bad, encoding="utf-8")
        with pytest.raises(SystemExit, match="placeholders or PENDING"):
            mp.main(["--src", str(src), "--out", str(tmp_path / "o.pdf")])


@pytest.mark.skipif(not (REPO / "nikhilpise_track2_report.pdf").exists(),
                    reason="PDF not built here (make track2-pdf)")
def test_built_pdf_is_a_pdf_with_pages():
    data = (REPO / "nikhilpise_track2_report.pdf").read_bytes()
    assert data.startswith(b"%PDF-")
    assert data.count(b"/Type /Page") >= 10
