from pathlib import Path
import csv, json, subprocess, re, os, sys
from collections import Counter

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"
OUT.mkdir(parents=True, exist_ok=True)

KEY_FEEDERS = [
    "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "processed_data/draw_reality_engine_v2.csv",
    "processed_data/draw_reality_view.csv",
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/hunt_research_2026.json",
    "processed_data/hunt_research_2026_ladder.json",
    "processed_data/hunt_research_2026_ladder_bonus_max_random.json",
    "processed_data/hunt_research_2026_ladder_preference.json",
    "processed_data/public_contracts/hunt_odds_history.csv",
    "processed_data/public_contracts/hunt_odds_history.json",
    "processed_data/public_contracts/hunt_predictions.json",
    "public/hard-copy/data/library_page_data.json",
    "public/hard-copy/data/library_page_hunts.csv",
    "public/hard-copy/data/library_page_summary.json",
    "public/hard-copy/manifests/hard_data_manifest.json",
    "hard-copy/data/documents.json",
]

KEY_CODE = [
    "scripts/build-database-publish-readiness-report.py",
    "scripts/build-library-page-data.js",
    "scripts/publish-runtime-assets-r2.js",
    "tools/verify_prediction_engine_targeted_backfill.py",
    "scripts/audit-active-data-feeds.js",
    "hunt-research.js",
    "scripts/rebuild-runtime-hunt-master-and-split.py",
    "config.js",
    "scripts/build-pages-dist.js",
    "tools/hunt_research_engine/audit_harvest_engine_ingestion.py",
    "assets/js/hard-copy-public-library.js",
    "assets/js/research-outlook-dashboard.js",
    "research.html",
    "hard-copy.html",
    "hard-data.html",
    "app.js",
    "ui.js",
    "header-layout.js",
]

def rel(p):
    return str(p).replace("\\", "/")

def git(args):
    try:
        return subprocess.check_output(["git"] + args, cwd=ROOT, text=True, stderr=subprocess.STDOUT, errors="ignore")
    except subprocess.CalledProcessError as e:
        return e.output
    except Exception as e:
        return str(e)

def file_size_mb(p):
    try:
        return round(p.stat().st_size / 1024 / 1024, 3)
    except Exception:
        return ""

def scan_csv(path):
    result = {
        "exists": path.exists(),
        "kind": "csv",
        "size_mb": file_size_mb(path) if path.exists() else "",
        "status": "MISSING",
        "rows_scanned": "",
        "columns": "",
        "null_cells_scanned": "",
        "duplicate_full_rows_scanned": "",
        "sample_columns": "",
        "notes": "",
    }
    if not path.exists():
        return result
    try:
        with path.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            seen = set()
            dup = 0
            nulls = 0
            rows = 0
            for row in reader:
                rows += 1
                vals = tuple(str(row.get(c, "")).strip() for c in fields)
                nulls += sum(1 for v in vals if v == "" or v.lower() in {"null","none","nan","na"})
                if vals in seen:
                    dup += 1
                else:
                    seen.add(vals)
                if rows >= 100000:
                    result["notes"] = "scanned_first_100000_rows"
                    break
        result.update({
            "status": "PASS" if fields and rows > 0 else "FAIL_EMPTY_OR_NO_HEADER",
            "rows_scanned": rows,
            "columns": len(fields),
            "null_cells_scanned": nulls,
            "duplicate_full_rows_scanned": dup,
            "sample_columns": ";".join(fields[:30]),
        })
    except Exception as e:
        result["status"] = "FAIL_READ"
        result["notes"] = str(e)[:300]
    return result

def scan_json(path):
    result = {
        "exists": path.exists(),
        "kind": "json",
        "size_mb": file_size_mb(path) if path.exists() else "",
        "status": "MISSING",
        "rows_scanned": "",
        "columns": "",
        "null_cells_scanned": "",
        "duplicate_full_rows_scanned": "",
        "sample_columns": "",
        "notes": "",
    }
    if not path.exists():
        return result

    try:
        with path.open("rb") as f:
            head = f.read(4096)
        text_head = head.decode("utf-8", errors="ignore").strip()
        first_char = text_head[:1]
        result["sample_columns"] = f"first_char={first_char}; head={text_head[:150].replace(chr(10),' ')}"

        # Full parse only if not giant. Huge JSON files are sampled to avoid freezing.
        if path.stat().st_size <= 80 * 1024 * 1024:
            obj = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            if isinstance(obj, list):
                result["rows_scanned"] = len(obj)
                if obj and isinstance(obj[0], dict):
                    result["columns"] = len(obj[0])
                    result["sample_columns"] = ";".join(list(obj[0].keys())[:30])
            elif isinstance(obj, dict):
                result["rows_scanned"] = len(obj)
                result["columns"] = "dict"
                result["sample_columns"] = ";".join(list(obj.keys())[:30])
            result["status"] = "PASS_JSON"
        else:
            # Try newline-delimited JSON sample.
            ok = 0
            bad = 0
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f):
                    if i >= 100:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        json.loads(line)
                        ok += 1
                    except Exception:
                        bad += 1
            if ok and not bad:
                result["status"] = "PASS_JSONL_SAMPLE"
                result["rows_scanned"] = ok
                result["notes"] = "large_file_sampled_as_jsonl"
            else:
                result["status"] = "FAIL_JSON_PARSE_OR_GIANT_NON_JSONL"
                result["rows_scanned"] = ok
                result["notes"] = f"sample_jsonl_ok={ok}; sample_jsonl_bad={bad}; full_parse_skipped_due_size"
    except Exception as e:
        result["status"] = "FAIL_JSON_READ"
        result["notes"] = str(e)[:300]
    return result

def scan_text_refs(path):
    p = ROOT / path
    row = {
        "path": path,
        "exists": p.exists(),
        "size_mb": file_size_mb(p) if p.exists() else "",
        "status": "MISSING",
        "data_refs": "",
        "r2_refs": "",
        "notes": "",
    }
    if not p.exists():
        return row
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
        refs = sorted(set(re.findall(r'["\']([^"\']*(?:processed_data|public/hard-copy|hard-copy/data|json\.uoga\.workers\.dev|hunt_research|draw_reality|ml_draw|point_ladder|documents\.json)[^"\']*)["\']', text)))
        r2 = sorted(set(re.findall(r'https?://[^"\'\s)]+|json\.uoga\.workers\.dev[^"\'\s)]*', text)))
        row["status"] = "PASS_READ"
        row["data_refs"] = ";".join(refs[:60])
        row["r2_refs"] = ";".join(r2[:30])
    except Exception as e:
        row["status"] = "FAIL_READ"
        row["notes"] = str(e)[:300]
    return row

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

feeder_rows = []
for f in KEY_FEEDERS:
    p = ROOT / f
    if f.lower().endswith(".csv"):
        r = scan_csv(p)
    elif f.lower().endswith(".json"):
        r = scan_json(p)
    else:
        r = {"exists": p.exists(), "kind": "other", "size_mb": file_size_mb(p) if p.exists() else "", "status": "EXISTS" if p.exists() else "MISSING", "rows_scanned": "", "columns": "", "null_cells_scanned": "", "duplicate_full_rows_scanned": "", "sample_columns": "", "notes": ""}
    r["file"] = f
    feeder_rows.append(r)

code_rows = [scan_text_refs(f) for f in KEY_CODE]

syntax_rows = []
for f in KEY_CODE:
    p = ROOT / f
    if not p.exists():
        syntax_rows.append({"file": f, "kind": "", "status": "MISSING", "notes": ""})
        continue
    if f.endswith(".py"):
        out = git(["-c", "core.quotepath=false", "diff", "--", f])
        proc = subprocess.run([sys.executable, "-m", "py_compile", str(p)], cwd=ROOT, text=True, capture_output=True)
        syntax_rows.append({"file": f, "kind": "python", "status": "PASS_SYNTAX" if proc.returncode == 0 else "FAIL_SYNTAX", "notes": (proc.stderr or proc.stdout)[:500]})
    elif f.endswith(".js"):
        proc = subprocess.run(["node", "--check", str(p)], cwd=ROOT, text=True, capture_output=True)
        syntax_rows.append({"file": f, "kind": "javascript", "status": "PASS_SYNTAX" if proc.returncode == 0 else "FAIL_SYNTAX_OR_NODE_MISSING", "notes": (proc.stderr or proc.stdout)[:500]})
    else:
        syntax_rows.append({"file": f, "kind": "text/html/css", "status": "NOT_SYNTAX_CHECKED", "notes": ""})

status_short = git(["status", "--short"])
diff_stat = git(["diff", "--stat"])
tracked_modified = []
for line in status_short.splitlines():
    if line.startswith(" M ") or line.startswith("M  ") or line.startswith("MM "):
        path = line[3:].strip()
        p = ROOT / path
        tracked_modified.append({
            "path": path,
            "size_mb": file_size_mb(p) if p.exists() else "",
            "risk": "HIGH_LARGE_TRACKED_FILE" if p.exists() and p.stat().st_size >= 10*1024*1024 else ("GENERATED_PUBLIC_DATA" if path.startswith("processed_data/") or path.startswith("public/") else "SOURCE_OR_STYLE"),
        })

write_csv("18_phase4_key_feeder_validation.csv", feeder_rows)
write_csv("19_phase4_page_code_data_refs.csv", code_rows)
write_csv("20_phase4_code_syntax_checks.csv", syntax_rows)
write_csv("21_phase4_modified_file_risk.csv", tracked_modified)

def md_table(rows, cols, limit=80):
    if not rows:
        return "_No rows._\n"
    lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows[:limit]:
        vals = []
        for c in cols:
            v = str(r.get(c, ""))
            v = v.replace("\n", " ").replace("|", "/")
            if len(v) > 120:
                v = v[:117] + "..."
            vals.append(v)
        lines.append("|" + "|".join(vals) + "|")
    if len(rows) > limit:
        lines.append(f"\n_Showing first {limit} of {len(rows)}._")
    return "\n".join(lines) + "\n"

md = []
md.append("# Phase 4 Read-Only Production Validation\n\n")
md.append("## Git Status\n\n```text\n" + status_short + "\n```\n")
md.append("## Diff Stat\n\n```text\n" + diff_stat + "\n```\n")
md.append("## Key Feeder Validation\n\n")
md.append(md_table(feeder_rows, ["file","kind","size_mb","status","rows_scanned","columns","null_cells_scanned","duplicate_full_rows_scanned","sample_columns","notes"], 80))
md.append("\n## Page / Code Data References\n\n")
md.append(md_table(code_rows, ["path","size_mb","status","data_refs","r2_refs","notes"], 80))
md.append("\n## Syntax Checks\n\n")
md.append(md_table(syntax_rows, ["file","kind","status","notes"], 80))
md.append("\n## Modified File Risk\n\n")
md.append(md_table(tracked_modified, ["path","size_mb","risk"], 120))
md.append("\n## Phase 4 Interpretation\n\n")
md.append("- PASS_JSONL_SAMPLE means the file is likely newline-delimited JSON or chunked records, not ordinary JSON. Do not call it corrupt until the consuming script is checked.\n")
md.append("- FAIL_JSON_PARSE_OR_GIANT_NON_JSONL means the first sample did not parse as ordinary JSON or JSONL. Verify whether the file is intentionally streamed, compressed, partial, or malformed.\n")
md.append("- HIGH_LARGE_TRACKED_FILE should not be committed without confirming it is required and intentionally regenerated.\n")
md.append("- GENERATED_PUBLIC_DATA should be committed only if it is the intended website delivery output.\n")

(OUT / "PHASE4_READ_ONLY_PRODUCTION_VALIDATION.md").write_text("".join(md), encoding="utf-8")

print("PHASE 4 COMPLETE")
print("Created:")
for name in [
    "18_phase4_key_feeder_validation.csv",
    "19_phase4_page_code_data_refs.csv",
    "20_phase4_code_syntax_checks.csv",
    "21_phase4_modified_file_risk.csv",
    "PHASE4_READ_ONLY_PRODUCTION_VALIDATION.md",
]:
    p = OUT / name
    print(f" - {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

print("")
print("Feeder statuses:")
for r in feeder_rows:
    print(f" - {r['file']}: {r['status']} rows={r.get('rows_scanned')} cols={r.get('columns')} size={r.get('size_mb')}MB")

print("")
print("Syntax statuses:")
for r in syntax_rows:
    print(f" - {r['file']}: {r['status']}")

print("")
print("Modified file risk:")
for r in tracked_modified:
    print(f" - {r['risk']}: {r['path']} {r['size_mb']}MB")

print("")
print("Git status:")
print(status_short)
