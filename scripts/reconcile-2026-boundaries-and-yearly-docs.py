#!/usr/bin/env python3
"""Reconcile current boundary identity and yearly BIBLE hunt-code rows."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPLIT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
STATUS = SPLIT_DIR / "crosswalk_2026_database_status_check.csv"
CANDIDATES = SPLIT_DIR / "crosswalk_2026_additional_source_candidates.csv"

DISPLAY_BOUNDARY = ROOT / "processed_data/display-boundary-index-2026.csv"
HUNT_BOUNDARY = ROOT / "processed_data/hunt_boundary_crosswalk_2026.csv"
BOUNDARY_ID_TO_CODE = ROOT / "processed_data/audits/boundary_id_to_hunt_code_crosswalk_2026.csv"
SPLIT_INDEX = ROOT / "processed_data/hunt_research_2026_split/hunt_research_2026.index.json"
BOUNDARIES_DIR = ROOT / "processed_data/boundaries"
YEAR_DOC_DIR = ROOT / "processed_data/audits/bible_hunt_code_year_documents"

CURRENT_OUT = SPLIT_DIR / "current_2026_boundary_source_reconciliation.csv"
YEAR_OUT = YEAR_DOC_DIR / "bible_hunt_code_year_boundary_reconciliation_2020_2026.csv"
YEAR_UNRESOLVED_OUT = YEAR_DOC_DIR / "bible_hunt_code_year_boundary_unresolved_2020_2026.csv"
SUMMARY_OUT = SPLIT_DIR / "boundary_and_yearly_reconciliation_summary.json"

CURRENT_COLUMNS = [
    "hunt_code",
    "database_boundary_id",
    "resolved_boundary_id",
    "boundary_resolution_status",
    "can_close_identity_boundary",
    "database_status",
    "display_boundary_id",
    "hunt_boundary_crosswalk_id",
    "split_index_boundary_id",
    "direct_hunt_code_geojson",
    "direct_boundary_id_geojson",
    "confirmed_boundary_ids_from_evidence",
    "candidate_boundary_ids_from_evidence",
    "boundary_source_count",
    "boundary_sources",
    "notes",
]

YEAR_COLUMNS = [
    "report_year",
    "draw_year",
    "model_year",
    "comparison_hunt_code",
    "resolved_boundary_id",
    "boundary_resolution_status",
    "current_database_presence",
    "current_database_hunt_name",
    "current_database_species",
    "current_database_boundary_id",
    "display_boundary_id",
    "hunt_boundary_crosswalk_id",
    "split_index_boundary_id",
    "direct_hunt_code_geojson",
    "direct_boundary_id_geojson",
    "source_family_values",
    "source_files",
    "year_document_status",
    "notes",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as handle:
        return [{key: (value or "").strip() for key, value in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, str]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def split_codes(value: str) -> list[str]:
    return re.findall(r"\b[A-Z]{1,3}\d{4}\b", value or "")


def unique_join(values: list[str]) -> str:
    return "|".join(sorted(dict.fromkeys(value for value in values if value)))


def load_split_index() -> dict[str, str]:
    if not SPLIT_INDEX.exists():
        return {}
    data = json.load(SPLIT_INDEX.open(encoding="utf-8-sig"))
    out: dict[str, str] = {}
    if isinstance(data, list):
        for row in data:
            if not isinstance(row, dict):
                continue
            code = str(row.get("hunt_code") or row.get("HuntCode") or row.get("huntCode") or "").strip()
            boundary = str(row.get("boundary_id") or row.get("boundaryId") or row.get("boundary") or "").strip()
            if code and boundary:
                out.setdefault(code, boundary)
    elif isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, dict):
                code = str(value.get("hunt_code") or key).strip()
                boundary = str(value.get("boundary_id") or value.get("boundaryId") or "").strip()
                if code and boundary:
                    out.setdefault(code, boundary)
    return out


def load_boundary_sources() -> dict[str, dict[str, str]]:
    display = {row["hunt_code"]: row.get("boundary_id", "") for row in read_csv(DISPLAY_BOUNDARY) if row.get("hunt_code")}
    hunt_boundary = {row["hunt_code"]: row.get("boundary_id", "") for row in read_csv(HUNT_BOUNDARY) if row.get("hunt_code")}
    split_index = load_split_index()
    boundary_id_to_code: dict[str, list[str]] = defaultdict(list)
    for row in read_csv(BOUNDARY_ID_TO_CODE):
        for code in split_codes(row.get("hunt_codes", "")):
            boundary_id_to_code[code].append(row.get("boundary_id", ""))

    direct_geojson_hunt_codes = {path.stem for path in BOUNDARIES_DIR.glob("*.geojson") if re.match(r"^[A-Z]{1,3}\d{4}$", path.stem)}
    direct_geojson_boundary_ids = {path.stem for path in BOUNDARIES_DIR.glob("*.geojson") if path.stem.isdigit()}

    codes = set(display) | set(hunt_boundary) | set(split_index) | set(boundary_id_to_code) | direct_geojson_hunt_codes
    out: dict[str, dict[str, str]] = {}
    for code in codes:
        out[code] = {
            "display_boundary_id": display.get(code, ""),
            "hunt_boundary_crosswalk_id": hunt_boundary.get(code, ""),
            "split_index_boundary_id": split_index.get(code, ""),
            "boundary_id_to_code_ids": unique_join(boundary_id_to_code.get(code, [])),
            "direct_hunt_code_geojson": "true" if code in direct_geojson_hunt_codes else "false",
        }
        ids = [
            out[code]["display_boundary_id"],
            out[code]["hunt_boundary_crosswalk_id"],
            out[code]["split_index_boundary_id"],
            *boundary_id_to_code.get(code, []),
        ]
        out[code]["direct_boundary_id_geojson"] = "true" if any(boundary_id in direct_geojson_boundary_ids for boundary_id in ids if boundary_id) else "false"
    return out


def resolve_boundary_id(code: str, db_boundary: str, source_row: dict[str, str]) -> tuple[str, str, list[str], list[str]]:
    sources: list[str] = []
    candidates = [
        ("DATABASE", db_boundary),
        ("display-boundary-index-2026.csv", source_row.get("display_boundary_id", "")),
        ("hunt_boundary_crosswalk_2026.csv", source_row.get("hunt_boundary_crosswalk_id", "")),
        ("hunt_research_2026_split.index", source_row.get("split_index_boundary_id", "")),
        ("boundary_id_to_hunt_code_crosswalk_2026.csv", source_row.get("boundary_id_to_code_ids", "")),
    ]
    values: list[str] = []
    for source, value in candidates:
        for part in str(value or "").split("|"):
            part = part.strip()
            if part:
                values.append(part)
                sources.append(source)
    unique_values = sorted(dict.fromkeys(values))
    if db_boundary and all(value == db_boundary for value in unique_values):
        return db_boundary, "BOUNDARY_ID_CONFIRMED", unique_values, sources
    if db_boundary and db_boundary in unique_values:
        return db_boundary, "DATABASE_BOUNDARY_ID_WITH_ADDITIONAL_CANDIDATES", unique_values, sources
    if not db_boundary and len(unique_values) == 1:
        return unique_values[0], "BOUNDARY_ID_FROM_RUNTIME_SOURCE_ONLY", unique_values, sources
    if len(unique_values) > 1:
        return db_boundary or unique_values[0], "BOUNDARY_ID_CONFLICT_REVIEW", unique_values, sources
    return db_boundary, "BOUNDARY_ID_MISSING_FROM_RUNTIME_SOURCES", unique_values, sources


def main() -> int:
    db_by_code = {row["hunt_code"]: row for row in read_csv(DATABASE) if row.get("hunt_code")}
    status_by_code = {row["hunt_code"]: row for row in read_csv(STATUS) if row.get("hunt_code")}
    candidates_by_code: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(CANDIDATES):
        if row.get("current_hunt_code"):
            candidates_by_code[row["current_hunt_code"]].append(row)
    boundary_sources = load_boundary_sources()

    current_rows: list[dict[str, str]] = []
    for code, status_row in status_by_code.items():
        db = db_by_code.get(code, {})
        source_row = boundary_sources.get(code, {})
        resolved_boundary, boundary_status, candidate_ids, sources = resolve_boundary_id(
            code,
            db.get("boundary_id", ""),
            source_row,
        )
        evidence = candidates_by_code.get(code, [])
        confirmed_evidence_ids = [
            row.get("current_boundary_id", "") for row in evidence if row.get("boundary_match") == "YES"
        ]
        candidate_evidence_ids = [row.get("current_boundary_id", "") for row in evidence if row.get("current_boundary_id")]
        can_close = (
            status_row.get("next_status") == "DATABASE_IDENTITY_READY"
            and boundary_status in {"BOUNDARY_ID_CONFIRMED", "DATABASE_BOUNDARY_ID_WITH_ADDITIONAL_CANDIDATES"}
        )
        current_rows.append(
            {
                "hunt_code": code,
                "database_boundary_id": db.get("boundary_id", ""),
                "resolved_boundary_id": resolved_boundary,
                "boundary_resolution_status": boundary_status,
                "can_close_identity_boundary": "true" if can_close else "false",
                "database_status": status_row.get("next_status", ""),
                "display_boundary_id": source_row.get("display_boundary_id", ""),
                "hunt_boundary_crosswalk_id": source_row.get("hunt_boundary_crosswalk_id", ""),
                "split_index_boundary_id": source_row.get("split_index_boundary_id", ""),
                "direct_hunt_code_geojson": source_row.get("direct_hunt_code_geojson", "false"),
                "direct_boundary_id_geojson": source_row.get("direct_boundary_id_geojson", "false"),
                "confirmed_boundary_ids_from_evidence": unique_join(confirmed_evidence_ids),
                "candidate_boundary_ids_from_evidence": unique_join(candidate_evidence_ids),
                "boundary_source_count": str(len(set(sources))),
                "boundary_sources": unique_join(sources),
                "notes": "Identity/boundary can close." if can_close else "Keep in active review bucket.",
            }
        )

    current_by_code = {row["hunt_code"]: row for row in current_rows}
    year_rows: list[dict[str, str]] = []
    for year_file in sorted(YEAR_DOC_DIR.glob("bible_hunt_code_year_document_*.csv")):
        if "summary" in year_file.name:
            continue
        for row in read_csv(year_file):
            code = row.get("comparison_hunt_code", "")
            if not code:
                continue
            db = db_by_code.get(code, {})
            boundary = current_by_code.get(code, {})
            source_row = boundary_sources.get(code, {})
            resolved_boundary = boundary.get("resolved_boundary_id", db.get("boundary_id", ""))
            if boundary:
                boundary_status = boundary.get("boundary_resolution_status", "")
            elif db:
                resolved_boundary, boundary_status, _, _ = resolve_boundary_id(code, db.get("boundary_id", ""), source_row)
            else:
                resolved_boundary, boundary_status, _, _ = resolve_boundary_id(code, "", source_row)
            year_rows.append(
                {
                    "report_year": row.get("report_year", ""),
                    "draw_year": row.get("draw_year", ""),
                    "model_year": row.get("model_year", ""),
                    "comparison_hunt_code": code,
                    "resolved_boundary_id": resolved_boundary,
                    "boundary_resolution_status": boundary_status,
                    "current_database_presence": "PRESENT" if db else "MISSING_CURRENT_DATABASE",
                    "current_database_hunt_name": db.get("hunt_name", ""),
                    "current_database_species": db.get("species", ""),
                    "current_database_boundary_id": db.get("boundary_id", ""),
                    "display_boundary_id": source_row.get("display_boundary_id", ""),
                    "hunt_boundary_crosswalk_id": source_row.get("hunt_boundary_crosswalk_id", ""),
                    "split_index_boundary_id": source_row.get("split_index_boundary_id", ""),
                    "direct_hunt_code_geojson": source_row.get("direct_hunt_code_geojson", "false"),
                    "direct_boundary_id_geojson": source_row.get("direct_boundary_id_geojson", "false"),
                    "source_family_values": row.get("source_family_values", ""),
                    "source_files": row.get("source_files", ""),
                    "year_document_status": row.get("year_document_status", ""),
                    "notes": row.get("notes", ""),
                }
            )

    year_unresolved = [
        row for row in year_rows
        if row["boundary_resolution_status"] in {"", "BOUNDARY_ID_MISSING_FROM_RUNTIME_SOURCES", "BOUNDARY_ID_CONFLICT_REVIEW"}
        or row["current_database_presence"] == "MISSING_CURRENT_DATABASE"
    ]

    write_csv(CURRENT_OUT, current_rows, CURRENT_COLUMNS)
    write_csv(YEAR_OUT, year_rows, YEAR_COLUMNS)
    write_csv(YEAR_UNRESOLVED_OUT, year_unresolved, YEAR_COLUMNS)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "current_325": {
            "rows": len(current_rows),
            "can_close_identity_boundary": sum(1 for row in current_rows if row["can_close_identity_boundary"] == "true"),
            "boundary_status_counts": dict(Counter(row["boundary_resolution_status"] for row in current_rows)),
            "database_status_counts": dict(Counter(row["database_status"] for row in current_rows)),
        },
        "year_documents": {
            "rows": len(year_rows),
            "unresolved_or_current_missing_rows": len(year_unresolved),
            "by_report_year": dict(Counter(row["report_year"] for row in year_rows)),
            "current_database_presence_counts": dict(Counter(row["current_database_presence"] for row in year_rows)),
            "boundary_status_counts": dict(Counter(row["boundary_resolution_status"] for row in year_rows)),
        },
        "boundary_sources_used": [
            DISPLAY_BOUNDARY.relative_to(ROOT).as_posix(),
            HUNT_BOUNDARY.relative_to(ROOT).as_posix(),
            BOUNDARY_ID_TO_CODE.relative_to(ROOT).as_posix(),
            SPLIT_INDEX.relative_to(ROOT).as_posix(),
            "processed_data/boundaries/*.geojson",
        ],
        "outputs": {
            "current_325_reconciliation": CURRENT_OUT.relative_to(ROOT).as_posix(),
            "yearly_reconciliation": YEAR_OUT.relative_to(ROOT).as_posix(),
            "yearly_unresolved": YEAR_UNRESOLVED_OUT.relative_to(ROOT).as_posix(),
            "summary": SUMMARY_OUT.relative_to(ROOT).as_posix(),
        },
        "notes": [
            "This pass only reconciles hunt-code and boundary identity.",
            "No DATABASE.csv values were modified.",
        ],
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
