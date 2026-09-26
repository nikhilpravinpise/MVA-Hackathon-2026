# Secondary-findings disclosure position

*(Plan.md Phase 4 deliverable - written position on the disclosure-ethics
question; community discussion #20 remains unanswered by organizers as of
2026-09-26.)*

## The question

The pipeline scans all 84 ACMG SF v3.3 genes. If it finds a reportable
pathogenic/likely-pathogenic variant unrelated to the MVA phenotype, should
it appear in the submission (`finding_type=secondary`) and in the report -
knowing the proband is a real, identifiable child?

## Our position

1. **Report medically actionable findings; disclose carefully.** The ACMG
   SF list exists precisely because these findings are actionable and the
   professional consensus is to report them when looked for. Suppressing a
   real finding to look tidy is not rigor. Each secondary row carries a
   `notes` rationale (gene, condition, ClinVar basis; the MOI rule is
   recorded in sf_findings.json's `moi` field) so a reviewer sees
   *why* it is listed without us making clinical claims.

2. **Describe, don't diagnose.** Rows and report text state the variant's
   evidence (ClinVar significance, consequence, MOI) - never a prediction
   about the individual. We are a computational pipeline, not a clinician;
   the report says so.

3. **No carrier-state noise.** AR-gene single heterozygotes are NOT emitted
   as secondary rows (carrier status is common and non-actionable here); AR
   genes report only homozygous/compound-het P/LP patterns per the SF
   reporting policy encoded in `src/sf_scan.py`.

4. **The family decides, not us.** Actual disclosure to a real family is a
   clinical-genetics question outside a hackathon's scope. Our written
   position ends at: document the finding honestly, flag its basis, and
   defer the disclosure decision to the appropriate channel. That is the
   thoughtful answer the judges (who include patient advocates) can evaluate
   - silence would not be.
