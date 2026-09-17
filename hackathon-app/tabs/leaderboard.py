"""Leaderboard tab for Track 1."""

from __future__ import annotations

import gradio as gr

from config import LEADERBOARD_HEADERS, CHALLENGE_ACTIVE
from utils import leaderboard_df

LEADERBOARD_MD = """
## Track 1 Leaderboard

Rankings update automatically as valid prediction files are scored. Only your team's highest-scoring prediction file
is displayed.

**Metrics:** Rank Points & F-max (adapted from _Stenton et al., 2024_)

> **Note:** Final Track 1 evaluation also includes your **methods write-up**, which is not reflected here. Your
> write-ups will be reviewed by a judging panel for scientific rigor after the Hackathon closes. See the FAQ
> for details.
"""


def render() -> gr.Dataframe:
    with gr.Tab("Leaderboard"):
        gr.Markdown(LEADERBOARD_MD)
        lb_table = gr.Dataframe(
            value=[],
            headers=LEADERBOARD_HEADERS,
            datatype=["str"] * 6,
            interactive=False,
            wrap=True,
            every=60 if CHALLENGE_ACTIVE else None,
            max_height=800,
        )
        refresh_btn = gr.Button("↻ Refresh leaderboard", variant="secondary", size="sm")
        refresh_btn.click(fn=leaderboard_df, inputs=[], outputs=lb_table)
        return lb_table
