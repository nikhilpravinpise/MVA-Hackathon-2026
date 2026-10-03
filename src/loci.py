"""Artifact-locus handling.

Genomic loci with documented mapping artifacts (the extended MHC and
similar low-mappability regions) are declared in ``config/pipeline.yaml``
under ``artifact_loci``. Facts falling inside a declared locus are removed
from hypothesis enumeration and disclosed as the ``locus_masked`` funnel
stage - the mask is the disclosure, not a hidden row-drop. See the
append-only decision row in docs/decisions.md.
"""
from __future__ import annotations


def _norm_chrom(chrom) -> str:
    """Contig comparison key: strip a leading 'chr' (case-insensitive),
    uppercase the rest. ``6``/``chr6``/``CHR6`` collapse together; so do
    ``X``/``chrX``. No UCSC-numeric mapping - artifact loci are declared on
    named contigs only."""
    c = str(chrom).strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    return c.upper()


def validate_artifact_loci(cfg: dict) -> None:
    """Fail loud on a malformed ``artifact_loci`` entry.

    Called once at ``run_pipeline`` entry: a malformed locus that silently
    matched nothing (or everything) would be an invisible funnel
    divergence - the same "loud is better" contract as load_config.
    """
    loci = cfg.get("artifact_loci")
    if loci is None:
        return
    if not isinstance(loci, list):
        raise ValueError(
            f"artifact_loci must be a list of mappings, got "
            f"{type(loci).__name__}")
    for i, loc in enumerate(loci):
        if not isinstance(loc, dict):
            raise ValueError(
                f"artifact_loci[{i}] must be a mapping, got "
                f"{type(loc).__name__}")
        for k in ("chrom", "start", "end"):
            if k not in loc:
                raise ValueError(
                    f"artifact_loci[{i}] missing required key {k!r}")
        if not isinstance(loc["chrom"], (str, int)) \
                or isinstance(loc["chrom"], bool):
            raise ValueError(
                f"artifact_loci[{i}].chrom must be a contig name, got "
                f"{loc['chrom']!r}")
        for k in ("start", "end"):
            v = loc[k]
            if not isinstance(v, int) or isinstance(v, bool):
                raise ValueError(
                    f"artifact_loci[{i}].{k} must be an int position, got "
                    f"{v!r}")
        if loc["start"] > loc["end"]:
            raise ValueError(
                f"artifact_loci[{i}] start={loc['start']} > "
                f"end={loc['end']} - bounds are inclusive and must be "
                "ordered")


def in_artifact_locus(chrom: str, pos: int, cfg: dict) -> str | None:
    """Return the locus label if (chrom, pos) falls inside a declared
    artifact locus (inclusive bounds), else ``None``.

    Pure function: a missing/empty ``artifact_loci`` list is a no-op.
    """
    loci = cfg.get("artifact_loci") or []
    key = _norm_chrom(chrom)
    for loc in loci:
        if _norm_chrom(loc["chrom"]) == key \
                and loc["start"] <= pos <= loc["end"]:
            return loc.get("label") or \
                f"{loc['chrom']}:{loc['start']}-{loc['end']}"
    return None
