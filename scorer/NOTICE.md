# Vendored scoring oracle

`scorer/evaluation.py` is an unmodified copy of the MVA Hackathon 2026
Track 1 evaluation script, vendored from the hackathon's own public Space
source (`hackathon-app/evaluation.py` in this repo mirrors the same code).

It is used **only as the local scoring oracle** - we never reimplement its
logic, so a local score is the official score by construction. Source:
the hackathon evaluation Space on Hugging Face (MVA-Hackathon-2026);
all rights remain with the hackathon organizers. This file is attributed,
not relicensed; if the organizers publish a license it applies here.
