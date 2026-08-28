#!/usr/bin/env python3
"""Finalize validation artifacts for the cumulative draw-results truth table.

The draw long table is intentionally left in place because runtime code already
uses it. This script adds the missing cumulative database validation layer:
summary, source audit, year-rule counts, duplicate-key checks, and database
coverage checks.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRUTH_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized"
PROCESSED_DIR = ROOT / "processed_data"
DRAW_LONG = TRUTH_DIR / "draw_results_long.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CROSSWALK = ROOT / "data_truth" / "crosswalk_truth" / "normalized" / "current_to_historical_hunt_code_crosswalk_2026.csv"

SUMMARY_JSON = TRUTH_DIR / "draw_results_all_years_summary.json"
SUMMARY_MD = TRUTH_DIR / "draw_results_all_years_summary.md"
SOURCE_AUDIT = TRUTH_DIR / "draw_results_all_years_source_audit.csv"
PROCESSED_SUMMARY_JSON = PROCESSED_DIR / "draw_results_all_years_summary.json"
PROCESSED_SUMMARY_MD = PROCESSED_DIR / "draw_results_all_years_summary.md"
PROCESSED_SOURCE_AUDIT = PROCESSED_DIR / "draw_results_all_years_source_audit.csv"
SOURCE_IDENTITY_COLLISIONS = TRUTH_DIR / "draw_results_unresolved_source_identity_collisions.csv"

COARSE_KEY_FIELDS = ["hunt_code", "year", "draw_pool", "residency", "points"]
SOURCE_IDENTITY_KEY_FIELDS = COARSE_KEY_FIELDS + [
    "source_scope",
    "source_file",
    "record_type",
    "pdf_page",
    "source_row_identifier",
]
SOURCE_AUDIT_FIELDS = [
    "source_file",
    "year",
    "row_count",
    "unique_hunt_codes",
    "resident_rows",
    "nonresident_rows",
    "database_truth_yes_rows",
    "database_truth_no_rows",
    "database_truth_blank_rows",
    "blank_hunt_code_rows",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{k: (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def safe_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def row_year(row: dict[str, str]) -> str:
    for field in ("actual_draw_year", "year", "draw_year", "model_target_year"):
        value = str(row.get(field) or "").strip()
        if value:
            return value
    return ""


def read_database_codes() -> set[str]:
    if not DATABASE.exists():
        return set()
    return {row["hunt_code"] for row in read_csv(DATABASE) if row.get("hunt_code")}


def read_crosswalk_current_codes() -> set[str]:
    if not CROSSWALK.exists():
        return set()
    return {row["current_hunt_code"] for row in read_csv(CROSSWALK) if row.get("current_hunt_code")}


def source_identity_key(row: dict[str, str], year: str | None = None) -> tuple[str, ...]:
    return (
        year if year is not None else row_year(row),
        row.get("hunt_code", ""),
        row.get("draw_pool", ""),
        row.get("residency", ""),
        row.get("points", ""),
        row.get("source_scope", ""),
        row.get("source_file", ""),
        row.get("record_type", ""),
        row.get("pdf_page", ""),
        row.get("source_row_identifier", ""),
    )


def build_source_audit(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[(row.get("source_file", ""), row_year(row))].append(row)

    audit_rows: list[dict[str, str]] = []
    for (source_file, year), group in sorted(grouped.items()):
        database_truth_counts = Counter(row.get("database_truth_match", "") for row in group)
        residency_counts = Counter(row.get("residency", "") for row in group)
        audit_rows.append(
            {
                "source_file": source_file,
                "year": year,
                "row_count": str(len(group)),
                "unique_hunt_codes": str(len({row.get("hunt_code", "") for row in group if row.get("hunt_code", "")})),
                "resident_rows": str(residency_counts.get("Resident", 0)),
                "nonresident_rows": str(residency_counts.get("Nonresident", 0)),
                "database_truth_yes_rows": str(database_truth_counts.get("YES", 0)),
                "database_truth_no_rows": str(database_truth_counts.get("NO", 0)),
                "database_truth_blank_rows": str(database_truth_counts.get("", 0)),
                "blank_hunt_code_rows": str(sum(1 for row in group if not row.get("hunt_code", ""))),
            }
        )
    return audit_rows


def build_summary(rows: list[dict[str, str]], source_audit_rows: list[dict[str, str]]) -> dict:
    database_codes = read_database_codes()
    crosswalk_codes = read_crosswalk_current_codes()

    year_counts: Counter[str] = Counter()
    model_target_year_counts: Counter[str] = Counter()
    residency_counts: Counter[str] = Counter()
    draw_method_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    database_truth_counts: Counter[str] = Counter()
    database_coverage_by_year: Counter[str] = Counter()
    blank_hunt_code_rows = 0
    invalid_year_rows = 0
    coarse_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    source_identity_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)

    for row in rows:
        year = row_year(row)
        year_counts[year] += 1
        parsed_year = safe_int(year)
        if parsed_year is None:
            invalid_year_rows += 1
        else:
            model_target_year_counts[str(parsed_year + 1)] += 1

        residency_counts[row.get("residency", "")] += 1
        draw_method_counts[row.get("draw_method", "")] += 1
        status_counts[row.get("status", "")] += 1
        database_truth_counts[row.get("database_truth_match", "")] += 1
        hunt_code = row.get("hunt_code", "")
        if not hunt_code:
            blank_hunt_code_rows += 1
        if hunt_code in database_codes:
            database_coverage_by_year[year] += 1
        coarse_key = (
            year,
            row.get("hunt_code", ""),
            row.get("draw_pool", ""),
            row.get("residency", ""),
            row.get("points", ""),
        )
        coarse_groups[coarse_key].append(row)
        source_identity_groups[source_identity_key(row, year)].append(row)

    coarse_key_collision_count = sum(len(group) - 1 for group in coarse_groups.values() if len(group) > 1)
    source_identity_collisions = [
        (key, group) for key, group in source_identity_groups.items() if len(group) > 1
    ]
    source_identity_collision_count = sum(len(group) - 1 for _, group in source_identity_collisions)
    source_identity_collision_examples = [
        {
            "year": key[0], "hunt_code": key[1], "draw_pool": key[2], "residency": key[3],
            "points": key[4], "source_scope": key[5], "source_file": key[6],
            "record_type": key[7], "pdf_page": key[8], "source_row_identifier": key[9], "row_count": len(group),
        }
        for key, group in source_identity_collisions[:10]
    ]

    blocker_codes = []
    if blank_hunt_code_rows:
        blocker_codes.append("BLANK_HUNT_CODES")
    if invalid_year_rows:
        blocker_codes.append("INVALID_DRAW_YEARS")
    if source_identity_collision_count:
        blocker_codes.append("UNRESOLVED_SOURCE_IDENTITY_DUPLICATES")

    summary = {
        "artifact": "draw_results_all_years_cumulative_truth",
        "source_long_csv": str(DRAW_LONG.relative_to(ROOT)).replace("\\", "/"),
        "normalized_long_rows": len(rows),
        "unique_draw_years": sorted(year for year in year_counts if year),
        "draw_year_counts": dict(sorted(year_counts.items())),
        "publish_year_counts": dict(sorted(year_counts.items())),
        "reported_hunt_year_inferred_counts": dict(sorted(year_counts.items())),
        "model_target_year_counts": dict(sorted(model_target_year_counts.items())),
        "unique_hunt_codes_all_years": len({row.get("hunt_code", "") for row in rows if row.get("hunt_code", "")}),
        "unique_sources": len({row.get("source_file", "") for row in rows if row.get("source_file", "")}),
        "source_audit_rows": len(source_audit_rows),
        "active_database_hunt_codes": len(database_codes),
        "active_database_coverage_by_draw_year": dict(sorted(database_coverage_by_year.items())),
        "crosswalk_current_code_count": len(crosswalk_codes),
        "crosswalk_current_codes_present_in_draw_rows": len(
            crosswalk_codes & {row.get("hunt_code", "") for row in rows if row.get("hunt_code", "")}
        ),
        "residency_counts": dict(sorted(residency_counts.items())),
        "draw_method_counts": dict(sorted(draw_method_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "database_truth_match_counts": dict(sorted(database_truth_counts.items())),
        "blank_hunt_code_rows": blank_hunt_code_rows,
        "invalid_year_rows": invalid_year_rows,
        "coarse_key_fields": COARSE_KEY_FIELDS,
        "coarse_key_collision_count": coarse_key_collision_count,
        "cross_scope_only_collision_count": coarse_key_collision_count - source_identity_collision_count,
        "source_identity_key_fields": SOURCE_IDENTITY_KEY_FIELDS,
        "source_identity_collision_group_count": len(source_identity_collisions),
        "source_identity_collision_count": source_identity_collision_count,
        "source_identity_collision_examples": source_identity_collision_examples,
        "blocker_count": len(blocker_codes),
        "blockers": blocker_codes,
        "outputs": {
            "long_csv": str(DRAW_LONG.relative_to(ROOT)).replace("\\", "/"),
            "source_audit_csv": str(SOURCE_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)).replace("\\", "/"),
            "summary_md": str(SUMMARY_MD.relative_to(ROOT)).replace("\\", "/"),
            "processed_source_audit_csv": str(PROCESSED_SOURCE_AUDIT.relative_to(ROOT)).replace("\\", "/"),
            "processed_summary_json": str(PROCESSED_SUMMARY_JSON.relative_to(ROOT)).replace("\\", "/"),
            "processed_summary_md": str(PROCESSED_SUMMARY_MD.relative_to(ROOT)).replace("\\", "/"),
            "source_identity_collisions_csv": str(SOURCE_IDENTITY_COLLISIONS.relative_to(ROOT)).replace("\\", "/"),
        },
        "guardrails": [
            "Draw year is treated as reported_hunt_year_inferred for historical draw-result rows.",
            "Model target year is draw/result year + 1 for predictive alignment summaries.",
            "Cross-scope records remain distinct official evidence and are not silently merged.",
            "This validation layer does not rewrite current hunt codes or probability math.",
        ],
    }
    return summary


def write_markdown(summary: dict) -> None:
    lines = [
        "# Draw Results All Years Cumulative Truth",
        "",
        "This validation layer finalizes the cumulative draw-results truth table without rewriting the runtime long CSV.",
        "",
        "## Validation",
        "",
        f"- Rows: {summary['normalized_long_rows']}",
        f"- Unique draw years: {', '.join(summary['unique_draw_years'])}",
        f"- Unique hunt codes: {summary['unique_hunt_codes_all_years']}",
        f"- Source audit rows: {summary['source_audit_rows']}",
        f"- Blank hunt-code rows: {summary['blank_hunt_code_rows']}",
        f"- Invalid year rows: {summary['invalid_year_rows']}",
        f"- Coarse-key collisions across all source scopes: {summary['coarse_key_collision_count']}",
        f"- Cross-scope-only collisions: {summary['cross_scope_only_collision_count']}",
        f"- Unresolved same-source identity collisions: {summary['source_identity_collision_count']}",
        f"- Blockers: {summary['blocker_count']}",
        "",
        "## Draw Year Counts",
        "",
    ]
    for year, count in summary["draw_year_counts"].items():
        lines.append(f"- {year}: {count}")
    lines.extend(["", "## Guardrails", ""])
    for guardrail in summary["guardrails"]:
        lines.append(f"- {guardrail}")
    content = "\n".join(lines) + "\n"
    SUMMARY_MD.write_text(content, encoding="utf-8")
    PROCESSED_SUMMARY_MD.write_text(content, encoding="utf-8")


def main() -> None:
    rows = read_csv(DRAW_LONG)
    source_audit_rows = build_source_audit(rows)
    summary = build_summary(rows, source_audit_rows)

    write_csv(SOURCE_AUDIT, source_audit_rows, SOURCE_AUDIT_FIELDS)
    write_csv(PROCESSED_SOURCE_AUDIT, source_audit_rows, SOURCE_AUDIT_FIELDS)
    collision_groups: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        collision_groups[source_identity_key(row)].append(row)
    collision_rows: list[dict[str, str]] = []
    for key, group in sorted(collision_groups.items()):
        if len(group) < 2:
            continue
        for row in group:
            collision_rows.append(
                {
                    "year": key[0], "hunt_code": key[1], "draw_pool": key[2], "residency": key[3],
                    "points": key[4], "source_scope": key[5], "source_file": key[6],
                    "record_type": key[7], "pdf_page": key[8], "source_row_identifier": key[9], "identity_group_row_count": str(len(group)),
                    "source_dataset": row.get("source_dataset", ""), "algorithm_status": row.get("algorithm_status", ""),
                    "eligible_applicants": row.get("eligible_applicants", ""), "total_permits": row.get("total_permits", ""),
                    "p_draw": row.get("p_draw", ""), "notes": row.get("notes", ""),
                }
            )
    collision_fields = [
        "year", "hunt_code", "draw_pool", "residency", "points", "source_scope", "source_file", "record_type",
        "pdf_page", "source_row_identifier", "identity_group_row_count", "source_dataset", "algorithm_status", "eligible_applicants", "total_permits", "p_draw", "notes",
    ]
    write_csv(SOURCE_IDENTITY_COLLISIONS, collision_rows, collision_fields)
    write_json(SUMMARY_JSON, summary)
    write_json(PROCESSED_SUMMARY_JSON, summary)
    write_markdown(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
