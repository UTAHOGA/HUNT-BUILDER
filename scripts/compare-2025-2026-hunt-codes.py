#!/usr/bin/env python3
"""Compare canonical 2025 historical hunt codes to 2026 current hunt codes.

This is a read-only comparison. It uses canonical DATABASE.csv for the full
2025 historical permit universe and the current 2026 DWR Hunt Planner universe,
then enriches exact-code differences with the promoted current-to-historical
crosswalk where available.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
HUNTS_ROOT = Path(str(_repo_root()))

DATABASE = HUNTS_ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
CROSSWALK = ROOT / "processed_data/current_to_historical_hunt_code_crosswalk_2026.csv"

OUTPUT = ROOT / "processed_data/hunt_code_comparison_2025_to_2026.csv"
SUMMARY_JSON = ROOT / "processed_data/hunt_code_comparison_2025_to_2026_summary.json"
SUMMARY_MD = ROOT / "processed_data/hunt_code_comparison_2025_to_2026.md"
VALIDATION_JSON = ROOT / "data_truth/comparison_outputs/validation/hunt_code_comparison_2025_to_2026_summary.json"

TRIPLE_FIELDS = ("res", "nr", "total")

OUTPUT_FIELDS = [
    "hunt_code",
    "hunt_name",
    "species",
    "hunt_type",
    "weapon",
    "sex_type",
    "boundary_id",
    "in_2026_database_universe",
    "has_2025_historical_permits",
    "has_2026_current_permits",
    "comparison_status",
    "comparison_confidence",
    "permits_2025_res",
    "permits_2025_nr",
    "permits_2025_total",
    "permits_2025_source",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permits_2026_source",
    "permit_delta_total_exact_or_candidate",
    "permit_delta_basis",
    "mapped_2025_historical_codes",
    "mapped_2025_historical_totals",
    "mapped_2025_historical_total_sum_candidate",
    "crosswalk_status",
    "crosswalk_confidence",
    "crosswalk_method",
    "review_priority",
    "review_reason",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\ufeff", "")
    if text in {"-", "nan", "None"}:
        return ""
    return text


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def maybe_int(value: object) -> int | None:
    text = int_text(value)
    if text == "":
        return None
    try:
        return int(text)
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def triple(row: dict[str, str], prefix: str) -> tuple[str, str, str]:
    return tuple(int_text(row.get(f"{prefix}_{field}", "")) for field in TRIPLE_FIELDS)  # type: ignore[return-value]


def has_triple(row: dict[str, str], prefix: str) -> bool:
    return any(triple(row, prefix))


def split_codes(value: str) -> list[str]:
    return [part.strip().upper() for part in clean(value).split("|") if part.strip()]


def load_crosswalk() -> dict[str, dict[str, str]]:
    if not CROSSWALK.exists():
        return {}
    return {clean(row.get("current_hunt_code")).upper(): row for row in read_csv(CROSSWALK) if row.get("current_hunt_code")}


def mapped_2025_codes_for_current(
    current_code: str,
    crosswalk: dict[str, dict[str, str]],
    database_by_code: dict[str, dict[str, str]],
) -> list[str]:
    row = crosswalk.get(current_code, {})
    # Only the promoted historical_hunt_code field is allowed to drive continuity.
    # Candidate/name-match fields are review evidence and must not be promoted here.
    candidate_codes = split_codes(row.get("historical_hunt_code", ""))
    output: list[str] = []
    seen: set[str] = set()
    for code in candidate_codes:
        if code in seen:
            continue
        seen.add(code)
        db_row = database_by_code.get(code)
        if db_row and has_triple(db_row, "permits_2025"):
            output.append(code)
    return output


def mapped_2025_totals(codes: list[str], database_by_code: dict[str, dict[str, str]]) -> tuple[list[str], str]:
    totals: list[str] = []
    total_sum = 0
    any_total = False
    for code in codes:
        total = int_text(database_by_code.get(code, {}).get("permits_2025_total"))
        totals.append(f"{code}:{total}")
        number = maybe_int(total)
        if number is not None:
            total_sum += number
            any_total = True
    return totals, str(total_sum) if any_total else ""


def delta(left: str, right: str) -> str:
    left_int = maybe_int(left)
    right_int = maybe_int(right)
    if left_int is None or right_int is None:
        return ""
    return str(right_int - left_int)


def build_row(
    row: dict[str, str],
    crosswalk: dict[str, dict[str, str]],
    database_by_code: dict[str, dict[str, str]],
) -> dict[str, str]:
    code = clean(row.get("hunt_code")).upper()
    has_2025 = has_triple(row, "permits_2025")
    has_2026 = has_triple(row, "permits_2026")
    mapped_codes = mapped_2025_codes_for_current(code, crosswalk, database_by_code)
    mapped_totals, mapped_total_sum = mapped_2025_totals(mapped_codes, database_by_code)
    crosswalk_row = crosswalk.get(code, {})

    if has_2025 and has_2026:
        status = "EXACT_SAME_CODE_2025_AND_2026_PERMITTED"
        confidence = "HIGH"
        priority = "NONE"
        reason = "Same hunt code has source-lined 2025 permits and populated 2026 current permits."
        delta_value = delta(row.get("permits_2025_total", ""), row.get("permits_2026_total", ""))
        delta_basis = "EXACT_CODE"
    elif has_2025 and not has_2026:
        status = "HISTORICAL_2025_CODE_PRESENT_BUT_NO_2026_PERMIT_VALUE"
        confidence = "MEDIUM"
        priority = "HIGH"
        reason = "2025 historical code remains in current DATABASE but lacks populated 2026 permits."
        delta_value = ""
        delta_basis = "NOT_CALCULATED"
    elif not has_2025 and has_2026 and mapped_codes:
        status = "CURRENT_2026_CODE_WITH_MAPPED_2025_HISTORY"
        confidence = clean(crosswalk_row.get("mapping_confidence")) or "MEDIUM"
        priority = "MEDIUM"
        reason = "No exact 2025 permit value on current code, but promoted crosswalk maps it to 2025 history."
        delta_value = delta(mapped_total_sum, row.get("permits_2026_total", ""))
        delta_basis = "CROSSWALK_CANDIDATE_SUM"
    elif not has_2025 and has_2026:
        status = "CURRENT_2026_PERMIT_CODE_NO_2025_HISTORY"
        confidence = "MEDIUM"
        priority = "MEDIUM"
        reason = "Populated 2026 permit code has no exact 2025 permit value and no promoted 2025 code mapping."
        delta_value = ""
        delta_basis = "NOT_CALCULATED"
    else:
        status = "CURRENT_2026_REFERENCE_ONLY_NO_2025_OR_2026_PERMITS"
        confidence = "LOW"
        priority = "LOW"
        reason = "Code exists in current 2026 DATABASE but has no populated 2025 or 2026 permit values."
        delta_value = ""
        delta_basis = "NOT_CALCULATED"

    return {
        "hunt_code": code,
        "hunt_name": clean(row.get("hunt_name")),
        "species": clean(row.get("species")),
        "hunt_type": clean(row.get("hunt_type")),
        "weapon": clean(row.get("weapon")),
        "sex_type": clean(row.get("sex_type")),
        "boundary_id": clean(row.get("boundary_id")),
        "in_2026_database_universe": "YES",
        "has_2025_historical_permits": "YES" if has_2025 else "NO",
        "has_2026_current_permits": "YES" if has_2026 else "NO",
        "comparison_status": status,
        "comparison_confidence": confidence,
        "permits_2025_res": int_text(row.get("permits_2025_res")),
        "permits_2025_nr": int_text(row.get("permits_2025_nr")),
        "permits_2025_total": int_text(row.get("permits_2025_total")),
        "permits_2025_source": clean(row.get("permits_2025_source")),
        "permits_2026_res": int_text(row.get("permits_2026_res")),
        "permits_2026_nr": int_text(row.get("permits_2026_nr")),
        "permits_2026_total": int_text(row.get("permits_2026_total")),
        "permits_2026_source": clean(row.get("permits_2026_source")),
        "permit_delta_total_exact_or_candidate": delta_value,
        "permit_delta_basis": delta_basis,
        "mapped_2025_historical_codes": "|".join(mapped_codes),
        "mapped_2025_historical_totals": "|".join(mapped_totals),
        "mapped_2025_historical_total_sum_candidate": mapped_total_sum,
        "crosswalk_status": clean(crosswalk_row.get("crosswalk_status")),
        "crosswalk_confidence": clean(crosswalk_row.get("mapping_confidence")),
        "crosswalk_method": clean(crosswalk_row.get("mapping_method")),
        "review_priority": priority,
        "review_reason": reason,
    }


def build_comparison() -> tuple[list[dict[str, str]], dict]:
    database_rows = read_csv(DATABASE)
    database_by_code = {clean(row.get("hunt_code")).upper(): row for row in database_rows if row.get("hunt_code")}
    crosswalk = load_crosswalk()
    output_rows = [build_row(row, crosswalk, database_by_code) for row in database_rows]

    codes_2025 = {row["hunt_code"] for row in output_rows if row["has_2025_historical_permits"] == "YES"}
    codes_2026_permit = {row["hunt_code"] for row in output_rows if row["has_2026_current_permits"] == "YES"}
    codes_2026_all = {row["hunt_code"] for row in output_rows}
    status_counts = Counter(row["comparison_status"] for row in output_rows)
    priority_counts = Counter(row["review_priority"] for row in output_rows)

    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in output_rows:
        grouped[row["species"]].append(row)
    species_status: dict[str, dict[str, int]] = {}
    for species, rows in grouped.items():
        species_status[species] = dict(sorted(Counter(row["comparison_status"] for row in rows).items()))

    summary = {
        "artifact": "hunt_code_comparison_2025_to_2026",
        "database_file": str(DATABASE).replace("\\", "/"),
        "crosswalk_file": CROSSWALK.relative_to(ROOT).as_posix() if CROSSWALK.exists() else "",
        "database_2026_universe_count": len(codes_2026_all),
        "historical_2025_permit_code_count": len(codes_2025),
        "current_2026_populated_permit_code_count": len(codes_2026_permit),
        "exact_same_code_2025_and_2026_count": len(codes_2025 & codes_2026_permit),
        "historical_2025_codes_absent_from_2026_database_count": len(codes_2025 - codes_2026_all),
        "historical_2025_codes_without_2026_permit_count": len(codes_2025 - codes_2026_permit),
        "current_2026_populated_codes_without_exact_2025_count": len(codes_2026_permit - codes_2025),
        "current_2026_populated_codes_with_mapped_2025_history_count": status_counts[
            "CURRENT_2026_CODE_WITH_MAPPED_2025_HISTORY"
        ],
        "current_2026_populated_codes_no_2025_history_count": status_counts[
            "CURRENT_2026_PERMIT_CODE_NO_2025_HISTORY"
        ],
        "current_2026_reference_only_no_2025_or_2026_count": status_counts[
            "CURRENT_2026_REFERENCE_ONLY_NO_2025_OR_2026_PERMITS"
        ],
        "status_counts": dict(sorted(status_counts.items())),
        "review_priority_counts": dict(sorted(priority_counts.items())),
        "species_status_counts": dict(sorted(species_status.items())),
        "guardrail": (
            "This is a read-only hunt-code comparison. Source-lined 2025 historical permit codes are canonical "
            "passed-year truth, and populated 2026 permit codes are current DWR Hunt Planner truth. Exact-code gaps "
            "must be checked against the promoted current-to-historical crosswalk before being treated as truly new. "
            "Only promoted historical_hunt_code mappings are used for continuity; candidate/name-match fields remain "
            "review evidence."
        ),
        "outputs": {
            "csv": OUTPUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix(),
            "summary_md": SUMMARY_MD.relative_to(ROOT).as_posix(),
            "validation_json": VALIDATION_JSON.relative_to(ROOT).as_posix(),
        },
    }
    return output_rows, summary


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(summary: dict) -> None:
    lines = [
        "# Hunt Code Comparison 2025 To 2026",
        "",
        "Read-only comparison of source-lined 2025 historical permit codes to current 2026 DATABASE hunt codes.",
        "",
        "## Summary",
        "",
        f"- 2026 DATABASE universe: `{summary['database_2026_universe_count']}`",
        f"- 2025 historical permit codes: `{summary['historical_2025_permit_code_count']}`",
        f"- 2026 populated permit codes: `{summary['current_2026_populated_permit_code_count']}`",
        f"- Exact same-code continuity: `{summary['exact_same_code_2025_and_2026_count']}`",
        f"- 2025 codes absent from 2026 DATABASE: `{summary['historical_2025_codes_absent_from_2026_database_count']}`",
        f"- 2025 codes without populated 2026 permits: `{summary['historical_2025_codes_without_2026_permit_count']}`",
        f"- 2026 populated codes without exact 2025 code: `{summary['current_2026_populated_codes_without_exact_2025_count']}`",
        f"- 2026 populated codes with mapped 2025 history: `{summary['current_2026_populated_codes_with_mapped_2025_history_count']}`",
        f"- 2026 populated codes with no mapped 2025 history: `{summary['current_2026_populated_codes_no_2025_history_count']}`",
        f"- 2026 reference-only rows without 2025/2026 permits: `{summary['current_2026_reference_only_no_2025_or_2026_count']}`",
        "",
        "## Guardrail",
        "",
        summary["guardrail"],
        "",
        "## Status Counts",
        "",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Review Priority Counts", ""])
    for priority, count in summary["review_priority_counts"].items():
        lines.append(f"- `{priority}`: `{count}`")
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows, summary = build_comparison()
    write_csv(OUTPUT, rows)
    write_json(SUMMARY_JSON, summary)
    write_json(VALIDATION_JSON, summary)
    write_markdown(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
