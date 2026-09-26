"""Leave-one-source-out ablations (plan.md 2.1.3 + Gate 2): each evidence
source is dropped in turn; the true pair must remain top-5 in every ablation.
A pipeline that only works with all knobs on is overfit to the case.
"""
from __future__ import annotations

import pytest

from src import synth
from src.pipeline import ABLATION_SOURCES, run_pipeline


@pytest.fixture(scope="module")
def spike(tmp_path_factory):
    return synth.spike_in_case(tmp_path_factory.mktemp("abl"))


def _pair_rank(res, truth):
    want = sorted((v["pos"], v["alt"]) for v in truth["pair"])
    for h in res["ranked"]:
        got = sorted((v["pos"], v["alt"]) for v in h["variants"])
        if h["model"] == "compound_het" and got == want:
            return h["rank"], h["score"], h["emitted"]
    return None, None, False


@pytest.mark.gate
@pytest.mark.parametrize("drop", sorted(ABLATION_SOURCES))
def test_ablation_source(spike, drop):
    """Falsification: the true pair drops below rank 5 when an evidence
    source is removed - the call leans on a single brittle input."""
    res = run_pipeline(
        spike["vcf"], spike["truth"]["hpo_terms"],
        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
        g2d_path=spike["gene2disease"], drops=frozenset({drop}))
    rank, score, emitted = _pair_rank(res, spike["truth"])
    assert rank is not None, f"pair vanished under --drop {drop}"
    assert rank <= 5, f"--drop {drop}: pair fell to rank {rank}"


@pytest.mark.gate
def test_gnomad_ablation_actually_changes_pool(spike):
    """Falsification: --drop gnomad leaves the candidate pool identical -
    the ablation flag is a no-op (rare-and-common variants must flood in)."""
    base = run_pipeline(spike["vcf"], spike["truth"]["hpo_terms"],
                        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
                        g2d_path=spike["gene2disease"])
    abl = run_pipeline(spike["vcf"], spike["truth"]["hpo_terms"],
                       obo_path=spike["obo"], hpoa_path=spike["hpoa"],
                       g2d_path=spike["gene2disease"],
                       drops=frozenset({"gnomad"}))
    assert abl["funnel"]["candidates"] > base["funnel"]["candidates"], \
        "drop gnomad admitted no new candidates - the flag is a no-op"


@pytest.mark.gate
def test_hpo_ablation_zeroes_pheno(spike):
    """Falsification: pheno scores nonzero after --drop hpo - ablation not
    applied to the phenotype layer."""
    res = run_pipeline(spike["vcf"], spike["truth"]["hpo_terms"],
                       obo_path=spike["obo"], hpoa_path=spike["hpoa"],
                       g2d_path=spike["gene2disease"],
                       drops=frozenset({"hpo"}))
    assert all(h["pheno_score"] == 0 for h in res["ranked"])
    # ...and the noise decoy must still lose on damage-terms only via
    # inheritance/damage weights it cannot exceed the true pair
    truth_genes = {"SPIKEA"}
    ttn_scores = [h["score"] for h in res["ranked"] if h["gene"] == "TTN"]
    spk = [h["score"] for h in res["ranked"]
           if h["gene"] in truth_genes and h["model"] == "compound_het"]
    assert spk and max(spk) >= max(ttn_scores or [0])
