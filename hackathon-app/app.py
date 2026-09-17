"""
Rare Disease, Real Kid: The MVA Hackathon 2026
"""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

import gradio as gr

from config import CHALLENGE_ACTIVE, SPONSOR_LOGOS
from tabs import (
    about,
    faq,
    leaderboard,
    rules,
    submit_track1,
    submit_track2,
)
from utils import leaderboard_df


def _data_uri(path: str) -> str:
    """
    Read a static asset and return a base64 data URI - works locally and on HF Spaces.
    Returns an empty string if the file doesn't exist (e.g. before web UI upload).
    """
    p = Path(path)
    if not p.exists():
        return ""
    mime = mimetypes.guess_type(p.name)[0] or "application/octet-stream"
    encoded = base64.b64encode(p.read_bytes()).decode()
    return f"data:{mime};base64,{encoded}"


IMG_CHILD = _data_uri("static/child-drawing.png")
_sponsor_imgs = [
    (_data_uri(path), alt, cls) for path, alt, cls in SPONSOR_LOGOS
]
_sponsor_html = "\n".join(
    f'<img src="{src}" alt="{alt}"' + (f' class="{cls}"' if cls else '') + '>'
    for src, alt, cls in _sponsor_imgs
)

# Load CSS from file and wrap it for injection.
_css = Path("static/styles.css").read_text()
GLOBAL_STYLES = f"""<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;0,9..40,800;1,9..40,400&display=swap" rel="stylesheet">
<style>
{_css}
</style>
"""



HERO_HTML = f"""
{GLOBAL_STYLES}
<div id="page-top"></div>
<div class="challenge-hero">
  <div class="badge">🧬 Rare Disease Hackathon</div>
  <h1>Rare Disease, Real Kid: The MVA Hackathon 2026</h1>
  <p>
    The genome and clinical story on this page belong to a real child living with
    Mosaic Variegated Aneuploidy (MVA), an ultra-rare genetic condition affecting fewer than
    50 people worldwide. There is currently no established treatment, and care today means
    managing symptoms.
  </p>
  <p class="hero-lede">
    The family has opened the case to the research community, hoping someone can find an answer.
  </p>
  <h3>Help us understand MVA better!</h3>
  <div class="sponsor-row">
    <span class="sponsor-row-label">Made possible by</span>
    <div class="sponsor-row-logos">
      {_sponsor_html}
    </div>
    <br/>
    <span class="hero-disclaimer">
      The MVA Hackathon is not intended to provide general medical care, diagnosis, or professional
      medical advice.
    </span>
  </div>
</div>
"""

# ─────────────────────────────────────────────────────────────────────────────
# Main app
# ─────────────────────────────────────────────────────────────────────────────
with gr.Blocks(title="Rare Disease, Real Kid: The MVA Hackathon 2026") as app:
    gr.HTML(HERO_HTML)
    if CHALLENGE_ACTIVE:
        gr.Markdown("**Register now - sign in to participate!**", elem_classes=["login-cta"])
        gr.LoginButton(elem_id="login-btn")
    else:
        gr.Markdown(
            "_Registration is now closed._",
            elem_classes=["login-cta"],
        )
    with gr.Tabs():
        about.render(img_child=IMG_CHILD)
        lb_table = leaderboard.render()
        app.load(fn=leaderboard_df, outputs=lb_table)
        if CHALLENGE_ACTIVE:
            quota_t1 = submit_track1.render()
            status_t2 = submit_track2.render()
            app.load(fn=submit_track1._quota_status, outputs=quota_t1)
            app.load(fn=submit_track2._quota_status, outputs=status_t2)
        faq.render()
        rules.render()



if __name__ == "__main__":
    app.launch(
        theme=gr.themes.Soft(
            primary_hue=gr.themes.colors.cyan,
            secondary_hue=gr.themes.colors.blue,
        ),
        css="footer.svelte-1ax1toq { display: none !important; }",
        allowed_paths=["static/", "templates/"],
    )
