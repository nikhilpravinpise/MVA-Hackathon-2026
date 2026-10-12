"""Thin clients for the engine's evidence sources.

Every function takes a :class:`~src.track2.httpcache.CachedHttp` and returns
plain parsed JSON already trimmed to the fields the engine consumes.  All
remote field names were introspected live on 2026-10-12:

- Open Targets Platform GraphQL: ``target.drugAndClinicalCandidates``,
  ``drug { mechanismsOfAction, indications, drugWarnings,
  maximumClinicalStage }``, ``search`` for symbol -> Ensembl id.
- ChEMBL REST: ``/molecule``, ``/mechanism``.
- DGIdb v5 GraphQL: ``genes(names:) { interactions { drug { conceptId }
  interactionTypes sources publications } }``.
- STRING 12.5: ``interaction_partners``, ``network``, ``get_string_ids``,
  ``version``.
- openFDA: ``/drug/label.json`` (pediatric_use, boxed_warning).
- MyChem.info: ``/query`` -> ``drugcentral`` block (approval rows, id).
- SigCom LINCS: ``metadata-api/entities|signatures/find`` +
  ``data-api/v1/enrich/ranktwosided`` (data host reached via the 307
  redirect target of ``/sigcom-lincs/data-api``).

Each returns a ``(data, meta)`` tuple where ``meta`` records status and a
short provenance note for the output block.
"""
from __future__ import annotations

import re
import urllib.parse


def _meta(source: str, status: str, note: str = "") -> dict:
    return {"source": source, "status": status, "note": note}


# ------------------------------------------------------- Open Targets -----
_OT_DRUG_FIELDS = ("id name maximumClinicalStage drugType "
                   "mechanismsOfAction { rows { mechanismOfAction actionType "
                   "targets { id approvedSymbol } } } "
                   "indications { count } "
                   "drugWarnings { warningType toxicityClass }")


def ot_search_target(http, base, symbol):
    """symbol -> Ensembl gene id via OT search (exact approvedSymbol match)."""
    q = ('{ search(queryString: "%s", entityNames: ["target"], '
         'page: {index: 0, size: 10}) { hits { id name entity } } }'
         % symbol.replace('"', ""))
    status, d = http.post_json(base, {"query": q})
    hits = (((d or {}).get("data") or {}).get("search") or {}).get("hits", [])
    ensembl = None
    for h in hits:
        if h.get("name", "").upper() == symbol.upper() \
                and str(h.get("id", "")).startswith("ENSG"):
            ensembl = h["id"]
            break
    if ensembl is None and hits:
        ensembl = hits[0]["id"]
    return ensembl, _meta("opentargets", "ok" if ensembl else "no_hit",
                          f"{symbol} -> {ensembl}")


def ot_known_drugs(http, base, ensembl_id):
    """Ensembl id -> [{drug:{id,name,maxClinicalStage}, maxClinicalStage}]."""
    q = ('{ target(ensemblId: "%s") { approvedSymbol '
         'drugAndClinicalCandidates { count rows { drug { id name '
         'maximumClinicalStage } } } } }' % ensembl_id)
    status, d = http.post_json(base, {"query": q})
    tgt = (((d or {}).get("data") or {}).get("target")) or {}
    rows = ((tgt.get("drugAndClinicalCandidates") or {}).get("rows")) or []
    return rows, _meta("opentargets", "ok", f"{len(rows)} clinical rows")


def ot_drug(http, base, chembl_id):
    """ChEMBL id -> OT drug detail (MoA, targets, warnings, stage)."""
    q = '{ drug(chemblId: "%s") { %s } }' % (chembl_id, _OT_DRUG_FIELDS)
    status, d = http.post_json(base, {"query": q})
    drug = (((d or {}).get("data") or {}).get("drug")) or {}
    return drug, _meta("opentargets", "ok" if drug else "no_hit")


# ------------------------------------------------------------- ChEMBL -----
def chembl_molecule(http, base, chembl_id):
    status, m = http.get_json(f"{base}/molecule/{chembl_id}.json")
    return (m if isinstance(m, dict) else {}), \
        _meta("chembl", "ok" if status == 200 else f"http_{status}")


def chembl_molecule_by_name(http, base, name):
    """Resolve an INN/pref name -> molecule record (iexact, first hit)."""
    url = (f"{base}/molecule.json?pref_name__iexact="
           f"{urllib.parse.quote(name)}&limit=3")
    status, d = http.get_json(url)
    mols = (d or {}).get("molecules", []) if isinstance(d, dict) else []
    return (mols[0] if mols else {}), \
        _meta("chembl", "ok" if mols else "no_hit", f"name={name}")


def chembl_molecules_batch(http, base, chembl_ids, chunk=50):
    """Batch molecule records by ChEMBL id list -> {chembl_id: molecule}."""
    out = {}
    ids = sorted(set(chembl_ids))
    for i in range(0, len(ids), chunk):
        part = ",".join(ids[i:i + chunk])
        status, d = http.get_json(
            f"{base}/molecule.json?molecule_chembl_id__in={part}&limit={chunk}")
        for m in (d or {}).get("molecules", []) if isinstance(d, dict) else []:
            if m.get("molecule_chembl_id"):
                out[m["molecule_chembl_id"]] = m
    return out, _meta("chembl", "ok", f"{len(out)}/{len(ids)} molecules")


def chembl_mechanism(http, base, chembl_id):
    status, d = http.get_json(f"{base}/mechanism.json"
                              f"?molecule_chembl_id={chembl_id}&limit=50")
    mech = (d or {}).get("mechanisms", []) if isinstance(d, dict) else []
    return mech, _meta("chembl", "ok", f"{len(mech)} mechanism rows")


# -------------------------------------------------------------- DGIdb -----
def dgidb_gene_interactions(http, base, symbols, chunk=40):
    """Batch gene -> drug interactions. Returns {symbol: [interaction,...]}."""
    out = {}
    for i in range(0, len(symbols), chunk):
        part = symbols[i:i + chunk]
        names = ", ".join('"%s"' % s.replace('"', "") for s in part)
        q = ("{ genes(names: [%s]) { nodes { name interactions { "
             "drug { name approved conceptId } "
             "interactionTypes { type directionality } "
             "publications { pmid } "
             "sources { sourceDbName } } } } }" % names)
        status, d = http.post_json(base, {"query": q})
        nodes = (((d or {}).get("data") or {}).get("genes") or {}) \
            .get("nodes") or []
        for g in nodes:
            out[g.get("name")] = g.get("interactions") or []
    return out, _meta("dgidb", "ok", f"{len(out)} genes")


# -------------------------------------------------------------- STRING ----
def string_version(http, base):
    status, v = http.get_json(f"{base}/json/version")
    ver = v[0] if isinstance(v, list) and v else {}
    return ver.get("string_version", "unknown"), \
        _meta("string", "ok", ver.get("string_version", "?"))


def string_partners(http, base, symbol, limit, score):
    """Top STRING neighbours of one gene. Returns list of {name, score}."""
    url = (f"{base}/json/interaction_partners?identifiers={symbol}"
           f"&species=9606&required_score={score}&limit={limit}")
    status, rows = http.get_json(url)
    if not isinstance(rows, list):
        rows = []
    out = [{"name": r.get("preferredName_B"), "score": r.get("score")}
           for r in rows]
    return out, _meta("string", "ok", f"{symbol}: {len(out)} partners")


def string_network(http, base, symbols, score, chunk=180):
    """Edges among ``symbols`` (deduped). Returns [{a,b,score}]."""
    edges = {}
    uniq = sorted(set(symbols))
    for i in range(0, len(uniq), chunk):
        part = uniq[i:i + chunk]
        form = {"identifiers": "\r".join(part), "species": "9606",
                "required_score": str(score), "caller_identity": "mva_t2"}
        status, rows = http.post_form(f"{base}/json/network", form)
        if not isinstance(rows, list):
            continue
        for r in rows:
            a, b = r.get("preferredName_A"), r.get("preferredName_B")
            if a and b:
                edges[(a, b)] = float(r.get("score", 0))
    out = [{"a": a, "b": b, "score": s} for (a, b), s in sorted(edges.items())]
    return out, _meta("string", "ok", f"{len(out)} edges / {len(uniq)} nodes")


# ------------------------------------------------------------- openFDA ----
# L11 (2026-10-13) label-resolution hardening:
#  * ChEMBL-style pref_names carry form words openFDA never indexes
#    ("dasatinib anhydrous", "metformin hydrochloride"): each miss retries
#    the name with trailing salt/hydrate/form words stripped, repeatedly.
#  * When the top hit is a COMBINATION product (metformin -> the
#    sitagliptin+metformin ZITUVIMET label) a limit-5 refinement prefers
#    the first single-ingredient label whose actives still cover the
#    queried drug.  The combination hit is kept (and flagged) only when
#    no single-ingredient label is among the top hits.
#  * The primary request is unchanged (generic/substance, limit 1) so all
#    recorded fixtures replay identically; refinements/variant retries
#    are *additional* deterministic requests.
_FORM_WORDS = re.compile(
    r"\s+(?:anhydrous|hydrochloride|hydrobromide|sulfate|sulfide|sodium|"
    r"potassium|calcium|magnesium|zinc|mesylate|maleate|tartrate|"
    r"bitartrate|fumarate|succinate|mepesuccinate|phosphate|"
    r"diphosphate|citrate|acetate|lactate|nitrate|palmitate|pamoate|"
    r"propionate|cypionate|enanthate|decanoate|undecanoate|valerate|"
    r"benzoate|dimesylate|esylate|"
    r"besylate|besilate|tosylate|monohydrate|dihydrate|trihydrate|"
    r"hemihydrate|hydrate|hcl)\b.*$", re.I)


def openfda_name_variants(name):
    """Search-order name variants: the raw name, then the same name with
    trailing salt/hydrate/form words stripped (repeatedly).

    "dasatinib anhydrous" -> ["dasatinib anhydrous", "dasatinib"];
    "dextran sulfate sodium" -> [..., "dextran sulfate", "dextran"];
    "sodium chloride" -> ["sodium chloride"] (leading word kept).
    """
    out, cur = [], re.sub(r"\s+", " ", (name or "").strip().lower())
    while cur and cur not in out:
        out.append(cur)
        cur = _FORM_WORDS.sub("", cur).strip()
    return out


def _label_actives(label):
    """Active-ingredient name list from a label's openfda block."""
    of = (label or {}).get("openfda") or {}
    actives = [s.upper() for s in of.get("substance_name") or []]
    if not actives:
        actives = [g.upper() for g in of.get("generic_name") or []]
    return actives


def openfda_is_combo(label):
    """True when the label is a combination product: more than one active,
    or a single active string joining ingredients ('X AND Y', 'X, Y, Z')."""
    actives = _label_actives(label)
    if len(actives) > 1:
        return True
    return any((" AND " in a) or a.count(",") >= 2 for a in actives)


def openfda_pick_single(results, base):
    """First single-ingredient label in ``results`` whose actives cover
    ``base`` (the form-stripped drug name, compared uppercase)."""
    base = (base or "").upper()
    for r in results or []:
        if openfda_is_combo(r):
            continue
        if any(base in a or a in base for a in _label_actives(r)):
            return r
    return None


def _openfda_search(http, base, safe, limit=1, field=None):
    """One label search; returns the results list ([] on miss)."""
    if field:
        q = urllib.parse.quote(f'openfda.{field}:"{safe}"')
    else:
        q = urllib.parse.quote(
            f'openfda.generic_name:"{safe}" OR '
            f'openfda.substance_name:"{safe}"')
    url = f"{base}?search={q}&limit={limit}"
    status, d = http.get_json(url)
    return (d or {}).get("results", []) if isinstance(d, dict) else []


def _match_note(variant_index, variant, how):
    note = f"matched via {how}"
    if variant_index:
        note += f" on name variant '{variant}'"
    return note


def openfda_label(http, base, name):
    """Best label hit for a drug name.  Returns (label, meta).

    Order per name variant: generic/substance (limit 1, unchanged request)
    -> if that hit is a combination product, a limit-5 refinement
    preferring the first single-ingredient label still covering the drug
    -> brand_name (limit 1) -> next name variant (form words stripped).
    ``meta.note`` records which variant/label won; ``meta.combo`` is True
    when the label used is a combination product.
    """
    variants = openfda_name_variants(name)
    for vi, variant in enumerate(variants):
        safe = variant.replace('"', "").upper()
        res = _openfda_search(http, base, safe)
        if res:
            hit = res[0]
            if openfda_is_combo(hit):
                pick = openfda_pick_single(
                    _openfda_search(http, base, safe, limit=5),
                    variants[-1])
                if pick is not None:
                    m = _meta("openfda", "ok", _match_note(
                        vi, variant, "generic_name; single-ingredient "
                        "label preferred over combination hit"))
                    m["combo"] = False
                    return pick, m
                m = _meta("openfda", "ok", _match_note(
                    vi, variant, "generic_name; combination label kept - "
                    "no single-ingredient label in top hits"))
                m["combo"] = True
                return hit, m
            m = _meta("openfda", "ok",
                      _match_note(vi, variant, "generic_name"))
            m["combo"] = False
            return hit, m
        res = _openfda_search(http, base, safe, field="brand_name")
        if res:
            m = _meta("openfda", "ok",
                      _match_note(vi, variant, "brand_name"))
            m["combo"] = openfda_is_combo(res[0])
            return res[0], m
    return {}, _meta("openfda", "no_hit")


# ---------------------------------------------------- MyChem/DrugCentral --
def mychem_drugcentral(http, base, name):
    """DrugCentral block for a drug via MyChem.info (approval rows + id)."""
    url = (f"{base}/query?q={urllib.parse.quote(name)}"
           f"&fields=inn,drugcentral,chembl.molecule_chembl_id&size=5")
    status, d = http.get_json(url)
    hits = (d or {}).get("hits", []) if isinstance(d, dict) else []
    pick = {}
    lname = name.lower()
    for h in hits:
        dc = h.get("drugcentral") or {}
        inn = (h.get("inn") or "").lower()
        if dc and (inn == lname or not pick):
            pick = h
            if inn == lname:
                break
    return pick, _meta("mychem", "ok" if pick else "no_hit")


# --------------------------------------------------------- SigCom LINCS ---
def lincs_entities(http, meta_base, symbols):
    """symbols -> SigCom entity uuids {symbol: uuid}."""
    payload = {"filter": {"where": {"meta.symbol": {"inq": list(symbols)}},
                          "fields": ["id", "meta.symbol"]}}
    status, ents = http.post_json(f"{meta_base}/entities/find", payload)
    if not isinstance(ents, list):
        ents = []
    return {e.get("meta", {}).get("symbol"): e.get("id")
            for e in ents if e.get("meta", {}).get("symbol")}, \
        _meta("sigcom_lincs", "ok", f"{len(ents)} entities")


def lincs_rank_twosided(http, data_base, up_ids, down_ids, library, limit):
    """Two-sided signature search -> rows tagged mimickers/reversers."""
    payload = {"up_entities": list(up_ids), "down_entities": list(down_ids),
               "database": library, "limit": limit}
    status, d = http.post_json(f"{data_base}/enrich/ranktwosided", payload)
    rows = (d or {}).get("results", []) if isinstance(d, dict) else []
    return rows, _meta("sigcom_lincs", "ok", f"{len(rows)} signature hits")


def lincs_signatures(http, meta_base, uuids):
    """signature uuids -> perturbagen metadata."""
    if not uuids:
        return [], _meta("sigcom_lincs", "ok", "0 signatures")
    payload = {"filter": {"where": {"id": {"inq": list(uuids)}},
                          "fields": ["id", "meta.pert_name", "meta.pert_type",
                                     "meta.pert_dose", "meta.cell_line",
                                     "meta.local_id"]}}
    status, sigs = http.post_json(f"{meta_base}/signatures/find", payload)
    if not isinstance(sigs, list):
        sigs = []
    return sigs, _meta("sigcom_lincs", "ok", f"{len(sigs)} signatures")
