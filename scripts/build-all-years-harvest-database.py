"""Build cumulative harvest truth databases from available yearly harvest packages."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah.quality.harvest_identity import (
    hunt_name_compatible,
    normalize_code,
    normalize_species,
    resolve_identity_match,
    species_family,
)


OUT_TRUTH = ROOT / "data_truth" / "harvest_results_truth" / "normalized"
OUT_PROCESSED = ROOT / "processed_data"
OUT_MODEL = ROOT / "data_model" / "harvest_quality"
OUT_OVERLAY = ROOT / "data_model" / "permit_overlays"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
HARVEST_ROOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database"
SOURCE_BUNDLE_ROOT = ROOT / "data_truth" / "harvest_results_truth" / "source_package_bundles"
MODEL_SOURCE_BUNDLE_ROOT = ROOT / "data_model" / "harvest_quality" / "source_package_bundles"
DWR_2025_DASHBOARD_SNAPSHOT = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "sources"
    / "dwr_2025_dashboard_snapshot_2026-09-19"
)
DWR_2025_DASHBOARD_MANIFEST = DWR_2025_DASHBOARD_SNAPSHOT / "manifest.json"
DWR_HISTORY_2017_2021 = (
    ROOT
    / "data_truth"
    / "harvest_results_truth"
    / "sources"
    / "dwr_official_harvest_history_2017_2021_normalized.csv"
)
AGE_DATABASE = OUT_MODEL / "harvest_average_age_global_merge_database.csv"


NORMALIZED_FIELDS = [
    "reported_hunt_year",
    "model_target_year",
    "hunt_code",
    "species",
    "sex_type",
    "hunt_name",
    "hunt_type",
    "weapon",
    "permits",
    "hunters_afield",
    "harvest_total",
    "harvest_male",
    "harvest_female",
    "harvest_young",
    "harvest_unknown",
    "percent_success",
    "average_days",
    "hunter_satisfaction",
    "average_age",
    "average_age_3yr_reported",
    "average_age_3yr_local_computed",
    "average_age_3yr_local_computed_status",
    "hunt_planner_current_age_3yr_average",
    "hunt_planner_current_age_source",
    "average_age_source_file",
    "average_age_source_page",
    "average_age_source_table_title",
    "average_age_crosswalk_confidence",
    "average_age_mapping_status",
    "male_harvest",
    "female_harvest",
    "harvest_objective",
    "trophy_left_points",
    "trophy_right_points",
    "trophy_antler_width",
    "trophy_left_length",
    "trophy_right_length",
    "trophy_left_circumference",
    "trophy_right_circumference",
    "survey_context_source_file",
    "survey_context_source_container",
    "survey_context_source_member",
    "survey_context_status",
    "source_file",
    "source_page",
    "source_container",
    "source_member",
    "source_kind",
    "source_priority",
    "source_status",
    "parse_status",
    "do_not_use_for_permit_quota",
    "do_not_use_directly_for_p_draw",
    "trend_feature_eligible",
    "data_quality_flags",
    "recommended_use",
]

OPTIONAL_NORMALIZED_FIELDS = {
    "average_age_3yr_local_computed",
    "average_age_3yr_local_computed_status",
    "hunt_planner_current_age_3yr_average",
    "hunt_planner_current_age_source",
    "trophy_left_points",
    "trophy_right_points",
    "trophy_antler_width",
    "trophy_left_length",
    "trophy_right_length",
    "trophy_left_circumference",
    "trophy_right_circumference",
    "survey_context_source_file",
    "survey_context_source_container",
    "survey_context_source_member",
    "survey_context_status",
}


def read_csv_rows_from_text(text: str) -> tuple[list[dict[str, str]], list[str]]:
    handle = io.StringIO(text)
    reader = csv.DictReader(handle)
    return list(reader), reader.fieldnames or []


def read_csv_file(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), reader.fieldnames or []


def read_preserved_normalized_long() -> list[dict[str, str]]:
    """Use the checked-in comprehensive normalized history when raw bundles are partial.

    Large raw/extracted harvest assets are optionally hydrated. The checked-in model
    history is therefore the reproducible local fallback and must be loaded before
    this builder overwrites its generated copy.
    """

    path = OUT_MODEL / "harvest_results_all_years_long.csv"
    if path.exists():
        rows, _ = read_csv_file(path)
        if len(rows) >= 50_000:
            return rows
    try:
        result = subprocess.run(
            ["git", "show", "HEAD:data_model/harvest_quality/harvest_results_all_years_long.csv"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    rows, _ = read_csv_rows_from_text(result.stdout.decode("utf-8-sig"))
    return rows if len(rows) >= 50_000 else []


def read_checked_in_csv(relative_path: str) -> list[dict[str, str]]:
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{relative_path}"],
            cwd=ROOT,
            check=True,
            capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return []
    rows, _ = read_csv_rows_from_text(result.stdout.decode("utf-8-sig"))
    return rows


def read_preserved_best_history() -> list[dict[str, str]]:
    path = OUT_MODEL / "harvest_quality_features_all_years_by_hunt_code.csv"
    if path.exists():
        rows, _ = read_csv_file(path)
        if len(rows) >= 5_500:
            return rows
    return read_checked_in_csv("data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv")


def read_database_codes() -> set[str]:
    if not DATABASE.exists():
        return set()
    rows, _ = read_csv_file(DATABASE)
    return {row["hunt_code"].strip() for row in rows if row.get("hunt_code", "").strip()}


def read_database_rows() -> dict[str, dict[str, str]]:
    if not DATABASE.exists():
        return {}
    rows, _ = read_csv_file(DATABASE)
    return {row["hunt_code"].strip(): row for row in rows if row.get("hunt_code", "").strip()}


def zip_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def harvest_zip_candidates() -> list[Path]:
    candidates = []
    for search_root in [HARVEST_ROOT, SOURCE_BUNDLE_ROOT, MODEL_SOURCE_BUNDLE_ROOT]:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*.zip"):
            name = path.name.lower()
            if "harvest" in name and ("database" in name or "turkey_harvest" in name or "supplement" in name):
                candidates.append(path)
    # De-dupe duplicate ZIP copies by SHA, preferring the path with an explicit year folder.
    by_sha: dict[str, Path] = {}
    for path in sorted(candidates, key=lambda p: (len(p.parts), str(p))):
        digest = zip_sha(path)
        current = by_sha.get(digest)
        if current is None or "\\20" in str(path) or "/20" in str(path):
            by_sha[digest] = path
    return sorted(by_sha.values())


def normalize_antlerless_hr(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        raw_rows = list(csv.reader(handle))
    header_index = None
    for index, row in enumerate(raw_rows):
        if len(row) >= 9 and row[0].strip() == "Species" and row[1].strip() == "Hunt #":
            header_index = index
            break
    if header_index is None:
        return []
    rows: list[dict[str, str]] = []
    for raw in raw_rows[header_index + 1 :]:
        if len(raw) < 9 or not raw[1].strip():
            continue
        rows.append(
            {
                "reported_hunt_year": "2023",
                "model_target_year": "2024",
                "species": raw[0].strip(),
                "hunt_code": raw[1].strip(),
                "hunt_name": raw[2].strip(),
                "weapon": raw[3].strip(),
                "permits": raw[4].strip(),
                "hunters_afield": raw[5].strip(),
                "harvest_total": raw[6].strip(),
                "percent_success": raw[7].strip(),
                "average_days": raw[8].strip(),
                "source_file": path.name,
                "source_kind": "positional_normalized_antlerless",
                "parse_status": "POSITIONAL_HEADER_NORMALIZED",
                "do_not_use_for_permit_quota": "True",
                "do_not_use_directly_for_p_draw": "True",
            }
        )
    return rows


def candidate_csv_members() -> list[tuple[str, Path | None, str | None, str, int]]:
    """Return candidates as (container, filesystem_path, zip_member, source_kind, priority)."""
    candidates: list[tuple[str, Path | None, str | None, str, int]] = []

    # Expanded 2023 uploaded/all-source files are the richest 2023 source and should outrank the older ZIP.
    expanded_dir = HARVEST_ROOT / "2024" / "csv" / "Harvest Results"
    for name, kind, priority in [
        ("harvest_results_2023_hunt_code_keyed_all_sources.csv", "expanded_2023_keyed_all_sources", 100),
        ("harvest_quality_features_by_hunt_code_2023_uploaded_reports.csv", "expanded_2023_quality_uploaded", 95),
        ("harvest_results_2023_uploaded_reports_all_long.csv", "expanded_2023_uploaded_long", 90),
        ("2024_antlerless_hr.csv", "expanded_2023_antlerless_positional", 85),
        ("turkey_hunt_code_keyed_2024_for_2025.csv", "turkey_2024_keyed", 80),
        ("turkey_quality_features_2023_24_for_2025.csv", "turkey_2023_24_quality", 75),
        ("turkey_harvest_results_2023_24_for_2025_all_long.csv", "turkey_2023_24_long", 70),
    ]:
        path = expanded_dir / name
        if path.exists():
            candidates.append((str(path.relative_to(ROOT)), path, None, kind, priority))

    standalone_antlerless = HARVEST_ROOT / "2024" / "csv" / "2024_antlerless_hr.csv"
    if standalone_antlerless.exists():
        candidates.append(
            (
                str(standalone_antlerless.relative_to(ROOT)),
                standalone_antlerless,
                None,
                "expanded_2023_antlerless_positional",
                84,
            )
        )

    # Extracted 2024/2025 keyed files, if present, are easier to audit than ZIP members.
    for rel, kind, priority in [
        (
            "2025/csv/harvest data/harvest_results_2024_for_2025_hunt_code_keyed.csv",
            "extracted_2024_keyed",
            100,
        ),
        (
            "2025/csv/harvest data/harvest_quality_features_by_hunt_code_2024_for_2025.csv",
            "extracted_2024_quality",
            95,
        ),
        (
            "2025/csv/harvest data/harvest_results_2025_for_2026_hunt_code_keyed.csv",
            "extracted_2025_keyed",
            100,
        ),
        (
            "2025/csv/harvest data/harvest_quality_features_by_hunt_code_2025_for_2026.csv",
            "extracted_2025_quality",
            95,
        ),
    ]:
        path = HARVEST_ROOT / rel
        if path.exists():
            candidates.append((str(path.relative_to(ROOT)), path, None, kind, priority))

    # ZIP members cover 2021, 2022, older 2023, 2024, 2025, and turkey packages.
    for zip_path in harvest_zip_candidates():
        with ZipFile(zip_path) as archive:
            for info in archive.infolist():
                name = info.filename
                lower = name.lower()
                if not lower.endswith(".csv"):
                    continue
                if "summary" in lower or "source_inventory" in lower:
                    continue
                if "hunt_code_keyed" in lower:
                    priority = 80
                    kind = "zip_keyed"
                elif "quality_features" in lower:
                    priority = 75
                    kind = "zip_quality"
                elif "all_long" in lower:
                    priority = 60
                    kind = "zip_long"
                else:
                    priority = 45
                    kind = "zip_species_or_supplement"
                candidates.append((str(zip_path.relative_to(ROOT)), None, name, kind, priority))
    return candidates


def read_candidate(container: str, path: Path | None, member: str | None) -> tuple[list[dict[str, str]], list[str]]:
    if path is not None:
        if path.name.lower() == "2024_antlerless_hr.csv":
            rows = normalize_antlerless_hr(path)
            return rows, list(rows[0].keys()) if rows else []
        return read_csv_file(path)
    assert member is not None
    zip_path = ROOT / container
    with ZipFile(zip_path) as archive:
        text = archive.read(member).decode("utf-8-sig")
    return read_csv_rows_from_text(text)


def first(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "")
        if str(value).strip():
            return str(value).strip()
    return ""


def truthy_flag(value: str, default: str = "True") -> str:
    text = str(value or "").strip()
    if not text:
        return default
    return "True" if text.lower() in {"true", "yes", "1", "y"} else "False" if text.lower() in {"false", "no", "0", "n"} else text


def infer_year(value: str) -> str:
    value = str(value or "").strip()
    if value and value.replace(".", "", 1).isdigit():
        return str(int(float(value)))
    return value


def normalize_row(
    row: dict[str, str], container: str, member: str | None, source_kind: str, priority: int
) -> dict[str, str] | None:
    hunt_code = first(row, "hunt_code", "Hunt #", "hunt_number", "selected_hunt_code")
    if not hunt_code:
        return None
    reported_year = infer_year(first(row, "reported_hunt_year", "harvest_quality_year"))
    model_year = infer_year(first(row, "model_target_year"))
    if reported_year and not model_year:
        model_year = str(int(reported_year) + 1)
    if not reported_year and model_year:
        reported_year = str(int(model_year) - 1)
    if not reported_year:
        return None

    normalized = {
        "reported_hunt_year": reported_year,
        "model_target_year": model_year,
        "hunt_code": hunt_code,
        "species": first(row, "species", "matched_species"),
        "sex_type": first(row, "sex_type"),
        "hunt_name": first(row, "hunt_name", "matched_hunt_name"),
        "hunt_type": first(row, "hunt_type", "source_family", "harvest_family", "report_family"),
        "weapon": first(row, "weapon"),
        "permits": first(row, "permits", "permits_or_permits_sold", "total_permits", "quota"),
        "hunters_afield": first(row, "hunters_afield", "harvest_hunters", "hunters_afield_or_total_hunters", "total_hunters"),
        "harvest_total": first(row, "harvest_total", "harvest", "total_harvest"),
        "harvest_male": first(row, "harvest_male", "male_harvest"),
        "harvest_female": first(row, "harvest_female", "female_harvest"),
        "harvest_young": first(row, "harvest_young"),
        "harvest_unknown": first(row, "unknown_harvest"),
        "percent_success": first(row, "percent_success", "harvest_success_percent"),
        "average_days": first(row, "average_days", "average_days_hunted", "harvest_average_days", "mean_days_afield"),
        "hunter_satisfaction": first(row, "hunter_satisfaction", "harvest_satisfaction"),
        "average_age": first(row, "average_age", "age_of_sheep", "age_of_sheep_decimal"),
        "average_age_3yr_reported": first(row, "average_age_3yr_reported", "average_harvest_age_3yr"),
        "average_age_3yr_local_computed": first(row, "average_age_3yr_local_computed"),
        "average_age_3yr_local_computed_status": first(row, "average_age_3yr_local_computed_status"),
        "hunt_planner_current_age_3yr_average": first(row, "hunt_planner_current_age_3yr_average"),
        "hunt_planner_current_age_source": first(row, "hunt_planner_current_age_source"),
        "average_age_source_file": first(row, "average_age_source_file", "age_source_file"),
        "average_age_source_page": first(row, "average_age_source_page", "age_source_page"),
        "average_age_source_table_title": first(
            row, "average_age_source_table_title", "age_source_table_title"
        ),
        "average_age_crosswalk_confidence": first(
            row, "average_age_crosswalk_confidence", "crosswalk_confidence"
        ),
        "average_age_mapping_status": first(row, "average_age_mapping_status", "age_mapping_status"),
        "male_harvest": first(row, "male_harvest"),
        "female_harvest": first(row, "female_harvest"),
        "harvest_objective": first(row, "harvest_objective"),
        "trophy_left_points": first(row, "trophy_left_points"),
        "trophy_right_points": first(row, "trophy_right_points"),
        "trophy_antler_width": first(row, "trophy_antler_width"),
        "trophy_left_length": first(row, "trophy_left_length"),
        "trophy_right_length": first(row, "trophy_right_length"),
        "trophy_left_circumference": first(row, "trophy_left_circumference"),
        "trophy_right_circumference": first(row, "trophy_right_circumference"),
        "survey_context_source_file": first(row, "survey_context_source_file"),
        "survey_context_source_container": first(row, "survey_context_source_container"),
        "survey_context_source_member": first(row, "survey_context_source_member"),
        "survey_context_status": first(row, "survey_context_status"),
        "source_file": first(row, "source_file") or (member or Path(container).name),
        "source_page": first(row, "source_page", "source_page_id"),
        "source_container": container,
        "source_member": member or "",
        "source_kind": source_kind,
        "source_priority": str(priority),
        "source_status": first(row, "source_status"),
        "parse_status": first(row, "parse_status"),
        "do_not_use_for_permit_quota": truthy_flag(first(row, "do_not_use_for_permit_quota")),
        "do_not_use_directly_for_p_draw": truthy_flag(
            first(row, "do_not_use_directly_for_p_draw", "do_not_use_for_p_draw_directly")
        ),
        "trend_feature_eligible": first(row, "trend_feature_eligible"),
        "data_quality_flags": first(row, "data_quality_flags"),
        "recommended_use": first(row, "recommended_use"),
    }
    return normalized


def row_score(row: dict[str, str]) -> tuple[int, int, int]:
    priority = int(row.get("source_priority") or 0)
    filled = sum(1 for field in ["permits", "hunters_afield", "harvest_total", "percent_success", "average_days"] if row.get(field))
    has_quality = 1 if row.get("percent_success") or row.get("average_days") or row.get("hunter_satisfaction") else 0
    return (priority, filled, has_quality)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dashboard_snapshot_row(
    raw: dict[str, str], species: str, dashboard_family: str, source_file: Path, source_url: str
) -> dict[str, str]:
    row = {field: "" for field in NORMALIZED_FIELDS}
    row.update(
        {
            "reported_hunt_year": infer_year(first(raw, "Year")),
            "model_target_year": "2026",
            "hunt_code": normalize_code(first(raw, "Hunt #")),
            "species": species,
            "sex_type": first(raw, "Sex"),
            "hunt_name": first(raw, "Name"),
            "hunt_type": first(raw, "Type"),
            "weapon": first(raw, "Weapon"),
            "permits": first(raw, "Permits"),
            "hunters_afield": first(raw, "Hunters"),
            "harvest_total": first(raw, "Harvest"),
            "harvest_male": first(raw, "Males"),
            "harvest_female": first(raw, "Females"),
            "male_harvest": first(raw, "Males"),
            "female_harvest": first(raw, "Females"),
            # Preserve DWR's exported value. It is not always a recomputation of
            # the displayed Harvest and Hunters cells.
            "percent_success": first(raw, "Success"),
            "trophy_left_points": first(raw, "Left Pts", "Left pts"),
            "trophy_right_points": first(raw, "Right Pts", "Right pts"),
            "trophy_antler_width": first(raw, "Antler Width") if dashboard_family == "antlers" else "",
            "trophy_left_length": first(raw, "Left length") if dashboard_family == "horns" else "",
            "trophy_right_length": first(raw, "Right length") if dashboard_family == "horns" else "",
            "trophy_left_circumference": first(raw, "Left circumference", "Left circumfrence")
            if dashboard_family == "horns"
            else "",
            "trophy_right_circumference": first(raw, "Right circumference", "Right circumfrence")
            if dashboard_family == "horns"
            else "",
            "source_file": source_file.name,
            "source_page": source_url,
            "source_container": str(DWR_2025_DASHBOARD_SNAPSHOT.relative_to(ROOT)),
            "source_member": source_file.name,
            "source_kind": "official_dashboard_current_snapshot",
            "source_priority": "120",
            "source_status": "official_dashboard_current_not_standalone_final_pdf",
            "parse_status": "EXACT_DWR_DASHBOARD_EXPORT",
            "do_not_use_for_permit_quota": "True",
            "do_not_use_directly_for_p_draw": "True",
            "trend_feature_eligible": "True",
            "data_quality_flags": "OFFICIAL_DWR_DASHBOARD|HUNT_CODE_KEYED|BIG_GAME_HARVEST|EXACT_EXPORT",
            "recommended_use": "harvest quality, demand-signal, and backcheck features only; do not use as permit quota or direct draw probability",
        }
    )
    return row


def _read_dashboard_snapshot() -> tuple[list[dict[str, str]], dict[str, object]]:
    manifest = json.loads(DWR_2025_DASHBOARD_MANIFEST.read_text(encoding="utf-8"))
    source_url = str(manifest["source_page"])
    current_rows: list[dict[str, str]] = []
    validated_files: list[dict[str, object]] = []
    for entry in manifest["files"]:
        path = DWR_2025_DASHBOARD_SNAPSHOT / str(entry["file"])
        if _sha256(path) != entry["sha256"]:
            raise RuntimeError(f"DWR dashboard source hash differs: {path.relative_to(ROOT)}")
        if path.stat().st_size != int(entry["bytes"]):
            raise RuntimeError(f"DWR dashboard source byte count differs: {path.relative_to(ROOT)}")
        rows, headers = read_csv_file(path)
        if len(rows) != int(entry["rows"]):
            raise RuntimeError(f"DWR dashboard source row count differs: {path.relative_to(ROOT)}")
        required = {
            "Year",
            "Hunt #",
            "Name",
            "Type",
            "Weapon",
            "Sex",
            "Permits",
            "Hunters",
            "Harvest",
            "Males",
            "Females",
            "Success",
        }
        if not required.issubset(headers):
            raise RuntimeError(f"DWR dashboard source headers differ: {path.relative_to(ROOT)}")
        rows_2025 = [row for row in rows if infer_year(row.get("Year", "")) == "2025"]
        if len(rows_2025) != int(entry["rows_2025"]):
            raise RuntimeError(f"DWR dashboard 2025 row count differs: {path.relative_to(ROOT)}")
        current_rows.extend(
            _dashboard_snapshot_row(
                raw,
                str(entry["species"]),
                str(entry["dashboard_family"]),
                path,
                source_url,
            )
            for raw in rows_2025
        )
        validated_files.append(
            {
                "file": str(entry["file"]),
                "sha256": str(entry["sha256"]),
                "rows": len(rows),
                "rows_2025": len(rows_2025),
            }
        )
    return current_rows, {
        "source_url": source_url,
        "dashboard_accessed_date": manifest["dashboard_accessed_date"],
        "snapshot_status": manifest["status"],
        "validated_files": validated_files,
        "expected_rows": int(manifest["expected_2025_rows"]),
        "expected_species_counts": {
            str(key): int(value) for key, value in manifest["expected_2025_species_counts"].items()
        },
    }


def reconcile_current_2025_dashboard(
    all_rows: list[dict[str, str]],
    database_rows: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    current_rows, snapshot = _read_dashboard_snapshot()
    baseline_member = "harvest_results_2025_for_2026_hunt_code_keyed.csv"
    baseline_source_rows = [
        row
        for row in all_rows
        if row.get("reported_hunt_year") == "2025"
        and Path(row.get("source_member", "")).name == baseline_member
    ]
    baseline_by_identity: dict[tuple[str, ...], dict[str, str]] = {}
    for row in baseline_source_rows:
        key = tuple(
            row.get(field, "")
            for field in (
                "species",
                "hunt_code",
                "hunt_name",
                "hunt_type",
                "weapon",
                "sex_type",
                "permits",
                "hunters_afield",
                "harvest_total",
                "percent_success",
                "average_days",
                "hunter_satisfaction",
            )
        )
        baseline_by_identity.setdefault(key, row)
    baseline_candidates = list(baseline_by_identity.values())
    baseline_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in baseline_candidates:
        baseline_by_code[normalize_code(row.get("hunt_code"))].append(row)
    database_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in database_rows.values():
        database_by_code[normalize_code(row.get("hunt_code"))].append(row)

    survey_match_count = 0
    survey_unmatched_codes: list[str] = []
    planner_age_match_count = 0
    for row in current_rows:
        code = normalize_code(row.get("hunt_code"))
        survey_match = resolve_identity_match(row, baseline_by_code.get(code, []))
        if survey_match.row is not None:
            source = survey_match.row
            row["average_days"] = str(source.get("average_days", ""))
            row["hunter_satisfaction"] = str(source.get("hunter_satisfaction", ""))
            row["survey_context_source_file"] = str(source.get("source_file", ""))
            row["survey_context_source_container"] = str(source.get("source_container", ""))
            row["survey_context_source_member"] = str(source.get("source_member", ""))
            row["survey_context_status"] = "PRELIMINARY_SURVEY_CONTEXT_RETAINED_EXACT_IDENTITY"
            row["data_quality_flags"] += "|PRELIMINARY_DAYS_SATISFACTION_RETAINED"
            survey_match_count += 1
        else:
            survey_unmatched_codes.append(code)

        planner_match = resolve_identity_match(row, database_by_code.get(code, []))
        if planner_match.row is not None and planner_match.row.get("current_age_3yr_average", ""):
            row["hunt_planner_current_age_3yr_average"] = str(
                planner_match.row.get("current_age_3yr_average", "")
            )
            row["hunt_planner_current_age_source"] = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
            planner_age_match_count += 1

    all_rows.extend(dict(row) for row in current_rows)

    species_counts = Counter(row["species"] for row in current_rows)
    expected_counts = Counter(snapshot["expected_species_counts"])
    if species_counts != expected_counts:
        raise RuntimeError(f"2025 DWR dashboard species counts differ: {dict(species_counts)}")
    if len(current_rows) != int(snapshot["expected_rows"]):
        raise RuntimeError(
            f"Expected {snapshot['expected_rows']} current 2025 dashboard rows, found {len(current_rows)}"
        )
    current_rows.sort(
        key=lambda row: (
            normalize_species(row.get("species")),
            normalize_code(row.get("hunt_code")),
            row.get("hunt_name", ""),
            row.get("weapon", ""),
        )
    )
    return current_rows, {
        "source_url": snapshot["source_url"],
        "dashboard_accessed_date": snapshot["dashboard_accessed_date"],
        "snapshot_status": snapshot["snapshot_status"],
        "source_files": snapshot["validated_files"],
        "baseline_preliminary_rows": len(baseline_candidates),
        "survey_context_exact_identity_matches": survey_match_count,
        "survey_context_unmatched_rows": len(survey_unmatched_codes),
        "survey_context_unmatched_hunt_codes": sorted(set(survey_unmatched_codes)),
        "hunt_planner_current_age_matches": planner_age_match_count,
        "current_rows": len(current_rows),
        "species_counts": dict(sorted(species_counts.items())),
    }


def reconcile_best_history(
    preserved_best_rows: list[dict[str, str]],
    current_2025_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    """Overlay current dashboard identities without collapsing shared hunt codes."""

    dashboard_species = {species_family(row.get("species")) for row in current_2025_rows}
    rows = []
    for row in preserved_best_rows:
        is_replaced_2025_big_game = (
            row.get("reported_hunt_year") == "2025"
            and species_family(row.get("species")) in dashboard_species
        )
        if not is_replaced_2025_big_game:
            rows.append(dict(row))
    rows.extend(dict(row) for row in current_2025_rows)
    rows.sort(
        key=lambda row: (
            row.get("reported_hunt_year", ""),
            normalize_code(row.get("hunt_code")),
            normalize_species(row.get("species")),
            row.get("hunt_name", ""),
            row.get("weapon", ""),
        )
    )
    return rows


def read_history_2017_2021_repairs() -> list[dict[str, str]]:
    if not DWR_HISTORY_2017_2021.exists():
        raise FileNotFoundError(
            "Missing normalized 2017-2021 DWR harvest repair source. "
            "Run: python scripts/extract-dwr-harvest-history-2017-2021.py"
        )
    rows, headers = read_csv_file(DWR_HISTORY_2017_2021)
    missing = sorted((set(NORMALIZED_FIELDS) - OPTIONAL_NORMALIZED_FIELDS) - set(headers))
    if missing:
        raise RuntimeError(f"2017-2021 DWR harvest repair source is missing columns: {missing}")
    expected_years = {str(year) for year in range(2017, 2022)}
    actual_years = {row.get("reported_hunt_year", "") for row in rows}
    if actual_years != expected_years:
        raise RuntimeError(f"2017-2021 DWR harvest repair years differ: {sorted(actual_years)}")
    return [{field: row.get(field, "") for field in NORMALIZED_FIELDS} for row in rows]


def merge_history_repairs_into_best(
    preserved_best_rows: list[dict[str, str]],
    repair_rows: list[dict[str, str]],
) -> list[dict[str, str]]:
    repair_years = {str(year) for year in range(2017, 2022)}
    preserved_by_year_code: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in preserved_best_rows:
        if row.get("reported_hunt_year") in repair_years:
            preserved_by_year_code[
                (row.get("reported_hunt_year", ""), normalize_code(row.get("hunt_code")))
            ].append(row)

    output = [dict(row) for row in preserved_best_rows if row.get("reported_hunt_year") not in repair_years]
    for repair in repair_rows:
        row = dict(repair)
        candidates = preserved_by_year_code.get(
            (row.get("reported_hunt_year", ""), normalize_code(row.get("hunt_code"))),
            [],
        )
        compatible = [
            candidate
            for candidate in candidates
            if normalize_species(candidate.get("species")) == normalize_species(row.get("species"))
            and (
                not candidate.get("hunt_name")
                or not row.get("hunt_name")
                or hunt_name_compatible(candidate.get("hunt_name"), row.get("hunt_name"))
            )
        ]
        if row.get("reported_hunt_year") == "2021" and not compatible:
            raise RuntimeError(
                f"No compatible preserved 2021 harvest identity for {row.get('hunt_code')} {row.get('hunt_name')}"
            )
        for field in (
            "average_age",
            "harvest_young",
            "harvest_unknown",
            "male_harvest",
            "female_harvest",
            "harvest_objective",
        ):
            if row.get(field):
                continue
            values = {candidate.get(field, "") for candidate in compatible if candidate.get(field, "")}
            if len(values) == 1:
                row[field] = next(iter(values))
        output.append(row)

    output.sort(
        key=lambda row: (
            row.get("reported_hunt_year", ""),
            normalize_code(row.get("hunt_code")),
            normalize_species(row.get("species")),
            row.get("hunt_name", ""),
            row.get("weapon", ""),
        )
    )
    return output


def read_age_database() -> list[dict[str, str]]:
    if not AGE_DATABASE.exists():
        raise FileNotFoundError(f"Missing official age merge database: {AGE_DATABASE.relative_to(ROOT)}")
    rows, headers = read_csv_file(AGE_DATABASE)
    required = {
        "reported_hunt_year",
        "hunt_code",
        "species",
        "average_harvest_age",
        "average_harvest_age_3yr",
        "age_source_file",
        "age_source_page",
        "age_source_table_title",
        "crosswalk_confidence",
        "age_mapping_status",
    }
    missing = sorted(required - set(headers))
    if missing:
        raise RuntimeError(f"Official age merge database is missing columns: {missing}")
    return rows


def merge_age_database(
    rows: list[dict[str, str]],
    age_rows: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Overlay official age fields by year, hunt code, and compatible species only."""

    age_by_identity: dict[tuple[str, str, str], dict[str, str]] = {}
    for age in age_rows:
        key = (
            age.get("reported_hunt_year", ""),
            normalize_code(age.get("hunt_code")),
            species_family(age.get("species")),
        )
        if not all(key):
            continue
        if key in age_by_identity:
            raise RuntimeError(f"Duplicate official age identity: {key}")
        age_by_identity[key] = age

    matched_source_keys: set[tuple[str, str, str]] = set()
    matched_output_rows = 0
    for source in rows:
        key = (
            source.get("reported_hunt_year", ""),
            normalize_code(source.get("hunt_code")),
            species_family(source.get("species")),
        )
        age = age_by_identity.get(key)
        if not age:
            continue
        source["average_age"] = age.get("average_harvest_age", "")
        source["average_age_3yr_reported"] = age.get("average_harvest_age_3yr", "")
        source["average_age_source_file"] = age.get("age_source_file", "")
        source["average_age_source_page"] = age.get("age_source_page", "")
        source["average_age_source_table_title"] = age.get("age_source_table_title", "")
        source["average_age_crosswalk_confidence"] = age.get("crosswalk_confidence", "")
        source["average_age_mapping_status"] = age.get("age_mapping_status", "")
        matched_source_keys.add(key)
        matched_output_rows += 1

    return rows, {
        "source_rows": len(age_rows),
        "matched_source_identity_rows": len(matched_source_keys),
        "unmatched_source_identity_rows": len(age_by_identity) - len(matched_source_keys),
        "matched_output_rows": matched_output_rows,
        "annual_age_nonblank": sum(bool(row.get("average_harvest_age", "")) for row in age_rows),
        "reported_3yr_age_nonblank": sum(bool(row.get("average_harvest_age_3yr", "")) for row in age_rows),
    }


def compute_local_three_year_age(rows: list[dict[str, str]]) -> dict[str, int]:
    """Compute a distinct local rolling age measure from three annual DWR ages.

    This never replaces the DWR-reported three-year value and never reads the
    Hunt Planner current-age field. A value is emitted only when the same exact
    hunt code and compatible species family have one unambiguous annual age in
    each of the current and prior two reported hunt years.
    """

    annual_values: dict[tuple[str, str, int], set[float]] = defaultdict(set)
    for row in rows:
        text = str(row.get("average_age", "")).strip()
        year_text = str(row.get("reported_hunt_year", "")).strip()
        if not text or not year_text.isdigit():
            continue
        try:
            value = float(text)
        except ValueError:
            continue
        key = (normalize_code(row.get("hunt_code")), species_family(row.get("species")), int(year_text))
        annual_values[key].add(value)

    populated = ambiguous = 0
    for row in rows:
        row["average_age_3yr_local_computed"] = ""
        row["average_age_3yr_local_computed_status"] = ""
        year_text = str(row.get("reported_hunt_year", "")).strip()
        if not year_text.isdigit():
            continue
        code = normalize_code(row.get("hunt_code"))
        family = species_family(row.get("species"))
        values: list[float] = []
        has_ambiguity = False
        for year in range(int(year_text) - 2, int(year_text) + 1):
            candidates = annual_values.get((code, family, year), set())
            if len(candidates) != 1:
                has_ambiguity = has_ambiguity or len(candidates) > 1
                values = []
                break
            values.append(next(iter(candidates)))
        if values:
            mean = sum(values) / 3
            row["average_age_3yr_local_computed"] = f"{mean:.2f}".rstrip("0").rstrip(".")
            row["average_age_3yr_local_computed_status"] = "LOCAL_MEAN_OF_THREE_ANNUAL_DWR_AGES"
            populated += 1
        elif has_ambiguity:
            row["average_age_3yr_local_computed_status"] = "AMBIGUOUS_ANNUAL_AGE_VALUES_WITHHELD"
            ambiguous += 1
    return {"populated_rows": populated, "ambiguous_rows": ambiguous}


def special_permit_overlay_class(row: dict[str, str], database_row: dict[str, str] | None = None) -> str:
    text = " ".join(
        [
            row.get("hunt_code", ""),
            row.get("hunt_name", ""),
            row.get("hunt_type", ""),
            row.get("source_file", ""),
            row.get("source_kind", ""),
            (database_row or {}).get("hunt_name", ""),
            (database_row or {}).get("hunt_type", ""),
            (database_row or {}).get("season", ""),
        ]
    ).lower()
    if "expo" in text:
        return "EXPO"
    if "conservation" in text:
        return "CONSERVATION"
    if "sportsman" in text or "sportsmen" in text:
        return "SPORTSMAN"
    if "cwmu" in text:
        return "CWMU"
    return ""


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    database_rows = read_database_rows()
    active_codes = set(database_rows)
    source_audit: list[dict[str, object]] = []
    all_rows: list[dict[str, str]] = []

    preserved_rows = [
        row
        for row in read_preserved_normalized_long()
        if row.get("source_kind")
        not in {"official_dashboard_current_delta", "official_dashboard_current_snapshot"}
    ]
    if preserved_rows:
        all_rows.extend(preserved_rows)
        codes = {row["hunt_code"] for row in preserved_rows}
        years = sorted({row["reported_hunt_year"] for row in preserved_rows})
        source_audit.append(
            {
                "container": str((OUT_MODEL / "harvest_results_all_years_long.csv").relative_to(ROOT)),
                "member": "",
                "source_kind": "preserved_comprehensive_normalized_history",
                "source_priority": 100,
                "raw_rows": len(preserved_rows),
                "normalized_rows": len(preserved_rows),
                "unique_hunt_codes": len(codes),
                "active_database_codes": len(codes & active_codes),
                "reported_hunt_years": "|".join(years),
                "header_count": len(NORMALIZED_FIELDS),
            }
        )
    else:
        for container, path, member, source_kind, priority in candidate_csv_members():
            rows, headers = read_candidate(container, path, member)
            normalized_rows = []
            for row in rows:
                normalized = normalize_row(row, container, member, source_kind, priority)
                if normalized:
                    normalized_rows.append(normalized)
            all_rows.extend(normalized_rows)
            codes = {row["hunt_code"] for row in normalized_rows}
            years = sorted({row["reported_hunt_year"] for row in normalized_rows})
            source_audit.append(
                {
                    "container": container,
                    "member": member or "",
                    "source_kind": source_kind,
                    "source_priority": priority,
                    "raw_rows": len(rows),
                    "normalized_rows": len(normalized_rows),
                    "unique_hunt_codes": len(codes),
                    "active_database_codes": len(codes & active_codes),
                    "reported_hunt_years": "|".join(years),
                    "header_count": len(headers),
                }
            )

    history_repairs = read_history_2017_2021_repairs()
    history_repair_kinds = {
        "official_dwr_harvest_pdf_hunt_code_aggregate",
        "official_dwr_2021_package_mapping_repair",
    }
    all_rows = [row for row in all_rows if row.get("source_kind") not in history_repair_kinds]
    all_rows.extend(dict(row) for row in history_repairs)
    history_codes = {row["hunt_code"] for row in history_repairs}
    source_audit.append(
        {
            "container": str(DWR_HISTORY_2017_2021.relative_to(ROOT)),
            "member": "",
            "source_kind": "official_dwr_history_2017_2021_repair",
            "source_priority": 115,
            "raw_rows": len(history_repairs),
            "normalized_rows": len(history_repairs),
            "unique_hunt_codes": len(history_codes),
            "active_database_codes": len(history_codes & active_codes),
            "reported_hunt_years": "2017|2018|2019|2020|2021",
            "header_count": len(NORMALIZED_FIELDS),
        }
    )

    current_2025_rows, current_2025_summary = reconcile_current_2025_dashboard(all_rows, database_rows)
    source_audit.append(
        {
            "container": str(DWR_2025_DASHBOARD_SNAPSHOT.relative_to(ROOT)),
            "member": "",
            "source_kind": "official_dashboard_current_snapshot",
            "source_priority": 120,
            "raw_rows": current_2025_summary["current_rows"],
            "normalized_rows": current_2025_summary["current_rows"],
            "unique_hunt_codes": len({row["hunt_code"] for row in current_2025_rows}),
            "active_database_codes": len({row["hunt_code"] for row in current_2025_rows} & active_codes),
            "reported_hunt_years": "2025",
            "header_count": len(NORMALIZED_FIELDS),
        }
    )

    all_rows.sort(key=lambda row: (row["reported_hunt_year"], row["hunt_code"], row["source_container"], row["source_member"]))

    preserved_best_rows = read_preserved_best_history()
    if preserved_best_rows:
        best_rows = merge_history_repairs_into_best(preserved_best_rows, history_repairs)
        best_rows = reconcile_best_history(best_rows, current_2025_rows)
    else:
        best: dict[tuple[str, str, str, str, str], dict[str, str]] = {}
        for row in all_rows:
            key = (
                row["reported_hunt_year"],
                normalize_code(row["hunt_code"]),
                normalize_species(row["species"]),
                row["hunt_name"],
                row["weapon"],
            )
            current = best.get(key)
            if current is None or row_score(row) > row_score(current):
                best[key] = row
        best_rows = [best[key] for key in sorted(best)]

    age_rows = read_age_database()
    all_rows, age_long_summary = merge_age_database(all_rows, age_rows)
    best_rows, age_best_summary = merge_age_database(best_rows, age_rows)
    current_2025_rows, age_current_summary = merge_age_database(current_2025_rows, age_rows)
    local_age_long_summary = compute_local_three_year_age(all_rows)
    local_age_best_summary = compute_local_three_year_age(best_rows)
    local_by_identity = {
        (
            normalize_code(row.get("hunt_code")),
            species_family(row.get("species")),
            row.get("hunt_name", ""),
            row.get("weapon", ""),
        ): (
            row.get("average_age_3yr_local_computed", ""),
            row.get("average_age_3yr_local_computed_status", ""),
        )
        for row in all_rows
        if row.get("reported_hunt_year") == "2025"
        and row.get("source_kind") == "official_dashboard_current_snapshot"
    }
    for row in current_2025_rows:
        key = (
            normalize_code(row.get("hunt_code")),
            species_family(row.get("species")),
            row.get("hunt_name", ""),
            row.get("weapon", ""),
        )
        local_value, local_status = local_by_identity.get(key, ("", ""))
        row["average_age_3yr_local_computed"] = local_value
        row["average_age_3yr_local_computed_status"] = local_status

    year_counts = Counter(row["reported_hunt_year"] for row in best_rows)
    model_year_counts = Counter(row["model_target_year"] for row in best_rows)
    active_by_year = defaultdict(int)
    for row in best_rows:
        if row["hunt_code"] in active_codes:
            active_by_year[row["reported_hunt_year"]] += 1

    OUT_TRUTH.mkdir(parents=True, exist_ok=True)
    OUT_PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT_MODEL.mkdir(parents=True, exist_ok=True)
    OUT_OVERLAY.mkdir(parents=True, exist_ok=True)
    long_path = OUT_TRUTH / "harvest_results_all_years_long.csv"
    best_path = OUT_TRUTH / "harvest_quality_features_all_years_by_hunt_code.csv"
    source_audit_path = OUT_TRUTH / "harvest_results_all_years_source_audit.csv"
    write_csv(long_path, all_rows, NORMALIZED_FIELDS)
    write_csv(best_path, best_rows, NORMALIZED_FIELDS)
    current_2025_path = OUT_TRUTH / "harvest_results_2025_for_2026_current.csv"
    write_csv(current_2025_path, current_2025_rows, NORMALIZED_FIELDS)
    write_csv(
        source_audit_path,
        [{key: str(value) for key, value in row.items()} for row in source_audit],
        [
            "container",
            "member",
            "source_kind",
            "source_priority",
            "raw_rows",
            "normalized_rows",
            "unique_hunt_codes",
            "active_database_codes",
            "reported_hunt_years",
            "header_count",
        ],
    )

    # Convenience processed copies for current tooling.
    write_csv(OUT_PROCESSED / "harvest_results_all_years_long.csv", all_rows, NORMALIZED_FIELDS)
    write_csv(OUT_PROCESSED / "harvest_quality_features_all_years_by_hunt_code.csv", best_rows, NORMALIZED_FIELDS)
    write_csv(OUT_MODEL / "harvest_results_all_years_long.csv", all_rows, NORMALIZED_FIELDS)
    write_csv(OUT_MODEL / "harvest_quality_features_all_years_by_hunt_code.csv", best_rows, NORMALIZED_FIELDS)
    write_csv(OUT_PROCESSED / "harvest_results_2025_for_2026_current.csv", current_2025_rows, NORMALIZED_FIELDS)
    write_csv(OUT_MODEL / "harvest_results_2025_for_2026_current.csv", current_2025_rows, NORMALIZED_FIELDS)

    # Harvest refreshes never regenerate permit-reconciliation overlays.
    overlay_rows = read_checked_in_csv("data_model/permit_overlays/special_permit_overlay_classes_all_years.csv")
    if not overlay_rows:
        raise RuntimeError("The checked-in special permit overlay is unavailable; refusing to reconstruct it from harvest rows.")
    overlay_fields = [
        "reported_hunt_year",
        "model_target_year",
        "hunt_code",
        "species",
        "hunt_name",
        "hunt_type",
        "permits",
        "permit_overlay_class",
        "permit_overlay_use",
        "public_draw_odds_use",
        "p_draw_math_use",
        "source_file",
        "source_container",
    ]
    write_csv(OUT_OVERLAY / "special_permit_overlay_classes_all_years.csv", overlay_rows, overlay_fields)
    write_csv(OUT_PROCESSED / "special_permit_overlay_classes_all_years.csv", overlay_rows, overlay_fields)

    duplicate_keys = len(all_rows) - len({(row["reported_hunt_year"], row["hunt_code"], row["source_container"], row["source_member"]) for row in all_rows})
    history_repair_year_counts = Counter(row["reported_hunt_year"] for row in history_repairs)
    history_repair_metric_counts = {
        year: {
            field: sum(bool(row.get(field, "")) for row in history_repairs if row["reported_hunt_year"] == year)
            for field in ("permits", "hunters_afield", "harvest_total", "percent_success", "average_days", "hunter_satisfaction")
        }
        for year in sorted(history_repair_year_counts)
    }
    summary = {
        "source_candidates": len(source_audit),
        "normalized_long_rows": len(all_rows),
        "best_by_year_hunt_code_rows": len(best_rows),
        "unique_reported_hunt_years": sorted(year_counts),
        "reported_hunt_year_counts": dict(sorted(year_counts.items())),
        "model_target_year_counts": dict(sorted(model_year_counts.items())),
        "active_database_hunt_codes": len(active_codes),
        "active_database_coverage_by_reported_hunt_year": dict(sorted(active_by_year.items())),
        "unique_hunt_codes_all_years": len({row["hunt_code"] for row in best_rows}),
        "special_permit_overlay_rows": len(overlay_rows),
        "special_permit_overlay_class_counts": dict(Counter(row["permit_overlay_class"] for row in overlay_rows)),
        "duplicate_source_key_count": duplicate_keys,
        "official_dwr_history_2017_2021": {
            "source": str(DWR_HISTORY_2017_2021.relative_to(ROOT)),
            "rows_by_year": dict(sorted(history_repair_year_counts.items())),
            "metric_nonblank_by_year": history_repair_metric_counts,
        },
        "official_harvest_age": {
            "source": str(AGE_DATABASE.relative_to(ROOT)),
            "normalized_long": age_long_summary,
            "best_by_hunt_identity": age_best_summary,
            "current_2025_dashboard": age_current_summary,
            "local_three_year_normalized_long": local_age_long_summary,
            "local_three_year_best_by_hunt_identity": local_age_best_summary,
        },
        "current_2025_dashboard": current_2025_summary,
        "outputs": {
            "long_csv": str(long_path.relative_to(ROOT)),
            "best_by_hunt_code_csv": str(best_path.relative_to(ROOT)),
            "source_audit_csv": str(source_audit_path.relative_to(ROOT)),
            "current_2025_dashboard_csv": str(current_2025_path.relative_to(ROOT)),
            "processed_long_csv": "processed_data/harvest_results_all_years_long.csv",
            "processed_best_by_hunt_code_csv": "processed_data/harvest_quality_features_all_years_by_hunt_code.csv",
            "data_model_long_csv": "data_model/harvest_quality/harvest_results_all_years_long.csv",
            "data_model_best_by_hunt_code_csv": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
            "special_permit_overlay_csv": "data_model/permit_overlays/special_permit_overlay_classes_all_years.csv",
            "summary_json": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_summary.json",
            "summary_md": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_summary.md",
        },
        "guardrails": [
            "Harvest permits remain harvest-report context and are not current-year draw allotments.",
            "Harvest rows are marked do_not_use_for_permit_quota=True and do_not_use_directly_for_p_draw=True by default.",
            "Reported hunt year drives model target year as reported_hunt_year + 1 when model_target_year is missing.",
            "Current-row reconciliation requires exact normalized hunt_code plus compatible hunt_name and species; boundary_id is never a match key.",
            "The 2017-2021 repair uses official DWR harvest PDFs/package rows and remains feature-only truth, never permit or direct p_draw truth.",
            "Annual harvest age and DWR-reported three-year harvest age remain separate fields with separate age provenance.",
            "DWR Hunt Planner current_age_3yr_average is retained only in hunt_planner_current_age_3yr_average for exact current identity matches; it never replaces a harvest-report age field.",
            "Locally computed three-year age is stored separately from DWR-reported three-year age and requires three unambiguous annual DWR ages for the same exact hunt code and compatible species.",
        ],
    }
    (OUT_TRUTH / "harvest_results_all_years_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    md = ["# All-Years Harvest Results Database", "", "## Summary"]
    for key, value in summary.items():
        if isinstance(value, dict):
            md.append(f"- {key}: {value}")
        elif isinstance(value, list):
            md.append(f"- {key}: {', '.join(map(str, value))}")
        else:
            md.append(f"- {key}: {value}")
    (OUT_TRUTH / "harvest_results_all_years_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
