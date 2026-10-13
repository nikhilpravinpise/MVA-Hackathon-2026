"""Loader for config/track2.yaml (the Track 2 decision-freeze artifact).

Same discipline as src/config.py: a missing required section fails loudly at
load time rather than silently falling back to defaults.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = REPO / "config" / "track2.yaml"

REQUIRED_SECTIONS = ("case", "seed_genes", "module", "approval",
                     "scoring", "benchmark", "endpoints")


def load_config(path: str | Path | None = None) -> dict:
    p = Path(path) if path else DEFAULT_CONFIG
    with open(p, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg, dict):
        raise ValueError(f"config {p} is not a YAML mapping")
    missing = [s for s in REQUIRED_SECTIONS if s not in cfg]
    if missing:
        raise ValueError(f"config {p} missing required section(s): {missing}")
    return cfg


def config_hash(path: str | Path | None = None) -> str:
    """SHA-256 of the on-disk config bytes (provenance for a frozen file)."""
    p = Path(path) if path else DEFAULT_CONFIG
    return hashlib.sha256(p.read_bytes()).hexdigest()


def config_dict_hash(cfg: dict) -> str:
    """SHA-256 of the actual config dict used (canonical JSON)."""
    return hashlib.sha256(
        json.dumps(cfg, sort_keys=True, default=str).encode()).hexdigest()
