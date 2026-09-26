"""GATE 2 negative control: on a plausible-but-noncausal VCF the funnel must
emit NOTHING (no-call is a valid answer). A funnel that finds a causal pair
everywhere finds nothing (plan.md 2.1.4).
"""
from __future__ import annotations

import pytest

from src import synth
from src.pipeline import run_pipeline


@pytest.fixture(scope="module")
def ctrl(tmp_path_factory):
    return synth.control_case(tmp_path_factory.mktemp("ctrl"))


@pytest.mark.gate
def test_no_emitted_hypotheses(ctrl):
    """Falsification: any hypothesis crosses the emit floor on the control -
    the funnel hallucinated a causal pair from noise."""
    res = run_pipeline(
        ctrl["vcf"], json_terms(ctrl), obo_path=ctrl["obo"],
        hpoa_path=ctrl["hpoa"], g2d_path=ctrl["gene2disease"])
    assert res["funnel"]["emitted"] == 0, \
        [h for h in res["ranked"] if h["emitted"]]


@pytest.mark.gate
def test_noise_gene_pair_below_floor(ctrl):
    """Falsification: the worst-case adversary (two rare damaging TTN hets
    forming a comp-het) is not visibly suppressed - the emit floor failed
    its designed purpose."""
    res = run_pipeline(
        ctrl["vcf"], json_terms(ctrl), obo_path=ctrl["obo"],
        hpoa_path=ctrl["hpoa"], g2d_path=ctrl["gene2disease"])
    from src.config import load_config
    floor = load_config()["scoring"]["emit_floor"]
    ttn = [h for h in res["ranked"] if h["gene"] == "TTN"]
    assert ttn, "control fixture lost its TTN decoy - fixture drifted"
    assert all(h["score"] < floor for h in ttn)


def json_terms(case):
    import json
    return json.loads(case["hpo"].read_text())["hpo_terms"]
