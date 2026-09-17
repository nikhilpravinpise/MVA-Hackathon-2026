"""Submit tab for Track 1."""

from __future__ import annotations

import os
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path

import gradio as gr

from config import MAX_TRACK1_SUBMISSIONS
from evaluation import load_submission, score_proband
from groundtruth import load_groundtruth
from utils import (
    append_submission,
    get_hf_username,
    hf_username_to_display_slug,
    submissions_by_user,
)

# Loaded once at startup (from private HF dataset if HF_TOKEN is set, else local fallback)
_GT = load_groundtruth()

INTRO_MD = f"""
Upload your Track 1 predictions file below to receive instant evaluation against the confirmed clinical groundtruth.

You are allowed up to <u>{MAX_TRACK1_SUBMISSIONS} submissions</u>; only your highest-scoring submission will be
featured on the leaderboard.

**Team Participation:** Each member receives their own submission quota; coordinate with your teammates to avoid
using submissions unnecessarily, and ensure everyone uses the exact same team name so your entries group
together on the leaderboard.
"""

INSTRUCTIONS_MD = """
### 1. Create your predictions file.

One row per proposed causal variant (or compound-het pair). Rank your predictions by your own estimated probability
of causal relationship (EPCR), where 1 is most likely causal and 0 is least likely. There is no fixed "confident enough"
cutoff, as only your ranking relative to your own guesses matters for scoring. Coordinates must use GRCh38.

**Up to 10 candidate rows accepted**. This is one case, not a cohort, so we're asking for your best-ranked guesses, not
an exhaustive list. Flag whether each row is your primary candidate or a secondary/incidental finding using the `finding_type`
column. Secondary or incidental findings won't hurt your automated score - include them if you want them considered.

| Field | Type | Description |
|---|---|---|
| `proband_id` | string | Proband identifier (provided in the dataset) |
| `chrom_1` | string | Chromosome of the first (or only) variant (e.g. `chr15`) |
| `pos_1` | integer | GRCh38 base-pair position of the first variant |
| `ref_1` | string | Reference allele of the first variant |
| `alt_1` | string | Alternate allele of the first variant |
| `chrom_2` | string | Chromosome of the second variant (if any); compound-het pairs only, blank otherwise |
| `pos_2` | integer | GRCh38 base-pair position of the second variant (blank if not applicable) |
| `ref_2` | string | Reference allele of the second variant (blank if not applicable) |
| `alt_2` | string | Alternate allele of the second variant (blank if not applicable) |
| `epcr` | float | Estimated probability of causal relationship, (0, 1] |
| `finding_type` | string | `primary` or `secondary` |
| `notes` | string | Optional - brief rationale, especially for secondary findings. For example, findings unrelated to the primary condition, but still worth surfacing |

When saving your predictions file, please include your username (or team name) in the filename, as well as a 
short descriptive name for your model or approach. For example, if your HF username is `jane-doe`, you might
name your predictions file:

* `jane-doe_gatk-haplotype.csv`
* `jane-doe_deepvariant-v2.csv`

### 2. Write your report.

Each model must include a brief report (PDF or Markdown) describing your approach, rationale, and any supporting evidence.
This is required for judging, but is not scored automatically.

> **Update 28 Aug 2026:** If you used an LLM or AI assistant, please record the provider, the plan or tier, and the
> relevant data-handling setting in your methods description. A line is enough, for example: *"Anthropic API, Claude
> Sonnet, commercial terms, no training on customer content."*

Not sure what details to include? Please use the provided methods description template to organize your analysis, then
export your report as a PDF or Markdown file for submission.

When saving your report, please include your username (or team name) in the filename. For example, if your HF username
is `jane-doe`, you might name your report file:

* `jane-doe_track1_report.pdf` (`.md` also accepted)

### 3. Prepare other supporting materials.

**GitHub Repository**

Your repository may remain private while the Hackathon is running. However, it must be made public once the
Hackathon ends so the judging panel can review your code and methods.

What to include:
- Documented, reproducible code (all scripts and configuration files needed to reproduce your results)
- Submission files *(optional)*
- Methods description *(optional but recommended)*


### 4. After submission:

Your CSV submission is evaluated automatically using rank points and F-max against the clinically confirmed
answer on the leaderboard.

Your method(s) will be reviewed separately as part of the judging criteria (e.g. innovation and scalability).
"""


def _score_csv_bytes(csv_bytes: bytes) -> tuple:
    """Write bytes to a temp file, run the scorer, return (ScoreResult, proband_id)."""
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="wb") as tmp:
        tmp.write(csv_bytes)
        tmp_path = tmp.name
    try:
        submissions = load_submission(tmp_path)
        if not submissions:
            raise ValueError("No valid rows found in the CSV.")
        proband_id = next(iter(submissions))
        true_variants = _GT.get(proband_id)
        if true_variants is None:
            raise ValueError(
                f"Unknown proband_id '{proband_id}'. "
                "Only PROBAND01 is accepted in this challenge."
            )
        result = score_proband(proband_id, submissions[proband_id], true_variants)
        return result, proband_id
    finally:
        os.unlink(tmp_path)


def _handle_submit(display_name_input: str, github_url: str, report_file, csv_file, request: gr.Request, oauth_profile: gr.OAuthProfile | None = None) -> tuple:
    """Gradio callback - returns (feedback_md, quota_md, report_file, csv_file)."""
    hf_username = get_hf_username(request, oauth_profile)
    if not hf_username:
        return "⚠️ Please sign in with your Hugging Face account to submit.", "", gr.update(), gr.update()

    display_name = (display_name_input or "").strip() or hf_username_to_display_slug(hf_username)

    github_url = (github_url or "").strip()
    if not github_url.startswith("https://github.com/"):
        return "⚠️ GitHub URL must start with `https://github.com/`.", _quota_status(request), gr.update(), gr.update()

    if report_file is None:
        return "⚠️ Please upload your report (PDF or Markdown).", _quota_status(request), gr.update(), gr.update()
    report_path = report_file if isinstance(report_file, str) else report_file.name
    if Path(report_path).suffix.lower() not in {".pdf", ".md"}:
        return "⚠️ Report must be a PDF (.pdf) or Markdown (.md) file.", _quota_status(request), gr.update(), gr.update()
    report_filename = Path(report_path).name

    if csv_file is None:
        return "⚠️ Please upload a CSV file.", _quota_status(request), gr.update(), gr.update()

    csv_path = csv_file if isinstance(csv_file, str) else csv_file.name
    csv_filename = Path(csv_path).name
    if Path(csv_path).suffix.lower() != ".csv":
        return "⚠️ File must be a CSV (.csv).", _quota_status(request), gr.update(), gr.update()

    count = submissions_by_user(hf_username)
    if count >= MAX_TRACK1_SUBMISSIONS:
        return (
            f"⚠️ You have already used all {MAX_TRACK1_SUBMISSIONS} submissions. "
            "Only your best-scoring submission counts toward final ranking.",
            _quota_status(request),
            gr.update(),
            gr.update(),
        )
    model_n = count + 1

    try:
        if isinstance(csv_file, str):
            csv_bytes = Path(csv_file).read_bytes()
        else:
            csv_bytes = csv_file.read() if hasattr(csv_file, "read") else Path(csv_file.name).read_bytes()
    except Exception as e:
        return f"⚠️ Could not read uploaded file: {e}", _quota_status(request), gr.update(), gr.update()

    try:
        result, proband_id = _score_csv_bytes(csv_bytes)
    except Exception as e:
        tb = traceback.format_exc()
        return (
            f"❌ **Scoring error:** {e}\n\n"
            f"<details><summary>Technical details</summary>\n\n```\n{tb}\n```\n</details>",
            _quota_status(request),
            gr.update(),
            gr.update(),
        )

    entry = {
        "hf_username": hf_username,
        "display_name": display_name,
        "filename": f"model{model_n}_{csv_filename}",
        "github_url": github_url,
        "report_filename": report_filename,
        "proband_id": proband_id,
        "rank_points": result.rank_points,
        "f_max": result.f_max,
        "full_match_rank": result.full_match_rank,
        "partial_match_rank": result.partial_match_rank,
        "submitted_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }
    append_submission(entry, report_path)

    match_desc = (
        f"✅ **Full match** at rank {result.full_match_rank}"
        if result.full_match_rank is not None
        else (
            f"⚠️ **Partial match** (one of two compound-het variants) at rank {result.partial_match_rank}"
            if result.partial_match_rank is not None
            else "❌ **No match** - true variant(s) not found in submission."
        )
    )

    feedback = f"""
## Submission received ✓

**{display_name}** (`{hf_username}`) &nbsp;|&nbsp; **Submission:** {model_n} &nbsp;|&nbsp; **Proband:** {proband_id}

---

### Your scores

| Metric | Value |
|---|---|
| Rank points | **{result.rank_points:.1f}** / 100 |
| F-max | **{result.f_max:.3f}** |
| F-max EPCR threshold | {result.f_max_threshold if result.f_max_threshold is not None else "-"} |

{match_desc}
"""
    return feedback.strip(), _quota_status(request), None, None


def _quota_status(request: gr.Request, oauth_profile: gr.OAuthProfile | None = None) -> str:
    hf_username = get_hf_username(request, oauth_profile)
    if not hf_username:
        return ""
    count = submissions_by_user(hf_username)
    remaining = MAX_TRACK1_SUBMISSIONS - count
    return (
        f'<div class="info-card quota-card">'
        f'<strong>{count} / {MAX_TRACK1_SUBMISSIONS}</strong> submissions used &nbsp;·&nbsp; '
        f'<strong>{remaining}</strong> remaining'
        f'</div>'
    )


def render() -> None:
    with gr.Tab("Submit - Track 1") as tab:
        gr.Markdown(INTRO_MD)
        quota_md = gr.HTML()
        with gr.Accordion("📋 Submission Format & Instructions", open=True, elem_classes=["faq-accordion"]):
            gr.Markdown("**Templates:**")
            gr.Markdown("<small>*Last updated 28 Aug 2026*</small>")
            with gr.Row():
                gr.DownloadButton(
                    label="📄 Submission template (CSV)",
                    value="static/templates/track1_submission_template.csv",
                    size="sm",
                    elem_classes=["template-dl-btn"],
                )
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
                    info="This will be displayed on the public leaderboard. Leave blank to use your "
                         "HF username if you are participating individually.",
                )
                github_box = gr.Textbox(
                                    label="GitHub repo URL *",
                                    placeholder="https://github.com/your-org/your-repo",
                                )
            with gr.Column():
                csv_file = gr.File(label="Predictions file (CSV) *", file_types=[".csv"])
                report_file = gr.File(
                    label="Report file (PDF or Markdown) *",
                    file_types=[".pdf", ".md"],
                )
        submit_btn = gr.Button("Submit & Score", variant="primary")
        result_md = gr.Markdown(label="Result")
        submit_btn.click(
            fn=_handle_submit,
            inputs=[team_name_box, github_box, report_file, csv_file],
            outputs=[result_md, quota_md, report_file, csv_file],
        )
        tab.select(fn=_quota_status, inputs=[], outputs=quota_md)
    return quota_md
