from pathlib import Path
import csv, json, subprocess, hashlib
from collections import Counter

ROOT = Path.cwd()
OUT = ROOT / "audits" / "prediction_engine_full_audit"
OUT.mkdir(parents=True, exist_ok=True)

CANDIDATES = {
    "point_ladder": [
        "processed_data/point_ladder_view.csv",
        "data_model/runtime_drafts/point_ladder_view_v2.csv",
        "data_model/runtime_drafts/point_ladder_view_v3.csv",
        "processed_data/backups/current_year_allotment_overlay_20260523_071315/point_ladder_view.csv",
    ],
    "draw_reality": [
        "processed_data/draw_reality_engine_predictive_v2.csv",
        "processed_data/draw_reality_engine_v2.csv",
        "processed_data/draw_reality_view.csv",
        "data_model/runtime_drafts/draw_reality_engine_v2.csv",
    ],
    "predictions": [
        "processed_data/ml_draw_predictions_v1.csv",
        "processed_data/public_contracts/hunt_predictions.json",
        "data/hunt_predictions.json",
    ],
    "library": [
        "public/hard-copy/data/documents.json",
        "public/hard-copy/data/library_page_data.json",
        "public/hard-copy/data/library_page_hunts.csv",
        "public/hard-copy/data/library_page_summary.json",
        "public/hard-copy/manifests/hard_data_manifest.json",
    ],
    "history": [
        "processed_data/public_contracts/hunt_odds_history.csv",
        "data/hunt_odds_history.csv",
        "processed_data/public_contracts/hunt_odds_history.json",
        "data/hunt_odds_history.json",
    ],
    "truth_database": [
        "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
    ],
}

EXPECTED_BY_FAMILY = {
    "point_ladder": ["hunt", "code", "point", "draw", "pool", "resid", "applicant", "permit", "odds", "prob"],
    "draw_reality": ["hunt", "code", "year", "species", "resid", "permit", "applicant", "draw", "odds"],
    "predictions": ["hunt", "code", "year", "species", "draw", "prob", "prediction", "permit"],
    "library": ["hunt", "code", "name", "species", "unit", "permit"],
    "history": ["hunt", "code", "year", "draw", "odds", "applicant", "permit"],
    "truth_database": ["hunt", "code", "name", "species", "unit", "permit"],
}

def sha_sample(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        h.update(f.read(1024 * 1024))
    return h.hexdigest()[:16]

def profile_csv(path, family):
    p = ROOT / path
    row = base(path, family, "csv")
    if not p.exists():
        row["status"] = "MISSING"
        return row
    try:
        row["size_mb"] = round(p.stat().st_size / 1024 / 1024, 3)
        row["sha256_first_mb"] = sha_sample(p)
        with p.open("r", encoding="utf-8-sig", errors="ignore", newline="") as f:
            reader = csv.DictReader(f)
            fields = reader.fieldnames or []
            rows = 0
            nulls = 0
            dup = 0
            seen = set()
            species = Counter()
            years = Counter()
            hunt_codes = set()
            sample_rows = []
            for r in reader:
                rows += 1
                vals = tuple(str(r.get(c, "")).strip() for c in fields)
                nulls += sum(1 for v in vals if not v or v.lower() in {"null","none","nan","na"})
                if vals in seen:
                    dup += 1
                else:
                    seen.add(vals)

                for k, v in r.items():
                    lk = k.lower()
                    sv = str(v).strip()
                    if "species" in lk and sv:
                        species[sv] += 1
                    if "year" in lk and sv:
                        years[sv] += 1
                    if ("hunt" in lk and "code" in lk) or lk in {"hunt_code", "huntcode", "hunt"}:
                        if sv:
                            hunt_codes.add(sv)
                if len(sample_rows) < 2:
                    sample_rows.append({k: r.get(k, "") for k in fields[:15]})

        lower_fields = [f.lower() for f in fields]
        expected = EXPECTED_BY_FAMILY.get(family, [])
        matched = [term for term in expected if any(term in c for c in lower_fields)]
        missing = [term for term in expected if term not in matched]

        score = 0
        if rows > 1000: score += 40
        if rows > 25000: score += 20
        if 15 <= len(fields) <= 80: score += 20
        if len(fields) > 100: score -= 10
        score += len(matched) * 8
        if dup == 0: score += 10
        if rows <= 10: score -= 100
        if family == "point_ladder" and rows > 50000 and 20 <= len(fields) <= 60:
            score += 30

        row.update({
            "status": "PASS",
            "rows": rows,
            "columns": len(fields),
            "null_cells": nulls,
            "duplicate_full_rows": dup,
            "unique_hunt_codes_detected": len(hunt_codes),
            "top_species": json.dumps(species.most_common(10), ensure_ascii=False),
            "top_years": json.dumps(years.most_common(10), ensure_ascii=False),
            "matched_terms": ";".join(matched),
            "missing_terms": ";".join(missing),
            "first_columns": ";".join(fields[:80]),
            "sample_rows": json.dumps(sample_rows, ensure_ascii=False)[:1200],
            "promotion_score": score,
        })
    except Exception as e:
        row["status"] = "FAIL_READ"
        row["notes"] = str(e)[:400]
    return row

def profile_json(path, family):
    p = ROOT / path
    row = base(path, family, "json")
    if not p.exists():
        row["status"] = "MISSING"
        return row
    try:
        row["size_mb"] = round(p.stat().st_size / 1024 / 1024, 3)
        row["sha256_first_mb"] = sha_sample(p)
        head = p.open("rb").read(2000).decode("utf-8", errors="ignore")
        row["sample_rows"] = head[:600].replace("\n", "\\n")
        if p.stat().st_size <= 120 * 1024 * 1024:
            obj = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
            row["status"] = "PASS"
            row["rows"] = len(obj) if hasattr(obj, "__len__") else ""
            if isinstance(obj, list) and obj and isinstance(obj[0], dict):
                fields = list(obj[0].keys())
                row["columns"] = len(fields)
                lower_fields = [f.lower() for f in fields]
                expected = EXPECTED_BY_FAMILY.get(family, [])
                matched = [term for term in expected if any(term in c for c in lower_fields)]
                row["matched_terms"] = ";".join(matched)
                row["missing_terms"] = ";".join([term for term in expected if term not in matched])
                row["first_columns"] = ";".join(fields[:80])
                row["promotion_score"] = 50 + len(matched) * 8
            elif isinstance(obj, dict):
                row["columns"] = "dict"
                row["first_columns"] = ";".join(list(obj.keys())[:80])
                row["promotion_score"] = 40
        else:
            # Large: determine if JSONL first line parses.
            first_line = head.splitlines()[0] if head.splitlines() else ""
            try:
                json.loads(first_line)
                row["status"] = "PASS_JSONL_SAMPLE"
                row["rows"] = "large_sampled"
                row["promotion_score"] = 35
            except Exception:
                row["status"] = "LARGE_UNPARSED"
                row["promotion_score"] = 5
                row["notes"] = "Large file not fully parsed and first line not standalone JSON."
    except Exception as e:
        row["status"] = "FAIL_READ_OR_PARSE"
        row["notes"] = str(e)[:400]
    return row

def base(path, family, kind):
    return {
        "family": family,
        "file": path,
        "kind": kind,
        "exists": "",
        "size_mb": "",
        "sha256_first_mb": "",
        "status": "",
        "rows": "",
        "columns": "",
        "null_cells": "",
        "duplicate_full_rows": "",
        "unique_hunt_codes_detected": "",
        "top_species": "",
        "top_years": "",
        "matched_terms": "",
        "missing_terms": "",
        "first_columns": "",
        "sample_rows": "",
        "promotion_score": 0,
        "recommended_role": "",
        "notes": "",
    }

rows = []
for family, files in CANDIDATES.items():
    for f in files:
        if f.endswith(".csv"):
            rows.append(profile_csv(f, family))
        elif f.endswith(".json"):
            rows.append(profile_json(f, family))
        else:
            r = base(f, family, "other")
            p = ROOT / f
            r["exists"] = p.exists()
            r["size_mb"] = round(p.stat().st_size / 1024 / 1024, 3) if p.exists() else ""
            r["status"] = "EXISTS" if p.exists() else "MISSING"
            rows.append(r)

# Pick best per family
for family in CANDIDATES:
    fam = [r for r in rows if r["family"] == family and str(r["status"]).startswith("PASS")]
    fam_sorted = sorted(fam, key=lambda r: int(r.get("promotion_score") or 0), reverse=True)
    if fam_sorted:
        fam_sorted[0]["recommended_role"] = "BEST_CANDIDATE"
        for r in fam_sorted[1:]:
            r["recommended_role"] = "SECONDARY_CANDIDATE"

keys = list(rows[0].keys())
out_csv = OUT / "27_phase6_promotion_candidate_completion_audit.csv"
with out_csv.open("w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    w.writerows(rows)

md = []
md.append("# Promotion Candidate Completion Audit\n\n")
md.append("## Recommendation Summary\n\n")
for family in CANDIDATES:
    fam = sorted([r for r in rows if r["family"] == family], key=lambda r: int(r.get("promotion_score") or 0), reverse=True)
    best = fam[0] if fam else None
    if best:
        md.append(f"### {family}\n")
        md.append(f"- Best current candidate: `{best['file']}`\n")
        md.append(f"- Status: {best['status']}\n")
        md.append(f"- Rows: {best['rows']}\n")
        md.append(f"- Columns: {best['columns']}\n")
        md.append(f"- Score: {best['promotion_score']}\n")
        md.append(f"- Missing expected terms: {best['missing_terms']}\n\n")

md.append("## Guardrails\n\n")
md.append("- This audit did not promote, copy, upload, stage, or push files.\n")
md.append("- Large tracked production feeders should not be rewritten unless selected as verified promotion outputs.\n")
md.append("- Wrangler refresh should only upload selected runtime files after this audit is reviewed.\n")

(OUT / "PHASE6_PROMOTION_CANDIDATE_COMPLETION_AUDIT.md").write_text("".join(md), encoding="utf-8")

print("PHASE 6 PROMOTION AUDIT COMPLETE")
print("")
for family in CANDIDATES:
    print(f"== {family} ==")
    fam = sorted([r for r in rows if r["family"] == family], key=lambda r: int(r.get("promotion_score") or 0), reverse=True)
    for r in fam:
        print(f" {r['promotion_score']:>4} | {r['status']:<18} | rows={r['rows']} cols={r['columns']} size={r['size_mb']}MB | {r['file']}")
    print("")

print("Created:")
print(" - audits/prediction_engine_full_audit/27_phase6_promotion_candidate_completion_audit.csv")
print(" - audits/prediction_engine_full_audit/PHASE6_PROMOTION_CANDIDATE_COMPLETION_AUDIT.md")
print("")
print("Git status:")
print(subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True, errors="ignore"))
