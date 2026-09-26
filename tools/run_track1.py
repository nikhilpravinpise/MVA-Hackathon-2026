"""One-command Track-1 driver: EDA -> funnel -> SF scan -> phasing -> CSV ->
oracle score -> report inputs.

    python tools/run_track1.py --case results/spike_case --out results/t1_spike

A "case dir" contains: <name>.vcf (any .vcf file), hpo_terms.json, hp.obo,
phenotype.hpoa, genes_to_disease.json, optionally truth.json. This same
command runs unchanged on the patient bundle once data/ lands - that is the
point of the stand-in-first strategy.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
for p in (REPO, REPO / "scorer"):
    sys.path.insert(0, str(p))

from src.config import load_config  # noqa: E402
from src.pipeline import ABLATION_SOURCES, run_pipeline  # noqa: E402


def find_vcf(case_dir: Path) -> Path:
    vcfs = sorted(case_dir.glob("*.vcf")) + sorted(case_dir.glob("*.vcf.gz"))
    if not vcfs:
        raise FileNotFoundError(f"no .vcf in {case_dir}")
    return vcfs[0]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, help="case bundle directory")
    ap.add_argument("--out", required=True)
    ap.add_argument("--sample", default=None)
    ap.add_argument("--sam", default=None,
                    help="locus SAM export (samtools view -O SAM) for "
                         "read-level phase evidence on the top pair")
    ap.add_argument("--skip-eda", action="store_true")
    args = ap.parse_args(argv)

    case = Path(args.case)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = load_config()
    t0 = time.time()
    summary: dict = {"case": str(case), "steps": {}}

    hpo_file = case / "hpo_terms.json"
    hpo = json.loads(hpo_file.read_text())
    hpo = hpo["hpo_terms"] if isinstance(hpo, dict) else hpo
    vcf = find_vcf(case)
    corpus = {k: (case / v).resolve() if (case / v).exists() else None
              for k, v in (("obo_path", "hp.obo"),
                           ("hpoa_path", "phenotype.hpoa"),
                           ("g2d_path", "genes_to_disease.json"))}

    # -- step 1: EDA ---------------------------------------------------------
    if args.skip_eda:
        summary["steps"]["eda"] = "skipped: --skip-eda"
    else:
        try:
            from src.vcf_qc import integrity_report
            eda = integrity_report(vcf)
            (out / "eda_report.json").write_text(json.dumps(eda, indent=1))
            summary["steps"]["eda"] = "ok"
        except Exception as e:
            summary["steps"]["eda"] = f"skipped: {e}"

    # -- step 2: funnel ------------------------------------------------------
    res = run_pipeline(vcf, hpo, sample=args.sample, cfg=cfg,
                       out_dir=out / "funnel", **corpus)
    summary["steps"]["funnel"] = res["funnel"]

    # -- step 3: ablations ----------------------------------------------------
    truth_f = case / "truth.json"
    truth = json.loads(truth_f.read_text()) if truth_f.exists() else None
    abl_out = {}
    for src in sorted(ABLATION_SOURCES):
        r = run_pipeline(vcf, hpo, sample=args.sample, cfg=cfg,
                         drops=frozenset({src}), **corpus)
        rank = None
        if truth:
            want = sorted((v["pos"], v["alt"]) for v in truth["pair"])
            for h in r["ranked"]:
                got = sorted((v["pos"], v["alt"]) for v in h["variants"])
                if h["model"] == "compound_het" and got == want:
                    rank = h["rank"]
                    break
        else:
            # no truth: report rank of the baseline top pair
            base_top = next((h for h in res["ranked"] if h["emitted"]), None)
            if base_top:
                want = sorted((v["pos"], v["alt"]) for v in base_top["variants"])
                for h in r["ranked"]:
                    got = sorted((v["pos"], v["alt"]) for v in h["variants"])
                    if h["model"] == base_top["model"] and got == want:
                        rank = h["rank"]
                        break
        abl_out[src] = {"pair_rank": rank, "emitted": r["funnel"]["emitted"]}
    (out / "ablations.json").write_text(json.dumps(abl_out, indent=1))
    summary["steps"]["ablations"] = abl_out

    # -- step 4: secondary findings ------------------------------------------
    try:
        from src.sf_scan import findings_to_rows, load_sf_list, scan_facts
        from src.triage import extract_facts
        from src.vcf import VcfReader
        sf_list = load_sf_list(REPO / "config" / "acmg_sf_v33.json")
        reader = VcfReader(vcf)
        sample = args.sample or (reader.samples[0] if reader.samples else "")
        facts = []
        for rec in reader.records(sample=sample):
            facts.extend(extract_facts(rec, sample, cfg))
        reader.close()
        findings = scan_facts(facts, sf_list, cfg)
        sf_rows = findings_to_rows(findings)
        sf_dump = [{**{k: getattr(f, k, None)
                        for k in ("gene", "disease", "moi", "category",
                                  "basis", "note")},
                    "variants": [v.vid for v in f.variants]}
                   for f in findings]
        (out / "sf_findings.json").write_text(json.dumps(sf_dump, indent=1))
        summary["steps"]["sf"] = f"{len(findings)} findings"
    except Exception as e:
        sf_rows = []
        summary["steps"]["sf"] = f"skipped: {e}"

    # -- step 5: phasing report on top pair -----------------------------------
    try:
        from src.phasing import determine_phase
        top = next((h for h in res["ranked"] if h["emitted"]
                    and h["model"] == "compound_het"), None)
        ph = {"evidence": [], "agreement": "n/a"}
        if top:
            # rebuild VariantFacts for the pair from facts list
            pair_keys = {(v["chrom"], v["pos"]) for v in top["variants"]}
            pair = [f for f in facts if (f.chrom, f.pos) in pair_keys]
            if len(pair) >= 2:
                call = determine_phase(pair[0], pair[1])
                ph["evidence"].append(
                    {"name": "PGT/PID read-backed phasing",
                     "mechanism": call.mechanism, "result": call.relation,
                     "detail": call.detail})
                ph["agreement"] = call.relation
                if args.sam:
                    from src.reads import phase_from_reads, evidence_report
                    sam_lines = Path(args.sam).read_text().splitlines()
                    read_ph = phase_from_reads(
                        iter(sam_lines), pair[0].key, pair[1].key)
                    ph["evidence"].append(
                        {"name": "read-level SAM evidence",
                         "mechanism": "read_level",
                         "result": read_ph.get("relation"),
                         "counts": read_ph.get("counts")})
                    comb = evidence_report(call, read_ph)
                    ph["agreement"] = comb.get(
                        "consensus_relation", comb.get("agreement"))
        (out / "phasing_report.json").write_text(json.dumps(ph, indent=1))
        summary["steps"]["phasing"] = ph.get("agreement")
    except Exception as e:
        summary["steps"]["phasing"] = f"skipped: {e}"

    # -- step 5b: ACMG/AMP classification of the top hypothesis ---------------
    try:
        from src.acmg import acmg_report
        top = next((h for h in res["ranked"] if h["emitted"]), None)
        if top:
            ctx = {"in_trans": top["in_trans"],
                   "pheno_score": top["pheno_score"],
                   "gene_known_for_disease": top["pheno_score"] > 0}
            rep = acmg_report(top, ctx)
            (out / "acmg_report.json").write_text(json.dumps(rep, indent=1))
            summary["steps"]["acmg"] = rep.get(
                "combined_classification", rep.get("combined"))
        else:
            summary["steps"]["acmg"] = "skipped: no emitted hypothesis"
    except Exception as e:
        summary["steps"]["acmg"] = f"skipped: {e}"

    # -- step 6: submission CSV + local oracle score --------------------------
    try:
        from src.submit import (build_rows, submission_bytes,
                                validate_submission_bytes)
        rows = build_rows(res["ranked"], sf_rows=sf_rows, cfg=cfg)
        data = submission_bytes(rows)
        (out / "submission.csv").write_bytes(data)
        summary["steps"]["csv_rows"] = len(rows)
        if truth:
            gt = frozenset(
                (v["chrom"] if v["chrom"].startswith("chr") else "chr" + v["chrom"],
                 v["pos"], v["ref"], v["alt"]) for v in truth["pair"])
            score = validate_submission_bytes(data, gt)
            summary["steps"]["oracle"] = {
                "rank_points": score.rank_points, "f_max": score.f_max,
                "full_match_rank": score.full_match_rank}
    except Exception as e:
        summary["steps"]["csv"] = f"skipped: {e}"

    summary["runtime_sec"] = round(time.time() - t0, 2)
    (out / "run_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
