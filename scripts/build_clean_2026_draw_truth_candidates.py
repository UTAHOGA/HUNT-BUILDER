from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
SCORABLE = REPO / "outputs" / "2026 scorable draw results.csv"
CANONICAL = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
OUT_DIR = REPO / "pipeline" / "R2_OFFLOAD" / "incoming" / "clean_2026_draw_truth_candidates"


KEY_FIELDS = ["hunt_code", "actual_draw_year", "draw_design", "residency", "points"]
NUMERIC_SUM_FIELDS = ["eligible_applicants", "bonus_permits", "regular_permits", "total_permits"]
REQUIRED_TEXT_FIELDS = [
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "draw_design",
    "boundary_id",
    "season",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def parse_int(value: object) -> int:
    text = clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except ValueError:
        return 0


def ratio(applicants: str, permits: str) -> str:
    app = parse_int(applicants)
    per = parse_int(permits)
    if app <= 0 or per <= 0:
        return "N/A"
    return f"{per / app:.9f}".rstrip("0").rstrip(".")


def key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(clean(row.get(field)).upper() if field == "hunt_code" else clean(row.get(field)) for field in KEY_FIELDS)


def is_point_row(row: dict[str, str]) -> bool:
    return clean(row.get("record_type")).lower() in {
        "point_level_draw_result",
        "point_row",
        "point_level",
        "sportsman_total",
        "sportsman_total_draw_result",
        "sportsman_random_total",
    } and all(clean(row.get(field)) for field in KEY_FIELDS)


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)


def collapse_rows(rows: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    passthrough: list[dict[str, str]] = []
    for row in rows:
        if is_point_row(row):
            grouped[key(row)].append(row)
        else:
            passthrough.append(row)

    collapsed: list[dict[str, str]] = []
    audit: list[dict[str, str]] = []
    for group_key, group in grouped.items():
        if len(group) == 1:
            collapsed.append(group[0])
            continue

        base = dict(group[0])
        for field in NUMERIC_SUM_FIELDS:
            base[field] = str(sum(parse_int(row.get(field)) for row in group))
        base["success_ratio"] = ratio(base.get("eligible_applicants", ""), base.get("total_permits", ""))
        # Do not fabricate p_draw/p_draw_percent; those are not source PDF fields.
        base["p_draw"] = ""
        base["p_draw_percent"] = ""

        source_files: list[str] = []
        for row in group:
            source_file = clean(row.get("source_file"))
            if source_file and source_file not in source_files:
                source_files.append(source_file)
        if source_files:
            base["source_file"] = "; ".join(source_files[:5])

        note = clean(base.get("notes"))
        collapse_note = f"collapsed_duplicate_point_rows={len(group)}"
        base["notes"] = f"{note}; {collapse_note}" if note else collapse_note
        collapsed.append(base)
        audit.append(
            {
                "hunt_code": base.get("hunt_code", ""),
                "actual_draw_year": base.get("actual_draw_year", ""),
                "draw_design": base.get("draw_design", ""),
                "residency": base.get("residency", ""),
                "points": base.get("points", ""),
                "collapsed_row_count": str(len(group)),
                "eligible_applicants_sum": base.get("eligible_applicants", ""),
                "total_permits_sum": base.get("total_permits", ""),
                "success_ratio_recomputed": base.get("success_ratio", ""),
                "source_files": base.get("source_file", ""),
            }
        )

    return collapsed + passthrough, audit


def audit_rows(rows: list[dict[str, str]]) -> dict[str, object]:
    keys = [key(row) for row in rows if is_point_row(row)]
    duplicate_keys = {item for item in keys if keys.count(item) > 1}
    return {
        "rows": len(rows),
        "unique_hunt_codes": len({clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))}),
        "point_rows": len(keys),
        "unique_point_keys": len(set(keys)),
        "duplicate_point_key_groups": len(duplicate_keys),
        "blank_counts": {
            field: sum(1 for row in rows if not clean(row.get(field)))
            for field in REQUIRED_TEXT_FIELDS
            if any(field in row for row in rows)
        },
    }


def process_file(source: Path, output_name: str) -> dict[str, object]:
    fields, rows = read_csv(source)
    before = audit_rows(rows)
    cleaned, collapse_audit = collapse_rows(rows)
    after = audit_rows(cleaned)
    out_path = OUT_DIR / output_name
    audit_path = OUT_DIR / output_name.replace(".csv", "_collapse_audit.csv")
    write_csv(out_path, fields, cleaned)
    write_csv(
        audit_path,
        [
            "hunt_code",
            "actual_draw_year",
            "draw_design",
            "residency",
            "points",
            "collapsed_row_count",
            "eligible_applicants_sum",
            "total_permits_sum",
            "success_ratio_recomputed",
            "source_files",
        ],
        collapse_audit,
    )
    return {
        "source": str(source.relative_to(REPO)).replace("\\", "/"),
        "output": str(out_path.relative_to(REPO)).replace("\\", "/"),
        "collapse_audit": str(audit_path.relative_to(REPO)).replace("\\", "/"),
        "before": before,
        "after": after,
        "collapsed_groups": len(collapse_audit),
        "output_size_mb": round(out_path.stat().st_size / 1024 / 1024, 3),
        "r2_required": out_path.stat().st_size > 10 * 1024 * 1024,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "rule": "Collapse duplicate 2026 point keys only; preserve identifiers and non-point/reference rows.",
        "outputs": [
            process_file(SCORABLE, "draw_results_2026_scorable_clean_candidate.csv"),
            process_file(CANONICAL, "draw_results_2026_for_2027_canonical_clean_candidate.csv"),
        ],
    }
    summary_path = OUT_DIR / "clean_2026_draw_truth_candidates_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
