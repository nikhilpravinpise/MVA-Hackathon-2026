"""Engine orchestration: seeds -> module -> candidates -> approved -> scored.

``run_case`` is used identically for the MVA case (seeds from config) and for
each benchmark case (seeds = the single disease gene).  Everything that can
vary (weights, thresholds, libraries, seeds) comes from ``cfg`` so a run is
fully described by the frozen config file.
"""
from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from . import direction as direction_mod
from . import prism as prism_mod
from . import proximity, scoring, sources


def pmap(fn, items, workers=1):
    """Order-preserving parallel map over IO-bound API calls.

    Determinism is unaffected: results are written into indexed slots, so
    output order never depends on completion order.  Workers>1 only helps
    wall-clock time for remote calls; replay mode is equally correct.
    """
    items = list(items)
    if workers <= 1 or len(items) <= 1:
        return [fn(x) for x in items]
    out = [None] * len(items)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(fn, x): i for i, x in enumerate(items)}
        for f, i in futs.items():
            out[i] = f.result()
    return out


def _norm(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _drug_key(name: str, alias_map: dict) -> str:
    """Canonical lowercase key for a drug/perturbagen name (alias-aware)."""
    n = name.strip().lower()
    n = alias_map.get(n, n)
    # strip common salt/form suffixes used in L1000 pert names
    n = re.sub(r"\s+(hydrochloride|sulfate|sodium|mesylate|maleate|"
               r"tartrate|fumarate|phosphate|citrate|acetate)\b.*$", "", n)
    return n.strip()


# ------------------------------------------------------------- module -----
def build_module(http, cfg, seed_symbols, disease_gene):
    """Disease module = seeds UNION top STRING neighbours of disease_gene.

    Returns (module:set, partner_map, notes, meta).  partner_map records
    disease-gene partners AND is extended by callers for the routing
    universe (neighbours of every module gene).
    """
    ep = cfg["endpoints"]
    mod = cfg["module"]
    module = set(seed_symbols)
    notes = []
    partners, meta = sources.string_partners(
        http, ep["string"], disease_gene,
        mod["neighbor_limit"], mod["required_score"])
    partner_map = {disease_gene: [p["name"] for p in partners if p["name"]]}
    module.update(partner_map[disease_gene])
    notes.append(f"{disease_gene}: +{len(partner_map[disease_gene])} "
                 f"STRING neighbours (score>={mod['required_score']})")
    return module, partner_map, notes, meta


def build_universe(http, cfg, module, partner_map):
    """Routing universe for shortest paths = module + neighbours of every
    module gene (per-gene limit, global cap - see config)."""
    ep = cfg["endpoints"]
    mod = cfg["module"]
    workers = int(cfg.get("workers", 1))

    def _fetch(g):
        if g in partner_map:
            return g, partner_map[g]
        partners, _ = sources.string_partners(
            http, ep["string"], g, mod["universe_partner_limit"],
            mod["required_score"])
        return g, [p["name"] for p in partners if p["name"]]

    universe = set(module)
    for g, partners in pmap(_fetch, sorted(module), workers):
        partner_map[g] = partners
        for n in sorted(partners):
            universe.add(n)
            if len(universe) >= mod["universe_cap"]:
                return universe
    return universe


# ------------------------------------------------------- drug collection --
_CODE_NAME = re.compile(r"^[A-Z]{1,6}[- ]?\d{2,8}([-.][A-Z0-9]{1,6})?$")


def _new_cand(cid, name):
    return {"chembl_id": cid, "names": set([name.lower()]) if name else set(),
            "module_hits": set(), "hit_types": {}, "ot_stage": None,
            "dgidb_pmids": set(), "dgidb_sources": set(),
            "dgidb_types": set()}


def collect_candidates(http, cfg, module, ensembl_cache):
    """Harvest candidate drugs for every module gene (Open Targets + DGIdb),
    keeping at most ``per_gene_cap`` per gene so hubs cannot crowd out
    coverage.  Returns (candidates dict, funnel counts).
    """
    ep = cfg["endpoints"]
    col = cfg.get("collection", {})
    per_gene_cap = col.get("per_gene_cap", 50)
    per_gene = {g: {} for g in module}
    funnel = {"module_genes": len(module), "ot_rows": 0,
              "dgidb_interactions": 0}
    workers = int(cfg.get("workers", 1))

    # --- Open Targets: target -> clinical-stage/approved drugs
    def _ot_rows(g):
        ens = ensembl_cache.get(g)
        if not ens:
            ens, _ = sources.ot_search_target(http, ep["opentargets"], g)
            ensembl_cache[g] = ens
        if not ens:
            return g, []
        rows, _ = sources.ot_known_drugs(http, ep["opentargets"], ens)
        return g, rows

    for g, rows in pmap(_ot_rows, sorted(module), workers):
        funnel["ot_rows"] += len(rows)
        for r in rows:
            d = r.get("drug") or {}
            cid, name = d.get("id"), (d.get("name") or "").strip()
            if not cid or not name:
                continue
            c = per_gene[g].setdefault(cid, _new_cand(cid, name))
            c["names"].add(name.lower())
            c["ot_stage"] = d.get("maximumClinicalStage") or c["ot_stage"]

    # --- DGIdb: curated gene -> drug interactions
    inter, _ = sources.dgidb_gene_interactions(
        http, ep["dgidb"], sorted(module))
    for g in sorted(inter):
        for it in inter[g]:
            funnel["dgidb_interactions"] += 1
            drug = it.get("drug") or {}
            cid = None
            m = re.match(r"chembl:(CHEMBL\d+)", drug.get("conceptId") or "")
            if m:
                cid = m.group(1)
            name = (drug.get("name") or "").strip()
            if not name and not cid:
                continue
            key = cid or f"name:{_norm(name)}"
            c = per_gene[g].setdefault(key, _new_cand(cid, name))
            if name:
                c["names"].add(name.lower())
            for s in it.get("sources") or []:
                if s.get("sourceDbName"):
                    c["dgidb_sources"].add(s["sourceDbName"])
            for p in it.get("publications") or []:
                if p.get("pmid"):
                    c["dgidb_pmids"].add(str(p["pmid"]))
            for t in it.get("interactionTypes") or []:
                if t.get("type"):
                    c["dgidb_types"].add(t["type"])

    # --- merge with per-gene cap (OT-approved first, then sources, name)
    cand = {}
    for g in sorted(per_gene):
        ranked = sorted(
            per_gene[g].values(),
            key=lambda c: (0 if c["ot_stage"] == "APPROVAL" else 1,
                           -len(c["dgidb_sources"]),
                           sorted(c["names"])[0] if c["names"] else ""))
        for c in ranked[:per_gene_cap]:
            key = c.get("chembl_id") or f"name:{_norm(sorted(c['names'])[0])}"
            cur = cand.get(key)
            if cur is None:
                cand[key] = c
            else:
                for f in ("names", "dgidb_pmids", "dgidb_sources",
                          "dgidb_types"):
                    cur[f] |= c[f]
                cur["ot_stage"] = cur["ot_stage"] or c["ot_stage"]
            cand[key]["module_hits"].add(g)
            # per-edge DGIdb interaction types - the direction layer needs
            # to know WHICH module gene carries an inhibitory edge, not
            # just that some edge did (aggregate dgidb_types is too coarse)
            cand[key]["hit_types"].setdefault(g, set()).update(
                c["dgidb_types"])
    return cand, funnel


def resolve_chembl(http, cfg, cand):
    """Resolve 'name:*' candidates to ChEMBL ids where possible.

    Path per name: MyChem (INN + synonyms -> chembl id, also yields the
    DrugCentral block reused later).  Investigational code names
    (CC-115, AZD-8055, ...) are skipped when ``skip_code_names`` - they
    never resolve to an approved INN.  Bare names with a single DGIdb
    source, no typed interaction and no publication are skipped as a weak
    tail (they almost never map to an approved drug).  Returns (map, stats).
    """
    ep = cfg["endpoints"]
    col = cfg.get("collection", {})
    workers = int(cfg.get("workers", 1))
    stats = {"name_lookups": 0, "code_names_skipped": 0,
             "weak_names_skipped": 0}
    pending = []
    out = {}
    for key in sorted(cand):
        c = cand[key]
        if c.get("chembl_id"):
            out[key] = c
            continue
        name = sorted(c["names"])[0] if c["names"] else ""
        if col.get("skip_code_names", True) and _CODE_NAME.match(name.upper()):
            stats["code_names_skipped"] += 1
            out[key] = c
            continue
        # weak tail: a bare name from a single DGIdb source with no typed
        # interaction and no publication is almost never an approved drug -
        # skip the lookup, record it, keep the entry honest in the funnel
        if (len(c["dgidb_sources"]) <= 1 and not c["dgidb_types"]
                and not c["dgidb_pmids"]):
            stats["weak_names_skipped"] += 1
            out[key] = c
            continue
        pending.append((key, c))

    budget = col.get("max_unresolved_name_lookups", 400) \
        if col.get("chembl_name_lookup", True) else 0
    lookups = pending[:budget]
    stats["name_lookups"] = len(lookups)
    for key, c in pending[budget:]:
        out[key] = c

    def _lookup(item):
        key, c = item
        name = sorted(c["names"])[0]
        hit, _ = sources.mychem_drugcentral(http, ep["mychem"], name)
        cid = (hit.get("chembl") or {}).get("molecule_chembl_id") if hit else None
        return key, c, hit, cid

    for key, c, hit, cid in pmap(_lookup, lookups, workers):
        if hit:
            c["mychem"] = hit
        if cid:
            c["chembl_id"] = cid
            if cid in out and out[cid] is not c:
                for f in ("names", "module_hits", "dgidb_pmids",
                          "dgidb_sources", "dgidb_types"):
                    out[cid][f] |= c[f]
                for g, ts in c.get("hit_types", {}).items():
                    out[cid]["hit_types"].setdefault(g, set()).update(ts)
                out[cid]["ot_stage"] = out[cid]["ot_stage"] or c["ot_stage"]
            else:
                out[cid] = c
        else:
            out[key] = c
    stats["unresolved_names"] = sum(
        1 for c in out.values() if not c.get("chembl_id"))
    return out, stats


# ------------------------------------------------------- approval gate ----
def approval_gate(http, cfg, candidates):
    """approved = ChEMBL max_phase==4 and not withdrawn (batch lookup).
    Returns (approved list, funnel counts)."""
    ep = cfg["endpoints"]
    ap = cfg["approval"]
    funnel = {"gated_in": 0, "gated_out_no_chembl": 0,
              "gated_out_phase": 0, "gated_out_withdrawn": 0,
              "gated_out_unresolved": 0}
    resolved = [c for c in candidates.values() if c.get("chembl_id")]
    mols, _ = sources.chembl_molecules_batch(
        http, ep["chembl"], [c["chembl_id"] for c in resolved])
    approved = []
    for c in resolved:
        mol = mols.get(c["chembl_id"])
        if not mol:
            funnel["gated_out_no_chembl"] += 1
            continue
        c["molecule"] = mol
        if mol.get("withdrawn_flag") and ap.get("exclude_withdrawn", True):
            funnel["gated_out_withdrawn"] += 1
            continue
        try:
            phase = float(mol.get("max_phase"))
        except (TypeError, ValueError):
            phase = -1.0
        if phase != float(ap.get("max_phase", 4)):
            funnel["gated_out_phase"] += 1
            continue
        funnel["gated_in"] += 1
        approved.append(c)
    funnel["gated_out_unresolved"] += \
        sum(1 for c in candidates.values() if not c.get("chembl_id"))
    return approved, funnel


# --------------------------------------------------- per-drug evidence ----
def drug_evidence(http, cfg, c):
    """Fill in label/MoA/warning detail for one approved candidate."""
    ep = cfg["endpoints"]
    name = sorted(c["names"])[0] if c["names"] else \
        (c.get("molecule") or {}).get("pref_name", "").lower()
    mol = c.get("molecule") or {}
    ev = {"sources": ["chembl"]}

    # openFDA label: FDA presence + pediatric text + boxed warning
    label, _ = sources.openfda_label(http, ep["openfda"], name)
    fda = bool(label)
    ped = ""
    if label:
        pu = label.get("pediatric_use")
        ped = (pu[0] if isinstance(pu, list) and pu else
               pu if isinstance(pu, str) else "")[:800]
        ev["sources"].append("openfda")
    ev["fda"] = fda
    ev["boxed_warning"] = bool(label.get("boxed_warning")) or \
        bool(mol.get("black_box_warning"))
    ev["pediatric_labeling"] = ped
    ev["fda_set_id"] = label.get("set_id")

    # DrugCentral via MyChem: approval agencies + id (reuse resolution hit)
    dc_hit = c.get("mychem")
    if not dc_hit:
        dc_hit, _ = sources.mychem_drugcentral(http, ep["mychem"], name)
    agencies, dc_id = set(), None
    if dc_hit:
        dc = dc_hit.get("drugcentral") or {}
        if isinstance(dc, list):
            dc = next((x for x in dc if isinstance(x, dict)), {})
        dc_id = dc.get("id")
        appr = dc.get("approval") or []
        if isinstance(appr, dict):
            appr = [appr]
        for a in appr:
            if isinstance(a, dict) and a.get("agency"):
                agencies.add(a["agency"].upper())
        if dc:
            ev["sources"].append("drugcentral")
    ev["ema"] = "EMA" in agencies or any(
        (x.get("xref_src") == "EMA") for x in mol.get("cross_references") or [])
    ev["fda_dc"] = "FDA" in agencies
    ev["fda"] = ev["fda"] or ev["fda_dc"]
    ev["ema_only"] = bool(ev["ema"] and not ev["fda"])
    ev["dc_agencies"] = sorted(agencies)
    ev["drugcentral_id"] = dc_id

    # Open Targets drug record: MoA targets, warnings, stage
    ot, _ = sources.ot_drug(http, ep["opentargets"], c["chembl_id"])
    moa, targets, warns = "", set(), []
    action_types, moa_target_actions = set(), {}
    if ot:
        ev["sources"].append("opentargets")
        for r in ((ot.get("mechanismsOfAction") or {}).get("rows")) or []:
            at = r.get("actionType")
            if at:
                action_types.add(at)
            if not moa:
                moa = r.get("mechanismOfAction") or ""
            for t in r.get("targets") or []:
                if t.get("approvedSymbol"):
                    targets.add(t["approvedSymbol"])
                    if at:
                        moa_target_actions.setdefault(
                            t["approvedSymbol"], set()).add(at)
        warns = [{"type": w.get("warningType"),
                  "tox": w.get("toxicityClass")}
                 for w in ot.get("drugWarnings") or []]
        ev["ot_indication_count"] = (ot.get("indications") or {}).get("count")
    if not moa:
        mech, _ = sources.chembl_mechanism(http, ep["chembl"], c["chembl_id"])
        moa = "; ".join(sorted({m.get("mechanism_of_action")
                                for m in mech if m.get("mechanism_of_action")}))
        for m in mech:
            if m.get("action_type"):
                action_types.add(m["action_type"])
    ev["mechanism_of_action"] = moa
    ev["ot_warnings"] = warns
    ev["moa_targets"] = sorted(targets)
    ev["action_types"] = sorted(action_types)
    ev["moa_target_actions"] = {g: sorted(a)
                              for g, a in sorted(moa_target_actions.items())}
    return ev


# -------------------------------------------------------------- LINCS -----
def lincs_reversal(http, cfg):
    """Disease-proxy signature reversal on SigCom LINCS.

    Returns ({normalized_pert_key: {score, pert, cell_line, dose,
    signature_id}}, meta).  Degrades to ({}, meta) on any failure.
    """
    ep, lx = cfg["endpoints"], cfg.get("lincs", {})
    if not lx.get("enabled", True):
        return {}, {"source": "sigcom_lincs", "status": "disabled"}
    try:
        alias = {k.lower(): v.lower()
                 for k, v in (lx.get("alias_map") or {}).items()}
        up, down = lx.get("up_genes") or [], lx.get("down_genes") or []
        ents, _ = sources.lincs_entities(http, ep["lincs_meta"], up + down)
        up_ids = [ents[g] for g in up if g in ents]
        down_ids = [ents[g] for g in down if g in ents]
        if not up_ids and not down_ids:
            return {}, {"source": "sigcom_lincs", "status": "no_entities"}
        rows, _ = sources.lincs_rank_twosided(
            http, ep["lincs_data"], up_ids, down_ids,
            lx["library"], lx.get("result_limit", 100))
        rev = [r for r in rows if r.get("type") == "reversers"]
        sigs, _ = sources.lincs_signatures(
            http, ep["lincs_meta"], [r["uuid"] for r in rev])
        meta_by_id = {s["id"]: s.get("meta", {}) for s in sigs}
        out = {}
        for r in rev:
            m = meta_by_id.get(r.get("uuid"), {})
            pert = m.get("pert_name")
            if not pert:
                continue
            key = alias.get(pert.lower(), _drug_key(pert, alias))
            logp = float(r.get("logp-fisher", 0) or 0)
            cur = out.get(key)
            rec = {"score": logp, "pert": pert,
                   "cell_line": m.get("cell_line"),
                   "dose": m.get("pert_dose"),
                   "signature_id": r.get("uuid")}
            if cur is None or logp > cur["score"]:
                out[key] = rec
        return out, {"source": "sigcom_lincs", "status": "ok",
                     "library": lx["library"],
                     "n_reversers": len(rev), "n_named": len(out)}
    except Exception as e:  # noqa: BLE001 - any source failure degrades
        return {}, {"source": "sigcom_lincs", "status": "unavailable",
                    "note": f"{type(e).__name__}: {e}"}


# ---------------------------------------------------------------- case ----
def run_case(http, cfg, case):
    """Full engine for one case.

    ``case`` = {name, disease, disease_gene, seed_genes:[{symbol,role,axis}],
                run_lincs:bool}
    Returns the candidates.json-shaped dict.
    """
    ep = cfg["endpoints"]
    provenance = {}
    seed_symbols = [g["symbol"] for g in case["seed_genes"]]
    axis_map = {g["symbol"]: g.get("axis") for g in case["seed_genes"]}
    disease_gene = case["disease_gene"]

    # 1. disease module + routing universe
    module, partner_map, notes, meta = build_module(
        http, cfg, seed_symbols, disease_gene)
    provenance["string"] = meta
    universe = build_universe(http, cfg, module, partner_map)
    edges, meta = sources.string_network(http, ep["string"],
                                         sorted(universe),
                                         cfg["module"]["required_score"])
    adj = proximity.adjacency(edges, universe)

    # 2. candidates from module genes
    ensembl_cache = {}
    cand, funnel = collect_candidates(http, cfg, module, ensembl_cache)
    funnel["collected"] = len(cand)

    # deterministic global cap pre-resolution (disclosed backstop bound)
    cap = cfg.get("collection", {}).get("max_candidates", 800)
    ranked = sorted(cand.values(),
                    key=lambda c: (-len(c["module_hits"]),
                                   -len(c["dgidb_sources"]),
                                   sorted(c["names"])[0] if c["names"] else ""))
    kept = ranked[:cap]
    funnel["dropped_over_cap"] = len(ranked) - len(kept)
    cand = {c.get("chembl_id") or f"name:{_norm(sorted(c['names'])[0])}": c
            for c in kept}

    # resolve names -> ChEMBL ids, then approval gate
    cand, stats = resolve_chembl(http, cfg, cand)
    funnel.update(stats)
    approved, gate = approval_gate(http, cfg, cand)
    funnel.update(gate)

    # 4. LINCS signature reversal (MVA case only; skipped in benchmark)
    rev_map = {}
    if case.get("run_lincs", True):
        rev_map, provenance["sigcom_lincs"] = lincs_reversal(http, cfg)
    else:
        provenance["sigcom_lincs"] = {"source": "sigcom_lincs",
                                      "status": "skipped_benchmark"}

    # 5. per-drug evidence + proximity + scoring
    alias = {k.lower(): v.lower()
             for k, v in (cfg.get("lincs", {}).get("alias_map") or {}).items()}
    w = cfg["scoring"]["weights"]
    prox = cfg["proximity"]
    workers = int(cfg.get("workers", 1))
    rules = direction_mod.compile_rules(cfg)
    prism_index, prism_meta = prism_mod.load_index(cfg)
    evidences = pmap(lambda c: drug_evidence(http, cfg, c), approved, workers)
    out_cands = []
    for c, ev in zip(approved, evidences):
        targets = sorted(set(ev["moa_targets"]) | c["module_hits"])
        module_targets = sorted(t for t in targets if t in module)
        axes = sorted({axis_map[t] for t in module_targets
                       if axis_map.get(t)})
        axis = "+".join(axes) if axes else "none"

        zinfo = proximity.proximity_zscore(
            adj, module, targets, prox["n_random"], prox["random_seed"],
            prox["unreachable_distance"])

        mol = c.get("molecule") or {}
        display = (mol.get("pref_name") or sorted(c["names"])[0]).lower()

        rev = None
        for nm in sorted(c["names"]) or [display]:
            rev = rev_map.get(_drug_key(nm, alias)) or \
                rev_map.get(_norm(_drug_key(nm, alias)))
            if rev:
                break
        channels = {
            "target_overlap": scoring.channel_target_overlap(targets, module),
            "network_proximity": scoring.channel_proximity(
                zinfo["z"], prox["z_full"], prox["z_zero"]),
            "signature_reversal": scoring.channel_reversal(
                rev["score"] if rev else None,
                cfg["scoring"]["reversal_logp_cap"]),
            "interaction_evidence": scoring.channel_interactions(
                len(c["module_hits"])),
            "literature": scoring.channel_literature(len(c["dgidb_pmids"])),
        }
        score = scoring.score_candidate(channels, w)
        rationale = []
        if module_targets:
            rationale.append("targets_module:" + ",".join(module_targets))
        if zinfo["z"] is not None:
            rationale.append(f"proximity_z:{zinfo['z']}")
        if rev:
            rationale.append(f"lincs_reverser:{rev['pert']}@"
                             f"logp{round(rev['score'], 1)}")
        if c["module_hits"]:
            rationale.append("module_genes:" +
                             ",".join(sorted(c["module_hits"])))
        if c["dgidb_pmids"]:
            rationale.append(f"pmids:{len(c['dgidb_pmids'])}")

        # mechanism-direction layer + pediatric flag + PRISM overlay
        cand_dir = {
            "drug": display,
            "names": sorted(c["names"]) + [display],
            "mechanism_of_action": ev["mechanism_of_action"],
            "action_types": ev["action_types"],
            "targets": targets,
            "module_targets": module_targets,
            "moa_target_actions": ev["moa_target_actions"],
            "hit_types": c.get("hit_types", {}),
        }
        d_dir, d_reasons = direction_mod.classify(cand_dir, rules)
        ped_flag = direction_mod.pediatric_flag(ev["pediatric_labeling"])

        out_cands.append({
            "drug": display,
            "chembl_id": c["chembl_id"],
            "drugcentral_id": ev["drugcentral_id"],
            "approval": {
                "max_phase": int(float(mol.get("max_phase") or 0)),
                "fda": ev["fda"], "ema": ev["ema"],
                "ema_only": ev["ema_only"],
                "first_approval": mol.get("first_approval"),
                "withdrawn": bool(mol.get("withdrawn_flag")),
                "pediatric_labeling": ev["pediatric_labeling"],
                "evidence": ev["sources"],
            },
            "targets": targets,
            "module_targets": module_targets,
            "moa_targets": ev["moa_targets"],
            "action_types": ev["action_types"],
            "moa_target_actions": ev["moa_target_actions"],
            "hit_types": {g: sorted(t)
                          for g, t in sorted(c.get("hit_types", {})
                                             .items())},
            "axis": axis,
            "mechanism_of_action": ev["mechanism_of_action"],
            "direction": d_dir,
            "direction_reasons": d_reasons,
            "pediatric_flag": ped_flag,
            "evidence": {
                "target_overlap": channels["target_overlap"],
                "network_proximity_z": zinfo["z"],
                "network_distance": zinfo["distance"],
                "signature_reversal": (
                    {"score": channels["signature_reversal"],
                     "logp": round(rev["score"], 3),
                     "signature": rev["pert"],
                     "signature_id": rev["signature_id"],
                     "source": "sigcom-lincs",
                     "cell_line": rev["cell_line"]}
                    if rev else {"score": 0.0, "signature": None,
                                 "source": "sigcom-lincs"}),
                "prism_aneuploidy": prism_mod.annotate(
                    prism_index, sorted(c["names"]) + [display]),
                "literature": len(c["dgidb_pmids"]),
            },
            "channels": {k: round(v, 4) for k, v in channels.items()},
            "score": score,
            "tier": scoring.tier(score, channels, cfg["scoring"]["tiers"],
                                 cfg["scoring"]["t1_min_channels"]),
            "rationale_keys": rationale,
            "warnings": {"black_box": ev["boxed_warning"],
                         "openfda_boxed": bool(ev["boxed_warning"]),
                         "ot_warnings": ev["ot_warnings"]},
            "pediatric_labeling": ev["pediatric_labeling"],
            "fda_set_id": ev["fda_set_id"],
            "dgidb": {"module_hits": sorted(c["module_hits"]),
                      "sources": sorted(c["dgidb_sources"]),
                      "interaction_types": sorted(c["dgidb_types"]),
                      "n_pmids": len(c["dgidb_pmids"])},
            "ot_stage": c.get("ot_stage"),
            "dc_agencies": ev["dc_agencies"],
        })

    out_cands.sort(key=lambda c: (-c["score"], c["drug"]))
    for i, c in enumerate(out_cands, 1):
        c["rank_before_direction"] = i

    # mechanism-direction split: opposed candidates leave the ranked list
    # and keep their would-be rank + rule reasons for transparency
    ranked = [c for c in out_cands if c["direction"] != "opposed"]
    excluded = [c for c in out_cands if c["direction"] == "opposed"]
    for i, c in enumerate(ranked, 1):
        c["rank"] = i
    rules_fired = {}
    for c in out_cands:
        for r in c["direction_reasons"]:
            rules_fired[r] = rules_fired.get(r, 0) + 1
    direction_summary = {
        "enabled": bool(rules),
        "version": (cfg.get("direction") or {}).get("version"),
        "added_after_freeze": (cfg.get("direction") or {}).get("added"),
        "n_rules": len(rules),
        "rules_fired": dict(sorted(rules_fired.items())),
        "n_opposed_excluded": len(excluded),
        "n_aligned": sum(1 for c in ranked if c["direction"] == "aligned"),
        "n_neutral": sum(1 for c in ranked if c["direction"] == "neutral"),
        "note": "opposed candidates are removed from `candidates` and kept "
                "in `excluded_mechanism_opposed` with their would-be rank; "
                "scoring is unchanged - this layer filters direction, it "
                "does not re-weight evidence",
    }
    n_prism_matched = sum(
        1 for c in out_cands
        if c["evidence"]["prism_aneuploidy"].get("status") == "screened")

    return {
        "schema": "t2.candidates/1",
        "generated_by": "tools/run_track2.py",
        "generated_at": datetime.now(timezone.utc)
                        .replace(microsecond=0).isoformat(),
        "case": {"name": case["name"], "disease": case["disease"],
                 "disease_gene": disease_gene,
                 "hpo_terms": case.get("hpo_terms", []),
                 "variants": case.get("variants", [])},
        "seed_genes": case["seed_genes"],
        "module": {"genes": sorted(module), "n": len(module),
                   "universe_nodes": len(universe), "universe_edges": len(edges),
                   "build_notes": notes},
        "provenance": provenance,
        "funnel": funnel,
        "lincs": provenance.get("sigcom_lincs"),
        # raw candidate space (pre-gate) - lets the benchmark report the
        # exact stage at which a known drug dropped out
        "collected_names": sorted({_norm(n) for c in kept
                                 for n in c["names"]}),
        "direction": direction_summary,
        "prism": {**prism_meta,
                  "n_candidates_screened": n_prism_matched,
                  "n_candidates_not_in_screen":
                      len(out_cands) - n_prism_matched},
        "excluded_mechanism_opposed": excluded,
        "candidates": ranked,
    }
