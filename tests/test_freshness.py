"""Freshness pins - pytest wrappers over tools/audit_freshness.py.

Each test runs one audit check and asserts zero FAIL rows (WARN rows -
git dirtiness, unverifiable-offline claims - are reported, not failed).
Artifact-dependent checks skip when the gitignored results/ tree is
absent (fresh clone); on the dev machine they run for real.

Falsification conditions (plan.md 2.2): each test names the drift it
catches.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import audit_freshness as af  # noqa: E402

PATIENT_ARTIFACTS = all((REPO / p).exists() for p in (
    "results/track1_patient_modal/track1_final_indelfix/funnel/"
    "result_head.json",
    "results/track1_patient_modal/track1_final_indelfix/funnel/"
    "funnel_counts.json",
    "results/track1_patient_modal/realign/region.sam",
    "results/exomiser_patient/WGS_EX2312012-PASS_ONLY.genes.tsv",
    "docs/figures/pileup_bub1b.svg",
))
needs_artifacts = pytest.mark.skipif(
    not PATIENT_ARTIFACTS, reason="patient results/ tree absent "
    "(gitignored; freshness-vs-artifacts is a local property)")


def _no_fail(fn):
    out = af.Out()
    fn(out)
    fails = [d for s, _, d in out.rows if s == "FAIL"]
    assert not fails, "; ".join(fails)


@pytest.mark.gate
@needs_artifacts
def test_csv_identity_and_oracle():
    """Drift caught: any of the three CSV copies diverging in bytes, CRLF
    creeping in, or a submissions/*.csv that doesn't oracle-verify.

    One of the three copies is the run-directory CSV under the gitignored
    results/ tree, so this is a local property like the other
    artifact-dependent checks."""
    _no_fail(af.check_csv_identity)


@pytest.mark.gate
def test_emitted_claims():
    """Drift caught: a doc quoting epcr 0.1324 (pre-fix) or another
    emitted-pair epcr without a historical marker."""
    if not PATIENT_ARTIFACTS:
        pytest.skip("needs result_head.json")
    _no_fail(af.check_emitted_claims)


@pytest.mark.gate
def test_section_refs():
    """Drift caught: report_map 'section N' pointing at a heading that no
    longer exists after a template renumber."""
    _no_fail(af.check_section_refs)


@pytest.mark.gate
def test_line_refs():
    """Drift caught: checklist citing vendored-app line anchors that no
    longer hold the token they claim."""
    _no_fail(af.check_line_refs)


def test_paths_exist():
    """Drift caught: a doc citing a results/docs/data path that has been
    deleted or moved - the classic stale-pointer bug."""
    _no_fail(af.check_paths_exist)


def test_banner_presence():
    """Drift caught: a regenerated report shipping the synthetic banner
    or dropping the mandated acknowledgement."""
    _no_fail(af.check_banner_presence)


def test_hygiene_scans():
    """Drift caught: em-dashes or TODO/FIXME strays in tracked markdown,
    ledger rows dated in the future. (git-dirty is WARN not FAIL.)"""
    _no_fail(af.check_hygiene)


def test_no_stale_markers():
    """Drift caught: unexplained 'pending/not yet/TBD' markers in live
    docs outside the allowlist of legitimately-open items."""
    _no_fail(af.check_markers)


def test_fixture_count():
    """Drift caught: '60 fixtures'/'19-fixture' claims outliving their
    fixture lists."""
    _no_fail(af.check_fixture_count)


@needs_artifacts
def test_artifact_numbers():
    """Drift caught: report funnel/ablation/Exomiser numbers diverging
    from the JSON artifacts they claim to summarize."""
    _no_fail(af.check_artifact_numbers)


@needs_artifacts
def test_figures_deterministic():
    """Drift caught: committed SVGs no longer matching what
    make_figures.py emits from the same artifacts (figure edited by hand,
    or artifact regenerated but figure stale)."""
    _no_fail(af.check_figures_deterministic)


@pytest.mark.gate
def test_truth_claims():
    """Drift caught: the false 'VCF carries no PGT/PID' wording returning,
    or the GenAI disclosure losing a provider / its opt-out assertion."""
    _no_fail(af.check_truth_claims)
