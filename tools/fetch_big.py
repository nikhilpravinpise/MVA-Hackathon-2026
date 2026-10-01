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
import http.client
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

CHUNK = 1 << 22  # 4 MB reads
MAX_RESUMES = 200  # reconnects allowed per part before giving up


def _size(url: str, extra: dict) -> int:
    req = urllib.request.Request(url,
                                 headers={"Range": "bytes=0-0", **extra})
    with urllib.request.urlopen(req, timeout=30) as r:
        cr = r.headers.get("Content-Range", "")
    try:
        return int(cr.split("/")[-1])
    except ValueError:
        raise SystemExit(
            f"no Content-Range from {url} - the server may not support "
            "byte ranges; this downloader requires Range support")


def _fetch_part(url: str, part: Path, start: int, end: int,
                extra: dict | None = None) -> None:
    extra = extra or {}
    want = end - start + 1
    resumes = 0
    # A part is complete ONLY when its bytes equal the range width. A
    # server may honour Range yet close the stream early (throttled CDNs
    # do this routinely): the read loop ending is NOT completion. Re-open
    # the range from where we stopped until have == want.
    while True:
        have = part.stat().st_size if part.exists() else 0
        if have == want:
            return
        if have > want:
            raise RuntimeError(
                f"{part} is {have} bytes but range is only {want} - corrupt "
                "part file (parts are only ever appended to); delete it and "
                "re-run")
        # resume inside the part: request from start+have
        req = urllib.request.Request(
            url, headers={"Range": f"bytes={start + have}-{end}", **extra})
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                if getattr(r, "status", None) != 206:
                    raise RuntimeError(
                        f"{part}: server answered {getattr(r, 'status', '?')} "
                        "to a Range request - appending a full body would "
                        "corrupt the part; delete it and re-run")
                with open(part, "ab") as f:
                    while True:
                        b = r.read(CHUNK)
                        if not b:
                            break
                        f.write(b)
        except (urllib.error.URLError, TimeoutError, ConnectionError,
                http.client.IncompleteRead):
            pass  # dropped connection - resume from `have` below
        resumes += 1
        if resumes > MAX_RESUMES:
            raise RuntimeError(
                f"{part}: still incomplete after {MAX_RESUMES} resumes "
                f"({have}/{want} bytes) - server too hostile")
        time.sleep(min(resumes, 30))


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
    ap.add_argument("--header", action="append", default=[],
                    help="'Name: value' header sent with every request "
                         "(repeatable); e.g. --header 'Authorization: "
                         "Bearer TOKEN' for gated hosts")
    args = ap.parse_args(argv)

    extra = {}
    for h in args.header:
        name, _, val = h.partition(":")
        if not name or not val.strip():
            print(f"ERROR: --header '{h}' is not 'Name: value'",
                  file=sys.stderr)
            return 2
        extra[name.strip()] = val.strip()

    out = Path(args.out)
    total = _size(args.url, extra)
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
        futs = [ex.submit(_fetch_part, args.url, p, s, e, extra)
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
    got = out.stat().st_size
    if got != total:  # not an assert - must hold under `python -O`
        raise RuntimeError(f"size mismatch {got} != {total} - "
                           "concatenated file is corrupt; parts kept for "
                           "inspection/resume")
    for p, _, _ in parts:
        p.unlink()
    print(f"wrote {out} ({got / 1e9:.2f} GB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
