"""Citation checker for docs/plan.md: verifies every traceable reference resolves.

    python tools/check_citations.py          # exits 0 if all checks pass

Checks performed (mechanical):
  1. `file.py:line(-line)` citations -> file exists under hackathon-app/ or
     hackathon-app/tabs/ AND every cited line is within file length.
  2. `deep dive §N` / `deep dive §Nx` references -> section heading exists in
     docs/DEEP_DIVE.md.
  3. Bare `something.py` mentions (no line number) -> file exists somewhere in
     the repo (planned future files like tests/test_funnel.py are reported
     as PLANNED, not failures - they live inside unchecked checkbox items).
  4. `docs/*.md` references on non-checkbox lines -> file exists.
Semantic correctness (does a cited line support the claim) stays human - the
script prints claim context + cited lines side by side for review.
"""
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

plan = (REPO / "docs" / "plan.md").read_text(encoding="utf-8")
dd_path = REPO / "docs" / "DEEP_DIVE.md"
dd = dd_path.read_text(encoding="utf-8") if dd_path.exists() else ""

fails = []

# ── 1. file.py:line citations ───────────────────────────────────────────────
pat = re.compile(r"([A-Za-z_0-9]+\.py):([0-9]+(?:-[0-9]+)?(?:,[0-9]+(?:-[0-9]+)?)*)")
seen = {}
for m in pat.finditer(plan):
    f, rng = m.group(1), m.group(2)
    ctx = plan[max(0, m.start() - 90):m.start()].replace("\n", " ").strip()
    seen.setdefault((f, rng), ctx[-70:])

print("========== file.py:line CITATIONS ==========")
for (f, rng), ctx in sorted(seen.items()):
    print(f"{f:22s} {rng:12s} | ...{ctx}")

print("\n========== SOURCE LINES ==========")
for (f, rng) in sorted(seen.keys()):
    path = None
    for cand in [REPO / "hackathon-app" / f, REPO / "hackathon-app" / "tabs" / f]:
        if cand.exists():
            path = cand
    if not path:
        fails.append((f, rng, "FILE NOT FOUND"))
        print(f"--- {f} {rng}: FILE NOT FOUND ---")
        continue
    lines = path.read_text(encoding="utf-8").splitlines()
    print(f"--- {f} {rng} ({path.relative_to(REPO)}) ---")
    for part in rng.split(","):
        if "-" in part:
            a, b = (int(x) for x in part.split("-"))
        else:
            a = b = int(part)
        if a < 1 or b > len(lines):
            fails.append((f, rng, f"line range {a}-{b} exceeds file length {len(lines)}"))
        for i in range(a, min(b, a + 40) + 1):
            if i <= len(lines):
                print(f"  {i:4d}: {lines[i - 1]}")

# ── 2. deep dive §N references ──────────────────────────────────────────────
print("\n========== DEEP DIVE SECTION REFERENCES ==========")
dd_secs = set()
for m in re.finditer(r"^#+\s*(?:Section\s+)?(\d+[a-z]?)\.?", dd, re.M):
    dd_secs.add(m.group(1))
    dd_secs.add(m.group(1) + ".")
dd_refs = sorted(set(re.findall(r"deep dive §(\d+[a-z]?)", plan)))
missing = [r for r in dd_refs if r not in dd_secs and r + "." not in dd_secs]
print("referenced:", dd_refs)
print("present:", sorted(s for s in dd_secs if not s.endswith('.')))
for r in missing:
    fails.append(("DEEP_DIVE.md", f"§{r}", "referenced section does not exist"))
print("missing:", missing if missing else "none")

# ── 3. bare .py filename references ─────────────────────────────────────────
print("\n========== BARE .py REFERENCES ==========")
# Modules declared in the plan's repo-layout spec (src/{...}) are PLANNED
# deliverables, not dangling references. External tools that merely look like
# python filenames are likewise not repo files to check.
declared = set()
_m = re.search(r"src/\{([^}]+)\}", plan)
if _m:
    declared = {x.strip() + ".py" for x in _m.group(1).split(",")}
EXTERNAL = {"hap.py"}  # Illumina hap.py benchmarking tool (jmcdani20/hap.py image)

bare = set()
for m in re.finditer(r"([A-Za-z_0-9]+\.py)(?!:)", plan):
    bare.add(m.group(1))
for f in sorted(bare):
    hits = list(REPO.rglob(f))
    exists = any(".git" not in str(h) for h in hits)
    if exists:
        print(f"  {f:28s} EXISTS ({[str(h.relative_to(REPO)) for h in hits if '.git' not in str(h)][0]})")
    elif f in EXTERNAL:
        print(f"  {f:28s} EXTERNAL TOOL (not a repo file)")
    elif f in declared:
        print(f"  {f:28s} PLANNED (declared src/ module in repo layout)")
    else:
        # planned = named inside a '- [ ]' checkbox block or a '**GATE' block
        # (gate text spans multiple lines; use the blank-line-delimited block)
        planned_ctx = False
        for m2 in re.finditer(re.escape(f), plan):
            b_start = plan.rfind("\n\n", 0, m2.start()) + 2
            block = plan[b_start:m2.end()]
            if "- [ ]" in block or "**GATE" in block:
                planned_ctx = True
        if planned_ctx:
            print(f"  {f:28s} PLANNED (deliverable in checkbox/gate)")
        else:
            fails.append((f, "-", "referenced but file does not exist and not declared planned"))
            print(f"  {f:28s} MISSING")

# ── 4. docs/*.md references ─────────────────────────────────────────────────
print("\n========== docs/*.md REFERENCES ==========")
# A docs/*.md file is PLANNED if it is named in ANY checkbox or gate line
# anywhere in the doc - deliverables are declared once and referenced elsewhere.
declared_docs = set()
for m in re.finditer(r"docs/([A-Za-z_0-9]+\.md)", plan):
    b_start = plan.rfind("\n\n", 0, m.start()) + 2
    block = plan[b_start:m.end()]
    if "- [ ]" in block or "**GATE" in block:
        declared_docs.add(m.group(1))
for m in re.finditer(r"docs/([A-Za-z_0-9]+\.md)", plan):
    fname = m.group(1)
    exists = (REPO / "docs" / fname).exists()
    planned = fname in declared_docs
    status = "EXISTS" if exists else ("PLANNED" if planned else "MISSING")
    if not exists and not planned:
        fails.append((f"docs/{fname}", "-", "referenced but not a declared deliverable"))
    print(f"  docs/{fname:20s} {status}")

print("\n========== RESULT ==========")
if fails:
    print("FAILURES:")
    for x in fails:
        print("  ", x)
    sys.exit(1)
print(f"ALL CHECKS PASS: {len(seen)} line citations, {len(dd_refs)} section refs, "
      f"{len(bare)} file refs verified")
