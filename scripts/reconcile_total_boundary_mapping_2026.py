import csv
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


REPO = Path(__file__).resolve().parents[1]

DATABASE_CSV = REPO / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
SPLIT_INDEX_JSON = REPO / "processed_data/hunt_research_2026_split/hunt_research_2026.index.json"
SPLIT_DETAIL_DIR = REPO / "processed_data/hunt_research_2026_split/hunts"
BOUNDARY_DIR = REPO / "processed_data/boundaries"
AUDIT_DIR = REPO / "processed_data/audits"
AUDIT_JSON = AUDIT_DIR / "total_boundary_reconciliation_validation_2026.json"
AUDIT_CSV = AUDIT_DIR / "total_boundary_reconciliation_changes_2026.csv"


@dataclass
class ChangeRow:
    surface: str
    key: str
    hunt_code: str
    before_boundary_id: str
    after_boundary_id: str
    note: str


def clean(value) -> str:
    return str(value or "").strip()


def load_database_map() -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with DATABASE_CSV.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            hunt_code = clean(row.get("hunt_code")).upper()
            boundary_id = clean(row.get("boundary_id"))
            if hunt_code:
                mapping[hunt_code] = boundary_id
    return mapping


def load_split_rows() -> List[dict]:
    payload = json.loads(SPLIT_INDEX_JSON.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("split index is not a list")
    return payload


def write_split_rows(rows: List[dict]) -> None:
    SPLIT_INDEX_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def reconcile_split_index(db_map: Dict[str, str], changes: List[ChangeRow], report: dict) -> None:
    rows = load_split_rows()
    overlap = 0
    no_db_match = 0
    mismatch_before = 0
    updated = 0

    for row in rows:
        hunt_code = clean(row.get("hunt_code")).upper()
        split_boundary = clean(row.get("boundary_id"))
        db_boundary = db_map.get(hunt_code)
        if not hunt_code:
            continue
        if db_boundary is None:
            no_db_match += 1
            continue
        overlap += 1
        if split_boundary != db_boundary:
            mismatch_before += 1
            row["boundary_id"] = db_boundary
            updated += 1
            changes.append(
                ChangeRow(
                    surface="split_index",
                    key=hunt_code,
                    hunt_code=hunt_code,
                    before_boundary_id=split_boundary,
                    after_boundary_id=db_boundary,
                    note="aligned to DATABASE boundary_id",
                )
            )

    mismatch_after = 0
    for row in rows:
        hunt_code = clean(row.get("hunt_code")).upper()
        if not hunt_code or hunt_code not in db_map:
            continue
        if clean(row.get("boundary_id")) != db_map[hunt_code]:
            mismatch_after += 1

    write_split_rows(rows)
    report["split_index"] = {
        "rows_total": len(rows),
        "rows_overlapping_database": overlap,
        "rows_without_database_match": no_db_match,
        "mismatch_before": mismatch_before,
        "updated_rows": updated,
        "mismatch_after": mismatch_after,
    }


def reconcile_split_details(db_map: Dict[str, str], changes: List[ChangeRow], report: dict) -> None:
    files_total = 0
    files_for_db_hunt_codes = 0
    mismatch_before = 0
    updated = 0
    invalid_json = 0
    missing_for_db_hunts = 0

    detail_files = {p.stem.upper(): p for p in SPLIT_DETAIL_DIR.glob("*.json")}

    for hunt_code, db_boundary in db_map.items():
        path = detail_files.get(hunt_code)
        if path is None:
            missing_for_db_hunts += 1
            continue
        files_for_db_hunt_codes += 1
        files_total += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            invalid_json += 1
            continue
        if not isinstance(doc, dict):
            invalid_json += 1
            continue

        before = clean(doc.get("boundary_id"))
        if before != db_boundary:
            mismatch_before += 1
            doc["boundary_id"] = db_boundary
            md = doc.get("metadata")
            if isinstance(md, dict):
                if clean(md.get("boundary_id")) != db_boundary:
                    md["boundary_id"] = db_boundary
                if "candidate_boundary_id" in md:
                    md["candidate_boundary_id"] = db_boundary
            path.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            updated += 1
            changes.append(
                ChangeRow(
                    surface="split_detail",
                    key=path.name,
                    hunt_code=hunt_code,
                    before_boundary_id=before,
                    after_boundary_id=db_boundary,
                    note="aligned detail boundary_id to DATABASE",
                )
            )

    for hc, path in detail_files.items():
        if hc in db_map:
            continue
        files_total += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            invalid_json += 1

    mismatch_after = 0
    for hunt_code, db_boundary in db_map.items():
        path = detail_files.get(hunt_code)
        if path is None:
            continue
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if clean(doc.get("boundary_id")) != db_boundary:
            mismatch_after += 1

    report["split_detail"] = {
        "files_total": files_total,
        "files_for_database_hunt_codes": files_for_db_hunt_codes,
        "database_hunt_codes_missing_detail_file": missing_for_db_hunts,
        "invalid_json_files": invalid_json,
        "mismatch_before": mismatch_before,
        "updated_files": updated,
        "mismatch_after": mismatch_after,
    }


def reconcile_boundaries_metadata(db_map: Dict[str, str], changes: List[ChangeRow], report: dict) -> None:
    files_total = 0
    files_with_hunt_code = 0
    files_no_database_match = 0
    invalid_json = 0
    mismatch_before = 0
    updated = 0

    for path in BOUNDARY_DIR.glob("*.geojson"):
        files_total += 1
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            invalid_json += 1
            continue
        if not isinstance(doc, dict):
            invalid_json += 1
            continue
        md = doc.get("metadata")
        if not isinstance(md, dict):
            continue
        hunt_code = clean(md.get("hunt_code")).upper()
        if not hunt_code:
            continue
        files_with_hunt_code += 1
        db_boundary = db_map.get(hunt_code)
        if db_boundary is None:
            files_no_database_match += 1
            continue
        before = clean(md.get("boundary_id"))
        if before != db_boundary:
            mismatch_before += 1
            md["boundary_id"] = db_boundary
            if "candidate_boundary_id" in md:
                md["candidate_boundary_id"] = db_boundary
            doc["metadata"] = md
            path.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            updated += 1
            changes.append(
                ChangeRow(
                    surface="boundary_geojson_metadata",
                    key=path.name,
                    hunt_code=hunt_code,
                    before_boundary_id=before,
                    after_boundary_id=db_boundary,
                    note="aligned metadata.boundary_id to DATABASE",
                )
            )

    mismatch_after = 0
    for path in BOUNDARY_DIR.glob("*.geojson"):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        md = doc.get("metadata") if isinstance(doc, dict) else None
        if not isinstance(md, dict):
            continue
        hunt_code = clean(md.get("hunt_code")).upper()
        if not hunt_code or hunt_code not in db_map:
            continue
        if clean(md.get("boundary_id")) != db_map[hunt_code]:
            mismatch_after += 1

    report["boundaries_metadata"] = {
        "files_total": files_total,
        "files_with_hunt_code": files_with_hunt_code,
        "files_without_database_match": files_no_database_match,
        "invalid_json_files": invalid_json,
        "mismatch_before": mismatch_before,
        "updated_files": updated,
        "mismatch_after": mismatch_after,
    }


def write_change_csv(changes: List[ChangeRow]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_CSV.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["surface", "key", "hunt_code", "before_boundary_id", "after_boundary_id", "note"])
        for c in changes:
            writer.writerow([c.surface, c.key, c.hunt_code, c.before_boundary_id, c.after_boundary_id, c.note])


def main() -> None:
    db_map = load_database_map()
    changes: List[ChangeRow] = []
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "truth_source": str(DATABASE_CSV.relative_to(REPO)).replace("\\", "/"),
        "truth_hunt_code_count": len(db_map),
    }

    reconcile_split_index(db_map, changes, report)
    reconcile_split_details(db_map, changes, report)
    reconcile_boundaries_metadata(db_map, changes, report)

    report["total_changes"] = len(changes)
    report["change_breakdown"] = {
        "split_index": sum(1 for c in changes if c.surface == "split_index"),
        "split_detail": sum(1 for c in changes if c.surface == "split_detail"),
        "boundary_geojson_metadata": sum(1 for c in changes if c.surface == "boundary_geojson_metadata"),
    }
    report["audit_files"] = [
        str(AUDIT_JSON.relative_to(REPO)).replace("\\", "/"),
        str(AUDIT_CSV.relative_to(REPO)).replace("\\", "/"),
    ]
    report["notes"] = [
        "DATABASE boundary_id is authoritative in this reconciliation pass.",
        "Only boundary mapping fields were reconciled; permit fields were untouched.",
    ]

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    write_change_csv(changes)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
