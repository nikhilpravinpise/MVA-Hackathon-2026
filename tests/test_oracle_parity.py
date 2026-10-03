"""Oracle parity: the vendored scorer imports, scores deterministically, and
its app-emulated path behaves per the verified contract.

Falsification: if evaluation.py fails to import, scores the template CSV
nondeterministically, or diverges from the documented rank/F-max semantics on
the canonical fixtures, the entire submission path is untrustworthy.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gate

from conftest import (HEADER, JUNK, REPO, V1, V2, prow, score_csv_text,
                      score_rows, vrow)


def test_oracle_imports_and_exposes_api(oracle_module):
    """Falsification: vendored scorer missing or API surface changed."""
    for name in ("load_submission", "score_proband", "ScoreResult",
                 "SubmissionRow", "RANK_POINT_TIERS"):
        assert hasattr(oracle_module, name), name
    assert oracle_module.RANK_POINT_TIERS == [(1, 100), (3, 50), (5, 25), (10, 10)]


def test_template_csv_scores_deterministically():
    """Falsification: template-style CSV does not score 100/1.000 twice
    identically - nondeterminism or wiring bug in the oracle path."""
    rows = [prow(V1, V2, "0.90"), vrow(JUNK[0], "0.30", ft="secondary")]
    r1 = score_rows(rows)
    r2 = score_rows(rows)
    assert (r1.rank_points, r1.f_max) == (r2.rank_points, r2.f_max)
    assert r1.rank_points == 100.0 and r1.f_max == 1.0
    assert r1.full_match_rank == 1 and r1.partial_match_rank is None


def test_score_result_fields_complete():
    """Falsification: ScoreResult missing any field the app reads."""
    r = score_rows([prow(V1, V2, "0.95")])
    for f in ("proband_id", "full_match_rank", "partial_match_rank",
              "rank_points", "f_max", "f_max_threshold",
              "n_predictions_at_f_max"):
        assert hasattr(r, f)
    assert r.proband_id == "PROBAND01"
    assert r.f_max_threshold == 0.95


def test_gt_wiring_guard():
    """Falsification (plan.md sec.6 'GT-wiring guard'): identical bytes must
    score differently under a different GT - otherwise fixtures are testing
    a hardcoded answer key, not scorer mechanics."""
    r_true = score_rows([prow(V1, V2)])
    assert r_true.rank_points == 100.0
    alt_gt = frozenset({V1, JUNK[0]})
    r_alt = score_rows([prow(V1, V2)], gt=alt_gt)
    assert r_alt.rank_points == 50.0 and r_alt.f_max == pytest.approx(0.5)


def test_scorer_copies_byte_identical():
    """Falsification: scorer/evaluation.py and hackathon-app/evaluation.py
    diverge - in-process tests exercise one copy while byte-subprocess
    tests exercise the other; a silent fork means the validated oracle is
    not the shipped oracle."""
    import hashlib
    a = (REPO / "scorer" / "evaluation.py").read_bytes()
    b = (REPO / "hackathon-app" / "evaluation.py").read_bytes()
    assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest()


@pytest.mark.gate
def test_parity_with_audit_battery_signature():
    """Falsification: the canonical perfect-submission shape does not give
    the verified 100/1.000 signature through the full app-emulated path."""
    text = HEADER + "\n" + prow(V1, V2, "0.95") + "\n"
    for _ in range(3):
        r = score_csv_text(text)
        assert r.rank_points == 100.0 and r.f_max == 1.0
