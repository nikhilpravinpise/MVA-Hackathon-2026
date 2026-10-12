# Pitch video

`video/out/pitch.mp4` is the 3-minute Track 2 pitch required by the
submission form (YouTube or Vimeo link; the form rejects a submission
without one). It is built, not recorded, so it regenerates whenever a
number in the report changes.

## Build

```sh
python -m venv .venv-video
.venv-video/Scripts/python.exe -m pip install edge-tts playwright pyyaml
.venv-video/Scripts/python.exe video/build.py            # full build
.venv-video/Scripts/python.exe video/build.py --slides   # slides only
```

Needs `ffmpeg`/`ffprobe` on PATH and Chrome installed (playwright drives
the installed browser, nothing is downloaded).

| Path | What |
|---|---|
| `scenes.yaml` | the script: narration (spoken) + bullets/html (on screen), voice and rate |
| `slides.css` | slide design (1920x1080, dark, three axis colours) |
| `build.py` | narration -> neural TTS -> slide PNG -> clip -> concat -> captions |
| `out/pitch.mp4` | the deliverable (gitignored; rebuild it) |
| `out/pitch.srt` | captions, also muxed into the mp4 as a soft subtitle track |
| `out/timing.json` | per-scene durations + the total the gate checks |

## The 3:00 gate

`build.py` measures the rendered file with `ffprobe` and fails if it
exceeds 180 s. `tests/test_video_build.py` pins the script's word budget
(calibrated from the measured cut) and re-checks `out/timing.json` when a
build is present, so the limit cannot drift silently.

Every figure spoken in the narration exists in `docs/track2/evidence/`;
see `docs/track2_report.md` for the sourced version of each claim.

## Upload (operator)

1. Upload `out/pitch.mp4` to YouTube (unlisted is fine) or Vimeo.
2. Open the link in a logged-out window to confirm it plays.
3. Paste it into the Track 2 submit form (see
   `docs/track2/submission_fields.md`).
