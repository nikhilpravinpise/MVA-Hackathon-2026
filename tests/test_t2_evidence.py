"""Contract pins for the Track 2 evidence layer (docs/track2/evidence/).

The report generator reads these files and nothing else, so their shape,
internal citation consistency and approval claims are gate-critical:
- every dossier / rejected entry / mechanism claim cites at least one id,
  and every cited id is present in that file's own citations map;
- every shortlisted or adjunct drug records ChEMBL max_phase 4 plus an
  openFDA label set_id (approval checked by code, never from memory);
- the committed citation cache covers every id, so an offline gate run
  needs zero network and fails on any id nobody resolved;
- no em dash characters (repo hygiene rule).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EV = REPO / "docs" / "track2" / "evidence"
CITE = re.compile(r"(PMID:\d+|DOI:10\.\S+|PMCID:PMC\d+)")

DOSSIERS = sorted((EV / "dossiers").glob("*.json"))


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


def _cites_in(obj) -> set[str]:
    return set(CITE.findall(json.dumps(obj)))


def test_dossiers_exist():
    assert len(DOSSIERS) >= 5


@pytest.mark.parametrize("path", DOSSIERS, ids=lambda p: p.stem)
def test_dossier_schema_and_internal_citations(path):
    d = _load(path)
    assert d["schema"] == "t2.dossier/1"
    for key in ("drug", "axis", "approval", "claims", "pediatric",
                "testability", "verdict", "verdict_reason", "citations"):
        assert key in d, key
    assert d["verdict"] in {"shortlist", "adjunct", "rejected"}
    assert set(d["testability"]) == {"celegans", "fibroblasts", "scrnaseq", "supplements"}
    assert d["claims"], "dossier without claims"
    for c in d["claims"]:
        assert c["cites"], f"uncited claim {c['id']}"
        missing = set(c["cites"]) - set(d["citations"])
        assert not missing, f"{c['id']} cites ids absent from citations map: {missing}"
    for cid, meta in d["citations"].items():
        assert meta.get("title") and meta.get("year"), cid


@pytest.mark.parametrize("path", DOSSIERS, ids=lambda p: p.stem)
def test_candidate_approval_checked_by_code(path):
    d = _load(path)
    if d["verdict"] == "rejected":
        return
    ap = d["approval"]
    assert ap.get("chembl_max_phase") == 4, ap
    assert ap.get("openfda_label_set_id"), "no openFDA label evidence"


def test_rejected_entries_are_reasoned_and_cited():
    r = _load(EV / "rejected.json")
    assert len(r["entries"]) >= 8
    for e in r["entries"]:
        assert e["drug"] and e["reason"]
        assert _cites_in(e), f"rejected entry without citation: {e['drug']}"


def test_mechanism_claims_cited_and_resolved():
    m = _load(EV / "mechanism.json")
    assert m["schema"] == "t2.mechanism/1"
    assert len(m["alleles"]) == 2
    for c in m["claims"]:
        assert c["cites"], c["id"]
        assert set(c["cites"]) <= set(m["citations"]), c["id"]
    # the phase caveat must survive any regeneration
    assert any("phase" in json.dumps(u).lower() for u in m["uncertainties"])


def test_testability_covers_all_programs():
    t = _load(EV / "testability.json")
    assert set(t["programs"]) == {"worm_repurposing_screen", "patient_fibroblasts",
                                  "multi_patient_scrnaseq", "supplements_cell_health"}


def test_offline_citation_gate_passes():
    """Every id in the evidence layer is in the committed cache and
    resolves clean (no unresolved / retracted / title-year mismatch)."""
    out = subprocess.run(
        [sys.executable, str(REPO / "tools" / "verify_citations.py"), "--offline",
         "--quiet", str(EV)],
        cwd=REPO, capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_no_em_dash_in_evidence():
    for p in EV.rglob("*.json"):
        assert "—" not in p.read_text(encoding="utf-8"), p
