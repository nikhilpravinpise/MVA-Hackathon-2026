"""Rules tab."""

from __future__ import annotations

import gradio as gr

RULES_MD = """
## Official Rules

To participate in this Hackathon, you must review and accept the following terms. Please read carefully and proceed
only if you agree to comply with the conditions below.

---

### Terms of Service & Eligibility
- You must abide by the [Hugging Face Terms of Service](https://huggingface.co/terms-of-service) and by these Hackathon
  Rules.
- You must be 18 years of age or older to participate.
- Each member of your Hackathon team must individually register as a participant and agree to these Hackathon Rules.

---

### Data Privacy & Recontact Restrictions
- You agree that you will not attempt to recontact the data subject, data subject family members, or any points of
  contact at the MVA Society.
- Your use of the data will comply with all applicable laws, rules, regulations, and professional standards.
- If any unauthorized disclosure of the data occurs or is suspected, you agree to contact Sage Bionetworks' Privacy and
  Compliance Office via Sage's Help Center.
- You will not release or otherwise grant data access to anyone, and you will establish appropriate safeguards to
  prevent unauthorized data use.

---

### Hackathon Flow:

1. <u>Registration:</u>  Participants must register with Hugging Face and request access to the data, including a valid
  email address and attestation to accepting these Hackathon Rules.

2. <u>Hackathon Tasks:</u> The Hackathon consists of two tasks:
   - Track 1 - Variant Identification: identify the disease-causing variant(s) using genetic variant information and
     phenotypic presentations.
   - Track 2 - Drug Repurposing: leveraging the genetic information and variant prediction from Task 1, identify
     existing market-approved medications whose mechanism of action may target the disease-causing pathway(s).

3. <u>Team Formation:</u> Teams are not required. Participants may form teams based on skills and interests.

4. <u>Data and Resource Provision:</u>
    - File types: genomic data in VCF format; raw sequencing data optionally in BAM/CRAM. Phenotypic data as
      standardized HPO terms.
    - Data size: ~85 GB (single-subject dataset).
    - Access: participants request access via Hugging Face's gated-dataset mechanism. No data may be reshared through
      any channel.
    - Compute: participants are responsible for their own compute environment and any associated costs.


5. <u>Development and Prototyping:</u>
    * Teams work intensively to develop a prototype or solution that addresses the Hackathon.
    * This involves brainstorming, coding, data analysis, and design.

6. <u>Data Deletion:</u>
    - Data retention after the Hackathon is not permitted for any purpose.
    - All data must be deleted within 30 days of Hackathon close from all environments (local machines, cloud instances,
      notebooks, private repos, and any intermediate or derived datasets).
    - <mark>All participants must email RarediseaserealkidMVAhackathon2026@synapse.org to confirm data has been deleted.
      **If you do not contact us, we may contact you directly in 30 days**</mark>

7. <u>Presentations & Judging:</u>
    - Each team's submission includes a written report, a GitHub repository, and a 3-minute recorded pitch video.
    - A panel of expert judges - researchers, clinicians, and patient advocates - will review all Track 2 submissions.
    - Judging takes place over approximately 2-3 months following submission close.
    - Presentations are pre-recorded; there is no live Q&A round.

8. <u>Evaluation and Outcome:</u>
    - Track 1 - Variant Prediction (automated): scored automatically against the NHS-validated causal variant(s) using
      rank points and F-max.
    - Track 2 - Drug Repurposing (panel-judged):
        * Scientific Rigor (35%)
        * Potential Impact (25%)
        * Innovation (25%)
        * Scalability (15%)

9. <u>Prizes:</u>
    The total prize pool is $50,000, sponsored by the AWS Imagine Grant program and Anthropic:
      * 🥇 1st Place: $12,000 cash + $12,000 Claude credits
      * 🥈 2nd Place: $7,000 cash + $7,000 Claude credits
      * 🥉 3rd Place: $4,000 cash + $4,000 Claude credits
      * 🌟 Innovation/Community Award: $2,000 cash + $2,000 Claude credits
      
      The Innovation/Community Award will be awarded at the judges' discretion to a submission demonstrating
      exceptional creativity, community impact, or patient-centered design, independent of overall placement

10. <u>Research Progress & Post-Hackathon Data Handling:</u>
    - Participants may publish and present on Hackathon results, subject to the embargo policy below.
    - All data must be deleted from participants' systems within 30 days of Hackathon close.
    - Anonymized results remain available to the research community via Synapse and/or Hugging Face after the Hackathon
      ends.
    - Submissions are released under a CC-BY license.

11. <u>Embargo Policy:</u>
    - The embargo period begins at Hackathon close and ends upon public posting of the hackathon summary report or
      preprint by the organizing team.
    - During the embargo period, participants may not submit manuscripts for peer-reviewed publication that use the
      hackathon dataset.
    - Participants are free to publicly share their code, models, and derived outputs at any time.
    - Participants may present preliminary findings in conference abstracts or posters with prior written approval from
      the organizers.

---

### Submission Reuse:

By registering, participants acknowledge that submissions may be rerun by the Hackathon organizers. Submissions are
subject to a CC-BY license, and your name will be shared as part of the open-access attribution.

---

### Recontact:

By providing your email address and participating, you consent to being recontacted by the Hackathon organizers for
purposes related to the Hackathon.

---

### Post-Hackathon Information Sharing:

All submitted results will be accessible to the broader research community to foster collaboration and innovacation.
Leading submissions may be prominently featured on the Hugging Face, Sage Bionetworks, or various Synapse-based websites,
ensuring visibility and recognition for impactful contributions. Additionally, follow-up activities such as blog posts,
video recaps, and social media highlights will showcase key submissions and behind-the-scenes moments. This open-access
approach ensures that the knowledge generated benefits the broader research community while inspiring future advancements
in rare disease research.

---

## Citation and Acknowledgement:

Any publication, preprint, conference abstract, or public communication arising from participation in this Hackathon
must include the following acknowledgement:

> _"This work was made possible through the Hackathon, organized by Sage Bionetworks in partnership with the MVA_
> _Society, Hugging Face, and BEACON (The Benchmarking, Evaluation, and Assessment Consortium for Science), with prize_
> _sponsorship from AWS and Anthropic. We are deeply grateful to the child and their family who generously contributed_
> _their data and their story to advance research into this rare disease. We acknowledge their trust in making this_
> _Hackathon possible."_

In addition, participants must observe the following requirements:

* **Data subject privacy** - Any publication referencing the underlying individual-level data must not include any information
  that could re-identify the data subject or their family, beyond what is already publicly available through the
  family's own blog posts and public communications.
* **Dataset citation** - The Hackathon dataset must be cited using the reference provided on the Hackathon Synapse page
  at the time of publication.
"""


def render() -> None:
    with gr.Tab("Official Rules"):
        gr.Markdown(RULES_MD)
        gr.HTML('<div class="back-to-top-row"><a class="back-to-top" href="javascript:void(0)" onclick="document.getElementById(\'page-top\').scrollIntoView({behavior:\'smooth\'})">↑ Back to top</a></div>')

