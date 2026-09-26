"""Read-backed phasing: PGT/PID phase sets and cis/trans determination.

Why this module exists (plan.md Phase 3): a compound-heterozygous recessive
diagnosis requires the two alleles to be *in trans* (one per haplotype).
``a|b`` phased genotypes plus a shared phase-set id (``PID``) are emitted by
GATK/Sentieon physical phasing from reads - the challenge VCF carries them,
so the primary evidence is already in the file; reads/BAM (src/reads.py) and
WhatsHap (tools/run_phasing.py) are the orthogonal confirmations.

Model
-----
Each site carries ``pgt`` (e.g. ``1|0``) and ``pid`` (phase-set label, shared
by every site phased together by the same supporting reads). Within a phase
set the pgt string orders alleles on the SAME two haplotypes, so::

    v1 pgt=1|0 (alt on hap A), v2 pgt=0|1 (alt on hap B)  -> TRANS
    v1 pgt=1|0,              v2 pgt=1|0                   -> CIS
    v1 pgt=1|0,              v2 pgt=0|1 (different PID)   -> chain needed

Chaining: two sites in *different* phase sets can still be resolved when a
third site links them - standard "phase set bridging" is NOT possible from
PGT/PID alone (phase sets have independent haplotype labels), but a common
heterozygote shared across two sets via a trio/LD does. Without trio data we
honestly report ``unknown`` for cross-PID pairs rather than guess.

Allele-index convention: for pgt ``a|b``, position 0 = haplotype H1,
position 1 = H2. ``alt_hap`` below is the set of haplotypes carrying the
alt allele of interest (alt index assumed 1 for biallelic sites; multi-allelic
sites resolve by matching alt allele index).
"""
from __future__ import annotations

from dataclasses import dataclass

from .triage import VariantFacts


@dataclass(frozen=True)
class PhaseCall:
    """cis/trans verdict for a pair of variants."""
    relation: str           # 'trans' | 'cis' | 'unknown'
    mechanism: str          # 'pgt_pid_same_set' | 'unphased'
    detail: str = ""


def _alt_haplotypes(pgt: str | None, alt_index: int = 1) -> frozenset[int] | None:
    """Haplotype indices (0-based) carrying ``alt_index`` under a ``a|b`` PGT."""
    if not pgt or "|" not in pgt:
        return None
    try:
        a, b = pgt.split("|")[:2]
        a, b = int(a), int(b)
    except ValueError:
        return None
    haps: set[int] = set()
    if a == alt_index:
        haps.add(0)
    if b == alt_index:
        haps.add(1)
    return frozenset(haps)


def determine_phase(v1: VariantFacts, v2: VariantFacts) -> PhaseCall:
    """Resolve cis/trans between two variants from PGT/PID.

    Only same-chromosome, same-phase-set pairs are decidable without extra
    data. Each site's ``alt_index`` (1-based ALT ordinal, see
    :class:`src.triage.VariantFacts`) is read from the fact itself, so a
    multi-allelic site's second/third ALT resolves against the matching
    PGT allele index rather than assuming index 1 for every site.
    """
    if v1.chrom != v2.chrom:
        return PhaseCall("unknown", "unphased", "different contigs")

    h1 = _alt_haplotypes(v1.pgt, v1.alt_index)
    h2 = _alt_haplotypes(v2.pgt, v2.alt_index)

    if v1.pid and v2.pid and v1.pid == v2.pid and h1 is not None and h2 is not None:
        if not h1 or not h2:
            # e.g. 1|1 homozygous alt - carries alt on both haps; not a het pair
            return PhaseCall("unknown", "pgt_pid_same_set",
                             "homozygous PGT cannot define a het pair")
        relation = "trans" if h1.isdisjoint(h2) else "cis"
        return PhaseCall(
            relation, "pgt_pid_same_set",
            f"PID={v1.pid}: {v1.vid} alt on hap{sorted(h1)}, "
            f"{v2.vid} alt on hap{sorted(h2)}")

    if h1 is not None and h2 is not None:
        return PhaseCall("unknown", "unphased",
                         f"different phase sets ({v1.pid} vs {v2.pid}); "
                         "needs bridging evidence (reads, LD reference)")

    return PhaseCall("unknown", "unphased",
                     "missing PGT/PID - unphased genotypes")
