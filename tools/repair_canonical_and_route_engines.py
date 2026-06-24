from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]

# Canonical/current hunt catalog
CURRENT_DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

# Engine-facing historical draw truth, if present
DRAW_RESULTS_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"

OUT_DIR = REPO / "audits" / "canonical_database_repair_and_engine_routing" / datetime.now().strftime("%Y%m%d_%H%M%S")
FEED_DIR = REPO / "processed_data" / "engine_feeds"

OUT_DIR.mkdir(parents=True, exist_ok=True)
FEED_DIR.mkdir(parents=True, exist_ok=True)


def make_unique_headers(headers):
    seen = Counter()
    fixed = []
    duplicates = []

    for h in headers:
        base = (h or "").strip()
        if not base:
            base = "blank_column"

        seen[base] += 1
        if seen[base] == 1:
            fixed.append(base)
        else:
            new_name = f"{base}__duplicate_{seen[base]}"
            fixed.append(new_name)
            duplicates.append((base, new_name))

    return fixed, duplicates


def read_csv_robust(path: Path):
    if not path.exists():
        return [], [], []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], [], []

        headers, duplicates = make_unique_headers(raw_headers)
        rows = []

        for line_no, values in enumerate(reader, start=2):
            # pad or trim safely
            if len(values) < len(headers):
                values = values + [""] * (len(headers) - len(values))
            elif len(values) > len(headers):
                values = values[:len(headers)]

            row = dict(zip(headers, values))
            row["_source_file"] = str(path.relative_to(REPO))
            row["_source_line"] = str(line_no)
            rows.append(row)

    return headers + ["_source_file", "_source_line"], rows, duplicates


def write_csv(path: Path, rows, preferred_headers=None):
    path.parent.mkdir(parents=True, exist_ok=True)

    all_headers = []
    seen = set()

    if preferred_headers:
        for h in preferred_headers:
            if h not in seen:
                all_headers.append(h)
                seen.add(h)

    for row in rows:
        for h in row.keys():
            if h not in seen:
                all_headers.append(h)
                seen.add(h)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=all_headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def val(row, *names):
    lowered = {k.lower(): k for k in row.keys()}
    for name in names:
        k = lowered.get(name.lower())
        if k is not None:
            return str(row.get(k, "")).strip()
    return ""


def norm_text(s):
    return re.sub(r"\s+", " ", str(s or "").strip())


def norm_code(s):
    return norm_text(s).upper()


def haystack(row):
    fields = [
        "hunt_code", "code",
        "hunt_name", "name",
        "species",
        "sex", "sex_class", "animal_class",
        "weapon",
        "hunt_type", "hunt_class", "hunt_category",
        "draw_design", "draw_method", "draw_system",
        "point_system", "permit_pool",
        "residency",
    ]
    return " | ".join(norm_text(val(row, f)).lower() for f in fields)


def classify_engine(row):
    h = haystack(row)

    hunt_code = norm_code(val(row, "hunt_code", "code"))
    hunt_name = norm_text(val(row, "hunt_name", "name")).lower()

    point_system = norm_text(val(row, "point_system")).lower()
    draw_method = norm_text(val(row, "draw_method")).lower()
    draw_design = norm_text(val(row, "draw_design")).lower()
    hunt_category = norm_text(val(row, "hunt_category", "hunt_type", "hunt_class")).lower()

    # Hard holds first. These must not accidentally enter preference math.
    bonus_terms = [
        "limited entry",
        "limited-entry",
        "le ",
        " l.e.",
        "premium limited",
        "once-in-a-lifetime",
        "oil",
        "o.i.l",
        "bonus",
        "bear",
        "cougar",
        "turkey",
        "bison",
        "moose",
        "sheep",
        "goat",
        "pronghorn buck",
        "buck pronghorn",
    ]

    if any(t in h for t in bonus_terms):
        # Doe pronghorn is preference; buck pronghorn is not.
        if "doe pronghorn" not in h and "doe antelope" not in h:
            return "HOLD_BONUS_OR_NONPREFERENCE", "LE/PLE/OIL/bonus/non-preference family held out of preference engine"

    availability_terms = [
        "otc",
        "over the counter",
        "unlimited",
        "pursuit",
        "availability",
        "available only",
        "direct allocation",
        "no draw",
        "not applicable",
        "conservation",
        "expo",
        "cwmu",
        "private land",
        "private-land",
        "landowner",
    ]

    if any(t in h for t in availability_terms):
        return "AVAILABILITY_ONLY", "Availability/direct-allocation/OTC-style row"

    if "youth" in h:
        # If it is explicitly a youth preference family, still route preference.
        if "preference" not in h:
            return "YOUTH_RANDOM", "Youth random-style row"

    preference_family_terms = [
        "general season buck deer",
        "general-season buck deer",
        "gs buck deer",
        "g.s. buck deer",
        "dedicated hunter",
        "d.h. deer",
        "dh deer",
        "antlerless deer",
        "antlerless elk",
        "doe pronghorn",
        "doe antelope",
    ]

    if point_system == "preference" or draw_method == "preference" or "preference" in draw_design:
        return "PREFERENCE_DRAW", "Explicit preference draw field"

    if any(t in h for t in preference_family_terms):
        return "PREFERENCE_DRAW", "Known Utah preference family"

    return "REVIEW_REQUIRED", "Could not safely classify engine route"


def canonical_key(row):
    return (
        norm_code(val(row, "hunt_code", "code")),
        norm_text(val(row, "hunt_name", "name")).lower(),
        norm_text(val(row, "residency")).lower(),
        norm_text(val(row, "points", "point_level", "bonus_points", "preference_points")).lower(),
        norm_text(val(row, "year", "permit_year", "source_year", "draw_year")).lower(),
    )


def repair_rows(rows):
    repaired = []
    duplicate_keys = Counter()

    for row in rows:
        new = dict(row)

        # Normalize core identity fields without deleting originals.
        if val(new, "hunt_code", "code"):
            new["hunt_code_normalized"] = norm_code(val(new, "hunt_code", "code"))

        if val(new, "hunt_name", "name"):
            new["hunt_name_normalized"] = norm_text(val(new, "hunt_name", "name"))

        if val(new, "residency"):
            r = norm_text(val(new, "residency")).lower()
            if r in {"res", "resident", "r"}:
                new["residency_normalized"] = "Resident"
            elif r in {"nonres", "nonresident", "non-resident", "nr"}:
                new["residency_normalized"] = "Nonresident"
            else:
                new["residency_normalized"] = norm_text(val(new, "residency"))

        route, reason = classify_engine(new)
        new["engine_route"] = route
        new["engine_route_reason"] = reason

        key = canonical_key(new)
        duplicate_keys[key] += 1
        new["_canonical_key"] = "||".join(key)

        repaired.append(new)

    for row in repaired:
        key = tuple(row["_canonical_key"].split("||"))
        row["_duplicate_key_count"] = str(duplicate_keys[key])

    return repaired


def summarize(rows):
    return {
        "row_count": len(rows),
        "engine_routes": dict(Counter(r.get("engine_route", "") for r in rows)),
        "duplicate_key_rows": sum(1 for r in rows if r.get("_duplicate_key_count") not in {"", "1"}),
        "missing_hunt_code": sum(1 for r in rows if not val(r, "hunt_code", "code")),
        "missing_hunt_name": sum(1 for r in rows if not val(r, "hunt_name", "name")),
    }


def main():
    sources = []

    for path in [CURRENT_DATABASE, DRAW_RESULTS_LONG]:
        headers, rows, duplicates = read_csv_robust(path)
        if rows:
            sources.append({
                "path": path,
                "headers": headers,
                "rows": rows,
                "duplicates": duplicates,
            })

    if not sources:
        raise SystemExit("No canonical input files found.")

    all_rows = []
    duplicate_header_report = []

    for src in sources:
        all_rows.extend(src["rows"])
        for old, new in src["duplicates"]:
            duplicate_header_report.append({
                "source_file": str(src["path"].relative_to(REPO)),
                "duplicate_header": old,
                "renamed_to": new,
            })

    repaired = repair_rows(all_rows)

    preferred = [
        "engine_route",
        "engine_route_reason",
        "hunt_code",
        "hunt_code_normalized",
        "hunt_name",
        "hunt_name_normalized",
        "species",
        "sex",
        "sex_class",
        "weapon",
        "residency",
        "residency_normalized",
        "points",
        "point_level",
        "year",
        "permit_year",
        "source_year",
        "draw_year",
        "draw_design",
        "draw_method",
        "draw_system",
        "point_system",
        "permit_pool",
        "hunt_category",
        "hunt_type",
        "hunt_class",
        "_source_file",
        "_source_line",
        "_canonical_key",
        "_duplicate_key_count",
    ]

    candidate_path = OUT_DIR / "CANONICAL_REPAIRED_CANDIDATE.csv"
    write_csv(candidate_path, repaired, preferred)

    routes = defaultdict(list)
    for row in repaired:
        routes[row["engine_route"]].append(row)

    feed_paths = {
        "PREFERENCE_DRAW": FEED_DIR / "preference_draw_feed.csv",
        "YOUTH_RANDOM": FEED_DIR / "youth_random_feed.csv",
        "AVAILABILITY_ONLY": FEED_DIR / "availability_only_feed.csv",
        "HOLD_BONUS_OR_NONPREFERENCE": FEED_DIR / "hold_bonus_or_nonpreference_feed.csv",
        "REVIEW_REQUIRED": FEED_DIR / "routing_review_required.csv",
    }

    for route, path in feed_paths.items():
        write_csv(path, routes.get(route, []), preferred)

    write_csv(OUT_DIR / "duplicate_header_report.csv", duplicate_header_report)

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "repo": str(REPO),
        "inputs": [
            {
                "path": str(src["path"].relative_to(REPO)),
                "rows": len(src["rows"]),
                "duplicate_headers": src["duplicates"],
            }
            for src in sources
        ],
        "summary": summarize(repaired),
        "outputs": {
            "canonical_candidate": str(candidate_path.relative_to(REPO)),
            "preference_draw_feed": str(feed_paths["PREFERENCE_DRAW"].relative_to(REPO)),
            "youth_random_feed": str(feed_paths["YOUTH_RANDOM"].relative_to(REPO)),
            "availability_only_feed": str(feed_paths["AVAILABILITY_ONLY"].relative_to(REPO)),
            "hold_bonus_or_nonpreference_feed": str(feed_paths["HOLD_BONUS_OR_NONPREFERENCE"].relative_to(REPO)),
            "review_required": str(feed_paths["REVIEW_REQUIRED"].relative_to(REPO)),
            "duplicate_header_report": str((OUT_DIR / "duplicate_header_report.csv").relative_to(REPO)),
        },
    }

    (OUT_DIR / "repair_and_route_summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")

    md = []
    md.append("# Canonical Database Repair and Engine Routing")
    md.append("")
    md.append(f"Created: {report['created_at']}")
    md.append("")
    md.append("## Inputs")
    for src in report["inputs"]:
        md.append(f"- `{src['path']}` rows={src['rows']} duplicate_headers={len(src['duplicate_headers'])}")
    md.append("")
    md.append("## Route counts")
    for route, count in report["summary"]["engine_routes"].items():
        md.append(f"- `{route}`: {count}")
    md.append("")
    md.append("## Quality checks")
    md.append(f"- Duplicate-key rows: {report['summary']['duplicate_key_rows']}")
    md.append(f"- Missing hunt code: {report['summary']['missing_hunt_code']}")
    md.append(f"- Missing hunt name: {report['summary']['missing_hunt_name']}")
    md.append("")
    md.append("## Outputs")
    for name, path in report["outputs"].items():
        md.append(f"- `{name}`: `{path}`")
    md.append("")
    md.append("## Promotion rule")
    md.append("Do not overwrite the live canonical database until `routing_review_required.csv` and duplicate-key rows are reviewed.")

    (OUT_DIR / "REPAIR_AND_ROUTE_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()