from pathlib import Path
import csv, json, subprocess, re, sys
from collections import Counter

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"
OUT.mkdir(parents=True, exist_ok=True)

def read_text(path, limit=500000):
    p = ROOT / path
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")[:limit]
    except Exception:
        return ""

def csv_profile(path):
    p = ROOT / path
    result = {
        "file": path,
        "exists": p.exists(),
        "size_mb": round(p.stat().st_size / 1024 / 1024, 3) if p.exists() else "",
        "rows": "",
        "columns": "",
        "sample_columns": "",
        "hunt_code_like_columns": "",
        "status": "MISSING",
        "notes": "",
    }
    if not p.exists():
        return result
    try:
        with p.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = 0
            sample = []
            for row in reader:
                rows += 1
                if len(sample) < 3:
                    sample.append({k: row.get(k, "") for k in fields[:12]})
            result["rows"] = rows
            result["columns"] = len(fields)
            result["sample_columns"] = ";".join(fields[:60])
            result["hunt_code_like_columns"] = ";".join([c for c in fields if "hunt" in c.lower() or "code" in c.lower()][:20])
            result["status"] = "PASS" if rows > 0 and fields else "FAIL_EMPTY"
            result["notes"] = str(sample)[:1000]
    except Exception as e:
        result["status"] = "FAIL_READ"
        result["notes"] = str(e)
    return result

def json_head_check(path):
    p = ROOT / path
    result = {
        "file": path,
        "exists": p.exists(),
        "size_mb": round(p.stat().st_size / 1024 / 1024, 3) if p.exists() else "",
        "status": "MISSING",
        "first_200": "",
        "parse_note": "",
    }
    if not p.exists():
        return result
    try:
        head = p.open("rb").read(2000).decode("utf-8", errors="ignore")
        result["first_200"] = head[:200].replace("\n", "\\n")
        try:
            if p.stat().st_size < 100 * 1024 * 1024:
                obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
                result["status"] = "PASS_JSON"
                result["parse_note"] = f"type={type(obj).__name__}; count={len(obj) if hasattr(obj,'__len__') else ''}"
            else:
                result["status"] = "SKIPPED_FULL_PARSE_LARGE"
        except Exception as e:
            # Try first line JSONL.
            line = head.splitlines()[0] if head.splitlines() else ""
            try:
                json.loads(line)
                result["status"] = "PASS_FIRST_LINE_JSONL"
                result["parse_note"] = "first line parses as JSON"
            except Exception as e2:
                result["status"] = "FAIL_PARSE_SAMPLE"
                result["parse_note"] = f"json={str(e)[:160]}; jsonl={str(e2)[:160]}"
    except Exception as e:
        result["status"] = "FAIL_READ"
        result["parse_note"] = str(e)
    return result

def grep_refs(path, patterns):
    text = read_text(path)
    rows = []
    for pat in patterns:
        hits = []
        for i, line in enumerate(text.splitlines(), 1):
            if pat.lower() in line.lower():
                hits.append(f"L{i}: {line.strip()[:220]}")
        rows.append({
            "file": path,
            "pattern": pat,
            "hit_count": len(hits),
            "sample_hits": " || ".join(hits[:12]),
        })
    return rows

def write_csv(name, rows):
    p = OUT / name
    if not rows:
        p.write_text("", encoding="utf-8")
        return
    keys = sorted({k for row in rows for k in row.keys()})
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)

point_files = [
    "processed_data/point_ladder_view.csv",
    "data_model/runtime_drafts/point_ladder_view_v2.csv",
    "data_model/runtime_drafts/point_ladder_view_v3.csv",
    "processed_data/backups/current_year_allotment_overlay_20260523_071315/point_ladder_view.csv",
]

json_files = [
    "processed_data/public_contracts/hunt_odds_history.json",
    "processed_data/public_contracts/hunt_predictions.json",
    "data/hunt_predictions.json",
    "data/hunt_odds_history.json",
    "processed_data/hunt_research_2026.json",
    "processed_data/hunt_research_2026_ladder.json",
]

hardcopy_files = [
    "hard-copy/data/documents.json",
    "public/hard-copy/data/documents.json",
    "public/hard-copy/data/library_page_data.json",
    "public/hard-copy/data/library_page_hunts.csv",
    "public/hard-copy/data/library_page_summary.json",
    "public/hard-copy/manifests/hard_data_manifest.json",
]

point_profiles = [csv_profile(f) for f in point_files]
json_profiles = [json_head_check(f) for f in json_files]
hardcopy_profiles = []
for f in hardcopy_files:
    if f.endswith(".csv"):
        hardcopy_profiles.append(csv_profile(f))
    else:
        hardcopy_profiles.append(json_head_check(f))

ref_rows = []
ref_rows += grep_refs("config.js", ["point_ladder_view.csv", "json.uoga.workers.dev", "hunt_research_2026_split", "draw_reality_engine_predictive_v2"])
ref_rows += grep_refs("hunt-research.js", ["point_ladder_view.csv", "json.uoga.workers.dev", "hunt_research_2026_split", "hunt_research_2026_ladder", "ml_draw"])
ref_rows += grep_refs("assets/js/hard-copy-public-library.js", ["documents.json", "library_page_data.json", "library_page_hunts.csv", "processed_data", "public/hard-copy"])
ref_rows += grep_refs("scripts/build-library-page-data.js", ["library_page_data.json", "point_ladder_view.csv", "ml_draw_predictions_v1.csv", "draw_reality_engine_predictive_v2.csv"])

write_csv("22_phase5_point_ladder_profiles.csv", point_profiles)
write_csv("23_phase5_json_breakpoint_profiles.csv", json_profiles)
write_csv("24_phase5_hardcopy_library_profiles.csv", hardcopy_profiles)
write_csv("25_phase5_code_reference_hits.csv", ref_rows)

status = subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, errors="ignore")

md = []
md.append("# Phase 5 Targeted Production Breakpoint Check\n\n")
md.append("## Git Status\n\n```text\n" + status + "\n```\n")
md.append("## Primary Findings To Review\n\n")
md.append("- Compare `processed_data/point_ladder_view.csv` against runtime draft versions. If production has only 2 rows while runtime draft has tens of thousands, production point ladder rendering is likely broken or starved.\n")
md.append("- `processed_data/public_contracts/hunt_odds_history.json` failed Phase 4 parsing. Confirm whether it is used. If not used, do not repair it unnecessarily. If used, regenerate from CSV or remove from runtime manifest.\n")
md.append("- `hard-copy/data/documents.json` is missing, but public hard-copy library data exists. Confirm whether the JS fallback prefers `public/hard-copy/data/library_page_data.json` or still expects `documents.json`.\n\n")

def md_table(rows, cols):
    if not rows:
        return "_No rows._\n"
    lines = ["|" + "|".join(cols) + "|", "|" + "|".join(["---"] * len(cols)) + "|"]
    for r in rows:
        vals = []
        for c in cols:
            v = str(r.get(c, "")).replace("\n"," ").replace("|","/")
            if len(v) > 140:
                v = v[:137] + "..."
            vals.append(v)
        lines.append("|" + "|".join(vals) + "|")
    return "\n".join(lines) + "\n"

md.append("## Point Ladder Profiles\n\n")
md.append(md_table(point_profiles, ["file","exists","size_mb","rows","columns","hunt_code_like_columns","status"]))
md.append("\n## JSON Breakpoint Profiles\n\n")
md.append(md_table(json_profiles, ["file","exists","size_mb","status","first_200","parse_note"]))
md.append("\n## Hard-Copy Library Profiles\n\n")
md.append(md_table(hardcopy_profiles, ["file","exists","size_mb","status","first_200","parse_note"]))
md.append("\n## Code Reference Hits\n\n")
md.append(md_table(ref_rows, ["file","pattern","hit_count","sample_hits"]))

(OUT / "PHASE5_TARGETED_BREAKPOINT_CHECK.md").write_text("".join(md), encoding="utf-8")

print("PHASE 5 COMPLETE")
print("")
print("Point ladder profiles:")
for r in point_profiles:
    print(f" - {r['file']}: exists={r['exists']} rows={r['rows']} cols={r['columns']} size={r['size_mb']}MB status={r['status']}")

print("")
print("JSON profiles:")
for r in json_profiles:
    print(f" - {r['file']}: {r['status']} size={r['size_mb']}MB note={r['parse_note'][:120]}")

print("")
print("Hard-copy profiles:")
for r in hardcopy_profiles:
    print(f" - {r['file']}: exists={r['exists']} status={r['status']} size={r['size_mb']}MB")

print("")
print("Reference hit summary:")
for r in ref_rows:
    print(f" - {r['file']} :: {r['pattern']} => {r['hit_count']} hits")

print("")
print("Created:")
for name in [
    "22_phase5_point_ladder_profiles.csv",
    "23_phase5_json_breakpoint_profiles.csv",
    "24_phase5_hardcopy_library_profiles.csv",
    "25_phase5_code_reference_hits.csv",
    "PHASE5_TARGETED_BREAKPOINT_CHECK.md",
]:
    p = OUT / name
    print(f" - {p.relative_to(ROOT)} ({p.stat().st_size} bytes)")

print("")
print("Git status:")
print(status)

