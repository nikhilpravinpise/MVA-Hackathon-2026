"""Frozen-config loader.

Reads config/pipeline.yaml (the decision-freeze artifact). Any post-freeze
change to that file must be justified in docs/decisions.md (plan.md 2.1.1).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "config" / "pipeline.yaml"


REQUIRED_SECTIONS = ("rarity", "consequence", "genotype_qc", "inheritance",
                     "scoring", "submission")

# Load-bearing numeric knobs and their legal ranges - a degenerate value
# here does not crash, it SILENTLY changes pipeline semantics (af_max<=0
# marks every variant common; a zero weight re-normalizes all scores).
_RANGE_CHECKS = (
    ("rarity.af_max", 0.0, float("inf"), "exclusive"),
    ("scoring.w_variant_damage", 0.0, 1.0, "inclusive"),
    ("scoring.w_phenotype", 0.0, 1.0, "inclusive"),
    ("scoring.w_inheritance", 0.0, 1.0, "inclusive"),
    ("scoring.emit_floor", 0.0, 1.0, "exclusive"),
    ("scoring.singleton_emit_floor", 0.0, 1.0, "exclusive"),
    ("scoring.epcr_top", 0.0, 1.0, "exclusive"),
    ("scoring.epcr_floor", 0.0, 1.0, "exclusive"),
    ("scoring.epcr_decay", 0.0, 1.0, "exclusive"),
    ("genotype_qc.min_dp", 0, float("inf"), "inclusive"),
    ("genotype_qc.min_gq", 0, float("inf"), "inclusive"),
    ("genotype_qc.het_vaf_min", 0.0, 1.0, "inclusive"),
    ("genotype_qc.het_vaf_max", 0.0, 1.0, "inclusive"),
    ("genotype_qc.hom_vaf_min", 0.0, 1.0, "inclusive"),
    ("submission.max_rows", 1, float("inf"), "inclusive"),
    ("submission.secondary_epcr_cap", 0.0, 1.0, "exclusive"),
    ("phenotype.ic_floor", 0.0, float("inf"), "inclusive"),
)


def _validate_ranges(cfg: dict, p: Path) -> None:
    """Range-check load-bearing numerics. A missing key uses the consumer's
    default (fine); a present-but-out-of-range value is a frozen-config bug
    and must fail at load time, not mid-funnel."""
    for dotted, lo, hi, mode in _RANGE_CHECKS:
        node = cfg
        parts = dotted.split(".")
        for part in parts[:-1]:
            node = node.get(part, {}) if isinstance(node, dict) else {}
        v = node.get(parts[-1]) if isinstance(node, dict) else None
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError(f"config {p}: {dotted}={v!r} is not numeric")
        ok = (lo < f < hi) if mode == "exclusive" else (lo <= f <= hi)
        if not ok:
            raise ValueError(
                f"config {p}: {dotted}={v!r} outside "
                f"{'(' if mode == 'exclusive' else '['}{lo},{hi}"
                f"{')' if mode == 'exclusive' else ']'} - a degenerate "
                "value would silently change pipeline semantics")


def load_config(path: str | Path | None = None) -> dict:
    """Load the frozen funnel configuration.

    Raises ``ValueError`` on a missing top-level section: consumers read
    ``cfg.get(...)`` with in-code defaults, so a lost section would silently
    fall back to duplicated defaults and diverge from the frozen config
    without any error. Also range-checks the load-bearing numerics: a
    degenerate af_max/emit_floor doesn't crash, it corrupts the funnel.
    Loud is better.
    """
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"config {p} is not a YAML mapping")
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ValueError(
            f"config {p} missing required section(s): {missing} - a "
            "missing section would silently fall back to in-code defaults "
            "and diverge from the frozen config")
    _validate_ranges(cfg, p)
    return cfg


def config_hash(path: str | Path | None = None) -> str:
    """SHA-256 of the on-disk config bytes - recorded in results for
    provenance when a run truly used the frozen file unmodified."""
    import hashlib

    p = Path(path) if path else DEFAULT_CONFIG
    return hashlib.sha256(p.read_bytes()).hexdigest()


def config_dict_hash(cfg: dict) -> str:
    """SHA-256 of the ACTUAL config dict a run used (canonical JSON).

    Unlike :func:`config_hash`, this reflects in-memory mutations (e.g. a
    sensitivity grid's per-point ``af_max``/``min_votes`` overrides) rather
    than re-hashing the on-disk file, so provenance never claims a frozen
    hash for a config that was actually modified before the run.
    """
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
