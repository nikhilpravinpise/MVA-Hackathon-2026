"""Edge-case regression battery - bugs found by adversarial audit.

Every test names its falsification condition. Cases here are ones the main
suite never touched: multi-allelic sites, truncated CSQ, malformed VCF
lines, same-position alleles, gzip path, and the secondary-finding rule
boundaries that decide what reaches a family's report.
"""
from __future__ import annotations

import gzip
import pytest

pytestmark = pytest.mark.gate

from conftest import REPO  # noqa: F401
from src import synth
from src.config import load_config
from src.genes import enumerate_hypotheses
from src.phasing import determine_phase, _alt_haplotypes
from src.pipeline import run_pipeline
from src import submit
from src.triage import extract_facts
from src.vcf import VcfReader

CFG = load_config()


def _write_raw(tmp_path, body_lines):
    """A synth-format VCF with literal record lines appended."""
    hdr = synth.write_vcf(tmp_path / "h.vcf", []).read_text()
    lines = [l for l in hdr.splitlines() if not l.startswith("#CHROM")]
    vcf = tmp_path / "t.vcf"
    vcf.write_text("\n".join(lines) +
                   "\n#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND01\n"
                   + "\n".join(body_lines) + "\n")
    return vcf


def _facts(path, sample="PROBAND01"):
    r = VcfReader(str(path))
    try:
        out = []
        for rec in r.records(sample):
            out.extend(extract_facts(rec, sample, CFG))
        return out
    finally:
        r.close()


class TestMultiAllelic:
    def _multiallelic_vcf(self, tmp_path):
        a_t = synth.Ann("T", "missense_variant", "MODERATE", "GA", "G1",
                        extra={"CADD_PHRED": 30, "REVEL": 0.9,
                               "AlphaMissense_score": 0.8,
                               "SIFT": "deleterious",
                               "PolyPhen": "probably_damaging"})
        a_g = synth.Ann("G", "stop_gained", "HIGH", "GA", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        a_a = synth.Ann("A", "missense_variant", "MODERATE", "GA", "G1",
                        extra={"CADD_PHRED": 29, "REVEL": 0.88,
                               "AlphaMissense_score": 0.7,
                               "SIFT": "deleterious",
                               "PolyPhen": "probably_damaging"})
        return _write_raw(tmp_path, [
            "7\t100\t.\tA\tT,G\t60.0\tPASS\tCSQ="
            + a_t.to_csq() + "," + a_g.to_csq()
            + "\tGT:AD:DP:GQ:PGT:PID\t1/2:0,20,20:40:99:1|2:PSM",
            "7\t200\t.\tC\tA\t60.0\tPASS\tCSQ=" + a_a.to_csq()
            + "\tGT:AD:DP:GQ:PGT:PID\t0/1:21,19:40:99:0|1:PSM",
        ])

    def test_multiallelic_fact_indices(self, tmp_path):
        """Falsification: second ALT not emitted as its own fact with
        alt_index=2 and correct het flag - multi-allelic sites silently
        collapse to ALT1 only."""
        f = _facts(self._multiallelic_vcf(tmp_path))
        by_alt = {x.alt: x for x in f if x.gene == "GA" and x.pos == 100}
        assert set(by_alt) == {"T", "G"}
        assert by_alt["T"].alt_index == 1 and by_alt["G"].alt_index == 2
        assert by_alt["T"].is_het and by_alt["G"].is_het

    def test_multiallelic_phase_resolution(self, tmp_path):
        """Falsification: PGT '1|2' resolved against allele index 1 only -
        the second ALT's haplotype is wrong (cis/trans flip)."""
        f = _facts(self._multiallelic_vcf(tmp_path))
        t = next(x for x in f if x.alt == "T" and x.gene == "GA")
        g = next(x for x in f if x.alt == "G" and x.gene == "GA")
        a = next(x for x in f if x.alt == "A")
        # T (alt1) is on hap0 (PGT 1|2); G (alt2) on hap1; A at site2 is 0|1
        # -> on hap1. So T vs A = trans; G vs A = cis.
        assert determine_phase(t, a).relation == "trans"
        assert determine_phase(g, a).relation == "cis"

    def test_multiallelic_vaf_per_alt_index(self, tmp_path):
        """Falsification: ALT2's VAF must come from AD[2], not AD[1] -
        before the fix, a GT=0/2 het read ALT1's depth (0) as its own and
        was silently dropped by the het-VAF QC window."""
        a_t = synth.Ann("T", "stop_gained", "HIGH", "GA", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tC,T\t60.0\tPASS\tCSQ=" + a_t.to_csq()
            + "\tGT:AD:DP:GQ\t0/2:30,0,15:45:99"])
        f = _facts(vcf)
        t_fact = next(x for x in f if x.alt == "T" and x.gene == "GA")
        assert t_fact.vaf == pytest.approx(15 / 45), t_fact.vaf
        assert "het_vaf_outside" not in t_fact.qc_fails

    def test_multiallelic_ad_dot_placeholder(self, tmp_path):
        """Falsification: AD '30,.,15' - dropping the '.' entry shifts
        every later allele's index; ALT2's depth must still be 15."""
        a_t = synth.Ann("T", "stop_gained", "HIGH", "GA", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tC,T\t60.0\tPASS\tCSQ=" + a_t.to_csq()
            + "\tGT:AD:DP:GQ\t0/2:30,.,15:45:99"])
        f = _facts(vcf)
        t_fact = next(x for x in f if x.alt == "T" and x.gene == "GA")
        assert t_fact.vaf == pytest.approx(15 / 45), t_fact.vaf

    def test_format_af_multi_value_uses_alt_index(self, tmp_path):
        """Falsification: FORMAT AF '0.6,0.33' - float() on the whole
        string fails to None (QC window skipped); it is Number=A and
        must be indexed per-ALT."""
        a_t = synth.Ann("T", "stop_gained", "HIGH", "GA", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tC,T\t60.0\tPASS\tCSQ=" + a_t.to_csq()
            + "\tGT:AF:DP:GQ\t0/2:0.6,0.33:45:99"])
        f = _facts(vcf)
        t_fact = next(x for x in f if x.alt == "T" and x.gene == "GA")
        assert t_fact.vaf == pytest.approx(0.33), t_fact.vaf

    def test_multiallelic_pair_enumerated(self, tmp_path):
        """Falsification: same-position multi-allelic alleles (a genuine
        trans-allelic pair) never enumerated as compound-het."""
        f = _facts(self._multiallelic_vcf(tmp_path))
        hyps = [h for h in enumerate_hypotheses(f, CFG)
                if h.model == "compound_het" and h.gene == "GA"]
        keys = {h.pair_key for h in hyps}
        same_pos = [k for k in keys if k[0][1] == k[1][1]]
        assert same_pos, "no same-position (multi-allelic) pair enumerated"


class TestMalformedInput:
    def test_truncated_record_line_context(self, tmp_path):
        """Falsification: a short record line raises a bare unpack error
        with no line number - undebuggable on a 5M-line VCF."""
        vcf = _write_raw(tmp_path, ["7\t100\t.\tA\tT"])
        r = VcfReader(str(vcf))
        with pytest.raises(ValueError, match=r"t\.vcf:\d+"):
            list(r.records("PROBAND01"))
        r.close()

    def test_short_csq_padded(self, tmp_path):
        """Falsification: a CSQ block shorter than the declared header
        misaligns consequence/SYMBOL (silent corruption)."""
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tT\t60.0\tPASS\tCSQ=T|stop_gained|HIGH|GA"
            "\tGT:AD:DP:GQ:PGT:PID\t0/1:20,20:40:99:.:."])
        f = _facts(vcf)
        assert f[0].consequence == "stop_gained" and f[0].gene == "GA"
        assert f[0].damage_tier == "lof"

    def test_blank_line_in_body_skipped(self, tmp_path):
        """Falsification: a stray blank line mid-body crashes the whole
        funnel (was: 'not enough values to unpack' on a 1-col line)."""
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tT\t60.0\tPASS\t.\tGT\t0/1",
            "",
            "7\t200\t.\tC\tG\t60.0\tPASS\t.\tGT\t0/1"])
        r = VcfReader(vcf)
        recs = list(r.records("PROBAND01"))
        r.close()
        assert len(recs) == 2

    def test_no_chrom_header_line_record_pushed_back(self, tmp_path):
        """Falsification: a record line before #CHROM is swallowed as a
        phantom header line -> zero records, silent empty run."""
        hdr = "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tP\n"
        body = "7\t100\t.\tA\tT\t60.0\tPASS\t.\tGT\t0/1\n"
        f1 = tmp_path / "withhdr.vcf"
        f1.write_text("##fileformat=VCFv4.2\n" + hdr + body)
        f2 = tmp_path / "nohdr.vcf"
        f2.write_text("##fileformat=VCFv4.2\n" + body)
        r1, r2 = VcfReader(f1), VcfReader(f2)
        assert len(list(r1.records("P"))) == 1
        assert len(list(r2.records("P"))) == 1  # not swallowed
        r1.close(); r2.close()

    def test_missing_sample_zero_calls_not_crash(self, tmp_path):
        """Falsification: records() on a sample absent from the VCF crashes
        - it must yield uncalled genotypes (the loud check lives in
        run_pipeline, which raises)."""
        vcf = synth.write_vcf(tmp_path / "t.vcf", synth.spike_variants())
        r = VcfReader(str(vcf))
        recs = list(r.records("GHOST"))
        r.close()
        assert recs and all(rec.samples.get("GHOST") is None or
                            not rec.samples["GHOST"].called for rec in recs)


class TestIOEdge:
    def test_gzip_path_identical(self, tmp_path):
        """Falsification: .vcf.gz input diverges from .vcf - magic-byte
        detection silently broken (results differ by filename suffix)."""
        case = synth.spike_in_case(tmp_path)
        gz = tmp_path / "s.vcf.gz"
        gz.write_bytes(gzip.compress(
            (tmp_path / "spike_proband.vcf").read_bytes()))
        plain = run_pipeline(tmp_path / "spike_proband.vcf",
                             case["truth"]["hpo_terms"], obo_path=case["obo"],
                             hpoa_path=case["hpoa"], g2d_path=case["gene2disease"])
        gzres = run_pipeline(str(gz), case["truth"]["hpo_terms"],
                             obo_path=case["obo"], hpoa_path=case["hpoa"],
                             g2d_path=case["gene2disease"])
        sig = [[(v["chrom"], v["pos"], v["alt"]) for v in h["variants"]]
               for h in plain["ranked"]]
        sig_gz = [[(v["chrom"], v["pos"], v["alt"]) for v in h["variants"]]
                  for h in gzres["ranked"]]
        assert sig == sig_gz
        assert plain["funnel"] == gzres["funnel"]

    def test_empty_vcf_zero_funnel(self, tmp_path):
        """Falsification: header-only VCF crashes or emits hypotheses -
        must be a clean zero-count no-call."""
        vcf = synth.write_vcf(tmp_path / "e.vcf", [])
        res = run_pipeline(vcf, ["HP:0001250"])
        assert res["funnel"]["records"] == 0
        assert res["funnel"]["emitted"] == 0 and res["ranked"] == []


class TestSBRulesBoundaries:
    def test_ttn_missense_not_reported(self, tmp_path):
        """Falsification: TTN's truncating_only rule ignored - a missense
        P/LP in TTN produces a false incidental-finding row."""
        from src.sf_scan import load_sf_list, scan_facts
        sf = load_sf_list(REPO / "config" / "acmg_sf_v33.json")
        vs = [synth.SVar("2", 179500000, "A", "T", gt="0/1", anns=[
                 synth.Ann("T", "missense_variant", "MODERATE", "TTN",
                           "ENSTT", extra={"CLIN_SIG": "pathogenic",
                                           "CADD_PHRED": 30})])]
        facts = _facts(synth.write_vcf(tmp_path / "t.vcf", vs))
        assert not any(f.gene == "TTN" for f in scan_facts(facts, sf, CFG))

    def test_ar_gene_single_het_not_reported(self, tmp_path):
        """Falsification: carrier-state AR het reported - exactly the
        carrier-noise the disclosure position promises to suppress."""
        from src.sf_scan import load_sf_list, scan_facts
        sf = load_sf_list(REPO / "config" / "acmg_sf_v33.json")
        ar_gene = next(g for g, d in sf.items()
                       if any(c.get("moi") == "AR" for c in
                              d.get("conditions", [])))
        vs = [synth.SVar("4", 89000000, "G", "A", gt="0/1", anns=[
                 synth.Ann("A", "stop_gained", "HIGH", ar_gene, "ENSA",
                           extra={"CLIN_SIG": "pathogenic",
                                  "CADD_PHRED": 39})])]
        facts = _facts(synth.write_vcf(tmp_path / "t.vcf", vs))
        assert not any(f.gene == ar_gene for f in
                       scan_facts(facts, sf, CFG)), \
            f"single het in AR gene {ar_gene} reported as SF"

    def test_submission_cap_drops_secondaries_first(self):
        """Falsification: 10+ primaries keep secondaries - a primary
        candidate must never lose its slot to an incidental finding."""
        from src.submit import build_rows
        ranked = [{"rank": i, "gene": f"G{i}", "model": "dominant_het",
                   "score": 0.9 - i * 0.01, "epcr": 0.95, "emitted": True,
                   "variants": [{"chrom": "1", "pos": i, "ref": "A",
                                 "alt": "T"}]}
                  for i in range(1, 13)]
        sf = [{"gene": "MSH2", "model": "secondary", "notes": "ACMG SF",
               "variants": [{"chrom": "2", "pos": 47798427, "ref": "A",
                             "alt": "G"}]}]
        rows = build_rows(ranked, sf_rows=sf)
        assert len(rows) == 10
        assert all(r["finding_type"] == "primary" for r in rows)


class TestPhaseEvidenceEdge:
    def test_unphased_separator_unknown(self):
        """Falsification: '0/1' (slash-separated GT-style PGT) parsed as
        phased - unphased input must yield unknown, not a fabricated call."""
        assert _alt_haplotypes("0/1", 1) is None
        assert _alt_haplotypes("1|0", 1) == frozenset({0})
        assert _alt_haplotypes("0|1", 1) == frozenset({1})

    def test_different_phase_sets_unknown(self, tmp_path):
        """Falsification: variants in different phase sets resolved anyway
        (cross-block trans/cis is unobservable from PGT alone)."""
        f = _facts(_write_raw(tmp_path, [
            "7\t100\t.\tA\tT\t60.0\tPASS\t.\tGT:AD:DP:GQ:PGT:PID\t0/1:20,20:40:99:1|0:PS1",
            "7\t200\t.\tG\tC\t60.0\tPASS\t.\tGT:AD:DP:GQ:PGT:PID\t0/1:21,19:40:99:0|1:PS2",
        ]))
        a, b = f[0], f[1]
        assert determine_phase(a, b).relation == "unknown"


def _facts_with_gt(tmp_path, gt: str, ann: synth.Ann, ad: str = "20,20"):
    vcf = _write_raw(tmp_path, [
        "7\t100\t.\tA\tT\t60.0\tPASS\tCSQ=" + ann.to_csq()
        + "\tGT:AD:DP:GQ\t" + gt + ":" + ad + ":40:99"])
    return _facts(vcf)


class TestSfRefRefGuard:
    """Falsification: a ref-ref (0/0) or uncalled fact must NEVER emit an
    SF finding - before the fix, _apply_rule('any') labelled it
    'heterozygous' and reported a pathogenic variant the proband doesn't
    carry."""

    _SF_LIST = {"BRCA2": {"conditions": [
        {"disease": "Breast/Ovarian cancer", "moi": "AD",
         "category": "SFv3.3"}]}}

    def _ann(self):
        return synth.Ann("T", "stop_gained", "HIGH", "BRCA2", "G1",
                         extra={"CLIN_SIG": "pathogenic"})

    def test_hom_ref_no_finding(self, tmp_path):
        from src.sf_scan import scan_facts
        f = _facts_with_gt(tmp_path, "0/0", self._ann())
        assert f and f[0].clinsig_pathogenic  # the P/LP tag is present...
        assert f[0].qc_pass                  # ...and QC passes...
        assert scan_facts(f, self._SF_LIST) == []  # ...but no finding

    def test_uncalled_no_finding(self, tmp_path):
        from src.sf_scan import scan_facts
        f = _facts_with_gt(tmp_path, "./.", self._ann())
        assert scan_facts(f, self._SF_LIST) == []

    def test_het_still_reports(self, tmp_path):
        from src.sf_scan import scan_facts
        f = _facts_with_gt(tmp_path, "0/1", self._ann())
        findings = scan_facts(f, self._SF_LIST)
        assert len(findings) == 1
        assert "heterozygous" in findings[0].reportability

    def test_hom_alt_reports_as_homozygous(self, tmp_path):
        from src.sf_scan import scan_facts
        f = _facts_with_gt(tmp_path, "1/1", self._ann(), ad="0,40")
        findings = scan_facts(f, self._SF_LIST)
        assert len(findings) == 1
        assert "homozygous" in findings[0].reportability


class TestInfoAfTrap:
    """Falsification (DEEP_DIVE sec.2): INFO ``AF`` is a within-sample
    allele fraction (AN=2, ~0.5/1.0 by construction) - it must NEVER
    enter rarity scoring. A variant with INFO AF=0.9 and NO gnomAD fields
    is still 'absent', not common."""

    def test_info_af_not_used_for_rarity(self, tmp_path):
        ann = synth.Ann("T", "stop_gained", "HIGH", "GA", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        vcf = _write_raw(tmp_path, [
            "7\t100\t.\tA\tT\t60.0\tPASS\tAF=0.9;CSQ=" + ann.to_csq()
            + "\tGT:AD:DP:GQ\t0/1:20,20:40:99"])
        f = _facts(vcf)
        assert f[0].absent is True       # INFO AF must not count as gnomAD
        assert f[0].rare is True
        assert f[0].rarity_score == pytest.approx(1.0)


class TestXLinkedContigSpelling:
    """Falsification: x_linked enumeration must accept both 'X' and 'chrX'
    contig spellings - a chr-prefixed patient VCF silently loses the whole
    X-linked model otherwise."""

    def _x_vcf(self, tmp_path, chrom):
        ann = synth.Ann("T", "stop_gained", "HIGH", "XGENE", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        return _write_raw(tmp_path, [
            f"{chrom}\t100\t.\tA\tT\t60.0\tPASS\tCSQ=" + ann.to_csq()
            + "\tGT:AD:DP:GQ\t0/1:20,20:40:99"])

    def test_bare_x_enumerates(self, tmp_path):
        f = _facts(self._x_vcf(tmp_path, "X"))
        hyps = enumerate_hypotheses(f, CFG)
        assert any(h.model == "x_linked" for h in hyps)

    def test_chrx_enumerates(self, tmp_path):
        f = _facts(self._x_vcf(tmp_path, "chrX"))
        hyps = enumerate_hypotheses(f, CFG)
        assert any(h.model == "x_linked" for h in hyps)


class TestHaploidHemizygous:
    """Falsification: a haploid ALT call (male chrX '1') must be modeled as
    hemizygous (hom-equivalent) - before the fix is_het=False and
    is_hom_alt=False (len<2) made the allele invisible to every model."""

    def _x_hemi_vcf(self, tmp_path, chrom):
        ann = synth.Ann("T", "stop_gained", "HIGH", "XGENE", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        return _write_raw(tmp_path, [
            f"{chrom}\t100\t.\tA\tT\t60.0\tPASS\tCSQ=" + ann.to_csq()
            + "\tGT\t1"])

    def test_haploid_x_enumerates_xlinked(self, tmp_path):
        f = _facts(self._x_hemi_vcf(tmp_path, "X"))
        fact = next(x for x in f if x.gene == "XGENE")
        assert not fact.is_het and fact.is_hom_alt
        hyps = enumerate_hypotheses(f, CFG)
        assert any(h.model == "x_linked" for h in hyps)

    def test_haploid_ref_not_alt(self, tmp_path):
        ann = synth.Ann("T", "stop_gained", "HIGH", "XGENE", "G1",
                        extra={"CLIN_SIG": "pathogenic"})
        vcf = _write_raw(tmp_path, [
            "X\t100\t.\tA\tT\t60.0\tPASS\tCSQ=" + ann.to_csq()
            + "\tGT\t0"])  # haploid ref
        f = _facts(vcf)
        fact = next(x for x in f if x.gene == "XGENE")
        assert not fact.is_het and not fact.is_hom_alt


class TestValidateSubmissionEncoding:
    """Falsification: validate_submission_bytes must score exactly like the
    app - which decodes under the Linux server's UTF-8 locale. A cp1252-only
    byte (e.g. raw 0xE9) must raise (the server raises UnicodeDecodeError);
    valid UTF-8 non-ASCII bytes must score, not false-fail locally."""

    def _bytes_with_notes(self, notes_bytes: bytes) -> bytes:
        # variant pair matches tests/conftest.GT (chr1:1234567 A>G + chr1:7654321 C>T)
        line = (b"PROBAND01,chr1,1234567,A,G,chr1,7654321,C,T,0.95,primary,"
                + notes_bytes + b"\n")
        return b"proband_id,chrom_1,pos_1,ref_1,alt_1,chrom_2,pos_2,ref_2,alt_2,epcr,finding_type,notes\n" + line

    def test_valid_utf8_scores(self):
        import sys
        sys.path.insert(0, "tests")
        from conftest import GT
        data = self._bytes_with_notes("café note".encode("utf-8"))
        res = submit.validate_submission_bytes(data, GT)
        assert res.rank_points == 100.0

    def test_cp1252_lone_byte_raises(self):
        import sys
        sys.path.insert(0, "tests")
        from conftest import GT
        data = self._bytes_with_notes(b"caf\xe9 note")  # raw cp1252 'e-acute'
        with pytest.raises(UnicodeDecodeError):
            submit.validate_submission_bytes(data, GT)


class TestStrayHashComment:
    """Falsification: a stray '#'-comment line before #CHROM must NOT be
    treated as the column header - that silently zeroes the sample list so
    every genotype reads as no_call."""

    def test_comment_before_chrom_keeps_samples(self, tmp_path):
        raw = ("##fileformat=VCFv4.2\n"
               "##contig=<ID=7,length=2000>\n"
               "##INFO=<ID=CSQ,Number=.,Type=String,Description=\"f: Allele|Consequence|IMPACT|SYMBOL|Gene\">\n"
               "# a stray comment from a tool\n"
               "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tPROBAND01\n"
               "7\t100\t.\tA\tT\t60.0\tPASS\tCSQ=T|missense_variant|MODERATE|GENEX|G1\tGT:AD:DP:GQ\t0/1:20,20:40:99\n")
        f = tmp_path / "c.vcf"
        f.write_text(raw)
        r = VcfReader(f)
        assert r.samples == ["PROBAND01"], \
            "stray # comment swallowed as header -> samples lost"
        recs = list(r.records(sample="PROBAND01"))
        assert recs[0].samples["PROBAND01"].called


class TestExomiserYaml:
    """Falsification (audit H5/H7): the generated analysis.yml must match
    the exomiser-cli 14.x preset-genome-analysis.yml schema - wrong key
    names or an empty steps chain produce an unrunnable or degenerate
    (no inheritanceFilter -> no comp-het) analysis. And an empty HPO list
    must fail loudly."""

    def test_schema_keys_and_chain(self, tmp_path):
        from tools import run_exomiser as rex
        y = rex.build_yaml(tmp_path / "x.vcf", ["HP:0001250"], "PROBAND01",
                           "PASS_ONLY", "GRCH38", str(tmp_path / "out" / "P"))
        import yaml
        d = yaml.safe_load(y)
        assert set(d) == {"sample", "analysis", "outputOptions"}
        assert set(d["sample"]) == {"vcf", "ped", "assembly", "proband",
                                    "hpoIds"}
        assert d["sample"]["assembly"] == "hg38"  # NOT 'GRCH38'
        assert d["sample"]["hpoIds"] == ["HP:0001250"]
        assert "AUTOSOMAL_RECESSIVE_COMP_HET" in \
            d["analysis"]["inheritanceModes"]
        assert "GNOMAD_E" in d["analysis"]["frequencySources"]
        steps = [list(s)[0] for s in d["analysis"]["steps"]]
        assert "inheritanceFilter" in steps  # empty steps => no MOI analysis
        assert d["outputOptions"]["outputFileName"]

    def test_empty_merged_hpo_fails(self, tmp_path, monkeypatch):
        import json
        from tools import run_exomiser as rex
        empty = tmp_path / "hpo.json"
        empty.write_text(json.dumps({"hpo_terms": []}))
        with pytest.raises(SystemExit) as ei:
            rex.main(["--vcf", "x.vcf", "--hpo-terms", str(empty),
                      "--dry-run"])
        assert ei.value.code != 0


class TestReadsFlagSkips:
    """Falsification: reads.py skip-counters for secondary/supp/dup/qcfail/
    low-mapq - every flag combination must be excluded from evidence, not
    silently counted."""

    def _sam(self, flag, mapq=60):
        return (f"r1\t{flag}\t7\t100\t{mapq}\t20M\t*\t0\t0\t"
                "AAAAAAAAAAAAAAAAAAAA\t" + "I" * 20)

    V1, V2 = ("7", 95, "A", "T"), ("7", 105, "G", "C")

    def test_flag_matrix(self):
        from src.reads import template_support
        # secondary(256) | supplementary(2048) | duplicate(1024) | qcfail(512)
        for flag, key in [(256, "skipped_secondary_supp"),
                          (2048, "skipped_secondary_supp"),
                          (1024, "skipped_duplicate"),
                          (512, "skipped_qcfail")]:
            r = template_support(iter([self._sam(flag)]),
                                 [self.V1, self.V2])
            assert r["stats"][key] == 1, \
                f"flag {flag} did not land in {key}: {r['stats']}"

    def test_low_mapq_skipped(self):
        from src.reads import template_support
        r = template_support(iter([self._sam(0, mapq=10)]),
                             [self.V1, self.V2], min_mapq=30)
        assert r["stats"]["skipped_low_mapq"] == 1

    def test_unmapped_skipped(self):
        from src.reads import template_support
        r = template_support(iter([self._sam(4)]),  # unmapped
                             [self.V1, self.V2])
        assert r["stats"]["skipped_unmapped"] == 1


class TestCsqAlleleUnmatched:
    """Falsification: a CSQ block whose Allele field matches NO record ALT
    (annotation/allele mismatch) silently loses the variant's gene - the
    n_csq_allele_unmatched counter must surface it in QC."""

    def test_mismatched_csq_allele_counted(self, tmp_path):
        from src.vcf_qc import compute_stats
        raw = ("##fileformat=VCFv4.2\n"
               "##contig=<ID=7,length=2000>\n"
               "##INFO=<ID=CSQ,Number=.,Type=String,Description=\"f Format: Allele|Consequence|IMPACT|SYMBOL|Gene\">\n"
               "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\tS1\n"
               # record ALT is T; CSQ claims allele G -> mismatch
               "7\t100\t.\tA\tT\t60.0\tPASS\tCSQ=G|missense_variant|MODERATE|GENEX|G1\tGT:AD:DP:GQ\t0/1:20,20:40:99\n")
        f = tmp_path / "m.vcf"
        f.write_text(raw)
        st = compute_stats(f, sample="S1")
        assert st["n_csq_allele_unmatched"] == 1
