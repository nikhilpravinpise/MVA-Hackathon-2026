"""Tests for tools/t2_mechanism.py - Track 2 lane L1 mechanism builder.

Network-free: every fixture exercised here was recorded under
tests/fixtures/track2/mechanism/ by a live run of the tool; tests replay
them. Pure functions (NMD positional rule, UniProt feature mapping, PDB
parsing, contact analysis) are tested on synthetic inputs.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from tools import t2_mechanism as tm  # noqa: E402

FIX = REPO / "tests" / "fixtures" / "track2" / "mechanism"
MECH_JSON = REPO / "docs" / "track2" / "evidence" / "mechanism.json"


def _load(name):
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def _replay_doc():
    """Assemble mechanism.json structure purely from recorded fixtures."""
    fetcher = tm.Fetcher(FIX, live=False)
    return tm.assemble(tm.fetch_all(fetcher), fetcher)


@pytest.fixture(scope="module")
def doc():
    return _replay_doc()


# ---------------------------------------------------------------------------
# transcript model / exon mapping
# ---------------------------------------------------------------------------

def _exons(spans):
    return [{"id": f"E{i}", "start": s, "end": e, "len": e - s + 1}
            for i, (s, e) in enumerate(spans, 1)]


def test_exon_order_plus_strand():
    lookup = _load("ensembl_lookup_ENST00000287598.json")
    exons = tm.exons_in_transcription_order(lookup)
    assert len(exons) == 23
    assert exons[0]["id"] == "ENSE00001929183"
    assert exons[-1]["id"] == "ENSE00001948417"
    # genomic order = transcription order on + strand
    assert [e["start"] for e in exons] == sorted(
        e["start"] for e in exons)


def test_locate_exon_real_variants():
    lookup = _load("ensembl_lookup_ENST00000287598.json")
    exons = tm.exons_in_transcription_order(lookup)
    assert tm.locate_exon(exons, 40209701) == 17     # p.Leu737Ter
    assert tm.locate_exon(exons, 40220612) == 23     # p.Asn1002Lys
    assert tm.locate_exon(exons, 1) is None          # outside gene
    assert tm.locate_exon(exons, 40209634) is None   # intron just 5' of exon 17


def test_spliced_offset_and_junction():
    lookup = _load("ensembl_lookup_ENST00000287598.json")
    exons = tm.exons_in_transcription_order(lookup)
    # VEP reports cDNA position 2362 for chr15:40209701 - cross-check ours.
    assert tm.spliced_offset(exons, 40209701, 1) == 2362
    assert tm.spliced_offset(exons, 40220612, 1) == (
        sum(e["len"] for e in exons[:22]) + (40220612 - 40220564) + 1)
    assert tm.last_junction_offset(exons) == 3109
    assert tm.spliced_offset(exons, 40209776, 1) is None  # intronic


# ---------------------------------------------------------------------------
# NMD positional rule (synthetic layouts incl. edge cases)
# ---------------------------------------------------------------------------

def test_nmd_far_upstream_triggers():
    # 3-exon transcript; variant early in exon 1 -> far from last junction
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    r = tm.nmd_analysis(exons, 120, 1)
    assert r["predicted_nmd"] is True


def test_nmd_far_upstream_math():
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    # junction = len(exon1)+len(exon2) = 200; gpos 120 -> offset 21 -> dist 179
    r = tm.nmd_analysis(exons, 120, 1)
    assert r["last_junction_offset"] == 200
    assert r["ptc_spliced_offset"] == 21
    assert r["ptc_to_last_junction_nt"] == 179
    assert r["predicted_nmd"] is True


def test_nmd_last_exon_escapes():
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    r = tm.nmd_analysis(exons, 550, 1)          # inside last exon
    assert r["ptc_to_last_junction_nt"] == -51
    assert r["predicted_nmd"] is False
    assert "downstream" in r["note"]


def test_nmd_boundary_at_rule():
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    # want PTC exactly 51 nt upstream of junction: offset = 200-51 = 149
    # -> gpos 48 of exon 2 (offset 101..200): spliced 149 = gpos 348
    r = tm.nmd_analysis(exons, 348, 1)
    assert r["ptc_to_last_junction_nt"] == 51
    assert r["predicted_nmd"] is True
    r2 = tm.nmd_analysis(exons, 349, 1)          # exactly 50 -> not > 50
    assert r2["ptc_to_last_junction_nt"] == 50
    assert r2["predicted_nmd"] is False


def test_nmd_codon_first_nt_shift():
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    # variant is 2nd nt of its codon (cds_pos %3 == 2); PTC starts 1 nt 5'
    r = tm.nmd_analysis(exons, 348, 1, cds_pos=200)
    # codon_off = (200-1)%3 = 1 -> measured from gpos 347
    assert r["ptc_spliced_offset"] == 148
    assert r["ptc_to_last_junction_nt"] == 52


def test_nmd_single_exon_not_applicable():
    exons = _exons([(100, 999)])
    r = tm.nmd_analysis(exons, 500, 1)
    assert r["last_junction_offset"] is None
    assert r["predicted_nmd"] is False
    assert "single-exon" in r["note"]


def test_nmd_minus_strand():
    # transcription-order exons for a - strand gene (5'->3' on mRNA)
    exons = _exons([(500, 599), (300, 399), (100, 199)])
    r = tm.nmd_analysis(exons, 550, -1)
    # spliced offset of gpos 550 in exon1 = 599-550+1 = 50
    # junction = len(exon1)+len(exon2) = 200 -> dist = 150
    assert r["ptc_spliced_offset"] == 50
    assert r["ptc_to_last_junction_nt"] == 150
    assert r["predicted_nmd"] is True


def test_nmd_outside_exon():
    exons = _exons([(100, 199), (300, 399), (500, 599)])
    r = tm.nmd_analysis(exons, 250, 1)           # intronic
    assert r["ptc_spliced_offset"] is None
    assert r["predicted_nmd"] is False


def test_nmd_real_allele1(doc):
    a1 = doc["alleles"][0]
    assert a1["nmd"]["ptc_to_last_junction_nt"] == 748
    assert a1["nmd"]["predicted_nmd"] is True
    assert a1["exon"]["index"] == 17
    assert a1["protein_loss"]["fraction_lost_pct"] == 29.9
    assert a1["interpretation"].startswith("null")


# ---------------------------------------------------------------------------
# UniProt feature mapping
# ---------------------------------------------------------------------------

def test_feature_mapping():
    feats = _load("uniprot_O60566.json")["features"]
    at_1002 = {(f["type"], f["start"], f["end"])
               for f in tm.features_covering(feats, 1002)}
    assert ("Domain", 766, 1050) in at_1002
    at_250 = [f for f in tm.features_covering(feats, 250)
              if f["type"] == "Modified residue"]
    assert at_250 and "acetyllysine" in at_250[0]["description"]
    # residue 737: only the Chain feature - no annotated domain
    at_737 = [f for f in tm.features_covering(feats, 737)
              if f["type"] != "Chain"]
    assert at_737 == []


# ---------------------------------------------------------------------------
# PDB parsing / structural neighbourhood (synthetic + real fixture)
# ---------------------------------------------------------------------------

def _atom(serial, name, resn, resi, x, y, z, plddt=90.0):
    return (f"ATOM  {serial:>5d} {name:^4s} {resn:>3s} A{resi:>4d}    "
            f"{x:8.3f}{y:8.3f}{z:8.3f}  1.00{plddt:6.2f}           C\n")


def test_parse_pdb_atoms():
    pdb = (_atom(1, "CA", "ALA", 1, 0, 0, 0, 91.5) +
           _atom(2, "CB", "ALA", 1, 1, 0, 0, 91.5) +
           _atom(3, "CA", "GLY", 2, 5, 0, 0, 50.0) +
           "END\n")
    atoms = tm.parse_pdb_atoms(pdb)
    assert len(atoms) == 3
    assert atoms[0]["plddt"] == 91.5
    byres = tm.group_atoms_by_residue(atoms)
    assert set(byres) == {1, 2}


def test_contact_residues_radius():
    pdb = (_atom(1, "CA", "ALA", 1, 0, 0, 0) +
           _atom(2, "CA", "GLY", 2, 5, 0, 0) +      # 5 A away
           _atom(3, "CA", "SER", 3, 20, 0, 0) +    # 20 A away
           _atom(4, "CA", "VAL", 4, 0, 7.9, 0))
    atoms = tm.parse_pdb_atoms(pdb)
    byres = tm.group_atoms_by_residue(atoms)
    assert tm.contact_residues(byres, 1, 8.0) == {2, 4}
    assert tm.contact_residues(byres, 3, 8.0) == set()
    assert tm.contact_residues(byres, 99, 8.0) == set()


def test_contact_number_percentile():
    pdb = (_atom(1, "CA", "ALA", 10, 0, 0, 0) +
           _atom(2, "CA", "GLY", 11, 5, 0, 0) +
           _atom(3, "CA", "SER", 12, 0, 5, 0) +
           _atom(4, "CA", "VAL", 13, 50, 0, 0))    # isolated
    atoms = tm.parse_pdb_atoms(pdb)
    byres = tm.group_atoms_by_residue(atoms)
    st = tm.contact_number_percentile(byres, 10, (10, 13), 8.0)
    assert st["contact_number"] == 2
    lone = tm.contact_number_percentile(byres, 13, (10, 13), 8.0)
    assert lone["contact_number"] == 0
    assert st["percentile_in_domain"] > lone["percentile_in_domain"]


def test_real_structure_res1002(doc):
    st = doc["alleles"][1]["structure"]
    assert st["plddt"] == pytest.approx(91.06, abs=0.01)
    assert 1002 not in st["residues_within_8a_allatom"]
    assert 1001 in st["residues_within_8a_allatom"]
    assert 1003 in st["residues_within_8a_allatom"]
    assert st["n_residues_within_8a_allatom"] == 27
    assert 0 <= st["burial"]["percentile_in_domain"] <= 100


# ---------------------------------------------------------------------------
# score / frequency / ClinVar extraction from fixtures
# ---------------------------------------------------------------------------

def test_scores_and_popfreqs(doc):
    a2 = doc["alleles"][1]
    assert a2["scores"]["alphamissense"] == pytest.approx(0.9229)
    assert a2["scores"]["alphamissense_class"] == "likely_pathogenic"
    assert a2["scores"]["revel"] == pytest.approx(0.472)
    assert a2["scores"]["sift_prediction"] == "deleterious"
    assert a2["gnomad"]["genome"]["ac"] == 0
    assert a2["gnomad"]["exome"]["ac"] == 1

    a1 = doc["alleles"][0]
    assert a1["gnomad"]["exome"]["ac"] == 115
    assert a1["clinvar"]["records"][0]["classification"] == \
        "Pathogenic/Likely pathogenic"
    assert any("Mosaic variegated aneuploidy" in t
               for t in a1["clinvar"]["records"][0]["traits"])
    # the c.3006T>G allele itself has no record; the same-AA c.3006T>A is VUS
    titles = [r["title"] for r in doc["alleles"][1]["clinvar"]["records"]]
    assert any("c.3006T>A" in t for t in titles)


# ---------------------------------------------------------------------------
# schema + citation discipline
# ---------------------------------------------------------------------------

CITE_RE = re.compile(r"^(PMID|DOI):")


def test_schema_keys(doc):
    for k in ("schema", "alleles", "pathway", "claims", "citations",
              "uncertainties", "therapeutic_implications",
              "contraindications"):
        assert k in doc
    assert doc["schema"] == "t2.mechanism/1"
    assert len(doc["alleles"]) == 2


def test_every_claim_cited(doc):
    assert len(doc["claims"]) >= 15
    for cl in doc["claims"]:
        assert cl["cites"], f"claim {cl['id']} has no citations"
        for cite in cl["cites"]:
            assert CITE_RE.match(cite), cite
            assert cite in doc["citations"], f"{cite} not resolved"


def test_all_sections_cited_and_resolved(doc):
    for sec in ("pathway", "uncertainties", "therapeutic_implications",
                "contraindications"):
        for blk in doc[sec]:
            assert blk["cites"], blk
            for cite in blk["cites"]:
                assert CITE_RE.match(cite)
                assert cite in doc["citations"]


def test_citation_metadata(doc):
    for handle, meta in doc["citations"].items():
        assert meta["title"], handle
        assert meta["journal"], handle
        if handle.startswith("PMID:"):
            assert 1900 <= int(meta["year"]) <= 2030, handle


def test_citation_gate_rejects_unresolved():
    fetcher = tm.Fetcher(FIX, live=False)
    with pytest.raises(RuntimeError):
        tm.resolve_citations(fetcher, ["999999999999"], [])


def test_replay_matches_written_json(doc):
    on_disk = json.loads(MECH_JSON.read_text(encoding="utf-8"))
    assert doc == on_disk


def test_claims_mention_phase_and_uncertainty(doc):
    assert any("Phase is UNKNOWN" in u["text"]
               for u in doc["uncertainties"])
    assert any("fibroblast" in u["text"] for u in doc["uncertainties"])
    # contraindication honesty: GH nuance recorded
    gh = [c for c in doc["contraindications"] if "growth hormone" in
          c["agent"]]
    assert gh and "Counter-evidence" in gh[0]["text"]
