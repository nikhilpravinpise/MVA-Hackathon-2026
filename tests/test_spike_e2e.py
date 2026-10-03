"""GATE 2 e2e: the complete funnel recovers the synthetic spike-in pair
blind, at the rank the plan requires, with in-trans evidence attached.

Falsification (plan.md Gate 2): if the true SPIKEA compound-het pair is not
the top emitted hypothesis (rank <= 3), the funnel is wrong - fix before
touching proband results.
"""
from __future__ import annotations

import json
import pytest

from src import synth
from src.pipeline import run_pipeline


@pytest.fixture(scope="module")
def spike(tmp_path_factory):
    d = tmp_path_factory.mktemp("spike")
    return synth.spike_in_case(d)


@pytest.mark.gate
def test_spike_pair_recovered_top3(spike, tmp_path):
    """Falsification: funnel fails to recover a known compound-het pair it
    was never told about - the pipeline does not work."""
    res = run_pipeline(
        spike["vcf"], spike["truth"]["hpo_terms"],
        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
        g2d_path=spike["gene2disease"], out_dir=tmp_path / "run")
    emitted = [h for h in res["ranked"] if h["emitted"]]
    assert emitted, "nothing emitted - emit floor swallowed the truth"
    top = emitted[0]
    assert top["rank"] <= 3, f"true pair ranked {top['rank']}"
    assert top["model"] == "compound_het"
    got = sorted((v["pos"], v["alt"]) for v in top["variants"])
    want = sorted((v["pos"], v["alt"]) for v in spike["truth"]["pair"])
    assert got == want, f"recovered {got}, truth {want}"
    assert top["in_trans"] == "trans"
    assert top["epcr"] == pytest.approx(0.95)


@pytest.mark.gate
def test_spike_funnel_monotonic(spike):
    """Falsification: a stage emits MORE items than it consumed - the funnel
    fabricates variants (monotonicity audit is the tripwire)."""
    res = run_pipeline(
        spike["vcf"], spike["truth"]["hpo_terms"],
        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
        g2d_path=spike["gene2disease"])
    assert res["monotonicity_violations"] == []
    fc = res["funnel"]
    assert fc["candidates"] < fc["records"] or fc["records"] == 0


@pytest.mark.gate
def test_decoys_suppressed(spike):
    """Falsification: adversarial decoys (TTN-class noise pair, common
    hom-alt, filtered LoF) reach the emitted set - funnel hallucinates."""
    res = run_pipeline(
        spike["vcf"], spike["truth"]["hpo_terms"],
        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
        g2d_path=spike["gene2disease"])
    emitted_genes = {h["gene"] for h in res["ranked"] if h["emitted"]}
    assert "TTN" not in emitted_genes
    assert res["funnel"]["emitted"] > 0, "no hypotheses emitted - assertion is vacuous"
    assert all(h["gene"] == "SPIKEA" for h in res["ranked"] if h["emitted"])


@pytest.mark.gate
def test_spike_deterministic_bytes(spike, tmp_path):
    """Falsification: two identical runs write different result.json bytes -
    hidden nondeterminism would make the submission irreproducible."""
    run_pipeline(spike["vcf"], spike["truth"]["hpo_terms"],
                 obo_path=spike["obo"], hpoa_path=spike["hpoa"],
                 g2d_path=spike["gene2disease"],
                 out_dir=tmp_path / "r1")
    run_pipeline(spike["vcf"], spike["truth"]["hpo_terms"],
                 obo_path=spike["obo"], hpoa_path=spike["hpoa"],
                 g2d_path=spike["gene2disease"],
                 out_dir=tmp_path / "r2")
    b1 = json.loads((tmp_path / "r1" / "result.json").read_text())
    b2 = json.loads((tmp_path / "r2" / "result.json").read_text())
    # runtime fields are allowed to differ; everything else must not
    for k in ("funnel", "ranked", "emitted", "monotonicity_violations"):
        assert b1[k] == b2[k], k
