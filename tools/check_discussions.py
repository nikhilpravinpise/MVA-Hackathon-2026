"""Discussions-watch: list new HF Discussions on the hackathon Space +
dataset since a given date (plan.md Phase-0 cadence item).

Read-only, unauthenticated - the public HF API exposes discussion lists
for public repos. Zero-dependency (urllib only).

    python tools/check_discussions.py                # all threads
    python tools/check_discussions.py --since 2026-10-01
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date

REPOS = [
    ("space", "SageBio/rare-disease-real-kid-mva-hackathon-2026"),
    ("dataset", "SageBio/mva-hackathon-2026-data"),
]
API = "https://huggingface.co/api/{kind}s/{repo}/discussions?p={page}"


def fetch(kind: str, repo: str) -> list[dict]:
    """Discussion list entries across pages; stops at `count`."""
    out = []
    for page in range(50):
        url = API.format(kind=kind, repo=repo, page=page)
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.loads(r.read().decode())
        out += d["discussions"]
        if len(out) >= d.get("count", 0) or not d["discussions"]:
            break
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default=None,
                    help="YYYY-MM-DD; only threads created/updated after")
    args = ap.parse_args(argv)
    since = date.fromisoformat(args.since) if args.since else None

    found = 0
    for kind, repo in REPOS:
        try:
            threads = fetch(kind, repo)
        except Exception as e:
            print(f"{repo}: fetch failed ({e}) - offline?", file=sys.stderr)
            return 2
        for t in threads:
            created = date.fromisoformat(t["createdAt"][:10])
            if since and created < since:
                continue
            found += 1
            flags = (" PR" if t.get("isPullRequest") else "") + \
                    (" PINNED" if t.get("pinned") else "")
            print(f"[{repo}] #{t.get('num')} {t.get('title')!r} "
                  f"by {t.get('author', {}).get('name', '?')} "
                  f"created {created} "
                  f"({t.get('numComments', 0)} comments) "
                  f"[{t.get('status', '?')}{flags}]")
    print(f"\n{found} discussion(s)"
          + (f" since {since}" if since else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
