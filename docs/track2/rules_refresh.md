# Track 2 rules refresh - discussions + live Space diff

Compiled 2026-10-12 by lane L4. Sources: `tools/check_discussions.py`
(read-only public HF API), per-thread fetches from
`https://huggingface.co/api/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/discussions/<num>`,
and raw file fetches from
`https://huggingface.co/spaces/SageBio/rare-disease-real-kid-mva-hackathon-2026/raw/main/<file>`
diffed against the vendored copy in `hackathon-app/` (vendored 2026-09 era).

**Bottom line: no Track 2 rule changes since 2026-09-20.** The only drift is
the judging/announcement calendar (winners Dec 18, judging window through
Dec 17). All plan.md / track2_plan.md constraints still hold.

## 1. New threads since 2026-09-20 (3 found)

| # | Title | Author | Created | Status | T2-relevant? |
|---|-------|--------|---------|--------|--------------|
| 26 | Update on announcement date | gandreoletti (org) | 2026-09-28 | open, PINNED | Yes - calendar only |
| 27 | Track 1 - consolidate duplicate team entries | mametoure | 2026-10-03 | closed | No (T1 admin) |
| 25 | Aligned reads and FASTQ lane/library information | donvitocorleone | 2026-09-23 | open | Marginal - data logistics |

### #26 "Update on announcement date" (PINNED, organizer, 2026-09-28)

> "New date: winners will be announced on *December 18*. This is an extension
> to the judging timeline only and it doesn't change anything about the
> submission deadline or how to submit. We'd simply rather our judges have
> the time each submission deserves than rush a decision, especially on
> Track 2, where the panel is reviewing real scientific reasoning behind
> every proposed drug candidate." - gandreoletti, 2026-09-28T17:30Z

Implications:
- Submission deadline unchanged: **2026-10-24 23:59 UTC**. The Oct 20 / Oct 23
  submission schedule in track2_plan.md section 7 stands.
- "reviewing real scientific reasoning behind every proposed drug candidate"
  reinforces the Scientific Rigor weighting: mechanism-first candidates with
  verifiable evidence, not lists.

### #27 "Track 1 - consolidate duplicate team entries" (closed, 2026-10-03)

Track 1 housekeeping: organizers archived a team's earlier entry so only the
latest is judged. Confirms the standing "latest submission is the one
reviewed" convention - same convention as Track 2 (only the most recent of up
to 3 entries is reviewed). No action.

### #25 "Aligned reads and FASTQ lane/library information" (open, 2026-09-23; follow-up 2026-10-11)

> "BAM/CRAM: Not currently available under the controlled-access arrangement -
> only the raw FASTQs are provided... Reference genome is GRCh38... Sequencing
> platform / library prep: Illumina DNA PCR-Free Prep, sequenced on an Illumina
> NovaSeq." - gandreoletti, 2026-09-25T17:31Z

A second participant (thkuo) asked 2026-10-11 whether the 4 FASTQ pairs are
lanes/replicates of one sample; unanswered as of this fetch. Track-1 data
logistics only - no T2 implication beyond confirming no extra data products
are coming.

## 2. Standing rules from earlier threads (restated for the T2 record)

These predate the --since window but define Track 2 constraints; included so
the refresh is self-contained.

### #5 "Combination with an experimental drug" (organizer answer 2026-08-30)

> "Combination of drugs: Yes, that's fine. you're welcome to propose a
> combination of market-approved medications if your analysis supports it, as
> long as your rationale for each drug (and why the combination makes sense)
> is clearly explained. / Drugs currently in research (not yet
> market-approved): Track 2 is scoped to existing, market-approved
> medications being considered for a new use, rather than investigational or
> trial-stage compounds." - gandreoletti, 2026-08-30T18:30Z

Implication (unchanged): **market-approved only**; combinations allowed if
each drug and the combination rationale are argued. Supplements may appear as
adjuncts/considered-and-rejected, not as primary candidates. This is the rule
`verify_citations.py` + the ChEMBL/DrugCentral/openFDA approval checks in L2/L3
operationalize.

### #7 "Request to reset accidental early Track 2 submission" (organizer answer 2026-08-29)

> "we've decided to increase the Track 2 submission quota up to 3 attempts...
> Please note that only your most recent submission will be evaluated by the
> judges." - vpchung, 2026-08-29T01:16Z

Implication (unchanged): max 3 submissions, latest-only review. Matches
`MAX_TRACK2_SUBMISSIONS = 3` in live `config.py` (verified identical today).

### #13 "Track2" (organizer answer 2026-08-31)

> "the dataset citation requirement only applies if you later publish
> something using this data (a paper, preprint, conference abstract, etc.) -
> it's not something you need to include in your Track 2 report submission
> itself for now." - gandreoletti, 2026-08-31T23:13Z

Implication: no Synapse dataset citation needed inside the report itself.

### #2 + #21 third-party LLM conditions (updated guidance 2026-09-28, supersedes #21 interim answer)

> "consumer-tier accounts (e.g., Claude Free/Pro, ChatGPT Plus) are permitted
> for use with patient-specific or derived information, not just Business/API
> tiers - provided both of the following hold: 1. You opt out of model
> training through your account settings. 2. You do not provide feedback on
> outputs... please document the provider, product tier, and
> training-opt-out setting you used in your methods description."
> - gandreoletti, 2026-09-28T23:09Z

Implication: our GenAI disclosure line (Devin Pro + Claude Pro/Max, opt-outs,
no feedback) satisfies the current guidance. Track 1 report already discloses
this; the T2 form answer must repeat it.

### #14 "Request for additional patient information" (organizer answer 2026-08-31)

> "additional clinical data beyond the genomic data and HPO-coded phenotype
> terms isn't available... more granular clinical records (labs, treatment
> history) fall outside that [IRB scope]." - gandreoletti, 2026-08-31T23:12Z

Implication: the report cannot claim current-medication interaction checks or
lab-guided dosing; the pediatric-safety section must explicitly name this as
a limitation (we cannot know the child's current medications).

### #20 incidental findings + public repo (organizer interim answer 2026-09-25)

Escalated to Privacy/IRB; interim guidance: keep repo private during the
challenge, do not contact the family/clinical team directly. Our privacy
posture (only the 8 HPO terms + 2 published variants in outputs) is
consistent and more conservative. Still open at fetch time.

### #22 "UK gene bank access - cis/trans issue" (organizer answer 2026-09-15)

> "You're free to use whatever dataset or approach works best for your
> method... We don't require a particular biobank." - gandreoletti,
> 2026-09-15T15:49Z

Implication: public-data freedom confirmed (relevant to L5 DepMap/PRISM use).

### #24 "Phase / parental transmission" (organizer answer 2026-09-25) - important for T2 mechanism framing

> "we're not able to confirm or deny transmission/phase status for specific
> candidate variants during the challenge - even privately... confirming
> trans-phase is functionally equivalent to confirming your hypothesis is
> correct... We're not planning to disclose phase information before the
> challenge closes... Any information already in the public domain (published
> literature, the family's own public communications) is fair game."
> - gandreoletti, 2026-09-25T18:54Z

Implication (confirms plan): **phase stays unknown**. The mechanism section
must present in-trans as a stated assumption with its basis (MVA1 genotype
pattern: null + hypomorph; viability of the compound-het), never as observed
fact. It also confirms literature/public-domain reasoning is the intended
path - exactly what the T2 report does.

## 3. Live Space file diff (fetched + diffed 2026-10-12)

Diff method: `curl` of the 5 raw files, diff vs `hackathon-app/` with CRLF
normalization (vendored files carry CRLF; live are LF).

| File | Result |
|------|--------|
| `tabs/submit_track2.py` | IDENTICAL - no rule drift (3-submission cap, GitHub URL prefix, video hard gate, .pdf/.md only) |
| `tabs/about.py` | Timeline table only: judging window "October 24 - November 24" -> "October 24 - ~~November 24~~ **December 17**"; winners "November 25" -> "~~November 25~~ **December 18**". Consistent with #26. |
| `tabs/rules.py` | One word: "innovacation" -> "innovation" (typo fix). No rule drift. |
| `tabs/faq.py` | IDENTICAL |
| `config.py` | IDENTICAL (`MAX_TRACK2_SUBMISSIONS = 3`, `CHALLENGE_ACTIVE = True`) |

No drift in: approved-drug scope, combination policy, report format, video
requirement, team submission rules, judging criteria, or deadline.

## 4. Net implications for Track 2

1. Calendar: judging now runs to Dec 17, winners Dec 18. Deadline Oct 24
   23:59 UTC stands - v1 Oct 20 / final Oct 23 stays the plan.
2. Rules: unchanged. Market-approved-only + combination-with-rationale is the
   governing constraint; the approval-by-code pipeline stands.
3. Phase: stays unknown; organizers will not disclose it pre-close. The
   in-trans assumption framing in the mechanism section is the correct and
   required posture.
4. Disclosure: GenAI line (provider/tier/opt-out) is required and our wording
   is compliant with the 2026-09-28 confirmed guidance.
5. Data: no additional clinical data will arrive; name it as a limitation.

## 5. Next re-check

Re-run `tools/check_discussions.py --since 2026-10-12` and re-diff the five
files on **Oct 19** (before the v1 submission) and **Oct 23** (before final).
Pinned threads (#10, #18, #26) carry organizer announcements; #26 is the
current calendar authority.
