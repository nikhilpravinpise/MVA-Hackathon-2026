"""Artifact-locus mask: declared low-mappability loci exit the funnel at a
disclosed stage between candidate enumeration and hypothesis enumeration.

Falsification focus: the mask must be chromosome- and position-exact
(boundary inclusive, chr-prefix agnostic), config-driven (empty = no-op),
and inherited by every ablation - a mask that silently under/over-removes
is an invisible funnel divergence.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.gate

from conftest import REPO  # noqa: F401  (sys.path setup side-effect)
from src import synth
from src.config import load_config
from src.loci import in_artifact_locus, validate_artifact_loci
from src.pipeline import run_pipeline

MHC = {"chrom": "6", "start": 28500000, "end": 33500000,
       "label": "extended_MHC"}
SPIKE_LOCUS = {"chrom": "7", "start": 900000, "end": 1100000,
               "label": "spike_locus"}


def _cfg(**over):
    cfg = load_config()
    cfg.update(over)
    return cfg


class TestInArtifactLocus:
    def test_inside_returns_label(self):
        cfg = {"artifact_loci": [MHC]}
        assert in_artifact_locus("6", 30000000, cfg) == "extended_MHC"

    def test_outside_returns_none(self):
        cfg = {"artifact_loci": [MHC]}
        assert in_artifact_locus("6", 28499999, cfg) is None
        assert in_artifact_locus("6", 33500001, cfg) is None
        assert in_artifact_locus("7", 30000000, cfg) is None

    def test_boundary_inclusive(self):
        """Falsification: off-by-one at locus edges drops/keeps one extra
        variant - the boundary must be inclusive on both ends."""
        cfg = {"artifact_loci": [MHC]}
        assert in_artifact_locus("6", 28500000, cfg) == "extended_MHC"
        assert in_artifact_locus("6", 33500000, cfg) == "extended_MHC"

    def test_chrom_normalization(self):
        """Falsification: 'chr6' facts on a '6' locus (or vice versa) slip
        the mask - the challenge VCF is bare-contig but contig spellings
        must not change mask semantics."""
        cfg = {"artifact_loci": [MHC]}
        for c in ("6", "chr6", "CHR6", "Chr6"):
            assert in_artifact_locus(c, 31000000, cfg) == "extended_MHC", c
        cfg_chr = {"artifact_loci": [{**MHC, "chrom": "chr6"}]}
        assert in_artifact_locus("6", 31000000, cfg_chr) == "extended_MHC"

    def test_position_agnostic_to_allele(self):
        """Falsification: mask keyed on alleles instead of position would
        miss the alternate allele of a multi-allelic site."""
        cfg = {"artifact_loci": [MHC]}
        assert in_artifact_locus("6", 31000000, cfg)
        # in_artifact_locus takes (chrom, pos) only - allele-blind by
        # signature; multi-allelic sites mask every alt uniformly.

    def test_empty_and_missing_are_noop(self):
        assert in_artifact_locus("6", 31000000, {}) is None
        assert in_artifact_locus("6", 31000000,
                               {"artifact_loci": []}) is None

    def test_label_default(self):
        cfg = {"artifact_loci": [{"chrom": "6", "start": 1, "end": 2}]}
        assert in_artifact_locus("6", 1, cfg) == "6:1-2"

    def test_int_chrom_accepted(self):
        cfg = {"artifact_loci": [{"chrom": 6, "start": 1, "end": 100}]}
        assert in_artifact_locus("chr6", 50, cfg)


class TestValidateArtifactLoci:
    def test_real_config_passes(self):
        validate_artifact_loci(load_config())

    def test_missing_and_empty_ok(self):
        validate_artifact_loci({})
        validate_artifact_loci({"artifact_loci": []})

    @pytest.mark.parametrize("bad", [
        {"chrom": "6", "start": 1},                      # missing end
        {"chrom": "6", "end": 2},                        # missing start
        {"start": 1, "end": 2},                          # missing chrom
        {"chrom": "6", "start": "1", "end": 2},          # non-int start
        {"chrom": "6", "start": 1, "end": 2.5},          # non-int end
        {"chrom": "6", "start": True, "end": 2},         # bool is not int
        {"chrom": "6", "start": 5, "end": 2},            # start > end
        "not-a-mapping",
    ])
    def test_malformed_entries_raise(self, bad):
        with pytest.raises(ValueError, match="artifact_loci"):
            validate_artifact_loci({"artifact_loci": [bad]})

    @pytest.mark.parametrize("bad_top", [
        {"chrom": "6", "start": 1, "end": 2},            # dict not list
        "6:1-2",                                         # string not list
        5,
    ])
    def test_non_list_top_level_raises(self, bad_top):
        with pytest.raises(ValueError, match="artifact_loci"):
            validate_artifact_loci({"artifact_loci": bad_top})

    def test_bad_chrom_type_raises(self):
        with pytest.raises(ValueError, match="artifact_loci"):
            validate_artifact_loci(
                {"artifact_loci": [{"chrom": None, "start": 1, "end": 2}]})

    def test_run_pipeline_rejects_malformed(self, tmp_path):
        """Falsification: run_pipeline silently ignoring a malformed locus -
        validation happens at entry, before any VCF work."""
        vcf = synth.write_vcf(tmp_path / "t.vcf", [])
        with pytest.raises(ValueError, match="artifact_loci"):
            run_pipeline(vcf, [], cfg=_cfg(
                artifact_loci={"chrom": "6"}))


@pytest.fixture(scope="module")
def spike(tmp_path_factory):
    d = tmp_path_factory.mktemp("spike")
    return synth.spike_in_case(d)


def _run(spike, cfg=None, drops=frozenset()):
    return run_pipeline(
        spike["vcf"], spike["truth"]["hpo_terms"],
        obo_path=spike["obo"], hpoa_path=spike["hpoa"],
        g2d_path=spike["gene2disease"], cfg=cfg, drops=drops)


class TestMaskE2E:
    def test_masked_pair_never_emits(self, spike):
        """Falsification: a hypothesis inside a declared locus still reaches
        the ranked/emitted set - the mask is cosmetic, not real."""
        res = _run(spike, cfg=_cfg(artifact_loci=[SPIKE_LOCUS]))
        fc = res["funnel"]
        assert fc["locus_masked_out"] > 0
        assert all(h["gene"] != "SPIKEA" for h in res["ranked"])
        assert res["monotonicity_violations"] == []

    def test_mask_off_unchanged(self, spike):
        """Falsification: empty artifact_loci still alters the funnel - a
        no-op that isn't a no-op means the stage leaks."""
        base = _run(spike, cfg=_cfg())
        masked = _run(spike, cfg=_cfg(artifact_loci=[]))
        assert masked["funnel"]["locus_masked"] == \
            masked["funnel"]["candidates"]
        assert masked["funnel"]["locus_masked_out"] == 0
        for k in ("ranked", "emitted"):
            assert base[k] == masked[k], k

    def test_count_invariants(self, spike):
        """Falsification: locus counts that don't sum - the disclosure
        stage must satisfy locus_masked + locus_masked_out == candidates
        and locus_masked <= candidates exactly."""
        res = _run(spike, cfg=_cfg(artifact_loci=[SPIKE_LOCUS]))
        fc = res["funnel"]
        assert fc["locus_masked"] <= fc["candidates"]
        assert (fc["locus_masked"] + fc["locus_masked_out"]
                == fc["candidates"])

    def test_locus_masked_in_monotonic_order(self):
        """Falsification: the disclosed stage sits outside the monotonic
        audit - a mask bug could fabricate candidates unchecked."""
        from src.pipeline import FunnelCounts
        c = FunnelCounts()
        c.stage_counts.update(
            {"alt_gene_facts": 10, "qc_pass": 8, "rare": 6,
             "candidates": 5, "locus_masked": 7})
        assert c.check_monotonic(), \
            "locus_masked > candidates must violate monotonicity"
        c.stage_counts["locus_masked"] = 5
        assert c.check_monotonic() == []

    @pytest.mark.parametrize("drop", ["gnomad", "damage_predictors",
                                      "clinvar", "hpo", "phasing"])
    def test_ablation_inherits_mask(self, spike, drop):
        """Falsification: an ablation path bypassing the mask - every drop
        must still remove locus facts (the mask is funnel-level, not
        evidence-level)."""
        res = _run(spike, cfg=_cfg(artifact_loci=[SPIKE_LOCUS]),
                   drops=frozenset({drop}))
        assert res["funnel"]["locus_masked_out"] > 0
        assert all(h["gene"] != "SPIKEA" for h in res["ranked"])

    def test_other_loci_untouched(self, spike):
        """Falsification: masking SPIKEA's locus also removes unrelated
        decoys outside it - the mask must be position-exact."""
        res = _run(spike, cfg=_cfg(artifact_loci=[SPIKE_LOCUS]))
        # TTN decoy lives on chr12 - outside the chr7 locus; its facts must
        # survive the mask (still suppressed downstream by noise_genes).
        fc = res["funnel"]
        assert fc["locus_masked"] > 0, "mask removed everything"
