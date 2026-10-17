"""Locus redaction for the public repo.

Two classes of patient-derived locus are NOT part of the causal call and are
withheld from every tracked file (decision A7, docs/track1_closeout.md):

* the MHC-region artifact cluster (the pseudo-LoF hypotheses that motivated
  the declared ``artifact_loci`` mask) - redacted by a generic rule: any
  variant coordinate inside the declared MHC window and any HLA gene symbol;
* one benign intronic heterozygous site between the two BUB1B alleles -
  redacted by a private token list (``results/withheld_sites.json``, which is
  gitignored together with the rest of ``results/``).

Generators (``make_report.py``) run ``scrub`` over their output, and
``tests/test_redaction.py`` fails if a tracked text file would change under
``scrub`` or contains a withheld token (checked by hash so this file does not
itself carry the value).

CLI::

    python tools/redact.py --check          # exit 1 if any tracked file leaks
    python tools/redact.py --apply          # rewrite offending tracked files
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE = ROOT / "results" / "withheld_sites.json"

# Variant coordinates inside the declared extended-MHC window
# (config/pipeline.yaml artifact_loci: 6:28500000-33500000). A trailing "-"
# or digit is excluded so the window definition itself is left alone.
_MHC_COORD = re.compile(r"\b(chr)?6:(?:2[89]|3[0-3])\d{6}(?![-\d])")
_HLA_GENE = re.compile(r"\bHLA-[A-Z][A-Za-z0-9]*")

SITE_ALIAS = "[intronic site withheld]"
COORD_ALIAS = "[withheld]"

# sha256 of withheld bare tokens, for the tracked-file guard.
WITHHELD_HASHES = frozenset({
    "09668d065e4e42fb03a9e38500b4b0cf7d37d799361c6f6da7273affe00174b3",
})

# Paths whose content is public reference data, not patient-derived.
EXEMPT_PREFIXES = (
    "docs/track2/evidence/", "tests/fixtures/", "docs/track2/citation_cache",
    "docs/track2/agent_reports/",
)
TEXT_SUFFIXES = {".md", ".py", ".yaml", ".yml", ".txt", ".svg", ".csv",
                 ".cff", ".json", ".toml", ".sh", ".css"}


def private_tokens() -> dict:
    """{"<chrom>:<pos>": {"ref": "A", "alt": "G"}} from the gitignored file."""
    try:
        return json.loads(PRIVATE.read_text(encoding="utf-8")).get(
            "sites", {})
    except (OSError, ValueError):
        return {}


def scrub(text: str) -> str:
    """Return ``text`` with every withheld locus replaced by an alias."""
    out = _MHC_COORD.sub(lambda m: (m.group(1) or "") + "6:" + COORD_ALIAS,
                         text)
    out = _HLA_GENE.sub("MHC-region", out)
    for site in private_tokens():
        chrom, pos = site.split(":")
        out = re.sub(rf"(?:chr)?{re.escape(chrom)}:{re.escape(pos)}"
                     r"(?::[ACGT]:[ACGT])?", SITE_ALIAS, out)
        out = out.replace(pos, COORD_ALIAS)
    return out


def leaks_by_hash(text: str) -> bool:
    """True if any 7-9 digit token in ``text`` hashes into the withheld set."""
    return any(
        hashlib.sha256(tok.encode()).hexdigest() in WITHHELD_HASHES
        for tok in re.findall(r"(?<!\d)\d{7,9}(?!\d)", text))


def tracked_text_files() -> list[Path]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True,
                         text=True, check=True).stdout.splitlines()
    files = []
    for rel in out:
        if rel.startswith(EXEMPT_PREFIXES):
            continue
        if Path(rel).suffix.lower() in TEXT_SUFFIXES:
            files.append(ROOT / rel)
    return files


def offenders() -> list[Path]:
    bad = []
    for p in tracked_text_files():
        try:
            t = p.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if scrub(t) != t or leaks_by_hash(t):
            bad.append(p)
    return bad


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)
    bad = offenders()
    for p in bad:
        print(("would rewrite " if args.check else "rewriting ")
              + str(p.relative_to(ROOT)))
        if args.apply:
            t = p.read_text(encoding="utf-8")
            p.write_text(scrub(t), encoding="utf-8", newline="")
    print(f"{len(bad)} file(s) {'leak' if args.check else 'rewritten'}")
    return 1 if (bad and args.check) else 0


if __name__ == "__main__":
    sys.exit(main())
