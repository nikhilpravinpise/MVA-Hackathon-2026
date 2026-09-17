"""Helpers to load from and push submissions.

* In production: submissions are written to a private HuggingFace dataset
* In local dev: submissions are written to a local folder
"""

from __future__ import annotations

import io
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path

from config import (
    LEADERBOARD_DATASET,
    TRACK1_SUBMISSIONS_FOLDER,
    TRACK2_SUBMISSIONS_FOLDER,
)

_LOCAL_DEV_DIR = Path("local_dev")


# ── Leaderboard cache ────────────────────────────────────────────────────────
# To help speed up leaderboard rendering, we cache the last downloaded leaderboard for a short time.
_leaderboard_cache: list[dict] = []
_leaderboard_cache_time: float = 0
_LEADERBOARD_CACHE_TTL = 60  # seconds


def _sanitize(name: str) -> str:
    """Return a filename-safe version of a name."""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "unknown"


# ── Identity helpers ────────────────────────────────────────────────

def get_hf_username(request=None, oauth_profile=None) -> str | None:
    """Extract HF username from a Gradio OAuthProfile or request, with a local dev override.

    Set HF_USERNAME_OVERRIDE in your environment to simulate a logged-in user
    during local development (where OAuth is not available).
    """
    override = os.getenv("HF_USERNAME_OVERRIDE")
    if override:
        return override
    if oauth_profile is not None:
        return getattr(oauth_profile, "username", None)
    return getattr(request, "username", None) if request else None


def hf_username_to_display_slug(username: str) -> str:
    """Convert an HF username to a display-safe slug (lowercase, hyphens)."""
    slug = re.sub(r"[^a-z0-9]+", "-", username.lower()).strip("-")
    return slug or "participant"


# ── Submissions ──────────────────────────────────────────────────────────────

# Track folder mapping
_TRACK_FOLDERS = {
    1: TRACK1_SUBMISSIONS_FOLDER,
    2: TRACK2_SUBMISSIONS_FOLDER,
}


def _local_submissions_dir(track: int = 1) -> Path:
    folder_name = f"track{track}_submissions"
    return _LOCAL_DEV_DIR / folder_name


def append_submission(entry: dict, report_path: str | None = None, *, track: int = 1) -> None:
    """
    Store a single submission as its own JSON file in the HF dataset (or locally in dev).
    Optionally also saves a report file alongside the JSON.
    
    Args:
        entry: Submission metadata dict
        report_path: Optional path to a report file to upload
        track: Track number (1 or 2)
    """
    submissions_folder = _TRACK_FOLDERS[track]
    track_label = f"track{track}"
    
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    safe_user = _sanitize(entry.get("hf_username", "unknown"))
    subfolder = f"{submissions_folder}{safe_user}/"
    filename = f"sub_{timestamp}.json"

    # Stamp the report filename with the same timestamp as the metadata.
    if report_path and entry.get("report_filename"):
        ext = Path(entry["report_filename"]).suffix
        entry["report_filename"] = f"report_{timestamp}{ext}"

    payload = json.dumps(entry, indent=2).encode()

    token = os.environ.get("HF_TOKEN")
    if token:
        from huggingface_hub import upload_file

        upload_file(
            path_or_fileobj=io.BytesIO(payload),
            path_in_repo=f"{subfolder}{filename}",
            repo_id=LEADERBOARD_DATASET,
            repo_type="dataset",
            token=token,
            commit_message=f"{track_label}: {entry.get('display_name', entry.get('hf_username', '?'))}",
        )
        if report_path and entry.get("report_filename"):
            upload_file(
                path_or_fileobj=report_path,
                path_in_repo=f"{subfolder}{entry['report_filename']}",
                repo_id=LEADERBOARD_DATASET,
                repo_type="dataset",
                token=token,
                commit_message=f"{track_label} report: {entry.get('display_name', entry.get('hf_username', '?'))}",
            )
    else:
        import shutil
        local_dir = _local_submissions_dir(track) / safe_user
        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / filename).write_bytes(payload)
        if report_path and entry.get("report_filename"):
            shutil.copy(report_path, local_dir / entry["report_filename"])


def load_leaderboard(force_refresh: bool = False) -> list[dict]:
    """
    Download all Track 1 submissions from the HF dataset and return them as a list.
    Falls back to local_dev/track1_submissions/ when HF_TOKEN is not set.
    """
    global _leaderboard_cache, _leaderboard_cache_time

    # Return cached data if still fresh
    if not force_refresh and _leaderboard_cache and (time.time() - _leaderboard_cache_time) < _LEADERBOARD_CACHE_TTL:
        return _leaderboard_cache

    token = os.environ.get("HF_TOKEN")
    if token:
        from huggingface_hub import snapshot_download

        try:
            # Download all submission JSON files in parallel with smart caching
            # Only downloads changed files; caches file listing for fast subsequent calls
            snapshot_path = snapshot_download(
                repo_id=LEADERBOARD_DATASET,
                repo_type="dataset",
                token=token,
                allow_patterns=f"{TRACK1_SUBMISSIONS_FOLDER}*/sub_*.json",
            )
            # Read all downloaded JSON files
            rows = []
            submissions_dir = Path(snapshot_path) / TRACK1_SUBMISSIONS_FOLDER.rstrip("/")
            if submissions_dir.exists():
                for f in submissions_dir.glob("*/sub_*.json"):
                    try:
                        rows.append(json.loads(f.read_text()))
                    except Exception:
                        continue
            _leaderboard_cache = rows
            _leaderboard_cache_time = time.time()
            return rows
        except Exception:
            return _leaderboard_cache or []

    # Local dev fallback
    rows = []
    for f in sorted(_local_submissions_dir(track=1).glob("**/sub_*.json")):
        try:
            rows.append(json.loads(f.read_text()))
        except Exception:
            continue
    _leaderboard_cache = rows
    _leaderboard_cache_time = time.time()
    return rows


def best_per_team(rows: list[dict]) -> list[dict]:
    """Return the best-scoring submission per team (display_name), sorted by score.
    
    Groups by display_name (team name), falling back to hf_username if not set.
    Among tied scores, earlier submissions rank higher.
    """
    best: dict[str, dict] = {}
    for row in rows:
        # Group by display_name (team name) first, then hf_username as fallback
        team = row.get("display_name") or row.get("hf_username") or "unknown"
        if team not in best:
            best[team] = row
        else:
            prev = best[team]
            if (row["rank_points"], row["f_max"]) > (prev["rank_points"], prev["f_max"]):
                best[team] = row

    # Sort by score (descending), then by submission time (ascending - earlier is better)
    sorted_rows = sorted(
        best.values(),
        key=lambda r: (-r["rank_points"], -r["f_max"], r.get("submitted_at", ""))
    )
    return [{**r, "place": i} for i, r in enumerate(sorted_rows, 1)]


def _list_user_files(hf_username: str, *, track: int = 1) -> list[str]:
    """Return sorted list of JSON submission paths for a user in the given track."""
    safe_user = _sanitize(hf_username)
    folder = _TRACK_FOLDERS[track]
    prefix = f"{folder}{safe_user}/sub_"
    token = os.environ.get("HF_TOKEN")
    if token:
        from huggingface_hub import HfApi
        try:
            return sorted(
                f for f in HfApi().list_repo_files(LEADERBOARD_DATASET, repo_type="dataset", token=token)
                if f.startswith(prefix) and f.endswith(".json")
            )
        except Exception:
            return []
    user_dir = _local_submissions_dir(track) / safe_user
    if not user_dir.exists():
        return []
    return sorted(str(f) for f in user_dir.glob("sub_*.json"))


def submissions_by_user(hf_username: str, *, track: int = 1) -> int:
    """Return the number of submissions made by a given HF user for the specified track."""
    return len(_list_user_files(hf_username, track=track))


def leaderboard_df() -> list[list]:
    """Return rows formatted for gr.Dataframe."""
    rows = best_per_team(load_leaderboard())
    if not rows:
        return []
    out = []
    for r in rows:
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(r["place"], str(r["place"]))
        display = r.get("display_name") or r.get("hf_username") or r.get("team", "?")
        hf_user = r.get("hf_username") or r.get("team", "?")
        participant = f"{display} (@{hf_user})" if display != hf_user else f"@{hf_user}"
        out.append([
            medal,
            participant,
            f'{r["rank_points"]:.1f}',
            f'{r["f_max"]:.3f}',
            r.get("filename") or r.get("model", ""),
            r["submitted_at"],
        ])
    return out
