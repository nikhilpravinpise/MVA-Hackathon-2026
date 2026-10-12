"""Pitch-video builder: scenes.yaml -> narrated, captioned 1080p mp4.

    .venv-video/Scripts/python.exe video/build.py            # full build
    .venv-video/Scripts/python.exe video/build.py --slides   # slides only

Pipeline per scene: narration text -> edge-tts neural voice (mp3 + word
timings) -> slide HTML rendered to a 1920x1080 PNG by headless Chrome
(playwright) -> still+audio clip (ffmpeg). Clips are concatenated, captions
(.srt) are built from the word timings, and the result is checked against
the 3:00 hard limit with ffprobe. Every step is deterministic given the
same voice service output; nothing here touches patient data.

Needs: ffmpeg/ffprobe on PATH, Chrome installed, `.venv-video` with
edge-tts + playwright + pyyaml (see video/README.md).
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
OUT = HERE / "out"
MAX_SECONDS = 180.0
PAD_SECONDS = 0.35          # breath between scenes
TICKS_PER_SEC = 10_000_000  # edge-tts offsets are 100-ns ticks


def srt_time(sec: float) -> str:
    """Seconds -> SRT timestamp `HH:MM:SS,mmm`."""
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def caption_cues(words: list[dict], offset: float, max_chars: int = 42,
                 max_gap: float = 0.6) -> list[tuple[float, float, str]]:
    """Group word timings (`{"text","start","end"}` in seconds, scene-local)
    into caption cues of at most `max_chars`, splitting on long pauses.
    Returns (start, end, text) in global seconds."""
    cues, cur, c_start, c_end = [], [], None, None
    for w in words:
        text = w["text"].strip()
        if not text:
            continue
        gap = (w["start"] - c_end) if c_end is not None else 0.0
        candidate = " ".join(cur + [text])
        if cur and (len(candidate) > max_chars or gap > max_gap):
            cues.append((offset + c_start, offset + c_end, " ".join(cur)))
            cur, c_start = [], None
        if c_start is None:
            c_start = w["start"]
        cur.append(text)
        c_end = w["end"]
    if cur:
        cues.append((offset + c_start, offset + c_end, " ".join(cur)))
    return cues


def to_srt(cues: list[tuple[float, float, str]]) -> str:
    lines = []
    for i, (a, b, t) in enumerate(cues, 1):
        lines += [str(i), f"{srt_time(a)} --> {srt_time(b)}", t, ""]
    return "\n".join(lines)


def load_scenes(path: Path) -> dict:
    import yaml
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    ids = [s["id"] for s in doc["scenes"]]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate scene ids in scenes.yaml")
    return doc


def slide_html(scene: dict, total: int, idx: int, css: str) -> str:
    body = scene.get("html") or "".join(
        f"<li>{html.escape(b)}</li>" for b in scene.get("bullets", []))
    if scene.get("bullets") and not scene.get("html"):
        body = f"<ul>{body}</ul>"
    kicker = html.escape(scene.get("kicker", ""))
    title = html.escape(scene.get("title", ""))
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{css}</style></head><body class="{scene.get('layout', 'std')}">
<div class="frame"><div class="kicker">{kicker}</div><h1>{title}</h1>
<div class="body">{body}</div>
<div class="foot"><span>nikhilpise - MVA Hackathon 2026 - Track 2</span>
<span>{idx}/{total}</span></div></div></body></html>"""


def render_slides(doc: dict) -> list[Path]:
    from playwright.sync_api import sync_playwright
    css = (HERE / "slides.css").read_text(encoding="utf-8")
    BUILD.mkdir(parents=True, exist_ok=True)
    pngs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1920, "height": 1080})
        scenes = doc["scenes"]
        for i, sc in enumerate(scenes, 1):
            hp = BUILD / f"{sc['id']}.html"
            hp.write_text(slide_html(sc, len(scenes), i, css), encoding="utf-8")
            page.goto(hp.as_uri())
            page.wait_for_timeout(150)
            png = BUILD / f"{sc['id']}.png"
            page.screenshot(path=str(png))
            pngs.append(png)
        browser.close()
    return pngs


async def _tts(text: str, voice: str, rate: str, mp3: Path) -> list[dict]:
    import edge_tts
    comm = edge_tts.Communicate(text, voice, rate=rate, boundary="WordBoundary")
    words = []
    with mp3.open("wb") as fh:
        async for chunk in comm.stream():
            if chunk["type"] == "audio":
                fh.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / TICKS_PER_SEC
                words.append({"text": chunk["text"], "start": start,
                              "end": start + chunk["duration"] / TICKS_PER_SEC})
    return words


def duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        check=True, capture_output=True, text=True).stdout.strip()
    return float(out)


def build(doc: dict) -> Path:
    voice = doc.get("voice", "en-US-AndrewNeural")
    rate = doc.get("rate", "+0%")
    pngs = render_slides(doc)
    clips, cues, t = [], [], 0.0
    timing = []
    for sc, png in zip(doc["scenes"], pngs):
        mp3 = BUILD / f"{sc['id']}.mp3"
        words = asyncio.run(_tts(sc["narration"].strip(), voice, rate, mp3))
        d = duration(mp3) + PAD_SECONDS
        clip = BUILD / f"{sc['id']}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", str(png),
             "-i", str(mp3), "-af", f"apad=pad_dur={PAD_SECONDS}",
             "-t", f"{d:.3f}", "-c:v", "libx264", "-tune", "stillimage",
             "-pix_fmt", "yuv420p", "-r", "30", "-c:a", "aac", "-b:a", "160k",
             "-ar", "48000", str(clip)], check=True)
        cues += caption_cues(words, t)
        timing.append({"id": sc["id"], "start": round(t, 2),
                       "seconds": round(d, 2)})
        t += d
        clips.append(clip)
    OUT.mkdir(parents=True, exist_ok=True)
    lst = BUILD / "concat.txt"
    lst.write_text("".join(f"file '{c.as_posix()}'\n" for c in clips),
                   encoding="utf-8")
    srt = OUT / "pitch.srt"
    srt.write_text(to_srt(cues), encoding="utf-8")
    raw = BUILD / "pitch_raw.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe",
                    "0", "-i", str(lst), "-c", "copy", str(raw)], check=True)
    final = OUT / "pitch.mp4"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-i",
                    str(srt), "-c", "copy", "-c:s", "mov_text",
                    "-metadata:s:s:0", "language=eng", str(final)], check=True)
    total = duration(final)
    (OUT / "timing.json").write_text(json.dumps(
        {"total_seconds": round(total, 2), "limit": MAX_SECONDS,
         "voice": voice, "scenes": timing}, indent=2), encoding="utf-8")
    print(f"pitch.mp4 {total:.1f}s ({len(clips)} scenes) -> {final}")
    if total > MAX_SECONDS:
        raise SystemExit(f"FAIL: {total:.1f}s exceeds the {MAX_SECONDS:.0f}s limit")
    return final


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scenes", default=str(HERE / "scenes.yaml"))
    ap.add_argument("--slides", action="store_true", help="render slides only")
    a = ap.parse_args(argv)
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise SystemExit(f"{tool} not on PATH")
    doc = load_scenes(Path(a.scenes))
    if a.slides:
        for p in render_slides(doc):
            print(p)
        return 0
    build(doc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
