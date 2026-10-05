"""Public-release pre-flight: is this repo's whole history safe to
publish? Run before flipping the repo to public (rules: repos must be
public at close or forfeit judging).

Two scan classes:

1. Scrub-derived identifier scan. The privacy commit (default
   ``--scrub-commit 20c8b3f``) is the authoritative record of WHICH
   identifiers were removed from the working tree. This tool derives
   that identifier set at runtime - tokens removed by the scrub commit
   that never re-appeared - then scans every added line in
   ``git log -p --all`` for them. Nothing identifier-like is hard-coded
   here, and previews are truncated (``--show`` prints tokens verbatim,
   for local eyes only).

   Findings are classified:
   * ``HISTORY-ONLY`` - token appears in history but not at HEAD: the
     pre-scrub snapshot still readable via old commits (the commit
     265b686 class of finding). Remediation options are printed.
   * ``HEAD-PRESENT`` - token exists at HEAD: an accepted identifier
     (e.g. dataset accession kept intentionally where reproduction
     requires it). Review, then accept or remove.

2. Generic sweeps over HEAD + history: HF tokens, private-key blocks,
   Synapse IDs, email addresses (noreply/github excluded), absolute
   home-dir paths, and blobs > 1 MB in history.

Exit 0 always unless a secrets-class finding is present (exit 1) - this
is a decision aid for the operator, not a CI gate.

    python tools/public_release_check.py [--show]
                                       [--out docs/public_release_audit.md]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# tokens shorter than this or matching generic words never count as
# identifiers
_STOP = re.compile(
    r"^(the|and|for|with|that|this|from|have|has|were|was|are|not|all|"
    r"but|see|http|https|www|com|org|www\.|hackathon|hackathon-app|"
    r"patient|variant|variants|report|docs|None|True|False)$",
    re.IGNORECASE)

GENERIC_PATTERNS = [
    ("hf_token", re.compile(r"hf_[A-Za-z0-9]{20,}")),
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY")),
    ("synapse_id", re.compile(r"\bsyn\d{5,}\b")),
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@(?!users\.noreply\.github\.com)"
        r"[A-Za-z0-9-]+\.[A-Za-z]{2,}\b")),
    ("home_path", re.compile(r"[A-Z]:\\Users\\[\w.-]+")),
]
SECRETS_CLASSES = {"hf_token", "private_key"}


def _git(*args) -> str:
    r = subprocess.run(["git", *args], cwd=REPO, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {r.stderr[:300]}")
    return r.stdout


def scrub_tokens(commit: str) -> dict[str, str]:
    """Return {token: sha8} for tokens REMOVED by the scrub commit that
    do not appear in the added lines of the same hunk."""
    diff = _git("show", commit, "--format=", "--", "docs")
    removed, added = set(), set()
    for line in diff.splitlines():
        if line.startswith("---") or line.startswith("+++"):
            continue
        toks = set(re.findall(r"[A-Za-z0-9][\w./:@-]{3,}", line[1:]))
        if line.startswith("-"):
            removed |= toks
        elif line.startswith("+"):
            added |= toks
    out = {}
    for t in sorted(removed - added):
        if _STOP.match(t) or t.startswith(("http", "www.")):
            continue
        out[t] = hashlib.sha1(t.encode()).hexdigest()[:8]
    return out


def head_tokens() -> str:
    """All tracked file content at HEAD as one blob (membership test)."""
    blob = []
    for rel in _git("ls-files").splitlines():
        p = REPO / rel
        if not p.is_file() or p.stat().st_size > 2_000_000:
            continue
        try:
            raw = p.read_bytes()
            if b"\x00" in raw[:8192]:  # binary - regex noise only
                continue
            blob.append(raw.decode("utf-8", errors="ignore"))
        except OSError:
            pass
    return "\n".join(blob)


def all_added_tokens_since(commit: str) -> set[str]:
    """Union of tokens added by the scrub commit and everything after it
    (all commits not ancestors of <commit>^) - 'reintroduced later' is
    membership in this set."""
    out = set()
    log = _git("log", "--all", "--not", f"{commit}^", "--format=", "-p")
    for line in log.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            out |= set(re.findall(r"[A-Za-z0-9][\w./:@-]{3,}", line[1:]))
    return out


def token_locations(tokens, cap=50):
    """Per token: up to `cap` (commit, path, line-no) locations where it
    appears in a history added-line."""
    locs = defaultdict(list)
    log = _git("log", "--all", "--format=COMMIT:%h", "-p")
    commit, path = "?", "?"
    lineno = 0
    for line in log.splitlines():
        if line.startswith("COMMIT:"):
            commit = line[7:]
        elif line.startswith("+++ b/"):
            path = line[6:]
            lineno = 0
        elif line.startswith("@@"):
            m = re.search(r"\+(\d+)", line)
            lineno = int(m.group(1)) - 1 if m else 0
        elif line.startswith("+") and not line.startswith("+++"):
            lineno += 1
            body = line[1:]
            for tok in tokens:
                if tok in body and len(locs[tok]) < cap:
                    locs[tok].append((commit, path, lineno))
        elif not line.startswith("-"):
            lineno += 1  # context lines advance the new-file counter
    return locs


def scan_generic(text_by_label: list[tuple[str, str]]):
    """Run GENERIC_PATTERNS over labeled text blobs; yield
    (label, class, match)."""
    for label, text in text_by_label:
        for name, rx in GENERIC_PATTERNS:
            for m in rx.finditer(text):
                yield label, name, m.group(0)


def large_blobs(limit=1_000_000):
    """Objects in history larger than `limit` bytes."""
    objs = _git("rev-list", "--objects", "--all")
    sized = subprocess.run(
        ["git", "cat-file", "--batch-check=%(objectname) "
         "%(objecttype) %(objectsize)"],
        cwd=REPO, input=objs, capture_output=True, text=True).stdout
    sizes = {}
    for l in sized.splitlines():
        parts = l.split()
        if len(parts) == 3 and parts[1] == "blob":
            sizes[parts[0]] = int(parts[2])
    rows = []
    for l in objs.splitlines():
        sha, _, p = l.partition(" ")
        if sizes.get(sha, 0) > limit:
            rows.append((sizes[sha], p))
    return sorted(rows, reverse=True)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="public-release pre-flight audit")
    ap.add_argument("--scrub-commit", default="20c8b3f")
    ap.add_argument("--show", action="store_true",
                    help="print scrubbed tokens verbatim (local use)")
    ap.add_argument("--out", default=None,
                    help="optional markdown report path")
    args = ap.parse_args(argv)

    tokens = scrub_tokens(args.scrub_commit)
    head = head_tokens()
    post = all_added_tokens_since(args.scrub_commit)
    head_set = {t for t in tokens if t in head}
    # true history-only: scrubbed out AND never re-added after the scrub
    hist_set = {t for t in tokens if t not in head and t not in post}
    readded = {t for t in tokens if t not in head and t in post}

    findings = token_locations(hist_set)
    generic = sorted(set(scan_generic(
        [("HEAD", head),
         ("history", _git("log", "--all", "-p", "--format="))])))
    blobs = large_blobs()

    lines = ["# Public-release audit", "",
             f"scrub commit: `{args.scrub_commit}`; "
             f"{len(tokens)} scrubbed tokens "
             f"({len(hist_set)} history-only, {len(head_set)} still "
             f"present at HEAD, {len(readded)} scrubbed-then-readded)",
             ""]
    secrets_hit = False
    lines.append(f"## HISTORY-ONLY tokens ({len(findings)} found)")
    lines += ["Identifiers removed by the scrub commit that still live "
              "in earlier commits - the public-history question this "
              "audit exists to answer.", ""]
    for tok in sorted(hist_set):
        locs = findings.get(tok, [])
        preview = tok if args.show else \
            f"{tok[:2]}...({len(tok)}ch sha:{tokens[tok]})"
        loc_txt = "; ".join(f"{c}:{p}:{n}" for c, p, n in locs[:6])
        lines.append(f"- `{preview}` at {loc_txt}"
                     + (f" (+{len(locs)-6} more)" if len(locs) > 6
                        else ""))
    lines += ["", f"## HEAD-PRESENT tokens ({len(head_set)})",
              "Scrubbed strings that exist at HEAD - accepted identifiers "
              "(e.g. dataset accessions kept where reproduction requires "
              "them); review and confirm.", ""]
    for tok in sorted(head_set):
        preview = tok if args.show else \
            f"{tok[:2]}...({len(tok)}ch sha:{tokens[tok]})"
        lines.append(f"- `{preview}`")
    lines += ["", f"## Scrubbed-then-reintroduced ({len(readded)})",
              "Tokens removed by the scrub that re-appeared in later "
              "commits' added lines - either prose coincidence or a "
              "re-leak; review.", ""]
    for tok in sorted(readded):
        preview = tok if args.show else \
            f"{tok[:2]}...({len(tok)}ch sha:{tokens[tok]})"
        lines.append(f"- `{preview}`")
    lines.append("")
    lines.append(f"## Generic sweeps ({len(generic)} hits)")
    for label, cls, m in generic[:200]:
        if cls in SECRETS_CLASSES:
            secrets_hit = True
        show = m if (args.show or cls in ("email", "home_path")) \
            else f"{m[:3]}...({len(m)}ch)"
        lines.append(f"- {cls} in {label}: `{show}`")
    lines += ["", f"## Blobs > 1 MB in history ({len(blobs)})"]
    for size, p in blobs[:50]:
        lines.append(f"- {size / 1e6:.1f} MB  `{p}`")
    lines += ["", "## Remediation options for HISTORY-ONLY findings", "",
              "1. **Accept** - the dataset is gated-public and the "
              "identifier class is already disclosed by the dataset "
              "itself; document the decision in docs/decisions.md.",
              "2. **Rewrite** - `git filter-repo --replace-text` on the "
              "token list, force-push (invalidates every commit hash "
              "cited across docs/decisions/llm_log - those citations "
              "must be re-mapped or footnoted).",
              "3. **Fresh repo** - new repo, single clean squash commit "
              "(loses all audit-trail history - weakest option for a "
              "repo whose value IS the trail).", ""]
    text = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {args.out}")
    else:
        print(text)
    if secrets_hit:
        print("\nSECRETS-CLASS FINDINGS PRESENT - do not publish until "
              "rotated/removed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
