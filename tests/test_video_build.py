"""Pure-function pins for video/build.py (captions + timing math).

The render/TTS/ffmpeg path needs Chrome, network and ffmpeg, so it is
exercised by `make track2-video`, not here."""
import importlib.util
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("video_build", REPO / "video" / "build.py")
vb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(vb)


def test_srt_time_rounding_and_hours():
    assert vb.srt_time(0) == "00:00:00,000"
    assert vb.srt_time(61.2346) == "00:01:01,235"
    assert vb.srt_time(3600 + 2.5) == "01:00:02,500"


def _w(text, start, end):
    return {"text": text, "start": start, "end": end}


def test_cues_split_on_length_and_offset_applied():
    words = [_w("alpha", 0.0, 0.4), _w("beta", 0.5, 0.9), _w("gamma", 1.0, 1.4)]
    cues = vb.caption_cues(words, offset=10.0, max_chars=11)
    assert cues == [(10.0, 10.9, "alpha beta"), (11.0, 11.4, "gamma")]


def test_cues_split_on_pause_and_skip_blank_tokens():
    words = [_w("one", 0.0, 0.2), _w(" ", 0.2, 0.3), _w("two", 2.0, 2.2)]
    cues = vb.caption_cues(words, offset=0.0, max_gap=0.6)
    assert [c[2] for c in cues] == ["one", "two"]


def test_cues_empty():
    assert vb.caption_cues([], offset=5.0) == []


def test_to_srt_numbering():
    srt = vb.to_srt([(0.0, 1.0, "a"), (1.0, 2.0, "b")])
    assert srt.splitlines()[:3] == ["1", "00:00:00,000 --> 00:00:01,000", "a"]
    assert "2\n00:00:01,000 --> 00:00:02,000\nb" in srt


def test_slide_html_escapes_text():
    page = vb.slide_html({"id": "x", "title": "<b>", "bullets": ["a&b"]}, 1, 1, "")
    assert "&lt;b&gt;" in page and "a&amp;b" in page and "<ul>" in page


@pytest.mark.skipif(not (REPO / "video" / "scenes.yaml").exists(),
                    reason="scenes.yaml not written yet")
def test_scenes_yaml_word_budget():
    """~150 wpm narration keeps a 3:00 cut; the builder enforces the hard
    limit on the rendered file, this pins the script budget early."""
    import yaml
    doc = yaml.safe_load((REPO / "video" / "scenes.yaml").read_text(encoding="utf-8"))
    words = sum(len(s["narration"].split()) for s in doc["scenes"])
    assert words <= 440, words
    assert "—" not in (REPO / "video" / "scenes.yaml").read_text(encoding="utf-8")
