# Deletion-confirmation email - staged draft

Send **after** the post-deadline deletions execute (runbook
`docs/deletion_runbook.md` sections 1-6), **to BOTH mailboxes** (the
attested mailbox per `docs/attestation_hf_gated_access.md` item 6, and
the rules-text mailbox which rejects unregistered senders per discussion
#15). If either bounces, post the attempt in the hackathon Space's
Discussions tab.

- To: `MVAHackathon2026@synapse.org`
- To: `RarediseaserealkidMVAhackathon2026@synapse.org`
- From: the Synapse-registered address used for the gated-data attestation
- Subject: MVA Hackathon 2026 - data deletion confirmation (team: nikhilpise, HF: @T0X1N)

---

Dear MVA Hackathon organizers,

This is the deletion confirmation required by the gated-dataset
attestation for the MVA Hackathon 2026 dataset.

Team: nikhilpise (Hugging Face account @T0X1N)
Dataset: SageBio/mva-hackathon-2026-data (gated; access granted
2026-10-01)

As of today I have deleted all copies of the dataset and all
patient-derived data in my possession, specifically:

- The gated files (patient WGS VCF + index, the clinical phenotype
  docx, and the 8 FASTQ files) from all local storage.
- Every derived artifact containing patient genotype-scale data:
  re-aligned and processed BAMs, read-level extraction files,
  full hypothesis-enumeration dumps, per-variant annotation outputs,
  and any intermediate representations containing patient genotypes.
- All cloud copies: the Modal volumes that hosted the data during
  analysis were deleted on 2026-10-04 (verified empty account: 0
  volumes, 0 secrets, 0 apps).
- Retained per the challenge rules: the ranked variant list (the
  submitted CSV), aggregate-level findings (coverage summaries, gene
  rankings, classification outputs), source code, reports, and the
  leaderboard entry - the classes the retention rules explicitly allow.

Deletion was executed per our published runbook
(docs/deletion_runbook.md in the GitHub repository accompanying our
submission); the retention manifests (data/RETENTION.md,
env/RETENTION.md, results/RETENTION.md) record the disposition of every
artifact class.

Happy to provide any further confirmation you need.

Nikhil Pise
