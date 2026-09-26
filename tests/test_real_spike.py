"""GATE-2 external validation on REAL data (plan.md section 2.1.2b).

The pipeline must recover, blind, a REAL ClinVar pathogenic compound-het
pair (PAH / phenylketonuria OMIM:261600 - firewall-clean of the proband
locus) spiked into a PUBLIC genome slice (GIAB HG002, chr12:102.8-103.0 Mb)
with realistic allele fractions and a real OMIM:261600 HPO set. Built by
tools/build_real_spike.py; annotation is real Ensembl REST VEP output.

Everything here is marked ``slow``: it parses the full hp.obo DAG and the
phenotype.hpoa corpus (~46 MB on disk) and runs the funnel twice (full +
--drop hpo ablation). Skips cleanly when the built case or the corpus is
absent - run tools/fetch_public_vcfs.py then tools/build_real_spike.py
(and tools/fetch_refs.py for the corpus) to materialize them.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.config import load_config
from src.pipeline import run_pipeline

REPO = Path(__file__).resolve().parents[1]
SPIKE_DIR = REPO / "env" / "real_spike"
CORPUS = REPO / "env" / "corpus"

SPIKE_VCF = SPIKE_DIR / "real_spike.vcf"
TRUTH = SPIKE_DIR / "truth.json"
HPO_JSON = SPIKE_DIR / "hpo_terms.json"
OBO = CORPUS / "hp.obo"
HPOA = CORPUS / "phenotype.hpoa"
G2D = CORPUS / "gene2disease.json"
G2P = CORPUS / "genes_to_phenotype.txt"


def _need(path: Path, how: str) -> Path:
    if not path.exists():
        pytest.skip(f"missing {path.name} - {how}")
    return path


def _g2d_path(tmp_dir: Path) -> Path:
    """gene->disease map: prefer the corpus JSON; otherwise derive it from
    genes_to_phenotype.txt (same disease_id convention as phenotype.hpoa)."""
    if G2D.exists():
        return G2D
    if G2P.exists():
        out = tmp_dir / "gene2disease.derived.json"
        g2d: dict[str, set] = {}
        for i, line in enumerate(
                open(G2P, encoding="utf-8", errors="replace")):
            cols = line.rstrip("\n").split("\t")
            if i == 0 and cols[0].lower() in ("ncbi_gene_id", "#"):
                continue
            if len(cols) >= 6 and cols[5].startswith(("OMIM:", "ORPHA:",
                                                      "DECIPHER:")):
                g2d.setdefault(cols[1], set()).add(cols[5])
        out.write_text(json.dumps({g: sorted(v) for g, v in g2d.items()}))
        return out
    pytest.skip("no gene->disease source: need env/corpus/gene2disease.json "
                "or genes_to_phenotype.txt")


def _pair_key(variant: dict) -> tuple:
    """Normalize a ranked-list variant to truth convention (chr-prefixed)."""
    from src.vcf import to_submission_chrom
    return (to_submission_chrom(variant["chrom"]), variant["pos"],
            variant["ref"], variant["alt"])


def _truth_pair(truth: dict) -> set:
    return {(v["chrom"], v["pos"], v["ref"], v["alt"])
            for v in truth["pair"]}


@pytest.fixture(scope="module")
def real_case(tmp_path_factory):
    """Locate the built case + corpus; run the funnel full and --drop hpo."""
    _need(SPIKE_VCF, "run tools/fetch_public_vcfs.py --chr-subset 12 "
                     "--region chr12:102800000-103000000 and then "
                     "tools/build_real_spike.py")
    _need(TRUTH, "run tools/build_real_spike.py")
    _need(HPO_JSON, "run tools/build_real_spike.py")
    _need(OBO, "run tools/fetch_refs.py")
    _need(HPOA, "run tools/fetch_refs.py")
    tmp_dir = tmp_path_factory.mktemp("real_spike")
    g2d = _g2d_path(tmp_dir)

    truth = json.loads(TRUTH.read_text())
    hpo = json.loads(HPO_JSON.read_text())
    hpo_terms = hpo["hpo_terms"] if isinstance(hpo, dict) else list(hpo)

    common = dict(obo_path=OBO, hpoa_path=HPOA, g2d_path=g2d)
    full = run_pipeline(SPIKE_VCF, hpo_terms, **common)
    abl = run_pipeline(SPIKE_VCF, hpo_terms, drops=frozenset({"hpo"}),
                       **common)
    return {"truth": truth, "hpo": hpo_terms, "full": full, "ablated": abl,
            "cfg": load_config()}


def _find_pair(res: dict, want: set) -> dict | None:
    for h in res["ranked"]:
        if h["model"] != "compound_het":
            continue
        if {_pair_key(v) for v in h["variants"]} == want:
            return h
    return None


def _top_table(res: dict, n: int = 10) -> str:
    lines = []
    for h in res["ranked"][:n]:
        vs = "+".join(f"{v['chrom']}:{v['pos']}{v['ref']}>{v['alt']}"
                      for v in h["variants"])
        lines.append(f"#{h['rank']} {h['gene']} {h['model']} "
                     f"score={h['score']} epcr={h['epcr']} "
                     f"trans={h['in_trans']} emitted={h['emitted']} {vs}")
    return "\n".join(lines)


@pytest.mark.slow
def test_real_spike_pair_recovered_top5(real_case):
    """Falsification: a REAL ClinVar P/LP PAH compound-het pair spiked into
    REAL HG002 background is not recovered as a compound_het in the emitted
    set at rank <=5 - then the funnel fails on data it never saw (the
    external-validation requirement itself fails: annotation mapping,
    rarity tiering, inheritance enumeration or phenotype scoring is broken
    somewhere on the real-data path)."""
    res = real_case["full"]
    want = _truth_pair(real_case["truth"])
    pair = _find_pair(res, want)
    assert pair is not None, (
        "true PAH pair absent from ranked hypotheses.\n" + _top_table(res))
    assert pair["rank"] <= 5, (
        f"true pair at rank {pair['rank']} (gate: <=5)\n" + _top_table(res))
    assert pair["in_trans"] == "trans", (
        f"PGT/PID trans evidence lost: {pair['phase_detail']}")
    assert pair["emitted"], (
        f"true pair below emit floor (score={pair['score']})")

    # no noise-gene hypothesis may outrank the true pair
    noise = set(real_case["cfg"].get("negative_control", {})
                .get("noise_genes", []))
    outrankers = [h for h in res["ranked"]
                  if h["rank"] < pair["rank"] and h["gene"] in noise]
    assert not outrankers, (
        f"noise genes outrank the truth: "
        f"{[(h['gene'], h['rank']) for h in outrankers]}")

    # audit printout for the report (visible with -s or on failure)
    print(f"\nreal-spike top ranks:\n{_top_table(res)}")
    print(f"true pair rank={pair['rank']} score={pair['score']} "
          f"trans={pair['in_trans']} funnel={res['funnel']}")


@pytest.mark.slow
def test_real_spike_ablation_drop_hpo(real_case):
    """Falsification: with phenotype evidence dropped, the true pair falls
    below rank 10 - meaning the funnel's ranking leaned entirely on the HPO
    match and carries too little variant-level evidence (rarity + damage +
    inheritance fit) to stand on its own."""
    res = real_case["ablated"]
    want = _truth_pair(real_case["truth"])
    pair = _find_pair(res, want)
    assert pair is not None, (
        "true pair vanished under --drop hpo.\n" + _top_table(res))
    assert pair["rank"] <= 10, (
        f"ablated rank {pair['rank']} (gate: <=10)\n" + _top_table(res))
    print(f"\n--drop hpo: true pair rank={pair['rank']} "
          f"score={pair['score']} emitted={pair['emitted']}")
