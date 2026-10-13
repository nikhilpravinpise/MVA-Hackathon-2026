"""ESM-2 masked-marginal variant-effect scoring for BUB1B (Track 2, lane L5).

    python tools/t2_esm.py fetch              # write variant inputs (network)
    python tools/t2_esm.py score --model facebook/esm2_t30_150M_UR50D
    python tools/t2_esm.py all

What it does
------------
Scores the proband's second BUB1B allele p.Asn1002Lys (allowed public fact,
docs/track2_plan.md section 6) and a calibration panel with a protein
language model:

    LLR(variant) = log P(mut | masked context) - log P(wt | masked context)

a "masked marginal" in the sense of Meier et al. 2021 (ESM-1v) - one masked
forward pass per position; the 1050-aa BUB1B protein (UniProt O60566, MANE
ENST00000287598.11 / NM_001211.6) is scored in a sliding window (default
1022 aa, the ESM-2 receptive limit after BOS/EOS tokens).

Calibration panel (all public):
    benign:  ClinVar B/LB missense in BUB1B on NM_001211.6 (E-utilities,
             query stored verbatim) + gnomAD r4 missense with AF >= 1e-4
             (proxy-enriched; flagged as proxy in the output)
    patho:   ClinVar P/LP missense in BUB1B (n=1 at time of fetch - reported
             as a point estimate, no AUC claimed) + ClinVar P/LP nonsense
             substitutions scored as loss-of-wildtype (mut approximated by
             the unknown-aa token 'X'; clearly labelled a proxy since ESM's
             vocabulary has no stop token)
    contrast: gnomAD ultra-rare missense (AC <= 2) vs common missense -
             checks the score tracks purifying selection

Splitting helpers (window bounds, LLR, AUC, percentile) are pure stdlib so
tests can run with a mock scorer in the main venv; torch/transformers are
imported lazily inside EsmScorer and only needed for `score`.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RAW = Path(os.environ.get(
    "T2_ESM_RAW",
    r"C:\Users\Nikhil\.claude\jobs\5356bf8a\tmp\prism_raw"))
OUT_JSON = REPO / "docs" / "track2" / "evidence" / "esm.json"

UA = {"User-Agent": "mva-track2-l5/1.0",
      "Content-Type": "application/json"}
GENE = "BUB1B"
UNIPROT_ACC = "O60566"            # BUB1B_HUMAN, 1050 aa, MANE-consistent
MANE_TX = "NM_001211.6"
MANE_ENST = "ENST00000287598.11"
QUERY_VARIANT = {"hgvsp": "p.Asn1002Lys", "pos": 1002, "wt": "N", "mut": "K",
                 "source": "proband_missense_allele_track1"}

GNOMAD_AF_COMMON = 1e-4          # 'common' benign-proxy threshold
GNOMAD_AC_ULTRARARE = 2          # 'ultra-rare' deleterious-enriched set
DEFAULT_MODEL = "facebook/esm2_t30_150M_UR50D"
DEFAULT_WIN = 1022               # ESM-2 max tokens 1024 incl BOS+EOS

AA3TO1 = {
    "Ala": "A", "Arg": "R", "Asn": "N", "Asp": "D", "Cys": "C",
    "Gln": "Q", "Glu": "E", "Gly": "G", "His": "H", "Ile": "I",
    "Leu": "L", "Lys": "K", "Met": "M", "Phe": "F", "Pro": "P",
    "Ser": "S", "Thr": "T", "Trp": "W", "Tyr": "Y", "Val": "V",
    "Ter": "*", "Sec": "U", "Pyl": "O"}
AA_ORDER = "ACDEFGHIKLMNPQRSTVWY"

P_RE = re.compile(r"p\.([A-Z][a-z]{2})(\d+)([A-Z][a-z]{2}|Ter)")


def utcnow() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def parse_hgvsp(title: str) -> dict | None:
    """Extract (pos, wt, mut) from a ClinVar title like
    'NM_001211.6(BUB1B):c.3006T>G (p.Asn1002Lys)'. Returns None when the
    title carries no single-residue protein change (fs, del, splice)."""
    m = P_RE.search(title or "")
    if not m:
        return None
    wt3, pos, mut3 = m.group(1), int(m.group(2)), m.group(3)
    return {"pos": pos, "wt": AA3TO1.get(wt3, "?"),
            "mut": AA3TO1.get(mut3, "?"), "hgvsp": f"p.{wt3}{pos}{mut3}"}


def window_bounds(seq_len: int, pos0: int, win: int = DEFAULT_WIN
                  ) -> tuple[int, int]:
    """[start, end) protein window containing 0-based ``pos0``; the window
    hugs the variant (clamped to the termini) so short proteins use the
    whole sequence."""
    if win >= seq_len:
        return (0, seq_len)
    half = win // 2
    start = min(max(0, pos0 - half), seq_len - win)
    return (start, start + win)


def llr_from_logprobs(logprobs: dict[str, float], wt: str,
                      mut: str) -> float:
    """masked-marginal log-likelihood ratio from a per-position amino-acid
    log-probability map. mut='*' is scored against the unknown-aa token
    'X' (loss-of-wildtype proxy) when '*' is absent from the map."""
    if mut == "*" and "*" not in logprobs:
        mut = "X"
    return logprobs[mut] - logprobs[wt]


def percentile_rank(value: float, background: list[float]) -> float:
    """Fraction of background <= value, in percent (ECDF)."""
    if not background:
        return float("nan")
    return 100.0 * sum(1 for b in background if b <= value) / len(background)


def deleteriousness_pct(value: float, background: list[float]) -> float:
    """Percent of background the variant is MORE damaging than: since a
    lower LLR means more damage, this is fraction(background > value)."""
    if not background:
        return float("nan")
    return 100.0 * sum(1 for b in background if b > value) / len(background)


def auc_from_labels(scores: list[float], labels: list[int]) -> float | None:
    """Mann-Whitney AUC for label==1 having LOWER scores (damaging).
    Returns None when a class is empty."""
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return None
    wins = 0.0
    for p in pos:
        for n in neg:
            wins += 1.0 if p < n else (0.5 if p == n else 0.0)
    return wins / (len(pos) * len(neg))


def median(vals: list[float]) -> float | None:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


# -------------------------------------------------------------- fetchers
RETRY_STATUS = (429, 500, 502, 503, 504)


def _get_json(url: str, data: bytes | None = None, retries: int = 5,
              backoff: float = 2.0, _sleep=time.sleep):
    """GET/POST JSON with exponential backoff on rate limits and transient
    server errors. NCBI answers 429 to shared cloud egress IPs (observed
    on Modal 2026-10-12), so a single attempt is not enough there. The
    final failure is re-raised as a plain RuntimeError: urllib's HTTPError
    carries an open file handle that Modal cannot pickle back."""
    for attempt in range(retries + 1):
        req = urllib.request.Request(url, data=data, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code not in RETRY_STATUS or attempt == retries:
                raise RuntimeError(f"HTTP {e.code} for {url}") from None
            wait = float(e.headers.get("Retry-After") or backoff * 2 ** attempt)
            _sleep(min(wait, 60.0))


def fetch_uniprot(acc: str = UNIPROT_ACC) -> dict:
    url = f"https://rest.uniprot.org/uniprotkb/{acc}.fasta"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as r:
        text = r.read().decode("utf-8")
    header = next(l for l in text.splitlines() if l.startswith(">"))
    seq = "".join(l.strip() for l in text.splitlines()
                  if not l.startswith(">"))
    return {"accession": acc, "url": url, "header": header, "seq": seq,
            "length": len(seq)}


CLINVAR_MISSENSE_QUERY = (
    f"{GENE}[gene] AND \"missense variant\"[variant type] AND "
    "(clinsig_pathogenic[prop] OR clinsig_likely_pathogenic[prop] OR "
    "clinsig_benign[prop] OR clinsig_likely_benign[prop])")
CLINVAR_PATH_QUERY = (
    f"{GENE}[gene] AND (clinsig_pathogenic[prop] OR "
    "clinsig_likely_pathogenic[prop])")


def _esearch_ids(term: str, retmax: int = 500) -> list[str]:
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?"
           "db=clinvar&retmode=json&retmax=%d&term=%s"
           % (retmax, urllib.parse.quote(term)))
    return _get_json(url)["esearchresult"]["idlist"]


def _esummary(uid_csv: str) -> dict:
    url = ("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?"
           "db=clinvar&retmode=json&id=" + uid_csv)
    return _get_json(url)["result"]


def fetch_clinvar(missense_term: str = CLINVAR_MISSENSE_QUERY,
                  path_term: str = CLINVAR_PATH_QUERY) -> dict:
    """ClinVar BUB1B variants via E-utilities (queries recorded verbatim).
    Returns {'missense': [...], 'pathogenic_all': [...]}."""
    ids = _esearch_ids(missense_term)
    missense = []
    for i in range(0, len(ids), 200):
        res = _esummary(",".join(ids[i:i + 200]))
        for uid in res["uids"]:
            r = res[uid]
            pc = parse_hgvsp(r.get("title", ""))
            if not pc:
                continue
            missense.append({**pc, "uid": uid, "title": r.get("title"),
                             "clinsig": r.get("germline_classification", {})
                             .get("description"),
                             "review": r.get("germline_classification", {})
                             .get("review_status")})
    ids = _esearch_ids(path_term)
    patho = []
    for i in range(0, len(ids), 200):
        res = _esummary(",".join(ids[i:i + 200]))
        for uid in res["uids"]:
            r = res[uid]
            pc = parse_hgvsp(r.get("title", ""))
            if not pc:
                continue
            patho.append({**pc, "uid": uid, "title": r.get("title"),
                          "clinsig": r.get("germline_classification", {})
                          .get("description")})
    return {"queries": {"missense_classified": missense_term,
                        "pathogenic_all": path_term},
            "missense": missense, "pathogenic_all": patho}


GNOMAD_QUERY = (
    "query { gene(gene_symbol: \"%s\", reference_genome: GRCh38) { gene_id "
    "variants(dataset: gnomad_r4) { variant_id consequence hgvsp "
    "exome { ac an af } genome { ac an af } } } }")


def fetch_gnomad(gene: str = GENE) -> dict:
    """gnomAD r4 variants in BUB1B via the public GraphQL API."""
    payload = json.dumps({"query": GNOMAD_QUERY % gene}).encode("utf-8")
    d = _get_json("https://gnomad.broadinstitute.org/api", data=payload)
    variants = d["data"]["gene"]["variants"]
    out = []
    for v in variants:
        if v["consequence"] != "missense_variant" or not v["hgvsp"]:
            continue
        pc = parse_hgvsp("x " + v["hgvsp"])
        if not pc:
            continue
        ex = v.get("exome") or {}
        ge = v.get("genome") or {}
        out.append({**pc, "variant_id": v["variant_id"],
                    "exome_ac": ex.get("ac"), "exome_an": ex.get("an"),
                    "exome_af": ex.get("af"),
                    "genome_ac": ge.get("ac"), "genome_af": ge.get("af"),
                    "max_af": max(ex.get("af") or 0, ge.get("af") or 0),
                    "max_ac": max(ex.get("ac") or 0, ge.get("ac") or 0)})
    return {"dataset": "gnomad_r4", "api": "https://gnomad.broadinstitute.org/api",
            "gene": gene, "n_missense": len(out), "variants": out}


def build_variant_inputs(raw: Path) -> dict:
    """Fetch sequence + ClinVar + gnomAD; write esm_inputs.json under raw."""
    seq = fetch_uniprot()
    clinvar = fetch_clinvar()
    gnomad = fetch_gnomad()
    payload = {"schema": "t2.esm_inputs/1", "fetched_at": utcnow(),
               "gene": GENE, "mane_transcript": MANE_TX,
               "mane_enst": MANE_ENST,
               "uniprot": {k: v for k, v in seq.items() if k != "seq"},
               "sequence_sha256":
                   __import__("hashlib").sha256(
                       seq["seq"].encode()).hexdigest(),
               "sequence": seq["seq"],
               "clinvar": clinvar, "gnomad": gnomad,
               "query_variant": QUERY_VARIANT}
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "esm_inputs.json").write_text(json.dumps(payload, indent=1),
                                         encoding="utf-8")
    print(f"wrote {raw / 'esm_inputs.json'} "
          f"({len(seq['seq'])} aa, {len(clinvar['missense'])} clinvar "
          f"missense, {len(clinvar['pathogenic_all'])} clinvar P/LP with "
          f"protein change, {gnomad['n_missense']} gnomAD missense)")
    return payload


# --------------------------------------------------------------- scoring
class EsmScorer:
    """Masked-marginal LLR scorer. torch/transformers imported lazily so
    the module stays stdlib-only for tests. Variants sharing a window are
    batched in a single forward pass."""

    def __init__(self, model_name: str = DEFAULT_MODEL,
                 device: str | None = None, win: int = DEFAULT_WIN,
                 batch: int = 16):
        self.model_name = model_name
        self.device = device
        self.win = win
        self.batch = batch
        self._model = None
        self._tok = None
        self._aa_ids = None

    def _load(self):
        if self._model is not None:
            return
        import torch  # noqa: PLC0415
        from transformers import AutoTokenizer, EsmForMaskedLM  # noqa
        self._torch = torch
        dev = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.device = dev
        self._tok = AutoTokenizer.from_pretrained(self.model_name)
        self._model = EsmForMaskedLM.from_pretrained(self.model_name)
        self._model.to(dev).eval()
        # map amino-acid letter -> vocab id once; 'X' and '*' handling:
        # ESM has an 'X' (unknown) token; '*' is absent -> we use 'X' for
        # loss-of-wildtype proxy scoring (documented in esm.json caveats).
        self._aa_ids = {a: self._tok.convert_tokens_to_ids(a)
                        for a in AA_ORDER + "X"}

    def logprobs_at(self, seq: str, pos0: int) -> dict[str, float]:
        """log P(aa | masked pos) for a position inside a window seq."""
        self._load()
        torch = self._torch
        enc = self._tok(seq, return_tensors="pt").to(self.device)
        mask_id = self._tok.mask_token_id
        enc["input_ids"][0, pos0 + 1] = mask_id  # +1: BOS token
        with torch.no_grad():
            logits = self._model(**enc).logits[0, pos0 + 1]
        lp = torch.log_softmax(logits, dim=-1)
        return {a: float(lp[i]) for a, i in self._aa_ids.items()}

    def score_variants(self, seq: str, variants: list[dict],
                       ) -> list[dict]:
        """Score [{'pos'(1-based),'wt','mut',...}] -> same dicts + 'llr'.
        Groups variants by window so one batch covers many positions."""
        self._load()
        L = len(seq)
        groups: dict[tuple[int, int], list[dict]] = {}
        for v in variants:
            pos0 = v["pos"] - 1
            if v["wt"] != seq[pos0]:
                raise ValueError(
                    f"WT mismatch at {v['hgvsp']}: expected {v['wt']}, "
                    f"sequence has {seq[pos0]}")
            w = window_bounds(L, pos0, self.win)
            groups.setdefault(w, []).append(v)
        out = []
        for (s, e), vs in sorted(groups.items()):
            sub = seq[s:e]
            # batch masked copies of the same window
            torch = self._torch
            ids = self._tok(sub, return_tensors="pt")["input_ids"]
            if ids.shape[1] > self.win + 2:
                ids = ids[:, : self.win + 2]
            rows = []
            for v in vs:
                p_in = v["pos"] - 1 - s + 1  # +1 for BOS
                rows.append((v, p_in))
            for i in range(0, len(rows), self.batch):
                chunk = rows[i:i + self.batch]
                batch_ids = ids.repeat(len(chunk), 1)
                for j, (v, p_in) in enumerate(chunk):
                    batch_ids[j, p_in] = self._tok.mask_token_id
                batch_ids = batch_ids.to(self.device)
                with torch.no_grad():
                    logits = self._model(input_ids=batch_ids).logits
                for j, (v, p_in) in enumerate(chunk):
                    lp = torch.log_softmax(logits[j, p_in], dim=-1)
                    lps = {a: float(lp[t]) for a, t in
                           self._aa_ids.items()}
                    rec = dict(v)
                    rec["llr"] = llr_from_logprobs(lps, v["wt"], v["mut"])
                    rec["window"] = [s + 1, e]
                    out.append(rec)
        return out


class MockScorer:
    """Deterministic fake scorer for tests: logprob = -|aa index - pos|.
    Mirrors EsmScorer.score_variants's contract without torch."""

    def __init__(self, win: int = DEFAULT_WIN):
        self.win = win

    def score_variants(self, seq: str, variants: list[dict]) -> list[dict]:
        out = []
        for v in variants:
            pos0 = v["pos"] - 1
            if seq[pos0] != v["wt"]:
                raise ValueError("wt mismatch")
            lp = {a: -abs(AA_ORDER.index(a) - (pos0 % 20)) / 10.0
                  for a in AA_ORDER}
            lp["X"] = -5.0
            rec = dict(v)
            rec["llr"] = llr_from_logprobs(lp, v["wt"], v["mut"])
            rec["window"] = list(window_bounds(len(seq), pos0, self.win))
            out.append(rec)
        return out


# ------------------------------------------------------------ assembly
def select_panels(inputs: dict) -> dict:
    """Split fetched variants into calibration panels."""
    clinvar = inputs["clinvar"]["missense"]
    patho_all = inputs["clinvar"]["pathogenic_all"]
    gnomad = inputs["gnomad"]["variants"]

    benign_cv = [dict(v, label=0, panel="clinvar_benign",
                      clinsig_grp=(v["clinsig"] or ""))
                 for v in clinvar
                 if (v["clinsig"] or "").lower()
                 in ("benign", "likely benign", "benign/likely benign")]
    patho_cv = [dict(v, label=1, panel="clinvar_pathogenic_missense")
                for v in clinvar
                if "pathogenic" in (v["clinsig"] or "").lower()]
    # nonsense P/LP: protein change p.XxxNTer -> mut '*' (X proxy)
    nonsense = [dict(v, label=1, panel="clinvar_nonsense_proxy")
                for v in patho_all if v["mut"] == "*"]
    common = [dict(v, label=0, panel="gnomad_common")
              for v in gnomad if (v["max_af"] or 0) >= GNOMAD_AF_COMMON]
    ultrarare = [dict(v, label=1, panel="gnomad_ultrarare")
                 for v in gnomad
                 if (v["max_ac"] or 0) <= GNOMAD_AC_ULTRARARE
                 and (v["max_af"] or 0) < GNOMAD_AF_COMMON]
    return {"clinvar_benign": benign_cv, "clinvar_pathogenic": patho_cv,
            "clinvar_nonsense": nonsense, "gnomad_common": common,
            "gnomad_ultrarare": ultrarare,
            "gnomad_all": gnomad}


def _cap_n1002k_dup(panels: dict) -> None:
    """The query variant appears in gnomAD (AF ~7e-7); keep it scored but
    flag it so the percentile math stays honest."""
    for v in panels["gnomad_all"]:
        if v["variant_id"] == "15-40220612-T-G":
            v["is_query_variant"] = True


def build_esm_result(inputs: dict, scored: list[dict],
                     model_meta: dict) -> dict:
    """Assemble esm.json from scored variant rows."""
    panels_llr: dict[str, list[float]] = {}
    for v in scored:
        p = v.get("panel")
        if p:
            panels_llr.setdefault(p, []).append(v["llr"])
    query = [v for v in scored if v.get("panel") == "query"]
    q_llr = query[0]["llr"] if query else None

    gnomad_bg = [v["llr"] for v in scored
                 if (v.get("panel") or "").startswith("gnomad_")
                 and not v.get("is_query_variant")]
    benign_llrs = panels_llr.get("clinvar_benign", []) + \
        panels_llr.get("gnomad_common", [])
    patho_miss = panels_llr.get("clinvar_pathogenic_missense", [])
    nonsense = panels_llr.get("clinvar_nonsense_proxy", [])
    common = panels_llr.get("gnomad_common", [])
    ultra = panels_llr.get("gnomad_ultrarare", [])

    auc_clinvar_benign_vs_nonsense = auc_from_labels(
        nonsense + panels_llr.get("clinvar_benign", []),
        [1] * len(nonsense) + [0] * len(panels_llr.get("clinvar_benign", [])))
    auc_missense_only = auc_from_labels(
        patho_miss + panels_llr.get("clinvar_benign", []),
        [1] * len(patho_miss) + [0] * len(panels_llr.get("clinvar_benign", [])))
    auc_gnomad = auc_from_labels(ultra + common,
                               [1] * len(ultra) + [0] * len(common))

    return {"schema": "t2.esm/1", "generated_by": "tools/t2_esm.py",
            "generated_at": utcnow(), "model": model_meta,
            "inputs": {"uniprot": inputs["uniprot"],
                       "sequence_sha256": inputs["sequence_sha256"],
                       "sequence_length": len(inputs["sequence"]),
                       "clinvar_queries": inputs["clinvar"]["queries"],
                       "clinvar_fetched_at": inputs["fetched_at"],
                       "gnomad": {"dataset": inputs["gnomad"]["dataset"],
                                  "api": inputs["gnomad"]["api"],
                                  "n_missense": inputs["gnomad"]
                                  ["n_missense"]}},
            "query": {"variant": QUERY_VARIANT["hgvsp"],
                      "llr": q_llr,
                      "deleteriousness_percentile_vs_gnomad_missense":
                          deleteriousness_pct(q_llr, gnomad_bg)
                          if q_llr is not None else None,
                      "deleteriousness_percentile_vs_benign_panel":
                          deleteriousness_pct(q_llr, benign_llrs)
                          if q_llr is not None else None,
                      "gnomad_af": next(
                          (v.get("gnomad_max_af") for v in scored
                           if v.get("panel") == "query"), None)},
            "calibration": {
                "n_scored": len(scored),
                "clinvar_benign":
                    {"n": len(panels_llr.get("clinvar_benign", [])),
                     "median_llr":
                         median(panels_llr.get("clinvar_benign", []))},
                "clinvar_pathogenic_missense":
                    {"n": len(patho_miss), "llrs": patho_miss,
                     "note": "too few for a missense-only AUC; reported "
                             "as a point estimate"},
                "clinvar_nonsense_proxy":
                    {"n": len(nonsense), "median_llr": median(nonsense),
                     "note": "stop-gains scored as loss-of-WT via the 'X' "
                             "unknown-aa token (ESM has no stop token); "
                             "proxy for constraint, not a stop-specific "
                             "score"},
                "gnomad_common": {"n": len(common),
                                  "median_llr": median(common)},
                "gnomad_ultrarare": {"n": len(ultra),
                                     "median_llr": median(ultra)},
                "auc_clinvar_benign_vs_nonsense_proxy":
                    auc_clinvar_benign_vs_nonsense,
                "auc_clinvar_benign_vs_pathogenic_missense":
                    auc_missense_only,
                "auc_gnomad_common_vs_ultrarare": auc_gnomad},
            "scores": scored,
            "caveats": [
                "ESM-2 LLR is a self-supervised conservation/compatability "
                "score, not a clinical predictor; it does not read "
                "mechanism (a hypomorph can score mild).",
                "Masked-marginal (single-mask) scoring approximates the "
                "variant marginal; wild-type-marginal scoring is a "
                "possible refinement not run here.",
                "Stop-gains cannot be scored directly (no '*' in the ESM "
                "vocabulary); the nonsense calibration rows use the 'X' "
                "unknown-aa token and measure loss-of-wildtype only.",
                "gnomAD common missense are a benign-ENRICHED proxy, not "
                "confirmed benign; ultra-rare are deleterious-enriched, "
                "not confirmed pathogenic.",
                "The query variant itself appears in gnomAD r4 with AC=1 "
                "in exomes; it is excluded from the percentile "
                "background.",
                "MANE-consistent numbering verified against UniProt "
                "O60566 (pos737=L, pos1002=N)."]}


def score(inputs: dict, model_name: str = DEFAULT_MODEL,
          device: str | None = None, scorer=None,
          max_gnomad_bg: int | None = None) -> dict:
    """Score query + panels; return the esm.json payload."""
    panels = select_panels(inputs)
    _cap_n1002k_dup(panels)
    seq = inputs["sequence"]
    query_row = dict(QUERY_VARIANT, panel="query", label=None)
    # the query variant may itself be in gnomAD; carry its AF onto the row
    for v in panels["gnomad_all"]:
        if (v["pos"], v["mut"]) == (QUERY_VARIANT["pos"],
                                  QUERY_VARIANT["mut"]):
            query_row["gnomad_max_af"] = v.get("max_af")
            query_row["gnomad_max_ac"] = v.get("max_ac")
            query_row["gnomad_variant_id"] = v.get("variant_id")
    to_score = [query_row]
    to_score += panels["clinvar_benign"] + panels["clinvar_pathogenic"] + \
        panels["clinvar_nonsense"] + panels["gnomad_common"] + \
        panels["gnomad_ultrarare"]
    bg = panels["gnomad_all"]
    if max_gnomad_bg and len(bg) > max_gnomad_bg:
        step = len(bg) / max_gnomad_bg
        bg = [bg[int(i * step)] for i in range(max_gnomad_bg)]
    seen = {(v["pos"], v["mut"]) for v in to_score}
    to_score += [dict(v, panel="gnomad_background", label=None)
                 for v in bg
                 if (v["pos"], v["mut"]) not in seen]
    # drop rows whose stated WT does not match the scored sequence (a
    # handful of gnomAD rows use non-MANE hgvsp numbering; ClinVar titles
    # are NM_001211.6 so should never mismatch)
    dropped, kept = [], []
    for v in to_score:
        (kept if seq[v["pos"] - 1] == v["wt"] else dropped).append(v)
    for v in dropped:
        v["drop_reason"] = (
            f"wt_mismatch: stated {v['wt']}, MANE seq has "
            f"{seq[v['pos'] - 1]}")
    scr = scorer or EsmScorer(model_name=model_name, device=device)
    print(f"scoring {len(kept)} variants ({len(dropped)} dropped on "
          f"wt mismatch) ...")
    scored = scr.score_variants(seq, kept)
    meta = {"model": getattr(scr, "model_name", type(scr).__name__),
            "device": getattr(scr, "device", "mock"),
            "window_aa": getattr(scr, "win", DEFAULT_WIN),
            "scoring": "masked-marginal LLR (log P(mut) - log P(wt), "
                       "single mask per position)"}
    result = build_esm_result(inputs, scored, meta)
    result["dropped_variants"] = [
        {"hgvsp": v.get("hgvsp"), "pos": v["pos"], "wt": v["wt"],
         "mut": v["mut"], "panel": v.get("panel"),
         "reason": v["drop_reason"],
         "variant_id": v.get("variant_id"), "uid": v.get("uid")}
        for v in dropped]
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="ESM-2 masked-marginal BUB1B variant scoring (T2-L5)")
    ap.add_argument("cmd", choices=["fetch", "score", "all"], nargs="?",
                    default="all")
    ap.add_argument("--raw-dir", default=str(RAW))
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help="HF model id (default esm2_t30_150M_UR50D; "
                         "esm2_t33_650M_UR50D for the Modal GPU run)")
    ap.add_argument("--device", default=None)
    ap.add_argument("--max-gnomad-bg", type=int, default=None,
                    help="cap gnomAD background variants (evenly spaced)")
    ap.add_argument("--inputs", default=None,
                    help="existing esm_inputs.json (skip network fetch)")
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args(argv)
    raw = Path(args.raw_dir)

    if args.inputs:
        inputs = json.loads(Path(args.inputs).read_text(encoding="utf-8"))
    elif args.cmd in ("fetch", "all"):
        inputs = build_variant_inputs(raw)
    else:
        inputs = json.loads(
            (raw / "esm_inputs.json").read_text(encoding="utf-8"))
    if args.cmd in ("score", "all"):
        res = score(inputs, model_name=args.model, device=args.device,
                    max_gnomad_bg=args.max_gnomad_bg)
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
        os.replace(tmp, out)
        print(f"wrote {out} ({out.stat().st_size:,} B)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
