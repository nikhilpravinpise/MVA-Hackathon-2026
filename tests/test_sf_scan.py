"""Tests for src/sf_scan.py - the ACMG SF v3.3 secondary-findings scan.

Falsification conditions (plan.md 2.2): each test names the concrete bug
it would catch. All fixtures are synthesized via src.synth; gene symbols
(BRCA2, ATP7B, TTN, ABCD1, HFE) are taken verbatim from
config/acmg_sf_v33.json, never from any leaked source.
"""
from __future__ import annotations

import conftest
import pytest

from src.config import load_config
from src.synth import SVar, Ann, write_vcf, _af_ann
from src.triage import extract_facts
from src.vcf import VcfReader
from src import sf_scan


def _facts(tmp_path, variants):
    """Funnel stage-0 over a synthetic VCF: records -> VariantFacts."""
    path = write_vcf(tmp_path / "case.vcf", variants)
    cfg = load_config()
    reader = VcfReader(path)
    sample = reader.samples[0]
    out = []
    try:
        for rec in reader.records(sample=sample):
            out.extend(extract_facts(rec, sample, cfg))
    finally:
        reader.close()
    return out


def _plp(chrom, pos, gene, gt="0/1", clin="pathogenic",
         cons="stop_gained", af=None, ad=(22, 23), hgvsp=""):
    """A ClinVar-P/LP-class variant in ``gene`` (P/LP via CLIN_SIG)."""
    extra = dict(_af_ann(af, af))
    extra["CLIN_SIG"] = clin
    if hgvsp:
        extra["HGVSp"] = hgvsp
    return SVar(chrom, pos, "A", "T", gt=gt, ad=ad,
                anns=[Ann("T", cons, "HIGH", gene, "ENSG0" + gene,
                          extra=extra)])


@pytest.fixture
def sf_list():
    return sf_scan.load_sf_list()


# ---------------------------------------------------------------------------
# AD gene: single het P/LP reportable
# ---------------------------------------------------------------------------

def test_ad_gene_het_pathogenic_emits_finding(tmp_path, sf_list):
    """Falsification: if a lone het ClinVar-P variant in an AD SF gene
    (BRCA2, moi='AD', 'All P and LP') produced no finding, the scanner is
    dropping the canonical reportable case."""
    facts = _facts(tmp_path, [_plp("7", 20_000_000, "BRCA2")])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert len(findings) == 1
    f = findings[0]
    assert f.gene == "BRCA2"
    assert f.moi == "AD"
    assert f.basis == "clinvar"
    assert f.disease == "Hereditary breast and ovarian cancer"
    assert f.suggested_finding_type == "secondary"
    assert len(f.variants) == 1 and f.variants[0].pos == 20_000_000


def test_common_af_clinvar_p_still_reportable(tmp_path, sf_list):
    """Falsification: if the rarity gate leaked into the SF scan, a
    ClinVar-P variant at popmax 2% (still actionable) would be dropped."""
    facts = _facts(tmp_path, [_plp("7", 20_100_000, "BRCA2", af=0.02)])
    assert not facts[0].rare  # funnel says common; SF must not care
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert len(findings) == 1 and findings[0].gene == "BRCA2"


# ---------------------------------------------------------------------------
# AR gene: carrier-pair policy
# ---------------------------------------------------------------------------

def test_ar_single_het_no_finding_second_het_finds(tmp_path, sf_list):
    """Falsification: catches two bugs - (a) reporting a lone AR carrier
    het (not reportable under SF policy), (b) failing the >=2 het
    gene-level aggregation for ATP7B ('P and LP (2 variants)')."""
    one = _facts(tmp_path, [_plp("12", 52_000_000, "ATP7B")])
    assert sf_scan.scan_facts(one, sf_list, load_config()) == []

    two = _facts(tmp_path, [
        _plp("12", 52_000_000, "ATP7B"),
        _plp("12", 52_050_000, "ATP7B", gt="0/1"),
    ])
    findings = sf_scan.scan_facts(two, sf_list, load_config())
    assert len(findings) == 1
    f = findings[0]
    assert f.gene == "ATP7B" and f.moi == "AR"
    assert len(f.variants) == 2
    assert "ar_carrier_pair" in f.caveats


def test_ar_homozygous_pathogenic_finding(tmp_path, sf_list):
    """Falsification: a homozygous ClinVar-P in an AR gene is the textbook
    reportable case; losing it means hom calls are mishandled."""
    facts = _facts(tmp_path, [
        _plp("12", 52_000_000, "ATP7B", gt="1/1", ad=(1, 40))])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert len(findings) == 1
    f = findings[0]
    assert f.variants[0].is_hom_alt
    assert "biallelic" in f.note or "hom" in f.note


# ---------------------------------------------------------------------------
# Restricted-gene rules and exclusions
# ---------------------------------------------------------------------------

def test_non_sf_gene_pathogenic_no_finding(tmp_path, sf_list):
    """Falsification: the scan must be restricted to the 84 SF genes; a
    ClinVar-P hit in a non-listed gene must produce nothing (an unbounded
    scan would flood secondary rows)."""
    facts = _facts(tmp_path, [_plp("7", 30_000_000, "NOTSF")])
    assert sf_scan.scan_facts(facts, sf_list, load_config()) == []


def test_benign_and_conflicting_clinsig_no_finding(tmp_path, sf_list):
    """Falsification: 'benign' and 'conflicting_interpretations_of_-
    pathogenicity' CLIN_SIG strings must not count as P/LP; a token
    matcher missing the 'conflict' exclusion would over-report."""
    facts = _facts(tmp_path, [
        _plp("7", 20_200_000, "BRCA2", clin="benign"),
        _plp("7", 20_300_000, "BRCA2",
             clin="conflicting_interpretations_of_pathogenicity"),
        _plp("7", 20_400_000, "BRCA2", clin=""),
    ])
    assert not any(f.clinsig_pathogenic for f in facts)
    assert sf_scan.scan_facts(facts, sf_list, load_config()) == []


def test_qc_fail_variant_no_finding(tmp_path, sf_list):
    """Falsification: a ClinVar-P variant failing genotype QC (low DP/GQ)
    must not be disclosed - a finding on a genotyping artifact is worse
    than no finding."""
    v = _plp("7", 20_500_000, "BRCA2")
    v.dp, v.gq, v.ad = 4, 12, (3, 1)
    facts = _facts(tmp_path, [v])
    assert not facts[0].qc_pass
    assert sf_scan.scan_facts(facts, sf_list, load_config()) == []


def test_ttn_truncating_only_rule(tmp_path, sf_list):
    """Falsification: TTN reports 'P and LP (truncating variants only)';
    a ClinVar-P MISSENSE in TTN must not be reported while a LoF one is.
    Catches a rule parser that ignores per-gene variant restrictions."""
    facts = _facts(tmp_path, [
        _plp("12", 17_000_000, "TTN", cons="missense_variant"),
        _plp("12", 17_100_000, "TTN", cons="stop_gained"),
    ])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert len(findings) == 1
    assert findings[0].variants[0].pos == 17_100_000
    assert findings[0].variants[0].damage_tier == "lof"


def test_xl_single_het_emits_with_sex_caveat(tmp_path, sf_list):
    """Falsification: ABCD1 needs hemi/hom P/LP or >=2 hets; with sex
    unknown a lone chrX het is a possible hemizygote and must be reported
    WITH the sex_unknown caveat, never silently."""
    facts = _facts(tmp_path, [_plp("X", 15_000_000, "ABCD1")])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert len(findings) == 1
    f = findings[0]
    assert f.moi == "XL"
    assert "sex_unknown" in f.caveats


def test_hfe_allele_restriction(tmp_path, sf_list):
    """Falsification: HFE reports 'p.C282Y homozygotes only'. A hom P/LP
    without HGVS confirmation must be dropped; a confirmed p.C282Y hom
    must be kept. Catches an allele-blind hom check."""
    unconfirmed = _facts(tmp_path, [
        _plp("12", 26_000_000, "HFE", gt="1/1", ad=(1, 40))])
    assert sf_scan.scan_facts(unconfirmed, sf_list, load_config()) == []

    confirmed = _facts(tmp_path, [
        _plp("12", 26_000_000, "HFE", gt="1/1", ad=(1, 40),
             hgvsp="p.Cys282Tyr")])
    findings = sf_scan.scan_facts(confirmed, sf_list, load_config())
    assert len(findings) == 1
    assert "allele_restricted" in findings[0].caveats


def test_predicted_lof_opt_in(tmp_path, sf_list):
    """Falsification: predicted-LoF reporting is opt-in only; with the
    flag off a LoF variant lacking ClinVar P/LP must stay unreported,
    with the flag on it must surface flagged 'predicted'."""
    facts = _facts(tmp_path, [_plp("7", 20_600_000, "BRCA2", clin="")])
    cfg = load_config()
    assert sf_scan.scan_facts(facts, sf_list, cfg) == []
    findings = sf_scan.scan_facts(facts, sf_list, cfg,
                                  include_predicted_lof=True)
    assert len(findings) == 1
    assert findings[0].basis == "predicted"
    assert "predicted_not_clinvar" in findings[0].caveats


# ---------------------------------------------------------------------------
# CSV-notes contract + funnel-to-rows gate
# ---------------------------------------------------------------------------

def test_notes_ascii_and_length(tmp_path, sf_list):
    """Falsification: notes cells go into a CSV judged by patient
    advocates; non-ASCII or >=80-char strings would break the contract."""
    facts = _facts(tmp_path, [
        _plp("7", 20_000_000, "BRCA2"),
        _plp("12", 52_000_000, "ATP7B"),
        _plp("12", 52_050_000, "ATP7B"),
        _plp("X", 15_000_000, "ABCD1"),
        _plp("12", 17_100_000, "TTN"),
        _plp("7", 21_000_000, "SCN5A", clin="likely_pathogenic"),
    ])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    assert findings, "expected several findings for the ASCII check"
    for f in findings:
        assert f.note.isascii()
        assert 0 < len(f.note) < 80


def test_gate_funnel_to_secondary_rows(tmp_path, sf_list):
    """Falsification (GATE 4): end-to-end - synthetic VCF -> extract_facts
    -> scan_facts -> findings_to_rows must yield writer-consumable
    secondary rows ('chr'-prefixed coords, finding_type='secondary') that
    the vendored scorer parses without error."""
    facts = _facts(tmp_path, [
        _plp("7", 20_000_000, "BRCA2"),
        _plp("12", 52_000_000, "ATP7B"),
        _plp("12", 52_050_000, "ATP7B"),
        _plp("7", 30_000_000, "NOTSF"),          # must not appear
    ])
    findings = sf_scan.scan_facts(facts, sf_list, load_config())
    rows = sf_scan.findings_to_rows(findings)

    assert rows, "no secondary rows produced"
    for r in rows:
        assert set(r) == {"chrom", "pos", "ref", "alt", "finding_type",
                          "note"}
        assert r["chrom"].startswith("chr")
        assert r["finding_type"] == "secondary"
        assert r["note"].isascii() and len(r["note"]) < 80
    # 1 BRCA2 variant + 2 ATP7B pair variants = 3 rows
    assert len(rows) == 3
    assert {r["pos"] for r in rows} == {20_000_000, 52_000_000, 52_050_000}

    # Emulate the writer: secondary rows at capped epcr, scored by the
    # vendored oracle - must parse cleanly (finding_type validated).
    csv_rows = [conftest.row(c1=r["chrom"], p1=str(r["pos"]), r1=r["ref"],
                             a1=r["alt"], epcr="0.2", ft="secondary",
                             notes=r["note"]) for r in rows]
    res = conftest.score_rows(csv_rows)
    assert res is not None  # parse + score succeeded; rows contract-valid


def test_sf_list_loader_shape(sf_list):
    """Falsification: the scan must run against the real 84-gene v3.3
    list; a swapped/truncated JSON would silently change the gene set."""
    assert len(sf_list) == 84
    assert sf_list["BRCA2"]["conditions"][0]["moi"] == "AD"
    assert sf_list["ATP7B"]["conditions"][0]["moi"] == "AR"
    assert sf_list["ABCD1"]["conditions"][0]["moi"] == "XL"
