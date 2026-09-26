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


@pytest.mark.gate
def test_phasing_drop_restores_unphased_score(tmp_path):
    """Falsification: --drop phasing on a CIS pair must produce the score
    a truly-unphased run gives (the inheritance bonus restored), not the
    cis-penalized score - before the fix the ablated run kept the
    zeroed inheritance_score, overstating phasing's contribution."""
    from src.config import load_config

    ann1 = synth.Ann("T", "stop_gained", "HIGH", "CISG", "G1",
                     extra={"CLIN_SIG": "pathogenic"})
    ann2 = synth.Ann("C", "stop_gained", "HIGH", "CISG", "G1",
                     extra={"CLIN_SIG": "pathogenic"})
    cis_vcf = synth.write_vcf(tmp_path / "cis.vcf", [
        synth.SVar("7", 1000, "A", "T", gt="0/1", pgt="1|0", pid="PS1",
                   ad=(20, 20), dp=40, gq=99, anns=[ann1]),
        synth.SVar("7", 2000, "G", "C", gt="0/1", pgt="1|0", pid="PS1",
                   ad=(20, 20), dp=40, gq=99, anns=[ann2])])
    unphased_vcf = synth.write_vcf(tmp_path / "unph.vcf", [
        synth.SVar("7", 1000, "A", "T", gt="0/1",
                   ad=(20, 20), dp=40, gq=99, anns=[ann1]),
        synth.SVar("7", 2000, "G", "C", gt="0/1",
                   ad=(20, 20), dp=40, gq=99, anns=[ann2])])
    cfg = load_config()

    base = run_pipeline(str(cis_vcf), [], cfg=cfg)
    cis = next(h for h in base["ranked"]
               if h["gene"] == "CISG" and h["model"] == "compound_het")
    assert cis["in_trans"] == "cis" and cis["inheritance_score"] == 0.0

    abl = run_pipeline(str(cis_vcf), [], cfg=cfg,
                       drops=frozenset({"phasing"}))
    ab = next(h for h in abl["ranked"]
              if h["gene"] == "CISG" and h["model"] == "compound_het")

    unp = run_pipeline(str(unphased_vcf), [], cfg=cfg)
    un = next(h for h in unp["ranked"]
              if h["gene"] == "CISG" and h["model"] == "compound_het")

    assert ab["in_trans"] == "unknown"
    assert ab["score"] == un["score"], \
        "ablated cis pair must score exactly like a truly-unphased pair"
    assert ab["inheritance_score"] == un["inheritance_score"]
