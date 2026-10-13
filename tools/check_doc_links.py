"""Markdown link integrity: every relative link/image target in tracked
``.md`` files must resolve to a tracked file or directory.

    python tools/check_doc_links.py    # table, exit 1 on broken links

External URLs (scheme://, mailto:), pure ``#anchors`` and code-fenced or
inline-code content are skipped. Links are checked against
``git ls-files``, not the working tree, so a link to a gitignored
artifact (e.g. ``video/out/pitch.mp4``) fails here - that is the point:
a judge cloning the repo must be able to follow every link.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

REPO = Path(__file__).resolve().parents[1]

# [text](target), ![alt](target), and <target> angle-wrapped variants
_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?")
_ATTR = re.compile(r"(?:href|src)\s*=\s*[\"']([^\"']+)[\"']")
_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def tracked_paths() -> tuple[set[str], set[str]]:
    """(tracked files, tracked directories) as POSIX paths."""
    out = subprocess.run(
        ["git", "-C", str(REPO), "ls-files", "-z"],
        check=True, capture_output=True,
    ).stdout.decode("utf-8", errors="replace")
    files = {p for p in out.split("\0") if p}
    dirs: set[str] = set()
    for p in files:
        for parent in PurePosixPath(p).parents:
            s = str(parent)
            if s == ".":
                break
            dirs.add(s)
    return files, dirs


def _targets(text: str) -> list[str]:
    return _LINK.findall(text) + _ATTR.findall(text)


def broken_links(
    path: Path, files: set[str], dirs: set[str], root: Path | None = None
) -> list[tuple[int, str]]:
    """(line_no, target) pairs that resolve outside the tracked tree."""
    broken: list[tuple[int, str]] = []
    in_fence = False
    base = root if root is not None else REPO
    rel_dir = path.parent.relative_to(base).as_posix()
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if _FENCE.match(raw):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = _INLINE_CODE.sub("", raw)
        for target in _targets(line):
            target = target.strip()
            if not target or target.startswith("#") or _SCHEME.match(target):
                continue
            target = unquote(urlsplit(target).path).strip("/")
            if not target:
                continue
            resolved = (PurePosixPath(rel_dir) / target) if rel_dir != "." else PurePosixPath(target)
            parts: list[str] = []
            for part in resolved.parts:
                if part == "..":
                    if not parts:
                        break
                    parts.pop()
                elif part != ".":
                    parts.append(part)
            else:
                posix = "/".join(parts)
                if posix in files or posix in dirs:
                    continue
            broken.append((n, target))
    return broken


def main() -> int:
    files, dirs = tracked_paths()
    md_files = [REPO / p for p in sorted(files) if p.endswith(".md")]
    total = 0
    for path in md_files:
        for n, target in broken_links(path, files, dirs):
            total += 1
            print(f"BROKEN {path.relative_to(REPO).as_posix()}:{n} -> {target}")
    print(f"{len(md_files)} markdown files scanned, {total} broken link(s)")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
