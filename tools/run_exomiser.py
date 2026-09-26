"""Generate an Exomiser genome-mode analysis YAML + print the run command.

    python tools/run_exomiser.py --vcf data/WGS.vcf.gz \
        --hpo-terms results/hpo_terms.json --dry-run
    python tools/run_exomiser.py --vcf data/WGS.vcf.gz \
        --hpo-terms results/hpo_terms.json --mode PASS_ONLY \
        --out results/exomiser/analysis.yml

This writes an exomiser-cli analysis YAML (Arm A, plan.md Phase 2) and prints
the exact `java -jar` command. It does NOT launch java - Exomiser jobs are
hours-long and are started deliberately, then logged into docs/runtime_log.md.

REQUIRED ONE-TIME DOWNLOADS (~30 GB, plan.md section 3)
---------------------------------------------------------
* exomiser-cli-14.x distribution (data.monarchinitiative.org/exomiser/latest
  or github.com/exomiser/Exomiser releases)
* exomiser data directory        - `2406_phenotype` + `2406_hg38` bundles
  unpacked under --data-dir; ``tools/fetch_big.py`` fetches them with
  resumable byte ranges when a single stream throttles.
* The hg38 bundle expects chr-prefixed contigs - the challenge VCF's bare
  contigs need ``tools/normalize_contigs.py`` first (a `.chr.vcf` derived
  copy; run_track1.find_vcf excludes it from case inputs).
* CADD/REMM are optional datasources NOT inside the bundles - the emitted
  YAML omits them deliberately (the jar halts if listed without the files);
  PASS_ONLY keeps RAM ~4-12 GB (plan.md section 3).

HPO ids are read from results/hpo_terms.json (the Phase-1 docx-extraction
artifact: {"proband_id": ..., "hpo_terms": ["HP:...", ...]} - a bare list
also parses). If the file is absent, --hpo HP:xxxx flags may supply terms;
--dry-run with neither fails loudly since an empty HPO set makes Exomiser
run variant-only, which is not the Arm-A contract.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# the verified local distribution is 14.0.0; if a newer CLI is unpacked
# alongside, prefer the glob so --jar isn't a stale-name copy-paste trap.
DEFAULT_JAR = "exomiser-cli-14.0.0.jar"
DEFAULT_DATA_VERSION = "2406"   # exomiser data bundle tag; update per release
OUTPUT_FORMATS = ["HTML", "JSON", "TSV_GENE", "TSV_VARIANT"]


def _yaml_list(items: list[str], indent: int = 8) -> str:
    pad = " " * indent
    return "\n".join(f"{pad}- {i}" for i in items)


# 'genomeAssembly:' inside analysis takes the hgNN spelling, NOT the GRChNN
# enum the CLI flag uses (audit H5: 'GRCH38' matches neither convention and
# halts the loader).
_YAML_ASM = {"GRCH38": "hg38", "GRCH37": "hg19"}

# Verified against the shipped examples/preset-genome-analysis.yml and
# test-analysis-genome.yml in exomiser-cli-14.0.0: inheritanceModes is a
# MAP of mode -> max-MAF-percent, NOT a list of mode names. AR must carry
# BOTH the HOM_ALT and COMP_HET modes or the recessive arm never runs.
_INHERITANCE_MODES = {
    "AUTOSOMAL_DOMINANT": 0.1,
    "AUTOSOMAL_RECESSIVE_HOM_ALT": 0.1,
    "AUTOSOMAL_RECESSIVE_COMP_HET": 2.0,
    "X_DOMINANT": 0.1,
    "X_RECESSIVE_HOM_ALT": 0.1,
    "X_RECESSIVE_COMP_HET": 2.0,
    "MITOCHONDRIAL": 0.2,
}
# Verified enum names: gnomAD subpopulations are spelled GNOMAD_{E,G}_<POP>
# (topmed/ESP/exac are folded into gnomAD as of v4, per the preset's own
# comment - the bare GNOMAD_E/GNOMAD_G names do NOT exist as enum values).
_FREQUENCY_SOURCES = [
    "UK10K",
    "GNOMAD_E_AFR", "GNOMAD_E_AMR", "GNOMAD_E_EAS", "GNOMAD_E_NFE",
    "GNOMAD_E_SAS",
    "GNOMAD_G_AFR", "GNOMAD_G_AMR", "GNOMAD_G_EAS", "GNOMAD_G_NFE",
    "GNOMAD_G_SAS",
]
# CADD/REMM are OPTIONAL datasources requiring their own tabix downloads +
# application.properties entries (the preset warns the jar halts without
# them) - they are NOT inside the 2406 bundle. REVEL/MVP/SPLICE_AI/
# ALPHA_MISSENSE are bundle-shipped.
_PATHOGENICITY_SOURCES = [
    "REVEL", "MVP", "SPLICE_AI", "ALPHA_MISSENSE",
]

# The preset's recommended order for a genome-sized analysis: phenotype
# prioritiser FIRST (cheap gene-level filter), then the variant chain.
_STEPS = """    steps: [
        hiPhivePrioritiser: { },
        priorityScoreFilter: { priorityType: HIPHIVE_PRIORITY, minPriorityScore: 0.501 },
        failedVariantFilter: { },
        regulatoryFeatureFilter: { },
        frequencyFilter: { maxFrequency: 2.0 },
        pathogenicityFilter: { keepNonPathogenic: true },
        inheritanceFilter: { },
        omimPrioritiser: { }
    ]"""


def build_yaml(vcf: Path, hpo: list[str], proband: str, mode: str,
               assembly: str, out_name: str) -> str:
    """Emit the analysis-file schema exomiser-cli 14.x actually loads -
    verified against examples/test-analysis-genome.yml shipped inside the
    14.0.0 distribution. A single ``analysis:`` section carries vcf/ped/
    proband/hpoIds/genomeAssembly/analysisMode + the filter chain; output
    control goes on the CLI (--output-* flags), not in this file."""
    hpo_fmt = "[" + ", ".join(f"'{t}'" for t in hpo) + "]"
    asm = _YAML_ASM[assembly]
    modes = ",\n        ".join(f"{k}: {v}" for k, v in
                              _INHERITANCE_MODES.items())
    freqs = ",\n        ".join(_FREQUENCY_SOURCES)
    return f"""# Exomiser genome-mode analysis - generated by tools/run_exomiser.py
# Arm A of the two-arm design (plan.md Phase 2). Paths are absolute on the
# host running the jar; regenerate per machine, do not hand-edit.
analysis:
    genomeAssembly: {asm}
    vcf: {str(vcf).replace(chr(92), '/')}
    ped:
    proband: {proband}
    hpoIds: {hpo_fmt}
    # inheritanceModes values = max MAF (%) tolerated as causative under
    # that mode; COMP_HET gets 2.0% (one common-ish carrier allele).
    # Without BOTH _HOM_ALT and _COMP_HET the recessive arm cannot run.
    inheritanceModes: {{
        {modes}
    }}
    # PASS_ONLY = analyse PASS-filter variants only (low RAM path).
    # FULL = every variant; needs ~16+ GB heap.
    analysisMode: {mode}
    # required: the AF sources the frequencyFilter consults - bare
    # 'GNOMAD_E' is NOT an enum value; subpopulations are required names
    frequencySources: [
        {freqs}
    ]
    pathogenicitySources: [ {', '.join(_PATHOGENICITY_SOURCES)} ]
{_STEPS}
"""


def load_hpo(path: Path) -> list[str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    terms = raw["hpo_terms"] if isinstance(raw, dict) else list(raw)
    return [t for t in terms if isinstance(t, str)]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Exomiser genome-mode runner prep")
    ap.add_argument("--vcf", required=True)
    ap.add_argument("--hpo-terms", default=str(REPO / "results" / "hpo_terms.json"))
    ap.add_argument("--hpo", action="append", default=[],
                    help="extra/override HPO id (repeatable)")
    ap.add_argument("--proband", default="PROBAND01")
    ap.add_argument("--mode", choices=["PASS_ONLY", "FULL"], default="PASS_ONLY")
    ap.add_argument("--assembly", choices=["GRCH38", "GRCH37"], default="GRCH38")
    ap.add_argument("--out", default=str(REPO / "results" / "exomiser"
                                         / "analysis.yml"))
    ap.add_argument("--jar", default=DEFAULT_JAR)
    ap.add_argument("--data-dir", default=str(REPO / "env" / "exomiser_data"))
    ap.add_argument("--xmx", default="12g")
    ap.add_argument("--dry-run", action="store_true",
                    help="print YAML + command; write nothing")
    args = ap.parse_args(argv)

    hpo_path = Path(args.hpo_terms)
    hpo = list(args.hpo)
    if hpo_path.exists():
        try:
            hpo = list(dict.fromkeys(load_hpo(hpo_path) + hpo))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise SystemExit(
                f"{hpo_path}: cannot parse HPO JSON ({e}) - refusing to "
                "emit an analysis YAML from a corrupt term list")
    elif not hpo:
        raise SystemExit(f"no HPO terms: {hpo_path} missing and no --hpo given "
                         "(variant-only run is not the Arm-A contract)")
    else:
        print(f"note: {hpo_path} not found; using --hpo terms only",
              file=sys.stderr)
    if not hpo:  # file existed but carried no terms, or was empty
        raise SystemExit(
            f"empty HPO list after merging {hpo_path} + --hpo - refusing to "
            "emit a variant-only analysis YAML")
    bad = [t for t in hpo if not re.fullmatch(r"HP:\d{7}", t)]
    if bad:
        raise SystemExit(f"invalid HPO ids {bad} - an unquoted value would "
                         "break the generated YAML (or score nonsense)")

    if not Path(args.vcf).exists():
        print(f"WARNING: --vcf {args.vcf} does not exist yet - the YAML "
              "points at a path that must exist before the jar runs",
              file=sys.stderr)
    out = Path(args.out)
    out_name = str(out.parent / (args.proband + "-" + args.mode))
    yaml_text = build_yaml(Path(args.vcf).resolve(), hpo, args.proband,
                           args.mode, args.assembly, out_name)
    # data dir + bundle version are spring properties, not YAML keys -
    # put them on the command line where the jar actually reads them.
    # hg38.version tells the app which <data-dir>/<ver>_<asm> folder to
    # open; output goes via --output-* flags (verified in --help).
    data_dir = str(Path(args.data_dir).resolve()).replace(chr(92), '/')
    out_dir = str(Path(out_name).parent.resolve()).replace(chr(92), '/')
    asm_prop = "hg38" if args.assembly == "GRCH38" else "hg19"
    cmd = (f"java -Xmx{args.xmx} "
           f"-Dexomiser.data-directory={data_dir} "
           f"-Dexomiser.{asm_prop}.data-version={DEFAULT_DATA_VERSION} "
           f"-Dexomiser.phenotype.data-version={DEFAULT_DATA_VERSION} "
           f"-jar {args.jar} --analysis {str(out).replace(chr(92), '/')} "
           f"--output-directory {out_dir} "
           f"--output-filename {Path(out_name).name} "
           f"--output-format {','.join(OUTPUT_FORMATS)}")

    print("Exomiser analysis YAML" + (" [dry-run]:" if args.dry_run else ":"))
    print(yaml_text)
    print("Run command:")
    print(f"  {cmd}")
    print("\nPrereqs: exomiser data dir must contain "
          f"{DEFAULT_DATA_VERSION}_{_YAML_ASM[args.assembly]}/ and "
          f"{DEFAULT_DATA_VERSION}_phenotype/ "
          "(~30 GB total; data.monarchinitiative.org/exomiser/latest).")
    if args.dry_run:
        return 0

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(yaml_text, encoding="utf-8", newline="\n")
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
