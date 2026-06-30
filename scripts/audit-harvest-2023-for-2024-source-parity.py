"""Anchor 2023 harvest source files for the 2024 model year.

This audit compares the user-supplied HUNTS 2024 Harvest Results folder to the
active HUNT-BUILDER harvest truth packages. It keeps harvest source parity
separate from draw/permit comparison, then records the existing same-year 2023
harvest-vs-draw alignment as review evidence.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
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
    str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/csv/Harvest Results")
)
ACTIVE_RAW_PACKAGES = ROOT / "data_truth" / "harvest_results_truth" / "raw_packages"
HARVEST_BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
SAME_YEAR_CSV = ROOT / "data_truth" / "comparison_outputs" / "validation" / "harvest_draw_same_year_alignment_2026.csv"
EXISTING_2023_COMPARISON_JSON = ROOT / "processed_data" / "complete_2023_harvest_vs_draw_comparison.json"
VALIDATION_DIR = ROOT / "data_truth" / "harvest_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "harvest_2023_for_2024_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "harvest_2023_for_2024_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "harvest_2023_for_2024_source_parity.md"

BASELINE_2023_FILES = {
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
}


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def source_group(name: str) -> str:
    if name in BASELINE_2023_FILES:
        return "2023_FOR_2024_ALL_SPECIES_BASELINE"
    if name.startswith("turkey_"):
        return "2023_24_TURKEY_FOR_2025_SEPARATE_PACKAGE"
    if "uploaded_reports" in name:
        return "2023_UPLOADED_REPORTS_SUPPLEMENT"
    if name == "2024_antlerless_hr.csv":
        return "2024_ANTLERLESS_HR_REVIEW"
    if "all_sources" in name:
        return "2023_ALL_SOURCES_SUPPLEMENT"
    if "bighorn" in name.lower():
        return "2023_BIGHORN_SUPPLEMENT"
    return "2023_SUPPLEMENTAL_HARVEST_EVIDENCE"


def best_active_match(source_path: Path, active_matches: list[Path]) -> dict[str, str]:
    source_fields, source_rows = read_rows(source_path)
    source_hash = sha256(source_path)
    best = {
        "active_package_path": "",
        "active_match_count": str(len(active_matches)),
        "active_rows": "",
        "active_columns": "",
        "fields_match": "NO",
        "row_content_match": "NO",
        "byte_hash_match": "NO",
        "active_sha256": "",
    }
    for active_path in active_matches:
        active_fields, active_rows = read_rows(active_path)
        fields_match = source_fields == active_fields
        rows_match = source_rows == active_rows
        byte_match = source_hash == sha256(active_path)
        candidate = {
            "active_package_path": relative(active_path),
            "active_match_count": str(len(active_matches)),
            "active_rows": str(len(active_rows)),
            "active_columns": str(len(active_fields)),
            "fields_match": "YES" if fields_match else "NO",
            "row_content_match": "YES" if rows_match else "NO",
            "byte_hash_match": "YES" if byte_match else "NO",
            "active_sha256": sha256(active_path),
        }
        if rows_match:
            return candidate
        if fields_match and best["fields_match"] != "YES":
            best = candidate
        elif not best["active_package_path"]:
            best = candidate
    return best


def build_active_index() -> dict[str, list[Path]]:
    index: dict[str, list[Path]] = {}
    for path in ACTIVE_RAW_PACKAGES.rglob("*.csv"):
        index.setdefault(path.name, []).append(path)
    return index


def normalized_year_counts(year: str) -> dict[str, int]:
    _, rows = read_rows(HARVEST_BEST)
    year_rows = [row for row in rows if row.get("reported_hunt_year") == year]
    return {
        f"normalized_{year}_best_rows": len(year_rows),
        f"normalized_{year}_unique_hunt_codes": len({row.get("hunt_code", "") for row in year_rows if row.get("hunt_code", "")}),
    }


def same_year_2023_summary() -> dict[str, str]:
    _, rows = read_rows(SAME_YEAR_CSV)
    for row in rows:
        if row.get("year") == "2023":
            return row
    return {}


def existing_complete_comparison_summary() -> dict[str, object]:
    if not EXISTING_2023_COMPARISON_JSON.exists():
        return {}
    payload = json.loads(EXISTING_2023_COMPARISON_JSON.read_text(encoding="utf-8"))
    return payload.get("summary", {})


def build_markdown(summary: dict[str, object]) -> str:
    same_year = summary["same_year_2023"]
    existing = summary["existing_complete_2023_harvest_vs_draw_comparison"]
    lines = [
        "# 2023 Harvest Source Parity For 2024 Modeling",
        "",
        "Compares the user-supplied 2023 harvest CSV package to active HUNT-BUILDER harvest truth packages.",
        "",
        "## Source Parity Result",
        "",
        f"- Source CSVs checked: {summary['source_file_count']}",
        f"- Active package row-content matches: {summary['content_match_count']}",
        f"- Active package byte-identical matches: {summary['byte_match_count']}",
        f"- Missing active package copies recorded for review: {summary['missing_active_package_copy_count']}",
        f"- Baseline 2023 package files matched by row content: {summary['baseline_content_match_count']} / {summary['baseline_source_file_count']}",
        f"- Turkey package files matched by row content: {summary['turkey_content_match_count']} / {summary['turkey_source_file_count']}",
        f"- Normalized 2023 harvest rows: {summary['normalized_2023_best_rows']}",
        f"- Normalized 2023 unique hunt codes: {summary['normalized_2023_unique_hunt_codes']}",
        "",
        "## 2023 Harvest vs Draw Same-Year Check",
        "",
        f"- 2023 harvest native hunt codes: {same_year.get('harvest_native_unique_hunt_codes', '')}",
        f"- 2023 draw native hunt codes: {same_year.get('draw_native_unique_hunt_codes', '')}",
        f"- Same-code overlap: {same_year.get('same_year_overlap_hunt_codes', '')}",
        f"- Harvest-only codes: {same_year.get('harvest_only_hunt_codes', '')}",
        f"- Draw-only codes: {same_year.get('draw_only_hunt_codes', '')}",
        "",
        "## Existing 2023 Comparison Artifact",
        "",
        f"- Complete comparison harvest codes: {existing.get('complete_harvest_hunt_codes', '')}",
        f"- Complete comparison draw odds codes: {existing.get('draw_odds_hunt_codes', '')}",
        f"- Both harvest and draw: {existing.get('both_harvest_and_draw', '')}",
        f"- Harvest-only: {existing.get('harvest_only', '')}",
        f"- Draw-only: {existing.get('draw_only', '')}",
        "",
        "## Interpretation",
        "",
        "- The promoted 2023 all-species baseline files are already mirrored in active harvest truth packages by row/header content.",
        "- The uploaded, all-sources, antlerless, and other supplemental CSVs are inventoried as review evidence until promoted intentionally.",
        "- The turkey files belong to the separate 2023-24 turkey package for 2025 modeling and are not folded into 2023 big-game harvest counts here.",
        "- Same-year comparison remains evidence only: harvest quality features and draw/permit results stay in separate source domains.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    source_files = sorted(LEGACY_SOURCE_DIR.glob("*.csv"))
    active_index = build_active_index()
    parity_rows: list[dict[str, str]] = []
    for source_path in source_files:
        source_fields, source_rows = read_rows(source_path)
        active_matches = active_index.get(source_path.name, [])
        match = best_active_match(source_path, active_matches)
        if not active_matches:
            status = "REVIEW_MISSING_ACTIVE_PACKAGE_COPY"
        elif match["row_content_match"] == "YES":
            status = "PASS_ACTIVE_PACKAGE_CONTENT_MATCH"
        elif match["fields_match"] == "YES":
            status = "REVIEW_ACTIVE_PACKAGE_FIELDS_ONLY"
        else:
            status = "REVIEW_ACTIVE_PACKAGE_MISMATCH"

        parity_rows.append(
            {
                "source_group": source_group(source_path.name),
                "file_name": source_path.name,
                "legacy_source_path": str(source_path),
                "active_package_path": match["active_package_path"],
                "active_match_count": match["active_match_count"],
                "legacy_exists": "YES" if source_path.exists() else "NO",
                "active_exists": "YES" if active_matches else "NO",
                "legacy_rows": str(len(source_rows)),
                "active_rows": match["active_rows"],
                "legacy_columns": str(len(source_fields)),
                "active_columns": match["active_columns"],
                "fields_match": match["fields_match"],
                "row_content_match": match["row_content_match"],
                "byte_hash_match": match["byte_hash_match"],
                "legacy_sha256": sha256(source_path),
                "active_sha256": match["active_sha256"],
                "status": status,
                "promotion_note": "PROMOTED_BASELINE_OR_TURKEY_PACKAGE" if match["row_content_match"] == "YES" else "REVIEW_EVIDENCE_NOT_PROMOTED",
            }
        )

    counts = Counter(row["source_group"] for row in parity_rows)
    normalized_counts = normalized_year_counts("2023")
    same_year = same_year_2023_summary()
    existing_comparison = existing_complete_comparison_summary()
    baseline_rows = [row for row in parity_rows if row["source_group"] == "2023_FOR_2024_ALL_SPECIES_BASELINE"]
    turkey_rows = [row for row in parity_rows if row["source_group"] == "2023_24_TURKEY_FOR_2025_SEPARATE_PACKAGE"]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_harvest_for_2024_source_parity_and_2023_draw_permit_comparison",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_raw_packages_dir": relative(ACTIVE_RAW_PACKAGES),
        "source_file_count": len(parity_rows),
        "content_match_count": sum(1 for row in parity_rows if row["row_content_match"] == "YES"),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_active_package_copy_count": sum(1 for row in parity_rows if row["status"] == "REVIEW_MISSING_ACTIVE_PACKAGE_COPY"),
        "review_file_count": sum(1 for row in parity_rows if row["status"].startswith("REVIEW")),
        "baseline_source_file_count": len(baseline_rows),
        "baseline_content_match_count": sum(1 for row in baseline_rows if row["row_content_match"] == "YES"),
        "turkey_source_file_count": len(turkey_rows),
        "turkey_content_match_count": sum(1 for row in turkey_rows if row["row_content_match"] == "YES"),
        "source_group_counts": dict(sorted(counts.items())),
        **normalized_counts,
        "same_year_2023": same_year,
        "existing_complete_2023_harvest_vs_draw_comparison": existing_comparison,
        "guardrails": [
            "Do not compare 2023 native harvest-code counts to the 2026 active hunt-code universe as a completeness score.",
            "Do not promote supplemental uploaded/all-sources files until they are intentionally reviewed.",
            "Do not use harvest permit counts as draw quotas or direct draw probability inputs.",
            "Keep 2023 harvest and 2023 draw data in separate source domains until a later feature-combine step.",
        ],
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(SUMMARY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }

    fields = [
        "source_group",
        "file_name",
        "legacy_source_path",
        "active_package_path",
        "active_match_count",
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
        "promotion_note",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "2023-for-2024 harvest source parity complete: "
        f"{summary['content_match_count']}/{summary['source_file_count']} files match active packages; "
        f"{summary['missing_active_package_copy_count']} supplemental files need promotion review."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
