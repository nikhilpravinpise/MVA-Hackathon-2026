"""Deterministic synthetic SAM generator for phasing tests.

Companion to :mod:`src.synth` (which builds VCFs): this module builds SAM
text fixtures for :mod:`src.reads` so the read-level phasing path can be
tested end to end without a real BAM. Everything is deterministic - fixed
positions, fixed sequences, fixed MAPQs - and firewall-clean (contig '7'
fixtures, no real-case coordinates).

Template model
--------------
A *template* is one DNA molecule = a QNAME. ``templates`` is a list of
dicts::

    {"name": "tmpl1",
     "reads": [(pos, seq, cigar_or_None, mapq, flag),         # min form
               (pos, seq, cigar_or_None, mapq, flag, rname), # +contig
               (pos, seq, cigar_or_None, mapq, flag, rname, qual)]}

``cigar`` None emits ``<len(seq)>M``; ``rname`` defaults to the module
contig ``"7"`` (bare, matching the challenge VCF convention); ``qual``
defaults to all-'I' (Phred 40). Two-read templates get RNEXT/PNEXT/TLEN
filled in; flags are passed through verbatim so fixtures control realism.

Case fixtures
-------------
``trans_case`` / ``cis_case`` place two het sites 120 bp apart (7:1000
A>T, 7:1120 G>C) inside paired-end span (~150 bp reads, ~200 bp inserts):

* trans: >=5 templates alt@v1+ref@v2 and >=5 ref@v1+alt@v2, ZERO alt@both.
* cis:   only alt@both and ref@both templates exist.

Each case also plants honest decoys: a low-MAPQ pair carrying the
case-consistent haplotype, a wrong-contig read, a non-spanning partial
read, a third-allele ('other') read, an unmapped record, and a read
covering neither site. ``long_range_case`` puts the sites 4 kb apart -
beyond any insert - so zero templates span both and the only honest call
is 'unknown'.
"""
from __future__ import annotations

from pathlib import Path

CONTIG = "7"
READ_LEN = 150

# Canonical test sites (shared by trans/cis; long-range replaces V2).
V1 = ("7", 1000, "A", "T")
V2 = ("7", 1120, "G", "C")
V2_FAR = ("7", 5000, "G", "C")

# FLAG values used in fixtures: paired/proper pairs (99/147), single
# reads (0), unmapped single (4).
_F_R1 = 99   # paired, proper, mate reverse, first
_F_R2 = 147  # paired, proper, reverse, second


def _seq(start: int, alleles: dict | None = None,
         length: int = READ_LEN, fill: str = "A") -> str:
    """Read sequence covering ``start..start+length-1`` (1-based ref).

    ``alleles`` maps ref position -> base to plant; everything else is
    ``fill``. Every covered site must be planted explicitly - an unplanted
    site would silently report ``fill`` as its allele.
    """
    s = [fill] * length
    for rp, b in (alleles or {}).items():
        i = rp - start
        if not (0 <= i < length):
            raise ValueError(f"allele at {rp} outside read span "
                             f"{start}-{start + length - 1}")
        s[i] = b
    return "".join(s)


def _pair(name: str, hap1: dict, hap2: dict, start1: int = 990,
          start2: int = 1050, mapq1: int = 60, mapq2: int = 60,
          contig: str = CONTIG) -> dict:
    """Two-mate template: R1 forward at ``start1``, R2 reverse at
    ``start2``; ``hap1``/``hap2`` are {refpos: base} per mate."""
    return {"name": name, "reads": [
        (start1, _seq(start1, hap1), None, mapq1, _F_R1, contig),
        (start2, _seq(start2, hap2), None, mapq2, _F_R2, contig)]}


def _single(name: str, start: int, hap: dict, length: int = READ_LEN,
            mapq: int = 60, flag: int = 0, contig: str = CONTIG) -> dict:
    """Unpaired single-read template."""
    return {"name": name,
            "reads": [(start, _seq(start, hap, length), None, mapq,
                       flag, contig)]}


def write_sam(path, templates, contig_len: int = 1_000_000,
              contig: str = CONTIG) -> Path:
    """Write a minimal valid SAM: @HD/@SQ header + one record per read."""
    p = Path(path)
    contigs = {contig}
    for t in templates:
        for rd in t["reads"]:
            rn = rd[5] if len(rd) > 5 else contig
            if rn not in (None, "*"):
                contigs.add(rn)

    lines = ["@HD\tVN:1.6\tSO:unsorted"]
    lines += [f"@SQ\tSN:{c}\tLN:{contig_len}" for c in sorted(contigs)]

    for t in templates:
        norm = []
        for rd in t["reads"]:
            pos, seq, cigar, mapq, flag = rd[:5]
            rname = rd[5] if len(rd) > 5 else contig
            qual = rd[6] if len(rd) > 6 else (
                "*" if seq == "*" else "I" * len(seq))
            cigar = cigar or ("*" if seq == "*" else f"{len(seq)}M")
            norm.append((pos, seq, cigar, mapq, flag, rname, qual))
        for i, (pos, seq, cigar, mapq, flag, rname, qual) in \
                enumerate(norm):
            if len(norm) == 2 and rname != "*":
                mate = norm[1 - i]
                rnext = "=" if mate[5] == rname else mate[5]
                pnext = mate[0]
                lo = min(pos, mate[0])
                span = max(pos + len(seq), mate[0] + len(mate[1])) - lo
                tlen = span if pos <= mate[0] else -span
            else:
                rnext, pnext, tlen = "*", 0, 0
            lines.append("\t".join(str(x) for x in (
                t["name"], flag, rname, pos, mapq, cigar,
                rnext, pnext, tlen, seq, qual)))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return p


# ---------------------------------------------------------------------------
# Case fixtures
# ---------------------------------------------------------------------------

def _decoys(hap_consistent: dict, hap_other: dict) -> list[dict]:
    """Decoy records shared by trans/cis cases.

    * ``decoy_lowmapq`` - MAPQ 0 pair carrying the case-consistent
      haplotype: harmless whether counted (default) or filtered via
      ``min_mapq``.
    * ``decoy_wrongcontig`` - on contig '12'; must never contribute.
    * ``decoy_partial`` - covers v1 only; lands in 'partial'.
    * ``decoy_other`` - carries a third allele at v1; lands in 'other'.
    * ``decoy_unmapped`` / ``decoy_nohit`` - no usable evidence.
    """
    return [
        {"name": "decoy_lowmapq", "reads": [
            (990, _seq(990, hap_consistent), None, 0, _F_R1, CONTIG),
            (1050, _seq(1050, {k: v for k, v in hap_consistent.items()
                               if 1050 <= k < 1200}),
             None, 0, _F_R2, CONTIG)]},
        {"name": "decoy_wrongcontig", "reads": [
            (990, _seq(990, {1000: "T", 1120: "C"}), None, 60, 0, "12")]},
        {"name": "decoy_partial", "reads": [
            (1000, _seq(1000, {1000: "A"}, 60), None, 60, 0, CONTIG)]},
        {"name": "decoy_other", "reads": [
            (990, _seq(990, hap_other), None, 60, 0, CONTIG)]},
        {"name": "decoy_unmapped", "reads": [
            (0, "N" * 60, "*", 0, 4, "*")]},
        {"name": "decoy_nohit", "reads": [
            (850, _seq(850, {}, 140), None, 60, 0, CONTIG)]},
    ]


def trans_case():
    """TRANS fixture: two het sites 120 bp apart, no alt@both molecule.

    Returns (sites, templates). Counts with default thresholds:
    alt1_ref2=7, ref1_alt2=6, alt_alt=0, ref_ref=0, other=1, partial=1,
    mate_disagreements=1.
    """
    sites = [V1, V2]
    templates = [
        # 5 clean alt@v1 + ref@v2 pairs (mates agree where they overlap)
        *(_pair(f"trA{i}", {1000: "T", 1120: "G"}, {1120: "G"})
          for i in range(1, 6)),
        # 1 alt1+ref2 pair whose low-MAPQ mate disagrees at v2 - the
        # higher-MAPQ mate wins, so the template still reads alt1+ref2.
        {"name": "trA6", "reads": [
            (990, _seq(990, {1000: "T", 1120: "G"}), None, 60, _F_R1,
             CONTIG),
            (1000, _seq(1000, {1000: "T", 1120: "C"}), None, 10, _F_R2,
             CONTIG)]},
        # 6 ref@v1 + alt@v2 pairs
        *(_pair(f"trB{i}", {1000: "A", 1120: "C"}, {1120: "C"})
          for i in range(1, 7)),
    ]
    # decoys: consistent haplotype = alt1+ref2; third allele C at v1
    templates += _decoys({1000: "T", 1120: "G"}, {1000: "C", 1120: "G"})
    return sites, templates


def cis_case():
    """CIS fixture: only alt@both and ref@both molecules exist.

    Returns (sites, templates). Counts with default thresholds:
    alt_alt=7, ref_ref=6, alt1_ref2=0, ref1_alt2=0, other=1, partial=1,
    mate_disagreements=1.
    """
    sites = [V1, V2]
    templates = [
        *(_pair(f"ciA{i}", {1000: "T", 1120: "C"}, {1120: "C"})
          for i in range(1, 6)),
        # alt@both pair with a disagreeing low-MAPQ mate at v2
        {"name": "ciA6", "reads": [
            (990, _seq(990, {1000: "T", 1120: "C"}), None, 60, _F_R1,
             CONTIG),
            (1000, _seq(1000, {1000: "T", 1120: "G"}), None, 10, _F_R2,
             CONTIG)]},
        *(_pair(f"ciB{i}", {1000: "A", 1120: "G"}, {1120: "G"})
          for i in range(1, 7)),
    ]
    templates += _decoys({1000: "T", 1120: "C"}, {1000: "C", 1120: "G"})
    return sites, templates


def long_range_case():
    """Long-range fixture: sites 4 kb apart, beyond any insert span.

    Ten honest paired templates cover exactly one site each - every one
    lands in 'partial', none spans both, so the only honest verdict is
    'unknown'. Returns (sites, templates).
    """
    sites = [V1, V2_FAR]
    templates = []
    for i in range(1, 4):  # alt@v1 carriers
        templates.append({"name": f"lrA{i}", "reads": [
            (950, _seq(950, {1000: "T"}), None, 60, _F_R1, CONTIG),
            (1000, _seq(1000, {1000: "T"}), None, 60, _F_R2, CONTIG)]})
    for i in range(4, 6):  # ref@v1 carriers
        templates.append({"name": f"lrA{i}", "reads": [
            (950, _seq(950, {1000: "A"}), None, 60, _F_R1, CONTIG),
            (1000, _seq(1000, {1000: "A"}), None, 60, _F_R2, CONTIG)]})
    for i in range(1, 4):  # alt@v2 carriers
        templates.append({"name": f"lrB{i}", "reads": [
            (4950, _seq(4950, {5000: "C"}), None, 60, _F_R1, CONTIG),
            (5000, _seq(5000, {5000: "C"}), None, 60, _F_R2, CONTIG)]})
    for i in range(4, 6):  # ref@v2 carriers
        templates.append({"name": f"lrB{i}", "reads": [
            (4950, _seq(4950, {5000: "G"}), None, 60, _F_R1, CONTIG),
            (5000, _seq(5000, {5000: "G"}), None, 60, _F_R2, CONTIG)]})
    return sites, templates
