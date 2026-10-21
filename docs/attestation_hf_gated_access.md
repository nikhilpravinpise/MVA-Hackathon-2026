# HF gated-access attestation - verbatim archive

Dataset: `SageBio/mva-hackathon-2026-data` (gated: `auto`)
Access granted to HF user `@T0X1N` on 2026-10-01 (docs/status.md row
"HF account + gated dataset access").

This file archives the exact text presented by the gating form at
acceptance time, retrieved verbatim from the public Hugging Face API
(`GET /api/datasets/SageBio/mva-hackathon-2026-data`, `cardData`
fields) on 2026-10-04. Verbatim text is quoted below; nothing is
paraphrased. The gating banner and `extra_gated_prompt` are included
for completeness.

## Gating banner (verbatim)

> You need to agree to share your contact information to access this
> dataset
>
> This repository is publicly accessible, but you have to accept the
> conditions to access its files and content.

## extra_gated_prompt (verbatim)

> You must understand and agree to follow the Hackathon Rules.

(The referenced Hackathon Rules document is vendored at
`hackathon-app/tabs/rules.py` / `hackathon-app/tabs/about.py`.)

## Required information fields

| # | Field | Type | Required |
|---|-------|------|----------|
| 0 | Institution | text | yes |
| 1 | City and Country | text | yes |
| 2 | Specific date | date_picker | yes |
| 3 | I want to use this dataset for | select | yes - single option: "Rare Disease, Real Kid: MVA Hackathon 2026" |

## Checkbox attestations (verbatim, in form order)

4. "I am 18 years old or older"

5. "I understand and agree that I must delete all data after I have
   completed the Hackathon"

6. "I agree to email MVAHackathon2026@synapse.org to notify Sage
   Bionetworks when data has been deleted from personal compute
   environments"

7. "I agree that I will not attempt to recontact the data subject,
   data subject family members, or any points of contact at the MVA
   Society"

8. "I agree that my use of the Data will be in compliance with all
   applicable laws, rules, regulations, and professional standards and
   I agree to contact Sage Bionetworks Privacy and Compliance Office
   via Sage Help Center
   (https://sagebionetworks.jira.com/servicedesk/customer/portal/20) if
   any unauthorized disclosure of the data occurs"

9. "I will not release or otherwise grant data access to anyone and I
   will establish appropriate safeguards to prevent unauthorized data
   use. Each member of my Hackathon team will be registered as a
   participant and agree to the Hackathon terms"

10. "I acknowledge that by registering for this Hackathon, submissions
    may be rerun by the Hackathon organizers, including Sage
    Bionetworks, Hugging Face, and the MVA Society. Submissions will be
    subject to a CC-BY 4.0 license and my name will be shared as part
    of the open-access information for the license to be implemented"

11. "I understand that by providing my email address and participating
    in the Hackathon, I consent to being recontacted by the Hackathon
    Organizers for purposes related to the Hackathon, including
    follow-up communications, feedback requests, and potential future
    research opportunities"

12. "I understand that all submitted results will be accessible to the
    broader research community to foster collaboration and innovation.
    Leading submissions may be prominently featured on the Hugging
    Face, Sage Bionetworks, or various Synapse-based websites, ensuring
    visibility and recognition for impactful contributions"

13. "I agree to follow the official hackathon rules published on the
    Rare Disease, Real Kid: MVA Hackathon 2026 page."

14. "I agree to follow the acknowledgement and citation requirements
    if I publish on my work and to follow additional requirements
    specified in the official hackathon rules"

## Obligations extracted (operational)

| Attestation | Where honored |
|-------------|---------------|
| #5 delete all data after hackathon | `docs/deletion_runbook.md`, `data/RETENTION.md`, `results/RETENTION.md` (DELETE/KEEP doctrine) |
| #6 email deletion confirmation | `docs/deletion_runbook.md` - the rules now name `cnb@sagebase.org` (updated 2026-10-13); copy the attested mailbox `MVAHackathon2026@synapse.org`. The older `RarediseaserealkidMVAhackathon2026@synapse.org` address rejects unregistered senders per discussion #15 and is a legacy copy only. If anything bounces, post the attempt in Discussions as documented. |
| #7 no recontact | no patient/family/society contact made or planned; community artifact offered via the public Information Hub channel only |
| #8 compliance + unauthorized-disclosure reporting | privacy scrub (decisions.md M3 rows, commit 20c8b3f); Sage Help Center link recorded here |
| #9 no data release + safeguards | gated data stays on operator machine + Modal volume only; `.gitignore` containment (data/, results genotype-scale dumps); per-person access (single operator) |
| #10 submissions may be rerun + CC-BY 4.0 + name shared | submissions + repo artifacts are CC-BY 4.0-compatible; public repo flip post-deadline; display name `nikhilpise` is the shared name |
| #13/#14 follow official rules + citation requirements | rules.py compliance throughout; if any publication follows, cite per official rules |

## Notes

- IRB: WCG protocol #20252010 (dataset card / deep dive s.2).
- Gating type is `auto` (checkbox attestation + required fields), not
  manual review - approval is granted on submission of a complete form.
- The API exposes the form schema verbatim; the submitted field VALUES
  (institution, city/country, date) are personal and intentionally not
  archived here.
