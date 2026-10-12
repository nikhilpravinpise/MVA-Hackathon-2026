"""Retrospective benchmark: run the engine blind on gene -> approved-drug
success cases declared (and frozen) in config/track2.yaml.

For every case the module is built exactly like the MVA case -
disease gene + STRING neighbours - and the declared drugs are never seeded.
A known drug is "recovered" if it lands in the ranked approved-candidate
list; its rank and the recall@k over all cases are reported honestly,
including the stage at which a missed drug dropped out.
"""
from __future__ import annotations

from datetime import datetime, timezone

from . import engine


def _match(result, name, alias):
    """Find a known drug in the ranked candidates (alias-normalised)."""
    key = engine._drug_key(name, alias)
    for c in result["candidates"]:
        ck = engine._drug_key(c["drug"], alias)
        if ck == key or engine._norm(ck) == engine._norm(key):
            return c
    return None


def run_benchmark(http, cfg):
    """Run every declared case. Returns the benchmark.json-shaped dict."""
    alias = {k.lower(): v.lower()
             for k, v in (cfg.get("lincs", {}).get("alias_map") or {}).items()}
    cases_out = []
    ks = (1, 5, 10, 25)
    hits = {k: 0 for k in ks}
    n_found = 0

    for bc in cfg["benchmark"]["cases"]:
        gene = bc["gene"]
        case = {
            "name": f"benchmark_{gene.lower()}",
            "disease": bc["disease"],
            "disease_gene": gene,
            "seed_genes": [{"symbol": gene, "role": "disease_gene",
                            "axis": None,
                            "justification": "benchmark disease gene"}],
            "run_lincs": False,
        }
        res = engine.run_case(http, cfg, case)
        collected = {engine._norm(x) for x in res.get("collected_names", [])}
        known = []
        best_rank = None
        for kd in bc["known_drugs"]:
            hit = _match(res, kd, alias)
            if hit:
                stage = "ranked"
            elif engine._norm(engine._drug_key(kd, alias)) in collected:
                stage = "collected_not_approved"
            else:
                stage = "not_collected"
            known.append({
                "drug": kd,
                "found": hit is not None,
                "stage": stage,
                "rank": hit["rank"] if hit else None,
                "score": hit["score"] if hit else None,
                "tier": hit["tier"] if hit else None,
            })
            if hit:
                n_found += 1
                if best_rank is None or hit["rank"] < best_rank:
                    best_rank = hit["rank"]
        for k in ks:
            if best_rank is not None and best_rank <= k:
                hits[k] += 1
        cases_out.append({
            "gene": gene,
            "disease": bc["disease"],
            "citations": bc.get("citations", []),
            "module_genes": res["module"]["n"],
            "n_candidates": len(res["candidates"]),
            "funnel": res["funnel"],
            "known_drugs": known,
            "rank_of_known": best_rank,
            "k": max(ks),
            "top10": [{"drug": c["drug"], "score": c["score"],
                       "tier": c["tier"]}
                      for c in res["candidates"][:10]],
        })

    n_cases = len(cases_out) or 1
    out = {
        "schema": "t2.benchmark/1",
        "generated_by": "tools/run_track2.py --benchmark",
        "generated_at": datetime.now(timezone.utc)
                        .replace(microsecond=0).isoformat(),
        "cases": cases_out,
        "n_cases": len(cases_out),
        "n_known_recovered": n_found,
        "recall_at_1": round(hits[1] / n_cases, 3),
        "recall_at_5": round(hits[5] / n_cases, 3),
        "recall_at_10": round(hits[10] / n_cases, 3),
        "recall_at_25": round(hits[25] / n_cases, 3),
        "notes": [
            "recall@k = fraction of cases whose best-ranked declared drug "
            "appears at rank <= k in the approved-candidate list",
            "a declared drug missing entirely means it never entered the "
            "candidate space (its targets are not module genes) or failed "
            "the approval gate - both reported via funnel counts",
        ],
    }
    return out
