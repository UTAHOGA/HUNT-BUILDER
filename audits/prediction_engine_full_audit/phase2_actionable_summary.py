from pathlib import Path
import csv, json, subprocess, collections, re

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"
PHASE = OUT / "ACTIONABLE_AUDIT_SUMMARY.md"

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

def git(args):
    try:
        return subprocess.check_output(["git"] + args, cwd=ROOT, text=True, stderr=subprocess.STDOUT, errors="ignore")
    except Exception as e:
        return str(e)

repo = read_csv("01_repo_inventory.csv")
code = read_csv("01_code_inventory.csv")
deps = read_csv("02_feeder_dependency_map.csv")
truth = read_csv("03_truth_source_matrix.csv")
engines = read_csv("04_engine_ingestion_audit.csv")
render = read_csv("06_rendering_audit.csv")
large = read_csv("00_large_files_over_10mb.csv")
conflicts = read_csv("03_truth_source_conflicts.csv")

important_terms = [
    "ml_draw_predictions", "draw_reality", "hunt_research", "point_ladder",
    "harvest", "database", "prediction", "predictive", "bonus", "preference",
    "sportsman", "bear", "turkey", "lion", "cougar", "antlerless",
    "research", "outfitter", "hard-copy", "library", "documents.json",
    "public_contracts", "json.uoga.workers.dev"
]

def score_text(*vals):
    s = " ".join(v or "" for v in vals).lower()
    score = 0
    for t in important_terms:
        if t in s:
            score += 5
    if "unknown" in s:
        score += 1
    if "fail" in s:
        score += 10
    if "public" in s:
        score += 3
    if "fetch" in s:
        score += 3
    if "processed_data" in s:
        score += 2
    return score

ranked_engines = sorted(
    engines,
    key=lambda r: score_text(r.get("engine_path"), r.get("keyword_hits"), r.get("expected_inputs_detected"), r.get("outputs_detected")),
    reverse=True
)[:100]

page_rows = [
    r for r in render
    if any(x in (r.get("page_area","") + " " + r.get("page_or_component","") + " " + r.get("data_refs","")).lower()
           for x in ["research", "outfitter", "library", "hard-copy", "documents"])
]

ranked_pages = sorted(
    page_rows,
    key=lambda r: score_text(r.get("page_or_component"), r.get("page_area"), r.get("data_refs"), r.get("public_delivery_hits")),
    reverse=True
)

failed_truth = [
    r for r in truth
    if str(r.get("status","")).startswith("FAIL") or r.get("truth_source_guess") == "unknown"
]
failed_truth_ranked = sorted(
    failed_truth,
    key=lambda r: score_text(r.get("feeder_file"), r.get("status"), r.get("truth_source_guess"), r.get("notes")) + float(r.get("size_mb") or 0),
    reverse=True
)[:250]

large_ranked = sorted(
    large,
    key=lambda r: float(r.get("size_mb") or 0),
    reverse=True
)

delivery_deps = [
    r for r in deps
    if any(x in (r.get("source_ref","") + " " + r.get("consumed_by","") + " " + r.get("output_ref","") + " " + r.get("page_area","")).lower()
           for x in important_terms)
]
delivery_deps = sorted(
    delivery_deps,
    key=lambda r: score_text(r.get("source_ref"), r.get("consumed_by"), r.get("output_ref"), r.get("page_area")),
    reverse=True
)[:300]

write_csv("07_ranked_engine_targets.csv", ranked_engines)
write_csv("08_ranked_page_rendering_targets.csv", ranked_pages)
write_csv("09_failed_or_unknown_truth_targets.csv", failed_truth_ranked)
write_csv("10_ranked_delivery_dependency_targets.csv", delivery_deps)
write_csv("11_ranked_large_files_do_not_stage.csv", large_ranked)

tracked_large = []
tracked = set(git(["ls-files"]).splitlines())
for r in large_ranked:
    if r.get("path") in tracked:
        tracked_large.append(r)
write_csv("12_tracked_large_files_review.csv", tracked_large)

status = git(["status", "--short"])
diffstat = git(["diff", "--stat"])

def table(rows, cols, limit=30):
    if not rows:
        return "_No rows._\n"
    lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows[:limit]:
        vals = []
        for c in cols:
            v = str(r.get(c, ""))
            v = v.replace("\n", " ").replace("|", "/")
            if len(v) > 110:
                v = v[:107] + "..."
            vals.append(v)
        lines.append("|" + "|".join(vals) + "|")
    if len(rows) > limit:
        lines.append(f"\n_Showing first {limit} of {len(rows)}._")
    return "\n".join(lines) + "\n"

md = []
md.append("# Actionable Audit Summary\n\n")
md.append("## Git Safety Status\n\n")
md.append("```text\n" + status + "\n```\n")
md.append("## Current Diff Stat\n\n")
md.append("```text\n" + diffstat + "\n```\n")

md.append("## Highest Priority Engine Targets\n\n")
md.append(table(ranked_engines, ["engine_path", "keyword_hits", "expected_inputs_detected", "outputs_detected"], 40))

md.append("\n## Research / Outfitter / Library Rendering Targets\n\n")
md.append(table(ranked_pages, ["page_or_component", "page_area", "data_refs", "public_delivery_hits", "status"], 40))

md.append("\n## Delivery Dependency Targets\n\n")
md.append(table(delivery_deps, ["source_ref", "consumed_by", "consumer_type", "output_ref", "page_area", "status"], 50))

md.append("\n## Failed Or Unknown Truth-Source Targets\n\n")
md.append(table(failed_truth_ranked, ["feeder_file", "size_mb", "truth_source_guess", "status", "rows", "columns", "notes"], 50))

md.append("\n## Large Files Do Not Stage\n\n")
md.append(table(large_ranked, ["path", "size_mb", "type", "truth_source_guess"], 50))

md.append("\n## Tracked Large Files Review\n\n")
md.append(table(tracked_large, ["path", "size_mb", "type", "truth_source_guess"], 50))

md.append("\n## Immediate Interpretation\n\n")
md.append("- The repo contains many backup, raw, duplicate, generated, and public/export copies. The first audit intentionally over-counted so nothing was missed.\n")
md.append("- The next repair pass should focus on the ranked engine targets, the ranked page targets, and the delivery dependencies only.\n")
md.append("- Do not stage large raw/generated files. Review `12_tracked_large_files_review.csv` before any commit.\n")
md.append("- Existing modified files `header-layout.js`, `index.html`, and `style.css` should be treated as Codex-owned changes unless inspected first.\n")

PHASE.write_text("".join(md), encoding="utf-8")

print("PHASE 2 COMPLETE")
print("Created:")
for name in [
    "ACTIONABLE_AUDIT_SUMMARY.md",
    "07_ranked_engine_targets.csv",
    "08_ranked_page_rendering_targets.csv",
    "09_failed_or_unknown_truth_targets.csv",
    "10_ranked_delivery_dependency_targets.csv",
    "11_ranked_large_files_do_not_stage.csv",
    "12_tracked_large_files_review.csv",
]:
    p = OUT / name
    print(f" - {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

print("")
print("Git status:")
print(status)
print("")
print("Diff stat:")
print(diffstat)
