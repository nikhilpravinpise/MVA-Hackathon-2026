"""Every relative link/image in tracked markdown must resolve to a
tracked file or directory - a judge cloning the repo should never hit a
dead link. External URLs and anchors are out of scope."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import check_doc_links as cdl  # noqa: E402


def test_no_broken_doc_links_in_repo():
    files, dirs = cdl.tracked_paths()
    broken = [
        (p.relative_to(REPO).as_posix(), n, t)
        for p in (REPO / f for f in sorted(files) if f.endswith(".md"))
        for n, t in cdl.broken_links(p, files, dirs)
    ]
    assert broken == []


def test_broken_link_is_caught(tmp_path):
    (tmp_path / "ok.md").write_text("ok\n")
    doc = tmp_path / "sub" / "doc.md"
    doc.parent.mkdir()
    doc.write_text(
        "see [missing](gone.md), [fine](../ok.md), [external](https://x.dev)\n"
        "and `not a [link](nope.md)` plus fenced:\n"
        "```\n[also not a link](missing.md)\n```\n"
        "![img](../ok.md) and [dir](../sub)\n"
    )
    files = {"ok.md", "sub/doc.md"}
    dirs = {"sub"}
    broken = cdl.broken_links(doc, files, dirs, root=tmp_path)
    # only the genuinely dead target is flagged; code, fences, anchors,
    # external URLs, file and directory links all pass
    assert broken == [(1, "gone.md")]


def test_link_extraction_returns_raw_targets():
    line = '[a](x.md) ![c](z.png) [d](#anchor) [e](mailto:a@b.c)'
    # anchors and scheme URLs surface here; broken_links() filters them
    assert cdl._targets(line) == ["x.md", "z.png", "#anchor", "mailto:a@b.c"]
