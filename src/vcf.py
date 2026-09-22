"""Minimal, dependency-free VCF reader with VEP-CSQ and FORMAT-field support.

Design notes
------------
* Streams records (generator) - a ~5M-variant WGS VCF never loads fully into RAM.
* Handles plain or bgzip/gzip-compressed input by magic bytes.
* Parses the VEP CSQ INFO annotation generically: the field list is read from
  the VCF header (``##INFO=<ID=CSQ,...Format: A|B|C``), so any VEP run works.
* FORMAT fields are exposed verbatim per sample; helpers decode GT/AD/DP/GQ/
  PGT/PID. ``PGT`` = phased genotype string (``1|0``), ``PID`` = phase-set ID
  (GATK/Sentieon physical phasing) used by the phasing module.
* INFO ``AF`` in the challenge VCF is the within-sample allele fraction
  (AN=2), NOT a population frequency (deep dive sec.2). Rarity must come from
  CSQ annotation (gnomAD), never from this field.
"""
from __future__ import annotations

import gzip
import io
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator

CSQ_ID = "CSQ"


def _open_maybe_gz(path: str | Path) -> io.TextIOBase:
    p = Path(path)
    with open(p, "rb") as probe:
        magic = probe.read(2)
    if magic == b"\x1f\x8b":
        return io.TextIOWrapper(gzip.open(p, "rb"), encoding="utf-8")
    return open(p, encoding="utf-8")


@dataclass
class SampleGenotype:
    """Decoded FORMAT data for one sample at one site."""

    raw: dict[str, str]
    gt: tuple[int | None, ...] = ()
    phased: bool = False

    @property
    def is_het(self) -> bool:
        if not self.called:
            return False
        return len(set(self.gt)) >= 2

    @property
    def is_hom_alt(self) -> bool:
        if not self.called or len(self.gt) < 2:
            return False
        return self.gt[0] not in (0, None) and all(a == self.gt[0] for a in self.gt)

    @property
    def called(self) -> bool:
        return bool(self.gt) and all(a is not None for a in self.gt)

    @property
    def dp(self) -> int | None:
        v = self.raw.get("DP")
        try:
            return int(v) if v not in (None, ".", "") else None
        except ValueError:
            return None

    @property
    def gq(self) -> float | None:
        v = self.raw.get("GQ")
        try:
            return float(v) if v not in (None, ".", "") else None
        except ValueError:
            return None

    @property
    def ad(self) -> list[int] | None:
        v = self.raw.get("AD")
        if not v:
            return None
        try:
            return [int(x) for x in v.split(",") if x not in (".", "")]
        except ValueError:
            return None

    @property
    def vaf(self) -> float | None:
        """Allele fraction of the (first) alt allele from AD, else FORMAT AF."""
        ad = self.ad
        if ad and len(ad) >= 2 and sum(ad) > 0:
            return ad[1] / sum(ad)
        v = self.raw.get("AF")
        try:
            return float(v) if v not in (None, ".", "") else None
        except ValueError:
            return None

    @property
    def pgt(self) -> str | None:
        v = self.raw.get("PGT")
        return v if v not in (None, "", ".") else None

    @property
    def pid(self) -> str | None:
        v = self.raw.get("PID")
        return v if v not in (None, "", ".") else None

    @property
    def pgt_alleles(self) -> tuple[int, int] | None:
        """Phased genotype as (mat, pat) allele indices, e.g. '1|0' -> (1, 0)."""
        v = self.pgt
        if not v or "|" not in v:
            return None
        try:
            a, b = v.split("|")[:2]
            return (int(a), int(b))
        except ValueError:
            return None


@dataclass
class VcfRecord:
    chrom: str
    pos: int
    vid: str
    ref: str
    alts: list[str]
    qual: float | None
    filters: list[str]
    info: dict[str, str | bool]
    samples: dict[str, SampleGenotype] = field(default_factory=dict)
    _csq_fields: list[str] = field(default_factory=list, repr=False)

    @property
    def passed(self) -> bool:
        return self.filters == [] or self.filters == ["PASS"] or self.filters == ["."]

    def alt(self, i: int = 0) -> str:
        return self.alts[i]

    def is_snv(self) -> bool:
        return len(self.ref) == 1 and all(len(a) == 1 for a in self.alts)

    def is_indel(self) -> bool:
        return not self.is_snv()

    def variant_tuple(self, alt_i: int = 0, chrom: str | None = None) -> tuple[str, int, str, str]:
        """(chrom,pos,ref,alt) tuple in scorer convention; chrom normalized via
        :func:`to_submission_chrom` unless overridden."""
        c = chrom if chrom is not None else to_submission_chrom(self.chrom)
        return (c, self.pos, self.ref, self.alts[alt_i])

    def annotations(self) -> list[dict[str, str]]:
        """Parsed CSQ entries: one dict per ``Allele|...`` annotation block."""
        raw = self.info.get(CSQ_ID)
        if not raw or not isinstance(raw, str):
            return []
        out: list[dict[str, str]] = []
        for entry in raw.split(","):
            parts = entry.split("|")
            d = {self._csq_fields[i]: parts[i] if i < len(parts) else ""
                 for i in range(len(self._csq_fields))}
            out.append(d)
        return out

    def csq_for_alt(self, alt: str) -> list[dict[str, str]]:
        return [a for a in self.annotations() if a.get("Allele") == alt]


class VcfReader:
    """Streaming VCF reader. Usage::

        r = VcfReader(path)
        for rec in r.records():
            ...

    Header is parsed on construction: ``r.contigs``, ``r.samples``,
    ``r.info_defs``, ``r.format_defs``, ``r.csq_fields``, ``r.meta`` (raw lines).
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._fh = _open_maybe_gz(self.path)
        self.meta: list[str] = []
        self.contigs: dict[str, int] = {}
        self.info_defs: dict[str, str] = {}
        self.format_defs: dict[str, str] = {}
        self.filter_defs: dict[str, str] = {}
        self.samples: list[str] = []
        self.csq_fields: list[str] = []
        self._header_done = False
        self._pending: str | None = None
        self._read_header()

    def _read_header(self) -> None:
        for line in self._fh:
            line = line.rstrip("\n")
            if line.startswith("##"):
                self.meta.append(line)
                self._parse_meta(line)
            elif line.startswith("#"):
                cols = line.lstrip("#").split("\t")
                self.samples = cols[9:] if len(cols) > 9 else []
                self._header_done = True
                return
        self._header_done = True

    _meta_re = re.compile(r"##(?P<key>\w+)=<ID=(?P<id>[^,>]+)(?P<rest>.*)>?$")

    def _parse_meta(self, line: str) -> None:
        m = self._meta_re.match(line)
        if m:
            key, iid = m.group("key"), m.group("id")
            if key == "contig":
                lm = re.search(r"length=(\d+)", line)
                self.contigs[iid] = int(lm.group(1)) if lm else 0
            elif key == "INFO":
                self.info_defs[iid] = line
                if iid == CSQ_ID:
                    fm = re.search(r"Format:\s*([^\"]+)", line)
                    if fm:
                        self.csq_fields = fm.group(1).strip().split("|")
            elif key == "FORMAT":
                self.format_defs[iid] = line
            elif key == "FILTER":
                self.filter_defs[iid] = line

    def records(self, sample: str | None = None) -> Iterator[VcfRecord]:
        fh = self._fh
        for line in fh:
            if not line or line.startswith("#"):
                continue
            yield self._parse_record(line.rstrip("\n"), sample)

    def _parse_record(self, line: str, sample: str | None) -> VcfRecord:
        cols = line.split("\t")
        chrom, pos, vid, ref, alts, qual, filt, info = cols[:8]
        fmt_keys = cols[8].split(":") if len(cols) > 8 else []
        samples: dict[str, SampleGenotype] = {}
        if self.samples and len(cols) > 9:
            for i, sname in enumerate(self.samples):
                if sample is not None and sname != sample:
                    continue
                vals = cols[9 + i].split(":") if 9 + i < len(cols) else []
                raw = {fmt_keys[j]: vals[j] if j < len(vals) else "."
                       for j in range(len(fmt_keys))}
                samples[sname] = decode_genotype(raw)
        inf: dict[str, str | bool] = {}
        if info != ".":
            for kv in info.split(";"):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    inf[k] = v
                else:
                    inf[kv] = True
        return VcfRecord(
            chrom=chrom,
            pos=int(pos),
            vid=vid,
            ref=ref,
            alts=alts.split(","),
            qual=None if qual in (".", "") else float(qual),
            filters=[] if filt in ("PASS", ".", "") else filt.split(";"),
            info=inf,
            samples=samples,
            _csq_fields=self.csq_fields,
        )

    def close(self) -> None:
        self._fh.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def decode_genotype(raw: dict[str, str]) -> SampleGenotype:
    gt_s = raw.get("GT", "")
    gt: tuple[int | None, ...] = ()
    phased = "|" in gt_s
    if gt_s and gt_s != ".":
        sep = "|" if phased else "/"
        try:
            gt = tuple(None if a == "." else int(a) for a in gt_s.split(sep))
        except ValueError:
            gt = ()
    return SampleGenotype(raw=raw, gt=gt, phased=phased)


def to_submission_chrom(chrom: str) -> str:
    """Normalize a VCF contig name to the scorer's ``chr``-prefixed convention.

    The challenge VCF uses bare contigs (``15``, ``X``, ``M``); the scorer's
    ground truth uses ``chr15``-style strings compared verbatim. Idempotent.
    """
    c = chrom.strip()
    if c.lower().startswith("chr"):
        return "chr" + c[3:]
    if c in ("M", "MT", "m", "mt"):
        return "chrM"
    return "chr" + c


def from_submission_chrom(chrom: str) -> str:
    """Inverse of :func:`to_submission_chrom` for VCF-convention contigs."""
    c = chrom.strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    return "M" if c == "MT" else c
