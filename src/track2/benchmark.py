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


def _match_excluded(result, name, alias):
    """Find a known drug in the mechanism-opposed exclusion list."""
    key = engine._drug_key(name, alias)
    for c in result.get("excluded_mechanism_opposed", []):
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
            excl = None if hit else _match_excluded(res, kd, alias)
            if hit:
                stage = "ranked"
            elif excl:
                # known drug exists but the direction layer removed it -
                # reported, and it must never happen for the frozen set
                stage = "excluded_mechanism_opposed"
            elif engine._norm(engine._drug_key(kd, alias)) in collected:
                stage = "collected_not_approved"
            else:
                stage = "not_collected"
            known.append({
                "drug": kd,
                "found": hit is not None,
                "stage": stage,
                "rank": hit["rank"] if hit else None,
                "rank_before_direction": (hit or excl or {})
                                          .get("rank_before_direction"),
                "score": (hit or excl or {}).get("score"),
                "tier": (hit or excl or {}).get("tier"),
                "direction": (hit or excl or {}).get("direction"),
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
            "n_excluded_mechanism_opposed":
                len(res.get("excluded_mechanism_opposed", [])),
            "funnel": res["funnel"],
            "known_drugs": known,
            "rank_of_known": best_rank,
            "k": max(ks),
            "top10": [{"drug": c["drug"], "score": c["score"],
                       "tier": c["tier"],
                       "direction": c.get("direction")}
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
        # frozen v1 numbers (pre-direction-layer run of 2026-10-12) kept so
        # a reader can see whether the layer changed recall - declared in
        # config/track2.yaml under benchmark.v1_frozen
        "v1_frozen": cfg["benchmark"].get("v1_frozen"),
        "direction": {
            "enabled": bool((cfg.get("direction") or {}).get("enabled")),
            "note": "recall computed on the post-direction ranked list; "
                    "known drugs must never classify as opposed (tested)",
        },
        "notes": [
            "recall@k = fraction of cases whose best-ranked declared drug "
            "appears at rank <= k in the approved-candidate list",
            "a declared drug missing entirely means it never entered the "
            "candidate space (its targets are not module genes) or failed "
            "the approval gate - both reported via funnel counts",
        ],
    }
    return out
