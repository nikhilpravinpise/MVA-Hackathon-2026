"""PRISM Repurposing x aneuploidy pharmacogenomic association (Track 2, lane L5).

    python tools/t2_prism.py fetch    --raw-dir <dir>   # download public inputs
    python tools/t2_prism.py derive   --raw-dir <dir>   # build small derived tables
    python tools/t2_prism.py analyze  --raw-dir <dir>   # regressions -> prism.json
    python tools/t2_prism.py run      --raw-dir <dir>   # all three

Data (all public, no patient data - docs/track2_plan.md section 5):
    PRISM Repurposing secondary screen (Corsello et al. 2020, Nat Cancer 1:235)
        secondary-screen-dose-response-curve-parameters.csv - per drug x cell
            line four-parameter curve fits (AUC is the sensitivity measure:
            lower AUC = stronger killing). figshare "PRISM Repurposing 19Q4".
        secondary-screen-cell-line-info.csv - depmap_id -> primary_tissue
    DepMap Public 19Q4 (figshare 11384241)
        CCLE_expression.csv  - BUB1B log2(TPM+1) column is extracted only
        CCLE_gene_cn.csv     - BUB1B copy-number column is extracted only
        sample_info.csv      - lineage cross-check
    Cohen-Sharir et al. 2021, Nature 590:486 supplementary tables (springer
        static-content): Table S1 per-line aneuploidy scores (n=997; AS =
        number of chromosome arms gained/lost vs basal ploidy), Table S2
        aneuploidy-associated genetic dependencies, Table S5 aneuploidy-
        associated chemical sensitivities (incl. the PRISM sheet used here as
        a positive-control concordance check).

Association model (per compound, per feature):
    AUC ~ aneuploidy_score + C(primary_tissue)
fitted exactly via the Frisch-Waugh-Lovell theorem (within-lineage demeaning
of response and regressor), so the code is pure stdlib and the tests run in
the main venv. beta < 0 means cell lines with more arm-level aneuploidy are
more sensitive to the drug. BH q-values across the tested compounds.

Screen choice: the readme recommends MTS010 (technical redos of 147 oncology
compounds) when a measurement exists for a (broad_id, depmap_id) pair; we
prefer MTS010 > HTS002 > MTS006 > MTS005 and keep one row per pair.

All statistics here are stdlib-only: OLS with absorbed fixed effects,
Student-t tail probabilities via the regularized incomplete beta function
(Numerical Recipes betai), Benjamini-Hochberg, Spearman rho with
mid-ranks for ties. Nothing about the proband enters this file beyond the
allowed public facts (gene symbol BUB1B, variant p.Asn1002Lys).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_RAW = Path(os.environ.get(
    "T2_PRISM_RAW",
    r"C:\Users\Nikhil\.claude\jobs\5356bf8a\tmp\prism_raw"))
OUT_JSON = REPO / "docs" / "track2" / "evidence" / "prism.json"
FIXTURE_DIR = REPO / "tests" / "fixtures" / "track2" / "prism"

UA = {"User-Agent": "mva-track2-l5/1.0"}
CHUNK = 1 << 20
CONNECT_TIMEOUT = 60

# ---------------------------------------------------------------- inputs
# Exact URLs fetched for this analysis. figshare file IDs are the ones linked
# from https://depmap.org/repurposing/ (PRISM Repurposing 19Q4) and from
# https://doi.org/10.6084/m9.figshare.11384241 (DepMap Public 19Q4 v3).
SOURCES: dict[str, str] = {
    "secondary-screen-readme.txt":
        "https://ndownloader.figshare.com/files/20238123",
    "secondary-screen-cell-line-info.csv":
        "https://ndownloader.figshare.com/files/20237769",
    "secondary-screen-dose-response-curve-parameters.csv":
        "https://ndownloader.figshare.com/files/20237739",
    "secondary-screen-replicate-collapsed-treatment-info.csv":
        "https://ndownloader.figshare.com/files/20237763",
    "depmap19q4_sample_info.csv":
        "https://ndownloader.figshare.com/files/20274744",
    "CCLE_expression.csv":
        "https://ndownloader.figshare.com/files/20234346",
    "CCLE_gene_cn.csv":
        "https://ndownloader.figshare.com/files/20234367",
    "CohenSharir_2021_SuppTable1_aneuploidy.xlsx":
        "https://static-content.springer.com/esm/"
        "art%3A10.1038%2Fs41586-020-03114-6/MediaObjects/"
        "41586_2020_3114_MOESM3_ESM.xlsx",
    "CohenSharir_2021_SuppTable2_genetic_deps.xlsx":
        "https://static-content.springer.com/esm/"
        "art%3A10.1038%2Fs41586-020-03114-6/MediaObjects/"
        "41586_2020_3114_MOESM4_ESM.xlsx",
    "CohenSharir_2021_SuppTable5_chemical_sens.xlsx":
        "https://static-content.springer.com/esm/"
        "art%3A10.1038%2Fs41586-020-03114-6/MediaObjects/"
        "41586_2020_3114_MOESM7_ESM.xlsx",
}
# Aliases used by earlier manual pulls into the same raw dir; fetch uses the
# canonical name, derive/analyze accept either.
ALIASES = {
    "secondary-screen-dose-response-curve-parameters.csv":
        ["secondary_dose_response_params.csv"],
    "CohenSharir_2021_SuppTable1_aneuploidy.xlsx":
        ["cohen_sharir_MOESM3.xlsx", "CohenSharir_SuppTable1_aneuploidy.xlsx"],
    "CohenSharir_2021_SuppTable2_genetic_deps.xlsx":
        ["cohen_sharir_MOESM4.xlsx"],
    "CohenSharir_2021_SuppTable5_chemical_sens.xlsx":
        ["CohenSharir_SuppTable5_chemsens.xlsx"],
}

SCREEN_PRIORITY = {"MTS010": 0, "HTS002": 1, "MTS006": 2, "MTS005": 3}
MIN_LINES_DEFAULT = 100
GENE = "BUB1B"

# SAC / mitotic positive-control name fragments (matched against lowercased
# PRISM 'name' + 'moa'). Direction predicted by Cohen-Sharir 2021: aneuploid
# lines are more sensitive to chronic (multi-day) SAC/mitotic perturbation.
SAC_POSITIVE_CONTROL = [
    "danusertib", "barasertib", "tozasertib", "zm-447439", "zm447439",
    "hesperadin", "gsk-1070916", "alisertib", "mln-8237", "mln8237",
    "azd1152", "azd-1152", "aurora kinase inhibitor",
    "bi-2536", "bi2536", "rigosertib", "volasertib", "gsk461364",
    "gw-843682", "plk1 inhibitor", "poloa-like kinase",
    "reversine", "mpi-0479605", "nms-p715", "mps1", "ttk inhibitor",
    "ispinesib", "sb-743921", "sb743921", "filanesib", "monastrol",
    "eg5 inhibitor", "kif11 inhibitor", "kinesin",
    "paclitaxel", "docetaxel", "vincristine", "vinblastine", "vinorelbine",
    "colchicine", "nocodazole", "cabazitaxel", "epothilone",
    "dinaciclib", "cdk1 inhibitor",
]
# nutlin/idasanutlin-class: MDM2 inhibitors were the top aneuploidy-selective
# hits in Cohen-Sharir Supp Table 5 - reported separately, not in the SAC set.
MDM2_CONTROL = ["nutlin", "idasanutlin", "cgm097", "amg-232", "amg232",
                "mi-773", "mdm2"]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(CHUNK), b""):
            h.update(chunk)
    return h.hexdigest()


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def find_input(raw: Path, name: str) -> Path | None:
    for cand in [name, *ALIASES.get(name, [])]:
        p = raw / cand
        if p.exists():
            return p
    return None


def fetch(raw: Path, only: list[str] | None = None) -> dict:
    """Download SOURCES into ``raw`` with a sha256 manifest (fetch_refs.py
    style). Skips files that already exist under the canonical name or an
    alias; always (re)writes the manifest for what is on disk."""
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = raw / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest_path.replace(manifest_path.with_suffix(".json.corrupt"))
    for name, url in SOURCES.items():
        if only and name not in only:
            continue
        dest = raw / name
        existing = find_input(raw, name)
        if existing is not None:
            print(f"[{name}] present ({existing.name}), hashing only")
            manifest[name] = {
                "url": url, "file": existing.name,
                "sha256": sha256_file(existing),
                "bytes": existing.stat().st_size, "fetched_at": utcnow()}
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        print(f"[{name}] {url}", flush=True)
        req = urllib.request.Request(url, headers=UA)
        sha = hashlib.sha256()
        nbytes = 0
        with urllib.request.urlopen(req, timeout=CONNECT_TIMEOUT) as r:
            if r.status != 200:
                raise urllib.error.HTTPError(url, r.status, "HTTP", None, None)
            with open(tmp, "wb") as out:
                while True:
                    chunk = r.read(CHUNK)
                    if not chunk:
                        break
                    out.write(chunk)
                    sha.update(chunk)
                    nbytes += len(chunk)
        tmp.replace(dest)
        manifest[name] = {"url": url, "file": name,
                          "sha256": sha.hexdigest(), "bytes": nbytes,
                          "fetched_at": utcnow()}
        print(f"[{name}] {nbytes:,} B sha256={sha.hexdigest()[:12]}...")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n",
                             encoding="utf-8")
    return manifest


# ------------------------------------------------------------ derive step
def _xlsx_rows(path: Path, sheet: str):
    """Yield rows of an xlsx sheet as tuples. Needs openpyxl (venv-t2);
    imported lazily so the stdlib analysis path never touches it."""
    import openpyxl  # noqa: PLC0415 - heavy import kept local on purpose
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        ws = wb[sheet]
        for row in ws.iter_rows(values_only=True):
            yield row
    finally:
        wb.close()


def derive_aneuploidy(xlsx_path: Path, out_csv: Path) -> int:
    """Cohen-Sharir Supp Table 1 -> depmap_id, aneuploidy_score, group."""
    rows = _xlsx_rows(xlsx_path, "Table_S1_CCLE_aneuploidy_scores")
    header = next(rows)
    idx = {h: i for i, h in enumerate(header)}
    n = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["depmap_id", "ccle_name", "aneuploidy_score",
                    "aneuploidy_group"])
        for r in rows:
            if r[idx["DepMap_ID"]] is None:
                continue
            w.writerow([r[idx["DepMap_ID"]], r[idx["CCLE_name"]],
                        r[idx["Aneuploidy_score"]],
                        r[idx["Aneuploidy_group_classification"]]])
            n += 1
    return n


def derive_supptable5(xlsx_path: Path, out_csv: Path) -> int:
    """Cohen-Sharir Supp Table 5 PRISM sheet -> drug_name, effect, p, q."""
    rows = _xlsx_rows(xlsx_path, "supp_table_5_prism")
    header = next(rows)
    idx = {h: i for i, h in enumerate(header)}
    n = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["drug_name", "effect_size", "p_value", "q_value"])
        for r in rows:
            if r[idx["Drug_name"]] is None:
                continue
            w.writerow([r[idx["Drug_name"]], r[idx["Effect_size"]],
                        r[idx["p_value"]], r[idx["q_value"]]])
            n += 1
    return n


def derive_supptable2(xlsx_path: Path, out_csv: Path,
                      q_max: float = 0.25) -> int:
    """Cohen-Sharir Supp Table 2 (both RNAi sheets) -> gene, effect, p, q;
    keeps rows with q <= q_max plus every BUB1B row regardless."""
    n = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["screen", "gene_symbol", "entrez", "effect_size",
                    "p_value", "q_value"])
        for sheet in ("supp_table_2_Achilles-RNAi", "supp_table_2_DRIVE-RNAi"):
            rows = _xlsx_rows(xlsx_path, sheet)
            header = next(rows)
            idx = {h: i for i, h in enumerate(header)}
            gcol = header[0]  # 'Gene_symbol (ENTREZ_ID)'
            for r in rows:
                cell = r[idx[gcol]]
                if cell is None:
                    continue
                m = re.match(r"^(.*)\((\d+)\)\s*$", str(cell).strip())
                sym, entrez = (m.group(1).strip(), m.group(2)) if m \
                    else (str(cell).strip(), "")
                q = r[idx["q_value"]]
                try:
                    qf = float(q)
                except (TypeError, ValueError):
                    continue
                if qf <= q_max or sym.upper() == GENE:
                    w.writerow([sheet, sym, entrez, r[idx["Effect_size"]],
                                r[idx["p_value"]], q])
                    n += 1
    return n


def _gene_column(fieldnames: list[str], gene: str) -> str | None:
    """DepMap wide files name columns 'SYMBOL (entrez)'; return the column
    whose symbol matches exactly (avoids BUB1B-PAK6 read-through)."""
    for c in fieldnames:
        if c.split(" ")[0] == gene:
            return c
    return None


def _scan_gene_column(path: Path, gene: str) -> dict[str, float]:
    """Stream a DepMap wide CSV (rows = ACH ids, cols = 'SYM (entrez)') and
    pull out one gene column without pandas."""
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        col = _gene_column(header[1:], gene)
        if col is None:
            raise KeyError(f"{gene} column not found in {path.name}")
        gi = header.index(col)
        for row in reader:
            try:
                out[row[0]] = float(row[gi])
            except (ValueError, IndexError):
                continue
    return out


def derive_bub1b(expr_csv: Path, cn_csv: Path, out_csv: Path) -> int:
    """BUB1B expression (log2(TPM+1)) and copy number per depmap_id."""
    expr = _scan_gene_column(expr_csv, GENE)
    cn = _scan_gene_column(cn_csv, GENE)
    ids = sorted(set(expr) | set(cn))
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["depmap_id", "bub1b_expr_log2tpm", "bub1b_cn_rel"])
        for d in ids:
            w.writerow([d, expr.get(d, ""), cn.get(d, "")])
    return len(ids)


def derive_cell_lines(cl_info: Path, sample_info: Path | None,
                      out_csv: Path) -> int:
    """depmap_id -> primary_tissue / lineage, plus STR-pass flag."""
    lin_by_id: dict[str, str] = {}
    if sample_info is not None and sample_info.exists():
        with open(sample_info, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("DepMap_ID") and r.get("lineage"):
                    lin_by_id[r["DepMap_ID"]] = r["lineage"]
    n = 0
    with open(out_csv, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["depmap_id", "ccle_name", "primary_tissue", "lineage",
                    "passed_str_profiling"])
        with open(cl_info, newline="", encoding="utf-8") as fh2:
            for r in csv.DictReader(fh2):
                did = r.get("depmap_id") or ""
                if not did:
                    continue
                w.writerow([did, r.get("ccle_name", ""),
                            r.get("primary_tissue", "") or "unknown",
                            lin_by_id.get(did, ""),
                            r.get("passed_str_profiling", "")])
                n += 1
    return n


def derive(raw: Path) -> dict:
    der = raw / "derived"
    der.mkdir(parents=True, exist_ok=True)
    written = {}
    jobs = [
        ("CohenSharir_2021_SuppTable1_aneuploidy.xlsx", "aneuploidy.csv",
         lambda p, o: derive_aneuploidy(p, o)),
        ("CohenSharir_2021_SuppTable2_genetic_deps.xlsx",
         "cohensharir_genetic_deps.csv", derive_supptable2),
        ("CohenSharir_2021_SuppTable5_chemical_sens.xlsx",
         "cohensharir_prism_chemsens.csv", derive_supptable5),
    ]
    for src, out_name, fn in jobs:
        p = find_input(raw, src)
        if p is None:
            print(f"MISSING {src} - run fetch first", file=sys.stderr)
            continue
        out = der / out_name
        n = fn(p, out)
        written[out_name] = {"rows": n, "sha256": sha256_file(out)}
        print(f"derived {out_name}: {n} rows")
    cl = find_input(raw, "secondary-screen-cell-line-info.csv")
    si = find_input(raw, "depmap19q4_sample_info.csv")
    if cl:
        out = der / "cell_lines.csv"
        n = derive_cell_lines(cl, si, out)
        written["cell_lines.csv"] = {"rows": n, "sha256": sha256_file(out)}
        print(f"derived cell_lines.csv: {n} rows")
    expr = find_input(raw, "CCLE_expression.csv")
    cn = find_input(raw, "CCLE_gene_cn.csv")
    if expr and cn:
        out = der / "bub1b_expr_cn.csv"
        n = derive_bub1b(expr, cn, out)
        written["bub1b_expr_cn.csv"] = {"rows": n, "sha256": sha256_file(out)}
        print(f"derived bub1b_expr_cn.csv: {n} rows")
    return written


# ------------------------------------------------------------- statistics
def _betacf(a: float, b: float, x: float) -> float:
    """Continued-fraction evaluation for the incomplete beta function
    (Numerical Recipes, betacf)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, 300):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 3e-14:
            break
    return h


def betai(a: float, b: float, x: float) -> float:
    """Regularized incomplete beta I_x(a,b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                  + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_two_sided_p(t: float, df: int) -> float:
    """Two-sided P(|T| >= |t|) for Student's t with ``df`` d.o.f."""
    if df <= 0:
        return 1.0
    if not math.isfinite(t):
        return 0.0          # infinite t (zero-residual fit) -> p ~ 0
    x = df / (df + t * t)
    return min(1.0, betai(df / 2.0, 0.5, x))


def ols_group_slope(y: list[float], x: list[float],
                    groups: list[str]) -> dict | None:
    """OLS slope of ``y ~ x + C(groups)`` via Frisch-Waugh-Lovell: demean y
    and x within each group, then regress residual-y on residual-x.

    Returns {beta, se, t, p, n, k_groups, rss_df} or None when the model is
    not identified (too few rows/groups or zero residual variance in x)."""
    n = len(y)
    sums_y: dict[str, float] = {}
    sums_x: dict[str, float] = {}
    cnt: dict[str, int] = {}
    for yi, xi, gi in zip(y, x, groups):
        sums_y[gi] = sums_y.get(gi, 0.0) + yi
        sums_x[gi] = sums_x.get(gi, 0.0) + xi
        cnt[gi] = cnt.get(gi, 0) + 1
    k = len(cnt)
    df = n - k - 1
    if df < 1:
        return None
    ry = [yi - sums_y[gi] / cnt[gi] for yi, gi in zip(y, groups)]
    rx = [xi - sums_x[gi] / cnt[gi] for xi, gi in zip(x, groups)]
    sxx = sum(v * v for v in rx)
    if sxx <= 0.0:
        return None
    sxy = sum(a * b for a, b in zip(rx, ry))
    beta = sxy / sxx
    rss = sum(v * v for v in ry) - beta * sxy
    s2 = max(rss, 0.0) / df
    se = math.sqrt(s2 / sxx)
    t = beta / se if se > 0 else math.copysign(float("inf"), beta)
    return {"beta": beta, "se": se, "t": t,
            "p": t_two_sided_p(t, df), "n": n, "k_groups": k,
            "rss_df": df}


def bh_qvalues(pvals: list[float]) -> list[float]:
    """Benjamini-Hochberg q-values, same order as input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [1.0] * m
    prev = 1.0
    for rank, i in enumerate(reversed(order)):
        r = m - rank
        val = min(prev, pvals[i] * m / r)
        q[i] = val
        prev = val
    return q


def _ranks(vals: list[float]) -> list[float]:
    order = sorted(range(len(vals)), key=lambda i: vals[i])
    r = [0.0] * len(vals)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        for t in range(i, j + 1):
            r[order[t]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return r


def spearman(x: list[float], y: list[float]) -> dict:
    """Spearman rho with mid-ranks for ties; p via t approximation."""
    n = len(x)
    if n < 3:
        return {"rho": float("nan"), "p": 1.0, "n": n}
    rx, ry = _ranks(x), _ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    dx = [a - mx for a in rx]
    dy = [b - my for b in ry]
    sxx = sum(a * a for a in dx)
    syy = sum(b * b for b in dy)
    if sxx <= 0 or syy <= 0:
        return {"rho": float("nan"), "p": 1.0, "n": n}
    rho = sum(a * b for a, b in zip(dx, dy)) / math.sqrt(sxx * syy)
    rho = max(-1.0, min(1.0, rho))
    if abs(rho) >= 1.0:
        return {"rho": rho, "p": 0.0, "n": n}
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    return {"rho": rho, "p": t_two_sided_p(t, n - 2), "n": n}


def norm_drug_name(name: str) -> str:
    """Lowercase, strip salt/formulation suffixes and punctuation so PRISM
    'name' matches Cohen-Sharir SuppTable5 'Drug_name'."""
    s = (name or "").lower().strip()
    for suffix in ("hydrochloride", "dihydrochloride", "hydrobromide",
                   "sodium", "potassium", "mesylate", "besylate", "tosylate",
                   "maleate", "tartrate", "citrate", "sulfate", "phosphate",
                   "acetate", "monohydrate", "hydrate", "hcl", "free base",
                   "disodium", "succinate", "nitrate", "oxalate"):
        if s.endswith(" " + suffix):
            s = s[: -len(suffix) - 1]
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


# ------------------------------------------------------------- load steps
def load_aneuploidy(path: Path) -> dict[str, dict]:
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                out[r["depmap_id"]] = {
                    "as_score": float(r["aneuploidy_score"]),
                    "as_group": r["aneuploidy_group"],
                    "ccle_name": r.get("ccle_name", "")}
            except (ValueError, KeyError):
                continue
    return out


def load_bub1b(path: Path) -> dict[str, dict]:
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rec = {}
            for k in ("bub1b_expr_log2tpm", "bub1b_cn_rel"):
                try:
                    rec[k] = float(r[k])
                except (ValueError, KeyError, TypeError):
                    rec[k] = None
            out[r["depmap_id"]] = rec
    return out


def load_lineages(path: Path) -> dict[str, dict]:
    out = {}
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            out[r["depmap_id"]] = r
    return out


def iter_auc_rows(path: Path):
    """Stream the 252 MB curve-parameter CSV; yield compact tuples.
    Columns (readme): broad_id,depmap_id,ccle_name,screen_id,upper_limit,
    lower_limit,slope,r2,auc,ec50,ic50,name,moa,target,disease.area,
    indication,smiles,phase,passed_str_profiling,row_name."""
    with open(path, newline="", encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("passed_str_profiling") != "TRUE":
                continue
            try:
                auc = float(r["auc"])
            except (ValueError, TypeError, KeyError):
                continue
            yield (r["broad_id"], r["depmap_id"], r.get("screen_id", ""),
                   auc, r.get("name", ""), r.get("moa", ""),
                   r.get("target", ""), r.get("phase", ""))


def collapse_screens(rows) -> dict[tuple[str, str], dict]:
    """One row per (broad_id, depmap_id): prefer MTS010 > HTS002 > MTS006 >
    MTS005 (secondary-screen readme recommendation)."""
    best: dict[tuple[str, str], dict] = {}
    for bid, did, sid, auc, name, moa, target, phase in rows:
        pri = SCREEN_PRIORITY.get(sid, 9)
        key = (bid, did)
        cur = best.get(key)
        if cur is None or pri < cur["pri"]:
            best[key] = {"pri": pri, "auc": auc, "name": name, "moa": moa,
                         "target": target, "phase": phase, "screen": sid}
    return best


def _quartile_stats(pairs: list[tuple[float, float]]) -> dict | None:
    """pairs = (feature, auc). Mean AUC in top vs bottom feature quartile;
    negative top-bottom = feature-high lines more sensitive."""
    n = len(pairs)
    if n < 16:
        return None
    srt = sorted(pairs, key=lambda p: p[0])
    q = n // 4
    lo = srt[:q]
    hi = srt[-q:]
    m_lo = sum(p[1] for p in lo) / len(lo)
    m_hi = sum(p[1] for p in hi) / len(hi)
    return {"n_bottom": len(lo), "n_top": len(hi),
            "auc_mean_bottom_quartile": m_lo,
            "auc_mean_top_quartile": m_hi,
            "auc_top_minus_bottom": m_hi - m_lo}


def _per_drug_table(results: list[dict]) -> None:
    """Attach BH q in place over a list of result dicts with 'p' key."""
    idx = [i for i, r in enumerate(results) if r is not None]
    qs = bh_qvalues([results[i]["p"] for i in idx])
    for i, q in zip(idx, qs):
        results[i]["q"] = q


def analyze(raw: Path, min_lines: int = MIN_LINES_DEFAULT) -> dict:
    der = raw / "derived"
    aneu_path = der / "aneuploidy.csv"
    bub_path = der / "bub1b_expr_cn.csv"
    cl_path = der / "cell_lines.csv"
    cs5_path = der / "cohensharir_prism_chemsens.csv"
    for p in (aneu_path, bub_path, cl_path):
        if not p.exists():
            raise FileNotFoundError(f"{p} - run `derive` first")
    aneu = load_aneuploidy(aneu_path)
    bub = load_bub1b(bub_path)
    lines = load_lineages(cl_path)
    print(f"lines with AS: {len(aneu)}, with BUB1B data: {len(bub)}, "
          f"PRISM cell-line records: {len(lines)}")

    dose_path = find_input(
        raw, "secondary-screen-dose-response-curve-parameters.csv")
    if dose_path is None:
        raise FileNotFoundError(
            "dose-response curve parameters csv not found in raw dir")
    print(f"scanning {dose_path.name} ...")
    best = collapse_screens(iter_auc_rows(dose_path))
    print(f"{len(best)} (broad_id, depmap_id) pairs after screen collapse")

    # group per broad_id
    drugs: dict[str, dict] = {}
    for (bid, did), rec in best.items():
        d = drugs.setdefault(bid, {"name": rec["name"], "moa": rec["moa"],
                                   "target": rec["target"],
                                   "phase": rec["phase"], "rows": []})
        lin = lines.get(did, {})
        d["rows"].append({
            "depmap_id": did, "auc": rec["auc"],
            "lineage": lin.get("primary_tissue") or "unknown",
            "as": aneu.get(did, {}).get("as_score"),
            "expr": (bub.get(did) or {}).get("bub1b_expr_log2tpm"),
            "cn": (bub.get(did) or {}).get("bub1b_cn_rel")})

    def regress(feature: str, phase_filter: str | None = None):
        out = []
        for bid, d in drugs.items():
            if phase_filter and d["phase"] != phase_filter:
                continue
            rows = [r for r in d["rows"] if r[feature] is not None]
            if len(rows) < min_lines:
                continue
            fit = ols_group_slope([r["auc"] for r in rows],
                                  [r[feature] for r in rows],
                                  [r["lineage"] for r in rows])
            if fit is None:
                continue
            rec = {"broad_id": bid, "name": d["name"], "moa": d["moa"],
                   "target": d["target"], "phase": d["phase"],
                   "n_lines": fit["n"], "n_lineages": fit["k_groups"],
                   "beta": fit["beta"], "se": fit["se"], "t": fit["t"],
                   "p": fit["p"], "rss_df": fit["rss_df"]}
            qs = _quartile_stats([(r[feature], r["auc"]) for r in rows])
            if qs:
                rec["quartiles"] = qs
            out.append(rec)
        _per_drug_table(out)
        out.sort(key=lambda r: r["beta"])
        return out

    print("regressing AUC ~ aneuploidy_score + C(lineage) ...")
    aneu_all = regress("as")
    aneu_launched = [r for r in aneu_all if r["phase"] == "Launched"]
    print(f"  tested {len(aneu_all)} compounds "
          f"({len(aneu_launched)} launched)")
    print("regressing AUC ~ BUB1B expression + C(lineage) ...")
    expr_all = regress("expr")
    expr_launched = [r for r in expr_all if r["phase"] == "Launched"]
    print(f"  tested {len(expr_all)} compounds "
          f"({len(expr_launched)} launched)")
    print("regressing AUC ~ BUB1B copy number + C(lineage) ...")
    cn_all = regress("cn")
    cn_launched = [r for r in cn_all if r["phase"] == "Launched"]
    print(f"  tested {len(cn_all)} compounds ({len(cn_launched)} launched)")

    # ---- positive control 1: Cohen-Sharir SuppTable5 name concordance
    concord = {"n_matched": 0}
    if cs5_path.exists():
        cs5 = {}
        with open(cs5_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                try:
                    cs5[norm_drug_name(r["drug_name"])] = float(
                        r["effect_size"])
                except (ValueError, TypeError):
                    continue
        mine = {norm_drug_name(r["name"]): r for r in aneu_all}
        xs, ys, matched = [], [], []
        for nm, es in cs5.items():
            if nm in mine:
                # Cohen-Sharir effect_size is positive when highly-aneuploid
                # lines are LESS sensitive (verified on nutlin-3: their
                # +0.154 vs our top-bottom-quartile AUC gap +0.124); our
                # +t = AUC rises with AS = aneuploid-resistant. Same scale.
                xs.append(mine[nm]["t"])
                ys.append(es)
                matched.append({"name": mine[nm]["name"],
                                "cs_effect_size": es,
                                "our_t": mine[nm]["t"],
                                "our_q": mine[nm]["q"]})
        sp = spearman(xs, ys)
        same_sign = sum(1 for a, b in zip(xs, ys)
                        if (a > 0) == (b > 0))
        concord = {"n_matched": len(xs),
                   "spearman_rho": sp["rho"], "spearman_p": sp["p"],
                   "sign_concordance": same_sign / len(xs) if xs else None,
                   "note": "x = t(AUC~AS|lineage); y = Cohen-Sharir Supp "
                           "Table 5 PRISM effect_size; positive = "
                           "aneuploid-RESISTANT in both (sign verified "
                           "against nutlin-3 and danusertib)",
                   "matched": sorted(matched,
                                     key=lambda m: -m["cs_effect_size"])[:40]}

    # ---- positive control 2: SAC/mitotic + MDM2 drug behaviour
    def _ctrl_hits(fragments):
        hits = []
        for r in aneu_all:
            hay = f"{r['name']} {r['moa']}".lower()
            if any(f in hay for f in fragments):
                hits.append({"name": r["name"], "moa": r["moa"],
                             "phase": r["phase"], "beta": r["beta"],
                             "p": r["p"], "q": r["q"],
                             "n_lines": r["n_lines"],
                             "aneuploid_selective": r["beta"] < 0})
        return sorted(hits, key=lambda h: h["beta"])
    sac_hits = _ctrl_hits(SAC_POSITIVE_CONTROL)
    mdm2_hits = _ctrl_hits(MDM2_CONTROL)

    # ---- positive control 3: BUB1B as aneuploidy-associated dependency
    bub_dep = {}
    dep_path = der / "cohensharir_genetic_deps.csv"
    if dep_path.exists():
        with open(dep_path, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r["gene_symbol"].upper() == GENE:
                    bub_dep[r["screen"]] = {
                        "effect_size": float(r["effect_size"]),
                        "p_value": float(r["p_value"]),
                        "q_value": float(r["q_value"])}

    manifest_path = raw / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            manifest = {}
    inputs = {name: {"url": SOURCES[name],
                     "file": e.get("file"), "sha256": e.get("sha256"),
                     "bytes": e.get("bytes")}
              for name, e in manifest.items() if name in SOURCES}

    return {
        "schema": "t2.prism/1",
        "generated_by": "tools/t2_prism.py",
        "generated_at": utcnow(),
        "model": ("AUC ~ feature + C(primary_tissue), OLS with absorbed "
                  "lineage fixed effects (FWL); beta < 0 = cell lines with "
                  "more of the feature are more sensitive to the drug; "
                  "q = Benjamini-Hochberg over tested compounds"),
        "params": {"min_lines": min_lines,
                   "screen_priority": SCREEN_PRIORITY,
                   "str_filter": "passed_str_profiling == TRUE",
                   "sensitivity_measure": "auc "
                       "(secondary-screen-dose-response-curve-parameters)"},
        "inputs": inputs,
        "references": {
            "prism": {"citation": "Corsello SM et al. Discovering the "
                      "anticancer potential of non-oncology drugs by "
                      "systematic viability profiling. Nat Cancer "
                      "1:235-248 (2020)",
                      "doi": "10.1038/s43018-019-0018-6",
                      "release": "PRISM Repurposing 19Q4 (figshare)"},
            "aneuploidy": {"citation": "Cohen-Sharir Y et al. Aneuploidy "
                           "renders cancer cells vulnerable to mitotic "
                           "checkpoint inhibition. Nature 590:486-491 (2021)",
                           "doi": "10.1038/s41586-020-03114-6",
                           "table": "Supplementary Table 1 (997 cell lines)"},
            "expression_cn": {"citation": "DepMap Public 19Q4",
                              "figshare_doi": "10.6084/m9.figshare.11384241"}},
        "aneuploidy": {
            "n_compounds_tested": len(aneu_all),
            "n_launched_tested": len(aneu_launched),
            "top_aneuploid_selective_launched": aneu_launched[:40],
            "all_results": aneu_all},
        "bub1b_expression": {
            "interpretation": "beta > 0 = lines with LOWER BUB1B expression "
                              "are more sensitive (AUC falls as expression "
                              "falls)",
            "n_compounds_tested": len(expr_all),
            "n_launched_tested": len(expr_launched),
            "top_low_expr_selective_launched":
                sorted(expr_launched, key=lambda r: -r["beta"])[:40],
            "all_results": expr_all},
        "bub1b_cn": {
            "n_compounds_tested": len(cn_all),
            "n_launched_tested": len(cn_launched),
            "all_results": cn_all},
        "positive_controls": {
            "cohensharir_supptable5_concordance": concord,
            "sac_mitotic_drugs": {
                "expected": "beta > 0 (aneuploid-RESISTANT) for "
                            "short-course SAC/mitotic perturbation: "
                            "Cohen-Sharir 2021 found aneuploid cells are "
                            "LESS sensitive to SAC inhibitors in screens "
                            "of this duration, in contrast to genetic "
                            "SAC depletion which aneuploid cells cannot "
                            "tolerate",
                "n_matched": len(sac_hits),
                "n_aneuploid_selective":
                    sum(1 for h in sac_hits if h["aneuploid_selective"]),
                "n_aneuploid_resistant":
                    sum(1 for h in sac_hits if not h["aneuploid_selective"]),
                "drugs": sac_hits},
            "mdm2_inhibitors": {
                "expected": "beta > 0 (aneuploid-RESISTANT): MDM2 "
                            "inhibitors carry the largest positive "
                            "effect_sizes in Cohen-Sharir Supp Table 5 "
                            "(sign verified vs nutlin-3 AUC gap)",
                "n_matched": len(mdm2_hits),
                "n_aneuploid_selective":
                    sum(1 for h in mdm2_hits if h["aneuploid_selective"]),
                "n_aneuploid_resistant":
                    sum(1 for h in mdm2_hits if not h["aneuploid_selective"]),
                "drugs": mdm2_hits},
            "bub1b_dependency_from_cohensharir_supptable2": {
                "expected": "negative effect_size = aneuploid lines MORE "
                            "dependent on BUB1B (genetic anchor)",
                "per_screen": bub_dep}},
        "caveats": [
            "AUC~AS association is observational across cancer cell lines; "
            "it is not evidence of mechanism and not evidence of benefit in "
            "a non-cancer context.",
            "PRISM lines are tumour cell lines, not a child's tissues; "
            "aneuploidy here is arm-level somatic copy-number load, which "
            "is related to - but not identical to - the mosaic whole-"
            "chromosome aneuploidy of MVA.",
            "Lineage fixed effects absorb coarse tissue-of-origin "
            "confounding only; growth rate, ploidy and mutation background "
            "can still confound.",
            "Phase field is the Broad Repurposing Hub annotation shipped "
            "with PRISM 19Q4; 'Launched' means marketed somewhere for some "
            "indication and is cross-checked against ChEMBL/DrugCentral/"
            "openFDA by the engine lane before any claim is made.",
            "Screen choice follows the PRISM readme (MTS010 redos preferred "
            "when present); no r2/convergence filter beyond valid AUC.",
        ],
    }


def write_prism_json(result: dict, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8")
    os.replace(tmp, out_path)
    print(f"wrote {out_path} ({out_path.stat().st_size:,} B)")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="PRISM x aneuploidy pharmacogenomic association (T2-L5)")
    ap.add_argument("cmd", choices=["fetch", "derive", "analyze", "run"])
    ap.add_argument("--raw-dir", default=str(DEFAULT_RAW),
                    help="raw download dir (outside git)")
    ap.add_argument("--min-lines", type=int, default=MIN_LINES_DEFAULT,
                    help="min cell lines per regression "
                         f"(default {MIN_LINES_DEFAULT})")
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args(argv)
    raw = Path(args.raw_dir)

    if args.cmd in ("fetch", "run"):
        fetch(raw)
    if args.cmd in ("derive", "run"):
        derive(raw)
    if args.cmd in ("analyze", "run"):
        res = analyze(raw, min_lines=args.min_lines)
        write_prism_json(res, Path(args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
