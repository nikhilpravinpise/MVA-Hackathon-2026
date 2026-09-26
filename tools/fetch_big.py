"""Parallel byte-range downloader for big public bundles (Resumable).

    python tools/fetch_big.py URL OUT [--parts N]

Splits the file into N equal ranges fetched concurrently (the Monarch CDN
throttles a single TCP stream to ~0.1-18 MB/s; parallel ranges aggregate
to wire speed). Each part lands as OUT.partNN and resumes on re-run, so a
killed download loses nothing. Part files are concatenated when all are
complete; the part dir is removed afterwards.
"""
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHUNK = 1 << 22  # 4 MB reads


def _size(url: str) -> int:
    req = urllib.request.Request(url, headers={"Range": "bytes=0-0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get("Content-Range", "")
    try:
        return int(cr.split("/")[-1])
    except ValueError:
        raise SystemExit(
            f"no Content-Range from {url} - the server may not support "
            "byte ranges; this downloader requires Range support")


def _fetch_part(url: str, part: Path, start: int, end: int) -> None:
    have = part.stat().st_size if part.exists() else 0
    want = end - start + 1
    if have == want:
        return
    if have > want:
        raise RuntimeError(
            f"{part} is {have} bytes but range is only {want} - corrupt "
            "part file (parts are only ever appended to); delete it and "
            "re-run")
    # resume inside the part: request from start+have
    req = urllib.request.Request(
        url, headers={"Range": f"bytes={start + have}-{end}"})
    with urllib.request.urlopen(req, timeout=120) as r, \
            open(part, "ab") as f:
        while True:
            b = r.read(CHUNK)
            if not b:
                break
            f.write(b)


def _n_parts(total: int, requested: int) -> int:
    """Every part must cover >=1 byte: span is derived from the
    requested count, then n is recomputed off that span - min(requested,
    total) alone is NOT sufficient (total=10, n=8, span=2 still gives
    parts starting past EOF)."""
    span = max(1, (total + requested - 1) // max(1, requested))
    return max(1, (total + span - 1) // span)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("out")
    ap.add_argument("--parts", type=int, default=8)
    args = ap.parse_args(argv)

    out = Path(args.out)
    total = _size(args.url)
    if total == 0:
        out.write_bytes(b"")
        print(f"wrote {out} (0 bytes - empty remote file)")
        return 0
    n = _n_parts(total, args.parts)
    span = (total + n - 1) // n
    parts = []
    for i in range(n):
        s = i * span
        e = min(total - 1, s + span - 1)
        parts.append((out.parent / f"{out.name}.part{i:02d}", s, e))

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=n) as ex:
        futs = [ex.submit(_fetch_part, args.url, p, s, e)
                for p, s, e in parts]
        while True:
            done = sum(f.done() for f in futs)
            got = sum(p.stat().st_size for p, _, _ in parts if p.exists())
            rate = got / max(time.time() - t0, 1) / 1e6
            print(f"\r{got / 1e9:.2f}/{total / 1e9:.2f} GB "
                  f"({rate:.1f} MB/s) [{done}/{n} parts]",
                  end="", flush=True)
            if done == n:
                break
            time.sleep(5)
        for f in futs:
            f.result()  # re-raises any part failure after the loop

    print(f"\nall parts fetched in {time.time() - t0:.0f}s - concatenating")
    with open(out, "wb") as dst:
        for p, _, _ in parts:
            with open(p, "rb") as src:
                while True:
                    b = src.read(CHUNK)
                    if not b:
                        break
                    dst.write(b)
            p.unlink()
    got = out.stat().st_size
    if got != total:  # not an assert - must hold under `python -O`
        raise RuntimeError(f"size mismatch {got} != {total} - "
                           "concatenated file is corrupt")
    print(f"wrote {out} ({got / 1e9:.2f} GB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
