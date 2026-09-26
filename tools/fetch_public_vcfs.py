"""Download public VCF data into env/public_vcfs/ (gitignored, re-fetchable).

These are the external-validation substrates for the answer-blind pipeline
(plan.md section 2.1.2): real public data, no patient material, no leaked
coordinates anywhere.

Datasets
--------
clinvar   NCBI ClinVar GRCh38 VCF
          https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/clinvar.vcf.gz
          (~198 MB gz) - downloaded whole with a streaming SHA-256, then a
          ``--chr-subset CHROM`` slice is emitted as an uncompressed VCF
          (header + matching records) because parsing 198 MB repeatedly is
          slow. The .tbi index is fetched too (tiny).
hg002     GIAB NIST v4.2.1 benchmark VCF for HG002/NA24385 (GRCh38)
          https://ftp-trace.ncbi.nlm.nih.gov/giab/ftp/release/AshkenazimTrio/
          HG002_NA24385_son/NISTv4.2.1/GRCh38/
          HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz (~156 MB gz)
          The whole file is streamed through gzip once; only records inside
          each ``--region chrom:start-end`` are written out (header kept),
          so the full VCF never has to be stored. The SHA-256 is still
          computed over the ENTIRE stream, giving a real integrity check of
          the source file without keeping it. ``--keep-hg002-full`` stores
          the gz too, for callers that want the whole benchmark.

Usage
-----
    python tools/fetch_public_vcfs.py \
        --chr-subset 12 --region chr12:102800000-103000000
    python tools/fetch_public_vcfs.py --dataset clinvar --chr-subset 12
    python tools/fetch_public_vcfs.py --dataset hg002 \
        --region chr12:102800000-103000000 --region chr7:1-2000000
    python tools/fetch_public_vcfs.py --force      # re-download everything

Everything is idempotent: a dataset whose manifest sha256 already matches
the file on disk is skipped unless ``--force``. Records are filtered on the
line's own CHROM value, normalized so ``12``, ``chr12`` and the RefSeq
accession ``NC_000012.12`` all match chromosome 12.

env/public_vcfs/manifest.json records per artifact:
    {url, sha256, bytes, fetched_at, kind, parent, chrom/region, records}
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT_DIR = REPO / "env" / "public_vcfs"
MANIFEST = OUT_DIR / "manifest.json"

CLINVAR_URL = ("https://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh38/"
               "clinvar.vcf.gz")
CLINVAR_TBI_URL = CLINVAR_URL + ".tbi"
HG002_URL = ("https://ftp-trace.ncbi.nlm.nih.gov/giab/ftp/release/"
             "AshkenazimTrio/HG002_NA24385_son/NISTv4.2.1/GRCh38/"
             "HG002_GRCh38_1_22_v4.2.1_benchmark.vcf.gz")

CHUNK = 1 << 20          # 1 MiB
CONNECT_TIMEOUT = 30     # seconds for connect / first byte
USER_AGENT = "mva-fetch-public-vcfs/1.0"


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_manifest() -> dict:
    if MANIFEST.exists():
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, indent=2) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Chromosome-name normalization: '12' / 'chr12' / 'NC_000012.12' -> '12'
# ---------------------------------------------------------------------------

_GRCH38_NC = {i: f"NC_{i:06d}.11" for i in range(1, 23)}
_GRCH38_NC.update({"X": "NC_000023.11", "Y": "NC_000024.10",
                   "MT": "NC_012920.1", "M": "NC_012920.1"})
_NC_RE = re.compile(r"^NC_0*(\d+)\.\d+$", re.IGNORECASE)


def norm_chrom(name: str) -> str:
    """Normalize a contig name to a bare chromosome token ('12','X','M')."""
    c = name.strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    m = _NC_RE.match(c)
    if m:
        n = int(m.group(1))
        c = {23: "X", 24: "Y"}.get(n, str(n))
    if c.upper() in ("MT",):
        c = "M"
    return c.upper() if c.upper() in ("X", "Y", "M") else c


def chrom_matches(line_chrom: str, wanted: str) -> bool:
    return norm_chrom(line_chrom) == norm_chrom(wanted)


def parse_region(spec: str) -> tuple[str, int, int]:
    """'chr12:102,800,000-103,000,000' -> ('12', 102800000, 103000000)."""
    m = re.match(r"^([^:]+):([\d,]+)-([\d,]+)$", spec.strip())
    if not m:
        raise ValueError(f"bad --region '{spec}'; expected chrom:start-end")
    chrom = norm_chrom(m.group(1))
    start, end = int(m.group(2).replace(",", "")), int(m.group(3).replace(",", ""))
    if not (0 < start <= end):
        raise ValueError(f"bad --region '{spec}'; need 0 < start <= end")
    return chrom, start, end


def _open_url(url: str):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    return urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT)


# ---------------------------------------------------------------------------
# Downloaders
# ---------------------------------------------------------------------------

def download_full(url: str, dest: Path) -> dict:
    """Stream ``url`` to ``dest`` (.part then rename); return manifest data."""
    tmp = dest.with_suffix(dest.suffix + ".part")
    sha = hashlib.sha256()
    nbytes = 0
    with _open_url(url) as r:
        if r.status != 200:
            raise urllib.error.HTTPError(url, r.status, f"HTTP {r.status}",
                                         r.headers, None)
        with open(tmp, "wb") as out:
            while True:
                chunk = r.read(CHUNK)
                if not chunk:
                    break
                out.write(chunk)
                sha.update(chunk)
                nbytes += len(chunk)
    if nbytes == 0:
        tmp.unlink(missing_ok=True)
        raise OSError(f"zero bytes from {url}")
    tmp.replace(dest)
    return {"url": url, "sha256": sha.hexdigest(), "bytes": nbytes,
            "fetched_at": _now()}


def slice_gz_by_chrom(src_gz: Path, chrom: str, dest: Path) -> dict:
    """Emit uncompressed VCF slice of ``src_gz`` for one chromosome."""
    n = 0
    with gzip.open(src_gz, "rt", encoding="utf-8", errors="replace") as inp, \
            open(dest, "w", encoding="utf-8", newline="") as out:
        for line in inp:
            if line.startswith("#"):
                out.write(line)
                continue
            if chrom_matches(line.split("\t", 1)[0], chrom):
                out.write(line)
                n += 1
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    return {"parent": src_gz.name, "chrom": norm_chrom(chrom),
            "records": n, "bytes": dest.stat().st_size,
            "sha256": sha, "fetched_at": _now()}


def _slice_gz_regions(src: gzip.GzipFile | io.TextIOBase,
                      regions: list[tuple[str, int, int]],
                      writers: dict[tuple, io.TextIOBase],
                      sha: hashlib._Hash | None = None) -> tuple[int, dict]:
    """Write header + in-region records from a decompressed-VCF line stream."""
    nbytes = 0
    counts = {r: 0 for r in regions}
    for line in src:
        if sha is not None:
            enc = line.encode("utf-8")
            sha.update(enc)
            nbytes += len(enc)
        if line.startswith("#"):
            for w in writers.values():
                w.write(line)
            continue
        fields = line.split("\t", 2)
        if len(fields) < 2:
            continue
        try:
            pos = int(fields[1])
        except ValueError:
            continue
        for reg in regions:
            if reg[1] <= pos <= reg[2] and chrom_matches(fields[0], reg[0]):
                writers[reg].write(line)
                counts[reg] += 1
                break
    return nbytes, counts


def stream_gz_by_regions(url: str, regions: list[tuple[str, int, int]],
                         out_paths: dict[tuple, Path]) -> dict:
    """Single streaming pass over a remote .vcf.gz: hash the decompressed
    bytes, write header + in-region records to per-region outputs. The full
    file is never stored (region slicing only).
    """
    sha = hashlib.sha256()
    writers: dict[tuple, io.TextIOBase] = {}
    try:
        for r in regions:
            out_paths[r].parent.mkdir(parents=True, exist_ok=True)
            writers[r] = open(out_paths[r], "w", encoding="utf-8", newline="")
        with _open_url(url) as r:
            if r.status != 200:
                raise urllib.error.HTTPError(url, r.status, f"HTTP {r.status}",
                                             r.headers, None)
            gz = gzip.GzipFile(fileobj=r)
            buf = io.TextIOWrapper(gz, encoding="utf-8", errors="replace",
                                   newline="")
            nbytes, counts = _slice_gz_regions(buf, regions, writers, sha)
    finally:
        for w in writers.values():
            w.close()
    return {"url": url,
            # NOTE: hashed over DECOMPRESSED bytes - a real integrity check
            # on the content even though the gz itself is never stored.
            "sha256_uncompressed_stream": sha.hexdigest(),
            "bytes_uncompressed": nbytes,
            "records_per_region": {f"{c}:{s}-{e}": n
                                   for (c, s, e), n in counts.items()},
            "fetched_at": _now()}


def slice_local_gz_by_regions(src_gz: Path,
                              regions: list[tuple[str, int, int]],
                              out_paths: dict[tuple, Path]) -> dict:
    """Slice regions out of an already-downloaded .vcf.gz."""
    writers = {r: open(out_paths[r], "w", encoding="utf-8", newline="")
               for r in regions}
    try:
        with gzip.open(src_gz, "rt", encoding="utf-8", errors="replace") as f:
            _, counts = _slice_gz_regions(f, regions, writers)
    finally:
        for w in writers.values():
            w.close()
    return {"records_per_region": {f"{c}:{s}-{e}": n
                                   for (c, s, e), n in counts.items()},
            "fetched_at": _now()}


def _manifest_entry_ok(entry: dict, path: Path) -> bool:
    """Idempotency check: file exists and sha256 (or size) matches."""
    if not path.exists():
        return False
    if entry.get("sha256"):
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(CHUNK), b""):
                h.update(chunk)
        return h.hexdigest() == entry["sha256"]
    return entry.get("bytes") == path.stat().st_size


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="fetch public VCF corpora into env/public_vcfs/")
    ap.add_argument("--dataset", choices=("clinvar", "hg002", "both"),
                    default="both")
    ap.add_argument("--chr-subset", default=None, metavar="CHROM",
                    help="also emit clinvar_<CHROM>.vcf slice (uncompressed)")
    ap.add_argument("--region", action="append", default=[], metavar="C:S-E",
                    help="HG002 region slice; repeatable")
    ap.add_argument("--keep-hg002-full", action="store_true",
                    help="also store the full HG002 gz (~156 MB)")
    ap.add_argument("--clinvar-tbi", action="store_true",
                    help="also fetch clinvar.vcf.gz.tbi")
    ap.add_argument("--out-dir", default=str(OUT_DIR))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    global MANIFEST  # tests may point --out-dir elsewhere
    if out_dir != OUT_DIR:
        MANIFEST = out_dir / "manifest.json"
    manifest = _load_manifest()
    did = []

    # ---------------- ClinVar ----------------
    if args.dataset in ("clinvar", "both"):
        dest = out_dir / "clinvar.vcf.gz"
        ent = manifest.get("clinvar.vcf.gz", {})
        if not args.force and _manifest_entry_ok(ent, dest):
            print("[clinvar] already present, sha256 verified - skipping",
                  flush=True)
        else:
            print(f"[clinvar] downloading {CLINVAR_URL} ...", flush=True)
            manifest["clinvar.vcf.gz"] = {"kind": "full_gz",
                                          **download_full(CLINVAR_URL, dest)}
            _save_manifest(manifest)
            print(f"[clinvar] OK {manifest['clinvar.vcf.gz']['bytes']:,} B",
                  flush=True)
        did.append("clinvar")

        if args.clinvar_tbi:
            tbi = out_dir / "clinvar.vcf.gz.tbi"
            if tbi.exists() and not args.force:
                print("[clinvar.tbi] already present - skipping", flush=True)
            else:
                try:
                    manifest["clinvar.vcf.gz.tbi"] = {
                        "kind": "tbi", **download_full(CLINVAR_TBI_URL, tbi)}
                    _save_manifest(manifest)
                    print(f"[clinvar.tbi] OK {tbi.stat().st_size:,} B",
                          flush=True)
                except Exception as exc:  # noqa: BLE001 - index is optional
                    print(f"[clinvar.tbi] skipped ({exc})", flush=True)

        if args.chr_subset:
            chrom = norm_chrom(args.chr_subset)
            slice_path = out_dir / f"clinvar_{chrom}.vcf"
            print(f"[clinvar] slicing chr {chrom} -> {slice_path.name} ...",
                  flush=True)
            info = slice_gz_by_chrom(dest, args.chr_subset, slice_path)
            manifest[slice_path.name] = {"kind": "chrom_slice", **info}
            _save_manifest(manifest)
            print(f"[clinvar] slice OK: {info['records']:,} records, "
                  f"{info['bytes']:,} B", flush=True)

    # ---------------- HG002 ----------------
    if args.dataset in ("hg002", "both"):
        regions = [parse_region(spec) for spec in args.region]
        keep = out_dir / HG002_URL.rsplit("/", 1)[-1] \
            if args.keep_hg002_full else None
        if not regions and keep is None:
            print("[hg002] no --region and no --keep-hg002-full: nothing to "
                  "do (the full file is never stored by default)", flush=True)
        else:
            out_paths = {(c, s, e): out_dir / f"hg002_{c}_{s}-{e}.vcf"
                         for c, s, e in regions}
            have_all = bool(regions) and all(
                _manifest_entry_ok(manifest.get(out_paths[r].name, {}),
                                   out_paths[r]) for r in regions)
            keep_ok = keep is not None and _manifest_entry_ok(
                manifest.get(keep.name, {}), keep)
            if not args.force and (not regions or have_all) \
                    and (keep is None or keep_ok):
                print("[hg002] requested slices already present - skipping",
                      flush=True)
            elif keep is not None:
                # full-file path: download the gz first, slice locally.
                print(f"[hg002] downloading {HG002_URL} ...", flush=True)
                manifest[keep.name] = {"kind": "full_gz",
                                       **download_full(HG002_URL, keep)}
                _save_manifest(manifest)
                print(f"[hg002] full gz OK "
                      f"{manifest[keep.name]['bytes']:,} B; slicing ...",
                      flush=True)
                res = slice_local_gz_by_regions(keep, regions, out_paths)
                for reg in regions:
                    p = out_paths[reg]
                    manifest[p.name] = {
                        "kind": "region_slice", "parent": keep.name,
                        "region": f"{reg[0]}:{reg[1]}-{reg[2]}",
                        "records": res["records_per_region"].get(
                            f"{reg[0]}:{reg[1]}-{reg[2]}", 0),
                        "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "fetched_at": _now()}
                _save_manifest(manifest)
            else:
                # stream-slice path (default): full file never stored.
                print(f"[hg002] streaming {HG002_URL}", flush=True)
                print("[hg002] slicing regions: "
                      + ", ".join(f"{c}:{s}-{e}" for c, s, e in regions),
                      flush=True)
                res = stream_gz_by_regions(HG002_URL, regions, out_paths)
                manifest["hg002_stream"] = {"kind": "stream_slice", **res}
                for reg in regions:
                    p = out_paths[reg]
                    manifest[p.name] = {
                        "kind": "region_slice", "parent": "hg002_stream",
                        "region": f"{reg[0]}:{reg[1]}-{reg[2]}",
                        "records": res["records_per_region"].get(
                            f"{reg[0]}:{reg[1]}-{reg[2]}", 0),
                        "bytes": p.stat().st_size,
                        "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                        "fetched_at": _now()}
                _save_manifest(manifest)
                print(f"[hg002] stream done: {res['bytes_uncompressed']:,} B "
                      f"decompressed; sha256(uncompressed)="
                      f"{res['sha256_uncompressed_stream'][:12]}...",
                      flush=True)
                for reg in regions:
                    p = out_paths[reg]
                    print(f"[hg002] {p.name}: "
                          f"{manifest[p.name]['records']:,} records, "
                          f"{p.stat().st_size:,} B", flush=True)
        did.append("hg002")

    _save_manifest(manifest)
    print(f"\nmanifest: {MANIFEST}")
    print("datasets processed: " + ", ".join(did))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
