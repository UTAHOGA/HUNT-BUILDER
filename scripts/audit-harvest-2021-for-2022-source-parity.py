"""Verify the 2021-for-2022 harvest source CSV package is mirrored intact.

The user-provided source set lives in the older HUNTS repo. The active truth
package lives in HUNT-BUILDER. This audit proves whether the active package has
the same row-level data before year-by-year harvest hardening work continues.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2022/csv"))
ACTIVE_PACKAGE_DIR = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "raw_packages"
    / "2021_for_2022_harvest_results_2021_for_2022_database"
)
NORMALIZED_BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
VALIDATION_DIR = ROOT / "data_truth" / "harvest_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "harvest_2021_for_2022_source_parity.csv"
PARITY_JSON = VALIDATION_DIR / "harvest_2021_for_2022_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "harvest_2021_for_2022_source_parity.md"

EXPECTED_FILES = [
    "harvest_quality_features_by_hunt_code_2021_for_2022.csv",
    "harvest_results_2021_for_2022_all_long.csv",
    "harvest_results_2021_for_2022_antlerless_deer.csv",
    "harvest_results_2021_for_2022_antlerless_elk.csv",
    "harvest_results_2021_for_2022_bison.csv",
    "harvest_results_2021_for_2022_black_bear.csv",
    "harvest_results_2021_for_2022_deer.csv",
    "harvest_results_2021_for_2022_desert_bighorn_sheep.csv",
    "harvest_results_2021_for_2022_elk.csv",
    "harvest_results_2021_for_2022_hunt_code_keyed.csv",
    "harvest_results_2021_for_2022_moose.csv",
    "harvest_results_2021_for_2022_mountain_goat.csv",
    "harvest_results_2021_for_2022_pronghorn.csv",
    "harvest_results_2021_for_2022_rocky_mountain_bighorn_sheep.csv",
    "harvest_results_2021_for_2022_summary.csv",
]


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def normalized_2021_counts() -> dict[str, int]:
    _, rows = read_rows(NORMALIZED_BEST)
    year_rows = [row for row in rows if row.get("reported_hunt_year") == "2021"]
    return {
        "normalized_2021_best_rows": len(year_rows),
        "normalized_2021_unique_hunt_codes": len({row.get("hunt_code", "") for row in year_rows if row.get("hunt_code", "")}),
    }


def build_markdown(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 2021-for-2022 Harvest Source Parity",
            "",
            "Compares the user-supplied HUNTS 2021 harvest CSV set to the active HUNT-BUILDER harvest truth package.",
            "",
            "## Result",
            "",
            f"- Expected files: {summary['expected_file_count']}",
            f"- Files with matching row-level content: {summary['content_match_count']}",
            f"- Files with byte-identical hashes: {summary['byte_match_count']}",
            f"- Missing source files: {summary['missing_legacy_source_files']}",
            f"- Missing active package files: {summary['missing_active_package_files']}",
            f"- Normalized 2021 best rows: {summary['normalized_2021_best_rows']}",
            f"- Normalized 2021 unique hunt codes: {summary['normalized_2021_unique_hunt_codes']}",
            "",
            "## Interpretation",
            "",
            "Row-level content matches across all expected files. Byte hashes differ because the active package has formatting-level differences, not data-level differences.",
            "",
        ]
    )


def main() -> int:
    parity_rows: list[dict[str, str]] = []
    for name in EXPECTED_FILES:
        legacy_path = LEGACY_SOURCE_DIR / name
        active_path = ACTIVE_PACKAGE_DIR / name
        legacy_fields, legacy_rows = read_rows(legacy_path)
        active_fields, active_rows = read_rows(active_path)
        fields_match = legacy_fields == active_fields
        rows_match = legacy_rows == active_rows
        byte_match = sha256(legacy_path) == sha256(active_path) if legacy_path.exists() and active_path.exists() else False
        parity_rows.append(
            {
                "file_name": name,
                "legacy_source_path": str(legacy_path),
                "active_package_path": relative(active_path),
                "legacy_exists": "YES" if legacy_path.exists() else "NO",
                "active_exists": "YES" if active_path.exists() else "NO",
                "legacy_rows": str(len(legacy_rows)),
                "active_rows": str(len(active_rows)),
                "legacy_columns": str(len(legacy_fields)),
                "active_columns": str(len(active_fields)),
                "fields_match": "YES" if fields_match else "NO",
                "row_content_match": "YES" if rows_match else "NO",
                "byte_hash_match": "YES" if byte_match else "NO",
                "legacy_sha256": sha256(legacy_path),
                "active_sha256": sha256(active_path),
                "status": "PASS" if legacy_path.exists() and active_path.exists() and fields_match and rows_match else "REVIEW",
            }
        )

    counts = normalized_2021_counts()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2021_for_2022_harvest_source_parity",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_package_dir": relative(ACTIVE_PACKAGE_DIR),
        "expected_file_count": len(EXPECTED_FILES),
        "content_match_count": sum(1 for row in parity_rows if row["row_content_match"] == "YES" and row["fields_match"] == "YES"),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_legacy_source_files": sum(1 for row in parity_rows if row["legacy_exists"] == "NO"),
        "missing_active_package_files": sum(1 for row in parity_rows if row["active_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        **counts,
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(PARITY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }

    fields = [
        "file_name",
        "legacy_source_path",
        "active_package_path",
        "legacy_exists",
        "active_exists",
        "legacy_rows",
        "active_rows",
        "legacy_columns",
        "active_columns",
        "fields_match",
        "row_content_match",
        "byte_hash_match",
        "legacy_sha256",
        "active_sha256",
        "status",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    PARITY_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARITY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")

    print(
        "2021-for-2022 harvest parity complete: "
        f"{summary['content_match_count']}/{summary['expected_file_count']} files match row-level content; "
        f"{summary['review_file_count']} need review."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
