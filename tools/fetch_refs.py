"""Download the public reference corpora into env/corpus/.

    python tools/fetch_refs.py                # fetch all, write manifest.json
    python tools/fetch_refs.py --only hp.obo  # fetch one file

Downloads three PUBLIC HPO artefacts used by the phenotype tier and the
external-validation corpus (plan.md Phase 2.5; no patient data involved -
env/corpus/ is gitignored, everything here is re-fetchable):

    hp.obo                  HPO ontology DAG (src.pheno.OboOntology)
    phenotype.hpoa          disease_id -> HPO annotation corpus (IC source)
    genes_to_phenotype.txt  gene_symbol -> {HPO terms, disease_id} table
                            (input to tools/genes_to_disease_json.py)

Each file is tried against a list of mirrors in order (GitHub release assets
first - purl.obolibrary.org can be slow); the first URL that responds is used
and recorded in the manifest. Downloads stream to disk in chunks with a
running SHA-256 so a ~150 MB file never sits in memory.

env/corpus/manifest.json records, per file:
    {url, sha256, bytes, fetched_at}   (fetched_at = UTC ISO-8601)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CORPUS = REPO / "env" / "corpus"
MANIFEST = CORPUS / "manifest.json"

_GH = ("https://github.com/obophenotype/human-phenotype-ontology"
       "/releases/latest/download")

FILES: dict[str, list[str]] = {
    "hp.obo": [
        f"{_GH}/hp.obo",
        "https://purl.obolibrary.org/obo/hp.obo",
    ],
    "phenotype.hpoa": [
        f"{_GH}/phenotype.hpoa",
        "https://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa",
        "http://purl.obolibrary.org/obo/hp/hpoa/phenotype.hpoa",
    ],
    "genes_to_phenotype.txt": [
        f"{_GH}/genes_to_phenotype.txt",
        "https://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt",
        "http://purl.obolibrary.org/obo/hp/hpoa/genes_to_phenotype.txt",
    ],
}

CHUNK = 1 << 20          # 1 MiB stream chunks
CONNECT_TIMEOUT = 30     # seconds for urlopen / first byte
READ_TIMEOUT = 300       # urllib has no read timeout; documented bound only


def fetch_one(name: str, dest_dir: Path) -> dict:
    """Try each mirror for ``name`` in order; return the manifest entry."""
    dest = dest_dir / name
    errors = []
    for url in FILES[name]:
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            print(f"[{name}] trying {url}", flush=True)
            req = urllib.request.Request(url, headers={"User-Agent":
                                                       "mva-fetch-refs/1.0"})
            sha = hashlib.sha256()
            nbytes = 0
            with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as r:
                if r.status != 200:
                    raise urllib.error.HTTPError(
                        url, r.status, f"HTTP {r.status}", r.headers, None)
                with open(tmp, "wb") as out:
                    while True:
                        chunk = r.read(CHUNK)
                        if not chunk:
                            break
                        out.write(chunk)
                        sha.update(chunk)
                        nbytes += len(chunk)
            if nbytes == 0:
                raise OSError("zero bytes downloaded")
            tmp.replace(dest)
            entry = {
                "url": url,
                "sha256": sha.hexdigest(),
                "bytes": nbytes,
                "fetched_at": datetime.now(timezone.utc)
                              .replace(microsecond=0).isoformat(),
            }
            print(f"[{name}] OK {nbytes:,} bytes sha256={sha.hexdigest()[:12]}...",
                  flush=True)
            return entry
        except Exception as exc:  # noqa: BLE001 - try next mirror on any failure
            errors.append(f"{url}: {exc}")
            print(f"[{name}] FAILED ({exc})", flush=True)
            tmp.unlink(missing_ok=True)
    raise RuntimeError(f"all mirrors failed for {name}:\n  " + "\n  ".join(errors))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="fetch public HPO reference corpora")
    ap.add_argument("--only", choices=sorted(FILES), default=None,
                    help="fetch a single file")
    ap.add_argument("--corpus-dir", default=str(CORPUS))
    args = ap.parse_args(argv)

    corpus = Path(args.corpus_dir)
    corpus.mkdir(parents=True, exist_ok=True)

    names = [args.only] if args.only else list(FILES)
    manifest_path = corpus / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    for name in names:
        manifest[name] = fetch_one(name, corpus)

    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                             encoding="utf-8")

    print("\nfetch_refs summary")
    print(f"  manifest: {manifest_path}")
    for name, e in manifest.items():
        print(f"  {name:26s} {e['bytes']:>12,} B  sha256={e['sha256'][:12]}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
