"""Submit tab for Track 2."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import gradio as gr

from config import MAX_TRACK2_SUBMISSIONS
from utils import (
    append_submission,
    get_hf_username,
    hf_username_to_display_slug,
    submissions_by_user,
)

INTRO_MD = f"""
Upload your Track 2 proposal here for review by our independent expert judging panel. Unlike Track 1,
this track uses qualitative evaluation rather than automated scoring.

You are allowed up to <u>{MAX_TRACK2_SUBMISSIONS} submissions</u> in case you need to make updates to your
findings/methods. The panel will only review your latest entry, so make sure your final submission is the one you
want reviewed.

**Team Participation:** Please designate a single team member to submit on the team's behalf. Additional or duplicate
submissions from other team members will not be reviewed.
"""

INSTRUCTIONS_MD = """
### 1. Write your report.

Prepare a written report (PDF or Markdown) proposing repositioned drug candidates supported by your
analysis. Include a characterization of the variant's mechanism (loss-of-function / gain-of-function,
pathway disrupted, downstream biological consequence) as the basis for your repurposing rationale.

> **Update 28 Aug 2026:** If you used an LLM or AI assistant, please record the provider, the plan or tier, and the
> relevant data-handling setting in your methods description. A line is enough, for example: *"Anthropic API, Claude
> Sonnet, commercial terms, no training on customer content."*

Not sure what details to include? Please use the provided methods description template to organize your
analysis and supporting materials, then export your report as a PDF or Markdown file for submission.

When saving your report, please include your username (or team name) in the filename. For example, if your
HF username is `jane-doe`, you might name your report file:

* `jane-doe_track2_report.pdf` (`.md` also accepted)

### 2. Prepare other supporting materials.

**GitHub Repository**

Your repository may remain private while the Hackathon is running. However, it must be made public once the
Hackathon ends so the panel can review your code and methods.

What to include:
- Documented, reproducible code (all scripts and configuration files needed to reproduce your results)
- Methods description *(optional but recommended)*

**Pitch Video**

Record a 3-minute pitch video walking through your reasoning and proposed candidates, then upload it to
YouTube or Vimeo.

### 3. After submission:

The independent panel will review all entries over a ~2-3 month window. Results will be announced at a
later date.
"""


def _handle_submit(
    display_name_input: str,
    github_url: str,
    video_url: str,
    report_file,
    notes: str,
    request: gr.Request,
    oauth_profile: gr.OAuthProfile | None = None,
) -> tuple:
    """Gradio callback - returns (feedback_md, quota_md, report_file)."""
    hf_username = get_hf_username(request, oauth_profile)
    if not hf_username:
        return "⚠️ Please sign in with your Hugging Face account to submit.", "", gr.update()

    display_name = (display_name_input or "").strip() or hf_username_to_display_slug(hf_username)

    github_url = (github_url or "").strip()
    if not github_url.startswith("https://github.com/"):
        return "⚠️ GitHub URL must start with `https://github.com/`.", _quota_status(request), gr.update()

    video_url = (video_url or "").strip()
    if not video_url:
        return "⚠️ A pitch video URL is required. Please upload your 3-minute video to YouTube or Vimeo and paste the link.", _quota_status(request), gr.update()

    if report_file is None:
        return "⚠️ Please upload your report (PDF or Markdown).", _quota_status(request), gr.update()

    report_path = report_file if isinstance(report_file, str) else report_file.name
    if Path(report_path).suffix.lower() not in {".pdf", ".md"}:
        return "⚠️ Report must be a PDF (.pdf) or Markdown (.md) file.", _quota_status(request), gr.update()

    count = submissions_by_user(hf_username, track=2)
    if count >= MAX_TRACK2_SUBMISSIONS:
        return (
            f"⚠️ You have already used all {MAX_TRACK2_SUBMISSIONS} submissions.",
            _quota_status(request),
            gr.update(),
        )
    submission_n = count + 1

    report_name = Path(
        report_file if isinstance(report_file, str) else report_file.name
    ).name

    entry = {
        "hf_username": hf_username,
        "display_name": display_name,
        "github_url": github_url,
        "video_url": (video_url or "").strip(),
        "report_filename": report_name,
        "notes": (notes or "").strip(),
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    append_submission(entry, report_path, track=2)

    video_line = f"[{entry['video_url']}]({entry['video_url']})" if entry["video_url"] else "_(not provided)_"

    feedback = f"""
## Track 2 submission received ✓

**{display_name}** (`{hf_username}`) &nbsp;|&nbsp; **Submission:** {submission_n}

Your submission has been logged and will be reviewed by the expert judging panel over the
~2-3 month judging window. Results will be announced after the judging period closes.

**What you submitted:**
- GitHub repository: [{github_url}]({github_url})
- Video: {video_line}
- Report file: `{report_name}`
"""
    return feedback.strip(), _quota_status(request), None


def _quota_status(request: gr.Request, oauth_profile: gr.OAuthProfile | None = None) -> str:
    hf_username = get_hf_username(request, oauth_profile)
    if not hf_username:
        return ""
    count = submissions_by_user(hf_username, track=2)
    remaining = MAX_TRACK2_SUBMISSIONS - count
    return (
        f'<div class="info-card quota-card">'
        f'<strong>{count} / {MAX_TRACK2_SUBMISSIONS}</strong> submissions used &nbsp;·&nbsp; '
        f'<strong>{remaining}</strong> remaining'
        f'</div>'
    )


def render() -> None:
    with gr.Tab("Submit - Track 2") as tab:
        gr.Markdown(INTRO_MD)
        quota_md = gr.HTML()
        with gr.Accordion("📋 Submission Format & Instructions", open=True, elem_classes=["faq-accordion"]):
            gr.Markdown("**Templates:**")
            gr.Markdown("<small>*Last updated 28 Aug 2026*</small>")
            with gr.Row():
                gr.DownloadButton(
                    label="📄 Methods description template (Excel)",
                    value="static/templates/methods_description_form.xlsx",
                    size="sm",
                    elem_classes=["template-dl-btn"],
                )
            gr.Markdown(INSTRUCTIONS_MD)
        gr.Markdown("---")
        with gr.Row():
            with gr.Column():
                team_name_box = gr.Textbox(
                    label="Team / Display Name (optional)",
                    placeholder="e.g. helix-squad",
                    info="This will be used for the public announcement. Leave blank to use your "
                         "HF username if you are participating individually.",
                )
                github_box = gr.Textbox(
                    label="GitHub repo URL *",
                    placeholder="https://github.com/your-org/your-repo",
                )
                video_box = gr.Textbox(
                    label="Pitch video URL *",
                    placeholder="https://youtu.be/...",
                )
                notes_box = gr.Textbox(
                    label="Notes for judges (optional)",
                    lines=3,
                    placeholder="Anything you want judges to know before they open your submission…",
                )
            with gr.Column():
                report_file = gr.File(
                    label="Report file (PDF or Markdown) *",
                    file_types=[".pdf", ".md"],
                )
        submit_btn = gr.Button("Submit", variant="primary")
        result_md = gr.Markdown(label="Confirmation")
        submit_btn.click(
            fn=_handle_submit,
            inputs=[team_name_box, github_box, video_box, report_file, notes_box],
            outputs=[result_md, quota_md, report_file],
        )
        tab.select(fn=_quota_status, inputs=[], outputs=quota_md)
    return quota_md
