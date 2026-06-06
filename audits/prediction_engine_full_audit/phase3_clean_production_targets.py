from pathlib import Path
import csv, re, subprocess

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"

EXCLUDE_PREFIXES = (
    "audits/",
    "pages-dist/",
    "pipeline/raw/",
    "processed_data/backups/",
    "node_modules/",
    ".git/",
    ".wrangler/",
)

PRODUCTION_ENGINE_ALLOW = (
    "engine/",
    "scripts/",
    "tools/",
    "app.js",
    "config.js",
    "hunt-research.js",
    "ui.js",
)

PRODUCTION_PAGE_ALLOW = (
    "index.html",
    "research.html",
    "hunt-research.html",
    "hard-data.html",
    "hard-copy.html",
    "coverage.html",
    "verify.html",
    "style.css",
    "header-layout.js",
    "app.js",
    "hunt-research.js",
    "ui.js",
    "config.js",
    "hard-copy/",
    "assets/js/",
)

NOISE_REFS = {"r", "w", "rb", "wb", "a", "GET", "\\n", "", ", "}

IMPORTANT = [
    "ml_draw_predictions",
    "draw_reality_engine_predictive_v2",
    "draw_reality_view",
    "draw_reality_engine",
    "hunt_research_2026",
    "hunt_research_2026_ladder",
    "point_ladder_view",
    "hunt_predictions",
    "hunt_odds_history",
    "harvest_results_all_years_long",
    "harvest_supplemental_metrics",
    "DATABASE.csv",
    "database.csv",
    "documents.json",
    "public_contracts",
    "json.uoga.workers.dev",
    "cloudflare",
    "r2",
]

def read_csv(name):
    p = OUT / name
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
        return list(csv.DictReader(f))

def write_csv(name, rows):
    p = OUT / name
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

def norm(path):
    return (path or "").replace("\\", "/")

def is_excluded(path):
    p = norm(path).lower()
    return any(p.startswith(x) for x in EXCLUDE_PREFIXES)

def is_prod_engine(path):
    p = norm(path)
    pl = p.lower()
    if is_excluded(p):
        return False
    if "/test_" in pl or pl.startswith("tests/"):
        return False
    return any(pl.startswith(x.lower()) or pl == x.lower() for x in PRODUCTION_ENGINE_ALLOW)

def is_prod_page(path):
    p = norm(path)
    pl = p.lower()
    if is_excluded(p):
        return False
    return any(pl.startswith(x.lower()) or pl == x.lower() for x in PRODUCTION_PAGE_ALLOW)

def clean_ref(ref):
    r = (ref or "").strip()
    if r in NOISE_REFS:
        return ""
    if len(r) <= 2:
        return ""
    return r

def score(*vals):
    s = " ".join(str(v or "") for v in vals).lower()
    n = 0
    for term in IMPORTANT:
        if term.lower() in s:
            n += 20
    for term in ["prediction", "predictive", "draw", "odds", "harvest", "research", "database", "point", "render", "fetch"]:
        if term in s:
            n += 5
    return n

code = read_csv("01_code_inventory.csv")
deps = read_csv("02_feeder_dependency_map.csv")
truth = read_csv("03_truth_source_matrix.csv")
large = read_csv("00_large_files_over_10mb.csv")

prod_engines = []
for r in code:
    p = norm(r.get("path"))
    if not is_prod_engine(p):
        continue
    refs = []
    for ref in (r.get("read_refs","") + ";" + r.get("write_refs","")).split(";"):
        c = clean_ref(ref)
        if c:
            refs.append(c)
    hit = score(p, r.get("keyword_hits"), r.get("public_delivery_hits"), ";".join(refs))
    if hit <= 0:
        continue
    prod_engines.append({
        "path": p,
        "type": r.get("type"),
        "score": hit,
        "keyword_hits": r.get("keyword_hits"),
        "public_delivery_hits": r.get("public_delivery_hits"),
        "clean_refs": ";".join(sorted(set(refs)))[:5000],
    })

prod_pages = []
for r in code:
    p = norm(r.get("path"))
    if not is_prod_page(p):
        continue
    refs = []
    for ref in (r.get("read_refs","") + ";" + r.get("write_refs","")).split(";"):
        c = clean_ref(ref)
        if c:
            refs.append(c)
    hit = score(p, r.get("keyword_hits"), r.get("public_delivery_hits"), ";".join(refs))
    if hit <= 0:
        continue
    prod_pages.append({
        "path": p,
        "type": r.get("type"),
        "score": hit,
        "keyword_hits": r.get("keyword_hits"),
        "public_delivery_hits": r.get("public_delivery_hits"),
        "clean_refs": ";".join(sorted(set(refs)))[:5000],
    })

prod_deps = []
for r in deps:
    consumed = norm(r.get("consumed_by"))
    src = clean_ref(r.get("source_ref"))
    out = clean_ref(r.get("output_ref"))
    if not src and not out:
        continue
    if is_excluded(consumed):
        continue
    if not (is_prod_engine(consumed) or is_prod_page(consumed)):
        continue
    hit = score(src, consumed, out, r.get("page_area"))
    if hit <= 0:
        continue
    prod_deps.append({
        "source_ref": src,
        "consumed_by": consumed,
        "consumer_type": r.get("consumer_type"),
        "output_ref": out,
        "page_area": r.get("page_area"),
        "score": hit,
        "status": r.get("status"),
    })

truth_targets = []
for r in truth:
    p = norm(r.get("feeder_file"))
    if is_excluded(p):
        continue
    hit = score(p, r.get("truth_source_guess"), r.get("status"), r.get("notes"))
    if hit <= 0:
        continue
    truth_targets.append({
        "feeder_file": p,
        "size_mb": r.get("size_mb"),
        "truth_source_guess": r.get("truth_source_guess"),
        "status": r.get("status"),
        "rows": r.get("rows"),
        "columns": r.get("columns"),
        "null_cells": r.get("null_cells"),
        "duplicate_full_rows": r.get("duplicate_full_rows"),
        "notes": r.get("notes"),
        "score": hit,
    })

prod_large = []
tracked = set(subprocess.check_output(["git","ls-files"], cwd=ROOT, text=True, errors="ignore").splitlines())
for r in large:
    p = norm(r.get("path"))
    if is_excluded(p):
        continue
    if p in tracked:
        prod_large.append({
            "path": p,
            "size_mb": r.get("size_mb"),
            "type": r.get("type"),
            "truth_source_guess": r.get("truth_source_guess"),
            "tracked": "yes",
        })

prod_engines = sorted(prod_engines, key=lambda r: int(r["score"]), reverse=True)
prod_pages = sorted(prod_pages, key=lambda r: int(r["score"]), reverse=True)
prod_deps = sorted(prod_deps, key=lambda r: int(r["score"]), reverse=True)
truth_targets = sorted(truth_targets, key=lambda r: (int(r["score"]), float(r.get("size_mb") or 0)), reverse=True)

write_csv("13_clean_production_engine_targets.csv", prod_engines)
write_csv("14_clean_production_page_targets.csv", prod_pages)
write_csv("15_clean_production_delivery_dependencies.csv", prod_deps)
write_csv("16_clean_truth_source_targets.csv", truth_targets)
write_csv("17_clean_tracked_large_files.csv", prod_large)

def table(rows, cols, limit=30):
    if not rows:
        return "_No rows._\n"
    lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows[:limit]:
        vals = []
        for c in cols:
            v = str(r.get(c,"")).replace("\n"," ").replace("|","/")
            if len(v) > 120:
                v = v[:117] + "..."
            vals.append(v)
        lines.append("|" + "|".join(vals) + "|")
    if len(rows) > limit:
        lines.append(f"\n_Showing first {limit} of {len(rows)}._")
    return "\n".join(lines) + "\n"

md = []
md.append("# Clean Production Audit Targets\n\n")
md.append("This pass excludes audit files, pages-dist duplicates, raw pipeline files, backup directories, tests, and false file references like r/w/rb.\n\n")

md.append("## Production Engine Targets\n\n")
md.append(table(prod_engines, ["path","score","keyword_hits","public_delivery_hits","clean_refs"], 40))

md.append("\n## Production Page / Rendering Targets\n\n")
md.append(table(prod_pages, ["path","score","keyword_hits","public_delivery_hits","clean_refs"], 40))

md.append("\n## Production Delivery Dependencies\n\n")
md.append(table(prod_deps, ["source_ref","consumed_by","consumer_type","output_ref","page_area","score","status"], 60))

md.append("\n## Truth Source Targets\n\n")
md.append(table(truth_targets, ["feeder_file","size_mb","truth_source_guess","status","rows","columns","null_cells","duplicate_full_rows","score"], 60))

md.append("\n## Tracked Large Files Still In Production Scope\n\n")
md.append(table(prod_large, ["path","size_mb","type","truth_source_guess","tracked"], 60))

md.append("\n## Next Repair Order\n\n")
md.append("1. Confirm production page data paths: research, hunt-research, hard-data, hard-copy/library.\n")
md.append("2. Confirm production engine feeders: hunt_research_2026, draw_reality, ml_draw_predictions, point_ladder, harvest long files, DATABASE.csv.\n")
md.append("3. Run only the engine CLIs/tests tied to those files.\n")
md.append("4. Patch rendering only where data fails to load, parses incorrectly, or creates duplicate text.\n")
md.append("5. Do not stage large data files; only stage audit reports and safe source fixes.\n")

(OUT / "CLEAN_PRODUCTION_AUDIT_TARGETS.md").write_text("".join(md), encoding="utf-8")

print("PHASE 3 COMPLETE")
print("Created:")
for name in [
    "13_clean_production_engine_targets.csv",
    "14_clean_production_page_targets.csv",
    "15_clean_production_delivery_dependencies.csv",
    "16_clean_truth_source_targets.csv",
    "17_clean_tracked_large_files.csv",
    "CLEAN_PRODUCTION_AUDIT_TARGETS.md",
]:
    p = OUT / name
    print(f" - {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

print("")
print("Top production engines:")
for r in prod_engines[:15]:
    print(" -", r["path"])

print("")
print("Top production pages:")
for r in prod_pages[:15]:
    print(" -", r["path"])

print("")
print("Tracked production large files:")
for r in prod_large[:25]:
    print(" -", r["path"], r["size_mb"], "MB")

print("")
print("Git status:")
print(subprocess.check_output(["git","status","--short"], cwd=ROOT, text=True, errors="ignore"))
