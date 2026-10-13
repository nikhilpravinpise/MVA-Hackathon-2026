"""Modal app for Track-2 lane-L5 compute (public data only - plan.md s5).

Functions:
    esm_variant_effect  - ESM-2 masked-marginal LLR scoring of BUB1B
                          p.Asn1002Lys + calibration panels (ClinVar
                          missense/nonsense, gnomAD common/ultra-rare).
                          GPU L4, timeout 1200 s. Default model
                          facebook/esm2_t33_650M_UR50D.
    prism_aneuploidy    - PRISM 19Q4 secondary screen x Cohen-Sharir
                          aneuploidy-score association (CPU): fetch ->
                          derive -> analyze -> JSON.

Volumes:
    mva-t2-cache - HuggingFace model cache + raw public downloads so
                   re-runs are cheap (public data only; the deletion
                   runbook wipes the volume for hygiene)

Run (lead only - agents must not invoke modal commands):
    MODAL_PROFILE=track2 modal run tools/modal_track2.py::esm_variant_effect
        --model-name facebook/esm2_t33_650M_UR50D
    MODAL_PROFILE=track2 modal run tools/modal_track2.py::prism_aneuploidy
    MODAL_PROFILE=track2 modal run tools/modal_track2.py        # both
    modal volume get mva-t2-cache out/esm.json docs/track2/evidence/esm.json
    modal volume get mva-t2-cache out/prism.json \\
        docs/track2/evidence/prism.json

Both functions also RETURN their result dict, so `modal run` prints the
JSON to stdout as a fallback capture path.
"""
from __future__ import annotations

import json
from pathlib import Path

import modal

app = modal.App("mva-track2")

CACHE = modal.Volume.from_name("mva-t2-cache", create_if_missing=True)
CACHE_DIR = "/cache"

REPO_ROOT = Path(__file__).resolve().parent.parent

# ------------------------------------------------------------- images
# The lane tools ride the image as local files; heavy deps only inside the
# container (transformers 5.x tested locally with torch 2.14.1+cpu).
esm_img = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("torch>=2.5,<3", "transformers>=4.56,<6")
    .add_local_file(str(REPO_ROOT / "tools" / "t2_esm.py"),
                    "/app/t2_esm.py")
)

prism_img = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install("openpyxl>=3.1")
    .add_local_file(str(REPO_ROOT / "tools" / "t2_prism.py"),
                    "/app/t2_prism.py")
)


def _save_and_return(result: dict, name: str) -> dict:
    """Persist result JSON on the cache volume AND return it."""
    out = Path(CACHE_DIR) / "out" / name
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    CACHE.commit()
    print(f"[modal_track2] wrote {out}")
    return result


@app.function(image=esm_img, gpu="L4", timeout=1200,
              volumes={CACHE_DIR: CACHE})
def esm_variant_effect(model_name: str = "facebook/esm2_t33_650M_UR50D",
                       max_gnomad_bg: int | None = None) -> dict:
    """Score BUB1B N1002K + calibration panels; return esm.json payload.

    Variant inputs (UniProt O60566 sequence, ClinVar queries, gnomAD r4
    missense) are fetched live inside the container on first run and
    cached on the volume; pass ``max_gnomad_bg`` to subsample the
    background if needed."""
    import sys
    sys.path.insert(0, "/app")
    import t2_esm

    inputs_path = Path(CACHE_DIR) / "esm_inputs.json"
    if inputs_path.exists():
        inputs = json.loads(inputs_path.read_text(encoding="utf-8"))
        print(f"[esm] loaded cached inputs ({inputs['fetched_at']})")
    else:
        inputs = t2_esm.build_variant_inputs(Path(CACHE_DIR))
        CACHE.commit()

    scorer = t2_esm.EsmScorer(model_name=model_name, device="cuda")
    result = t2_esm.score(inputs, scorer=scorer,
                          max_gnomad_bg=max_gnomad_bg)
    result["compute"] = {"runner": "modal", "gpu": "L4",
                         "model_name": model_name}
    return _save_and_return(result, "esm.json")


@app.function(image=prism_img, timeout=3600, memory=8192,
              volumes={CACHE_DIR: CACHE})
def prism_aneuploidy(min_lines: int = 100) -> dict:
    """Run the full PRISM x aneuploidy association; return prism.json
    payload. Raw public files download once into the cache volume."""
    import sys
    sys.path.insert(0, "/app")
    import t2_prism

    raw = Path(CACHE_DIR) / "prism_raw"
    raw.mkdir(parents=True, exist_ok=True)
    t2_prism.fetch(raw)
    CACHE.commit()
    t2_prism.derive(raw)
    CACHE.commit()
    result = t2_prism.analyze(raw, min_lines=min_lines)
    result["compute"] = {"runner": "modal", "gpu": None}
    return _save_and_return(result, "prism.json")


@app.local_entrypoint()
def run_all(model_name: str = "facebook/esm2_t33_650M_UR50D") -> None:
    """`modal run tools/modal_track2.py` -> both jobs, sequential."""
    esm_variant_effect.remote(model_name=model_name)
    prism_aneuploidy.remote()
