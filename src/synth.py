"""Synthetic data generator - the stand-in corpus for all pre-access work.

The patient VCF/docx are gated; per plan.md section 7 the entire harness is
built and validated on synthetic stand-ins so dataset approval unblocks only
the final rerun. Every fixture here is firewall-clean (section 2.1.5): no
coordinates, gene names, or values from any leaked/public-inferable source.

THE ANNOTATION CONTRACT
-----------------------
``CSQ_FIELDS`` defines the VEP-CSQ INFO layout the funnel reads. It mirrors a
VEP 116 + gnomAD + dbNSFP-5.3.1 annotation run (field names follow VEP/dbNSFP
convention). ``src/vcf.py`` parses the field list from the header's
``Format:`` declaration, so a real VEP run with a different field set still
works - but tests and the funnel resolve these names:

    Allele, Consequence, IMPACT, SYMBOL, Gene, Feature, Feature_type, BIOTYPE,
    EXON, INTRON, HGVSc, HGVSp, Protein_position, Amino_acids, Codons,
    Existing_variation, DISTANCE, STRAND,
    gnomADe_AF + 10 subpop AFs, gnomADg_AF + 10 subpop AFs,
    CLIN_SIG, SIFT, PolyPhen, CADD_PHRED, REVEL,
    AlphaMissense_score, AlphaMissense_class,
    SpliceAI_pred_DS_{AG,AL,DG,DL}, LOEUF, phyloP

FORMAT columns emitted: GT:AD:DP:GQ:PGT:PID (PGT/PID = Sentieon/GATK
read-backed phasing fields consumed by src/phasing.py).
"""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

CSQ_FIELDS = [
    "Allele", "Consequence", "IMPACT", "SYMBOL", "Gene", "Feature",
    "Feature_type", "BIOTYPE", "EXON", "INTRON", "HGVSc", "HGVSp",
    "Protein_position", "Amino_acids", "Codons", "Existing_variation",
    "DISTANCE", "STRAND",
    "gnomADe_AF", "gnomADe_AFR_AF", "gnomADe_AMR_AF", "gnomADe_ASJ_AF",
    "gnomADe_EAS_AF", "gnomADe_FIN_AF", "gnomADe_MID_AF", "gnomADe_NFE_AF",
    "gnomADe_SAS_AF", "gnomADe_OTH_AF",
    "gnomADg_AF", "gnomADg_AFR_AF", "gnomADg_AMR_AF", "gnomADg_ASJ_AF",
    "gnomADg_EAS_AF", "gnomADg_FIN_AF", "gnomADg_MID_AF", "gnomADg_NFE_AF",
    "gnomADg_SAS_AF", "gnomADg_OTH_AF",
    "CLIN_SIG", "SIFT", "PolyPhen", "CADD_PHRED", "REVEL",
    "AlphaMissense_score", "AlphaMissense_class",
    "SpliceAI_pred_DS_AG", "SpliceAI_pred_DS_AL",
    "SpliceAI_pred_DS_DG", "SpliceAI_pred_DS_DL",
    "LOEUF", "phyloP",
]
CSQ_FORMAT = "|".join(CSQ_FIELDS)

CONTIGS = {"1": 249_250_621, "7": 159_345_973, "12": 133_275_309,
           "15": 101_991_189, "X": 156_040_895}


@dataclass
class Ann:
    """One CSQ annotation; only named fields are set, rest emit ''."""
    allele: str = ""
    consequence: str = "intergenic_variant"
    impact: str = "MODIFIER"
    symbol: str = ""
    gene: str = ""
    feature: str = "ENST00000000001"
    biotype: str = "protein_coding"
    extra: dict = field(default_factory=dict)

    _KEY = {
        "allele": "Allele", "consequence": "Consequence", "impact": "IMPACT",
        "symbol": "SYMBOL", "gene": "Gene", "feature": "Feature",
        "feature_type": "Feature_type", "biotype": "BIOTYPE",
        "exon": "EXON", "intron": "INTRON", "hgvsc": "HGVSc",
        "hgvsp": "HGVSp", "protein_position": "Protein_position",
        "amino_acids": "Amino_acids", "codons": "Codons",
        "existing_variation": "Existing_variation", "distance": "DISTANCE",
        "strand": "STRAND",
    }

    def to_csq(self) -> str:
        vals = {k: "" for k in CSQ_FIELDS}
        for attr, csq_name in self._KEY.items():
            v = getattr(self, attr, "")
            if v:
                vals[csq_name] = str(v)
        vals["Feature_type"] = "Transcript"
        unknown = [k for k in self.extra if k not in vals]
        if unknown:
            raise ValueError(
                f"Ann.extra keys not in CSQ_FIELDS: {unknown} - a typo'd "
                "field name would silently emit empty annotation")
        for k, v in self.extra.items():
            if v is not None:
                vals[k] = str(v)
        return "|".join(vals[k] for k in CSQ_FIELDS)


@dataclass
class SVar:
    """A synthetic variant with genotype and annotations."""
    chrom: str
    pos: int
    ref: str
    alt: str
    vid: str = "."
    qual: float = 60.0
    filters: tuple = ("PASS",)
    gt: str = "0/1"
    ad: tuple = (22, 23)
    dp: int = 45
    gq: int = 99
    pgt: str | None = None
    pid: str | None = None
    anns: list = field(default_factory=list)
    info_extra: dict = field(default_factory=dict)

    def vcf_line(self, sample: str) -> str:
        info = dict(self.info_extra)
        if self.anns:
            info["CSQ"] = ",".join(a.to_csq() for a in self.anns)
        info_s = ";".join(f"{k}={v}" for k, v in info.items()) or "."
        filt = ";".join(self.filters) if self.filters else "."
        fmt = "GT:AD:DP:GQ:PGT:PID"
        sval = ":".join([
            self.gt, ",".join(str(x) for x in self.ad), str(self.dp),
            str(self.gq), self.pgt or ".", self.pid or ".",
        ])
        return "\t".join([self.chrom, str(self.pos), self.vid, self.ref,
                          self.alt, f"{self.qual:.1f}", filt, info_s,
                          fmt, sval])


def write_vcf(path, variants, contigs=None, samples=("PROBAND01",),
              source="synth-v1") -> Path:
    """Write a VCF (bare contigs like the challenge file, CSQ header included)."""
    p = Path(path)
    contigs = contigs or CONTIGS
    lines = [
        "##fileformat=VCFv4.2",
        f"##source={source}",
        "##reference=GRCh38_no_alt_analysis_set",
        '##INFO=<ID=CSQ,Number=.,Type=String,Description="Consequence '
        f'annotations. Format: {CSQ_FORMAT}">',
        '##INFO=<ID=AF,Number=A,Type=Float,Description="Allele fraction '
        '(within-sample, AN=2)">',
        '##FORMAT=<ID=GT,Number=1,Type=String,Description="Genotype">',
        '##FORMAT=<ID=AD,Number=R,Type=Integer,Description="Allelic depths">',
        '##FORMAT=<ID=DP,Number=1,Type=Integer,Description="Read depth">',
        '##FORMAT=<ID=GQ,Number=1,Type=Integer,Description="Genotype quality">',
        '##FORMAT=<ID=PGT,Number=1,Type=String,Description="Physical phasing '
        'genotype">',
        '##FORMAT=<ID=PID,Number=1,Type=String,Description="Physical phasing '
        'ID">',
    ]
    lines += [f"##contig=<ID={c},length={l}>" for c, l in contigs.items()]
    lines.append("#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t"
                 + "\t".join(samples))
    for v in sorted(variants, key=lambda x: (x.chrom, x.pos)):
        lines.append(v.vcf_line(samples[0]))
    p.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="")
    return p


# ---------------------------------------------------------------------------
# Tiny ontology / annotation corpus builders
# ---------------------------------------------------------------------------

OBO_TERMS = [
    ("HP:0000001", "All", []),
    ("HP:0000118", "Phenotypic abnormality", ["HP:0000001"]),
    ("HP:0001000", "Abnormality of chromosome stability", ["HP:0000118"]),
    ("HP:0001001", "Aneuploidy", ["HP:0001000"]),
    ("HP:0001002", "Growth delay", ["HP:0000118"]),
    ("HP:0001003", "Microcephaly", ["HP:0000118"]),
    ("HP:0001004", "Prematurely aged appearance", ["HP:0000118"]),
    ("HP:0002000", "Abnormality of the cardiovascular system", ["HP:0000118"]),
    ("HP:0002001", "Arrhythmia", ["HP:0002000"]),
    ("HP:0003000", "Abnormality of the eye", ["HP:0000118"]),
    ("HP:0003001", "Retinal dystrophy", ["HP:0003000"]),
]

PROBAND_HPO = ["HP:0001001", "HP:0001002", "HP:0001003", "HP:0001004"]
CONTROL_HPO = ["HP:0001001", "HP:0001003"]  # MVA-like set for negative control


def write_obo(path, terms=None) -> Path:
    terms = terms or OBO_TERMS
    chunks = ["format-version: 1.2\n"]
    for tid, name, parents in terms:
        body = f"[Term]\nid: {tid}\nname: {name}\n"
        body += "".join(f"is_a: {p} ! parent\n" for p in parents)
        chunks.append(body)
    Path(path).write_text("\n".join(chunks), encoding="utf-8")
    return Path(path)


def write_hpoa(path, rows=None) -> Path:
    """rows: {disease_id: (disease_name, [hpo_ids])}"""
    if rows is None:
        rows = {
            "OMIM:999999": ("Synthetic spike syndrome", PROBAND_HPO),
            "OMIM:188840": ("Synthetic cardiomyopathy", ["HP:0002001"]),
            "OMIM:300300": ("Synthetic retinopathy", ["HP:0003001"]),
        }
    p = Path(path)
    lines = ["#description: synthetic annotation corpus for tests\n"]
    for did, (name, hpos) in rows.items():
        for h in hpos:
            lines.append(f"{did}\t{name}\t\t{h}\t\t\t\t\t\t\t\t\t\t\n")
    p.write_text("".join(lines), encoding="utf-8")
    return p


def write_gene2disease(path, mapping=None) -> Path:
    if mapping is None:
        mapping = {"SPIKEA": ["OMIM:999999"], "CARDG": ["OMIM:188840"],
                   "EYEG": ["OMIM:300300"]}
    Path(path).write_text(json.dumps(mapping, indent=1), encoding="utf-8")
    return Path(path)


def write_docx(path, paragraphs) -> Path:
    """Minimal valid .docx (zip with word/document.xml)."""
    body = "".join(
        "<w:p><w:r><w:t>" + t + "</w:t></w:r></w:p>" for t in paragraphs)
    document = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/'
        'wordprocessingml/2006/main"><w:body>' + body + "</w:body></w:document>")
    p = Path(path)
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml",
                   '<?xml version="1.0"?><Types xmlns="http://schemas.'
                   'openxmlformats.org/package/2006/content-types">'
                   '<Default Extension="xml" ContentType="application/xml"/>'
                   '<Default Extension="rels" ContentType="application/'
                   'vnd.openxmlformats-package.relationships+xml"/>'
                   '<Override PartName="/word/document.xml" ContentType='
                   '"application/vnd.openxmlformats-officedocument.'
                   'wordprocessingml.document.main+xml"/></Types>')
        z.writestr("_rels/.rels",
                   '<?xml version="1.0"?><Relationships xmlns="http://'
                   'schemas.openxmlformats.org/package/2006/relationships">'
                   '<Relationship Id="rId1" Type="http://schemas.openxml'
                   'formats.org/officeDocument/2006/relationships/'
                   'officeDocument" Target="word/document.xml"/>'
                   "</Relationships>")
        z.writestr("word/document.xml", document)
    return p


# ---------------------------------------------------------------------------
# Case builders: spike-in proband and negative control
# ---------------------------------------------------------------------------

def _af_ann(gnomade=None, gnomadg=None):
    """gnomAD AF dict; None values stay empty (absent from gnomAD)."""
    d = {}
    for grp, val in (("gnomADe", gnomade), ("gnomADg", gnomadg)):
        if val is not None:
            d[f"{grp}_AF"] = val
            for pop in ("AFR", "AMR", "ASJ", "EAS", "FIN", "MID", "NFE",
                        "SAS", "OTH"):
                d[f"{grp}_{pop}_AF"] = val
    return d


def spike_variants():
    """The synthetic proband: a true compound-het pair plus adversarial decoys.

    Truth (returned by spike_in_case): SPIKEA compound-het on chrom 7 -
    stop_gained (PGT 1|0) + damaging missense (PGT 0|1), same phase set
    PS_SPIKE chained through an intervening common het -> in trans.
    """
    variants = [
        # ---- TRUE PAIR: SPIKEA, in trans via PID=PS_SPIKE ----
        SVar("7", 1_000_000, "A", "T", gt="0/1", pgt="1|0", pid="PS_SPIKE",
             anns=[Ann("T", "stop_gained", "HIGH", "SPIKEA", "ENSG0SPIKE",
                       extra={**_af_ann(), "CADD_PHRED": 41, "REVEL": "",
                              "SIFT": "", "PolyPhen": "",
                              "LOEUF": 0.31, "phyloP": 7.5})]),
        SVar("7", 1_004_000, "G", "C", gt="0/1", pgt="0|1", pid="PS_SPIKE",
             anns=[Ann("C", "missense_variant", "MODERATE", "SPIKEA",
                       "ENSG0SPIKE",
                       extra={**_af_ann(), "CADD_PHRED": 32, "REVEL": 0.91,
                              "AlphaMissense_score": 0.93,
                              "AlphaMissense_class": "likely_pathogenic",
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging",
                              "LOEUF": 0.31, "phyloP": 6.2})]),
        # intervening common het in the same phase block (LD chain element)
        SVar("7", 1_002_000, "C", "G", gt="0/1", pgt="0|1", pid="PS_SPIKE",
             anns=[Ann("G", "synonymous_variant", "LOW", "SPIKEA",
                       "ENSG0SPIKE", extra=_af_ann(0.31, 0.29))]),
        # ---- DECOYS ----
        # common hom-alt synonymous: fails rarity
        SVar("12", 5_000_000, "T", "C", gt="1/1", ad=(2, 40),
             anns=[Ann("C", "synonymous_variant", "LOW", "CARDG",
                       "ENSG0CARDG", extra=_af_ann(0.42, 0.38))]),
        # TTN noise-gene pair: two eligible rare damaging hets -> comp-het
        # candidate that MUST be suppressed by phenotype scoring
        SVar("12", 6_000_000, "G", "A", gt="0/1", pgt="1|0", pid="PS_TTN",
             anns=[Ann("A", "stop_gained", "HIGH", "TTN", "ENSG0TTN",
                       extra={**_af_ann(), "CADD_PHRED": 39})]),
        SVar("12", 6_050_000, "C", "T", gt="0/1", pgt="0|1", pid="PS_TTN",
             anns=[Ann("T", "missense_variant", "MODERATE", "TTN",
                       "ENSG0TTN",
                       extra={**_af_ann(), "CADD_PHRED": 33, "REVEL": 0.88,
                              "AlphaMissense_score": 0.9,
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging"})]),
        # rare missense with NO damaging votes: survives rarity, not damage
        SVar("1", 3_000_000, "A", "G", gt="0/1",
             anns=[Ann("G", "missense_variant", "MODERATE", "EYEG",
                       "ENSG0EYEG",
                       extra={**_af_ann(5e-6), "CADD_PHRED": 12,
                              "REVEL": 0.21, "AlphaMissense_score": 0.2,
                              "SIFT": "tolerated", "PolyPhen": "benign"})]),
        # non-PASS LoF: dropped at filter stage
        SVar("1", 3_500_000, "G", "T", gt="0/1", filters=("LowQual",),
             anns=[Ann("T", "stop_gained", "HIGH", "SPIKEB", "ENSG0SPKB",
                       extra=_af_ann())]),
        # low-DP het damaging: dropped at genotype QC
        SVar("1", 4_000_000, "C", "A", gt="0/1", ad=(3, 1), dp=4, gq=12,
             anns=[Ann("A", "missense_variant", "MODERATE", "EYEG",
                       "ENSG0EYEG",
                       extra={**_af_ann(), "CADD_PHRED": 30, "REVEL": 0.9,
                              "AlphaMissense_score": 0.9,
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging"})]),
        # common AF damaging missense: dropped at rarity stage
        SVar("12", 7_000_000, "T", "G", gt="0/1",
             anns=[Ann("G", "missense_variant", "MODERATE", "CARDG",
                       "ENSG0CARDG",
                       extra={**_af_ann(0.012), "CADD_PHRED": 31,
                              "REVEL": 0.85, "AlphaMissense_score": 0.8,
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging"})]),
        # chrX hemizygous-looking het: exercises x_linked model
        SVar("X", 10_000_000, "G", "A", gt="0/1",
             anns=[Ann("A", "missense_variant", "MODERATE", "XGENE",
                       "ENSG0XGENE",
                       extra={**_af_ann(), "CADD_PHRED": 29, "REVEL": 0.7,
                              "AlphaMissense_score": 0.8,
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging"})]),
        # hom-alt rare LoF: hom_alt hypothesis competitor
        SVar("12", 8_000_000, "A", "T", gt="1/1", ad=(0, 42),
             anns=[Ann("T", "stop_gained", "HIGH", "HOMG", "ENSG0HOMG",
                       extra={**_af_ann(8e-6), "CADD_PHRED": 38,
                              "LOEUF": 0.9})]),
        # lone splice-region het (SpliceAI 0.6): no partner in gene -> no pair
        SVar("1", 5_500_000, "C", "T", gt="0/1",
             anns=[Ann("T", "splice_region_variant", "LOW", "SPLICG",
                       "ENSG0SPLC",
                       extra={**_af_ann(), "CADD_PHRED": 22,
                              "SpliceAI_pred_DS_AG": 0.6})]),
        # deep-intronic with weak SpliceAI: 'other' tier, no partner
        SVar("1", 5_800_000, "A", "G", gt="0/1",
             anns=[Ann("G", "intron_variant", "MODIFIER", "SPLICG",
                       "ENSG0SPLC",
                       extra={**_af_ann(), "SpliceAI_pred_DS_DG": 0.15})]),
    ]
    return variants


def control_variants():
    """Negative control: no plausible causal pair. Contains the worst-case
    adversary - two rare damaging TTN hets forming a comp-het - that must be
    suppressed below the emit floor by zero phenotype support."""
    return [
        SVar("7", 2_000_000, "G", "A", gt="0/1",
             anns=[Ann("A", "synonymous_variant", "LOW", "CARDG",
                       "ENSG0CARDG", extra=_af_ann(0.3, 0.28))]),
        SVar("12", 6_000_000, "G", "A", gt="0/1",
             anns=[Ann("A", "stop_gained", "HIGH", "TTN", "ENSG0TTN",
                       extra={**_af_ann(2e-5), "CADD_PHRED": 39})]),
        SVar("12", 6_050_000, "C", "T", gt="0/1",
             anns=[Ann("T", "missense_variant", "MODERATE", "TTN",
                       "ENSG0TTN",
                       extra={**_af_ann(2e-5), "CADD_PHRED": 33,
                              "REVEL": 0.88, "AlphaMissense_score": 0.9,
                              "SIFT": "deleterious",
                              "PolyPhen": "probably_damaging"})]),
        SVar("1", 9_000_000, "T", "C", gt="0/1",
             anns=[Ann("C", "missense_variant", "MODERATE", "EYEG",
                       "ENSG0EYEG",
                       extra={**_af_ann(1e-4), "CADD_PHRED": 26,
                              "REVEL": 0.6, "AlphaMissense_score": 0.7})]),
    ]


def spike_in_case(dir_path):
    """Build the full external-validation bundle in ``dir_path``.

    Returns dict with paths + truth. Falsification target (GATE 2): Arm B
    must recover the SPIKEA pair at rank <= 3.
    """
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)
    vcf = write_vcf(d / "spike_proband.vcf", spike_variants())
    obo = write_obo(d / "hp.obo")
    hpoa = write_hpoa(d / "phenotype.hpoa")
    g2d = write_gene2disease(d / "genes_to_disease.json")
    hpo = {"proband_id": "PROBAND01", "hpo_terms": PROBAND_HPO,
           "source": "synthetic"}
    (d / "hpo_terms.json").write_text(json.dumps(hpo, indent=1))
    truth = {
        "gene": "SPIKEA",
        "model": "compound_het",
        "pair": [{"chrom": "chr7", "pos": 1_000_000, "ref": "A", "alt": "T"},
                 {"chrom": "chr7", "pos": 1_004_000, "ref": "G", "alt": "C"}],
        "phase_set": "PS_SPIKE",
        "in_trans": True,
        "hpo_terms": PROBAND_HPO,
    }
    (d / "truth.json").write_text(json.dumps(truth, indent=1))
    return {"vcf": vcf, "obo": obo, "hpoa": hpoa, "gene2disease": g2d,
            "hpo": d / "hpo_terms.json", "truth": truth, "dir": d}


def control_case(dir_path):
    """Negative-control bundle: plausible-looking noise, no causal pair."""
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)
    vcf = write_vcf(d / "control_proband.vcf", control_variants())
    obo = write_obo(d / "hp.obo")
    hpoa = write_hpoa(d / "phenotype.hpoa")
    g2d = write_gene2disease(d / "genes_to_disease.json")
    hpo = {"proband_id": "PROBAND01", "hpo_terms": CONTROL_HPO,
           "source": "synthetic"}
    (d / "hpo_terms.json").write_text(json.dumps(hpo, indent=1))
    return {"vcf": vcf, "obo": obo, "hpoa": hpoa, "gene2disease": g2d,
            "hpo": d / "hpo_terms.json", "dir": d}
