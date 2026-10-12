"""Render the Track 2 report from the evidence layer - no hand-typed numbers.

    python tools/make_track2_report.py                       # docs/track2_report.md
    python tools/make_track2_report.py --upload              # + nikhilpise_track2_report.md

Inputs (all under docs/track2/evidence/, each produced by a tool or a
logged curation step):
    mechanism.json      tools/t2_mechanism.py         per-allele + pathway
    candidates.json     tools/run_track2.py           engine ranking
    benchmark.json      tools/run_track2.py --benchmark
    prism.json          tools/t2_prism.py             aneuploidy pharmacogenomics
    esm.json            tools/t2_esm.py               protein-LM variant effect
    dossiers/*.json     curated literature layer (L3)
    rejected.json       considered-and-rejected
    testability.json    candidate x MVA Society program matrix
    portfolio.json      the integrated ranking decision (lead), citing the above
Template: docs/track2_report_template.md ({{PLACEHOLDER}} blocks). A
missing input renders as an explicit PENDING note, never as invented text.
Citations render as PubMed/DOI links; the reference list is built from the
committed citation cache (docs/track2/citation_cache.json) so every title in
the report is the registry's own title, not a model's recollection.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
EV = REPO / "docs" / "track2" / "evidence"
TEMPLATE = REPO / "docs" / "track2_report_template.md"
OUT = REPO / "docs" / "track2_report.md"
UPLOAD = REPO / "nikhilpise_track2_report.md"
CACHE = REPO / "docs" / "track2" / "citation_cache.json"
PENDING = "> *PENDING - input artifact not yet produced; this section fills on regeneration.*"
CITE_RE = re.compile(r"(PMID:\d+|DOI:10\.[^\s,;)\]]+|PMCID:PMC\d+)")
AXIS_NAME = {"A": "A - residual-BubR1 rescue",
             "B": "B - senescence / damage mitigation",
             "C": "C - aneuploid-cell vulnerability / cancer interception"}
PROGRAM_NAME = {"worm_repurposing_screen": "Worm repurposing screen",
                "patient_fibroblasts": "Patient fibroblasts",
                "multi_patient_scrnaseq": "Multi-patient scRNA-seq",
                "supplements_cell_health": "Supplements & cell health"}


def load(name: str):
    p = EV / name
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


# ---------------------------------------------------------------- citations

class Refs:
    """Collects citations in first-use order for the reference list."""

    def __init__(self, cache: dict):
        self.cache = cache
        self.order: list[str] = []

    def link(self, cid: str) -> str:
        if cid not in self.order:
            self.order.append(cid)
        if cid.startswith("PMID:"):
            return f"[{cid}](https://pubmed.ncbi.nlm.nih.gov/{cid[5:]}/)"
        if cid.startswith("DOI:"):
            return f"[{cid}](https://doi.org/{cid[4:]})"
        if cid.startswith("PMCID:"):
            return f"[{cid}](https://pmc.ncbi.nlm.nih.gov/articles/{cid[6:]}/)"
        return cid

    def bare(self, ids) -> str:
        return "; ".join(self.link(i) for i in (ids or []) if i)

    def cites(self, ids) -> str:
        b = self.bare(ids)
        return f" ({b})" if b else ""

    def linkify(self, text: str) -> str:
        """Turn bare PMID:/DOI: tokens in free text into links."""
        return CITE_RE.sub(lambda m: self.link(m.group(1)), text or "")

    def register_text(self, text: str) -> None:
        for m in CITE_RE.finditer(text):
            if m.group(1) not in self.order:
                self.order.append(m.group(1))

    def table(self) -> str:
        rows = ["| # | Identifier | Title (as registered) | Year |", "|---|---|---|---|"]
        for n, cid in enumerate(self.order, 1):
            e = self.cache.get(cid) or {}
            title = (e.get("title") or "(not in cache - run tools/verify_citations.py)").replace("|", "/")
            rows.append(f"| {n} | {self.link(cid)} | {title} | {e.get('year') or ''} |")
        return "\n".join(rows)


def md_cell(s) -> str:
    return str(s if s is not None else "").replace("|", "/").replace("\n", " ")


# ---------------------------------------------------------------- mechanism

def allele_table(m: dict | None, refs: Refs) -> str:
    if not m:
        return PENDING
    rows = ["| | Allele 1 | Allele 2 |", "|---|---|---|"]
    a, b = m["alleles"][0], m["alleles"][1]

    def g(al, *path, default="-"):
        cur = al
        for k in path:
            if not isinstance(cur, dict) or cur.get(k) is None:
                return default
            cur = cur[k]
        return cur

    def nmd(al):
        n = al.get("nmd") or {}
        if not n:
            return "-"
        verdict = "predicted NMD" if n.get("predicted_nmd") else "escapes NMD"
        return f"{verdict} ({n.get('note', '')})"

    def gn(al, src):
        x = g(al, "gnomad", src, default=None)
        if not x or not x.get("an") or not x.get("ac"):
            return "absent"
        return f"{x['ac']}/{x['an']} (AF {x['af']:.1e}; hom {x.get('homozygote_count', 0)})"

    def am(al):
        x = g(al, "vep", "alphamissense", default=None)
        return f"{x['am_pathogenicity']} ({x['am_class']})" if x else "n/a (truncating)"

    def clin(al):
        # Position searches return every allele at the site; only a record
        # whose title names this exact cDNA change describes this variant.
        recs = [r for r in g(al, "clinvar", "records", default=[]) or []
                if f"{al['cdna']} " in r.get("title", "") or r.get("title", "").endswith(al["cdna"])]
        if not recs:
            return md_cell(al.get("clinvar_note") or "no record for this exact change")
        r = recs[0]
        return f"{r['classification']} - {r['review_status']} ({r['accession']})"

    def loss(al):
        pl = al.get("protein_loss")
        if not pl:
            return "full-length protein"
        return (f"{pl['truncated_product_length']}-aa product, "
                f"{pl['fraction_lost_pct']}% lost incl. kinase-like domain")

    def struct(al):
        s = al.get("structure") or {}
        if not s:
            return "-"
        bur = s.get("burial") or {}
        return (f"pLDDT {s.get('plddt')}; {s.get('n_residues_within_8a_allatom')} residues within 8 A; "
                f"contact number at the {bur.get('percentile_in_domain')}th percentile of the domain")

    fields = [
        ("Genomic (GRCh38)", lambda al: al["hgvs_genomic"]),
        ("cDNA / protein (NM_001211.6)", lambda al: f"{al['cdna']} {al['protein']}"),
        ("Consequence (VEP)", lambda al: ", ".join(g(al, "vep", "consequence_terms", default=[]))),
        ("Exon", lambda al: f"{g(al, 'exon', 'index')}/{g(al, 'exon', 'of')}"),
        ("NMD (50-55 nt rule)", nmd),
        ("Protein consequence", loss),
        ("CADD phred / phyloP", lambda al: f"{g(al, 'vep', 'cadd_phred')} / {g(al, 'vep', 'phylop470way_mammalian')}"),
        ("AlphaMissense", am),
        ("REVEL / SIFT / PolyPhen", lambda al: f"{g(al, 'vep', 'revel')} / {g(al, 'vep', 'sift_score')} / {g(al, 'vep', 'polyphen_score')}"),
        ("AlphaFold context", struct),
        ("gnomAD v4 exomes", lambda al: gn(al, "exome")),
        ("gnomAD v4 genomes", lambda al: gn(al, "genome")),
        ("ClinVar", clin),
        ("Interpretation", lambda al: al.get("interpretation") or "-"),
    ]
    for label, fn in fields:
        try:
            va, vb = fn(a), fn(b)
        except (KeyError, TypeError):
            continue
        rows.append(f"| {label} | {md_cell(va)} | {md_cell(vb)} |")
    rows.append("")
    rows.append("Sources: Ensembl REST VEP + transcript model, UniProt O60566, "
                "AlphaFold DB v6, gnomAD v4 GraphQL, ClinVar E-utilities - raw "
                "responses replayed from `tests/fixtures/track2/mechanism/` "
                "[repo:tools/t2_mechanism.py]" + refs.cites(["DOI:10.1093/nar/gkab1049"]) + ".")
    return "\n".join(rows)


def claim_list(items, refs: Refs, text_key="text", lead_key=None) -> str:
    out = []
    for it in items or []:
        lead = f"**{md_cell(it.get(lead_key))}** - " if lead_key and it.get(lead_key) else ""
        out.append(f"- {lead}{refs.linkify(it.get(text_key) or it.get('claim', ''))}"
                   f"{refs.cites(it.get('cites'))}")
    return "\n".join(out) if out else PENDING


def pathway_table(m: dict | None, refs: Refs) -> str:
    if not m:
        return PENDING
    rows = ["| Step | Claim | Evidence | Sources |", "|---|---|---|---|"]
    for s in m["pathway"]:
        rows.append(f"| {md_cell(s['step'])} | {md_cell(s['claim'])} | "
                    f"{md_cell(s.get('evidence'))} | {refs.bare(s.get('cites'))} |")
    return "\n".join(rows)


# ---------------------------------------------------------------- engine

def _ped(x: dict) -> str:
    flag = x.get("pediatric_flag")
    if flag:
        return {"labeled_pediatric_indication": "labeled pediatric indication",
                "pediatric_text_only": "pediatric text only", "none": "none"}.get(flag, flag)
    return "label text" if (x.get("approval") or {}).get("pediatric_labeling") else "-"


def engine_section(c: dict | None, refs: Refs) -> str:
    if not c:
        return PENDING
    f = c.get("funnel") or {}
    cands = c.get("candidates") or []
    opposed = c.get("excluded_mechanism_opposed") or []
    lincs = c.get("lincs") or {}
    head = (f"**Funnel (MVA run, config sha `{str(c.get('config_sha', ''))[:12]}`).** Disease module: "
            f"{f.get('module_genes')} genes (seeds + STRING neighbours of BUB1B at score >= 700). "
            f"{f.get('ot_rows')} Open Targets clinical rows and {f.get('dgidb_interactions')} DGIdb "
            f"interactions -> {f.get('collected')} distinct drug names -> approval gate: "
            f"{f.get('gated_in')} approved, {f.get('gated_out_phase')} not phase 4, "
            f"{f.get('gated_out_withdrawn')} withdrawn, {f.get('gated_out_unresolved')} unresolvable "
            f"names (investigational codes or non-drug entities, counted rather than guessed). "
            f"LINCS L1000 reversal: status `{lincs.get('status')}`, {lincs.get('n_reversers')} reversers "
            f"on `{lincs.get('library')}`.")
    if opposed:
        head += (f" The mechanism-direction layer then removed **{len(opposed)} mechanism-opposed** "
                 f"approved drugs (genotoxic, aneugenic, antimitotic or checkpoint-weakening - section 3) "
                 f"from the ranking; they are listed, not hidden, in the evidence file.")
    rows = ["| Rank | Drug | Module targets | Axis | Direction | Tier | Score | Pediatric label |",
            "|---|---|---|---|---|---|---|---|"]
    for i, x in enumerate(cands[:20], 1):
        tg = ", ".join(x.get("module_targets") or x.get("targets") or [])
        rows.append(f"| {i} | {md_cell(x['drug'])} | {md_cell(tg)} | "
                    f"{md_cell(x.get('axis'))} | {md_cell(x.get('direction', '-'))} | {md_cell(x.get('tier'))} | "
                    f"{(x.get('score') or 0):.3f} | {_ped(x)} |")
    tail = ""
    if opposed:
        tail = ("\n\nTop mechanism-opposed exclusions (would-be rank, rule): " + "; ".join(
            f"{md_cell(x['drug'])} (#{x.get('rank_before_direction', '?')}, "
            f"{md_cell(', '.join(x.get('direction_reasons') or []))})" for x in opposed[:8]) + ".")
    return (head + "\n\n" + "\n".join(rows) + tail +
            "\n\nThe engine ranks *evidence density*, not suitability for this child: databases "
            "over-represent oncology, so the curated layer (section 5) and the pediatric facts decide "
            "the portfolio. Full output incl. every evidence channel: "
            "[repo:docs/track2/evidence/candidates.json].")


RECALL_KEYS = ("recall_at_1", "recall_at_5", "recall_at_10", "recall_at_25")


def benchmark_section(b: dict | None, refs: Refs) -> str:
    if not b:
        return PENDING
    rows = ["| Disease gene | Disease | Known approved drug(s): rank in engine output | Evidence for the known pair |",
            "|---|---|---|---|"]
    for case in b.get("cases") or []:
        kd = []
        for k in case.get("known_drugs") or []:
            if k.get("found") and k.get("rank"):
                kd.append(f"{k['drug']}: #{k['rank']}")
            else:
                kd.append(f"{k['drug']}: {str(k.get('stage', 'not found')).replace('_', ' ')}")
        ids = [f"PMID:{c['pmid']}" for c in case.get("citations") or [] if c.get("pmid")]
        rows.append(f"| {md_cell(case.get('gene'))} | {md_cell(case.get('disease'))} | "
                    f"{md_cell('; '.join(kd))} | {refs.bare(ids)} |")
    rec = " / ".join(f"{b[k]:.2f}" for k in RECALL_KEYS if isinstance(b.get(k), (int, float)))
    v1 = b.get("v1_frozen")
    v1s = ""
    if isinstance(v1, dict):
        v1s = (" (frozen pre-direction-layer run: "
               + " / ".join(f"{v1[k]:.2f}" for k in RECALL_KEYS if k in v1) + ")")
    return (f"The identical pipeline, run blind on {b.get('n_cases')} genes whose approved repurposed or "
            f"targeted drug is established (truth committed in `config/track2.yaml` before the run; the "
            f"drug is never seeded). **recall@1 / @5 / @10 / @25 = {rec}**{v1s} "
            f"[repo:docs/track2/evidence/benchmark.json].\n\n" + "\n".join(rows) +
            "\n\n**Reading it honestly.** Every miss is structural: the known drug acts on a target "
            "outside the disease gene's interaction module (for example losartan acts on the angiotensin "
            "receptor, not on FBN1's partners), so a target-overlap engine never collects it. Recall is "
            "therefore a floor on what network-seeded repurposing can do, and it is why this report pairs "
            "the engine with a mechanism-led literature layer rather than trusting either alone.")


def prism_section(p: dict | None, refs: Refs) -> str:
    if not p:
        return PENDING
    a = p["aneuploidy"]
    cs = (p.get("positive_controls") or {}).get("cohensharir_supptable5_concordance") or {}
    top = a.get("top_aneuploid_selective_launched") or []
    qs = [x["q"] for x in (a.get("all_results") or top)
          if x.get("phase") == "Launched" and isinstance(x.get("q"), (int, float))]
    min_q = f"{min(qs):.3f}" if qs else "n/a"
    rows = ["| Launched drug (Broad annotation) | MOA | beta (AUC ~ aneuploidy, lineage-adjusted) | p | q (BH) | lines |",
            "|---|---|---|---|---|---|"]
    for x in top[:8]:
        rows.append(f"| {md_cell(x['name'])} | {md_cell(x.get('moa'))} | {x['beta']:.4f} | {x['p']:.2g} | "
                    f"{x['q']:.2f} | {x['n_lines']} |")
    ids = [f"DOI:{p['references']['prism']['doi']}", f"DOI:{p['references']['aneuploidy']['doi']}"]
    return (f"Model: {md_cell(p.get('model'))}. {a.get('n_launched_tested')} launched compounds tested "
            f"(of {a.get('n_compounds_tested')}){refs.cites(ids)}. **Validation:** our per-drug "
            f"statistics reproduce the published PRISM-aneuploidy analysis (Spearman rho = "
            f"{cs.get('spearman_rho', float('nan')):.2f}, sign concordance {cs.get('sign_concordance', 0):.0%}, "
            f"n = {cs.get('n_matched')} drugs). **Result:** no launched drug is aneuploidy-selective after "
            f"FDR correction (minimum q = {min_q}); the top directional hits are listed only as "
            f"hypothesis-generating:\n\n" + "\n".join(rows) +
            "\n\nTwo findings shape the portfolio: mitotic/checkpoint drugs are mostly *aneuploid-resistant* "
            "in this short-exposure screen (supporting their place in the rejected table), and metformin, "
            "chloroquine and hydroxychloroquine are absent from the screen, so no PRISM claim is made for "
            "them. Full results and controls: [repo:docs/track2/evidence/prism.json].")


def esm_section(e: dict | None, refs: Refs, small: dict | None = None) -> str:
    """Headline model (esm.json) side by side with the smaller model run
    (esm_150m.json) on identical inputs - the model-size disagreement is
    reported, not hidden."""
    if not e:
        return PENDING
    runs = [(e, "esm.json")] + ([(small, "esm_150m.json")] if small else [])
    rows = ["| Model (run) | LLR p.Asn1002Lys | More damaging than ... of gnomAD BUB1B missense | "
            "... of benign panel | AUC common vs ultra-rare gnomAD | AUC benign vs nonsense proxy |",
            "|---|---|---|---|---|---|"]
    for d, fname in runs:
        q, c = d["query"], d["calibration"]
        where = (d.get("compute") or {}).get("gpu") or d["model"].get("device")
        rows.append(f"| {d['model']['model'].split('/')[-1]} ({where}, [repo:docs/track2/evidence/{fname}]) | "
                    f"{q['llr']:.2f} | {q['deleteriousness_percentile_vs_gnomad_missense']:.0f}% | "
                    f"{q['deleteriousness_percentile_vs_benign_panel']:.0f}% | "
                    f"{c['auc_gnomad_common_vs_ultrarare']:.2f} | {c['auc_clinvar_benign_vs_nonsense_proxy']:.2f} |")
    c = e["calibration"]
    n_bg = e["inputs"]["gnomad"]["n_missense"]
    return ("\n".join(rows) + "\n\n"
            f"Masked-marginal log-likelihood ratios over {c['n_scored']} scored variants "
            f"({n_bg} gnomAD v4 BUB1B missense as background; the query itself, seen once in gnomAD, "
            f"is excluded from it). Only {c['clinvar_pathogenic_missense']['n']} classified pathogenic "
            f"BUB1B missense exists in ClinVar, so a missense-only pathogenicity AUC cannot be estimated. "
            "The larger model places p.Asn1002Lys among the most constrained substitutions in the "
            "protein while the smaller one scores it mid-distribution; we cite the larger model, which "
            "also separates the gnomAD frequency classes better, and report both. A conservation "
            "score does not measure residual function: a strongly constrained residue is compatible "
            "with a hypomorphic, partially functional product.")


# ---------------------------------------------------------------- portfolio

def dossier(drug_key: str) -> dict | None:
    p = EV / "dossiers" / f"{drug_key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else None


def engine_rank(drugs: list[str], cands: dict | None) -> str:
    """Where the engine placed each of a lead's drugs - looked up at render
    time so the table can never disagree with candidates.json."""
    if not cands:
        return "-"
    def same(name: str, k: str) -> bool:      # "dasatinib anhydrous" is dasatinib
        name = name.lower()
        return name == k or name.startswith(k + " ")

    ranked = [x["drug"] for x in cands.get("candidates") or []]
    opposed = [x["drug"] for x in cands.get("excluded_mechanism_opposed") or []]
    out = []
    for d in drugs:
        k = d.lower()
        hit = next((i for i, n in enumerate(ranked) if same(n, k)), None)
        if hit is not None:
            out.append(f"{d} #{hit + 1}/{len(ranked)}")
        elif any(same(n, k) for n in opposed):
            out.append(f"{d}: excluded (opposed)")
        else:
            out.append(f"{d}: not in module")
    return "; ".join(out)


def shortlist_table(port: dict | None, refs: Refs, cands: dict | None = None) -> str:
    if not port:
        return PENDING
    rows = ["| Rank | Candidate | Axis | Approval (checked by code) | Pediatric label | Evidence grade | Engine placement |",
            "|---|---|---|---|---|---|---|"]
    for item in port["ranked"]:
        d = dossier(item["dossier"]) or {}
        ap = d.get("approval") or {}
        ped = (d.get("pediatric") or {}).get("approved_pediatric_indication") or "-"
        rows.append(
            f"| {item['rank']} | **{md_cell(item['label'])}** | {md_cell(AXIS_NAME.get(d.get('axis'), d.get('axis')))} | "
            f"ChEMBL max_phase {ap.get('chembl_max_phase')}, first approval {ap.get('chembl_first_approval', '-')}; "
            f"openFDA set_id `{str(ap.get('openfda_label_set_id', ''))[:8]}` | {md_cell(ped)[:160]} | "
            f"{md_cell(item.get('grade'))} | {md_cell(engine_rank(item.get('engine_drugs') or [], cands))} |")
    return "\n".join(rows)


def lead_sections(port: dict | None, refs: Refs) -> str:
    if not port:
        return PENDING
    out = []
    for item in port["ranked"]:
        d = dossier(item["dossier"])
        if not d:
            continue
        ped = d.get("pediatric") or {}
        out.append(f"### {item['rank']}. {item['label']}\n")
        out.append(f"*Why it is here:* {refs.linkify(item['why'])}\n")
        out.append("*Evidence:*\n")
        for c in d["claims"]:
            out.append(f"- [{md_cell(c.get('kind', ''))}, {md_cell(c.get('strength', ''))}] "
                       f"{refs.linkify(c['text'])}{refs.cites(c['cites'])}")
        out.append("")
        out.append(f"*Pediatric label facts* ({md_cell(ped.get('label_source'))}): "
                   f"{refs.linkify(md_cell(ped.get('approved_pediatric_indication')))} "
                   f"Boxed warning: {md_cell(ped.get('boxed_warning'))}")
        risks = ped.get("key_risks") or []
        if risks:
            out.append("\n*Risks specific to this child's phenotype:*\n")
            out += [f"- {refs.linkify(md_cell(r))}" for r in risks]
        if item.get("falsifier"):
            out.append(f"\n*What would make us wrong:* {refs.linkify(item['falsifier'])}")
        out.append("")
    return "\n".join(out)


def adjunct_list(port: dict | None, refs: Refs) -> str:
    if not port:
        return PENDING
    return "\n".join(f"- **{md_cell(a['label'])}** - {refs.linkify(a['why'])}"
                     for a in port.get("adjuncts") or []) or "-"


def rejected_table(r: dict | None, refs: Refs) -> str:
    if not r:
        return PENDING
    rows = ["| Considered | Category | Why rejected | Sources |", "|---|---|---|---|"]
    for e in r["entries"]:
        ids = sorted(set(CITE_RE.findall(json.dumps(e))))
        reason = CITE_RE.sub("", e["reason"])
        reason = re.sub(r"\s*\([\s;,]*\)", "", reason)          # emptied "(PMID:x; ...)"
        reason = re.sub(r"\s+([;,.])", r"\1", reason).strip()
        rows.append(f"| {md_cell(e['drug'])} | {md_cell(e.get('category'))} | {md_cell(reason)} | "
                    f"{refs.bare(ids)} |")
    return "\n".join(rows)


def testability_section(t: dict | None, refs: Refs) -> str:
    if not t:
        return PENDING
    progs = t["programs"]
    rows = ["| Candidate | " + " | ".join(PROGRAM_NAME.get(p, p) for p in progs) + " |",
            "|---" * (len(progs) + 1) + "|"]
    for line in t["matrix"]:
        by = {e["program"]: e for e in line["entries"]}
        cells = []
        for p in progs:
            e = by.get(p)
            cells.append(md_cell(f"{e['readout']}; GO: {e['go_no_go']} ({e['cost_tier']}, {e['time_to_result']})")
                         if e else "-")
        rows.append(f"| **{md_cell(line['drug'])}** | " + " | ".join(cells) + " |")
    core = "\n".join(f"- {refs.linkify(md_cell(x))}" for x in t.get("fibroblast_core_readouts") or [])
    tiers = ", ".join(f"{k}: {v}" for k, v in (t.get("cost_tiers") or {}).items())
    return ("\n".join(rows) + f"\n\nCost tiers - {tiers}.\n\n**Fibroblast core readouts:**\n\n{core}\n\n"
            f"**Decision logic:** {refs.linkify(md_cell(t.get('decision_logic')))}")


def screen_counts(md_path: Path) -> dict | None:
    """Recompute the literature-screen flow from the query-log table in
    candidates.md (section 1), so the report cannot drift from the log."""
    if not md_path.is_file():
        return None
    text = md_path.read_text(encoding="utf-8")
    sec = text.split("## 1.", 1)[-1].split("\n## ", 1)[0]
    queries = hits = screened = 0
    for line in sec.splitlines():
        c = [x.strip() for x in line.split("|")]
        if len(c) < 6 or not c[1].isdigit():
            continue
        if c[3].isdigit():
            queries += 1
            hits += int(c[3])
        if c[4].isdigit():
            screened += int(c[4])
    papers = len(set(re.findall(r"PMID:(\d+)", text)))
    return {"queries": queries, "hits": hits, "screened": screened, "papers": papers}


def screen_section(_port=None) -> str:
    s = screen_counts(REPO / "docs" / "track2" / "candidates.md")
    if not s or not s["queries"]:
        return PENDING
    return (f"{s['queries']} PubMed queries, logged verbatim with hit counts and screening decisions, "
            f"returned {s['hits']:,} hits (per query, not de-duplicated) -> {s['screened']} "
            f"title/abstract screenings -> {s['papers']} distinct papers carried into the dossiers, the "
            f"programs file and the rejected table. Inclusion rule: an approved medicine (ChEMBL "
            f"max_phase 4 + openFDA label) or direct mechanistic evidence on BubR1 / SAC / aneuploid-cell "
            f"biology that maps to one. Supplements were demoted to adjuncts. No MVA-specific "
            f"drug-treatment paper exists, so every dossier is explicitly mechanistic extrapolation. "
            f"Query log: [repo:docs/track2/candidates.md].")


# ---------------------------------------------------------------- rigor

def citation_gate_line() -> str:
    proc = subprocess.run(
        [sys.executable, str(REPO / "tools" / "verify_citations.py"), "--offline", "--quiet",
         "--json", str(REPO / "docs" / "track2" / "_gate.json")],
        cwd=REPO, capture_output=True, text=True)
    p = REPO / "docs" / "track2" / "_gate.json"
    if not p.is_file():
        return PENDING
    rep = json.loads(p.read_text(encoding="utf-8"))
    p.unlink()
    s = rep["counts"]
    return (f"`tools/verify_citations.py --offline` over the whole Track 2 tree: "
            f"**{s['citations']} distinct citations, {s['unresolved']} unresolved, "
            f"{s['retracted']} retracted, {s['mismatch']} title/year mismatches, "
            f"{s['uncovered_claims']} uncovered claim sentences** (exit {proc.returncode}, "
            f"{s['http_requests']} network requests).")


def test_count_line() -> str:
    proc = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q",
                           "tests/test_t2_evidence.py", "tests/test_t2_mechanism.py",
                           "tests/test_verify_citations.py"]
                          + [str(p.relative_to(REPO)) for p in sorted((REPO / "tests").glob("test_track2_*.py"))]
                          + [str(p.relative_to(REPO)) for p in sorted((REPO / "tests").glob("test_t2_prism.py"))]
                          + [str(p.relative_to(REPO)) for p in sorted((REPO / "tests").glob("test_t2_esm.py"))],
                          cwd=REPO, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", proc.stdout)
    return f"{m.group(1)} Track 2 tests (network-free, recorded fixtures)" if m else "Track 2 tests"


GENAI = (
    "Two commercial GenAI products were used (operator-confirmed settings, "
    "2026-10-12): (1) **Cognition Devin Pro**, model SWE-2 Max, Data Controls "
    "training opt-out enabled (no training, zero data retention with model "
    "providers) - five headless lane agents (mechanism, engine, dossiers, rigor "
    "tooling, compute); (2) **Anthropic Claude Code, Claude Pro/Max consumer "
    "plan** (Claude Opus 5.5), model-training opt-out enabled, no feedback ever "
    "given - lead/orchestrator, integration, report generation, review. Both "
    "settings follow the organizers' 2026-09-28 guidance (discussion #2). Only "
    "the two published BUB1B variants and the 8 published HPO terms entered any "
    "prompt; no patient file was opened in Track 2. Every literature claim an "
    "agent produced was machine-resolved against PubMed/Crossref/DataCite "
    "before inclusion (section 9). Per-session ledger: `docs/llm_log.md`.")


def fill(template: str, mapping: dict) -> str:
    for k, v in mapping.items():
        template = template.replace("{{" + k + "}}", v)
    left = set(re.findall(r"\{\{[A-Z0-9_]+\}\}", template)) - {"{{REFERENCES}}"}
    if left:
        raise SystemExit(f"unfilled placeholders: {sorted(set(left))}")
    return template


def build() -> str:
    cache = (json.loads(CACHE.read_text(encoding="utf-8")).get("entries", {})
             if CACHE.is_file() else {})
    refs = Refs(cache)
    template = TEMPLATE.read_text(encoding="utf-8")
    m = load("mechanism.json")
    port = load("portfolio.json")
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO,
                          capture_output=True, text=True).stdout.strip()
    # Built in reading order, so the reference list numbers follow the text.
    mapping = {
        "GENERATED": f"{date.today().isoformat()} from commit `{head}`",
        "CITE_HANKS": refs.cites(["PMID:15475955", "PMID:20516114"]),
        "CITE_DOSAGE": refs.cites(["PMID:24825348", "PMID:23242215"]),
        "CITE_P16": refs.cites(["PMID:22048312"]),
        "CITE_COHEN": refs.cites(["PMID:33505028"]),
        "ALLELE_TABLE": allele_table(m, refs),
        "PATHWAY_TABLE": pathway_table(m, refs),
        "UNCERTAINTIES": claim_list((m or {}).get("uncertainties"), refs),
        "THERAPEUTIC_AXES": claim_list((m or {}).get("therapeutic_implications"), refs, lead_key="axis"),
        "CONTRAINDICATIONS": claim_list((m or {}).get("contraindications"), refs, lead_key="agent"),
        "ENGINE_SECTION": engine_section(load("candidates.json"), refs),
        "BENCHMARK_SECTION": benchmark_section(load("benchmark.json"), refs),
        "PRISM_SECTION": prism_section(load("prism.json"), refs),
        "ESM_SECTION": esm_section(load("esm.json"), refs, load("esm_150m.json")),
        "SCREEN_SECTION": screen_section(port),
        "SHORTLIST_TABLE": shortlist_table(port, refs, load("candidates.json")),
        "LEAD_SECTIONS": lead_sections(port, refs),
        "ADJUNCTS": adjunct_list(port, refs),
        "REJECTED_TABLE": rejected_table(load("rejected.json"), refs),
        "TESTABILITY_SECTION": testability_section(load("testability.json"), refs),
        "CITATION_GATE": citation_gate_line(),
        "TEST_COUNT": test_count_line(),
        "GENAI_LINE": GENAI,
    }
    body = fill(template, {k: v for k, v in mapping.items()})
    refs.register_text(body)
    return body.replace("{{REFERENCES}}", refs.table())


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--upload", action="store_true",
                    help="also write the repo-root upload copy nikhilpise_track2_report.md")
    a = ap.parse_args(argv)
    text = build()
    if "—" in text:
        raise SystemExit("em dash in rendered report")
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(f"wrote {OUT.relative_to(REPO)} ({len(text.split())} words)")
    if a.upload:
        UPLOAD.write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {UPLOAD.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
