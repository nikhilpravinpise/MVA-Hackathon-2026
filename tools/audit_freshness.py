"""Freshness auditor - every checkable claim in the live docs vs the
artifacts on disk.

Rationale (plan.md doctrine): the repo's credibility rests on "verify,
don't claim". This tool makes staleness a checked property rather than a
maintained hope: numbers cited in README/status/checklist are compared
against the artifacts they claim to summarize, file references are
resolved on disk, the three submission CSV copies are byte-compared and
re-scored through the vendored oracle, and hygiene scans catch
typo-class drift (em-dashes, future dates, leftover TODOs).

Dated/append-only ledgers (decisions.md, llm_log.md, runtime_log.md,
*_audit_*.md, plan.md, DEEP_DIVE.md) are exempt from number checks -
their rows are point-in-time records. Live docs only.

    python tools/audit_freshness.py            # table, exit 1 on FAIL
    make freshness                             # same thing
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

TODAY = date.today().isoformat()
PY = sys.executable

# Docs whose claims describe CURRENT state (staleness-checked). Dated
# audits, append-only ledgers, and the status-dated plan/deep-dive are
# historical records - banners mark them, numbers stay as-written.
LIVE_DOCS = [
    "README.md",
    "docs/report.md",
    "docs/report_map.md",
    "docs/report_model2.md",
    "docs/status.md",
    "docs/submission_checklist.md",
    "docs/track1_closeout.md",
    "docs/team.md",
    "docs/rubric_self_assessment.md",
    "docs/FAMILY_EXPLAINER.md",
    "docs/ANSWER_BLIND_PROTOCOL.md",
    "docs/disclosure_position.md",
    "docs/deletion_runbook.md",
    "docs/figures/pileup_ascii.md",
    "submissions/README.md",
    "nikhilpise_track1_report.md",
]

RUN = "results/track1_patient_modal/track1_final_indelfix"
ARMS = "results/track1_patient_modal/track1_final"
GT = frozenset([("chr15", 40209701, "T", "G"),
                ("chr15", 40220612, "T", "G")])


# The run outputs live under the gitignored results/ tree: present on the
# machine that produced them, absent in a fresh clone or a worktree. The
# checks that read them report WARN there instead of FAIL, matching the
# skip the pytest wrappers apply (tests/test_freshness.py).
PATIENT_TREE = REPO / "results" / "track1_patient_modal"


def artifacts_present() -> bool:
    return PATIENT_TREE.is_dir()


def needs_artifacts(name: str, out) -> bool:
    """True when the check should be skipped; records the WARN row."""
    if artifacts_present():
        return False
    out.warn(name, "skipped: gitignored results/ tree absent here "
                   "(run on the machine holding the artifacts)")
    return True


class Out:
    def __init__(self):
        self.rows = []

    def add(self, status, name, detail=""):
        self.rows.append((status, name, detail))

    def ok(self, name, detail=""):
        self.add("PASS", name, detail)

    def warn(self, name, detail=""):
        self.add("WARN", name, detail)

    def fail(self, name, detail=""):
        self.add("FAIL", name, detail)


def _read(rel):
    p = REPO / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def _emitters_only(body: str) -> str:
    """Strip fenced code blocks and table rows whose cells are commands -
    paths inside shell examples are recipes, not claims."""
    return re.sub(r"```.*?```", "", body, flags=re.S)


# ---------------------------------------------------------------------
# numeric-claim checks
# ---------------------------------------------------------------------

def check_test_count(out: Out):
    """pytest collection count vs 'N tests'/'N passed' claims in live
    docs. The suite count is THE drift-prone number (it changes with
    every new test module)."""
    r = subprocess.run([PY, "-m", "pytest", "tests", "--collect-only",
                        "-q"], cwd=REPO, capture_output=True, text=True)
    m = re.search(r"(\d+) tests? collected", r.stdout + r.stderr)
    if not m:
        out.warn("test-count", "could not collect suite count")
        return
    n = int(m.group(1))
    claims = []
    for rel in LIVE_DOCS:
        for i, line in enumerate(_read(rel).splitlines(), 1):
            for mm in re.finditer(r"(\d{3}) (?:tests|passed)", line):
                # 'N passed + 1 env-gated skip' style: pass-count is the
                # collected count minus the skipped one
                claims.append((rel, i, int(mm.group(1)),
                               bool(re.search(r"skip", line))))
    bad = [(r2, i, v) for r2, i, v, sk in claims
           if v != n and not (sk and v == n - 1)]
    if bad:
        out.fail("test-count",
                 f"suite={n}; stale claims: " +
                 "; ".join(f"{r}:{i}={v}" for r, i, v in bad))
    else:
        out.ok("test-count",
               f"{n} collected; {len(claims)} doc claims agree")


def check_fixture_count(out: Out):
    """Two fixture counts must match their sources: the scorer-audit
    battery (tools/audit_scorer_fixtures.py tests + BYTE_TESTS lists,
    the '60 fixtures' claim) and the oracle mutation audit
    (tests/test_adversarial.py MUTATIONS + NOOP_MUTATIONS, the
    '19-fixture' claim)."""
    sys.path.insert(0, str(REPO / "tests"))
    try:
        from tools import audit_scorer_fixtures as af
        import test_adversarial as ta
        n_battery = len(af.tests) + len(af.BYTE_TESTS)
        n_mutation = len(ta.MUTATIONS) + len(ta.NOOP_MUTATIONS)
    except Exception as e:  # pragma: no cover
        out.warn("fixture-count", f"cannot import fixture lists: {e}")
        return
    probs = []
    for rel in ("README.md", "docs/report_map.md", "docs/report.md"):
        body = _read(rel)
        for mm in re.finditer(
                r"(\d+)[ -]?(?:adversarial )?(?:CSV )?fixtures", body):
            if int(mm.group(1)) != n_battery:
                probs.append(f"{rel}: battery claim {mm.group(1)} vs "
                             f"actual {n_battery}")
        for mm in re.finditer(r"(\d+)-fixture oracle mutation", body):
            if int(mm.group(1)) != n_mutation:
                probs.append(f"{rel}: mutation claim {mm.group(1)} vs "
                             f"actual {n_mutation}")
    if probs:
        out.fail("fixture-count", "; ".join(probs))
    else:
        out.ok("fixture-count", f"battery {n_battery} + mutation "
                                f"{n_mutation}; claims agree")


def check_emitted_claims(out: Out):
    """The emitted hypothesis (rank/epcr/pair) vs claims in live docs."""
    try:
        res = json.loads((_read(f"{RUN}/funnel/result_head.json")))
        e = [h for h in res["ranked"] if h.get("emitted")][0]
    except Exception as e:
        out.warn("emitted-claims", f"cannot read result_head.json: {e}")
        return
    epcr, rank = e["epcr"], e["rank"]
    hist = re.compile(r"(?i)superseded|pre-indel|was |PRE-FIX|"
                      r"masked-run|run-2|track1_final/|previously")
    for rel in LIVE_DOCS:
        for i, line in enumerate(_read(rel).splitlines(), 1):
            if hist.search(line):
                continue
            for mm in re.finditer(r"epcr[= ]+0\.\d+", line):
                # only claims about THE emitted patient pair are checked;
                # other epcr mentions (synthetic rank map, examples) are
                # legitimate context
                if re.search(r"(?i)emitted|submission|patient|"
                             r"proband|uploaded|submitted", line) and \
                        mm.group(0).replace(" ", "=") != f"epcr={epcr}":
                    out.fail("emitted-claims",
                             f"{rel}:{i} '{mm.group(0)}' vs emitted "
                             f"epcr {epcr}")
                    return
    # superseded epcr (0.1324) may appear only in explicitly-historical
    # wording in live docs, or inside sections that ARE the historical
    # record (prior-iteration table, superseded-run acceptance gates)
    hist_heading = re.compile(
        r"(?i)0a\.|prior|superseded|masked-run|masked run|pre-fix|"
        r"pre-indel|run-2|track1_final,|baseline")
    hist_line = re.compile(
        r"superseded|pre-indel|was |masked-run|PRE-FIX|run-2|"
        r"track1_final/")
    for rel in LIVE_DOCS:
        in_hist = False
        for i, line in enumerate(_read(rel).splitlines(), 1):
            if re.match(r"#{1,3} ", line):
                in_hist = bool(hist_heading.search(line))
            if "0.1324" in line and not in_hist and \
                    not hist_line.search(line):
                out.fail("emitted-claims",
                         f"{rel}:{i} cites superseded epcr 0.1324 "
                         "without a historical marker")
                return
    out.ok("emitted-claims", f"emitted pair rank {rank} epcr {epcr}; "
                             "no unmarked stale epcr claims")


def check_artifact_numbers(out: Out):
    """Stage counts, ablation ranks, Exomiser + mosdepth numbers cited in
    docs/report.md vs the JSON artifacts they were generated from."""
    if needs_artifacts("artifact-numbers", out):
        return
    rep = _read("docs/report.md")
    problems = []
    try:
        counts = json.loads(_read(f"{RUN}/funnel/funnel_counts.json"))
        for k, v in counts.items():
            if isinstance(v, int) and v >= 1000 and \
                    f"{v:,}" not in rep and str(v) not in rep:
                problems.append(f"funnel {k}={v:,} absent from report")
    except Exception as e:
        problems.append(f"funnel_counts unreadable: {e}")
    try:
        abl = json.loads(_read(f"{RUN}/ablations.json"))
        for src, d in sorted(abl.items()):
            r = d.get("bub1b_rank")
            if r is not None and f"| {src} | {r} |" not in rep:
                problems.append(f"ablation {src} rank {r} absent")
    except Exception as e:
        problems.append(f"ablations unreadable: {e}")
    try:
        genes = (REPO / "results/exomiser_patient/"
                 "WGS_EX2312012-PASS_ONLY.genes.tsv").read_text()
        score = [l for l in genes.splitlines()
                 if l.startswith("1\t")][0].split("\t")[6]
        if score not in rep:
            problems.append(f"Exomiser combined {score} absent")
    except Exception as e:
        problems.append(f"exomiser tsv unreadable: {e}")
    if problems:
        out.fail("artifact-numbers", "; ".join(problems))
    else:
        out.ok("artifact-numbers", "funnel/ablation/exomiser figures in "
                                   "report match artifacts")


def check_csv_identity(out: Out):
    """The three copies of the submitted CSV must be byte-identical, and
    every submissions/*.csv must oracle-score 100/1.0/rank-1."""
    if needs_artifacts("csv-identity", out):
        return
    import csv
    import io
    from src.submit import validate_submission_bytes
    paths = ["nikhilpise_answer-blind-funnel.csv",
             "submissions/model1_nikhilpise_answer-blind-funnel.csv",
             f"{RUN}/submission.csv"]
    blobs = []
    for rel in paths:
        p = REPO / rel
        if not p.exists():
            out.fail("csv-identity", f"{rel} missing")
            return
        blobs.append((rel, p.read_bytes()))
    if len({b for _, b in blobs}) != 1:
        out.fail("csv-identity",
                 "byte drift between: " + ", ".join(r for r, _ in blobs))
        return
    for p in sorted((REPO / "submissions").glob("*.csv")):
        data = p.read_bytes()
        if b"\r" in data:
            out.fail("csv-identity", f"{p.name}: CRLF bytes")
            return
        res = validate_submission_bytes(data, GT)
        if not (res.rank_points == 100.0 and res.f_max == 1.0
                and res.full_match_rank == 1):
            out.fail("csv-identity",
                     f"{p.name}: scores {res.rank_points}/{res.f_max}")
            return
        rows = list(csv.DictReader(io.StringIO(data.decode("utf-8"))))
        pair = {(rows[0]["chrom_1"], int(rows[0]["pos_1"])),
                (rows[0]["chrom_2"], int(rows[0]["pos_2"]))}
        if pair != {("chr15", 40209701), ("chr15", 40220612)}:
            out.fail("csv-identity", f"{p.name}: pair drift {pair}")
            return
    out.ok("csv-identity", "3 copies byte-identical; all submissions "
                           "oracle-verify 100/1.0/rank1, LF-only")


# ---------------------------------------------------------------------
# reference-integrity checks
# ---------------------------------------------------------------------

def _brace_expand(s: str) -> list[str]:
    m = re.search(r"\{([^{}]+)\}", s)
    if not m:
        return [s]
    out = []
    for part in m.group(1).split(","):
        out += _brace_expand(s[:m.start()] + part + s[m.end():])
    return out


PATH_DOCS = [d for d in LIVE_DOCS
             if d not in ("docs/status.md", "docs/report_map.md",
                          "docs/deletion_runbook.md")]

# Trees that .gitignore keeps out of the repo: patient data, run outputs
# and downloaded corpora. They exist on the machine that produced them,
# never in a fresh clone or a worktree.
GITIGNORED_ROOTS = ("results", "data", "env")


def check_paths_exist(out: Out):
    """Artifact paths cited in live docs must exist on disk (results/ are
    gitignored but present locally - a vanished path = stale doc).
    status.md is exempt: its rows cite where artifacts LANDED on the
    row's date; ledgers (RETENTION) intentionally describe DELETE-
    candidate state. Absolute container paths (/data/...) and paths
    inside plan-item quotes are provenance, not live claims."""
    import glob as globmod
    pats = []
    for rel in PATH_DOCS:
        for i, line in enumerate(_read(rel).splitlines(), 1):
            # paths cited inside a deletion/removal clause are records of
            # what was deleted, not live references
            if re.search(r"(?i)deleted|removed", line):
                continue
            for mm in re.finditer(
                        r"`?(?<![\w./])((?:results|docs|data|env|tools|"
                        r"tests|src|submissions|config|scorer)/"
                        r"[\w./{},*-]+)`?", line):
                    pat = mm.group(1)
                    if ".." in pat:  # 'results/.../x' placeholder syntax
                        continue
                    pats.append((rel, i, pat))
    missing, ungitted = [], []
    for rel, i, pat in pats:
        for ex in _brace_expand(pat.rstrip(".,;:")):
            ex = ex.rstrip("/")
            if "*" in ex:
                gone = not globmod.glob(str(REPO / ex))
            else:
                gone = not (REPO / ex).exists()
            if not gone:
                continue
            # results/, data/ and env/ are gitignored: absent in a fresh
            # clone (and in a worktree), present on the run machine. A
            # vanished tracked path is drift; a vanished gitignored one is
            # only reportable where the artifacts live.
            (ungitted if ex.split("/", 1)[0] in GITIGNORED_ROOTS
             else missing).append(f"{rel}:{i} {ex}")
    if missing:
        out.fail("paths-exist",
                 f"{len(missing)} missing: " + "; ".join(missing[:8]))
    elif ungitted:
        out.warn("paths-exist",
                 f"{len(pats)} path refs checked; {len(ungitted)} under "
                 f"gitignored roots not present here (run on the machine "
                 f"holding the artifacts to verify): "
                 + "; ".join(ungitted[:4]))
    else:
        out.ok("paths-exist", f"{len(pats)} path refs resolve on disk")


def check_section_refs(out: Out):
    """report_map 'section N' pointers must exist as headings in the
    regenerated report."""
    rep = _read("docs/report.md")
    have = set(re.findall(r"^#{1,3} (\d+[a-z]?)\.", rep, flags=re.M))
    # unnumbered-but-referenced sections
    have |= {"0a"} if "## 0a." in rep else set()
    missing = []
    for i, line in enumerate(_read("docs/report_map.md").splitlines(), 1):
        for mm in re.finditer(r"sections? (\d+[a-z]?)(?:\s*\+\s*(\d+[a-z]?)"
                              r"|/(\d+[a-z]?))*", line):
            for g in mm.groups():
                if g and g not in have:
                    missing.append(f"report_map:{i} -> section {g}")
        for mm in re.finditer(r"section (\d+[a-z]?)\b", line):
            if mm.group(1) not in have:
                missing.append(f"report_map:{i} -> section {mm.group(1)}")
    if missing:
        out.fail("section-refs", "; ".join(sorted(set(missing))))
    else:
        out.ok("section-refs", f"{len(have)} sections; all map refs "
                               "resolve")


def check_line_refs(out: Out):
    """submission_checklist's vendored-app line refs must still resolve
    (the app is frozen but the check pins the assumption)."""
    anchors = {"submit_track1.py": {"display_name": None,
                                    "github_url": None}}
    src = _read("hackathon-app/tabs/submit_track1.py")
    for tok in anchors["submit_track1.py"]:
        anchors["submit_track1.py"][tok] = tok in src
    if not all(anchors["submit_track1.py"].values()):
        out.fail("line-refs",
                 "submit_track1.py no longer contains "
                 + str([k for k, v in anchors["submit_track1.py"].items()
                        if not v]))
    else:
        out.ok("line-refs", "vendored submit_track1.py anchors intact")


# ---------------------------------------------------------------------
# determinism + hygiene
# ---------------------------------------------------------------------

def check_figures_deterministic(out: Out):
    """Regenerate docs/figures into a temp dir; bytes must match the
    committed copies (a stale figure = a report that lies)."""
    if needs_artifacts("figures-deterministic", out):
        return
    args = [PY, "tools/make_figures.py",
            "--sam", "results/track1_patient_modal/realign/region.sam",
            "--allele-balance", f"{ARMS}/allele_balance.json",
            "--funnel-counts", f"{RUN}/funnel/funnel_counts.json",
            "--mosdepth-dist",
            f"{ARMS}/mosdepth/WGS.mosdepth.global.dist.txt",
            "--mosdepth-summary",
            f"{ARMS}/mosdepth/mosdepth_summary.json",
            "--ablations", f"{RUN}/ablations.json"]
    with tempfile.TemporaryDirectory() as td:
        r = subprocess.run(args + ["--out-dir", td], cwd=REPO,
                           capture_output=True, text=True)
        if r.returncode != 0:
            out.fail("figures-deterministic",
                     f"make_figures exited {r.returncode}: "
                     f"{r.stderr[-300:]}")
            return
        drift = []
        for f in sorted((REPO / "docs/figures").iterdir()):
            regen = Path(td) / f.name
            if not regen.exists():
                drift.append(f"{f.name} not regenerated")
            elif regen.read_bytes() != f.read_bytes():
                drift.append(f"{f.name} bytes differ")
    if drift:
        out.fail("figures-deterministic", "; ".join(drift))
    else:
        out.ok("figures-deterministic", "regeneration is byte-stable")


def check_hygiene(out: Out):
    """Em-dash scan (repo convention), future-dated ledger rows,
    TODO/FIXME strays, and git state."""
    dash = []
    r = subprocess.run(["git", "ls-files", "*.md"], cwd=REPO,
                       capture_output=True, text=True)
    for rel in r.stdout.splitlines():
        body = _read(rel)
        if "—" in body:
            dash.append(rel)
    if dash:
        out.fail("emdash", "em-dash in tracked md: " + ", ".join(dash))
    else:
        out.ok("emdash", "no em-dashes in tracked markdown")

    future = []
    for rel in LIVE_DOCS + ["docs/decisions.md", "docs/llm_log.md",
                            "docs/runtime_log.md"]:
        for i, line in enumerate(_read(rel).splitlines(), 1):
            for mm in re.finditer(r"\|\s*(20\d\d-\d\d-\d\d)\s*\|", line):
                if mm.group(1) > TODAY:
                    future.append(f"{rel}:{i} row dated {mm.group(1)}")
    if future:
        out.fail("future-dates", "; ".join(future))
    else:
        out.ok("future-dates", "no ledger rows dated after today")

    todos = []
    for rel in r.stdout.splitlines():
        body = _read(rel)
        for mm in re.finditer(r"\b(TODO|FIXME)\b", body):
            todos.append(f"{rel}: '{mm.group(0)}'")
    if todos:
        out.warn("todo-markers", "; ".join(todos[:5]))
    else:
        out.ok("todo-markers", "no TODO/FIXME strays in tracked files")

    g = subprocess.run(["git", "status", "--porcelain"], cwd=REPO,
                       capture_output=True, text=True)
    dirty = g.stdout.strip()
    if dirty:
        out.warn("git-clean",
                 f"{len(dirty.splitlines())} uncommitted paths")
    else:
        g2 = subprocess.run(["git", "rev-list", "--count",
                             "@{u}..HEAD"], cwd=REPO, capture_output=True,
                            text=True)
        if g2.returncode == 0 and g2.stdout.strip() == "0":
            out.ok("git-clean", "clean tree, nothing unpushed")
        else:
            out.warn("git-clean", f"clean tree; unpushed="
                                  f"{g2.stdout.strip() or 'no upstream'}")


def check_markers(out: Out):
    """'pending'/'not yet'/'TBD' in live docs - every hit is either a
    real open item (allowlist) or staleness."""
    allow = {
        "docs/status.md": ("Discussions-watch", "out of scope",
                           "env-gated", "Pending dataset access",
                           "public-repo", "pending-note"),
        "docs/submission_checklist.md": ("[ ]",),
        "docs/track1_closeout.md": ("operator", "deadline"),
        "docs/deletion_runbook.md": ("deletion", "post-deadline",
                                     "30 days"),
        "docs/report.md": ("Pending", "unknown"),
        "nikhilpise_track1_report.md": ("Pending", "unknown"),
        "docs/rubric_self_assessment.md": ("pending",),
        "docs/disclosure_position.md": ("pending",),
        "docs/FAMILY_EXPLAINER.md": ("pending",),
        "docs/ANSWER_BLIND_PROTOCOL.md": ("[ ]", "pending"),
        "docs/report_model2.md": ("pending",),
        "docs/team.md": ("pending",),
        "README.md": ("Pending",),
        "docs/report_map.md": ("Pending dataset access", "pending",
                               "not yet run"),
        "docs/figures/pileup_ascii.md": (),
        "submissions/README.md": (),
    }
    hits = []
    for rel in LIVE_DOCS:
        allowed = allow.get(rel, ())
        for i, line in enumerate(_read(rel).splitlines(), 1):
            for mm in re.finditer(r"(?i)\b(pending|not yet|TBD)\b", line):
                if not any(a.lower() in line.lower() for a in allowed):
                    hits.append(f"{rel}:{i}: ...{line.strip()[:80]}")
    if hits:
        out.warn("stale-markers",
                 f"{len(hits)} unreviewed hits: " + "; ".join(hits[:6]))
    else:
        out.ok("stale-markers", "no unexplained pending/not-yet markers")


def check_banner_presence(out: Out):
    """docs/report.md must carry the PATIENT banner (not the synthetic
    default) and the mandated acknowledgement."""
    rep = _read("docs/report.md")
    up = _read("nikhilpise_track1_report.md")
    problems = []
    for tag, body in (("docs/report.md", rep), ("root upload copy", up)):
        if "PATIENT RUN (PROBAND01" not in body:
            problems.append(f"{tag}: missing PATIENT banner")
        if "VALIDATED ON SYNTHETIC STAND-IN" in body:
            problems.append(f"{tag}: synthetic banner on patient report")
        if "This work was made possible through the Hackathon" \
                not in body:
            problems.append(f"{tag}: acknowledgement missing")
    if problems:
        out.fail("banner-presence", "; ".join(problems))
    else:
        out.ok("banner-presence", "patient banner + acknowledgement in "
                                  "both report copies")


def check_truth_claims(out: Out):
    """Absolute-negative claims that were once wrong: (1) the patient VCF
    does declare PGT/PID and 770k records carry them - only the two BUB1B
    sites lack them, so live docs must not say the VCF/file 'carries no
    PGT/PID'; (2) the GenAI disclosure must name every provider in the
    ledger and assert the training opt-out (organizer guidance, thread #2)."""
    problems = []
    bad = re.compile(r"(?i)(vcf|file)\s+carries\s+no\s+PGT")
    for rel in ("docs/status.md", "docs/track1_closeout.md", "README.md",
                "docs/report.md", "nikhilpise_track1_report.md"):
        if bad.search(_read(rel)):
            problems.append(f"{rel}: whole-VCF 'no PGT/PID' claim (false)")
    for rel in ("docs/report.md", "nikhilpise_track1_report.md"):
        sec = _read(rel).split("## 10. GenAI disclosure", 1)[-1][:3500]
        for need in ("Devin", "Claude", "opt-out"):
            if need not in sec:
                problems.append(f"{rel}: section 10 lacks '{need}'")
    log = _read("docs/llm_log.md")
    if "Anthropic Claude Code" not in log:
        problems.append("llm_log.md: no Claude Code row")
    if problems:
        out.fail("truth-claims", "; ".join(problems))
    else:
        out.ok("truth-claims", "PGT/PID wording + two-provider GenAI "
                               "disclosure with opt-out assertions")


# ---------------------------------------------------------------------

CHECKS = [
    check_test_count,
    check_fixture_count,
    check_emitted_claims,
    check_artifact_numbers,
    check_csv_identity,
    check_paths_exist,
    check_section_refs,
    check_line_refs,
    check_figures_deterministic,
    check_hygiene,
    check_markers,
    check_banner_presence,
    check_truth_claims,
]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--quiet", action="store_true",
                    help="print only WARN/FAIL rows")
    args = ap.parse_args(argv)
    out = Out()
    for fn in CHECKS:
        fn(out)
    fails = sum(1 for s, _, _ in out.rows if s == "FAIL")
    warns = sum(1 for s, _, _ in out.rows if s == "WARN")
    for s, name, detail in out.rows:
        if args.quiet and s == "PASS":
            continue
        line = f"{s:4} {name}"
        print(line + (f" - {detail}" if detail else ""))
    print(f"\n{len(out.rows)} checks: {len(out.rows) - fails - warns} "
          f"PASS, {warns} WARN, {fails} FAIL")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
