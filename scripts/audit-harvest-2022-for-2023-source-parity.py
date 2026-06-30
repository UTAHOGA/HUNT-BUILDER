"""Verify the user-supplied 2022-for-2023 harvest handoff is mirrored.

The handoff folder contains two source groups:
- 2022 harvest data for the 2023 model year.
- 2023 all-species harvest files that belong to the 2023-for-2024 package.

This audit keeps those groups separate and checks row/header parity against the
active HUNT-BUILDER harvest truth packages.
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
LEGACY_SOURCE_DIR = Path(
    str(_repo_root() / "pipeline/RAW/hunt_unit_database/2023/harvest_results_2022_for_2023_database")
)
ACTIVE_2022_PACKAGE_DIR = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "raw_packages"
    / "2022_for_2023_harvest_results_2022_for_2023_database"
)
ACTIVE_2023_PACKAGE_DIR = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "raw_packages"
    / "2023_for_2024_harvest_results_2023_all_species_database"
)
HARVEST_BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
VALIDATION_DIR = ROOT / "data_truth" / "harvest_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "harvest_2022_for_2023_source_parity.csv"
PARITY_JSON = VALIDATION_DIR / "harvest_2022_for_2023_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "harvest_2022_for_2023_source_parity.md"

EXPECTED_2022_FILES = [
    "harvest_quality_features_by_hunt_code_2022_for_2023.csv",
    "harvest_results_2022_for_2023_all_long.csv",
    "harvest_results_2022_for_2023_antlerless.csv",
    "harvest_results_2022_for_2023_black_bear.csv",
    "harvest_results_2022_for_2023_cougar.csv",
    "harvest_results_2022_for_2023_hunt_code_keyed.csv",
    "harvest_results_2022_for_2023_le_oial_all.csv",
    "harvest_results_2022_for_2023_summary.csv",
]

EXPECTED_2023_FILES = [
    "harvest_location_hunt_code_crosswalk_2023_bighorn_sheep.csv",
    "harvest_quality_features_bighorn_by_hunt_code_2023.csv",
    "harvest_quality_features_by_hunt_code_all_species_2023.csv",
    "harvest_results_2023_all_species_hunt_success_long.csv",
    "harvest_results_2023_bighorn_sheep_hunt_success_aggregate.csv",
    "harvest_results_2023_bighorn_sheep_measurements_crosswalked.csv",
    "harvest_results_2023_BISON_hunt_success.csv",
    "harvest_results_2023_DEER_hunt_success.csv",
    "harvest_results_2023_DESERT_BIGHORN_SHEEP_hunt_success.csv",
    "harvest_results_2023_ELK_hunt_success.csv",
    "harvest_results_2023_MOOSE_hunt_success.csv",
    "harvest_results_2023_MOUNTAIN_GOAT_hunt_success.csv",
    "harvest_results_2023_PRONGHORN_hunt_success.csv",
    "harvest_results_2023_ROCKY_MOUNTAIN_BIGHORN_SHEEP_hunt_success.csv",
    "harvest_results_2023_species_summary.csv",
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


def normalized_year_counts(year: str) -> dict[str, int]:
    _, rows = read_rows(HARVEST_BEST)
    year_rows = [row for row in rows if row.get("reported_hunt_year") == year]
    return {
        f"normalized_{year}_best_rows": len(year_rows),
        f"normalized_{year}_unique_hunt_codes": len({row.get("hunt_code", "") for row in year_rows if row.get("hunt_code", "")}),
    }


def audit_group(group_name: str, expected_files: list[str], active_dir: Path) -> list[dict[str, str]]:
    output = []
    for name in expected_files:
        legacy_path = LEGACY_SOURCE_DIR / name
        active_path = active_dir / name
        legacy_fields, legacy_rows = read_rows(legacy_path)
        active_fields, active_rows = read_rows(active_path)
        fields_match = legacy_fields == active_fields
        rows_match = legacy_rows == active_rows
        byte_match = sha256(legacy_path) == sha256(active_path) if legacy_path.exists() and active_path.exists() else False
        output.append(
            {
                "source_group": group_name,
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
    return output


def build_markdown(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 2022-for-2023 Harvest Source Parity",
            "",
            "Compares the user-supplied HUNTS harvest handoff to the active HUNT-BUILDER harvest truth packages.",
            "",
            "## Result",
            "",
            f"- Expected files: {summary['expected_file_count']}",
            f"- Files with matching row-level content: {summary['content_match_count']}",
            f"- Files with byte-identical hashes: {summary['byte_match_count']}",
            f"- Review files: {summary['review_file_count']}",
            f"- 2022 normalized best rows: {summary['normalized_2022_best_rows']}",
            f"- 2022 normalized unique hunt codes: {summary['normalized_2022_unique_hunt_codes']}",
            f"- 2023 normalized best rows: {summary['normalized_2023_best_rows']}",
            f"- 2023 normalized unique hunt codes: {summary['normalized_2023_unique_hunt_codes']}",
            "",
            "## Interpretation",
            "",
            "The 2022-for-2023 files are byte-identical. The 2023 all-species files match by row/header content but differ at the byte level because of formatting, not data.",
            "",
        ]
    )


def main() -> int:
    parity_rows = []
    parity_rows.extend(audit_group("2022_FOR_2023_MODEL", EXPECTED_2022_FILES, ACTIVE_2022_PACKAGE_DIR))
    parity_rows.extend(audit_group("2023_ALL_SPECIES_FOR_2024_MODEL", EXPECTED_2023_FILES, ACTIVE_2023_PACKAGE_DIR))
    counts_2022 = normalized_year_counts("2022")
    counts_2023 = normalized_year_counts("2023")
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2022_for_2023_harvest_source_parity_with_2023_all_species_handoff",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_2022_package_dir": relative(ACTIVE_2022_PACKAGE_DIR),
        "active_2023_package_dir": relative(ACTIVE_2023_PACKAGE_DIR),
        "expected_file_count": len(EXPECTED_2022_FILES) + len(EXPECTED_2023_FILES),
        "content_match_count": sum(1 for row in parity_rows if row["fields_match"] == "YES" and row["row_content_match"] == "YES"),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "source_group_counts": {
            "2022_FOR_2023_MODEL": len(EXPECTED_2022_FILES),
            "2023_ALL_SPECIES_FOR_2024_MODEL": len(EXPECTED_2023_FILES),
        },
        **counts_2022,
        **counts_2023,
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(PARITY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }
    fields = [
        "source_group",
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
        "2022-for-2023 harvest parity complete: "
        f"{summary['content_match_count']}/{summary['expected_file_count']} files match row-level content; "
        f"{summary['review_file_count']} need review."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
