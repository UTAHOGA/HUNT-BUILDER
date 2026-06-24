from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

DEFAULT_DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
DEFAULT_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"

OUT_DIR = REPO / "audits" / "database_blank_fill" / STAMP
OUT_DIR.mkdir(parents=True, exist_ok=True)

BLANK_VALUES = {"", "na", "n/a", "none", "null", "nan", "-", "--"}

SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    "node_modules",
    "__pycache__",
}

DO_NOT_FILL_PATTERNS = [
    r"^_",
    r"engine_route",
    r"engine_route_reason",
    r"previous_engine_route",
    r"review_resolution_reason",
    r"qa_notes",
    r"notes__duplicate",
    r"geometry",
    r"coordinates",
]

SOURCE_PRIORITY = {
    "geojson": 90,
    "json": 80,
    "long_csv": 70,
}

ALIAS_GROUPS = [
    ["hunt_code", "hunt_code_normalized", "code", "huntcode", "hunt_cd"],
    ["hunt_name", "hunt_name_normalized", "name", "unit", "hunt_unit", "raw_hunt_name"],
    ["boundary_id", "boundaryid", "hunt_boundary_id", "boundary", "id", "area_id"],
    ["species", "animal", "game_species"],
    ["sex", "sex_type", "gender"],
    ["sex_class", "animal_class", "class", "sex_type", "gender"],
    ["weapon", "weapon_type", "method"],
    ["season", "season_dates", "hunt_season", "dates"],
    ["hunt_category", "hunt_type", "hunt_class", "hunt_draw_class", "draw_category"],
    ["draw_design", "draw_type", "draw_category"],
    ["draw_method", "draw_system", "draw_2026_system_type", "draw_2025_type"],
    ["point_system", "points_system"],
    ["permit_pool", "pool"],
    ["percent_harvest_success_previous_hunting_season", "harvest_success", "percent_harvest_success", "success_rate"],
    ["average_harvest_age", "avg_harvest_age", "average_age"],
    ["average_harvest_age_reported_hunt_year", "harvest_age_year", "reported_hunt_year"],
    ["dwr_huntplanner_age_objective", "age_objective"],
    ["dwr_huntplanner_population_objective", "population_objective"],
    ["dwr_huntplanner_current_population_estimate", "current_population_estimate", "population_estimate"],
    ["conservation_permits_2026_total", "conservation_permits", "conservation_total"],
]


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def norm_key(value: Any) -> str:
    return clean(value).upper()


def norm_loose(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", clean(value).lower())


def is_blank(value: Any) -> bool:
    return clean(value).lower() in BLANK_VALUES


def should_skip_fill_column(col: str) -> bool:
    for pattern in DO_NOT_FILL_PATTERNS:
        if re.search(pattern, col, flags=re.IGNORECASE):
            return True
    return False


def make_unique_headers(headers: list[str], source_name: str):
    seen_lower = Counter()
    used_lower = set()
    fixed = []
    dupes = []

    for idx, raw in enumerate(headers, start=1):
        base = clean(raw) or "blank_column"
        lower = base.lower()
        seen_lower[lower] += 1

        if lower not in used_lower:
            new = base
        else:
            n = seen_lower[lower]
            new = f"{base}__duplicate_{n}"
            while new.lower() in used_lower:
                n += 1
                new = f"{base}__duplicate_{n}"

            dupes.append({
                "source_file": source_name,
                "column_number": idx,
                "original_header": base,
                "renamed_to": new,
            })

        fixed.append(new)
        used_lower.add(new.lower())

    return fixed, dupes


def read_csv_unique(path: Path, source_kind: str):
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], [], []

        headers, dupes = make_unique_headers(raw_headers, str(path.relative_to(REPO)))
        rows = []

        for line_no, values in enumerate(reader, start=2):
            if len(values) < len(headers):
                values = values + [""] * (len(headers) - len(values))
            elif len(values) > len(headers):
                values = values[:len(headers)]

            row = dict(zip(headers, values))
            row["_source_kind"] = source_kind
            row["_source_file"] = str(path.relative_to(REPO))
            row["_source_line"] = str(line_no)
            rows.append(row)

    return headers, rows, dupes


def write_csv(path: Path, rows: list[dict], preferred_headers: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = []
    seen = set()

    if preferred_headers:
        for h in preferred_headers:
            if h not in seen:
                headers.append(h)
                seen.add(h)

    for row in rows:
        for h in row:
            if h not in seen:
                headers.append(h)
                seen.add(h)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get(row: dict, *names: str) -> str:
    lower = {k.lower(): k for k in row.keys()}
    loose = {norm_loose(k): k for k in row.keys()}

    for name in names:
        k = lower.get(name.lower())
        if k is not None and not is_blank(row.get(k)):
            return clean(row.get(k))

        k = loose.get(norm_loose(name))
        if k is not None and not is_blank(row.get(k)):
            return clean(row.get(k))

    return ""


def safe_rglob(pattern: str):
    for p in REPO.rglob(pattern):
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if "audits" in p.parts:
            continue
        if "hunt-docs" in p.parts:
            continue
        yield p


def auto_find_long_file() -> Path | None:
    if DEFAULT_LONG.exists():
        return DEFAULT_LONG

    candidates = []
    for p in safe_rglob("*long*.csv"):
        name = p.name.lower()
        if "draw" in name or "result" in name:
            candidates.append(p)

    if not candidates:
        return None

    candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
    return candidates[0]


def auto_find_json_files() -> list[Path]:
    direct = [
        REPO / "hunt_research_2026.json",
        REPO / "processed_data" / "hunt_research_2026.json",
        REPO / "processed_data" / "hunt_research_2026_ladder.json",
        REPO / "public" / "hunt_research_2026.json",
        REPO / "data_model" / "runtime_drafts" / "hunt_research_2026.json",
    ]

    found = [p for p in direct if p.exists() and p.is_file()]

    if found:
        return found

    candidates = []
    for p in safe_rglob("*.json"):
        name = p.name.lower()
        path_text = str(p).lower()
        if any(term in name or term in path_text for term in ["hunt_research", "hunt_unit", "planner", "master", "database"]):
            candidates.append(p)

    candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
    return candidates[:5]


def auto_find_geojson_files() -> list[Path]:
    candidates = list(safe_rglob("*.geojson"))
    candidates.sort(key=lambda x: x.stat().st_size, reverse=True)
    return candidates[:10]


def flatten_dict(d: dict, prefix: str = "") -> dict:
    out = {}

    for k, v in d.items():
        key = f"{prefix}_{k}" if prefix else str(k)

        if isinstance(v, dict):
            out.update(flatten_dict(v, key))
        elif isinstance(v, list):
            if all(not isinstance(x, (dict, list)) for x in v) and len(v) <= 20:
                out[key] = "; ".join(clean(x) for x in v)
        else:
            out[key] = v

    return out


def looks_like_record(d: dict) -> bool:
    keys = {norm_loose(k) for k in d.keys()}

    important = {
        "huntcode",
        "code",
        "huntname",
        "unit",
        "species",
        "boundaryid",
        "weapon",
        "season",
        "drawmethod",
        "drawsystem",
        "hunttype",
        "huntclass",
    }

    return bool(keys & important) or len([v for v in d.values() if not isinstance(v, (dict, list)) and not is_blank(v)]) >= 4


def collect_json_records(obj: Any, records: list[dict], depth: int = 0):
    if depth > 8:
        return

    if isinstance(obj, dict):
        if looks_like_record(obj):
            records.append(flatten_dict(obj))

        for v in obj.values():
            if isinstance(v, (dict, list)):
                collect_json_records(v, records, depth + 1)

    elif isinstance(obj, list):
        for item in obj:
            collect_json_records(item, records, depth + 1)


def load_json_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))

    records = []

    if isinstance(data, dict) and data.get("type") == "FeatureCollection" and isinstance(data.get("features"), list):
        return records

    collect_json_records(data, records)

    out = []
    for idx, row in enumerate(records, start=1):
        flat = dict(row)
        flat["_source_kind"] = "json"
        flat["_source_file"] = str(path.relative_to(REPO))
        flat["_source_line"] = str(idx)
        out.append(flat)

    return out


def load_geojson_records(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    out = []

    if not isinstance(data, dict) or data.get("type") != "FeatureCollection":
        return out

    features = data.get("features") or []

    for idx, feature in enumerate(features, start=1):
        props = dict(feature.get("properties") or {})

        if feature.get("id") is not None:
            props["feature_id"] = feature.get("id")

        geometry = feature.get("geometry") or {}
        if isinstance(geometry, dict):
            props["geometry_type"] = geometry.get("type", "")
            props["has_geometry"] = "yes" if geometry else ""

        flat = flatten_dict(props)
        flat["_source_kind"] = "geojson"
        flat["_source_file"] = str(path.relative_to(REPO))
        flat["_source_line"] = str(idx)
        out.append(flat)

    return out


def derive_long_fields(row: dict) -> dict:
    out = dict(row)

    year = get(row, "actual_draw_year", "draw_year", "year", "source_year", "permit_year")
    year_match = re.search(r"(20\d{2})", year or "")

    if not year_match:
        return out

    y = year_match.group(1)

    res = get(
        row,
        "resident_total_permits",
        "resident_permits",
        "res_total_permits",
        "res_permits",
        "permits_res",
        "permits_r",
    )
    nr = get(
        row,
        "nonresident_total_permits",
        "nonresident_permits",
        "nonresident_total",
        "nr_total_permits",
        "nr_permits",
        "permits_nr",
    )
    total = get(
        row,
        "total_permits",
        "permits_total",
        "permit_count",
        "permits",
        "quota",
    )

    if res:
        out[f"permits_{y}_res"] = res
    if nr:
        out[f"permits_{y}_nr"] = nr
    if total:
        out[f"permits_{y}_total"] = total

    if res or nr or total:
        out[f"permits_{y}_source"] = f"long_csv:{get(row, '_source_file')}"

    return out


def alias_candidates_for_target(target_col: str, source_row: dict) -> list[str]:
    target_loose = norm_loose(target_col)
    source_cols = list(source_row.keys())

    candidates = []

    for c in source_cols:
        if c.lower() == target_col.lower() or norm_loose(c) == target_loose:
            candidates.append(c)

    for group in ALIAS_GROUPS:
        group_loose = {norm_loose(x) for x in group}

        if target_loose in group_loose:
            for c in source_cols:
                if norm_loose(c) in group_loose:
                    candidates.append(c)

    m = re.match(r"permits_(20\d{2})_(res|nr|total|source)$", target_col, flags=re.IGNORECASE)
    if m:
        y, bucket = m.group(1), m.group(2).lower()
        dynamic = [f"permits_{y}_{bucket}"]

        if bucket == "res":
            dynamic += ["resident_total_permits", "resident_permits", "permits_res"]
        elif bucket == "nr":
            dynamic += ["nonresident_total_permits", "nonresident_permits", "permits_nr"]
        elif bucket == "total":
            dynamic += ["total_permits", "permits_total", "permit_count", "quota"]

        for c in source_cols:
            if norm_loose(c) in {norm_loose(x) for x in dynamic}:
                candidates.append(c)

    m = re.match(r"permit_allotment_(20\d{2})_(res|nr|total|source)$", target_col, flags=re.IGNORECASE)
    if m:
        y, bucket = m.group(1), m.group(2).lower()
        dynamic = [f"permit_allotment_{y}_{bucket}", f"permits_{y}_{bucket}"]

        for c in source_cols:
            if norm_loose(c) in {norm_loose(x) for x in dynamic}:
                candidates.append(c)

    seen = set()
    out = []

    for c in candidates:
        if c not in seen:
            out.append(c)
            seen.add(c)

    return out


def source_identity(row: dict):
    code = norm_key(get(row, "hunt_code", "hunt_code_normalized", "code", "huntcode"))
    boundary_id = norm_key(get(row, "boundary_id", "boundaryid", "hunt_boundary_id", "id", "feature_id"))
    species = norm_loose(get(row, "species"))
    name = norm_loose(get(row, "hunt_name", "hunt_name_normalized", "unit", "name", "raw_hunt_name"))
    sex = norm_loose(get(row, "sex", "sex_class", "sex_type", "gender"))
    weapon = norm_loose(get(row, "weapon", "weapon_type", "method"))

    composite = "|".join([species, name, sex, weapon]) if species and name else ""

    return {
        "hunt_code": code,
        "boundary_id": boundary_id,
        "composite": composite,
    }


def build_source_indexes(source_rows: list[dict]):
    by_code = defaultdict(list)
    by_boundary = defaultdict(list)
    by_composite = defaultdict(list)

    for row in source_rows:
        ident = source_identity(row)

        if ident["hunt_code"]:
            by_code[ident["hunt_code"]].append(row)

        if ident["boundary_id"]:
            by_boundary[ident["boundary_id"]].append(row)

        if ident["composite"]:
            by_composite[ident["composite"]].append(row)

    return by_code, by_boundary, by_composite


def dedupe_source_rows(rows: list[dict]) -> list[dict]:
    seen = set()
    out = []

    for r in rows:
        key = (
            r.get("_source_kind", ""),
            r.get("_source_file", ""),
            str(r.get("_source_line", "")),
        )
        if key not in seen:
            out.append(r)
            seen.add(key)

    return out


def comparable_value(value: str) -> str:
    value = clean(value)

    try:
        f = float(value.replace(",", ""))
        if f.is_integer():
            return str(int(f))
        return f"{f:.6f}".rstrip("0").rstrip(".")
    except Exception:
        pass

    return value.lower()


def source_label(row: dict, source_col: str) -> str:
    return f"{row.get('_source_kind')}:{row.get('_source_file')}:{row.get('_source_line')}:{source_col}"


def fill_candidate_database(
    db_rows: list[dict],
    db_headers: list[str],
    source_rows: list[dict],
    use_composite: bool = False,
):
    by_code, by_boundary, by_composite = build_source_indexes(source_rows)

    fill_log = []
    conflict_log = []
    unfilled_log = []
    column_fill_counts = Counter()
    source_fill_counts = Counter()

    candidate_rows = []

    for idx, original in enumerate(db_rows, start=2):
        row = dict(original)
        ident = source_identity(row)

        matches = []

        if ident["hunt_code"]:
            matches.extend(by_code.get(ident["hunt_code"], []))

        if ident["boundary_id"]:
            matches.extend(by_boundary.get(ident["boundary_id"], []))

        if use_composite and ident["composite"]:
            matches.extend(by_composite.get(ident["composite"], []))

        matches = dedupe_source_rows(matches)

        fill_count = 0
        fill_sources = []

        for target_col in db_headers:
            if should_skip_fill_column(target_col):
                continue

            if not is_blank(row.get(target_col)):
                continue

            candidates = []

            for src in matches:
                source_kind = src.get("_source_kind", "")
                priority = SOURCE_PRIORITY.get(source_kind, 50)

                source_cols = alias_candidates_for_target(target_col, src)

                for source_col in source_cols:
                    value = clean(src.get(source_col, ""))

                    if is_blank(value):
                        continue

                    if len(value) > 500:
                        continue

                    candidates.append({
                        "value": value,
                        "compare": comparable_value(value),
                        "source_kind": source_kind,
                        "source_file": src.get("_source_file", ""),
                        "source_line": src.get("_source_line", ""),
                        "source_col": source_col,
                        "priority": priority,
                    })

            if not candidates:
                unfilled_log.append({
                    "db_row": idx,
                    "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                    "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                    "target_column": target_col,
                    "reason": "blank_no_matching_source_value",
                })
                continue

            grouped = defaultdict(list)
            for c in candidates:
                grouped[c["compare"]].append(c)

            if len(grouped) > 1:
                conflict_log.append({
                    "db_row": idx,
                    "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                    "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                    "target_column": target_col,
                    "conflicting_values": " || ".join(
                        f"{items[0]['value']} [{len(items)} source(s)]"
                        for _, items in grouped.items()
                    ),
                    "sources": " || ".join(
                        source_label(c, c["source_col"])
                        for c in candidates[:20]
                    ),
                    "action": "not_filled",
                })
                continue

            chosen_group = list(grouped.values())[0]
            chosen_group.sort(key=lambda x: x["priority"], reverse=True)
            chosen = chosen_group[0]

            row[target_col] = chosen["value"]
            fill_count += 1
            column_fill_counts[target_col] += 1
            source_fill_counts[chosen["source_kind"]] += 1
            fill_sources.append(source_label(chosen, chosen["source_col"]))

            fill_log.append({
                "db_row": idx,
                "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                "target_column": target_col,
                "filled_value": chosen["value"],
                "source_kind": chosen["source_kind"],
                "source_file": chosen["source_file"],
                "source_line": chosen["source_line"],
                "source_column": chosen["source_col"],
                "match_hunt_code": ident["hunt_code"],
                "match_boundary_id": ident["boundary_id"],
                "match_composite": ident["composite"] if use_composite else "",
            })

        row["_blank_fill_count"] = str(fill_count)
        row["_blank_fill_run_id"] = STAMP
        row["_blank_fill_sources"] = "; ".join(fill_sources[:25])

        candidate_rows.append(row)

    return {
        "candidate_rows": candidate_rows,
        "fill_log": fill_log,
        "conflict_log": conflict_log,
        "unfilled_log": unfilled_log,
        "column_fill_counts": column_fill_counts,
        "source_fill_counts": source_fill_counts,
    }


def html_report(summary: dict) -> str:
    blockers = summary.get("blockers", [])
    blocker_html = ""

    if blockers:
        blocker_html = "<h2>Blockers</h2><ul>"
        for b in blockers:
            blocker_html += f"<li><strong>{b.get('issue')}</strong>: {b.get('detail')}</li>"
        blocker_html += "</ul>"

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Database Blank Fill Audit</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; max-width: 1100px; }}
table {{ border-collapse: collapse; }}
td, th {{ border: 1px solid #ddd; padding: 6px; }}
.status {{ padding: 12px; background: #f7f7f7; border: 1px solid #ddd; }}
</style>
</head>
<body>
<h1>Database Blank Fill Audit</h1>
<div class="status">
<p><strong>Status:</strong> {summary["status"]}</p>
<p><strong>Created:</strong> {summary["created_at"]}</p>
<p><strong>Database rows:</strong> {summary["database_rows"]:,}</p>
<p><strong>Source rows:</strong> {summary["source_rows"]:,}</p>
<p><strong>Cells filled:</strong> {summary["cells_filled"]:,}</p>
<p><strong>Conflicts:</strong> {summary["conflicts"]:,}</p>
<p><strong>Unfilled blanks logged:</strong> {summary["unfilled_blanks_logged"]:,}</p>
</div>

{blocker_html}

<h2>Output files</h2>
<ul>
<li>{summary["candidate_database"]}</li>
<li>{summary["fill_log"]}</li>
<li>{summary["conflict_log"]}</li>
<li>{summary["unfilled_log"]}</li>
<li>{summary["summary_json"]}</li>
</ul>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default=str(DEFAULT_DATABASE))
    parser.add_argument("--long", default=None)
    parser.add_argument("--json", nargs="*", default=None)
    parser.add_argument("--geojson", nargs="*", default=None)
    parser.add_argument("--use-composite", action="store_true")
    parser.add_argument("--promote", action="store_true")
    args = parser.parse_args()

    database_path = Path(args.database)
    if not database_path.is_absolute():
        database_path = REPO / database_path

    long_path = Path(args.long) if args.long else auto_find_long_file()
    if long_path and not long_path.is_absolute():
        long_path = REPO / long_path

    json_paths = [Path(p) for p in args.json] if args.json else auto_find_json_files()
    geojson_paths = [Path(p) for p in args.geojson] if args.geojson else auto_find_geojson_files()

    json_paths = [(REPO / p if not p.is_absolute() else p) for p in json_paths]
    geojson_paths = [(REPO / p if not p.is_absolute() else p) for p in geojson_paths]

    blockers = []

    if not database_path.exists():
        blockers.append({
            "issue": "missing_database",
            "detail": str(database_path),
        })

    if blockers:
        summary = {
            "status": "BLOCKED",
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "blockers": blockers,
        }
        write_json(OUT_DIR / "summary.json", summary)
        print(json.dumps(summary, indent=2))
        raise SystemExit(1)

    source_inventory = []
    duplicate_header_report = []

    db_headers, db_rows, db_dupes = read_csv_unique(database_path, "database_target")
    duplicate_header_report.extend(db_dupes)

    source_rows = []

    if long_path and long_path.exists():
        long_headers, long_rows, long_dupes = read_csv_unique(long_path, "long_csv")
        duplicate_header_report.extend(long_dupes)

        for row in long_rows:
            source_rows.append(derive_long_fields(row))

        source_inventory.append({
            "source_kind": "long_csv",
            "path": str(long_path.relative_to(REPO)),
            "rows": len(long_rows),
            "exists": True,
        })
    else:
        source_inventory.append({
            "source_kind": "long_csv",
            "path": str(long_path) if long_path else "",
            "rows": 0,
            "exists": False,
        })

    for path in json_paths:
        if not path.exists():
            source_inventory.append({
                "source_kind": "json",
                "path": str(path),
                "rows": 0,
                "exists": False,
            })
            continue

        try:
            rows = load_json_records(path)
        except Exception as e:
            blockers.append({
                "issue": "json_read_failed",
                "detail": f"{path}: {e}",
            })
            rows = []

        source_rows.extend(rows)
        source_inventory.append({
            "source_kind": "json",
            "path": str(path.relative_to(REPO)),
            "rows": len(rows),
            "exists": True,
        })

    for path in geojson_paths:
        if not path.exists():
            source_inventory.append({
                "source_kind": "geojson",
                "path": str(path),
                "rows": 0,
                "exists": False,
            })
            continue

        try:
            rows = load_geojson_records(path)
        except Exception as e:
            blockers.append({
                "issue": "geojson_read_failed",
                "detail": f"{path}: {e}",
            })
            rows = []

        source_rows.extend(rows)
        source_inventory.append({
            "source_kind": "geojson",
            "path": str(path.relative_to(REPO)),
            "rows": len(rows),
            "exists": True,
        })

    result = fill_candidate_database(
        db_rows=db_rows,
        db_headers=db_headers,
        source_rows=source_rows,
        use_composite=args.use_composite,
    )

    candidate_rows = result["candidate_rows"]
    fill_log = result["fill_log"]
    conflict_log = result["conflict_log"]
    unfilled_log = result["unfilled_log"]

    candidate_database = OUT_DIR / "DATABASE_FILLED_CANDIDATE.csv"
    fill_log_path = OUT_DIR / "fill_log.csv"
    conflict_log_path = OUT_DIR / "conflict_log.csv"
    unfilled_log_path = OUT_DIR / "unfilled_blanks.csv"
    duplicate_header_path = OUT_DIR / "duplicate_header_report.csv"
    source_inventory_path = OUT_DIR / "source_inventory.csv"
    column_counts_path = OUT_DIR / "column_fill_counts.csv"
    source_counts_path = OUT_DIR / "source_fill_counts.csv"

    write_csv(candidate_database, candidate_rows, db_headers + ["_blank_fill_count", "_blank_fill_run_id", "_blank_fill_sources"])
    write_csv(fill_log_path, fill_log)
    write_csv(conflict_log_path, conflict_log)
    write_csv(unfilled_log_path, unfilled_log)
    write_csv(duplicate_header_path, duplicate_header_report)
    write_csv(source_inventory_path, source_inventory)

    write_csv(
        column_counts_path,
        [{"column": k, "filled_cells": v} for k, v in result["column_fill_counts"].most_common()],
    )
    write_csv(
        source_counts_path,
        [{"source_kind": k, "filled_cells": v} for k, v in result["source_fill_counts"].most_common()],
    )

    status = "CANDIDATE_CREATED"
    promoted_to = ""

    if args.promote:
        backup = database_path.with_name(f"{database_path.stem}.BACKUP_BEFORE_BLANK_FILL_{STAMP}{database_path.suffix}")
        shutil.copy2(database_path, backup)
        shutil.copy2(candidate_database, database_path)
        promoted_to = str(database_path.relative_to(REPO))
        status = "PROMOTED_WITH_BACKUP"

    summary = {
        "status": status,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "database": str(database_path.relative_to(REPO)),
        "database_rows": len(db_rows),
        "source_rows": len(source_rows),
        "cells_filled": len(fill_log),
        "conflicts": len(conflict_log),
        "unfilled_blanks_logged": len(unfilled_log),
        "duplicate_headers_detected": len(duplicate_header_report),
        "used_composite_matching": args.use_composite,
        "candidate_database": str(candidate_database.relative_to(REPO)),
        "fill_log": str(fill_log_path.relative_to(REPO)),
        "conflict_log": str(conflict_log_path.relative_to(REPO)),
        "unfilled_log": str(unfilled_log_path.relative_to(REPO)),
        "duplicate_header_report": str(duplicate_header_path.relative_to(REPO)),
        "source_inventory": str(source_inventory_path.relative_to(REPO)),
        "column_fill_counts": str(column_counts_path.relative_to(REPO)),
        "source_fill_counts": str(source_counts_path.relative_to(REPO)),
        "summary_json": str((OUT_DIR / "summary.json").relative_to(REPO)),
        "promoted_to": promoted_to,
        "blockers": blockers,
    }

    write_json(OUT_DIR / "summary.json", summary)
    (OUT_DIR / "index.html").write_text(html_report(summary), encoding="utf-8")

    md = [
        f"# Database Blank Fill Audit — {status}",
        "",
        f"Created: {summary['created_at']}",
        "",
        "## Counts",
        f"- Database rows: {summary['database_rows']:,}",
        f"- Source rows: {summary['source_rows']:,}",
        f"- Cells filled: {summary['cells_filled']:,}",
        f"- Conflicts: {summary['conflicts']:,}",
        f"- Unfilled blanks logged: {summary['unfilled_blanks_logged']:,}",
        f"- Duplicate headers detected: {summary['duplicate_headers_detected']:,}",
        f"- Composite matching used: {summary['used_composite_matching']}",
        "",
        "## Outputs",
        f"- Candidate database: `{summary['candidate_database']}`",
        f"- Fill log: `{summary['fill_log']}`",
        f"- Conflict log: `{summary['conflict_log']}`",
        f"- Unfilled blanks: `{summary['unfilled_log']}`",
        f"- Source inventory: `{summary['source_inventory']}`",
        f"- Column fill counts: `{summary['column_fill_counts']}`",
        f"- HTML report: `{str((OUT_DIR / 'index.html').relative_to(REPO))}`",
        "",
        "## Promotion rule",
        "Review `fill_log.csv` and `conflict_log.csv` before replacing the live DATABASE.csv.",
        "",
        "## Safe promotion command",
        "After review, run the script again with `--promote`, or manually backup and copy the candidate.",
    ]

    (OUT_DIR / "AUDIT_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
