from pathlib import Path
import os, re, json, csv, hashlib, datetime, sys
from collections import defaultdict, Counter

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"
OUT.mkdir(parents=True, exist_ok=True)

IGNORE_PARTS = {
    ".git", "node_modules", ".wrangler", ".next", "dist", "build",
    "__pycache__", ".pytest_cache", ".venv", "venv"
}

ENGINE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
DATA_EXTS = {".csv", ".json", ".jsonl", ".parquet", ".xlsx", ".xls", ".pdf", ".kml", ".geojson"}
WEB_EXTS = {".html", ".css", ".js", ".jsx", ".ts", ".tsx", ".astro", ".vue", ".svelte"}

ENGINE_KEYWORDS = [
    "predict", "prediction", "draw", "odds", "harvest", "classifier", "materialize",
    "engine", "ingest", "etl", "transform", "validate", "audit", "reconcile",
    "preference", "bonus", "sportsman", "bear", "turkey", "lion", "cougar",
    "antlerless", "point_ladder", "hunt_research", "database"
]

READ_PATTERNS = [
    r"read_csv\(['\"]([^'\"]+)",
    r"read_json\(['\"]([^'\"]+)",
    r"json\.load\(open\(['\"]([^'\"]+)",
    r"open\(['\"]([^'\"]+)",
    r"Path\(['\"]([^'\"]+)",
    r"fetch\(['\"]([^'\"]+)",
    r"d3\.csv\(['\"]([^'\"]+)",
    r"Papa\.parse\(['\"]([^'\"]+)",
    r"import\s+.*?from\s+['\"]([^'\"]+)",
]

OUTPUT_PATTERNS = [
    r"to_csv\(['\"]([^'\"]+)",
    r"to_json\(['\"]([^'\"]+)",
    r"write_text\(['\"]([^'\"]+)",
    r"write_bytes\(['\"]([^'\"]+)",
    r"open\(['\"]([^'\"]+)['\"],\s*['\"]w",
]

PUBLIC_HINTS = [
    "public/", "/public/", "processed_data/", "data_model/", "hard-copy/",
    "json.uoga.workers.dev", "r2", "cloudflare", "ml_draw_predictions",
    "draw_reality", "hunt_research", "documents.json", "point_ladder"
]

def ignored(path: Path) -> bool:
    return any(part in IGNORE_PARTS for part in path.parts)

def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return str(path).replace("\\", "/")

def safe_read_text(path: Path, limit=2_000_000):
    try:
        if path.stat().st_size > limit:
            with path.open("rb") as f:
                data = f.read(limit)
            return data.decode("utf-8", errors="ignore")
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""

def file_type(path: Path, text: str):
    r = rel(path).lower()
    name = path.name.lower()
    ext = path.suffix.lower()

    if ext in ENGINE_EXTS and any(k in r or k in text.lower() for k in ENGINE_KEYWORDS):
        return "engine_or_transform"
    if ext in WEB_EXTS and any(x in text for x in ["fetch(", "document.", "React", "component", "<html", "className", "hard-copy", "research", "outfitter"]):
        return "website_page_or_component"
    if ext in DATA_EXTS:
        return "data_or_feeder"
    if ext in ENGINE_EXTS:
        return "code"
    return "other"

def classify_truth_source(path: Path):
    r = rel(path).lower()
    if "official" in r or "dwr" in r or "guidebook" in r or "draw_odds" in r or "draw-results" in r or "draw_results" in r:
        return "official_or_extracted_official"
    if "database.csv" in r or r.endswith("/database.csv"):
        return "canonical_database"
    if "reconcile" in r or "reconciled" in r or "draw_reality" in r:
        return "reconciled_database_or_view"
    if "hunt_research" in r:
        return "master_hunt_research_feed"
    if "ml_draw_predictions" in r or "predictions" in r or "predictive" in r:
        return "generated_engine_output"
    if "crosswalk" in r:
        return "manual_or_generated_crosswalk"
    if "harvest" in r:
        return "harvest_source_or_output"
    return "unknown"

def scan_csv(path: Path):
    result = {
        "rows": None, "columns": None, "null_cells": None, "blank_rows": 0,
        "duplicate_full_rows": None, "status": "UNSCANNED", "notes": ""
    }
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            result["columns"] = len(fields)
            rows = []
            null_cells = 0
            blank_rows = 0
            seen = set()
            dup = 0
            row_count = 0
            for row in reader:
                row_count += 1
                values = [str(row.get(c, "")).strip() for c in fields]
                if not any(values):
                    blank_rows += 1
                null_cells += sum(1 for v in values if v == "" or v.lower() in {"null","none","nan","na"})
                sig = tuple(values)
                if sig in seen:
                    dup += 1
                else:
                    seen.add(sig)
                if row_count >= 250000:
                    result["notes"] = "scanned_first_250000_rows"
                    break
            result["rows"] = row_count
            result["null_cells"] = null_cells
            result["blank_rows"] = blank_rows
            result["duplicate_full_rows"] = dup
            result["status"] = "PASS" if row_count > 0 and len(fields) > 0 else "FAIL_EMPTY_OR_NO_HEADER"
    except Exception as e:
        result["status"] = "FAIL_READ"
        result["notes"] = str(e)[:300]
    return result

def scan_json(path: Path):
    result = {"status": "UNSCANNED", "top_type": "", "top_count": None, "notes": ""}
    try:
        text = safe_read_text(path, limit=20_000_000)
        obj = json.loads(text)
        result["top_type"] = type(obj).__name__
        if isinstance(obj, list):
            result["top_count"] = len(obj)
        elif isinstance(obj, dict):
            result["top_count"] = len(obj.keys())
        result["status"] = "PASS"
    except Exception as e:
        result["status"] = "FAIL_JSON_PARSE"
        result["notes"] = str(e)[:300]
    return result

all_files = []
code_rows = []
dep_rows = []
data_rows = []
render_rows = []
engine_rows = []

for path in ROOT.rglob("*"):
    if not path.is_file() or ignored(path):
        continue

    rp = rel(path)
    ext = path.suffix.lower()
    size = path.stat().st_size
    text = safe_read_text(path) if ext in ENGINE_EXTS or ext in WEB_EXTS or ext in {".json", ".html", ".css"} else ""

    ftype = file_type(path, text)
    truth = classify_truth_source(path)

    all_files.append({
        "path": rp,
        "size_bytes": size,
        "size_mb": round(size / 1024 / 1024, 3),
        "extension": ext,
        "type": ftype,
        "truth_source_guess": truth,
        "modified": datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
    })

    if ext in ENGINE_EXTS or ext in WEB_EXTS:
        lower_text = text.lower()
        reads, writes = [], []
        for pat in READ_PATTERNS:
            reads += re.findall(pat, text)
        for pat in OUTPUT_PATTERNS:
            writes += re.findall(pat, text)

        keyword_hits = sorted({k for k in ENGINE_KEYWORDS if k in rp.lower() or k in lower_text})
        public_hits = sorted({h for h in PUBLIC_HINTS if h.lower() in lower_text or h.lower() in rp.lower()})

        code_rows.append({
            "path": rp,
            "type": ftype,
            "size_bytes": size,
            "keyword_hits": ";".join(keyword_hits),
            "public_delivery_hits": ";".join(public_hits),
            "read_refs": ";".join(sorted(set(reads)))[:5000],
            "write_refs": ";".join(sorted(set(writes)))[:5000],
        })

        if ftype == "engine_or_transform":
            engine_rows.append({
                "engine_path": rp,
                "status": "INVENTORIED_NEEDS_RUNTIME_CHECK",
                "keyword_hits": ";".join(keyword_hits),
                "expected_inputs_detected": ";".join(sorted(set(reads)))[:5000],
                "outputs_detected": ";".join(sorted(set(writes)))[:5000],
                "notes": ""
            })

        for src in sorted(set(reads)):
            dep_rows.append({
                "source_ref": src,
                "consumed_by": rp,
                "consumer_type": ftype,
                "ingestion_method": "detected_reference",
                "output_ref": "",
                "rendered_by": rp if ftype == "website_page_or_component" else "",
                "page_area": "research" if "research" in rp.lower() or "research" in src.lower() else ("outfitter" if "outfitter" in rp.lower() or "outfitter" in src.lower() else ("library_or_hard_copy" if "hard-copy" in rp.lower() or "library" in rp.lower() or "documents.json" in src.lower() else "")),
                "status": "TRACE_DETECTED",
                "notes": ""
            })

        for dst in sorted(set(writes)):
            dep_rows.append({
                "source_ref": "",
                "consumed_by": rp,
                "consumer_type": ftype,
                "ingestion_method": "detected_writer",
                "output_ref": dst,
                "rendered_by": "",
                "page_area": "",
                "status": "OUTPUT_DETECTED",
                "notes": ""
            })

        if ftype == "website_page_or_component":
            render_rows.append({
                "page_or_component": rp,
                "page_area": "research" if "research" in rp.lower() or "research" in lower_text else ("outfitter" if "outfitter" in rp.lower() or "outfitter" in lower_text else ("library_or_hard_copy" if "library" in rp.lower() or "hard-copy" in rp.lower() or "documents.json" in lower_text else "other")),
                "data_refs": ";".join(sorted(set(reads)))[:5000],
                "public_delivery_hits": ";".join(public_hits),
                "status": "INVENTORIED_NEEDS_BROWSER_CHECK",
                "notes": ""
            })

    if ext in DATA_EXTS:
        row = {
            "feeder_file": rp,
            "extension": ext,
            "size_bytes": size,
            "size_mb": round(size / 1024 / 1024, 3),
            "truth_source_guess": truth,
            "status": "INVENTORIED",
            "rows": "",
            "columns": "",
            "null_cells": "",
            "blank_rows": "",
            "duplicate_full_rows": "",
            "notes": ""
        }

        if ext == ".csv":
            s = scan_csv(path)
            row.update({
                "status": s["status"],
                "rows": s["rows"],
                "columns": s["columns"],
                "null_cells": s["null_cells"],
                "blank_rows": s["blank_rows"],
                "duplicate_full_rows": s["duplicate_full_rows"],
                "notes": s["notes"]
            })
        elif ext == ".json":
            s = scan_json(path)
            row.update({
                "status": s["status"],
                "rows": s["top_count"],
                "columns": s["top_type"],
                "notes": s["notes"]
            })

        data_rows.append(row)

def write_csv(name, rows):
    path = OUT / name
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    keys = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=keys)
        writer.writeheader()
        writer.writerows(rows)

write_csv("01_repo_inventory.csv", all_files)
write_csv("01_code_inventory.csv", code_rows)
write_csv("02_feeder_dependency_map.csv", dep_rows)
write_csv("03_truth_source_matrix.csv", data_rows)
write_csv("04_engine_ingestion_audit.csv", engine_rows)
write_csv("06_rendering_audit.csv", render_rows)

conflicts = []
by_name = defaultdict(list)
for r in data_rows:
    by_name[Path(r["feeder_file"]).name.lower()].append(r)
for name, rows in by_name.items():
    if len(rows) > 1:
        truths = sorted(set(r["truth_source_guess"] for r in rows))
        statuses = sorted(set(r["status"] for r in rows))
        conflicts.append({
            "file_name": name,
            "copies": len(rows),
            "paths": ";".join(r["feeder_file"] for r in rows),
            "truth_source_guesses": ";".join(truths),
            "statuses": ";".join(statuses),
            "recommended_action": "review_duplicate_feeder_names"
        })
write_csv("03_truth_source_conflicts.csv", conflicts)

large_files = [r for r in all_files if r["size_bytes"] >= 10 * 1024 * 1024]
write_csv("00_large_files_over_10mb.csv", large_files)

summary = {
    "generated_at": datetime.datetime.now().isoformat(timespec="seconds"),
    "repo": str(ROOT),
    "total_files": len(all_files),
    "code_files": len(code_rows),
    "engine_or_transform_files": len(engine_rows),
    "data_or_feeder_files": len(data_rows),
    "dependency_edges_detected": len(dep_rows),
    "rendering_files_detected": len(render_rows),
    "truth_conflicts_by_duplicate_name": len(conflicts),
    "large_files_over_10mb": len(large_files),
    "data_status_counts": Counter(r["status"] for r in data_rows),
    "truth_source_guess_counts": Counter(r["truth_source_guess"] for r in data_rows),
}
(OUT / "05_engine_output_rowcounts.json").write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")

def md_table(rows, max_rows=40):
    if not rows:
        return "_No rows._\n"
    keys = list(rows[0].keys())
    lines = ["|" + "|".join(keys) + "|", "|" + "|".join(["---"] * len(keys)) + "|"]
    for r in rows[:max_rows]:
        vals = []
        for k in keys:
            v = str(r.get(k, ""))
            v = v.replace("\n", " ").replace("|", "/")
            if len(v) > 120:
                v = v[:117] + "..."
            vals.append(v)
        lines.append("|" + "|".join(vals) + "|")
    if len(rows) > max_rows:
        lines.append(f"\n_Showing first {max_rows} of {len(rows)} rows._")
    return "\n".join(lines) + "\n"

final = []
final.append("# Hunt Builder Engine / Database / Rendering Audit\n")
final.append(f"Generated: {summary['generated_at']}\n")
final.append("## Executive Summary\n")
final.append(f"- Total files inventoried: {summary['total_files']}\n")
final.append(f"- Engine/transform files detected: {summary['engine_or_transform_files']}\n")
final.append(f"- Data/feeder files detected: {summary['data_or_feeder_files']}\n")
final.append(f"- Dependency references detected: {summary['dependency_edges_detected']}\n")
final.append(f"- Website/rendering files detected: {summary['rendering_files_detected']}\n")
final.append(f"- Large files over 10 MB: {summary['large_files_over_10mb']}\n")
final.append(f"- Duplicate feeder-name conflicts: {summary['truth_conflicts_by_duplicate_name']}\n\n")

final.append("## Engines Inventoried\n")
final.append(md_table(engine_rows, 80))

final.append("\n## Feeder Files / Truth Source Status\n")
priority_data = sorted(data_rows, key=lambda r: (r["truth_source_guess"] == "unknown", -int(r["size_bytes"] or 0)))
final.append(md_table(priority_data, 80))

final.append("\n## Duplicate/Conflict Candidates\n")
final.append(md_table(conflicts, 80))

final.append("\n## Website Delivery / Rendering Inventory\n")
final.append(md_table(render_rows, 80))

final.append("\n## Large Files Not To Stage\n")
final.append(md_table(large_files, 80))

final.append("\n## Initial Findings\n")
final.append("- This audit is inventory/read-only. It does not repair data, stage Git files, or push.\n")
final.append("- Any file listed in `00_large_files_over_10mb.csv` should be reviewed before staging. Most large raw/generated files belong in R2 or ignored local storage, not Git.\n")
final.append("- Engine files marked `INVENTORIED_NEEDS_RUNTIME_CHECK` need direct CLI/test execution after their feeder dependencies are confirmed.\n")
final.append("- Website files marked `INVENTORIED_NEEDS_BROWSER_CHECK` need local preview validation after data paths are confirmed.\n")

final.append("\n## Next Required Terminal Checks\n")
final.append("```powershell\n")
final.append("git status --short\n")
final.append("Get-ChildItem audits\\prediction_engine_full_audit -File | Select-Object Name,Length,LastWriteTime\n")
final.append("```\n")

(OUT / "FINAL_ENGINE_DATABASE_RENDERING_AUDIT.md").write_text("".join(final), encoding="utf-8")

print("AUDIT COMPLETE")
print(json.dumps(summary, indent=2, default=str))
print("")
print("Generated files:")
for p in sorted(OUT.glob("*")):
    print(" -", p.relative_to(ROOT))
