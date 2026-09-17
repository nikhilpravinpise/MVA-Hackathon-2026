"""
Groundtruth loader for Track 1 evaluation.

* In production: load data from private HF dataset
* In local dev: use small hardcoded dataset (_LOCAL_FALLBACK)
"""

from __future__ import annotations

import json
import os
import warnings
from pathlib import Path

from config import GROUNDTRUTH_DATASET, GROUNDTRUTH_FILENAME

# Fallback for local development only.
_LOCAL_FALLBACK: dict[str, frozenset] = {
    "PROBAND01": frozenset([
        ("chr2", 12345678, "T", "G"),
        ("chr15", 12345678, "T", "G"),
    ]),
}


def load_groundtruth() -> dict[str, frozenset]:
    """
    Load the ground truth from a private HF dataset if HF_TOKEN is set,
    otherwise warn and return the local fallback.
    """
    token = os.environ.get("HF_TOKEN")

    if not token:
        warnings.warn(
            "HF_TOKEN not set - using local fallback ground truth. "
            "Set HF_TOKEN as a Space secret in production.",
            stacklevel=2,
        )
        return _LOCAL_FALLBACK

    try:
        from huggingface_hub import hf_hub_download

        path = hf_hub_download(
            repo_id=GROUNDTRUTH_DATASET,
            filename=GROUNDTRUTH_FILENAME,
            repo_type="dataset",
            token=token,
        )
        raw: dict = json.loads(Path(path).read_text())
        result = {}
        for proband_id, entry in raw.items():
            if proband_id.startswith("_"):
                continue
            if isinstance(entry, list):
                result[proband_id] = frozenset(tuple(v) for v in entry)
            else:
                variants = entry.get("primary_variants", [])
                result[proband_id] = frozenset(
                    (v["chrom"], v["pos"], v["ref"], v["alt"]) for v in variants
                )
        return result
    except Exception as e:
        warnings.warn(
            f"Failed to load ground truth from {GROUNDTRUTH_DATASET}: {e}. "
            "Falling back to local data.",
            stacklevel=2,
        )
        return _LOCAL_FALLBACK
