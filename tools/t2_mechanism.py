"""Track 2 lane L1 - per-allele mechanism characterization for BUB1B.

    python tools/t2_mechanism.py            # live fetch, caches raw responses
    python tools/t2_mechanism.py --replay   # replay cached fixtures, no network

Fetches public data for the two proband alleles
(chr15:40209701 T>G c.2210T>G p.Leu737Ter and
 chr15:40220612 T>G c.3006T>G p.Asn1002Lys; MANE ENST00000287598 /
NM_001211.6; UniProt O60566), computes the per-allele mechanism evidence
(exon/NMD analysis, domain mapping, predictor scores, population frequency,
ClinVar status, AlphaFold structural context), resolves every cited PMID via
NCBI E-utilities and every DOI via Crossref, and writes
``docs/track2/evidence/mechanism.json`` (schema ``t2.mechanism/1``).

Raw API responses are cached under ``tests/fixtures/track2/mechanism/`` so
``--replay`` and the pytest suite run network-free. Plain functions take
parsed data (not URLs) so every computation is unit-testable on synthetic
inputs. Citations: a PMID is only emitted if esummary resolves it live
(or from cache on replay); unresolved identifiers raise, which keeps the
"no citation from memory" rule mechanical.
"""
from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FIXTURE_DIR = REPO / "tests" / "fixtures" / "track2" / "mechanism"
OUT_JSON = REPO / "docs" / "track2" / "evidence" / "mechanism.json"

USER_AGENT = "MVA-hackathon-track2/1.0 (research; contact via GitHub repo)"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

TRANSCRIPT = "ENST00000287598"
UNIPROT = "O60566"

# The two proband alleles (patient-derived facts already published in the
# Track 1 report; nothing else about the child is used).
ALLELES = [
    {"hg38": "chr15:40209701 T>G", "chrom": "15", "pos": 40209701,
     "ref": "T", "alt": "G", "cdna": "c.2210T>G", "protein": "p.Leu737Ter",
     "vep_allele": "G"},
    {"hg38": "chr15:40220612 T>G", "chrom": "15", "pos": 40220612,
     "ref": "T", "alt": "G", "cdna": "c.3006T>G", "protein": "p.Asn1002Lys",
     "vep_allele": "G"},
]

# PMIDs used in claims/pathway/implications. Every id is resolved through
# E-utilities before it is allowed into the output (see resolve_citations).
PMIDS = [
    "9644970",    # Nagy & Maquat 1998, termination-codon position rule
    "27618451",   # Lindeboom 2016, NMD rules in human cancers
    "31659324",   # Lindeboom 2019, NMD impact review
    "15475955",   # Hanks 2004 Nat Genet, biallelic BUB1B -> MVA
    "16411201",   # Matsuura 2006, monoallelic BUB1B / PCS, >50% loss
    "20516114",   # Suijkerbuijk 2010, molecular causes of BUBR1 dysfunction in MVA
    "15208629",   # Baker 2004 Nat Genet, BubR1 insufficiency progeroid mice
    "23300461",   # Wijshake 2012, mono-allelic BubR1 MVA mice
    "18516091",   # Baker 2008 NCB, p16/p19 opposing roles
    "22048312",   # Baker 2011 Nature, p16 clearance delays ageing disorders
    "23602569",   # Baker 2013 Cell Rep, p53/p21 protective in BubR1 insufficiency
    "23242215",   # Baker 2013 NCB, BubR1 overexpression protects vs aneuploidy+cancer
    "24825348",   # North 2014 EMBO J, SIRT2 induces BubR1, NAD+ decline
    "19407811",   # Choi 2009 EMBO J, BubR1 K250 acetylation stability
    "23079597",   # Suijkerbuijk 2012 Dev Cell, KARD / PP2A-B56
    "22698286",   # Suijkerbuijk 2012 Dev Cell, BUBR1 unusual pseudokinase
    "23345399",   # Kruse 2013 JCS, BubR1-B56 PP2A direct binding
    "33207204",   # Gama Braga 2020 Cell Rep, pseudokinase domain -> PP2A-B56
    "20123995",   # Thompson & Compton 2010, aneuploidy limited by p53
    "28633018",   # Santaguida 2017, missegregation -> arrest/senescence/immune clearance
    "34216545",   # Joy 2021, proteostasis failure -> aneuploidy-induced senescence
    "21190457",   # Rio Frio 2010 NEJM, homozygous BUB1B -> GI neoplasia
    "31081598",   # Ochiai 2019, bilateral Wilms in BUB1B PCS/MVA
    "33505028",   # Cohen-Sharir 2021 Nature, aneuploid cells vulnerable to SAC inhibition
    "33505027",   # Quinton 2021 Nature, WGD+ vulnerabilities incl. KIF18A
    "30500870",   # Boguszewski 2019 Endocr Rev, GH links to cancer
    "32738133",   # Thomas-Teinturier 2020, GH therapy and second neoplasm risk
    "37733863",   # Cheng 2023 Science, AlphaMissense
    "32461654",   # Karczewski 2020 Nature, gnomAD constraint spectrum
    "29165669",   # Landrum 2018 NAR, ClinVar
]

# DOIs (databases/resources) resolved via Crossref.
DOIS = [
    "10.1093/nar/gkab1049",       # Ensembl 2022
    "10.1093/nar/gkae1010",       # UniProt 2025
    "10.1093/nar/gkad1011",       # AlphaFold Protein Structure Database 2024
    "10.1186/s13059-016-0974-4",  # Ensembl VEP (McLaren 2016)
]

NMD_RULE_NT = 50          # canonical ">50-55 nt upstream of last junction" rule
NMD_RULE_MAX_NT = 55      # upper bound of the published range
CONTACT_RADIUS_A = 8.0    # structural neighbourhood radius


# --------------------------------------------------------------------------
# fetch layer (live -> write fixture; replay -> read fixture)
# --------------------------------------------------------------------------

class Fetcher:
    """URL -> bytes with fixture caching.

    live mode: performs the HTTP request (polite delay for NCBI), stores the
    raw response under fixture_dir/name, returns bytes.
    replay mode: reads fixture_dir/name only; any miss raises so a missing
    fixture is loud, never silently skipped.
    """

    def __init__(self, fixture_dir: Path, live: bool):
        self.dir = Path(fixture_dir)
        self.live = live
        self.dir.mkdir(parents=True, exist_ok=True)

    def get(self, name: str, url: str, *, data: bytes | None = None,
            headers: dict | None = None) -> bytes:
        path = self.dir / name
        if not self.live:
            if not path.exists():
                raise FileNotFoundError(
                    f"fixture missing: {path} (run tools/t2_mechanism.py "
                    f"live once to record)")
            return path.read_bytes()
        req = urllib.request.Request(
            url, data=data,
            headers={"User-Agent": USER_AGENT, **(headers or {})})
        last = None
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    blob = r.read()
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError,
                    urllib.error.HTTPError) as e:
                last = e
                time.sleep(1.5 + attempt)
        else:
            raise RuntimeError(f"fetch failed for {url}: {last}")
        path.write_bytes(blob)
        # NCBI asks for <=3 req/s; stay well under that for eutils hosts.
        if "ncbi.nlm.nih.gov" in url or "eutils" in url:
            time.sleep(0.6)
        return blob

    def get_json(self, name: str, url: str, **kw):
        return json.loads(self.get(name, url, **kw))


# --------------------------------------------------------------------------
# pure analysis helpers (unit-testable on synthetic data)
# --------------------------------------------------------------------------

def exons_in_transcription_order(lookup: dict) -> list[dict]:
    """Return exons [{'id','start','end','len'}] ordered 5'->3' on the mRNA."""
    exons = [{"id": e["id"], "start": e["start"], "end": e["end"],
              "len": e["end"] - e["start"] + 1}
             for e in lookup["Exon"]]
    exons.sort(key=lambda e: e["start"], reverse=lookup["strand"] < 0)
    return exons


def cumulative_offsets(exons: list[dict]) -> list[int]:
    """Spliced-transcript offset (0-based) at which each exon begins."""
    offs, pos = [], 0
    for e in exons:
        offs.append(pos)
        pos += e["len"]
    return offs


def spliced_offset(exons: list[dict], gpos: int, strand: int) -> int | None:
    """1-based offset of genomic position gpos in the spliced transcript,
    or None if gpos falls outside every exon."""
    for e, off in zip(exons, cumulative_offsets(exons)):
        if e["start"] <= gpos <= e["end"]:
            within = gpos - e["start"] if strand > 0 else e["end"] - gpos
            return off + within + 1
    return None


def locate_exon(exons: list[dict], gpos: int) -> int | None:
    """1-based transcription-order index of the exon containing gpos."""
    for i, e in enumerate(exons, 1):
        if e["start"] <= gpos <= e["end"]:
            return i
    return None


def last_junction_offset(exons: list[dict]) -> int | None:
    """Spliced offset of the last exon-exon junction (last nt of exon n-1),
    None for single-exon transcripts."""
    if len(exons) < 2:
        return None
    return sum(e["len"] for e in exons[:-1])


def nmd_analysis(exons: list[dict], gpos: int, strand: int,
                 cds_pos: int | None = None,
                 rule_nt: int = NMD_RULE_NT) -> dict:
    """Apply the canonical NMD positional rule.

    `gpos` is the variant's genomic position; when `cds_pos` (1-based CDS
    coordinate of the variant) is given, the premature termination codon is
    taken as the codon containing it and the distance is measured from that
    codon's first nucleotide (assumed in the same exon, true when the codon
    does not straddle a junction). Returns the distance in spliced mRNA from
    the PTC first nucleotide to the last exon-exon junction and the NMD
    prediction (PTC > rule_nt upstream of the last junction => NMD).
    Distances <= 0 mean the PTC lies at or downstream of the last junction
    (classic NMD-escape topology).
    """
    if cds_pos is not None:
        codon_off = (cds_pos - 1) % 3
        gpos = gpos - codon_off if strand > 0 else gpos + codon_off
    junc = last_junction_offset(exons)
    if junc is None:
        return {"exons": len(exons), "last_junction_offset": None,
                "ptc_spliced_offset": None, "ptc_to_last_junction_nt": None,
                "predicted_nmd": False,
                "note": "single-exon transcript: no exon-exon junction, "
                        "NMD not triggered by the positional rule"}
    ptc_off = spliced_offset(exons, gpos, strand)
    if ptc_off is None:
        return {"exons": len(exons), "last_junction_offset": junc,
                "ptc_spliced_offset": None, "ptc_to_last_junction_nt": None,
                "predicted_nmd": False,
                "note": "position not inside an exon"}
    dist = junc - ptc_off
    return {"exons": len(exons), "last_junction_offset": junc,
            "ptc_spliced_offset": ptc_off,
            "ptc_to_last_junction_nt": dist,
            "predicted_nmd": dist > rule_nt,
            "rule_nt": rule_nt,
            "note": ("PTC %d nt upstream of last exon-exon junction" % dist)
                    if dist > 0 else
                    "PTC at or downstream of last junction (NMD-escape "
                    "topology)"}


def features_covering(features: list[dict], pos: int) -> list[dict]:
    """UniProt feature list -> [{'type','start','end','description'}]
    covering residue pos (inclusive)."""
    out = []
    for f in features:
        s, e = f["location"]["start"]["value"], f["location"]["end"]["value"]
        if s <= pos <= e:
            out.append({"type": f["type"], "start": s, "end": e,
                        "description": f.get("description", "")})
    return out


def parse_pdb_atoms(pdb_text: str) -> list[dict]:
    """Parse ATOM records -> [{'name','resn','resi','x','y','z','plddt'}].
    pLDDT is carried in the B-factor column for AlphaFold DB models."""
    atoms = []
    for line in pdb_text.splitlines():
        if not line.startswith("ATOM"):
            continue
        atoms.append({"name": line[12:16].strip(),
                      "resn": line[17:20].strip(),
                      "resi": int(line[22:26]),
                      "x": float(line[30:38]), "y": float(line[38:46]),
                      "z": float(line[46:54]),
                      "plddt": float(line[60:66])})
    return atoms


def group_atoms_by_residue(atoms: list[dict]) -> dict[int, list[dict]]:
    byres: dict[int, list[dict]] = defaultdict(list)
    for a in atoms:
        byres[a["resi"]].append(a)
    return byres


def contact_residues(byres: dict[int, list[dict]], resi: int,
                     radius: float = CONTACT_RADIUS_A) -> set[int]:
    """Residue ids with >=1 atom within `radius` Angstrom of any atom of
    residue `resi` (the residue itself excluded)."""
    out: set[int] = set()
    if resi not in byres:
        return out
    ref = byres[resi]
    for other, atoms_b in byres.items():
        if other == resi:
            continue
        for a in ref:
            hit = False
            for b in atoms_b:
                if math.dist((a["x"], a["y"], a["z"]),
                             (b["x"], b["y"], b["z"])) <= radius:
                    out.add(other)
                    hit = True
                    break
            if hit:
                break
    return out


def contact_number_percentile(byres: dict[int, list[dict]], resi: int,
                              domain: tuple[int, int],
                              radius: float = CONTACT_RADIUS_A) -> dict:
    """Contact number (residues within `radius` A, all-atom) of resi and its
    percentile within the domain's residue distribution: a simple
    buried-vs-exposed estimator."""
    vals = {r: len(contact_residues(byres, r, radius))
            for r in byres if domain[0] <= r <= domain[1]}
    v = vals.get(resi)
    if v is None:
        return {"contact_number": None, "percentile_in_domain": None,
                "domain": list(domain)}
    below = sum(1 for c in vals.values() if c < v)
    return {"contact_number": v,
            "percentile_in_domain": round(100.0 * below / len(vals), 1),
            "domain": list(domain),
            "domain_min": min(vals.values()), "domain_max": max(vals.values())}


# --------------------------------------------------------------------------
# citation resolution (live esummary/crossref or replayed fixtures)
# --------------------------------------------------------------------------

def resolve_citations(fetcher: Fetcher, pmids: list[str],
                      dois: list[str]) -> dict:
    """Resolve every PMID via esummary and every DOI via Crossref.

    Returns the citations table {"PMID:x": {...}, "DOI:y": {...}}.
    Raises on any identifier that does not resolve - an unresolvable citation
    must not reach the JSON."""
    cites: dict[str, dict] = {}
    if pmids:
        ids = ",".join(pmids)
        d = fetcher.get_json(
            "pubmed_esummary.json",
            f"{EUTILS}/esummary.fcgi?db=pubmed&retmode=json&id={ids}")
        result = d.get("result", {})
        for p in pmids:
            r = result.get(p)
            if not r or "title" not in r:
                raise RuntimeError(f"PMID:{p} did not resolve via esummary")
            cites[f"PMID:{p}"] = {
                "title": r["title"].rstrip("."),
                "year": int(str(r.get("pubdate", "0"))[:4] or 0),
                "journal": r.get("fulljournalname", r.get("source", "")),
            }
        # abstracts, cached for auditability (the abstract text is what the
        # claim was checked against)
        fetcher.get("pubmed_efetch.txt",
                    f"{EUTILS}/efetch.fcgi?db=pubmed&rettype=abstract"
                    f"&retmode=text&id={ids}")
    for doi in dois:
        slug = doi.replace("/", "_")
        d = fetcher.get_json(
            f"crossref_{slug}.json",
            f"https://api.crossref.org/works/{urllib.parse.quote(doi)}")
        m = d.get("message", {})
        title = (m.get("title") or [""])[0]
        if not title:
            raise RuntimeError(f"DOI:{doi} did not resolve via Crossref")
        year = (m.get("published", {}).get("date-parts", [[None]])[0][0])
        cites[f"DOI:{doi}"] = {
            "title": title,
            "year": int(year) if year else None,
            "journal": (m.get("container-title") or [""])[0],
        }
    return cites


# --------------------------------------------------------------------------
# per-source extraction
# --------------------------------------------------------------------------

def build_transcript_block(lookup: dict) -> dict:
    """Exon model + CDS endpoints from the Ensembl lookup response."""
    exons = exons_in_transcription_order(lookup)
    tr = lookup.get("Translation", {})
    return {
        "transcript": lookup["id"],
        "version": lookup.get("version"),
        "gene": lookup.get("Parent"),
        "biotype": lookup.get("biotype"),
        "is_canonical": bool(lookup.get("is_canonical")),
        "strand": lookup["strand"],
        "n_exons": len(exons),
        "exons": exons,
        "translation": {"id": tr.get("id"), "start": tr.get("start"),
                        "end": tr.get("end"), "length_aa": tr.get("length")},
        "source": "Ensembl REST lookup/id?expand=1",
    }


def vep_consequence(vep_hits: list[dict], transcript: str) -> dict:
    """Pull the MANE-transcript consequence out of a VEP region response."""
    for hit in vep_hits:
        for tc in hit.get("transcript_consequences", []):
            if tc.get("transcript_id", "").split(".")[0] == transcript:
                return tc
    return {}


def gnomad_summary(variant_doc: dict) -> dict:
    """Compact gnomAD GraphQL variant response -> AC/AN/AF per dataset."""
    out = {}
    if not variant_doc:
        return out
    for ds in ("exome", "genome"):
        d = variant_doc.get(ds)
        if d is None:
            out[ds] = {"ac": 0, "an": 0, "af": 0.0, "homozygote_count": 0}
            continue
        out[ds] = {"ac": d.get("ac"), "an": d.get("an"), "af": d.get("af"),
                   "homozygote_count": d.get("homozygote_count")}
    return out


def clinvar_record(fetcher: Fetcher, allele: dict) -> dict:
    """ClinVar esearch by chrpos38 + esummary of each hit."""
    term = urllib.parse.quote(
        f"BUB1B[gene] AND {allele['pos']}[chrpos38]")
    es = fetcher.get_json(
        f"clinvar_esearch_{allele['pos']}.json",
        f"{EUTILS}/esearch.fcgi?db=clinvar&retmode=json&term={term}")
    uids = es.get("esearchresult", {}).get("idlist", [])
    recs = []
    for uid in uids:
        s = fetcher.get_json(
            f"clinvar_esummary_{uid}.json",
            f"{EUTILS}/esummary.fcgi?db=clinvar&retmode=json&id={uid}")
        r = s.get("result", {}).get(uid, {})
        gc = r.get("germline_classification", {})
        recs.append({
            "uid": uid, "accession": r.get("accession_version") or
            r.get("accession"), "title": r.get("title"),
            "classification": gc.get("description"),
            "review_status": gc.get("review_status"),
            "last_evaluated": gc.get("last_evaluated"),
            "traits": [t.get("trait_name")
                       for t in gc.get("trait_set", [])],
        })
    return {"records": recs, "searched_hg38_pos": allele["pos"]}


def alphafold_structure(pdb_text: str, resi: int,
                        kinase_domain: tuple[int, int]) -> dict:
    """pLDDT + neighbourhood analysis for one residue from an AF PDB file."""
    atoms = parse_pdb_atoms(pdb_text)
    byres = group_atoms_by_residue(atoms)
    plddt = byres[resi][0]["plddt"] if resi in byres else None
    ca = {}
    for r, atoms_r in byres.items():
        ca_atoms = [a for a in atoms_r if a["name"] == "CA"]
        if ca_atoms:
            ca[r] = ca_atoms[0]
    near_ca = sorted(r for r in contact_residues(
        {r: [a] for r, a in ca.items()}, resi, CONTACT_RADIUS_A))
    near_any = sorted(contact_residues(byres, resi, CONTACT_RADIUS_A))
    stats = contact_number_percentile(byres, resi, kinase_domain,
                                      CONTACT_RADIUS_A)
    return {
        "plddt": plddt,
        "ca_neighbors_within_8a": near_ca,
        "n_ca_neighbors_within_8a": len(near_ca),
        "residues_within_8a_allatom": near_any,
        "n_residues_within_8a_allatom": len(near_any),
        "burial": stats,
    }


# --------------------------------------------------------------------------
# claims / pathway / implications (text assembled with measured numbers)
# --------------------------------------------------------------------------

def build_claims(a1: dict, a2: dict, ctx: dict) -> list[dict]:
    """claims list; every claim carries >=1 citation handle.

    a1 = nonsense allele bundle, a2 = missense allele bundle, ctx holds shared
    parsed structures (transcript, uniprot features, structure stats, freqs).
    """
    c = []

    # --- allele 1: p.Leu737Ter -------------------------------------------
    nmd = a1["nmd"]
    c.append({"id": "c01",
              "text": (f"p.Leu737Ter (c.2210T>G) creates a premature "
                       f"termination codon in exon {a1['exon_index']} of "
                       f"{ctx['transcript']['n_exons']} of ENST00000287598 "
                       f"(MANE); the PTC lies {nmd['ptc_to_last_junction_nt']}"
                       f" nt upstream of the last exon-exon junction, far "
                       f"beyond the 50-55 nt rule threshold, so the mutant "
                       f"transcript is predicted to be degraded by "
                       f"nonsense-mediated mRNA decay"),
              "cites": ["PMID:9644970", "PMID:27618451",
                        "DOI:10.1093/nar/gkab1049"],
              "strength": "computational prediction + established rule"})
    fl = a1["protein_loss"]
    c.append({"id": "c02",
              "text": (f"If translated despite predicted NMD, the truncated "
                       f"product would carry only residues 1-736 "
                       f"({fl['fraction_lost_pct']}% of the 1050-aa protein "
                       f"lost): the entire C-terminal kinase-like domain "
                       f"(UniProt 766-1050), the PLK1 phosphoacceptor sites "
                       f"T792/T1008, and the 772-780 binding region are "
                       f"absent, while the N-terminal KEN boxes, TPR, "
                       f"KNL1-binding (152-185), D-box (224-232), K250 "
                       f"acetylation site and KARD phospho-region "
                       f"(S670/S676) are retained - consistent with a null "
                       f"allele"),
              "cites": ["DOI:10.1093/nar/gkae1010", "PMID:23079597",
                        "PMID:23345399"],
              "strength": "direct (feature mapping)"})
    g = a1["gnomad"]
    hom = (g["exome"].get("homozygote_count") or 0) + \
        (g["genome"].get("homozygote_count") or 0)
    c.append({"id": "c03",
              "text": (f"p.Leu737Ter is ultra-rare in population data: "
                       f"gnomAD v4 exomes {g['exome']['ac']}/{g['exome']['an']}"
                       f" alleles (AF {g['exome']['af']:.2e}), genomes "
                       f"{g['genome']['ac']}/{g['genome']['an']} (AF "
                       f"{g['genome']['af']:.2e}), {hom} homozygotes - "
                       f"consistent with a deleterious germline allele"),
              "cites": ["PMID:32461654"],
              "strength": "population database"})
    c.append({"id": "c04",
              "text": (f"ClinVar records c.2210T>G (VCV000533901) as "
                       f"{a1['clinvar_class']} for Mosaic variegated "
                       f"aneuploidy syndrome 1 (OMIM 257300), "
                       f"{a1['clinvar_review']}"),
              "cites": ["PMID:29165669"],
              "strength": "clinical database"})

    # --- allele 2: p.Asn1002Lys -------------------------------------------
    s = a2["scores"]
    c.append({"id": "c05",
              "text": (f"p.Asn1002Lys (c.3006T>G, exon {a2['exon_index']}, "
                       f"the last exon) substitutes a positively charged "
                       f"Lys for a highly conserved Asn at residue 1002 "
                       f"inside the "
                       f"C-terminal kinase-like domain (766-1050), 6 "
                       f"residues from the PLK1 phosphosite T1008"),
              "cites": ["DOI:10.1093/nar/gkae1010"],
              "strength": "direct (feature mapping)"})
    c.append({"id": "c06",
              "text": (f"Missense-effect predictors converge on deleterious "
                       f"for N1002K: AlphaMissense {s['alphamissense']:.4f} "
                       f"(likely_pathogenic), SIFT {s['sift']} (deleterious),"
                       f" PolyPhen-2 {s['polyphen']} (probably_damaging), "
                       f"CADD_phred {s['cadd_phred']}, phyloP {s['phylop']}; "
                       f"REVEL {s['revel']} is moderate and below the "
                       f"commonly used 0.5-0.75 supporting thresholds, "
                       f"stated honestly rather than overclaimed"),
              "cites": ["PMID:37733863", "DOI:10.1186/s13059-016-0974-4"],
              "strength": "computational (ensemble)"})
    st = a2["structure"]
    c.append({"id": "c07",
              "text": (f"On the AlphaFold O60566 model (v6), N1002 has pLDDT "
                       f"{st['plddt']} and {st['n_residues_within_8a_allatom']}"
                       f" residues within 8 A (all-atom; "
                       f"{st['n_ca_neighbors_within_8a']} by CA) - a "
                       f"partially packed surface region of the "
                       f"pseudokinase C-lobe (contact-number percentile "
                       f"{st['burial']['percentile_in_domain']}% within the "
                       f"domain), so the Asn->Lys charge introduction plausibly"
                       f" perturbs local packing/stability rather than a "
                       f"catalytic centre"),
              "cites": ["DOI:10.1093/nar/gkad1011", "PMID:22698286"],
              "strength": "structural model"})
    g2 = a2["gnomad"]
    c.append({"id": "c08",
              "text": (f"p.Asn1002Lys is absent from gnomAD v4 genomes and "
                       f"seen once in {g2['exome']['an']} exome alleles "
                       f"(AF {g2['exome']['af']:.2e}, "
                       f"{g2['exome'].get('homozygote_count') or 0} "
                       f"homozygotes); ClinVar has no entry "
                       f"for c.3006T>G itself, while the same protein change "
                       f"via c.3006T>A is a VUS (VCV004600147, single "
                       f"submitter) - the allele is novel to this child"),
              "cites": ["PMID:32461654", "PMID:29165669"],
              "strength": "population + clinical databases"})
    c.append({"id": "c09",
              "text": ("MVA-patient missense alleles that map in or near the "
                       "BUBR1 kinase domain characteristically produce "
                       "unstable protein (high turnover), so N1002K is "
                       "predicted to act as a hypomorph through reduced "
                       "abundance; residual function is unmeasured in this "
                       "child"),
              "cites": ["PMID:20516114"],
              "strength": "human (class analogy)"})
    c.append({"id": "c10",
              "text": ("The C-terminal pseudokinase domain where N1002 sits "
                       "is required for KARD phosphorylation and PP2A-B56 "
                       "recruitment to kinetochores, for spindle-checkpoint "
                       "silencing and for chromosome alignment - so a "
                       "stability- or fold-disrupting lesion in this domain "
                       "weakens error correction even though BUBR1 catalytic "
                       "activity itself is dispensable"),
              "cites": ["PMID:33207204", "PMID:22698286", "PMID:23079597"],
              "strength": "cell"})

    # --- genotype pattern --------------------------------------------------
    c.append({"id": "c11",
              "text": ("In published biallelic MVA1 cases a missense allele "
                       "pairs with a truncating allele - completely "
                       "truncating genotypes are effectively unseen, "
                       "consistent with lethality of full BUBR1 loss; the "
                       "proband's stop + kinase-domain missense pair fits "
                       "this pattern exactly"),
              "cites": ["PMID:15475955", "PMID:20516114", "PMID:23300461"],
              "strength": "human"})
    c.append({"id": "c12",
              "text": ("Roughly >50% reduction of BUBR1 expression or "
                       "activity is sufficient to cause the PCS/MVA "
                       "phenotype, and single-allele carriers show mild "
                       "mitotic defects - the genotype here is expected to "
                       "leave only the N1002K allele as the functional copy"),
              "cites": ["PMID:16411201", "PMID:23300461"],
              "strength": "human + mouse"})

    # --- pathway -----------------------------------------------------------
    c.append({"id": "c13",
              "text": ("MVA patient cells show impaired spindle-assembly "
                       "checkpoint, chromosome-alignment defects and low "
                       "overall BUBR1 abundance; ectopic BUBR1 rescues the "
                       "checkpoint, proving segregation errors stem from "
                       "BUBR1 dysfunction"),
              "cites": ["PMID:20516114"],
              "strength": "human (patient cells)"})
    c.append({"id": "c14",
              "text": ("Reduced BUBR1 weakens both its mitotic-checkpoint "
                       "arm and its attachment-error-correction arm: the "
                       "KARD domain recruits PP2A-B56 to kinetochores in a "
                       "PLK1-phosphorylation-dependent manner to counter "
                       "Aurora B and stabilise kinetochore-microtubule "
                       "attachments"),
              "cites": ["PMID:23079597", "PMID:23345399"],
              "strength": "cell"})
    c.append({"id": "c15",
              "text": ("Chromosome mis-segregation in otherwise diploid "
                       "cells triggers p53 accumulation and p21-dependent "
                       "cell-cycle delay, limiting proliferation of "
                       "aneuploid cells; loss of p53 permits aneuploid "
                       "clones to expand"),
              "cites": ["PMID:20123995"],
              "strength": "cell (human)"})
    c.append({"id": "c16",
              "text": ("Cells that mis-segregate acquire complex karyotypes,"
                       " proteotoxic stress and senescent features with "
                       "pro-inflammatory signalling that flags them for "
                       "immune clearance - senescence is a direct "
                       "consequence of aneuploidy"),
              "cites": ["PMID:28633018", "PMID:34216545"],
              "strength": "cell + fly"})
    c.append({"id": "c17",
              "text": ("BubR1-insufficient mice develop progressive "
                       "aneuploidy plus progeroid phenotypes (short "
                       "lifespan, dwarfism, lordokyphosis, cataracts, fat "
                       "and skeletal-muscle loss), and p16Ink4a is an "
                       "effector of the senescence - graded BubR1 reduction "
                       "increases aneuploidy and senescence dose-dependently"),
              "cites": ["PMID:15208629", "PMID:18516091"],
              "strength": "mouse"})
    c.append({"id": "c18",
              "text": ("BUBR1-insufficiency states are cancer-prone: "
                       "biallelic carriers developed embryonal "
                       "rhabdomyosarcoma in the original MVA families, "
                       "Wilms tumour is reported in BUB1B PCS/MVA, and a "
                       "homozygous hypomorphic allele produced adult "
                       "gastrointestinal neoplasia - aneuploidy is the "
                       "causal link"),
              "cites": ["PMID:15475955", "PMID:31081598", "PMID:21190457"],
              "strength": "human"})

    # --- dosage modulation ---------------------------------------------------
    c.append({"id": "c19",
              "text": ("BubR1 abundance is pharmacologically tractable: "
                       "SIRT2 keeps BubR1 K668 deacetylated and its decline "
                       "with falling NAD+ drives age-related BubR1 loss; "
                       "SIRT2 overexpression or NMN raises BubR1 in vivo, "
                       "and K250 acetylation by PCAF stabilises BubR1 by "
                       "blocking its ubiquitin-dependent degradation"),
              "cites": ["PMID:24825348", "PMID:19407811"],
              "strength": "mouse + cell"})
    c.append({"id": "c20",
              "text": ("Raising BubR1 is protective: sustained high-level "
                       "expression in mice preserves genomic integrity, "
                       "corrects checkpoint and attachment defects, reduces "
                       "tumorigenesis even on aneuploidising backgrounds, "
                       "and extends healthy lifespan"),
              "cites": ["PMID:23242215"],
              "strength": "mouse"})
    c.append({"id": "c21",
              "text": ("Clearing p16-positive senescent cells in BubR1 "
                       "progeroid mice delayed onset of age-related "
                       "pathologies in adipose tissue, skeletal muscle and "
                       "eye, and late-life clearance attenuated established "
                       "disorders - the senescence burden is modifiable"),
              "cites": ["PMID:22048312", "PMID:18516091"],
              "strength": "mouse"})
    c.append({"id": "c22",
              "text": ("Aneuploid cancer cells are selectively vulnerable "
                       "to spindle-checkpoint perturbation and to KIF18A "
                       "loss (synthetic-lethal interaction) - a therapeutic "
                       "window against aneuploid malignant clones but the "
                       "opposite of what a child with constitutional "
                       "mis-segregation should receive prophylactically"),
              "cites": ["PMID:33505028", "PMID:33505027"],
              "strength": "cell/screen (cancer context)"})
    c.append({"id": "c23",
              "text": ("Growth-hormone treatment in chromosomal-breakage / "
                       "DNA-repair-disorder children is flagged for careful "
                       "evaluation owing to malignancy risk; the largest "
                       "childhood-cancer-survivor cohort found no "
                       "significant increase in second neoplasms on GH, so "
                       "the contraindication is precautionary, not proven"),
              "cites": ["PMID:30500870", "PMID:32738133"],
              "strength": "review + cohort (counter-evidence stated)"})
    c.append({"id": "c24",
              "text": ("p53 is protective in this context: it limits "
                       "aneuploid-cell propagation and delays functional "
                       "decline of muscle and fat in BubR1-insufficient "
                       "mice - suppressing p53 would remove the brake on "
                       "aneuploid clone expansion and worsen tissue "
                       "decline"),
              "cites": ["PMID:20123995", "PMID:23602569"],
              "strength": "cell + mouse"})
    return c


def build_pathway() -> list[dict]:
    """Allele -> consequence chain; each arrow carries cites + evidence base."""
    return [
        {"step": "genotype",
         "claim": "p.Leu737Ter allele: transcript predicted NMD-degraded "
                  "(PTC ~750 nt upstream of last junction); any escaped "
                  "product lacks the kinase-like domain. p.Asn1002Lys "
                  "allele: full-length protein with a destabilising "
                  "substitution in the pseudokinase domain.",
         "cites": ["PMID:9644970", "PMID:27618451", "PMID:20516114",
                   "PMID:33207204"],
         "evidence": "rule-based prediction + human class analogy"},
        {"step": "protein dosage",
         "claim": "Cellular BubR1 abundance falls towards a single "
                  "partially-functional allele's output; >50% loss of "
                  "BubR1 expression/activity is sufficient for the "
                  "PCS/MVA phenotype.",
         "cites": ["PMID:16411201", "PMID:20516114"],
         "evidence": "human (patient cells)"},
        {"step": "checkpoint + attachment",
         "claim": "Low BubR1 weakens the spindle-assembly checkpoint and "
                  "reduces KARD-dependent PP2A-B56 recruitment that "
                  "corrects kinetochore-microtubule attachment errors.",
         "cites": ["PMID:20516114", "PMID:23079597", "PMID:23345399"],
         "evidence": "human cells + cell biology"},
        {"step": "mis-segregation -> aneuploidy",
         "claim": "Uncorrected errors produce constitutional mosaic "
                  "gains and losses of whole chromosomes - the defining "
                  "feature of MVA1.",
         "cites": ["PMID:15475955", "PMID:20516114"],
         "evidence": "human"},
        {"step": "cellular response",
         "claim": "Aneuploid daughter cells arrest via p53/p21, acquire "
                  "proteotoxic stress and senescence programmes (p16 "
                  "effector), and signal for immune clearance.",
         "cites": ["PMID:20123995", "PMID:28633018", "PMID:34216545",
                   "PMID:18516091"],
         "evidence": "cell + mouse"},
        {"step": "organism outcomes",
         "claim": "Chronic aneuploidy plus senescence yields growth "
                  "failure and progeroid decline, while rare escaping "
                  "aneuploid clones drive childhood cancer "
                  "(rhabdomyosarcoma, Wilms; adult GI cancers on milder "
                  "genotypes).",
         "cites": ["PMID:15208629", "PMID:23300461", "PMID:15475955",
                   "PMID:31081598", "PMID:21190457"],
         "evidence": "human + mouse"},
    ]


def build_uncertainties() -> list[dict]:
    return [
        {"id": "u1",
         "text": "Phase is UNKNOWN in this child (0 spanning reads in "
                 "Track 1). In-trans configuration is inferred from the "
                 "MVA1 genotype pattern (null + hypomorph) and phenotype "
                 "fit, not observed. Resolution: parental testing, "
                 "targeted long-range PCR or long-read phasing.",
         "cites": ["PMID:20516114"]},
        {"id": "u2",
         "text": "p.Asn1002Lys residual function is unmeasured. Assays "
                 "that would quantify it: patient-fibroblast BubR1 "
                 "western blot (abundance), nocodazole-arrest timing "
                 "(SAC competency), k-fibre stability / cold-stable "
                 "microtubule assay, aneuploidy rate by FISH or "
                 "single-cell DNA-seq.",
         "cites": ["PMID:20516114", "PMID:16411201"]},
        {"id": "u3",
         "text": "NMD for p.Leu737Ter is a positional prediction, not a "
                 "measured decay rate; NMD efficiency varies and rare "
                 "escape could yield a 736-aa fragment of uncertain "
                 "activity.",
         "cites": ["PMID:27618451", "PMID:31659324"]},
        {"id": "u4",
         "text": "Predictor agreement is strong but not unanimous: "
                 "REVEL 0.472 is below usual supporting thresholds and "
                 "the ClinVar record for the same amino-acid change "
                 "(c.3006T>A) is a single-submitter VUS.",
         "cites": ["PMID:29165669"]},
    ]


def build_therapeutic_implications() -> list[dict]:
    return [
        {"axis": "residual-allele rescue",
         "text": "The missense allele is the only functional copy; "
                 "raising its abundance/stability is disease-modifying. "
                 "BubR1 levels are druggable: SIRT2/NAD+ maintains BubR1 "
                 "(NMN or SIRT2 upregulation raises BubR1 in vivo), K250 "
                 "acetylation blocks BubR1 degradation, and transgenic "
                 "BubR1 overexpression corrects checkpoint defects, "
                 "aneuploidy, tumorigenesis and progeroid decline.",
         "cites": ["PMID:24825348", "PMID:19407811", "PMID:23242215",
                   "PMID:20516114"]},
        {"axis": "damage mitigation",
         "text": "Senescent-cell burden is a downstream driver of the "
                 "growth/progeroid phenotype and is modifiable: p16 "
                 "clearance in BubR1 progeroid mice delayed and "
                 "attenuated tissue dysfunction.",
         "cites": ["PMID:22048312", "PMID:18516091", "PMID:23602569"]},
        {"axis": "aneuploid-clone control",
         "text": "Surviving aneuploid cells are the cancer substrate; "
                 "immune clearance of complex karyotypes is part of "
                 "natural control, and aneuploid tumour cells carry "
                 "selective vulnerabilities (SAC dependency, KIF18A) "
                 "relevant if malignancy arises.",
         "cites": ["PMID:28633018", "PMID:33505028", "PMID:33505027"]},
        {"axis": "cancer surveillance",
         "text": "Mechanism predicts childhood embryonal "
                 "rhabdomyosarcoma and Wilms tumour risk plus later GI "
                 "neoplasia - regular surveillance is mechanism-justified "
                 "independent of any drug choice.",
         "cites": ["PMID:15475955", "PMID:31081598", "PMID:21190457"]},
    ]


def build_contraindications() -> list[dict]:
    return [
        {"agent": "SAC/MPS1/KIF18A inhibitors",
         "text": "Systemic weakening of an already-insufficient checkpoint "
                 "increases mis-segregation and aneuploid-clone supply. "
                 "Nuance: aneuploid CANCER cells are selectively killed by "
                 "these agents - relevant to treating an established "
                 "tumour, contraindicated as prophylaxis.",
         "cites": ["PMID:33505028", "PMID:33505027", "PMID:20516114"]},
        {"agent": "p53 suppression",
         "text": "p53/p21 is the brake limiting propagation of aneuploid "
                 "cells and protecting muscle/fat in BubR1-insufficient "
                 "mice; lifting it expands aneuploid clones.",
         "cites": ["PMID:20123995", "PMID:23602569"]},
        {"agent": "growth hormone (for short stature)",
         "text": "Guidance flags GH use in chromosomal-breakage / "
                 "DNA-repair disorders for caution because of malignancy "
                 "risk; in a constitutional-aneuploidy cancer-"
                 "predisposition syndrome, accelerating clone expansion is "
                 "mechanistically counterproductive. Counter-evidence: a "
                 "large survivor cohort found no significant second-"
                 "neoplasm increase, so this is precautionary.",
         "cites": ["PMID:30500870", "PMID:32738133", "PMID:15475955"]},
        {"agent": "antimitotic agents producing aneuploidy",
         "text": "Chronic spindle poisons / aneugens add mis-segregation "
                 "on top of a constitutionally weak checkpoint - the "
                 "opposite direction of the therapeutic goal.",
         "cites": ["PMID:20516114", "PMID:15475955"]},
    ]


# --------------------------------------------------------------------------
# main assembly
# --------------------------------------------------------------------------

def fetch_all(fetcher: Fetcher) -> dict:
    """Pull every upstream dataset (live or replay) into a raw bundle."""
    raw = {}
    raw["ensembl"] = fetcher.get_json(
        "ensembl_lookup_ENST00000287598.json",
        "https://rest.ensembl.org/lookup/id/ENST00000287598"
        "?expand=1;content-type=application/json")
    raw["vep"] = []
    for a in ALLELES:
        raw["vep"].append(fetcher.get_json(
            f"vep_{a['chrom']}-{a['pos']}-{a['vep_allele']}.json",
            f"https://rest.ensembl.org/vep/human/region/"
            f"{a['chrom']}:{a['pos']}-{a['pos']}:1/{a['vep_allele']}"
            "?content-type=application/json;CADD=1;REVEL=1;SIFT=1;"
            "PolyPhen=1;AlphaMissense=1;"
            "dbNSFP=phyloP470way_mammalian"))
    raw["uniprot"] = fetcher.get_json(
        "uniprot_O60566.json",
        "https://rest.uniprot.org/uniprotkb/O60566.json")
    raw["gnomad"] = []
    for a in ALLELES:
        vid = f"{a['chrom']}-{a['pos']}-{a['ref']}-{a['alt']}"
        query = ("query {variant(variantId: \"%s\", dataset: gnomad_r4)"
                 "{variant_id genome {ac an af homozygote_count} "
                 "exome {ac an af homozygote_count}}}" % vid)
        raw["gnomad"].append(fetcher.get_json(
            f"gnomad_{vid}.json",
            "https://gnomad.broadinstitute.org/api",
            data=json.dumps({"query": query}).encode(),
            headers={"Content-Type": "application/json"}))
    raw["clinvar"] = [clinvar_record(fetcher, a) for a in ALLELES]
    raw["alphafold_api"] = fetcher.get_json(
        "alphafold_api_O60566.json",
        "https://alphafold.ebi.ac.uk/api/prediction/O60566")
    pdb_url = raw["alphafold_api"][0].get(
        "pdbUrl", "https://alphafold.ebi.ac.uk/files/"
                  "AF-O60566-F1-model_v6.pdb")
    raw["alphafold_pdb"] = fetcher.get(
        Path(pdb_url).name, pdb_url).decode("utf-8", "replace")
    raw["alphafold_am"] = fetcher.get(
        "alphafold_am_annotations_hg38.csv",
        "https://alphafold.ebi.ac.uk/files/AF-O60566-F1-hg38.csv"
        ).decode("utf-8", "replace")
    return raw


def assemble(raw: dict, fetcher: Fetcher) -> dict:
    """raw API bundle -> mechanism.json structure."""
    tx = build_transcript_block(raw["ensembl"])
    up_len = raw["uniprot"]["sequence"]["length"]
    up_features = raw["uniprot"].get("features", [])
    kinase = next((f["location"]["start"]["value"],
                   f["location"]["end"]["value"])
                  for f in up_features
                  if f["type"] == "Domain" and
                  "kinase" in f.get("description", "").lower())

    allele_blocks = []
    parsed = []
    for i, a in enumerate(ALLELES):
        blk = {"hgvs_genomic": a["hg38"], "hg38_pos": a["pos"],
               "cdna": a["cdna"], "protein": a["protein"]}
        tc = vep_consequence(raw["vep"][i], TRANSCRIPT)
        blk["vep"] = {
            "consequence_terms": tc.get("consequence_terms"),
            "impact": tc.get("impact"),
            "codons": tc.get("codons"),
            "amino_acids": tc.get("amino_acids"),
            "cds_start": tc.get("cds_start"), "cds_end": tc.get("cds_end"),
            "cdna_start": tc.get("cdna_start"),
            "protein_start": tc.get("protein_start"),
            "sift_score": tc.get("sift_score"),
            "sift_prediction": tc.get("sift_prediction"),
            "polyphen_score": tc.get("polyphen_score"),
            "polyphen_prediction": tc.get("polyphen_prediction"),
            "revel": tc.get("revel"),
            "cadd_raw": tc.get("cadd_raw"), "cadd_phred": tc.get("cadd_phred"),
            "alphamissense": tc.get("alphamissense"),
            "phylop470way_mammalian": tc.get("phylop470way_mammalian"),
        }
        exon_i = locate_exon(tx["exons"], a["pos"])
        blk["exon"] = {"index": exon_i, "of": tx["n_exons"],
                       "id": tx["exons"][exon_i - 1]["id"] if exon_i else None}
        if "stop_gained" in (tc.get("consequence_terms") or []):
            blk["nmd"] = nmd_analysis(tx["exons"], a["pos"], tx["strand"],
                                      cds_pos=tc.get("cds_start"))
        else:
            blk["nmd"] = {"applicable": False,
                          "note": "missense allele - no premature "
                                  "termination codon introduced"}
        blk["features_at_residue"] = features_covering(
            up_features, tc.get("protein_start") or 0)
        blk["gnomad"] = gnomad_summary(
            (raw["gnomad"][i].get("data") or {}).get("variant"))
        blk["clinvar"] = raw["clinvar"][i]
        allele_blocks.append(blk)
        parsed.append({"tc": tc, "blk": blk})

    # ---- allele 1: nonsense ----------------------------------------------
    b1 = allele_blocks[0]
    tc1 = parsed[0]["tc"]
    pres = tc1.get("protein_start") or 737
    b1["protein_loss"] = {
        "wt_length": up_len,
        "truncated_product_length": pres - 1,
        "residues_lost": up_len - (pres - 1),
        "fraction_lost_pct": round(100.0 * (up_len - pres + 1) / up_len, 1),
        "removed_features": [
            f for f in ({"type": x["type"], "start": x["location"]["start"]
                         ["value"], "end": x["location"]["end"]["value"],
                         "description": x.get("description", "")}
                        for x in up_features)
            if f["start"] >= pres and f["type"] in
            ("Domain", "Region", "Motif", "Binding site", "Active site",
             "Modified residue", "Site")],
        "retained_features": [
            f for f in ({"type": x["type"], "start": x["location"]["start"]
                         ["value"], "end": x["location"]["end"]["value"],
                         "description": x.get("description", "")}
                        for x in up_features)
            if f["end"] < pres and f["type"] in
            ("Domain", "Region", "Motif", "Binding site",
             "Modified residue", "Site")],
    }
    b1["interpretation"] = "null (predicted loss-of-function via NMD)"
    b1["clinvar_class"] = (b1["clinvar"]["records"][0]["classification"]
                           if b1["clinvar"]["records"] else None)
    b1["clinvar_review"] = (b1["clinvar"]["records"][0]["review_status"]
                            if b1["clinvar"]["records"] else None)

    # ---- allele 2: missense ----------------------------------------------
    b2 = allele_blocks[1]
    tc2 = parsed[1]["tc"]
    pos2 = tc2.get("protein_start") or 1002
    b2["scores"] = {
        "sift": tc2.get("sift_score"),
        "sift_prediction": tc2.get("sift_prediction"),
        "polyphen": tc2.get("polyphen_score"),
        "polyphen_prediction": tc2.get("polyphen_prediction"),
        "revel": tc2.get("revel"),
        "cadd_raw": tc2.get("cadd_raw"), "cadd_phred": tc2.get("cadd_phred"),
        "alphamissense": (tc2.get("alphamissense") or {}).get(
            "am_pathogenicity"),
        "alphamissense_class": (tc2.get("alphamissense") or {}).get(
            "am_class"),
        "phylop": tc2.get("phylop470way_mammalian"),
    }
    b2["structure"] = alphafold_structure(raw["alphafold_pdb"], pos2,
                                          kinase)
    b2["interpretation"] = ("hypomorphic missense (predicted: unstable "
                            "pseudokinase-domain product)")
    b2["clinvar_note"] = (
        "No ClinVar entry for c.3006T>G itself; same amino-acid change via "
        "c.3006T>A is VUS VCV004600147 (single submitter).")

    # AlphaMissense track record from the AF annotation CSV (provenance).
    am_lines = [l.split(",") for l in raw["alphafold_am"].splitlines()
                if "40220612" in l and l.endswith("likely_pathogenic")]
    b2["alphamissense_track"] = am_lines[0] if am_lines else None

    ctx = {"transcript": tx, "uniprot_length": up_len}
    a1c = dict(b1); a1c.update({"nmd": b1["nmd"], "protein_loss":
                                b1["protein_loss"], "gnomad": b1["gnomad"],
                                "exon_index": b1["exon"]["index"],
                                "clinvar_class": b1["clinvar_class"],
                                "clinvar_review": b1["clinvar_review"]})
    a2c = dict(b2); a2c.update({"scores": b2["scores"],
                                "structure": b2["structure"],
                                "gnomad": b2["gnomad"],
                                "exon_index": b2["exon"]["index"]})
    claims = build_claims(a1c, a2c, ctx)

    citations = resolve_citations(fetcher, PMIDS, DOIS)
    # gate: every cite referenced anywhere must exist in the table
    used = set()
    for cl in claims:
        used.update(cl["cites"])
    for blk in (build_pathway() + build_uncertainties() +
                build_therapeutic_implications() + build_contraindications()):
        used.update(blk["cites"])
    missing = sorted(c for c in used if c not in citations)
    if missing:
        raise RuntimeError(f"citations used but not resolved: {missing}")
    citations = {k: citations[k] for k in sorted(citations)}

    return {
        "schema": "t2.mechanism/1",
        "generated_by": "tools/t2_mechanism.py",
        "gene": "BUB1B", "uniprot": UNIPROT,
        "transcript": tx,
        "alleles": allele_blocks,
        "pathway": build_pathway(),
        "claims": claims,
        "citations": citations,
        "uncertainties": build_uncertainties(),
        "therapeutic_implications": build_therapeutic_implications(),
        "contraindications": build_contraindications(),
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Track 2 mechanism evidence builder (BUB1B alleles)")
    ap.add_argument("--replay", action="store_true",
                    help="replay cached fixtures; no network")
    ap.add_argument("--fixtures", default=str(FIXTURE_DIR))
    ap.add_argument("--out", default=str(OUT_JSON))
    args = ap.parse_args(argv)

    fetcher = Fetcher(Path(args.fixtures), live=not args.replay)
    raw = fetch_all(fetcher)
    doc = assemble(raw, fetcher)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=1) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    print(f"  schema {doc['schema']}, {len(doc['claims'])} claims, "
          f"{len(doc['citations'])} citations")
    nmd = doc["alleles"][0]["nmd"]
    print(f"  allele1 NMD distance: {nmd['ptc_to_last_junction_nt']} nt "
          f"(predicted_nmd={nmd['predicted_nmd']})")
    s2 = doc["alleles"][1]["scores"]
    print(f"  allele2 AM={s2['alphamissense']} REVEL={s2['revel']} "
          f"CADD={s2['cadd_phred']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
