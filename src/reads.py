"""Read-level phasing evidence from SAM text.

Biological model
----------------
A compound-heterozygous recessive diagnosis requires the two candidate
alleles to lie on DIFFERENT haplotypes (in trans). The most direct evidence
is the DNA molecules themselves: a read (or paired-end template) that spans
both sites observes one haplotype.

    IN TRANS - haplotype A carries alt@v1 + ref@v2, haplotype B carries
               ref@v1 + alt@v2. NO molecule in the sample carries both
               alt alleles, so observing many spanning templates of the
               two trans classes and ZERO alt@both carriers is positive
               in-trans evidence.
    IN CIS   - one haplotype carries alt@v1 + alt@v2, the other carries
               ref@v1 + ref@v2. Only alt@both and ref@both templates
               exist.
    UNKNOWN  - sites separated by more than a read/insert span produce
               ZERO spanning templates; the honest answer is 'unknown'.
               We never fabricate phase from non-spanning data.

Input contract
--------------
This module consumes SAM *text* (an iterable of lines: an open file from
``samtools view -O SAM``, or a synthetic SAM written by
:mod:`src.synth_sam`). BAM binary is intentionally not decoded in-repo;
``tools/run_phasing.py`` documents the samtools export command. SAM contig
names must use the same convention as the VCF (the challenge data uses
bare contigs, ``7`` not ``chr7``) - a mismatch yields zero coverage and an
honest 'unknown', never a wrong call.

Design notes
------------
* ``parse_sam_line`` builds an explicit ref->query map per read, so indel
  and clipped CIGARs can never shift allele lookup off-register.
* ``template_support`` groups records by QNAME (mates = one template) and
  merges per-site allele calls; on mate disagreement the higher-MAPQ mate
  wins and the conflict is counted - a silently averaged molecule is not
  evidence.
* Secondary/supplementary/unmapped records are skipped (counted in
  ``stats``): they would double-count haplotypes or add none.
* Site allele calls are single-base: SNV sites classify cleanly as
  'ref'/'alt'/'other'. Indel alleles degrade to 'other'/'ref' at the
  anchor base - acceptable because candidate compound-het loci are
  assessed here for SNVs; indel phasing needs alignment-aware calling.
"""
from __future__ import annotations

import re
from typing import Iterable

# SAM FLAG bits used here.
_F_PAIRED = 0x1
_F_UNMAPPED = 0x4
_F_REVERSE = 0x10
_F_READ1 = 0x40
_F_READ2 = 0x80
_F_SECONDARY = 0x100
_F_QCFAIL = 0x200
_F_DUP = 0x400
_F_SUPPLEMENTARY = 0x800

_CIGAR_RE = re.compile(r"(\d+)([MIDNSHP=X])")
_CIGAR_FULL = re.compile(r"(\d+[MIDNSHP=X])+")

# op -> (consumes_reference, consumes_query)
_OPS = {
    "M": (True, True), "=": (True, True), "X": (True, True),
    "I": (False, True), "S": (False, True),
    "D": (True, False), "N": (True, False),
    "H": (False, False), "P": (False, False),
}

_BASES = {"A", "C", "G", "T", "N"}


def _decode_cigar(pos: int, cigar: str) -> tuple[dict[int, int], int | None]:
    """Build {1-based ref pos -> 0-based query index} and ref_end (1-based).

    Only M/=/X ops enter the map: they are the ops where a query base is
    aligned to a reference position. I/S consume query without a ref
    position (soft clips must NOT count as aligned); D/N consume ref
    without a query base (no allele to report); H/P consume nothing.
    """
    ref_to_q: dict[int, int] = {}
    q = 0
    r = pos
    ref_end: int | None = None
    for n_s, op in _CIGAR_RE.findall(cigar):
        n = int(n_s)
        cr, cq = _OPS[op]
        if cr and cq:
            for i in range(n):
                ref_to_q[r + i] = q + i
        if cr:
            r += n
            ref_end = r - 1
        if cq:
            q += n
    return ref_to_q, ref_end


def parse_sam_line(line: str) -> dict | None:
    """Parse one SAM record; return None for header/blank/malformed lines.

    Returned dict carries the 11 mandatory fields plus parsed FLAG bits,
    optional tags, and the derived ``ref_to_query`` coordinate map /
    ``ref_end`` (both empty/None for unmapped records).
    """
    if not line:
        return None
    line = line.rstrip("\r\n")
    if not line or line.startswith("@"):
        return None
    cols = line.split("\t")
    if len(cols) < 11:
        return None
    qname, flag_s, rname, pos_s, mapq_s, cigar = cols[:6]
    rnext, pnext_s, tlen_s, seq, qual = cols[6:11]
    try:
        flag = int(flag_s)
        pos = int(pos_s)
        mapq = int(mapq_s)
        pnext = int(pnext_s)
        tlen = int(tlen_s)
    except ValueError:
        return None
    if flag < 0 or pos < 0 or mapq < 0:
        return None
    if cigar != "*" and not _CIGAR_FULL.fullmatch(cigar):
        return None

    unmapped = bool(flag & _F_UNMAPPED) or rname == "*" or cigar == "*" \
        or pos == 0
    if unmapped:
        ref_to_q: dict[int, int] = {}
        ref_end = None
    else:
        ref_to_q, ref_end = _decode_cigar(pos, cigar)

    tags: dict[str, str] = {}
    for t in cols[11:]:
        parts = t.split(":", 2)
        if len(parts) == 3:
            tags[parts[0]] = parts[2]

    return {
        "qname": qname, "flag": flag, "rname": rname, "pos": pos,
        "mapq": mapq, "cigar": cigar, "rnext": rnext, "pnext": pnext,
        "tlen": tlen, "seq": seq, "qual": qual, "tags": tags,
        "ref_to_query": ref_to_q, "ref_end": ref_end,
        "is_unmapped": unmapped,
        "is_paired": bool(flag & _F_PAIRED),
        "is_read1": bool(flag & _F_READ1),
        "is_read2": bool(flag & _F_READ2),
        "is_reverse": bool(flag & _F_REVERSE),
        "is_secondary": bool(flag & _F_SECONDARY),
        "is_supplementary": bool(flag & _F_SUPPLEMENTARY),
        "is_duplicate": bool(flag & _F_DUP),
        "is_qcfail": bool(flag & _F_QCFAIL),
    }


def read_allele_at(rec: dict, chrom: str, pos: int) -> str | None:
    """Base a read carries at a 1-based reference position, or None.

    None when the read is on a different contig, does not align over
    ``pos`` (soft-clip / insertion / deletion / outside the aligned span),
    or when the SEQ/QUAL strings do not cover the mapped query index
    (a truncated base-quality string means the base call is unreliable).
    A QUAL of '*' means no qualities exist at all - the base itself is
    still knowable, so it is returned (callers stratify on MAPQ, not
    per-base quality).
    """
    if not rec or rec["rname"] != chrom:
        return None
    qpos = rec["ref_to_query"].get(pos)
    if qpos is None:
        return None
    seq = rec["seq"]
    if qpos >= len(seq):
        return None
    qual = rec["qual"]
    if qual != "*" and qpos >= len(qual):
        return None
    return seq[qpos].upper()


def template_support(sam_iter: Iterable[str], sites,
                     min_mapq: int = 0) -> dict:
    """Collect per-template allele calls at ``sites`` from SAM lines.

    ``sites`` is a list of ``(chrom, pos, ref, alt)`` tuples. Records are
    grouped by QNAME (mates = one template); each read covering a site
    casts one (base, MAPQ) vote. Mates are merged into a single template
    allele per site - on disagreement the higher-MAPQ mate wins and the
    conflict is counted in ``n_mate_disagreements``.

    Returns::

        {
          "sites": [(chrom,pos,ref,alt), ...],
          "templates": {qname: {(chrom,pos): {"base","class","n_reads",
                                             "disagreed","mapq"}}},
          "n_templates", "n_mate_disagreements",
          "templates_per_site": {"chrom:pos": n},
          "stats": {records/skipped counters},
        }

    ``class`` is 'ref', 'alt' or 'other' (a third allele - typically a
    sequencing error or an indel allele this single-base view cannot
    represent; 'other' templates never count toward trans/cis classes).
    """
    site_list = [tuple(s) for s in sites]
    meta = {(c, p): (r, a) for c, p, r, a in site_list}
    stats = {"records": 0, "skipped_malformed": 0, "skipped_unmapped": 0,
             "skipped_secondary_supp": 0, "skipped_low_mapq": 0}

    # qname -> {site_key: [(base, mapq), ...]}
    votes: dict[str, dict[tuple, list[tuple[str, int]]]] = {}
    for line in sam_iter:
        rec = parse_sam_line(line)
        if rec is None:
            stats["skipped_malformed"] += 1
            continue
        stats["records"] += 1
        if rec["is_unmapped"]:
            stats["skipped_unmapped"] += 1
            continue
        if rec["is_secondary"] or rec["is_supplementary"]:
            stats["skipped_secondary_supp"] += 1
            continue
        if rec["mapq"] < min_mapq:
            stats["skipped_low_mapq"] += 1
            continue
        hits = {}
        for (c, p) in meta:
            if rec["rname"] != c:
                continue
            b = read_allele_at(rec, c, p)
            if b is not None:
                hits[(c, p)] = b
        if not hits:
            continue
        slot = votes.setdefault(rec["qname"], {})
        for k, b in hits.items():
            slot.setdefault(k, []).append((b, rec["mapq"]))

    templates: dict[str, dict] = {}
    disagreements = 0
    for qname, site_map in votes.items():
        t: dict[tuple, dict] = {}
        for (c, p), vs in site_map.items():
            bases = {b for b, _ in vs}
            if len(bases) > 1:
                disagreements += 1
                # Higher-MAPQ mate wins; alphabetical base breaks ties so
                # the merge is deterministic for a fixed input order.
                best = sorted(vs, key=lambda bm: (-bm[1], bm[0]))[0][0]
                disagreed = True
            else:
                best = vs[0][0]
                disagreed = False
            ref, alt = meta[(c, p)]
            cls = ("alt" if best == alt.upper()
                   else "ref" if best == ref.upper() else "other")
            t[(c, p)] = {"base": best, "class": cls, "n_reads": len(vs),
                         "disagreed": disagreed,
                         "mapq": max(m for _, m in vs)}
        templates[qname] = t

    per_site = {k: 0 for k in meta}
    for t in templates.values():
        for k in t:
            per_site[k] += 1
    return {
        "sites": site_list,
        "templates": templates,
        "n_templates": len(templates),
        "n_mate_disagreements": disagreements,
        "templates_per_site": {f"{c}:{p}": n for (c, p), n in
                               per_site.items()},
        "stats": stats,
    }


def phase_from_reads(sam_iter: Iterable[str], v1, v2,
                     min_support: int = 3, min_mapq: int = 0) -> dict:
    """Phase ``v1`` x ``v2`` from read-level evidence.

    ``v1``/``v2`` are ``(chrom, pos, ref, alt)`` tuples in VCF convention;
    the SAM must share the contig naming. Returns a PhaseCall-like dict::

        {"relation": "trans"|"cis"|"unknown",
         "mechanism": "read_level",
         "counts": {...}, "min_support": n, "detail": str}

    Verdict rules (conservative, evidence-first):

    * ``trans`` iff (alt@v1 + ref@v2) AND (ref@v1 + alt@v2) templates each
      reach ``min_support`` AND alt@both templates == 0 (the count is
      always reported - a single alt@both molecule breaks the claim).
    * ``cis`` iff alt@both AND ref@both templates each reach
      ``min_support`` AND no trans-class template exists.
    * anything else - including zero spanning templates when the sites
      exceed the insert span - is 'unknown' with the counts reported.
    """
    v1, v2 = tuple(v1), tuple(v2)
    sup = template_support(sam_iter, [v1, v2], min_mapq=min_mapq)
    k1, k2 = (v1[0], v1[1]), (v2[0], v2[1])
    counts = {"alt1_ref2": 0, "ref1_alt2": 0, "alt_alt": 0, "ref_ref": 0,
              "other": 0, "partial": 0, "spanning": 0,
              "templates_total": sup["n_templates"],
              "mate_disagreements": sup["n_mate_disagreements"]}
    for tmap in sup["templates"].values():
        a1, a2 = tmap.get(k1), tmap.get(k2)
        if a1 is None and a2 is None:
            continue
        if a1 is None or a2 is None:
            counts["partial"] += 1
            continue
        counts["spanning"] += 1
        c1, c2 = a1["class"], a2["class"]
        if c1 == "alt" and c2 == "ref":
            counts["alt1_ref2"] += 1
        elif c1 == "ref" and c2 == "alt":
            counts["ref1_alt2"] += 1
        elif c1 == "alt" and c2 == "alt":
            counts["alt_alt"] += 1
        elif c1 == "ref" and c2 == "ref":
            counts["ref_ref"] += 1
        else:
            counts["other"] += 1

    if (counts["alt1_ref2"] >= min_support
            and counts["ref1_alt2"] >= min_support
            and counts["alt_alt"] == 0):
        relation = "trans"
    elif (counts["alt_alt"] >= min_support
            and counts["ref_ref"] >= min_support
            and counts["alt1_ref2"] == 0
            and counts["ref1_alt2"] == 0):
        relation = "cis"
    else:
        relation = "unknown"

    detail = (
        f"read_level: alt1_ref2={counts['alt1_ref2']} "
        f"ref1_alt2={counts['ref1_alt2']} alt_alt={counts['alt_alt']} "
        f"ref_ref={counts['ref_ref']} other={counts['other']} "
        f"partial={counts['partial']} spanning={counts['spanning']} "
        f"(min_support={min_support}) -> {relation}")
    return {"relation": relation, "mechanism": "read_level",
            "min_support": min_support, "counts": counts,
            "detail": detail}


def evidence_report(vcfsite_phasecall, read_phase: dict | None) -> dict:
    """Combine a PGT/PID PhaseCall with read-level evidence.

    ``vcfsite_phasecall`` is a :class:`src.phasing.PhaseCall` (or a dict
    with the same fields); ``read_phase`` is the dict returned by
    :func:`phase_from_reads` (or None when no SAM was supplied).

    ``agreement`` levels:

    * ``concordant``    - both lines decisive and identical
    * ``discordant``    - both decisive and contradictory (a real finding;
                          reported, never silently resolved)
    * ``read_only``     - VCF phasing unknown, reads decisive
    * ``vcf_only``      - VCF decisive, reads could not test it
    * ``uninformative`` - neither line decisive
    """
    if hasattr(vcfsite_phasecall, "relation"):
        v = {"relation": vcfsite_phasecall.relation,
             "mechanism": vcfsite_phasecall.mechanism,
             "detail": getattr(vcfsite_phasecall, "detail", "")}
    else:
        v = {"relation": vcfsite_phasecall.get("relation", "unknown"),
             "mechanism": vcfsite_phasecall.get("mechanism", "?"),
             "detail": vcfsite_phasecall.get("detail", "")}
    r = dict(read_phase) if read_phase else {
        "relation": "unknown", "mechanism": "none",
        "counts": {}, "detail": "no read-level evidence supplied"}

    decisive = {"trans", "cis"}
    vr, rr = v["relation"], r.get("relation")
    if vr in decisive and rr in decisive:
        agreement = "concordant" if vr == rr else "discordant"
        consensus = vr if vr == rr else "conflict"
    elif rr in decisive:
        agreement, consensus = "read_only", rr
    elif vr in decisive:
        agreement, consensus = "vcf_only", vr
    else:
        agreement, consensus = "uninformative", "unknown"

    detail = (f"vcf={vr}({v['mechanism']}) + reads={rr}"
              f"({r.get('mechanism', '?')}) -> {agreement}; "
              f"consensus={consensus}")
    return {"vcf_phase": v, "read_phase": r, "agreement": agreement,
            "consensus_relation": consensus, "detail": detail}
