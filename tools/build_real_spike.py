"""Build the REAL-DATA spike-in external-validation case under env/real_spike/.

    python tools/build_real_spike.py
    python tools/build_real_spike.py --refresh        # re-hit Ensembl REST
    python tools/build_real_spike.py --list-candidates # print ClinVar table only

Purpose (plan.md section 2.1.2b): the whole funnel must recover a REAL
ClinVar pathogenic compound-het pair spiked into a PUBLIC genome (GIAB
HG002) with realistic allele fractions and a matching HPO set - blind,
before we trust it on the proband. Firewall: the proband locus is never
touched; this case lives entirely in PAH (chr12, phenylketonuria
OMIM:261600, autosomal recessive, dense ClinVar P/LP coverage).

Structure of the synthetic proband
----------------------------------
* Background: every HG002 NIST-v4.2.1 record inside a 200 kb window around
  the PAH locus (chr12:102,800,000-103,000,000; PAH itself spans
  ~102,838-102,958 kb). Real genotypes, real common/rare SNP mix. The
  sample is rewritten to PROBAND01 with GT:AD:DP:GQ:PGT:PID synthesized to
  a ~35x short-read WGS profile (deterministic, seeded per variant key);
  GTs are HG002's real calls.
* Spike: two different ClinVar P/LP PAH variants forming a classic AR
  compound-het - one canonical-LoF class allele + one missense allele,
  both SNVs for clean annotation. ``--lof``/``--missense`` override the
  deterministic auto-pick (lowest-position P/LP SNV per class). PGT/PID
  put the two alts IN TRANS inside one phase set (PS_PAH), exactly the
  mechanism src/phasing.determine_phase consumes (1|0 vs 0|1, shared PID).
* Truth + phenotype: truth.json records the pair in scorer convention
  (chr-prefixed), in_trans, the phase set; hpo_terms.json carries REAL
  OMIM:261600 terms lifted from env/corpus/phenotype.hpoa (source marked;
  curated clinically-characteristic subset, not the whole 30-term list -
  see pick_proband_hpo).

Annotation approach - STATE OF THE CONTRACT
---------------------------------------------
The funnel reads VEP-style CSQ (src/synth.CSQ_FIELDS). EVERY variant in the
emitted VCF is annotated through the Ensembl REST VEP endpoint
(POST /vep/homo_sapiens/region, batches of <=150, cached in vep_cache.json):

* consequence terms / SYMBOL / Gene / Feature / BIOTYPE / IMPACT / EXON /
  INTRON / HGVSc / HGVSp / Protein_position / Amino_acids / Codons /
  DISTANCE / STRAND come from transcript_consequences (per gene: the worst
  consequence, MANE_Select > canonical preferred as representative);
* gnomADe/g pooled + subpop AFs come from colocated_variants[].frequencies
  (matched per allele; gnomAD 'remaining'/'ami' folds into OTH via max);
* CADD_PHRED / REVEL / AlphaMissense_score+class / SIFT / PolyPhen are
  requested REST plugins and land per transcript consequence;
* CLIN_SIG comes from the ClinVar VCF record itself when one exists at the
  same (chrom,pos,ref,alt) - the file we selected spikes from is the
  authoritative clin_sig source; REST clin_sig is the fallback;
* SpliceAI DS_*, LOEUF and phyloP are NOT available via REST -> left ''.
  SpliceAI is only a rescue path in the funnel; LOEUF/phyloP are unused by
  triage. The missense spike clears the damage bar on CADD+REVEL+SIFT+
  PolyPhen votes regardless (documented in BUILD_REPORT.json).

Fallback when REST is unreachable or an allele is rejected: a minimal CSQ
block built from ClinVar fields (GENEINFO->SYMBOL, MC->Consequence,
CLNSIG->CLIN_SIG) or a bare intron/intergenic default with no SYMBOL - such
a variant can still pass QC/rarity but cannot form a same-gene pair, so
annotation gaps degrade gracefully. Per-variant annotation status is
recorded in BUILD_REPORT.json (annotation_coverage).

Multi-allelic records are kept as single VCF lines (ALT=a,b); each alt is
annotated independently and CSQ Allele tags carry the verbatim VCF allele
(the funnel matches Allele==alt). CSQ blocks: one per gene (worst
consequence), plus an intergenic block for off-transcript records.

Outputs: real_spike.vcf, truth.json, hpo_terms.json, BUILD_REPORT.json,
vep_cache.json (annotation cache; delete to force re-annotation).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from src.synth import Ann, SVar, write_vcf  # noqa: E402
from src.triage import _severity as so_severity  # noqa: E402

ENV = REPO / "env"
CORPUS = ENV / "corpus"
PUBVCF = ENV / "public_vcfs"
OUT = ENV / "real_spike"

VEP_URL = "https://rest.ensembl.org/vep/homo_sapiens/region"
VEP_PARAMS = ("CADD=1;REVEL=1;AlphaMissense=1;af_gnomade=1;af_gnomadg=1;"
              "hgvs=1;canonical=1;mane=1;SIFT=1;PolyPhen=1;numbers=1")
USER_AGENT = "mva-real-spike/1.0 (external-validation spike-in builder)"
BATCH = 150          # POST variant strings per request (REST limit ~200)
RETRIES = 4
SLEEP_S = 0.4        # polite inter-batch pause

GENE = "PAH"
DISEASE = "OMIM:261600"
WINDOW = (102_800_000, 103_000_000)     # chr12, GRCh38
PAH_BOUNDS = (102_838_000, 102_959_000)  # approximate PAH gene body
CHR12_LEN = 133_275_309
SEED = 20260926
PHASE_SET = "PS_PAH"

# ClinVar MC tokens treated as LoF-class vs missense for spike selection.
_LOF_MC = ("nonsense", "frameshift_variant", "splice_acceptor_variant",
           "splice_donor_variant", "start_lost", "stop_lost")

# Proband HPO: prefer the clinically characteristic PKU set; fill to N from
# remaining hpoa order. Non-phenotypic rows (inheritance pattern, pregnancy
# history, maternal-foetal terms) are excluded first.
HPO_PREFERRED = [
    "HP:0004923",   # Hyperphenylalaninemia - the defining PKU finding
    "HP:0034458",   # Elevated urinary phenylpyruvic acid level
    "HP:0004920",   # Phenylpyruvic acidemia
    "HP:0001250",   # Seizure
    "HP:0001249",   # Intellectual disability
    "HP:0002286",   # Fair hair (hypopigmentation)
    "HP:0000964",   # Eczematoid dermatitis
]
HPO_EXCLUDE = {
    "HP:0002686",   # Pregnancy history - context, not a patient phenotype
    "HP:0000007",   # Autosomal recessive inheritance - not a phenotype
    "HP:0100610",   # Maternal hyperphenylalaninemia - mother's phenotype
}
HPO_N = 6


# ---------------------------------------------------------------------------
# corpus / input plumbing
# ---------------------------------------------------------------------------

def ensure_corpus() -> dict:
    """Make sure env/corpus holds the HPO reference files this build needs.

    Calls tools/fetch_refs.py when present (it owns the mirror list); falls
    back to a direct urllib fetch of the same canonical URLs otherwise.
    Idempotent: existing files are never re-downloaded here.
    """
    needed = ["hp.obo", "phenotype.hpoa", "genes_to_phenotype.txt"]
    missing = [n for n in needed if not (CORPUS / n).exists()]
    status = {}
    if not missing:
        return {"corpus": "present", "fetched": []}
    fetch_refs = REPO / "tools" / "fetch_refs.py"
    CORPUS.mkdir(parents=True, exist_ok=True)
    for name in missing:
        if fetch_refs.exists():
            print(f"[corpus] fetching {name} via tools/fetch_refs.py")
            subprocess.run([sys.executable, str(fetch_refs), "--only", name],
                           check=True)
        else:
            _fetch_fallback(name)
        status[name] = (CORPUS / name).exists()
    return {"corpus": "completed", "fetched": missing, "ok": status}


def _fetch_fallback(name: str) -> None:
    """Last-resort fetcher mirroring fetch_refs.py's URL list (kept in sync
    with the HPO release layout: GitHub release asset -> purl.obolibrary)."""
    gh = ("https://github.com/obophenotype/human-phenotype-ontology"
          "/releases/latest/download")
    urls = {
        "hp.obo": [f"{gh}/hp.obo",
                   "https://purl.obolibrary.org/obo/hp.obo"],
        "phenotype.hpoa": [f"{gh}/phenotype.hpoa",
                           "https://purl.obolibrary.org/obo/hp/hpoa/"
                           "phenotype.hpoa"],
        "genes_to_phenotype.txt": [f"{gh}/genes_to_phenotype.txt",
                                   "https://purl.obolibrary.org/obo/hp/hpoa/"
                                   "genes_to_phenotype.txt"],
    }[name]
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            (CORPUS / name).write_bytes(data)
            print(f"[corpus] {name} <- {url} ({len(data):,} B)")
            return
        except Exception as exc:  # noqa: BLE001
            print(f"[corpus] {url} failed: {exc}")
    raise RuntimeError(f"could not fetch {name}")


# ---------------------------------------------------------------------------
# ClinVar slice parsing + spike selection
# ---------------------------------------------------------------------------

def _info_field(info: str, key: str) -> str:
    m = re.search(rf"(?:^|;){re.escape(key)}=([^;]*)", info)
    return m.group(1) if m else ""


def parse_clinvar_pah(path: Path, window: tuple[int, int]) -> list[dict]:
    """PAH records from the ClinVar chromosome slice (GENEINFO 'PAH:<id>')."""
    out = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            continue
        c = line.rstrip("\n").split("\t")
        pos = int(c[1])
        if not (window[0] <= pos <= window[1]):
            continue
        info = c[7]
        gi = _info_field(info, "GENEINFO")
        if not re.search(r"(^|\|)PAH:", gi):
            continue
        out.append({
            "chrom": c[0], "pos": pos, "vid": c[2], "ref": c[3], "alt": c[4],
            "clnsig": _info_field(info, "CLNSIG"),
            "clnvc": _info_field(info, "CLNVC"),
            "mc": _info_field(info, "MC"),
            "revstat": _info_field(info, "CLNREVSTAT"),
            "clndn": _info_field(info, "CLNDN"),
        })
    return out


def _is_plp(clnsig: str) -> bool:
    s = clnsig.lower()
    return ("pathogenic" in s and "conflict" not in s and "benign" not in s)


def _is_snv(r: dict) -> bool:
    return len(r["ref"]) == 1 and len(r["alt"]) == 1


def spike_candidates(recs: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split P/LP SNV candidates into (lof_class, missense_class) pools."""
    lof, mis = [], []
    for r in recs:
        if not (_is_plp(r["clnsig"]) and _is_snv(r)):
            continue
        mc = r["mc"]
        if any(t in mc for t in _LOF_MC):
            lof.append(r)
        elif "missense_variant" in mc and "splice" not in mc:
            mis.append(r)
    key = lambda r: (0 if "expert_panel" in r["revstat"] else 1, r["pos"])
    return sorted(lof, key=key), sorted(mis, key=key)


def print_candidates(lof: list[dict], mis: list[dict], show: int = 15) -> None:
    """The candidate list the pair was chosen from (BUILD_REPORT echoes it)."""
    print(f"\nClinVar PAH P/LP candidates: {len(lof)} LoF-class, "
          f"{len(mis)} missense (SNV only)")
    for tag, pool in (("LOF ", lof), ("MISS", mis)):
        print(f"  -- {tag} (first {show}) --")
        for r in pool[:show]:
            star = "*" if "expert_panel" in r["revstat"] else " "
            print(f"  {tag}{star} {r['pos']} {r['ref']}>{r['alt']} "
                  f"VCV{r['vid']:>8s} {r['clnsig'][:30]:30s} {r['mc'][:60]}")


def _pick(pool: list[dict], pos: int | None, what: str) -> dict:
    if pos is not None:
        for r in pool:
            if r["pos"] == pos:
                return r
        raise SystemExit(f"--{what} {pos} not in the P/LP SNV pool")
    if not pool:
        raise SystemExit(f"no {what} candidates - widen the window?")
    return pool[0]


# ---------------------------------------------------------------------------
# HG002 background parsing
# ---------------------------------------------------------------------------

def parse_hg002(path: Path, window: tuple[int, int]) -> list[dict]:
    """Background records in the window. GT is kept verbatim per alt."""
    recs = []
    for line in open(path, encoding="utf-8"):
        if line.startswith("#"):
            continue
        c = line.rstrip("\n").split("\t")
        pos = int(c[1])
        if not (window[0] <= pos <= window[1]):
            continue
        fmt = c[8].split(":") if len(c) > 8 else []
        sval = c[9].split(":") if len(c) > 9 else []
        raw = {fmt[i]: sval[i] if i < len(sval) else "."
               for i in range(len(fmt))}
        recs.append({"chrom": c[0].removeprefix("chr"), "pos": pos,
                     "id": c[2], "ref": c[3], "alts": c[4].split(","),
                     "qual": c[5], "filters": c[6],
                     "gt": raw.get("GT", "0/1")})
    return recs


def _synth_format(gt: str, n_alt: int, key: str, seed: int,
                  spike: bool = False) -> dict:
    """Deterministic ~35x genotype block; returns {gt,ad,dp,gq,pgt,pid}."""
    rng = random.Random(f"{seed}:{key}")
    dp = rng.randint(30, 42)
    gq = 99 if spike else rng.randint(60, 99)
    alleles = gt.replace("|", "/").split("/")
    # distribute dp across carried alleles with mild jitter
    parts = [rng.uniform(0.85, 1.15) for _ in alleles]
    tot = sum(parts) or 1.0
    ad = [0] * (n_alt + 1)
    remaining = dp
    for i, a in enumerate(alleles):
        try:
            ai = int(a)
        except ValueError:
            continue
        share = dp if i == len(alleles) - 1 else int(dp * parts[i] / tot)
        share = max(1, min(share, remaining))
        ad[ai] += share
        remaining -= share
    if ad[0] == 0 and 0 in [int(a) for a in alleles if a.isdigit()]:
        ad[0] = 1
    return {"gt": gt, "ad": tuple(ad), "dp": dp, "gq": gq,
            "pgt": None, "pid": None}


# ---------------------------------------------------------------------------
# Ensembl REST VEP annotation
# ---------------------------------------------------------------------------

def to_vep_region(chrom: str, pos: int, ref: str, alt: str) -> str | None:
    """VCF (pos,ref,alt) -> VEP region string 'chrom start end ref/alt +'.

    Minimal representation: shared suffix then prefix are trimmed; a pure
    insertion becomes '-/ALT' with start=end+1, a pure deletion 'REF/-'.
    Multi-base substitutions stay as 'REF/ALT' over the covered span.
    """
    if ref == alt:
        return None
    while len(ref) > 1 and len(alt) > 1 and ref[-1] == alt[-1]:
        ref, alt = ref[:-1], alt[:-1]
    while ref and alt and ref[0] == alt[0]:
        ref, alt, pos = ref[1:], alt[1:], pos + 1
    if not ref:                       # pure insertion
        return f"{chrom} {pos} {pos - 1} -/{alt} +"
    if not alt:                       # pure deletion
        return f"{chrom} {pos} {pos + len(ref) - 1} {ref}/- +"
    return f"{chrom} {pos} {pos + len(ref) - 1} {ref}/{alt} +"


class VepClient:
    """Batched POST /vep/homo_sapiens/region client with on-disk cache."""

    def __init__(self, cache_path: Path, batch: int = BATCH,
                 offline: bool = False):
        self.cache_path = cache_path
        self.batch = batch
        self.offline = offline
        self.cache: dict = {}
        if cache_path.exists():
            self.cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.stats = {"rest_ok": 0, "rest_err": 0, "cached": 0}

    def annotate(self, keys: list[str]) -> dict:
        """keys are 'chrom start end ref/alt +' region strings."""
        uniq = list(dict.fromkeys(keys))
        # cached REST *errors* are re-queried (transient failures self-heal);
        # --refresh wipes the whole cache for a clean re-annotation.
        need = [k for k in uniq
                if k not in self.cache or "__error__" in self.cache[k]]
        self.stats["cached"] = len(uniq) - len(need)
        for i in range(0, len(need), self.batch):
            chunk = need[i:i + self.batch]
            if self.offline:
                for k in chunk:
                    self.cache[k] = {"__error__": "offline (--skip-rest)"}
                continue
            self._post(chunk)
        if not self.offline:
            self.cache_path.write_text(json.dumps(self.cache), encoding="utf-8")
        return {k: self.cache.get(k, {"__error__": "not queried"})
                for k in dict.fromkeys(keys)}

    def _post(self, chunk: list[str]) -> None:
        url = f"{VEP_URL}?{VEP_PARAMS}"
        body = json.dumps({"variants": chunk}).encode()
        last = None
        data = None
        for attempt in range(RETRIES):
            try:
                req = urllib.request.Request(
                    url, data=body, method="POST",
                    headers={"Content-Type": "application/json",
                             "Accept": "application/json",
                             "User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = json.loads(r.read())
                break
            except urllib.error.HTTPError as e:
                last = f"HTTP {e.code}: {e.read()[:200]!r}"
                if e.code in (400, 404):
                    break
                time.sleep(2 ** attempt)
            except Exception as exc:  # noqa: BLE001
                last = repr(exc)
                time.sleep(2 ** attempt)
        if not isinstance(data, list):
            data = [{"input": k, "error": last or "malformed REST response"}
                    for k in chunk]
        # map response entries to inputs: positionally when lengths match,
        # else by the echoed 'input' field (REST may drop failed variants)
        if len(data) == len(chunk):
            pairs = zip(chunk, data)
        else:
            by_input = {d.get("input"): d for d in data
                        if isinstance(d, dict) and d.get("input")}
            pairs = [(k, by_input.get(k) or {"error": "no result returned"})
                     for k in chunk]
        for k, item in pairs:
            if not isinstance(item, dict) or (
                    "error" in item
                    and "transcript_consequences" not in item):
                self.cache[k] = {"__error__": str(
                    item.get("error", "bad entry") if isinstance(item, dict)
                    else "bad entry")}
                self.stats["rest_err"] += 1
            else:
                self.cache[k] = item
                self.stats["rest_ok"] += 1
        time.sleep(SLEEP_S)


def _allele_freqs(cv_entry: dict, vep_allele: str) -> dict | None:
    """gnomAD frequencies for our (VEP-normalized) allele in one colocated
    entry. Frequencies are keyed per ALT allele; '-' is the deletion key."""
    freqs = cv_entry.get("frequencies") or {}
    if vep_allele in freqs:
        return freqs[vep_allele]
    for k, v in freqs.items():
        if vep_allele and vep_allele in k.split("/"):
            return v
    return None


def collect_afs(colocated: list, vep_allele: str) -> dict:
    """Max-AF per population across matching colocated variant entries.

    Allele-matching policy (conservative for background noise control):
    * our allele key present in an entry's frequencies -> real AFs;
    * our allele documented in an entry's allele_string but carrying no
      frequency of its own (e.g. the reference/major allele of a known
      SNP) -> estimate AF as 1 - sum(other alleles' pooled AF), written
      only into the pooled AF fields. This errs toward COMMON, which is
      the safe direction: phantom-'absent' on a real common allele would
      mark it rare and manufacture noise hypotheses;
    * no colocated entry documents our allele -> absent (genuinely novel).
    """
    pops = {"gnomade": "gnomADe_AF", "gnomadg": "gnomADg_AF"}
    for grp, popsfx in (("gnomade", "gnomADe"), ("gnomadg", "gnomADg")):
        for p in ("afr", "amr", "asj", "eas", "fin", "mid", "nfe", "sas"):
            pops[f"{grp}_{p}"] = f"{popsfx}_{p.upper()}_AF"
    out: dict[str, float] = {}
    for cv in colocated or []:
        fr = _allele_freqs(cv, vep_allele)
        alts = (cv.get("allele_string") or "").split("/")
        if fr is None:
            if not (cv.get("frequencies") and vep_allele in alts):
                continue
            # documented allele without its own frequency: complement est.
            others = 0.0
            for v in (cv.get("frequencies") or {}).values():
                for grp in ("gnomade", "gnomadg"):
                    try:
                        others = max(others, float(v.get(grp) or 0.0))
                    except (TypeError, ValueError, AttributeError):
                        continue
            est = max(0.0, 1.0 - others)
            out["gnomADe_AF"] = max(est, out.get("gnomADe_AF", 0.0))
            out["gnomADg_AF"] = max(est, out.get("gnomADg_AF", 0.0))
            continue
        for k, csq_name in pops.items():
            v = fr.get(k)
            if v is None:
                continue
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            out[csq_name] = max(v, out.get(csq_name, 0.0))
        # gnomAD 'remaining'/'ami' both fold into the OTH column
        for grp in ("gnomade", "gnomadg"):
            oth = "gnomADe_OTH_AF" if grp == "gnomade" else "gnomADg_OTH_AF"
            for k in (f"{grp}_remaining", f"{grp}_ami"):
                v = fr.get(k)
                try:
                    v = float(v) if v is not None else None
                except (TypeError, ValueError):
                    continue
                if v is not None:
                    out[oth] = max(v, out.get(oth, 0.0))
    return out


def _clin_sig_of(colocated: list, allele: str) -> str:
    """REST clin_sig for our allele, e.g. 'pathogenic'."""
    for cv in colocated or []:
        if not cv.get("clin_sig"):
            continue
        alts = (cv.get("allele_string") or "").split("/")
        if allele in alts or "-" in alts or not alts:
            return "&".join(cv["clin_sig"])
    return ""


def _first_existing_variation(colocated: list) -> str:
    for cv in colocated or []:
        i = cv.get("id")
        if i and str(i).startswith("rs"):
            return i
    for cv in colocated or []:
        if cv.get("id"):
            return str(cv["id"])
    return ""


def tc_to_ann(tc: dict, vcf_alt: str, afs: dict, clin_sig: str,
              existing: str) -> Ann:
    """One VEP transcript_consequence dict -> one synth.Ann (CSQ block)."""
    extra = dict(afs)
    if clin_sig:
        # ClinVar VCF encodes multi-value CLNSIG with '|'; VEP CSQ uses
        # '&' inside a field ('|' is the CSQ column separator)
        extra["CLIN_SIG"] = clin_sig.replace("|", "&")
    if existing:
        extra["Existing_variation"] = existing
    if tc.get("cadd_phred") is not None:
        extra["CADD_PHRED"] = tc["cadd_phred"]
    if tc.get("revel") is not None:
        extra["REVEL"] = tc["revel"]
    am = tc.get("alphamissense") or {}
    if am.get("am_pathogenicity") is not None:
        extra["AlphaMissense_score"] = am["am_pathogenicity"]
        extra["AlphaMissense_class"] = am.get("am_class", "")
    if tc.get("sift_prediction"):
        extra["SIFT"] = (f"{tc['sift_prediction']}"
                         + (f"({tc['sift_score']})"
                            if tc.get("sift_score") is not None else ""))
    if tc.get("polyphen_prediction"):
        extra["PolyPhen"] = (f"{tc['polyphen_prediction']}"
                             + (f"({tc['polyphen_score']})"
                                if tc.get("polyphen_score") is not None
                                else ""))
    protein_pos = ""
    if tc.get("protein_start") is not None:
        protein_pos = (str(tc["protein_start"]) if
                       tc.get("protein_start") == tc.get("protein_end")
                       else f"{tc.get('protein_start')}-"
                            f"{tc.get('protein_end')}")
    ann = Ann(allele=vcf_alt,
              consequence="&".join(tc.get("consequence_terms") or
                                   ["intergenic_variant"]),
              impact=tc.get("impact", "MODIFIER"),
              symbol=tc.get("gene_symbol") or "",
              gene=tc.get("gene_id") or "",
              feature=tc.get("transcript_id") or "",
              biotype=tc.get("biotype") or "",
              extra=extra)
    ann.extra.setdefault("EXON", tc.get("exon", ""))
    ann.extra.setdefault("INTRON", tc.get("intron", ""))
    ann.extra.setdefault("HGVSc", tc.get("hgvsc", ""))
    ann.extra.setdefault("HGVSp", tc.get("hgvsp", ""))
    ann.extra.setdefault("Protein_position", protein_pos)
    ann.extra.setdefault("Amino_acids", tc.get("amino_acids", ""))
    ann.extra.setdefault("Codons", tc.get("codons", ""))
    ann.extra.setdefault("DISTANCE", tc.get("distance", ""))
    ann.extra.setdefault("STRAND", tc.get("strand", ""))
    return ann


def anns_from_vep(item: dict, vcf_alt: str, vep_allele: str = "",
                  clin_sig_override: str = "",
                  max_genes: int = 6) -> tuple[list[Ann], dict]:
    """Map one REST result to CSQ blocks: worst consequence per gene.

    ``vcf_alt`` is the verbatim VCF allele written into the CSQ Allele tag;
    ``vep_allele`` is the VEP-normalized allele used for frequency/clin_sig
    matching ('-' for deletions, the inserted bases for insertions).

    Returns (anns, meta) where meta records annotation provenance for the
    build report.
    """
    meta = {"vep_status": "ok", "n_tc": 0, "genes": []}
    colocated = item.get("colocated_variants") or []
    afs = collect_afs(colocated, vep_allele or vcf_alt)
    clin_sig = clin_sig_override or _clin_sig_of(
        colocated, vep_allele or vcf_alt)
    existing = _first_existing_variation(colocated)
    tcs = item.get("transcript_consequences") or []
    meta["n_tc"] = len(tcs)

    per_gene: dict[str, dict] = {}
    for tc in tcs:
        gene = tc.get("gene_symbol") or tc.get("gene_id") or ""
        cur = per_gene.get(gene)
        def rank(t: dict) -> tuple:
            return (so_severity("&".join(t.get("consequence_terms") or [])),
                    0 if t.get("mane") or t.get("mane_select") else 1,
                    0 if t.get("canonical") == 1 else 1)
        if cur is None or rank(tc) < rank(cur):
            per_gene[gene] = tc
    anns: list[Ann] = []
    for i, (gene, tc) in enumerate(
            sorted(per_gene.items(),
                   key=lambda kv: so_severity(
                       "&".join(kv[1].get("consequence_terms") or [])))):
        if i >= max_genes:
            break
        anns.append(tc_to_ann(tc, vcf_alt, afs, clin_sig, existing))
        meta["genes"].append(gene)
    if not anns:
        # regulatory / intergenic fallback so the record still parses
        alt_terms = []
        for k in ("regulatory_feature_consequences",
                  "motif_feature_consequences",
                  "intergenic_consequences"):
            for tc in item.get(k) or []:
                alt_terms = tc.get("consequence_terms") or []
                if alt_terms:
                    break
            if alt_terms:
                break
        anns.append(Ann(allele=vcf_alt,
                        consequence="&".join(alt_terms or
                                             ["intergenic_variant"]),
                        impact="MODIFIER", symbol="", gene="",
                        extra=dict(afs)))
        meta["vep_status"] = "no_transcript_consequence"
    return anns, meta


# ---------------------------------------------------------------------------
# minimal-CSQ fallback when REST cannot annotate a variant
# ---------------------------------------------------------------------------

def fallback_anns(vcf_alt: str, clinvar_rec: dict | None) -> list[Ann]:
    """Minimal CSQ when REST failed: ClinVar MC/GENEINFO if we have one,
    else a bare intergenic block carrying no SYMBOL (cannot pair)."""
    if clinvar_rec:
        mcs = [m.split("|", 1)[1] for m in clinvar_rec["mc"].split(",")
               if "|" in m]
        cons = "&".join(mcs) if mcs else "intron_variant"
        return [Ann(allele=vcf_alt, consequence=cons, impact="MODERATE",
                    symbol=GENE,
                    extra={"CLIN_SIG":
                           clinvar_rec["clnsig"].replace("|", "&")})]
    return [Ann(allele=vcf_alt, consequence="intergenic_variant",
                impact="MODIFIER")]


# ---------------------------------------------------------------------------
# HPO terms for the proband
# ---------------------------------------------------------------------------

def pick_proband_hpo(hpoa_path: Path) -> tuple[list[str], str]:
    """REAL OMIM:261600 terms, first N clinically characteristic ones.

    Order: the hpoa file order filtered for non-phenotypic rows is the
    deterministic source; HPO_PREFERRED reorders it to put the canonical
    PKU findings first. Returns (terms, source_string).
    """
    if not hpoa_path.exists():
        return (HPO_PREFERRED[:HPO_N],
                "fallback:documented-PKU-terms(hpoa missing)")
    ordered: list[str] = []
    for line in open(hpoa_path, encoding="utf-8", errors="replace"):
        if line.startswith("#") or not line.startswith(DISEASE + "\t"):
            continue
        cols = line.rstrip("\n").split("\t")
        if len(cols) > 3 and re.fullmatch(r"HP:\d{7}", cols[3] or ""):
            t = cols[3]
            if t not in ordered and t not in HPO_EXCLUDE:
                ordered.append(t)
    chosen = [t for t in HPO_PREFERRED if t in ordered][:HPO_N]
    if len(chosen) < 3:  # safety: fill from file order
        chosen += [t for t in ordered if t not in chosen][:HPO_N - len(chosen)]
    return chosen, "env/corpus/phenotype.hpoa rows for OMIM:261600"


# ---------------------------------------------------------------------------
# VCF emission
# ---------------------------------------------------------------------------

class RawRec:
    """Duck-typed SVar-compatible record for multi-allelic background
    (write_vcf only needs .chrom/.pos/.vcf_line)."""

    def __init__(self, chrom, pos, vid, ref, alts, sample_fmt):
        self.chrom, self.pos, self.vid = chrom, pos, vid
        self.ref, self.alts = ref, alts
        self.sample_fmt = sample_fmt      # dict from _synth_format
        self.csq: list[str] = []

    def vcf_line(self, sample: str) -> str:
        f = self.sample_fmt
        ad = ",".join(str(x) for x in f["ad"])
        sval = ":".join([f["gt"], ad, str(f["dp"]), str(f["gq"]),
                         f["pgt"] or ".", f["pid"] or "."])
        info = "CSQ=" + ",".join(self.csq) if self.csq else "."
        return "\t".join([self.chrom, str(self.pos), self.vid, self.ref,
                          ",".join(self.alts), "50.0", "PASS", info,
                          "GT:AD:DP:GQ:PGT:PID", sval])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--clinvar-slice",
                    default=str(PUBVCF / "clinvar_12.vcf"))
    ap.add_argument("--hg002-slice",
                    default=str(PUBVCF / "hg002_12_102750000-103050000.vcf"))
    ap.add_argument("--window", default=f"{WINDOW[0]}-{WINDOW[1]}",
                    help="chr12 window for background, e.g. 102800000-103000000")
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--lof", type=int, default=None,
                    help="pos override for the LoF spike allele")
    ap.add_argument("--missense", type=int, default=None,
                    help="pos override for the missense spike allele")
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--batch", type=int, default=BATCH)
    ap.add_argument("--refresh", action="store_true",
                    help="ignore vep_cache.json and re-annotate")
    ap.add_argument("--skip-rest", action="store_true",
                    help="no REST calls: minimal-CSQ fallback everywhere")
    ap.add_argument("--list-candidates", action="store_true")
    args = ap.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    w = tuple(int(x) for x in args.window.split("-"))
    clinvar_path = Path(args.clinvar_slice)
    hg002_path = Path(args.hg002_slice)
    for p in (clinvar_path, hg002_path):
        if not p.exists():
            raise SystemExit(f"missing {p} - run tools/fetch_public_vcfs.py "
                             f"first (--chr-subset 12 --region "
                             f"chr12:{w[0]}-{w[1]})")

    # ---- 1. choose the pair from real ClinVar P/LP --------------------
    recs = parse_clinvar_pah(clinvar_path, (PAH_BOUNDS[0] - 5000,
                                            PAH_BOUNDS[1] + 5000))
    lof_pool, mis_pool = spike_candidates(recs)
    print_candidates(lof_pool, mis_pool)
    if args.list_candidates:
        return 0
    lof = _pick(lof_pool, args.lof, "lof")
    mis = _pick(mis_pool, args.missense, "missense")
    if lof["pos"] == mis["pos"]:
        raise SystemExit("lof and missense collide at the same position")
    print(f"\nCHOSEN PAIR (LoF + missense, in trans):")
    print(f"  LOF : {lof['pos']} {lof['ref']}>{lof['alt']} VCV{lof['vid']} "
          f"{lof['clnsig']} ({lof['mc'].split(',')[-1]})")
    print(f"  MISS: {mis['pos']} {mis['ref']}>{mis['alt']} VCV{mis['vid']} "
          f"{mis['clnsig']} ({mis['mc'].split(',')[-1]})")

    # ---- 2. background records from HG002 ------------------------------
    bg = parse_hg002(hg002_path, w)
    spike_keys = {(lof["pos"], lof["ref"], lof["alt"]),
                  (mis["pos"], mis["ref"], mis["alt"])}
    bg = [r for r in bg if all(
        (r["pos"], r["ref"], a) not in spike_keys for a in r["alts"])]
    print(f"\nbackground: {len(bg)} HG002 records in "
          f"12:{w[0]}-{w[1]} (spike-position collisions removed)")

    # ---- 3. ensure corpus + proband HPO -------------------------------
    corp = ensure_corpus()
    hpo_terms, hpo_src = pick_proband_hpo(CORPUS / "phenotype.hpoa")
    print(f"hpo corpus: {corp}; proband terms {hpo_terms}")

    # ---- 4. annotate everything via REST (cached) ---------------------
    cache_path = out / "vep_cache.json"
    if args.refresh and cache_path.exists():
        cache_path.unlink()
    client = VepClient(cache_path, batch=args.batch, offline=args.skip_rest)

    clin_at = {}
    for line in open(clinvar_path, encoding="utf-8"):
        if line.startswith("#"):
            continue
        c = line.split("\t")
        pos = int(c[1])
        if w[0] <= pos <= w[1]:
            for alt in c[4].split(","):
                clin_at.setdefault(
                    (pos, c[3], alt),
                    {"clnsig": _info_field(c[7], "CLNSIG"),
                     "mc": _info_field(c[7], "MC"),
                     "vid": c[2]})

    # variant work list: [(region_key, bg_rec_or_None, alt)]
    work = []
    for rec in bg:
        for alt in rec["alts"]:
            k = to_vep_region(rec["chrom"], rec["pos"], rec["ref"], alt)
            if k:
                work.append((k, rec, alt))
    spike_sig = {}
    for sv in (lof, mis):
        k = to_vep_region("12", sv["pos"], sv["ref"], sv["alt"])
        spike_sig[k] = sv
        work.append((k, None, sv["alt"]))
    keys = [k for k, _, _ in work if k]
    print(f"\nannotating {len(keys)} alleles via Ensembl REST "
          f"({'OFFLINE fallback' if args.skip_rest else 'batches of ' + str(args.batch)}) ...")
    t0 = time.time()
    results = client.annotate(keys)
    print(f"annotation done in {time.time() - t0:.1f}s: "
          f"{client.stats}")

    annot_meta = {}
    anns_of_key = {}
    for k, rec, alt in work:
        item = results.get(k) or {"__error__": "missing"}
        vep_allele = k.split()[3].split("/", 1)[1] if k else alt
        if rec is None:
            sv = spike_sig.get(k)
            cov_sig = sv["clnsig"] if sv else ""
            cov_rec = {"clnsig": cov_sig, "mc": sv["mc"]} if sv else None
        else:
            cov_rec = clin_at.get((rec["pos"], rec["ref"], alt))
            cov_sig = cov_rec["clnsig"] if cov_rec else ""
        if "__error__" in item:
            anns_of_key[(k, alt)] = fallback_anns(alt, cov_rec)
            annot_meta.setdefault("fallback", []).append(k)
        else:
            anns, meta = anns_from_vep(item, alt, vep_allele=vep_allele,
                                     clin_sig_override=cov_sig)
            anns_of_key[(k, alt)] = anns
            annot_meta[k] = meta

    # ---- 5. emit VCF ----------------------------------------------------
    variants = []
    for rec in bg:
        fmt = _synth_format(rec["gt"], len(rec["alts"]),
                            f"{rec['pos']}:{rec['ref']}>{','.join(rec['alts'])}",
                            args.seed)
        if len(rec["alts"]) == 1:
            alt = rec["alts"][0]
            k = to_vep_region(rec["chrom"], rec["pos"], rec["ref"], alt)
            anns = anns_of_key.get((k, alt), fallback_anns(alt, None))
            variants.append(SVar(rec["chrom"], rec["pos"], rec["ref"], alt,
                                 vid=rec["id"] if rec["id"] != "." else ".",
                                 gt=fmt["gt"], ad=fmt["ad"], dp=fmt["dp"],
                                 gq=fmt["gq"], anns=anns))
        else:
            rr = RawRec(rec["chrom"], rec["pos"], rec["id"], rec["ref"],
                        rec["alts"], fmt)
            for alt in rec["alts"]:
                k = to_vep_region(rec["chrom"], rec["pos"], rec["ref"], alt)
                for a in anns_of_key.get((k, alt),
                                         fallback_anns(alt, None)):
                    rr.csq.append(a.to_csq())
            variants.append(rr)
    for sv, pgt in ((lof, "0|1"), (mis, "1|0")):
        k = to_vep_region("12", sv["pos"], sv["ref"], sv["alt"])
        anns = anns_of_key.get((k, sv["alt"]), [])
        fmt = _synth_format("0/1", 1, f"spike:{sv['pos']}", args.seed,
                          spike=True)
        vid = "."
        for a in anns:
            if a.extra.get("Existing_variation"):
                vid = a.extra["Existing_variation"].split("&")[0]
        variants.append(SVar("12", sv["pos"], sv["ref"], sv["alt"], vid=vid,
                             gt="0/1", ad=fmt["ad"], dp=fmt["dp"],
                             gq=fmt["gq"], pgt=pgt, pid=PHASE_SET,
                             anns=anns))

    vcf_path = write_vcf(out / "real_spike.vcf", variants,
                         contigs={"12": CHR12_LEN},
                         samples=("PROBAND01",),
                         source="real-spike-v1 (HG002 + ClinVar PAH)")
    n_records = len(variants)

    # ---- 6. truth / hpo / report ---------------------------------------
    truth = {"gene": GENE, "model": "compound_het", "in_trans": True,
             "phase_set": PHASE_SET,
             "pair": [
                 {"chrom": "chr12", "pos": mis["pos"], "ref": mis["ref"],
                  "alt": mis["alt"],
                  "clinvar_vid": mis["vid"], "clnsig": mis["clnsig"],
                  "class": "missense", "pgt": "1|0"},
                 {"chrom": "chr12", "pos": lof["pos"], "ref": lof["ref"],
                  "alt": lof["alt"],
                  "clinvar_vid": lof["vid"], "clnsig": lof["clnsig"],
                  "class": "lof", "pgt": "0|1"}],
             "disease": DISEASE, "hpo_terms": hpo_terms,
             "note": "bare chrom '12' in the VCF; 'chr12' is the scorer "
                     "convention (to_submission_chrom)"}
    (out / "truth.json").write_text(json.dumps(truth, indent=1) + "\n")

    (out / "hpo_terms.json").write_text(json.dumps(
        {"proband_id": "PROBAND01", "hpo_terms": hpo_terms,
         "source": hpo_src}, indent=1) + "\n")

    report = {
        "built_at": datetime.now(timezone.utc).replace(microsecond=0)
        .isoformat(),
        "gene": GENE, "disease": DISEASE, "window": f"12:{w[0]}-{w[1]}",
        "annotation_approach": (
            "Ensembl REST VEP POST /vep/homo_sapiens/region for EVERY "
            "variant (batches<=%d); per-gene worst consequence; gnomAD e/g "
            "AFs from colocated_variants.frequencies; CADD/REVEL/"
            "AlphaMissense/SIFT/PolyPhen via REST plugins; CLIN_SIG from "
            "the ClinVar VCF record where one exists; SpliceAI/LOEUF/"
            "phyloP unavailable via REST and left blank" % args.batch),
        "spike_pair": truth["pair"],
        "spike_choice_rule": ("lowest-position ClinVar P/LP SNV per class "
                              "unless --lof/--missense override"),
        "candidate_counts": {"lof_pool": len(lof_pool),
                             "missense_pool": len(mis_pool)},
        "background": {"hg002_records": len(bg),
                       "window": f"12:{w[0]}-{w[1]}"},
        "vcf_records": n_records,
        "annotation": {"rest_stats": client.stats,
                       "alleles_queried": len(keys),
                       "fallback_alleles": len(
                           annot_meta.get("fallback", [])),
                       "cache": str(cache_path)},
        "corpus": corp, "proband_hpo": hpo_terms, "hpo_source": hpo_src,
        "seed": args.seed,
    }
    (out / "BUILD_REPORT.json").write_text(json.dumps(report, indent=1) + "\n")
    print(f"\nwrote {vcf_path} ({n_records} records) + truth/hpo/BUILD_REPORT")
    print("next: python tools/run_pipeline.py --vcf env/real_spike/"
          "real_spike.vcf --hpo-terms env/real_spike/hpo_terms.json "
          "--obo env/corpus/hp.obo --hpoa env/corpus/phenotype.hpoa "
          "--gene2disease env/corpus/gene2disease.json --out results/run_real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
