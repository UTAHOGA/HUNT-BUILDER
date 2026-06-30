#!/usr/bin/env python3
"""Build a governed research library master with explicit hunt-code mapping fields.

The existing library-master is useful as a catalog, but it cannot be promoted as
truth while hunt_code/boundary_id are absent. This builder follows the same
truth-output pattern as the draw/harvest database scripts: source catalog in,
normalized truth candidate out, validation summary beside it.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
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
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
HUNTS_ROOT = Path(str(_repo_root()))

SOURCE_LIBRARY = ROOT / "pipeline/RAW/hunt_unit_database/library-master.csv"
RECONCILED_LIBRARY = ROOT / "pipeline/RAW/hunt_unit_database/library-master.reconciled.csv"
DATABASE = HUNTS_ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
LOCAL_DATABASE_FALLBACK = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
DWR_HUNT_PLANNER_CSV_DIR = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv"
HUNT_MASTER = ROOT / "processed_data/hunt_master_enriched.csv"
CROSSWALK = ROOT / "data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv"

TRUTH_DIR = ROOT / "data_truth/research_library_truth/normalized"
VALIDATION_DIR = ROOT / "data_truth/research_library_truth/validation"
PROCESSED_DIR = ROOT / "processed_data"

MASTER_CSV = TRUTH_DIR / "research_library_master.csv"
MASTER_JSON = TRUTH_DIR / "research_library_master.json"
SUMMARY_JSON = VALIDATION_DIR / "research_library_master_summary.json"
GAPS_CSV = VALIDATION_DIR / "research_library_master_mapping_gaps.csv"
PROCESSED_CSV = PROCESSED_DIR / "research_library_master.csv"
PROCESSED_MD = PROCESSED_DIR / "research_library_master.md"

FEEDER_SOURCES = [
    {
        "record_id": "feeder_database_2026_canonical",
        "title": "2026 DATABASE.csv Canonical Hunt-Code And Boundary-ID Source",
        "path": DATABASE,
        "source_role": "CANONICAL_DATABASE",
        "boundary_alignment_role": "PRIMARY_BOUNDARY_ID_SOURCE",
        "notes": "Primary current 2026 hunt_code + boundary_id authority supplied from HUNTS.",
    },
    {
        "record_id": "feeder_database_2026_local_mirror",
        "title": "2026 DATABASE.csv Local Mirror",
        "path": LOCAL_DATABASE_FALLBACK,
        "source_role": "DATABASE_MIRROR",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Local mirror used only as fallback/crosscheck, not as primary authority when HUNTS DATABASE exists.",
    },
    {
        "record_id": "feeder_hunt_master_enriched",
        "title": "hunt_master_enriched.csv",
        "path": ROOT / "processed_data/hunt_master_enriched.csv",
        "source_role": "ENRICHED_RUNTIME_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Current enriched hunt reference with repeated rows by residency, points, and draw pool.",
    },
    {
        "record_id": "feeder_point_ladder_view",
        "title": "point_ladder_view.csv",
        "path": ROOT / "point_ladder_view.csv",
        "source_role": "POINT_LADDER_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Point ladder reference keyed by hunt_code/residency/points.",
    },
    {
        "record_id": "feeder_rac_recommended_permits_2026_xlsx",
        "title": "2026 RAC Recommended Permits Workbook",
        "path": ROOT / "pipeline/RAW/hunt_unit_database/2026/pdf/current_year_permit_numbers/Draw Odds/2026 rac recommended permits.xlsx",
        "source_role": "CURRENT_YEAR_PERMIT_RECOMMENDATION",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "User-supplied current-year RAC recommended permit numbers workbook.",
    },
    {
        "record_id": "feeder_rac_recommended_permits_2026_pdf",
        "title": "2026 RAC Recommended Permits PDF",
        "path": ROOT / "pipeline/RAW/hunt_unit_database/2026/pdf/current_year_permit_numbers/Draw Odds/2026 rac recommended permits.pdf",
        "source_role": "CURRENT_YEAR_PERMIT_RECOMMENDATION",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "User-supplied current-year RAC recommended permit numbers PDF companion.",
    },
    {
        "record_id": "feeder_preliminary_bg_harvest_2025_pdf",
        "title": "2025 Preliminary Big Game Harvest Report PDF",
        "path": ROOT / "pipeline/RAW/hunt_unit_database/2026/pdf/harvest_report/2026-03-06-2025-preliminary-bg-harvest.pdf",
        "source_role": "PRELIMINARY_HARVEST_REPORT",
        "boundary_alignment_role": "HUNT_CODE_HARVEST_CROSSCHECK_SOURCE",
        "notes": "User-supplied preliminary 2025 big game harvest report PDF.",
    },
    {
        "record_id": "feeder_hunt_master_canonical_json",
        "title": "hunt-master-canonical-2026.json",
        "path": ROOT / "hunt-master-canonical-2026.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Major canonical JSON surface.",
    },
    {
        "record_id": "feeder_hunt_master_canonical_coverage_json",
        "title": "hunt-master-canonical-2026.coverage.json",
        "path": ROOT / "hunt-master-canonical-2026.coverage.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_COVERAGE_REFERENCE",
        "notes": "Canonical coverage report used to audit current surface coverage.",
    },
    {
        "record_id": "feeder_hunt_master_canonical_built_csv",
        "title": "hunt_master_canonical_2026_built.csv",
        "path": ROOT / "hunt_master_canonical_2026_built.csv",
        "source_role": "CANONICAL_BUILD_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Built canonical CSV snapshot.",
    },
    {
        "record_id": "feeder_hunt_master_canonical_built_sqlite",
        "title": "hunt_master_canonical_2026_built.sqlite",
        "path": ROOT / "hunt_master_canonical_2026_built.sqlite",
        "source_role": "CANONICAL_BUILD_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Built canonical SQLite snapshot.",
    },
    {
        "record_id": "feeder_hunt_planner_2026_json",
        "title": "canonical/hunt-planner-2026.json",
        "path": ROOT / "canonical/hunt-planner-2026.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Canonical Hunt Planner JSON.",
    },
    {
        "record_id": "feeder_hunt_research_2026_processed_json",
        "title": "processed_data/hunt_research_2026.json",
        "path": ROOT / "processed_data/hunt_research_2026.json",
        "source_role": "RESEARCH_RUNTIME_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Large processed research JSON surface.",
    },
    {
        "record_id": "feeder_hunt_research_2026_index_json",
        "title": "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
        "path": ROOT / "processed_data/hunt_research_2026_split/hunt_research_2026.index.json",
        "source_role": "RESEARCH_RUNTIME_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Split research index JSON.",
    },
    {
        "record_id": "feeder_canonical_hunt_research_json",
        "title": "canonical/hunt-research-2026.json",
        "path": ROOT / "canonical/hunt-research-2026.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Canonical hunt-research contract.",
    },
    {
        "record_id": "feeder_canonical_hard_copies_json",
        "title": "canonical/hard-copies-2026.json",
        "path": ROOT / "canonical/hard-copies-2026.json",
        "source_role": "DOCUMENT_LIBRARY_REFERENCE",
        "boundary_alignment_role": "NO_BOUNDARY_ALIGNMENT",
        "notes": "Canonical hard-copy document contract.",
    },
    {
        "record_id": "feeder_canonical_shared_json",
        "title": "canonical/shared-2026.json",
        "path": ROOT / "canonical/shared-2026.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Shared canonical constants/reference contract.",
    },
    {
        "record_id": "feeder_canonical_outfitter_verification_json",
        "title": "canonical/outfitter-verification-2026.json",
        "path": ROOT / "canonical/outfitter-verification-2026.json",
        "source_role": "CANONICAL_JSON_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "notes": "Canonical outfitter verification surface.",
    },
    {
        "record_id": "feeder_canonical_field_usage_map_json",
        "title": "canonical/canonical-field-usage-map.json",
        "path": ROOT / "canonical/canonical-field-usage-map.json",
        "source_role": "CANONICAL_AUDIT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_FIELD_USAGE_REFERENCE",
        "notes": "Field usage map for canonical surfaces.",
    },
    {
        "record_id": "feeder_canonical_rebuild_coverage_json",
        "title": "canonical/canonical-rebuild-coverage.json",
        "path": ROOT / "canonical/canonical-rebuild-coverage.json",
        "source_role": "CANONICAL_AUDIT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_COVERAGE_REFERENCE",
        "notes": "Canonical rebuild coverage report.",
    },
    {
        "record_id": "feeder_boundary_alignment_reconcile_json",
        "title": "canonical/boundary-id-alignment-reconcile-2026-20260508_143652.json",
        "path": ROOT / "canonical/boundary-id-alignment-reconcile-2026-20260508_143652.json",
        "source_role": "BOUNDARY_ALIGNMENT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_ALIGNMENT_REPORT",
        "notes": "Boundary-ID alignment reconciliation report.",
    },
    {
        "record_id": "feeder_boundary_alignment_reconcile_followup_json",
        "title": "canonical/boundary-id-alignment-reconcile-2026-20260508_143854.json",
        "path": ROOT / "canonical/boundary-id-alignment-reconcile-2026-20260508_143854.json",
        "source_role": "BOUNDARY_ALIGNMENT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_ALIGNMENT_REPORT",
        "notes": "Follow-up boundary-ID alignment reconciliation report.",
    },
    {
        "record_id": "feeder_composite_synthetic_boundary_assign_json",
        "title": "canonical/composite-synthetic-boundary-id-assign-2026-20260508_144635.json",
        "path": ROOT / "canonical/composite-synthetic-boundary-id-assign-2026-20260508_144635.json",
        "source_role": "BOUNDARY_ALIGNMENT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_ID_ASSIGNMENT_REPORT",
        "notes": "Composite synthetic boundary-ID assignment evidence.",
    },
    {
        "record_id": "feeder_statewide_composite_boundaries_geojson",
        "title": "processed_data/statewide_composite_boundaries_2026.geojson",
        "path": ROOT / "processed_data/statewide_composite_boundaries_2026.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "PRIMARY_GEOMETRY_SOURCE",
        "notes": "Major statewide composite boundary geometry source.",
    },
    {
        "record_id": "feeder_utah_boundaries_canonical_geojson",
        "title": "data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson",
        "path": ROOT / "data/utah/foundation_bundle_2026/utah_boundaries_canonical_2026.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "PRIMARY_GEOMETRY_SOURCE",
        "notes": "Foundation-bundle canonical boundary geometry source.",
    },
    {
        "record_id": "feeder_composite_hunt_unit_mapping_geojson",
        "title": "processed_data/composite_hunt_unit_mapping_2026.geojson",
        "path": ROOT / "processed_data/composite_hunt_unit_mapping_2026.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "HUNT_UNIT_GEOMETRY_MAPPING_SOURCE",
        "notes": "Composite hunt-unit mapping geometry.",
    },
    {
        "record_id": "feeder_hunt_boundaries_arcgis_json",
        "title": "data/hunt_boundaries_arcgis.json",
        "path": ROOT / "data/hunt_boundaries_arcgis.json",
        "source_role": "BOUNDARY_JSON_REFERENCE",
        "boundary_alignment_role": "ARCGIS_BOUNDARY_SOURCE",
        "notes": "ArcGIS hunt-boundary source JSON.",
    },
    {
        "record_id": "feeder_hunt_boundaries_geojson",
        "title": "data/hunt_boundaries.geojson",
        "path": ROOT / "data/hunt_boundaries.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "PUBLISHED_GEOMETRY_SOURCE",
        "notes": "Published hunt boundary GeoJSON.",
    },
    {
        "record_id": "feeder_hunt_boundaries_lite_geojson",
        "title": "data/hunt-boundaries-lite.geojson",
        "path": ROOT / "data/hunt-boundaries-lite.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "PUBLISHED_GEOMETRY_SOURCE",
        "notes": "Published lite hunt boundary GeoJSON.",
    },
    {
        "record_id": "feeder_cwmu_boundaries_geojson",
        "title": "data/cwmu-boundaries.geojson",
        "path": ROOT / "data/cwmu-boundaries.geojson",
        "source_role": "BOUNDARY_GEOJSON_REFERENCE",
        "boundary_alignment_role": "CWMU_GEOMETRY_SOURCE",
        "notes": "Published CWMU boundary GeoJSON.",
    },
    {
        "record_id": "feeder_unavailable_boundary_rows_json",
        "title": "processed_data/unavailable_boundary_rows_2026.json",
        "path": ROOT / "processed_data/unavailable_boundary_rows_2026.json",
        "source_role": "BOUNDARY_AUDIT_REFERENCE",
        "boundary_alignment_role": "BOUNDARY_GAP_REFERENCE",
        "notes": "Boundary rows that were unavailable during boundary processing.",
    },
]

OUTPUT_FIELDS = [
    "research_record_id",
    "source_record_id",
    "source_document_id",
    "record_type",
    "source_role",
    "boundary_alignment_role",
    "mapping_scope",
    "hunt_code",
    "boundary_id",
    "hunt_code_mapping_status",
    "boundary_id_mapping_status",
    "candidate_hunt_code",
    "candidate_boundary_id",
    "candidate_historical_hunt_code",
    "candidate_historical_relationship",
    "candidate_match_status",
    "candidate_hunt_name",
    "candidate_species",
    "candidate_sex_type",
    "candidate_weapon",
    "candidate_hunt_type",
    "candidate_season",
    "candidate_permits_2026_res",
    "candidate_permits_2026_nr",
    "candidate_permits_2026_total",
    "candidate_permits_2026_source",
    "source_title",
    "source_species",
    "source_category",
    "source_organization",
    "source_group",
    "source_area",
    "source_condition",
    "year_start",
    "year_end",
    "public_visible",
    "prediction_engine_source",
    "source_pdf",
    "source_page",
    "source_repo_path",
    "source_file_status",
    "source_sha256",
    "file_size_bytes",
    "source_row_count",
    "source_unique_hunt_codes",
    "source_unique_boundary_ids",
    "source_page_count",
    "source_sheet_count",
    "source_filename_years",
    "source_path_years",
    "source_file_modified_utc",
    "permit_allotment_2026_promotion_status",
    "permit_allotment_2026_promotion_notes",
    "data_status",
    "source_truth_status",
    "mapping_review_required",
    "mapping_method",
    "mapping_notes",
    "original_notes",
]

REQUIRED_MAPPING_FIELDS = [
    "hunt_code",
    "boundary_id",
    "hunt_code_mapping_status",
    "boundary_id_mapping_status",
    "candidate_hunt_code",
    "candidate_boundary_id",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def normalize_bool(value: str) -> str:
    return "YES" if (value or "").strip().lower() in {"true", "yes", "1"} else "NO"


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def resolve_source_path(row: dict[str, str]) -> Path | None:
    candidates = [
        row.get("source_repo_path", ""),
        row.get("file_path", ""),
        row.get("source_pdf", ""),
    ]
    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate)
        if not path.is_absolute():
            path = ROOT / candidate
        if path.exists() and path.is_file():
            return path
    return None


def sha256_for_path(path: Path | None) -> str:
    if path is None:
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def years_in_text(value: str) -> str:
    years = sorted(set(re.findall(r"(?<!\d)(20\d{2})(?!\d)", value or "")))
    return "|".join(years)


def file_modified_utc(path: Path | None) -> str:
    if path is None or not path.exists() or not path.is_file():
        return ""
    modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    return modified.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def source_file_profile(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists() or not path.is_file():
        return {
            "file_size_bytes": "",
            "source_row_count": "",
            "source_unique_hunt_codes": "",
            "source_unique_boundary_ids": "",
            "source_page_count": "",
            "source_sheet_count": "",
            "source_file_modified_utc": "",
        }

    profile = {
        "file_size_bytes": str(path.stat().st_size),
        "source_row_count": "",
        "source_unique_hunt_codes": "",
        "source_unique_boundary_ids": "",
        "source_page_count": "",
        "source_sheet_count": "",
        "source_file_modified_utc": file_modified_utc(path),
    }

    if path.suffix.lower() == ".csv":
        try:
            row_count = 0
            hunt_codes: set[str] = set()
            boundary_ids: set[str] = set()
            with path.open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                for row in reader:
                    row_count += 1
                    normalized_row = {re.sub(r"[^a-z0-9]+", "", (key or "").lower()): value for key, value in row.items()}
                    hunt_code = (
                        normalized_row.get("huntcode")
                        or normalized_row.get("huntnumber")
                        or normalized_row.get("hunt")
                        or normalized_row.get("huntid")
                        or ""
                    ).strip()
                    boundary_id = (
                        normalized_row.get("boundaryid")
                        or normalized_row.get("boundaryids")
                        or normalized_row.get("boundary")
                        or ""
                    ).strip()
                    if hunt_code:
                        hunt_codes.add(hunt_code)
                    if boundary_id:
                        for part in re.split(r"[|,; ]+", boundary_id):
                            if part.strip():
                                boundary_ids.add(part.strip())
        except Exception:
            return profile
        profile["source_row_count"] = str(row_count)
        profile["source_unique_hunt_codes"] = str(len(hunt_codes))
        profile["source_unique_boundary_ids"] = str(len(boundary_ids))
        return profile

    if path.suffix.lower() == ".xlsx":
        try:
            with zipfile.ZipFile(path) as archive:
                workbook_xml = archive.read("xl/workbook.xml")
            root = ElementTree.fromstring(workbook_xml)
            namespaces = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
            sheets = root.findall(".//main:sheet", namespaces)
            profile["source_sheet_count"] = str(len(sheets))
        except Exception:
            return profile
        return profile

    if path.suffix.lower() == ".pdf":
        try:
            from pypdf import PdfReader  # type: ignore

            profile["source_page_count"] = str(len(PdfReader(str(path)).pages))
        except Exception:
            try:
                from PyPDF2 import PdfReader  # type: ignore

                profile["source_page_count"] = str(len(PdfReader(str(path)).pages))
            except Exception:
                profile["source_page_count"] = ""
        return profile

    # Lightweight JSON scan only. Very large boundary files are intentionally not parsed here.
    if path.suffix.lower() == ".json" and path.stat().st_size <= 10_000_000:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return profile
        profile["source_unique_hunt_codes"] = str(len(set(re.findall(r"\b[A-Z]{1,3}\d{4}\b", text))))
        boundary_ids = set(re.findall(r'"boundary_id"\s*:\s*"?([A-Za-z0-9_-]+)"?', text))
        profile["source_unique_boundary_ids"] = str(len(boundary_ids))

    return profile


def source_document_id(row: dict[str, str]) -> str:
    if row.get("record_type") == "document":
        return row.get("record_id", "")
    source_pdf = (row.get("source_pdf") or row.get("source_repo_path") or row.get("file_path") or "").lower()
    if "2022" in source_pdf and "2024" in source_pdf and "conservation" in source_pdf:
        return "doc_2022_2024_conservation_permits"
    if "conservation" in (row.get("title", "").lower()):
        return "doc_2022_2024_conservation_permits"
    return ""


def load_database() -> dict[str, dict[str, str]]:
    database_path = DATABASE if DATABASE.exists() else LOCAL_DATABASE_FALLBACK
    rows = read_csv(database_path)
    return {row["hunt_code"]: row for row in rows if row.get("hunt_code")}


def load_hunt_master_codes() -> set[str]:
    if not HUNT_MASTER.exists():
        return set()
    return {row["hunt_code"] for row in read_csv(HUNT_MASTER) if row.get("hunt_code")}


def load_crosswalk() -> dict[str, dict[str, str]]:
    if not CROSSWALK.exists():
        return {}
    return {row["current_hunt_code"]: row for row in read_csv(CROSSWALK) if row.get("current_hunt_code")}


def mapping_for_row(
    row: dict[str, str],
    database: dict[str, dict[str, str]],
    crosswalk: dict[str, dict[str, str]],
) -> dict[str, str]:
    record_type = row.get("record_type", "")
    candidate_code = row.get("database_hunt_code", "")
    database_row = database.get(candidate_code, {}) if candidate_code else {}
    crosswalk_row = crosswalk.get(candidate_code, {}) if candidate_code else {}

    if record_type == "document":
        return {
            "mapping_scope": "DOCUMENT_LEVEL",
            "hunt_code": "",
            "boundary_id": "",
            "hunt_code_mapping_status": "DOCUMENT_LEVEL_MAPPING_REQUIRED",
            "boundary_id_mapping_status": "DOCUMENT_LEVEL_MAPPING_REQUIRED",
            "mapping_review_required": "YES",
            "mapping_method": "document_catalog_row_not_extracted_to_hunt_code_rows",
            "mapping_notes": "Document rows must be extracted into per-hunt-code rows before promotion.",
        }

    if candidate_code:
        return {
            "mapping_scope": "PERMIT_ALLOCATION_ROW",
            "hunt_code": "",
            "boundary_id": "",
            "hunt_code_mapping_status": "HISTORICAL_PREFIX_REVIEW_REQUIRED",
            "boundary_id_mapping_status": "HISTORICAL_PREFIX_REVIEW_REQUIRED",
            "mapping_review_required": "YES",
            "mapping_method": "candidate_from_library_database_reconciliation_not_promoted",
            "mapping_notes": (
                "Candidate only. The 2022-2024 conservation rows predate/current-prefix changes; "
                "current hunt_code and boundary_id require reviewed crosswalk promotion."
            ),
            "candidate_boundary_id": database_row.get("boundary_id", ""),
            "candidate_historical_hunt_code": crosswalk_row.get("historical_hunt_code", ""),
            "candidate_historical_relationship": crosswalk_row.get("relationship_type", ""),
        }

    return {
        "mapping_scope": "UNKNOWN_OR_UNMAPPED_ROW",
        "hunt_code": "",
        "boundary_id": "",
        "hunt_code_mapping_status": "UNMAPPED_REVIEW_REQUIRED",
        "boundary_id_mapping_status": "UNMAPPED_REVIEW_REQUIRED",
        "mapping_review_required": "YES",
        "mapping_method": "no_candidate_hunt_code_available",
        "mapping_notes": "No candidate hunt code is available; source row must be reviewed manually.",
    }


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return slug or "source"


def classify_direct_dwr_csv(path: Path) -> tuple[str, str, str]:
    name = path.name.lower()
    if name == "database.csv":
        return (
            "DATABASE_MIRROR",
            "BOUNDARY_ID_CROSSCHECK_SOURCE",
            "Direct Utah DWR Hunt Planner CSV folder database mirror.",
        )
    if "hunt_master_canonical" in name:
        return (
            "CANONICAL_BUILD_REFERENCE",
            "BOUNDARY_ID_CROSSCHECK_SOURCE",
            "Direct Utah DWR Hunt Planner CSV folder canonical hunt master build.",
        )
    if name.startswith("2026_rac_") or "rac_" in name or "permit" in name or "current_year_permit" in name:
        return (
            "DWR_HUNT_PLANNER_PERMIT_CSV",
            "BOUNDARY_ID_CROSSCHECK_SOURCE",
            "Direct Utah DWR Hunt Planner CSV folder permit/recommendation source.",
        )
    if "draw_results" in name or "draw_database" in name or "le_elk_2025_draw" in name:
        return (
            "DWR_HUNT_PLANNER_DRAW_RESULT_CSV",
            "HUNT_CODE_DRAW_CROSSCHECK_SOURCE",
            "Direct Utah DWR Hunt Planner CSV folder draw-results/reference source.",
        )
    if "harvest" in name:
        return (
            "DWR_HUNT_PLANNER_HARVEST_CSV",
            "HUNT_CODE_HARVEST_CROSSCHECK_SOURCE",
            "Direct Utah DWR Hunt Planner CSV folder harvest source.",
        )
    return (
        "DWR_HUNT_PLANNER_DIRECT_CSV",
        "BOUNDARY_ID_CROSSCHECK_SOURCE",
        "Direct Utah DWR Hunt Planner CSV folder source.",
    )


def discover_direct_dwr_csv_sources() -> list[dict[str, object]]:
    if not DWR_HUNT_PLANNER_CSV_DIR.exists():
        return []

    sources: list[dict[str, object]] = []
    for path in sorted(DWR_HUNT_PLANNER_CSV_DIR.glob("*.csv"), key=lambda item: item.name.lower()):
        source_role, boundary_role, notes = classify_direct_dwr_csv(path)
        sources.append(
            {
                "record_id": f"feeder_dwr_csv_{slugify(path.stem)}",
                "title": f"Direct DWR Hunt Planner CSV - {path.name}",
                "path": path,
                "source_role": source_role,
                "boundary_alignment_role": boundary_role,
                "notes": notes,
            }
        )
    return sources


def build_feeder_file_rows(start_index: int) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen_paths: set[str] = set()
    next_index = start_index

    for feeder in [*FEEDER_SOURCES, *discover_direct_dwr_csv_sources()]:
        path = Path(feeder["path"])
        normalized_path = str(path.resolve()).lower() if path.exists() else str(path).lower()
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)

        source_exists = path.exists() and path.is_file()
        profile = source_file_profile(path if source_exists else None)
        rows.append(
            {
                "research_record_id": f"research_library_{next_index:04d}",
                "source_record_id": feeder["record_id"],
                "source_document_id": feeder["record_id"],
                "record_type": "feeder_file",
                "source_role": feeder["source_role"],
                "boundary_alignment_role": feeder["boundary_alignment_role"],
                "mapping_scope": "FILE_LEVEL_REFERENCE",
                "hunt_code": "",
                "boundary_id": "",
                "hunt_code_mapping_status": "FILE_LEVEL_REFERENCE_CONTAINS_OR_SUPPORTS_HUNT_CODES",
                "boundary_id_mapping_status": "FILE_LEVEL_REFERENCE_CONTAINS_OR_SUPPORTS_BOUNDARY_IDS",
                "candidate_hunt_code": "",
                "candidate_boundary_id": "",
                "candidate_historical_hunt_code": "",
                "candidate_historical_relationship": "",
                "candidate_match_status": "SOURCE_FILE_REGISTERED",
                "candidate_hunt_name": "",
                "candidate_species": "",
                "candidate_sex_type": "",
                "candidate_weapon": "",
                "candidate_hunt_type": "",
                "candidate_season": "",
                "candidate_permits_2026_res": "",
                "candidate_permits_2026_nr": "",
                "candidate_permits_2026_total": "",
                "candidate_permits_2026_source": "",
                "source_title": feeder["title"],
                "source_species": "Mixed",
                "source_category": "Feeder Reference",
                "source_organization": "",
                "source_group": "",
                "source_area": "",
                "source_condition": "",
                "year_start": "2026",
                "year_end": "2026",
                "public_visible": "NO",
                "prediction_engine_source": "NO",
                "source_pdf": "",
                "source_page": "",
                "source_repo_path": relative(path),
                "source_file_status": "FOUND" if source_exists else "MISSING",
                "source_sha256": sha256_for_path(path if source_exists else None),
                "file_size_bytes": profile["file_size_bytes"],
                "source_row_count": profile["source_row_count"],
                "source_unique_hunt_codes": profile["source_unique_hunt_codes"],
                "source_unique_boundary_ids": profile["source_unique_boundary_ids"],
                "source_page_count": profile["source_page_count"],
                "source_sheet_count": profile["source_sheet_count"],
                "source_filename_years": years_in_text(path.name),
                "source_path_years": years_in_text(str(path)),
                "source_file_modified_utc": profile["source_file_modified_utc"],
                "permit_allotment_2026_promotion_status": "NOT_PROMOTED_SOURCE_REGISTRY_ONLY",
                "permit_allotment_2026_promotion_notes": (
                    "Registered as source evidence only. Do not promote 2025 permit values to 2026 available "
                    "allotment without reviewed source-date context and explicit promotion step."
                ),
                "data_status": "REFERENCE_FILE_REGISTERED",
                "source_truth_status": feeder["source_role"],
                "mapping_review_required": "NO",
                "mapping_method": "registered_feeder_reference_file",
                "mapping_notes": feeder["notes"],
                "original_notes": "",
            }
        )
        next_index += 1

    return rows


def build_rows() -> tuple[list[dict[str, str]], dict]:
    source_rows = read_csv(SOURCE_LIBRARY)
    reconciled_rows = {row["record_id"]: row for row in read_csv(RECONCILED_LIBRARY)}
    database = load_database()
    hunt_master_codes = load_hunt_master_codes()
    crosswalk = load_crosswalk()

    output_rows: list[dict[str, str]] = []
    for index, source_row in enumerate(source_rows, start=1):
        row = {**source_row, **reconciled_rows.get(source_row.get("record_id", ""), {})}
        candidate_code = row.get("database_hunt_code", "")
        database_row = database.get(candidate_code, {}) if candidate_code else {}
        path = resolve_source_path(row)
        mapping = mapping_for_row(row, database, crosswalk)

        output_rows.append(
            {
                "research_record_id": f"research_library_{index:04d}",
                "source_record_id": row.get("record_id", ""),
                "source_document_id": source_document_id(row),
                "record_type": row.get("record_type", ""),
                "source_role": "LIBRARY_CATALOG_SOURCE",
                "boundary_alignment_role": "ROW_LEVEL_CANDIDATE_BOUNDARY_ALIGNMENT",
                "mapping_scope": mapping.get("mapping_scope", ""),
                "hunt_code": mapping.get("hunt_code", ""),
                "boundary_id": mapping.get("boundary_id", ""),
                "hunt_code_mapping_status": mapping.get("hunt_code_mapping_status", ""),
                "boundary_id_mapping_status": mapping.get("boundary_id_mapping_status", ""),
                "candidate_hunt_code": candidate_code,
                "candidate_boundary_id": mapping.get("candidate_boundary_id", ""),
                "candidate_historical_hunt_code": mapping.get("candidate_historical_hunt_code", ""),
                "candidate_historical_relationship": mapping.get("candidate_historical_relationship", ""),
                "candidate_match_status": row.get("database_match_status", ""),
                "candidate_hunt_name": database_row.get("hunt_name", row.get("database_hunt_name", "")),
                "candidate_species": database_row.get("species", row.get("database_species", "")),
                "candidate_sex_type": database_row.get("sex_type", row.get("database_sex_type", "")),
                "candidate_weapon": database_row.get("weapon", row.get("database_weapon", "")),
                "candidate_hunt_type": database_row.get("hunt_type", row.get("database_hunt_type", "")),
                "candidate_season": database_row.get("season", row.get("database_season", "")),
                "candidate_permits_2026_res": database_row.get(
                    "permits_2026_res", row.get("database_permits_2026_res", "")
                ),
                "candidate_permits_2026_nr": database_row.get(
                    "permits_2026_nr", row.get("database_permits_2026_nr", "")
                ),
                "candidate_permits_2026_total": database_row.get(
                    "permits_2026_total", row.get("database_permits_2026_total", "")
                ),
                "candidate_permits_2026_source": database_row.get(
                    "permits_2026_source", row.get("database_permits_2026_source", "")
                ),
                "source_title": row.get("title", ""),
                "source_species": row.get("species", ""),
                "source_category": row.get("category", ""),
                "source_organization": row.get("organization", ""),
                "source_group": row.get("group", ""),
                "source_area": row.get("area", ""),
                "source_condition": row.get("condition", ""),
                "year_start": row.get("year_start", ""),
                "year_end": row.get("year_end", ""),
                "public_visible": normalize_bool(row.get("public_visible", "")),
                "prediction_engine_source": normalize_bool(row.get("prediction_engine_source", "")),
                "source_pdf": row.get("source_pdf", ""),
                "source_page": row.get("source_page", ""),
                "source_repo_path": row.get("source_repo_path") or row.get("file_path", ""),
                "source_file_status": "FOUND" if path else row.get("document_file_status", "NOT_RESOLVED"),
                "source_sha256": sha256_for_path(path),
                **source_file_profile(path),
                "source_filename_years": years_in_text((path.name if path else "") or row.get("source_pdf", "")),
                "source_path_years": years_in_text((str(path) if path else "") or row.get("source_repo_path", "")),
                "permit_allotment_2026_promotion_status": "NOT_PROMOTED_CATALOG_REVIEW_REQUIRED",
                "permit_allotment_2026_promotion_notes": (
                    "Catalog/candidate row only. Permit values must not feed 2026 available allotment without "
                    "reviewed source-date context and explicit promotion step."
                ),
                "data_status": row.get("data_status", ""),
                "source_truth_status": "CATALOG_ONLY_NOT_TRUTH",
                "mapping_review_required": mapping.get("mapping_review_required", "YES"),
                "mapping_method": mapping.get("mapping_method", ""),
                "mapping_notes": mapping.get("mapping_notes", ""),
                "original_notes": row.get("notes", ""),
            }
        )

    output_rows.extend(build_feeder_file_rows(len(output_rows) + 1))

    candidate_codes = {row["candidate_hunt_code"] for row in output_rows if row.get("candidate_hunt_code")}
    feeder_rows = [row for row in output_rows if row.get("record_type") == "feeder_file"]
    summary = {
        "artifact": "research_library_master",
        "status": "REVIEW_REQUIRED",
        "source_library": relative(SOURCE_LIBRARY),
        "source_reconciled_library": relative(RECONCILED_LIBRARY),
        "database_source": relative(DATABASE if DATABASE.exists() else LOCAL_DATABASE_FALLBACK),
        "record_count": len(output_rows),
        "source_record_count": len(output_rows),
        "source_catalog_record_count": len(source_rows),
        "feeder_file_record_count": len(feeder_rows),
        "direct_dwr_hunt_planner_csv_folder": relative(DWR_HUNT_PLANNER_CSV_DIR),
        "direct_dwr_hunt_planner_csv_files_discovered": len(discover_direct_dwr_csv_sources()),
        "direct_dwr_hunt_planner_csv_feeder_rows": sum(
            1 for row in feeder_rows if row.get("source_record_id", "").startswith("feeder_dwr_csv_")
        ),
        "record_type_counts": dict(sorted(Counter(row["record_type"] for row in output_rows).items())),
        "source_role_counts": dict(sorted(Counter(row["source_role"] for row in output_rows).items())),
        "boundary_alignment_role_counts": dict(
            sorted(Counter(row["boundary_alignment_role"] for row in output_rows).items())
        ),
        "mapping_scope_counts": dict(sorted(Counter(row["mapping_scope"] for row in output_rows).items())),
        "hunt_code_mapping_status_counts": dict(
            sorted(Counter(row["hunt_code_mapping_status"] for row in output_rows).items())
        ),
        "boundary_id_mapping_status_counts": dict(
            sorted(Counter(row["boundary_id_mapping_status"] for row in output_rows).items())
        ),
        "review_required_rows": sum(1 for row in output_rows if row["mapping_review_required"] == "YES"),
        "reviewed_hunt_code_rows": sum(1 for row in output_rows if row.get("hunt_code")),
        "reviewed_boundary_id_rows": sum(1 for row in output_rows if row.get("boundary_id")),
        "candidate_hunt_code_rows": sum(1 for row in output_rows if row.get("candidate_hunt_code")),
        "candidate_hunt_code_unique_count": len(candidate_codes),
        "candidate_boundary_id_rows": sum(1 for row in output_rows if row.get("candidate_boundary_id")),
        "candidate_historical_hunt_code_rows": sum(
            1 for row in output_rows if row.get("candidate_historical_hunt_code")
        ),
        "permit_allotment_2026_promotion_status_counts": dict(
            sorted(Counter(row.get("permit_allotment_2026_promotion_status", "") for row in output_rows).items())
        ),
        "source_rows_missing_year_context": sum(
            1
            for row in output_rows
            if not row.get("source_filename_years") and not row.get("source_path_years")
        ),
        "feeder_files_missing": [
            row["source_repo_path"] for row in feeder_rows if row.get("source_file_status") != "FOUND"
        ],
        "canonical_database_feeder_rows": sum(1 for row in feeder_rows if row.get("source_role") == "CANONICAL_DATABASE"),
        "boundary_alignment_feeder_rows": sum(
            1
            for row in feeder_rows
            if row.get("boundary_alignment_role") not in {"", "NO_BOUNDARY_ALIGNMENT"}
        ),
        "candidate_codes_missing_database": sorted(code for code in candidate_codes if code not in database),
        "candidate_codes_missing_hunt_master": sorted(code for code in candidate_codes if code not in hunt_master_codes),
        "missing_required_mapping_fields": [
            field for field in REQUIRED_MAPPING_FIELDS if field not in OUTPUT_FIELDS
        ],
        "duplicate_research_record_ids": [
            record_id
            for record_id, count in Counter(row["research_record_id"] for row in output_rows).items()
            if count > 1
        ],
        "law": [
            "Every research library row must carry hunt_code and boundary_id columns.",
            "Blank reviewed hunt_code/boundary_id fields require explicit mapping status fields.",
            "Candidate hunt codes and candidate boundary IDs are not truth fields.",
            "DATABASE.csv is the canonical current hunt-code and boundary-id source.",
            "Direct Utah DWR Hunt Planner CSV-folder files are registered as source evidence.",
            "Feeder files are registered as source evidence with hashes before their values can be used.",
            "Do not promote 2025 permit values to 2026 available allotment without reviewed source-date context.",
            "Historical/current prefix changes must flow through the crosswalk before promotion.",
            "Document-level rows must be extracted into per-hunt-code rows before they can feed prediction/runtime data.",
        ],
        "outputs": {
            "master_csv": relative(MASTER_CSV),
            "master_json": relative(MASTER_JSON),
            "summary_json": relative(SUMMARY_JSON),
            "mapping_gaps_csv": relative(GAPS_CSV),
            "processed_csv": relative(PROCESSED_CSV),
            "processed_md": relative(PROCESSED_MD),
        },
    }

    blockers = []
    if summary["source_catalog_record_count"] != len(source_rows):
        blockers.append("SOURCE_ROW_COUNT_MISMATCH")
    if summary["missing_required_mapping_fields"]:
        blockers.append("MISSING_REQUIRED_MAPPING_FIELDS")
    if summary["duplicate_research_record_ids"]:
        blockers.append("DUPLICATE_RESEARCH_RECORD_IDS")
    if summary["candidate_codes_missing_database"]:
        blockers.append("CANDIDATE_CODES_MISSING_DATABASE")
    if summary["candidate_codes_missing_hunt_master"]:
        blockers.append("CANDIDATE_CODES_MISSING_HUNT_MASTER")
    if summary["feeder_files_missing"]:
        blockers.append("FEEDER_FILES_MISSING")
    if summary["canonical_database_feeder_rows"] != 1:
        blockers.append("CANONICAL_DATABASE_FEEDER_NOT_REGISTERED")
    if summary["direct_dwr_hunt_planner_csv_feeder_rows"] < 80:
        blockers.append("DIRECT_DWR_HUNT_PLANNER_CSV_FOLDER_UNDER_REGISTERED")
    summary["blockers"] = blockers
    summary["blocker_count"] = len(blockers)
    if blockers:
        summary["status"] = "BLOCKED"

    return output_rows, summary


def write_markdown(summary: dict) -> None:
    lines = [
        "# Research Library Master",
        "",
        "This is the governed research-library master generated from the existing library catalog.",
        "",
        "## Status",
        "",
        f"- Status: `{summary['status']}`",
        f"- Rows: `{summary['record_count']}`",
        f"- Source catalog rows: `{summary['source_catalog_record_count']}`",
        f"- Feeder file rows: `{summary['feeder_file_record_count']}`",
        f"- Direct DWR Hunt Planner CSV feeder rows: `{summary['direct_dwr_hunt_planner_csv_feeder_rows']}`",
        f"- Reviewed hunt-code rows: `{summary['reviewed_hunt_code_rows']}`",
        f"- Candidate hunt-code rows: `{summary['candidate_hunt_code_rows']}`",
        f"- Unique candidate hunt codes: `{summary['candidate_hunt_code_unique_count']}`",
        f"- Boundary-alignment feeder rows: `{summary['boundary_alignment_feeder_rows']}`",
        f"- Rows missing source-year context: `{summary['source_rows_missing_year_context']}`",
        f"- Rows requiring review: `{summary['review_required_rows']}`",
        f"- Blockers: `{summary['blocker_count']}`",
        "",
        "## Law",
        "",
    ]
    lines.extend(f"- {item}" for item in summary["law"])
    lines.extend(
        [
            "",
            "## Mapping Status Counts",
            "",
        ]
    )
    for key, value in summary["hunt_code_mapping_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Outputs", ""])
    for label, path in summary["outputs"].items():
        lines.append(f"- `{label}`: `{path}`")
    PROCESSED_MD.parent.mkdir(parents=True, exist_ok=True)
    PROCESSED_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows, summary = build_rows()
    gaps = [row for row in rows if row.get("mapping_review_required") == "YES"]

    write_csv(MASTER_CSV, rows, OUTPUT_FIELDS)
    write_json(MASTER_JSON, {"metadata": summary, "rows": rows})
    write_json(SUMMARY_JSON, summary)
    write_csv(GAPS_CSV, gaps, OUTPUT_FIELDS)
    write_csv(PROCESSED_CSV, rows, OUTPUT_FIELDS)
    write_markdown(summary)

    print(json.dumps(summary, indent=2, sort_keys=True))
    return 1 if summary["blocker_count"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
