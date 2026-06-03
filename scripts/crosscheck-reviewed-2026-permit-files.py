from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PERMIT_DIR = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits"
MANIFEST = PERMIT_DIR / "2026 superseded permit fragments manifest.csv"
REMAINING = ROOT / "processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_hanumber_hunttable_database_rule.csv"

OUT_DIR = ROOT / "processed_data/audits/current_2026_reviewed_permit_file_crosscheck"
NORMALIZED = OUT_DIR / "reviewed_2026_permit_sources_normalized.csv"
BY_CODE = OUT_DIR / "reviewed_2026_permit_sources_by_hunt_code.csv"
CROSSCHECK = OUT_DIR / "reviewed_2026_permit_remaining_unresolved_crosscheck.csv"
SUPPORTED = OUT_DIR / "supported_by_reviewed_2026_permit_files.csv"
STRICT_RESOLVED = OUT_DIR / "strictly_resolved_by_reviewed_2026_permit_files.csv"
STILL_UNRESOLVED = OUT_DIR / "still_unresolved_after_reviewed_2026_permit_files.csv"
SUMMARY = OUT_DIR / "reviewed_2026_permit_file_crosscheck_summary.json"
REPORT = OUT_DIR / "reviewed_2026_permit_file_crosscheck.md"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


def permit_value(value: object) -> str:
    text = clean(value)
    for label in ["Res", "NonRes", "Total"]:
        match = re.search(rf"\b{label}:\s*([0-9,]+)", text, re.I)
        if match:
            return int_text(match.group(1))
    return int_text(text)


def triple(res: object, nr: object, total: object) -> tuple[str, str, str]:
    res_text = permit_value(res)
    nr_text = permit_value(nr)
    total_text = permit_value(total)
    if total_text in {"", "0"} and (res_text not in {"", "0"} or nr_text not in {"", "0"}):
        total_text = str(int(res_text or 0) + int(nr_text or 0))
    if (res_text, nr_text, total_text) in {("", "", ""), ("0", "0", "0"), ("0", "0", "")}:
        return "", "", ""
    if res_text == "0" and nr_text == "0" and total_text not in {"", "0"}:
        return "", "", total_text
    return res_text, nr_text, total_text


def has_value(values: tuple[str, str, str]) -> bool:
    return any(value not in {"", "0"} for value in values)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def superseded_files() -> set[str]:
    if not MANIFEST.exists():
        return set()
    return {row["file_name"] for row in read_csv(MANIFEST) if row.get("status")}


def source_role(path: Path, superseded: set[str]) -> str:
    name = path.name
    if name == MANIFEST.name:
        return "MANIFEST_NOT_PERMIT_ROWS"
    if name == "2026 reviewed permit truth master.csv":
        return "REVIEWED_MASTER"
    if name in superseded:
        return "SUPERSEDED_FRAGMENT_DO_NOT_USE_FOR_CANONICAL"
    if "reviewed" in name.lower():
        return "REVIEWED_FAMILY"
    return "UNREVIEWED_FRAGMENT"


def is_usable_role(role: str) -> bool:
    return role in {"REVIEWED_MASTER", "REVIEWED_FAMILY"}


def normalize_sources() -> list[dict[str, str]]:
    superseded = superseded_files()
    rows: list[dict[str, str]] = []
    for path in sorted(PERMIT_DIR.glob("*.csv")):
        role = source_role(path, superseded)
        if role == "MANIFEST_NOT_PERMIT_ROWS":
            continue
        for row_number, row in enumerate(read_csv(path), start=2):
            code = clean(row.get("hunt_code")).upper()
            if not re.fullmatch(r"[A-Z]{2}\d{4}", code):
                continue
            values = triple(row.get("permits_2026_res"), row.get("permits_2026_nr"), row.get("permits_2026_total"))
            rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": row.get("hunt_name", ""),
                    "species": row.get("species", ""),
                    "sex_type": row.get("sex_type", ""),
                    "weapon": row.get("weapon", ""),
                    "hunt_type": row.get("hunt_type", ""),
                    "season": row.get("season", ""),
                    "permits_2026_res": values[0],
                    "permits_2026_nr": values[1],
                    "permits_2026_total": values[2],
                    "has_permit_value": "true" if has_value(values) else "false",
                    "permit_count_status": row.get("permit_count_status", ""),
                    "hunt_code_mapping_status": row.get("hunt_code_mapping_status", ""),
                    "boundary_id": row.get("boundary_id", ""),
                    "boundary_id_mapping_status": row.get("boundary_id_mapping_status", ""),
                    "source_role": role,
                    "source_file": path.relative_to(ROOT).as_posix(),
                    "source_row_number": row.get("source_row_number") or str(row_number),
                }
            )
    return rows


def by_code_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row["hunt_code"]].append(row)
    out_rows = []
    for code, code_rows in sorted(grouped.items()):
        usable = [row for row in code_rows if is_usable_role(row["source_role"])]
        usable_values = [
            (row["permits_2026_res"], row["permits_2026_nr"], row["permits_2026_total"])
            for row in usable
            if row["has_permit_value"] == "true"
        ]
        value_counts = Counter(usable_values)
        if value_counts:
            consensus_value, consensus_count = value_counts.most_common(1)[0]
            unique_values = len(value_counts)
        else:
            consensus_value, consensus_count, unique_values = ("", "", ""), 0, 0
        out_rows.append(
            {
                "hunt_code": code,
                "hunt_name": next((row["hunt_name"] for row in usable or code_rows if row["hunt_name"]), ""),
                "species": next((row["species"] for row in usable or code_rows if row["species"]), ""),
                "usable_reviewed_source_count": str(len(usable)),
                "usable_reviewed_value_source_count": str(len(usable_values)),
                "usable_reviewed_unique_value_count": str(unique_values),
                "reviewed_consensus_res": consensus_value[0],
                "reviewed_consensus_nr": consensus_value[1],
                "reviewed_consensus_total": consensus_value[2],
                "reviewed_consensus_source_count": str(consensus_count),
                "reviewed_consensus_status": (
                    "NO_REVIEWED_VALUE"
                    if not value_counts
                    else "REVIEWED_CONSENSUS"
                    if unique_values == 1
                    else "REVIEWED_SOURCE_VALUE_CONFLICT"
                ),
                "all_reviewed_values": "|".join(f"{value[0]}/{value[1]}/{value[2]}:{count}" for value, count in sorted(value_counts.items())),
                "usable_source_files": "|".join(sorted({row["source_file"] for row in usable})),
                "all_source_roles": "|".join(sorted({row["source_role"] for row in code_rows})),
            }
        )
    return out_rows


def remaining_values(row: dict[str, str], prefix: str) -> tuple[str, str, str]:
    if prefix == "database":
        return (
            row.get("database_res_reference", ""),
            row.get("database_nr_reference", ""),
            row.get("database_total_reference", ""),
        )
    return (row.get(f"{prefix}_res", ""), row.get(f"{prefix}_nr", ""), row.get(f"{prefix}_total", ""))


def compare_status(row: dict[str, str], reviewed: dict[str, str] | None) -> tuple[str, str]:
    if not reviewed or reviewed["reviewed_consensus_status"] == "NO_REVIEWED_VALUE":
        return "NO_REVIEWED_PERMIT_VALUE", "Reviewed permit files do not provide a permit value for this code."
    if reviewed["reviewed_consensus_status"] == "REVIEWED_SOURCE_VALUE_CONFLICT":
        return "REVIEWED_SOURCE_VALUE_CONFLICT", "Reviewed permit source files disagree with each other."
    rv = (
        reviewed["reviewed_consensus_res"],
        reviewed["reviewed_consensus_nr"],
        reviewed["reviewed_consensus_total"],
    )
    matches = []
    conflicts = []
    for source in ["hanumber", "hunttable", "utahdraws", "buck_deer", "database"]:
        sv = remaining_values(row, source)
        if not has_value(sv):
            continue
        if sv == rv:
            matches.append(source.upper())
        elif sv[2] and rv[2] and sv[2] == rv[2]:
            matches.append(source.upper() + "_TOTAL")
        else:
            conflicts.append(source.upper())
    if row.get("remaining_unresolved_bucket") == "database_only_external_missing" and "DATABASE" in matches:
        return "RESOLVES_DATABASE_ONLY_EXTERNAL_MISSING", "Reviewed value matches existing DATABASE reference where external sources were blank."
    if row.get("remaining_unresolved_bucket") == "true_no_permit_value":
        return "RESOLVES_TRUE_NO_PERMIT_VALUE", "Reviewed value supplies a permit value where prior compared sources were blank."
    if conflicts and matches:
        return "SUPPORTS_REVIEWED_VALUE_WITH_REMAINING_CONFLICT", f"Reviewed value matches {', '.join(matches)} but conflicts with {', '.join(conflicts)}."
    if conflicts:
        return "REVIEWED_VALUE_CONFLICTS_WITH_EXISTING_SOURCES", f"Reviewed value conflicts with {', '.join(conflicts)}."
    if matches:
        return "SUPPORTS_EXISTING_VALUE", f"Reviewed value matches {', '.join(matches)}."
    return "REVIEWED_VALUE_ONLY", "Reviewed files provide the only current value in compared sources."


def main() -> int:
    normalized = normalize_sources()
    by_code = by_code_rows(normalized)
    by_code_map = {row["hunt_code"]: row for row in by_code}
    remaining = read_csv(REMAINING)
    cross_rows = []
    supported = []
    strict_resolved = []
    still_unresolved = []
    for row in remaining:
        reviewed = by_code_map.get(row["hunt_code"])
        status, note = compare_status(row, reviewed)
        out = dict(row)
        if reviewed:
            out.update({f"reviewed_{key}": value for key, value in reviewed.items() if key != "hunt_code"})
        else:
            out.update(
                {
                    "reviewed_hunt_name": "",
                    "reviewed_species": "",
                    "reviewed_usable_reviewed_source_count": "0",
                    "reviewed_usable_reviewed_value_source_count": "0",
                    "reviewed_usable_reviewed_unique_value_count": "0",
                    "reviewed_reviewed_consensus_res": "",
                    "reviewed_reviewed_consensus_nr": "",
                    "reviewed_reviewed_consensus_total": "",
                    "reviewed_reviewed_consensus_source_count": "0",
                    "reviewed_reviewed_consensus_status": "NO_REVIEWED_ROW",
                    "reviewed_all_reviewed_values": "",
                    "reviewed_usable_source_files": "",
                    "reviewed_all_source_roles": "",
                }
            )
        out["reviewed_permit_resolution_status"] = status
        out["reviewed_permit_resolution_note"] = note
        cross_rows.append(out)
        if status.startswith("RESOLVES_"):
            strict_resolved.append(out)
        if status.startswith("RESOLVES_") or status in {"SUPPORTS_EXISTING_VALUE", "SUPPORTS_REVIEWED_VALUE_WITH_REMAINING_CONFLICT", "REVIEWED_VALUE_ONLY"}:
            supported.append(out)
        still_unresolved.append(out)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(NORMALIZED, normalized)
    write_csv(BY_CODE, by_code)
    write_csv(CROSSCHECK, cross_rows)
    cross_fieldnames = list(cross_rows[0].keys()) if cross_rows else []
    write_csv(SUPPORTED, supported, cross_fieldnames)
    write_csv(STRICT_RESOLVED, strict_resolved, cross_fieldnames)
    write_csv(STILL_UNRESOLVED, still_unresolved)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_permit_directory": PERMIT_DIR.relative_to(ROOT).as_posix(),
        "remaining_unresolved_input": REMAINING.relative_to(ROOT).as_posix(),
        "row_counts": {
            "normalized_source_rows": len(normalized),
            "normalized_source_rows_with_values": sum(1 for row in normalized if row["has_permit_value"] == "true"),
            "by_code_rows": len(by_code),
            "remaining_unresolved_input_rows": len(remaining),
            "crosscheck_rows": len(cross_rows),
            "strictly_resolved_by_reviewed_files": len(strict_resolved),
            "supported_by_reviewed_files": len(supported),
            "still_unresolved_after_reviewed_files": len(still_unresolved),
        },
        "source_role_counts": dict(Counter(row["source_role"] for row in normalized)),
        "resolution_status_counts": dict(Counter(row["reviewed_permit_resolution_status"] for row in cross_rows)),
        "strictly_resolved_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in strict_resolved).items())),
        "supported_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in supported).items())),
        "still_unresolved_prefix_counts": dict(sorted(Counter(row["hunt_code"][:2] for row in still_unresolved).items())),
        "outputs": {
            "normalized_csv": NORMALIZED.relative_to(ROOT).as_posix(),
            "by_code_csv": BY_CODE.relative_to(ROOT).as_posix(),
            "crosscheck_csv": CROSSCHECK.relative_to(ROOT).as_posix(),
            "supported_csv": SUPPORTED.relative_to(ROOT).as_posix(),
            "strict_resolved_csv": STRICT_RESOLVED.relative_to(ROOT).as_posix(),
            "still_unresolved_csv": STILL_UNRESOLVED.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": REPORT.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "Superseded fragments are normalized for audit visibility but excluded from reviewed consensus.",
            "DATABASE.csv is not modified.",
            "Rows marked with reviewed source conflicts remain review-only.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def write_csv(path: Path, rows: list[dict[str, str]], fieldnames: list[str] | None = None) -> None:
    fieldnames = fieldnames or (list(rows[0].keys()) if rows else [])
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_report(summary: dict[str, object]) -> None:
    rows = summary["row_counts"]
    status_counts = summary["resolution_status_counts"]
    role_counts = summary["source_role_counts"]
    assert isinstance(rows, dict)
    assert isinstance(status_counts, dict)
    assert isinstance(role_counts, dict)
    lines = [
        "# Reviewed 2026 Permit File Crosscheck",
        "",
        "## Purpose",
        "",
        "This audit normalizes the local reviewed 2026 permit CSV files and compares them against the current remaining unresolved 2026 permit review set. It is audit-only and does not modify `DATABASE.csv`.",
        "",
        "## Key Counts",
        "",
        f"- Normalized source rows: `{rows['normalized_source_rows']}`",
        f"- Normalized source rows with permit values: `{rows['normalized_source_rows_with_values']}`",
        f"- Unique hunt codes in normalized table: `{rows['by_code_rows']}`",
        f"- Remaining unresolved input rows: `{rows['remaining_unresolved_input_rows']}`",
        f"- Rows strictly resolved by reviewed files: `{rows['strictly_resolved_by_reviewed_files']}`",
        f"- Rows supported by reviewed files but still requiring precedence review: `{rows['supported_by_reviewed_files']}`",
        f"- Rows still unresolved after reviewed file crosscheck: `{rows['still_unresolved_after_reviewed_files']}`",
        "",
        "## Source Role Counts",
        "",
    ]
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(role_counts.items()))
    lines.extend(["", "## Resolution Status Counts", ""])
    lines.extend(f"- `{key}`: `{value}`" for key, value in sorted(status_counts.items()))
    lines.extend(["", "## Outputs", ""])
    outputs = summary["outputs"]
    assert isinstance(outputs, dict)
    lines.extend(f"- `{value}`" for value in outputs.values())
    REPORT.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
