"""VCF-level QC / EDA - pure-Python replacement for ``bcftools stats``.

plan.md Phase 1 ("Data audit / EDA - judge the data before trusting it")
requires caller-agnostic VCF forensics: Ti/Tv sanity (~2.0 for human WGS),
SNV/indel split, PASS/FILTER histogram, per-contig counts, QUAL distribution,
het/hom balance, dbSNP ID presence and multiallelic rate - plus header checks
aimed at the three documented hazards of the challenge VCF (deep dive sec.2,
participant-reported):

* bare contigs with no ``chr`` prefix - a silent-empty tabix trap;
* Sentieon caller with PGT/PID physical-phasing FORMAT fields;
* INFO ``AF`` = within-sample allele fraction (AN=2), NOT population frequency.

bcftools is not guaranteed on this Windows dev box, so every stat the Gate-1
battery needs is reimplemented here in streaming pure Python on top of
``src.vcf.VcfReader`` (a ~5M-variant VCF never loads fully into RAM - only
per-contig counters and a QUAL value-count histogram are kept). All functions
return plain JSON-able dicts so results land verbatim in ``results/eda/`` and
``tests/test_data_integrity.py`` consumes them unchanged - on synthetic
stand-ins now, on the patient VCF (``MVA_REAL_VCF``) later, per the plan.md
sec.7 risk-mitigation row on delayed dataset access.
"""
from __future__ import annotations

import re

from .vcf import VcfReader

#: Transition substitutions: purine<->purine (A<->G), pyrimidine<->pyrimidine
#: (C<->T). Every other single-base substitution is a transversion.
TRANSITION_PAIRS = frozenset(
    [("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")])
_DNA = frozenset("ACGT")

#: chrX het-rate decision bounds for :func:`sex_check` (frozen, documented):
#: a genetic male is hemizygous on chrX outside the PAR regions, so a diploid
#: caller emits almost no true chrX hets (a few PAR calls plus miscalls); a
#: female chrX looks autosomal (het rate ~0.5+). Between the bounds we
#: report ``ambiguous`` rather than guess.
MALE_X_HET_MAX = 0.05
FEMALE_X_HET_MIN = 0.15

_CALLER_RE = re.compile(
    r"sentieon|haplotypecaller|gatk|deepvariant|strelka|dragen|freebayes|"
    r"bcftools|mutect|octopus",
    re.IGNORECASE)


def _zero_contig() -> dict:
    return {"n_records": 0, "n_pass": 0, "n_filtered": 0, "het": 0,
            "hom_alt": 0, "hom_ref": 0, "haploid": 0, "no_call": 0}


def _contig_key(name: str):
    """Natural contig ordering: 1..N numeric first, then X/Y/M/others,
    ``chr``-prefix-insensitive. Deterministic for JSON output."""
    s = name[3:] if name.lower().startswith("chr") else name
    return (0, int(s)) if s.isdigit() else (1, s)


def _median_from_counts(counts: dict) -> float | None:
    """Exact median of a {value: count} histogram; None if empty."""
    n = sum(counts.values())
    if n == 0:
        return None
    t1, t2 = (n - 1) // 2, n // 2  # 0-based order stats (equal when n odd)
    got: list = []
    cum = 0
    for value, k in sorted(counts.items()):
        prev, cum = cum, cum + k
        for t in (t1, t2):
            if prev <= t < cum:
                got.append(value)
    return (got[0] + got[1]) / 2.0


def compute_stats(vcf_path, sample: str | None = None) -> dict:
    """Stream ``vcf_path`` once and return the Gate-1 stat bundle (JSON-able).

    Counting rules (frozen so tests can falsify them):

    * record classes - ``n_snv``: ``len(ref)==1 and all(len(alt)==1)``;
      ``n_indel``: everything else (matches ``VcfRecord.is_snv/is_indel``,
      so ``n_snv + n_indel == n_records`` always).
    * Ti/Tv - counted per ALT allele over single-base A/C/G/T substitutions:
      a multiallelic site contributes one event per SNV-like alt; alleles
      that shift length or leave A/C/G/T contribute none. ``titv`` is None
      when no transversions were seen.
    * ``filter_histogram`` - one ``PASS`` count per passing record and one
      count per FILTER token per failing record, so a record failing two
      filters increments both (histogram totals can exceed ``n_filtered``).
    * genotypes - for ``sample`` (default: first column sample), per-record
      buckets: het / hom_alt / hom_ref / haploid (called GT with one allele,
      e.g. male chrX emit-style "1") / no_call. Same buckets per contig to
      feed :func:`sex_check`.
    """
    reader = VcfReader(vcf_path)
    if sample is None:
        sample = reader.samples[0] if reader.samples else None

    n_records = n_snv = n_indel = n_multi = n_rsid = 0
    n_pass = n_filtered = 0
    ti = tv = 0
    filt_hist: dict[str, int] = {}
    per_contig: dict[str, dict] = {}
    geno = {"het": 0, "hom_alt": 0, "hom_ref": 0, "haploid": 0, "no_call": 0}
    n_phased = 0
    qual_counts: dict[float, int] = {}
    n_qual_missing = 0
    qsum = 0.0

    try:
        for rec in reader.records(sample=sample):
            n_records += 1
            if rec.is_snv():
                n_snv += 1
            else:
                n_indel += 1
            if len(rec.alts) > 1:
                n_multi += 1
            if rec.vid not in (".", ""):
                n_rsid += 1
            if rec.passed:
                n_pass += 1
                filt_hist["PASS"] = filt_hist.get("PASS", 0) + 1
            else:
                n_filtered += 1
                for f in rec.filters:
                    filt_hist[f] = filt_hist.get(f, 0) + 1

            pc = per_contig.setdefault(rec.chrom, _zero_contig())
            pc["n_records"] += 1
            pc["n_pass" if rec.passed else "n_filtered"] += 1

            r = rec.ref.upper()
            if len(r) == 1 and r in _DNA:
                for a in rec.alts:
                    a = a.upper()
                    if len(a) == 1 and a in _DNA:
                        if (r, a) in TRANSITION_PAIRS:
                            ti += 1
                        else:
                            tv += 1

            if rec.qual is None:
                n_qual_missing += 1
            else:
                qual_counts[rec.qual] = qual_counts.get(rec.qual, 0) + 1
                qsum += rec.qual

            sg = rec.samples.get(sample) if sample else None
            if sg is None or not sg.called:
                geno["no_call"] += 1
                pc["no_call"] += 1
            else:
                if len(sg.gt) == 1:
                    geno["haploid"] += 1
                    pc["haploid"] += 1
                elif sg.is_het:
                    geno["het"] += 1
                    pc["het"] += 1
                elif sg.is_hom_alt:
                    geno["hom_alt"] += 1
                    pc["hom_alt"] += 1
                else:
                    geno["hom_ref"] += 1
                    pc["hom_ref"] += 1
                if sg.phased or sg.pgt:
                    n_phased += 1
    finally:
        reader.close()

    n_qual = n_records - n_qual_missing
    quals = sorted(qual_counts)
    return {
        "vcf": str(vcf_path),
        "sample": sample,
        "n_records": n_records,
        "n_snv": n_snv,
        "n_indel": n_indel,
        "n_multiallelic": n_multi,
        "n_with_rsid": n_rsid,
        "n_pass": n_pass,
        "n_filtered": n_filtered,
        "transitions": ti,
        "transversions": tv,
        "titv": (ti / tv) if tv else None,
        "filter_histogram": dict(sorted(filt_hist.items())),
        "per_contig": {c: per_contig[c]
                       for c in sorted(per_contig, key=_contig_key)},
        "qual": {
            "n": n_qual,
            "n_missing": n_qual_missing,
            "min": quals[0] if quals else None,
            "max": quals[-1] if quals else None,
            "mean": (qsum / n_qual) if n_qual else None,
            "median": _median_from_counts(qual_counts),
        },
        "genotypes": geno,
        "n_phased_gt": n_phased,
    }


def _af_interpretation(defn: str | None) -> str:
    """Heuristic read of an INFO-AF definition line.

    The challenge VCF's INFO ``AF`` is documented (participant-reported,
    deep dive sec.2) as the within-sample allele fraction (AN=2); the trap
    is treating it as a population frequency. Only explicit wording moves
    the needle - a bare "Allele Frequency" description stays ``ambiguous``
    because GATK uses that phrasing for within-sample AF as well.
    """
    if not defn:
        return "absent"
    d = defn.lower()
    if ("within-sample" in d or "an=2" in d or "allele fraction" in d
            or "fraction of reads" in d):
        return "within_sample_fraction"
    if "population" in d or "gnomad" in d or "1000g" in d or "1kg" in d:
        return "population_frequency_suspect"
    return "ambiguous"


def header_forensics(vcf_path) -> dict:
    """Header-only audit of the challenge-specific hazards (JSON-able).

    Returns fileformat, per-contig names/lengths with ``chr``-prefix flags,
    PGT/PID presence in FORMAT defs, CSQ INFO presence + parsed field count,
    the raw ``##source``/caller lines, the ``##reference`` line, the INFO
    ``AF`` definition text plus a within-sample-vs-population heuristic,
    declared FILTER/INFO/FORMAT IDs, and the sample names. These are the
    checks plan.md Phase 1 lists under "VCF header forensics - confirm,
    don't assume".
    """
    reader = VcfReader(vcf_path)
    try:
        meta = reader.meta
        fileformat = next(
            (m.split("=", 1)[1] for m in meta
             if m.startswith("##fileformat=")), None)
        contigs = [
            {"name": name, "length": length,
             "chr_prefix": name.lower().startswith("chr")}
            for name, length in reader.contigs.items()
        ]
        any_chr = any(c["chr_prefix"] for c in contigs)
        af_def = reader.info_defs.get("AF")
        return {
            "vcf": str(vcf_path),
            "fileformat": fileformat,
            "contigs": contigs,
            "chr_prefix": {
                "any": any_chr,
                "all": bool(contigs)
                and all(c["chr_prefix"] for c in contigs),
                "none": not any_chr,
            },
            "format_fields": {
                "PGT": "PGT" in reader.format_defs,
                "PID": "PID" in reader.format_defs,
            },
            "format_ids": sorted(reader.format_defs),
            "filter_ids": sorted(reader.filter_defs),
            "info_ids": sorted(reader.info_defs),
            "csq": {
                "present": "CSQ" in reader.info_defs,
                "n_fields": len(reader.csq_fields),
                "fields": list(reader.csq_fields),
            },
            "source": [m for m in meta if m.startswith("##source")],
            "caller_lines": [m for m in meta if _CALLER_RE.search(m)],
            "reference": next(
                (m for m in meta if m.startswith("##reference")), None),
            "af_info_definition": af_def,
            "af_interpretation": _af_interpretation(af_def),
            "samples": list(reader.samples),
        }
    finally:
        reader.close()


def sex_check(stats_or_per_contig, male_max: float = MALE_X_HET_MAX,
              female_min: float = FEMALE_X_HET_MIN) -> dict:
    """Sex-consistency signal from chrX het rate + chrY call counts.

    Accepts either the dict returned by :func:`compute_stats` (its
    ``per_contig`` table is used) or a bare ``{contig: counts}`` map where
    each count block carries at least ``het`` and ``hom_alt`` (``hom``
    accepted as an alias; ``called`` may supply the denominator directly).
    Contig names may be ``X``/``chrX`` or ``Y``/``chrY``.

    Decision rule (frozen, documented): ``x_het_rate`` = chrX het calls /
    all called chrX genotypes (het + hom_alt + hom_ref + haploid). Below
    ``male_max`` the pattern is consistent with a hemizygous male chrX;
    above ``female_min`` with a diploid female chrX; between the bounds -
    or when no chrX calls exist - the answer is ``ambiguous`` rather than
    a guess. A sample-swap check is only worth something when it can say
    "insufficient data".
    """
    pc = (stats_or_per_contig.get("per_contig", stats_or_per_contig)
          if isinstance(stats_or_per_contig, dict) else {})

    def _find(target: str) -> dict:
        for name, counts in pc.items():
            n = name[3:] if isinstance(name, str) \
                and name.lower().startswith("chr") else name
            if n == target and isinstance(counts, dict):
                return counts
        return {}

    def _called(c: dict) -> int:
        if "called" in c:
            return int(c["called"])
        return int(c.get("het", 0)) + int(c.get("hom_alt", c.get("hom", 0))) \
            + int(c.get("hom_ref", 0)) + int(c.get("haploid", 0))

    x = _find("X")
    y = _find("Y")
    x_het = int(x.get("het", 0)) if x else 0
    x_called = _called(x) if x else 0
    n_y = _called(y) if y else 0
    rate = (x_het / x_called) if x_called else None

    notes: list[str] = []
    if not x or x_called == 0:
        inferred = "ambiguous"
        notes.append(
            "no chrX records/called genotypes - cannot assess sex consistency")
    elif rate < male_max:  # type: ignore[operator]
        inferred = "male"
        if n_y == 0:
            notes.append(
                "chrX looks hemizygous but chrY has zero calls - confirm Y "
                "is in the call set before trusting 'male'")
    elif rate > female_min:  # type: ignore[operator]
        inferred = "female"
        if n_y:
            notes.append(
                "chrY calls present alongside a female-like chrX - check "
                "for contamination or a mosaic pattern before reporting")
    else:
        inferred = "ambiguous"
        notes.append(
            f"chrX het rate {rate:.3f} sits between the male/female bounds -"
            " insufficient signal")
    return {
        "inferred": inferred,
        "x_het_rate": rate,
        "x_het": x_het,
        "x_called": x_called,
        "n_y_calls": n_y,
        "bounds": {"male_x_het_max": male_max,
                   "female_x_het_min": female_min},
        "notes": notes,
    }


def integrity_report(vcf_path, sample: str | None = None) -> dict:
    """One JSON-able bundle: compute_stats + header_forensics + sex_check."""
    stats = compute_stats(vcf_path, sample=sample)
    return {
        "vcf": str(vcf_path),
        "stats": stats,
        "header": header_forensics(vcf_path),
        "sex_check": sex_check(stats),
    }
