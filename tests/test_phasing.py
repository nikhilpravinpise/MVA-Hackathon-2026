"""Gate tests for cis/trans phasing evidence (plan.md Phase 3, GATE 3).

Two evidence lines are covered, and must AGREE before the pair is
believed:

* PGT/PID read-backed phasing already in the VCF - src/phasing.
  determine_phase over VariantFacts (unit level) and the full
  VCF -> extract_facts -> candidate -> comp-het enumeration chain
  (end to end on the synthetic spike-in proband).
* read-level evidence - src/reads.phase_from_reads over SAM text from
  the deterministic src/synth_sam fixtures: in-trans = no molecule
  carries both alt alleles.

Every test docstring names its falsification condition - the concrete
regression it would catch (plan.md section 2.2).
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from src import phasing, reads, synth, synth_sam
from src.config import load_config
from src.genes import enumerate_hypotheses
from src.triage import VariantFacts, eligible, extract_facts
from src.vcf import VcfReader

pytestmark = pytest.mark.gate

REPO = Path(__file__).resolve().parents[1]

# tools/ is a script dir, not a package - load run_phasing by path so the
# test does not depend on namespace-package resolution order.
_spec = importlib.util.spec_from_file_location(
    "run_phasing_tool", REPO / "tools" / "run_phasing.py")
run_phasing = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(run_phasing)


def _vf(pgt=None, pid=None, pos=1000, ref="A", alt="T", chrom="7",
        alt_index=1):
    """Minimal het VariantFacts for determine_phase (only chrom/pos/ref/
    alt/pgt/pid/alt_index/vid are read)."""
    return VariantFacts(
        chrom=chrom, pos=pos, ref=ref, alt=alt, gene="GENE",
        gene_id="ENSG0X", transcript="ENST0X",
        consequence="missense_variant", impact="MODERATE",
        biotype="protein_coding", is_het=True, pgt=pgt, pid=pid,
        alt_index=alt_index)


class TestPgtPidPhase:
    """determine_phase over PGT/PID - the primary phasing evidence."""

    def test_same_pid_trans(self):
        """Falsification: alt-on-hap1 vs alt-on-hap2 inside one phase set
        must resolve to trans; fails if PGT allele ordering or the PID
        equality check regresses."""
        c = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("0|1", "PS1", pos=2000, ref="G", alt="C"))
        assert c.relation == "trans"
        assert c.mechanism == "pgt_pid_same_set"
        assert "PS1" in c.detail

    def test_same_pid_cis(self):
        """Falsification: alt on the SAME haplotype in both sites must
        resolve to cis; fails if the haplotype-set disjointness test
        flips."""
        c = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("1|0", "PS1", pos=2000, ref="G", alt="C"))
        assert c.relation == "cis"
        assert c.mechanism == "pgt_pid_same_set"

    def test_different_pids_unknown(self):
        """Falsification: two sites in different phase sets cannot be
        resolved from PGT/PID alone; fails if the tool guesses instead of
        honestly reporting unknown + unphased mechanism."""
        c = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("0|1", "PS2", pos=2000, ref="G", alt="C"))
        assert c.relation == "unknown"
        assert c.mechanism == "unphased"
        assert "phase set" in c.detail

    def test_missing_pgt_unknown(self):
        """Falsification: an unphased genotype (no '|' PGT) yields no
        haplotype membership; fails if a missing PGT is treated as
        evidence."""
        for bad_pgt in (None, "0/1"):
            c = phasing.determine_phase(
                _vf(bad_pgt, "PS1", pos=1000),
                _vf("0|1", "PS1", pos=2000, ref="G", alt="C"))
            assert c.relation == "unknown", bad_pgt
            assert c.mechanism == "unphased", bad_pgt

    def test_hom_alt_pgt_edge(self):
        """Falsification: non-het PGT handling must not silently change.
        A 0|0 site has an EMPTY alt-haplotype set -> 'unknown' with the
        homozygous detail. A 1|1 site carries alt on both haps, so its
        haplotype set {0,1} is never disjoint from a het's -> mechanical
        'cis'. (Hom sites never reach pair enumeration downstream - only
        is_het facts pair - so this pins semantics, not pipeline output.)
        """
        het = _vf("0|1", "PS1", pos=2000, ref="G", alt="C")

        c = phasing.determine_phase(_vf("0|0", "PS1", pos=1000), het)
        assert c.relation == "unknown"
        assert c.mechanism == "pgt_pid_same_set"
        assert "alt absent" in c.detail

        c2 = phasing.determine_phase(_vf("1|1", "PS1", pos=1000), het)
        assert c2.relation == "cis"  # {0,1} not disjoint from {1}
        assert c2.mechanism == "pgt_pid_same_set"

    def test_different_contigs_unknown(self):
        """Falsification: phase is a same-molecule concept; cross-contig
        pairs must be undecidable."""
        c = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000, chrom="7"),
            _vf("0|1", "PS1", pos=2000, ref="G", alt="C", chrom="12"))
        assert c.relation == "unknown"
        assert c.mechanism == "unphased"

    def test_multiallelic_second_alt_uses_its_own_index(self):
        """Falsification: a multi-allelic site's second ALT must resolve
        against its OWN alt_index, not a hardcoded 1 - a REF=A ALT=T,C
        site with GT=1/2, PGT=1|2 puts T (alt_index=1) on hap0 and C
        (alt_index=2) on hap1: genuinely trans. Hardcoding alt_index=1 for
        the C fact would check hap0 for value 1 (found -> {0}), making it
        look like it shares T's haplotype -> a false 'cis' call."""
        t_fact = _vf("1|2", "PS1", pos=1000, ref="A", alt="T", alt_index=1)
        c_fact = _vf("1|2", "PS1", pos=1000, ref="A", alt="C", alt_index=2)
        c = phasing.determine_phase(t_fact, c_fact)
        assert c.relation == "trans"


class TestSamParsing:
    """parse_sam_line / read_allele_at coordinate honesty."""

    def test_softclip_and_insertion_cigar(self):
        """Falsification: soft-clips must not count as aligned and an
        insertion must not shift the ref->query map; fails on any
        off-register lookup."""
        seq = "C" * 10 + "A" * 5 + "GG" + "T" * 5  # 10S + 5M + 2I + 5M
        rec = reads.parse_sam_line(
            f"r1\t0\t7\t100\t60\t10S5M2I5M\t*\t0\t0\t{seq}\t{'I' * len(seq)}")
        assert rec is not None
        assert rec["ref_end"] == 109
        assert reads.read_allele_at(rec, "7", 99) is None    # before span
        assert reads.read_allele_at(rec, "7", 100) == "A"    # seq[10]
        assert reads.read_allele_at(rec, "7", 104) == "A"    # last pre-indel M
        assert reads.read_allele_at(rec, "7", 105) == "T"    # after the 2I
        assert reads.read_allele_at(rec, "7", 110) is None   # beyond ref end
        assert reads.read_allele_at(rec, "12", 100) is None  # wrong contig

    def test_deletion_gap_returns_none(self):
        """Falsification: a ref position consumed by D has no query base;
        fails if the gap reports a phantom allele."""
        rec = reads.parse_sam_line(
            f"r1\t0\t7\t100\t60\t5M2D5M\t*\t0\t0\t{'A' * 10}\t{'I' * 10}")
        assert rec is not None
        assert reads.read_allele_at(rec, "7", 104) == "A"    # seq[4]
        assert reads.read_allele_at(rec, "7", 106) is None   # inside 2D
        assert reads.read_allele_at(rec, "7", 107) == "A"    # seq[5]

    def test_malformed_header_blank_skipped(self):
        """Falsification: header, blank, truncated and bad-FLAG lines must
        all parse to None; fails if junk enters the evidence stream."""
        assert reads.parse_sam_line("@HD\tVN:1.6\tSO:unsorted") is None
        assert reads.parse_sam_line("") is None
        assert reads.parse_sam_line("\n") is None
        assert reads.parse_sam_line("r1\t0\t7") is None
        assert reads.parse_sam_line(
            "r1\tx\t7\t100\t60\t10M\t*\t0\t0\tAAAAAAAAAA\tIIIIIIIIII"
        ) is None


class TestReadLevelPhase:
    """phase_from_reads over deterministic synth_sam fixtures."""

    def _run(self, tmp_path, case, **kw):
        sites, templates = case()
        sam = synth_sam.write_sam(tmp_path / "locus.sam", templates)
        with open(sam, encoding="utf-8") as fh:
            return sites, reads.phase_from_reads(fh, sites[0], sites[1],
                                                 **kw)

    def test_trans_case(self, tmp_path):
        """Falsification: fails if template merging, allele
        classification, or the 'zero alt@both' trans rule regresses -
        e.g. if the wrong-contig/unmapped decoys leaked into the counts
        or the mate disagreement were mishandled."""
        _, res = self._run(tmp_path, synth_sam.trans_case)
        assert res["relation"] == "trans"
        assert res["mechanism"] == "read_level"
        c = res["counts"]
        assert c["alt1_ref2"] == 7   # 5 clean + 1 mate-merge + 1 low-MAPQ
        assert c["ref1_alt2"] == 6
        assert c["alt_alt"] == 0     # the disqualifying class stays empty
        assert c["ref_ref"] == 0
        assert c["other"] == 1       # third-allele decoy
        assert c["partial"] == 1     # non-spanning decoy
        assert c["mate_disagreements"] == 1

    def test_cis_case(self, tmp_path):
        """Falsification: only alt@both + ref@both molecules exist;
        fails if trans-class templates were fabricated or the cis
        exclusivity check dropped."""
        _, res = self._run(tmp_path, synth_sam.cis_case)
        assert res["relation"] == "cis"
        c = res["counts"]
        assert c["alt_alt"] == 7
        assert c["ref_ref"] == 6
        assert c["alt1_ref2"] == 0
        assert c["ref1_alt2"] == 0
        assert c["other"] == 1
        assert c["partial"] == 1
        assert c["mate_disagreements"] == 1

    def test_long_range_unknown(self, tmp_path):
        """Falsification: sites beyond insert span produce zero spanning
        templates and the only honest call is 'unknown'; fails if phase
        is fabricated from non-spanning data."""
        _, res = self._run(tmp_path, synth_sam.long_range_case)
        assert res["relation"] == "unknown"
        assert res["mechanism"] == "read_level"
        assert res["counts"]["spanning"] == 0
        assert res["counts"]["partial"] == 10

    def test_min_support_enforced(self, tmp_path):
        """Falsification: a trans pattern below min_support must not call
        trans; fails if the support threshold is ignored."""
        _, res = self._run(tmp_path, synth_sam.trans_case,
                           min_support=99)
        assert res["relation"] == "unknown"


class TestEvidenceReport:
    """evidence_report agreement logic over both evidence lines."""

    def test_concordant(self):
        """Falsification: identical decisive calls must be concordant."""
        call = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("0|1", "PS1", pos=2000, ref="G", alt="C"))
        rep = reads.evidence_report(
            call, {"relation": "trans", "mechanism": "read_level",
                   "counts": {}})
        assert rep["agreement"] == "concordant"
        assert rep["consensus_relation"] == "trans"

    def test_discordant(self):
        """Falsification: vcf-trans vs reads-cis is a real conflict and
        must surface as discordant/conflict, never be silently resolved."""
        call = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("0|1", "PS1", pos=2000, ref="G", alt="C"))
        rep = reads.evidence_report(
            call, {"relation": "cis", "mechanism": "read_level",
                   "counts": {}})
        assert rep["agreement"] == "discordant"
        assert rep["consensus_relation"] == "conflict"

    def test_uninformative_and_vcf_only(self):
        """Falsification: unknown read evidence must not upgrade or
        downgrade the VCF call; fails if 'unknown' is counted as a vote."""
        call = phasing.determine_phase(
            _vf("1|0", "PS1", pos=1000),
            _vf("0|1", "PS1", pos=2000, ref="G", alt="C"))
        rep = reads.evidence_report(
            call, {"relation": "unknown", "mechanism": "read_level",
                   "counts": {}})
        assert rep["agreement"] == "vcf_only"
        assert rep["consensus_relation"] == "trans"


class TestEndToEndSpike:
    """Full chain on the synthetic spike-in proband (GATE 3 target)."""

    def test_spike_pair_in_trans(self, tmp_path):
        """Falsification: the true SPIKEA pair (7:1000000 A>T +
        7:1004000 G>C, PID=PS_SPIKE, pgt 1|0 x 0|1) must come out trans
        through VCF parse -> extract_facts -> eligibility -> comp-het
        enumeration -> determine_phase. Fails if pgt/pid are dropped
        during flattening or pair ordering flips the haplotype labels."""
        bundle = synth.spike_in_case(tmp_path / "spike_case")
        cfg = load_config()
        facts = []
        reader = VcfReader(bundle["vcf"])
        try:
            for rec in reader.records(sample="PROBAND01"):
                facts.extend(extract_facts(rec, "PROBAND01", cfg))
        finally:
            reader.close()
        cand = [f for f in facts if eligible(f, cfg)]
        hyps = enumerate_hypotheses(cand, cfg)

        spike = [h for h in hyps
                 if h.gene == "SPIKEA" and h.model == "compound_het"
                 and {v.key for v in h.variants}
                 == {("7", 1_000_000, "A", "T"),
                     ("7", 1_004_000, "G", "C")}]
        assert len(spike) == 1
        h = spike[0]
        assert h.in_trans == "trans"
        assert "PS_SPIKE" in h.phase_detail


class TestRunPhasingCli:
    """tools/run_phasing.py end-to-end."""

    def _write_vcf(self, tmp_path):
        return synth.write_vcf(
            tmp_path / "case.vcf",
            [synth.SVar("7", 1000, "A", "T", gt="0/1", pgt="1|0",
                        pid="PS1"),
             synth.SVar("7", 1120, "G", "C", gt="0/1", pgt="0|1",
                        pid="PS1")],
            contigs={"7": 1_000_000})

    def test_cli_vcf_only(self, tmp_path):
        """Falsification: without --sam the report must carry the VCF
        call only, honestly marked untested at read level. Fails if the
        CLI invents read evidence or drops the agreement field."""
        vcf = self._write_vcf(tmp_path)
        out = tmp_path / "out"
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "chr7:1000",  # chr-prefix norm
                               "--site2", "7:1120",
                               "--out", str(out)])
        assert rc == 0
        rep = json.loads((out / "phasing_report.json").read_text())
        assert rep["sites"][0]["chrom"] == "7"
        assert rep["vcf_phase"]["relation"] == "trans"
        assert rep["vcf_phase"]["mechanism"] == "pgt_pid_same_set"
        assert rep["read_phase"]["relation"] == "unknown"
        assert rep["agreement"] == "vcf_only"
        assert rep["consensus_relation"] == "trans"

    def test_cli_with_sam_concordant(self, tmp_path):
        """Falsification: PGT-trans + reads-trans must agree at
        'concordant'; fails if either evidence line is dropped or the
        agreement flag is mis-set."""
        sites, templates = synth_sam.trans_case()
        sam = synth_sam.write_sam(tmp_path / "locus.sam", templates)
        vcf = self._write_vcf(tmp_path)
        out = tmp_path / "out"
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:1120",
                               "--sam", str(sam), "--out", str(out)])
        assert rc == 0
        rep = json.loads((out / "phasing_report.json").read_text())
        assert rep["vcf_phase"]["relation"] == "trans"
        assert rep["read_phase"]["relation"] == "trans"
        assert rep["read_phase"]["counts"]["alt_alt"] == 0
        assert rep["agreement"] == "concordant"
        assert rep["consensus_relation"] == "trans"

    def test_cli_with_whatshap_concordant(self, tmp_path):
        """Falsification: a third, algorithmically independent evidence
        line (WhatsHap-style phased VCF) that agrees with PGT/PID must be
        surfaced and folded into 'concordant' - fails if the CLI ignores
        --whatshap-vcf or drops the evidence line from the report."""
        vcf = self._write_vcf(tmp_path)
        whatshap_vcf = synth.write_vcf(
            tmp_path / "whatshap.vcf",
            [synth.SVar("7", 1000, "A", "T", gt="0/1", pgt="1|0",
                        pid="WHPS1"),
             synth.SVar("7", 1120, "G", "C", gt="0/1", pgt="0|1",
                        pid="WHPS1")],
            contigs={"7": 1_000_000})
        out = tmp_path / "out"
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:1120",
                               "--whatshap-vcf", str(whatshap_vcf),
                               "--out", str(out)])
        assert rc == 0
        rep = json.loads((out / "phasing_report.json").read_text())
        assert rep["vcf_phase"]["relation"] == "trans"
        assert rep["whatshap_phase"]["relation"] == "trans"
        assert rep["agreement"] == "concordant"
        assert rep["consensus_relation"] == "trans"

    def test_cli_mito_mt_spelling_found(self, tmp_path):
        """Falsification: a VCF spelling the mito contig 'MT' must still
        be found when the operator passes --site chrM:pos (the scorer's
        chr-prefixed convention collapses both spellings to 'chrM') -
        fails if the lookup only tries the literal 'M' contig and drops
        mito sites with a spurious 'not in VCF' error."""
        vcf = synth.write_vcf(
            tmp_path / "mito.vcf",
            [synth.SVar("MT", 500, "A", "T", gt="0/1", pgt="1|0",
                        pid="PSM"),
             synth.SVar("MT", 600, "G", "C", gt="0/1", pgt="0|1",
                        pid="PSM")],
            contigs={"MT": 16_569})
        out = tmp_path / "out"
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "chrM:500", "--site2", "chrM:600",
                               "--out", str(out)])
        assert rc == 0
        rep = json.loads((out / "phasing_report.json").read_text())
        assert rep["vcf_phase"]["relation"] == "trans"

    def test_cli_bam_requires_sam_export(self, tmp_path, capsys):
        """Falsification: --bam must never be silently accepted - the
        tool exits non-zero with the samtools export instruction; fails
        if someone wires in a BAM path without SAM conversion."""
        vcf = self._write_vcf(tmp_path)
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:1120",
                               "--bam", "region.bam",
                               "--ref", "ref.fa",
                               "--out", str(tmp_path / "out")])
        assert rc == 2
        assert "samtools view -O SAM" in capsys.readouterr().err


    def test_missing_site_rc2(self, tmp_path, capsys):
        """Falsification: a --site absent from the VCF must exit 2 with
        'not in VCF', not silently produce a report."""
        vcf = self._write_vcf(tmp_path)
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:9999",
                               "--out", str(tmp_path / "out")])
        assert rc == 2
        assert "not in VCF" in capsys.readouterr().err

    def test_same_site_rc2(self, tmp_path, capsys):
        """Falsification: --site1 == --site2 must exit 2, not 'phase' a
        variant against itself."""
        vcf = self._write_vcf(tmp_path)
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:1000",
                               "--out", str(tmp_path / "out")])
        assert rc == 2
        assert "same position" in capsys.readouterr().err

    def test_min_support_zero_rejected(self, tmp_path):
        """Falsification: --min-support 0 lets an empty SAM 'prove' trans
        (0 >= 0 for both trans classes) - must raise, not call."""
        sites, templates = synth_sam.trans_case()
        sam = synth_sam.write_sam(tmp_path / "locus.sam", templates)
        vcf = self._write_vcf(tmp_path)
        rc = run_phasing.main(["--vcf", str(vcf),
                               "--site1", "7:1000", "--site2", "7:1120",
                               "--sam", str(sam), "--min-support", "0",
                               "--out", str(tmp_path / "out")])
        assert rc != 0
