#!/usr/bin/env python3
"""Rebuild runtime hunt-master and split-index artifacts from DATABASE.csv."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
RESEARCH_SUMMARY = ROOT / "processed_data" / "hunt_research_2026_summary.json"
SPLIT_DIR = ROOT / "processed_data" / "hunt_research_2026_split"
SPLIT_HUNTS_DIR = SPLIT_DIR / "hunts"
AUDIT_PATH = ROOT / "processed_data" / "audits" / "runtime_website_universe_update_matrix.csv"
SUMMARY_PATH = ROOT / "processed_data" / "audits" / "runtime_website_universe_update_summary.json"

HUNT_MASTER_TARGETS = [
    ROOT / "data" / "hunt-master-canonical-2026-foundation.json",
    ROOT / "data" / "hunt-master-canonical-2026-source-of-truth.json",
    ROOT / "data" / "hunt-master-canonical-2026-database-candidate.json",
    ROOT / "processed_data" / "hunt-master-canonical-2026-source-of-truth.json",
]

HUNT_MASTER_CSV_TARGETS = [
    ROOT / "data" / "hunt-master-canonical-2026-foundation.csv",
    ROOT / "data" / "hunt-master-canonical-2026-source-of-truth.csv",
    ROOT / "data" / "hunt-master-canonical-2026-database-candidate.csv",
    ROOT / "processed_data" / "hunt-master-canonical-2026-source-of-truth.csv",
]

RUNTIME_CANDIDATES = [
    ("BUILDER_FIRST_LOAD", "data/hunt-master-canonical-2026-foundation.json", "REPO_PUBLIC"),
    ("BUILDER_FALLBACK", "data/hunt-master-canonical-2026-source-of-truth.json", "REPO_PUBLIC"),
    ("BUILDER_CANDIDATE", "data/hunt-master-canonical-2026-database-candidate.json", "REPO_PUBLIC"),
    ("PROCESSED_CURRENT_MASTER", "processed_data/hunt-master-canonical-2026-source-of-truth.json", "REPO_PUBLIC"),
    ("PROCESSED_CURRENT_MASTER_CSV", "processed_data/hunt-master-canonical-2026-source-of-truth.csv", "REPO_PUBLIC"),
    ("RESEARCH_CONTRACT", "processed_data/hunt_research_2026.json", "CLOUDFLARE_R2_PUBLIC"),
    ("RESEARCH_SUMMARY", "processed_data/hunt_research_2026_summary.json", "CLOUDFLARE_R2_PUBLIC"),
    ("RESEARCH_LADDER", "processed_data/hunt_research_2026_ladder.json", "CLOUDFLARE_R2_PUBLIC"),
    ("RESEARCH_LADDER_PREFERENCE", "processed_data/hunt_research_2026_ladder_preference.json", "CLOUDFLARE_R2_PUBLIC"),
    ("RESEARCH_LADDER_BONUS_MAX_RANDOM", "processed_data/hunt_research_2026_ladder_bonus_max_random.json", "CLOUDFLARE_R2_PUBLIC"),
    ("RESEARCH_SPLIT_INDEX", "processed_data/hunt_research_2026_split/hunt_research_2026.index.json", "CLOUDFLARE_R2_PUBLIC"),
    ("DRAW_REALITY_ENGINE", "processed_data/draw_reality_engine.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("DRAW_REALITY_ENGINE_V2", "processed_data/draw_reality_engine_v2.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("DRAW_REALITY_ENGINE_PREDICTIVE_V2", "processed_data/draw_reality_engine_predictive_v2.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("DRAW_REALITY_VIEW", "processed_data/draw_reality_view.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("ML_DRAW_PREDICTIONS_V1", "processed_data/ml_draw_predictions_v1.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("HUNT_MASTER_ENRICHED", "processed_data/hunt_master_enriched.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("HUNT_UNIT_REFERENCE_LINKED", "processed_data/hunt_unit_reference_linked.csv", "CLOUDFLARE_R2_PUBLIC"),
    ("POINT_LADDER_VIEW", "processed_data/point_ladder_view.csv", "CLOUDFLARE_R2_PUBLIC"),
]


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def clean(value: object) -> str:
    text = "" if value is None else str(value).strip()
    if text.endswith(".0"):
        head = text[:-2]
        if head and (head.isdigit() or (head.startswith("-") and head[1:].isdigit())):
            return head
    return text


def first(*values: object) -> str:
    for value in values:
        text = clean(value)
        if text:
            return text
    return ""


def read_database() -> list[dict[str, str]]:
    with DATABASE.open("r", encoding="utf-8-sig", newline="") as fh:
        rows = [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(fh)]
    seen: set[str] = set()
    duplicates: list[str] = []
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            raise ValueError("DATABASE.csv contains a blank hunt_code row.")
        if code in seen:
            duplicates.append(code)
        seen.add(code)
    if duplicates:
        raise ValueError(f"DATABASE.csv contains duplicate hunt_code values: {duplicates[:10]}")
    return sorted(rows, key=lambda row: clean(row.get("hunt_code")).upper())


def read_research_summary() -> dict[str, list[dict[str, object]]]:
    if not RESEARCH_SUMMARY.exists():
        return {}
    rows = json.loads(RESEARCH_SUMMARY.read_text(encoding="utf-8"))
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code:
            grouped[code].append(row)
    return dict(grouped)


def to_runtime_record(row: dict[str, str], generated_at: str) -> dict[str, object]:
    code = clean(row.get("hunt_code")).upper()
    boundary_id = first(row.get("boundary_id"), row.get("boundaryId"), row.get("BoundaryID"))
    hunt_name = first(row.get("hunt_name"), row.get("unit_name"), code)
    season = first(row.get("season"), row.get("season_dates"))
    total_2026 = first(row.get("permit_allotment_2026_total"), row.get("permits_2026_total"))
    res_2026 = first(row.get("permit_allotment_2026_res"), row.get("permits_2026_res"))
    nr_2026 = first(row.get("permit_allotment_2026_nr"), row.get("permits_2026_nr"))
    record = {
        "hunt_code": code,
        "boundary_id": boundary_id,
        "hunt_name": hunt_name,
        "species": first(row.get("species")),
        "hunt_class": first(row.get("hunt_class")),
        "hunt_type": first(row.get("hunt_type")),
        "draw_family": first(row.get("draw_2026_system_type")),
        "weapon": first(row.get("weapon")),
        "sex_type": first(row.get("sex_type")),
        "season": season,
        "access_type": first(row.get("access_type"), "Public"),
        "permits_2024_res": first(row.get("permits_2024_res")),
        "permits_2024_nr": first(row.get("permits_2024_nr")),
        "permits_2024_total": first(row.get("permits_2024_total")),
        "permits_2024_source": first(row.get("permits_2024_source")),
        "permits_2025_res": first(row.get("permits_2025_res")),
        "permits_2025_nr": first(row.get("permits_2025_nr")),
        "permits_2025_total": first(row.get("permits_2025_total")),
        "permits_2025_source": first(row.get("permits_2025_source")),
        "permits_2026_res": res_2026,
        "permits_2026_nr": nr_2026,
        "permits_2026_total": total_2026,
        "permits_2026_source": first(row.get("permits_2026_source"), row.get("permit_allotment_2026_source")),
        "permits_2026_draw_source": first(row.get("permits_2026_draw_source")),
        "permit_allotment_2026_res": res_2026,
        "permit_allotment_2026_nr": nr_2026,
        "permit_allotment_2026_total": total_2026,
        "permit_allotment_2026_source": first(row.get("permit_allotment_2026_source")),
        "permit_allotment_2026_source_file": first(row.get("permit_allotment_2026_source_file")),
        "permit_allotment_2026_status": first(row.get("permit_allotment_2026_status")),
        "draw_2026_system_type": first(row.get("draw_2026_system_type")),
        "draw_2025_bg_pdf_page": first(row.get("draw_2025_bg_pdf_page")),
        "draw_2025_bg_report_page": first(row.get("draw_2025_bg_report_page")),
        "draw_2025_type": first(row.get("draw_2025_type")),
        "percent_harvest_success_previous_hunting_season": first(row.get("percent_harvest_success_previous_hunting_season")),
        "average_harvest_age": first(row.get("average_harvest_age")),
        "current_age_3yr_average": first(row.get("current_age_3yr_average")),
        "average_harvest_age_source_file": first(row.get("average_harvest_age_source_file")),
        "average_harvest_age_review_status": first(row.get("average_harvest_age_review_status")),
        "dwr_huntplanner_age_objective": first(row.get("dwr_huntplanner_age_objective")),
        "dwr_huntplanner_population_objective": first(row.get("dwr_huntplanner_population_objective")),
        "dwr_huntplanner_current_population_estimate": first(row.get("dwr_huntplanner_current_population_estimate")),
        "conservation_permits_2026_total": first(row.get("conservation_permits_2026_total")),
        "conservation_permits_2026_source": first(row.get("conservation_permits_2026_source")),
        "notes": first(row.get("NOTES"), row.get("notes")),
        "source_authority": "DATABASE.csv",
        "source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
        "data_status": "CURRENT_DATABASE_CANONICAL",
        "generated_at": generated_at,
    }
    record.update(
        {
            "huntCode": code,
            "code": code,
            "title": hunt_name,
            "huntTitle": hunt_name,
            "unitName": hunt_name,
            "unitCode": boundary_id or code,
            "boundaryId": boundary_id,
            "boundaryID": boundary_id,
            "BoundaryID": boundary_id,
            "boundary_id_numeric": boundary_id,
            "totalPermits": total_2026,
            "permitsTotal": total_2026,
            "quota": total_2026,
            "dates": season,
            "sex": first(row.get("sex_type")),
            "sexType": first(row.get("sex_type")),
            "type": first(row.get("hunt_type")),
            "category": first(row.get("hunt_class")),
            "Weapon": first(row.get("weapon")),
            "boundaryLink": f"https://dwrapps.utah.gov/huntboundary/hbstart?HN={code}",
        }
    )
    return record


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_master_csv(path: Path, records: list[dict[str, object]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                seen.add(key)
                fields.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def preferred_summary(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return {}
    for residency in ("Resident", "All", "Nonresident"):
        for row in rows:
            if clean(row.get("residency")).lower() == residency.lower():
                return row
    return rows[0]


def rebuild_split(records: list[dict[str, object]], research_by_code: dict[str, list[dict[str, object]]], generated_at: str) -> dict[str, object]:
    SPLIT_HUNTS_DIR.mkdir(parents=True, exist_ok=True)
    db_codes = {str(record["hunt_code"]).upper() for record in records}
    stale_files = []
    for detail_file in SPLIT_HUNTS_DIR.glob("*.json"):
        if detail_file.stem.upper() not in db_codes:
            stale_files.append(detail_file.name)
            detail_file.unlink()

    index_rows: list[dict[str, object]] = []
    detail_count = 0
    for record in records:
        code = str(record["hunt_code"]).upper()
        summary_rows = research_by_code.get(code, [])
        summary = preferred_summary(summary_rows)
        detail_path = f"hunts/{code}.json"
        detail_file = SPLIT_HUNTS_DIR / f"{code}.json"
        existing: dict[str, object] = {}
        if detail_file.exists():
            try:
                loaded = json.loads(detail_file.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    existing = loaded
            except json.JSONDecodeError:
                existing = {}
        detail = {
            **existing,
            **record,
            "detail_path": detail_path,
            "research_summary_rows": summary_rows,
            "research_summary_row_count": len(summary_rows),
            "split_source": "DATABASE.csv + processed_data/hunt_research_2026_summary.json",
            "split_rebuilt_at": generated_at,
        }
        write_json(detail_file, detail)
        detail_count += 1

        index_row = {
            "hunt_code": code,
            "species": first(record.get("species")),
            "hunt_name": first(record.get("hunt_name")),
            "hunt_type": first(record.get("hunt_type")),
            "hunt_class": first(record.get("hunt_class")),
            "weapon": first(record.get("weapon")),
            "sex_type": first(record.get("sex_type")),
            "boundary_id": first(record.get("boundary_id")),
            "permits_2026_res": first(record.get("permits_2026_res")),
            "permits_2026_nr": first(record.get("permits_2026_nr")),
            "permits_2026_total": first(record.get("permits_2026_total")),
            "permits_2025_res": first(record.get("permits_2025_res")),
            "permits_2025_nr": first(record.get("permits_2025_nr")),
            "permits_2025_total": first(record.get("permits_2025_total")),
            "availability_status": first(summary.get("availability_status"), summary.get("status")),
            "draw_2026_system_type": first(record.get("draw_2026_system_type"), summary.get("draw_2026_system_type")),
            "average_harvest_age": first(record.get("average_harvest_age"), summary.get("average_harvest_age")),
            "current_age_3yr_average": first(record.get("current_age_3yr_average"), summary.get("current_age_3yr_average")),
            "research_summary_row_count": len(summary_rows),
            "detail_path": detail_path,
        }
        index_rows.append(index_row)

    write_json(SPLIT_DIR / "hunt_research_2026.index.json", index_rows)
    write_json(
        SPLIT_DIR / "manifest.json",
        {
            "count": len(index_rows),
            "index_file": "hunt_research_2026.index.json",
            "detail_dir": "hunts",
            "canonical_source": "DATABASE.csv + processed_data/hunt_research_2026_summary.json",
            "status": "REBUILT_CURRENT_DATABASE_CANONICAL",
            "generated_at": generated_at,
            "notes": "Split index/detail files now align to the 2026 DATABASE.csv hunt-code universe. Legacy extra codes were removed from the split detail directory.",
        },
    )
    write_json(
        SPLIT_DIR / "split-summary.json",
        {
            "count": len(index_rows),
            "index_bytes": (SPLIT_DIR / "hunt_research_2026.index.json").stat().st_size,
            "detail_files": detail_count,
            "stale_old_detail_files_removed": len(stale_files),
            "stale_removed_examples": stale_files[:25],
            "generated_at": generated_at,
        },
    )
    return {
        "split_index_count": len(index_rows),
        "split_detail_files": detail_count,
        "stale_split_detail_files_removed": len(stale_files),
    }


def count_json_codes(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload if isinstance(payload, list) else payload.get("records", [])
    codes = {clean(row.get("hunt_code") or row.get("huntCode") or row.get("code")).upper() for row in rows if isinstance(row, dict)}
    codes.discard("")
    return len(rows), len(codes)


def count_csv_codes(path: Path) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = 0
        codes: set[str] = set()
        for row in reader:
            rows += 1
            code = clean(row.get("hunt_code") or row.get("huntCode") or row.get("code")).upper()
            if code:
                codes.add(code)
    return rows, len(codes)


def is_lfs_pointer(path: Path) -> bool:
    if not path.exists() or path.is_dir():
        return False
    with path.open("rb") as fh:
        return fh.read(120).startswith(b"version https://git-lfs.github.com/spec/v1")


def write_runtime_audit(db_code_count: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for label, rel_path, target in RUNTIME_CANDIDATES:
        path = ROOT / rel_path
        exists = path.exists()
        size = path.stat().st_size if exists else ""
        row_count = ""
        code_count = ""
        if exists and path.suffix.lower() == ".json" and path.is_file():
            try:
                row_count, code_count = count_json_codes(path)
            except Exception as exc:  # noqa: BLE001
                row_count, code_count = "PARSE_ERROR", f"{type(exc).__name__}: {exc}"
        elif exists and path.suffix.lower() == ".csv":
            row_count, code_count = count_csv_codes(path)
        status = "OK"
        if not exists:
            status = "MISSING"
        elif is_lfs_pointer(path):
            status = "LFS_POINTER_BLOCKER"
        elif isinstance(code_count, int) and code_count and label in {
            "BUILDER_FIRST_LOAD",
            "BUILDER_FALLBACK",
            "BUILDER_CANDIDATE",
            "PROCESSED_CURRENT_MASTER",
            "PROCESSED_CURRENT_MASTER_CSV",
            "RESEARCH_SUMMARY",
            "RESEARCH_SPLIT_INDEX",
        } and code_count != db_code_count:
            status = "CODE_COUNT_MISMATCH"
        rows.append(
            {
                "asset_label": label,
                "path": rel_path,
                "exists": "yes" if exists else "no",
                "size_bytes": size,
                "row_count": row_count,
                "unique_hunt_codes": code_count,
                "database_unique_hunt_codes": db_code_count,
                "target_delivery": target,
                "lfs_pointer": "yes" if exists and is_lfs_pointer(path) else "no",
                "status": status,
            }
        )
    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def main() -> None:
    generated_at = utc_now()
    db_rows = read_database()
    records = [to_runtime_record(row, generated_at) for row in db_rows]
    db_codes = {str(record["hunt_code"]).upper() for record in records}
    research_by_code = read_research_summary()
    missing_research_codes = sorted(db_codes - set(research_by_code))
    extra_research_codes = sorted(set(research_by_code) - db_codes)
    if missing_research_codes or extra_research_codes:
        raise ValueError(
            "Research summary is not aligned to DATABASE.csv: "
            f"missing={len(missing_research_codes)} extra={len(extra_research_codes)}"
        )

    for path in HUNT_MASTER_TARGETS:
        write_json(path, records)
    for path in HUNT_MASTER_CSV_TARGETS:
        write_master_csv(path, records)

    split_summary = rebuild_split(records, research_by_code, generated_at)
    audit_rows = write_runtime_audit(len(db_codes))
    status_counts: dict[str, int] = defaultdict(int)
    for row in audit_rows:
        status_counts[str(row["status"])] += 1
    write_json(
        SUMMARY_PATH,
        {
            "generated_at": generated_at,
            "database_rows": len(db_rows),
            "database_unique_hunt_codes": len(db_codes),
            "hunt_master_targets_written": [str(path.relative_to(ROOT)).replace("\\", "/") for path in HUNT_MASTER_TARGETS + HUNT_MASTER_CSV_TARGETS],
            **split_summary,
            "runtime_audit": str(AUDIT_PATH.relative_to(ROOT)).replace("\\", "/"),
            "status_counts": dict(sorted(status_counts.items())),
        },
    )
    print(f"Rebuilt runtime hunt master records: {len(records)}")
    print(f"Rebuilt split index records: {split_summary['split_index_count']}")
    print(f"Removed stale split detail files: {split_summary['stale_split_detail_files_removed']}")
    print(f"Wrote audit: {AUDIT_PATH.relative_to(ROOT)}")
    print(f"Wrote summary: {SUMMARY_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
