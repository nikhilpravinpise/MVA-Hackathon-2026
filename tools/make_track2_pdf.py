"""Render the Track 2 report to PDF (the submit form takes .md or .pdf).

    python tools/make_track2_pdf.py                 # -> nikhilpise_track2_report.pdf

Markdown -> styled HTML -> headless Chrome print-to-PDF. No pandoc, no
LaTeX: markdown-it-py plus the Chrome already installed for the slide
renderer. Links stay live, tables keep their rules, and headings do not
split across pages.

The .md remains the primary artifact (it is what `--upload` writes and
what the repo tracks); this is the reading copy for the panel.
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "nikhilpise_track2_report.md"
OUT = REPO / "nikhilpise_track2_report.pdf"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
:root { --ink:#15202b; --muted:#5b6b7c; --rule:#d8e0e8; --accent:#1f6feb; }
* { box-sizing: border-box; }
body { font-family: "Segoe UI", "Inter", system-ui, sans-serif; color: var(--ink);
       font-size: 10.2pt; line-height: 1.5; margin: 0; }
h1 { font-size: 20pt; line-height: 1.2; margin: 0 0 6pt; }
h2 { font-size: 14pt; margin: 18pt 0 6pt; padding-bottom: 3pt;
     border-bottom: 1.5px solid var(--rule); break-after: avoid; }
h3 { font-size: 11.5pt; margin: 13pt 0 4pt; break-after: avoid; }
h2, h3, h4 { break-inside: avoid; }
p, li { orphans: 2; widows: 2; }
blockquote { margin: 8pt 0; padding: 7pt 11pt; background: #f4f7fa;
             border-left: 3px solid var(--accent); color: var(--ink); }
blockquote p { margin: 0; }
table { border-collapse: collapse; width: 100%; font-size: 8.4pt; margin: 8pt 0;
        break-inside: auto; }
th, td { border: 1px solid var(--rule); padding: 4pt 6pt; text-align: left;
         vertical-align: top; }
th { background: #eef3f8; font-weight: 600; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
code { font-family: Consolas, "SF Mono", monospace; font-size: 8.6pt;
       background: #f2f5f8; padding: 1px 3px; border-radius: 3px; }
a { color: var(--accent); text-decoration: none; }
hr { border: 0; border-top: 1px solid var(--rule); margin: 14pt 0; }
ul, ol { padding-left: 16pt; margin: 6pt 0; }
li { margin-bottom: 3pt; }
em { color: var(--muted); }
"""

HEADER = """<div style="font-size:7pt;color:#5b6b7c;width:100%;padding:0 16mm;">
<span>MVA Hackathon 2026 - Track 2 - nikhilpise</span></div>"""
FOOTER = """<div style="font-size:7pt;color:#5b6b7c;width:100%;padding:0 16mm;
text-align:right;"><span class="pageNumber"></span> / <span class="totalPages"></span></div>"""


def to_html(md_text: str) -> str:
    from markdown_it import MarkdownIt
    md = MarkdownIt("commonmark", {"html": True, "linkify": True}).enable("table")
    # [repo:path] markers are artifact pointers, not links - render them as code
    md_text = re.sub(r"\[repo:([^\]]+)\]", r"`\1`", md_text)
    body = md.render(md_text)
    return (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>MVA Hackathon 2026 - Track 2 - nikhilpise</title>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")


def render(html: str, out: Path) -> None:
    from playwright.sync_api import sync_playwright
    tmp = out.with_suffix(".tmp.html")
    tmp.write_text(html, encoding="utf-8")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel="chrome")
            page = browser.new_page()
            page.goto(tmp.as_uri(), wait_until="load")
            page.pdf(path=str(out), format="A4", print_background=True,
                     display_header_footer=True, header_template=HEADER,
                     footer_template=FOOTER,
                     margin={"top": "18mm", "bottom": "20mm",
                             "left": "16mm", "right": "16mm"})
            browser.close()
    finally:
        tmp.unlink(missing_ok=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", default=str(SRC))
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    src = Path(a.src)
    if not src.is_file():
        raise SystemExit(f"{src} missing - run tools/make_track2_report.py --upload first")
    text = src.read_text(encoding="utf-8")
    if "{{" in text or "PENDING" in text:
        raise SystemExit("report still has placeholders or PENDING sections")
    out = Path(a.out)
    render(to_html(text), out)
    kb = out.stat().st_size / 1024
    print(f"wrote {out.relative_to(REPO)} ({kb:.0f} KB, from {src.name}, {date.today()})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
