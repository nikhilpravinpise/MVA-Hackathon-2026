"""Frozen-config loader.

Reads config/pipeline.yaml (the decision-freeze artifact). Any post-freeze
change to that file must be justified in docs/decisions.md (plan.md 2.1.1).
"""
from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = REPO / "config" / "pipeline.yaml"


def load_config(path: str | Path | None = None) -> dict:
    """Load the frozen funnel configuration."""
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


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
