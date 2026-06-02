from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SOURCE_2024 = ROOT / "data_truth/draw_results_truth/normalized/draw_odds_2024_model_target_2025_permit_totals.csv"
NEXT_YEAR_SOURCES = [
    ROOT / "data_truth/draw_results_truth/normalized/le_deer_2025_draw_results_model_target_2026_permit_totals.csv",
    ROOT / "data_truth/draw_results_truth/normalized/oil_2025_draw_results_model_target_2026_permit_totals.csv",
]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
TRUSTED_CROSSWALK = (
    ROOT / "data_truth/crosswalk_truth/normalized/current_to_historical_hunt_code_crosswalk_2026.csv"
)

OUT_CSV = ROOT / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years.csv"
DROPPED_CSV = ROOT / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_dropped_review.csv"
SUMMARY_JSON = ROOT / "data_truth/crosswalk_truth/validation/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years_summary.json"
REPORT_MD = ROOT / "processed_data/hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years.md"

HISTORICAL_ONLY_NOTE = "HISTORICAL_2025_DRAW_ONLY_NOT_ACTIVE_2026"
NEXT_YEAR_PDF_PREFIXES = {"BI", "DB", "DS", "GO", "MB", "RS"}

FIELDS = [
    "source_hunt_code",
    "source_model_target_year",
    "source_hunt_name",
    "source_species",
    "source_sex_type",
    "source_weapon",
    "source_hunt_type",
    "source_boundary_id",
    "source_total_public_draw_permits",
    "next_year_pdf_coverage_status",
    "same_code_in_2025_pdf",
    "same_code_current_database_presence",
    "crosswalk_status",
    "mapped_hunt_code",
    "mapped_hunt_name",
    "mapped_boundary_id",
    "mapped_source",
    "mapped_confidence",
    "candidate_hunt_codes",
    "candidate_boundary_ids",
    "candidate_reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def prefix(code: str) -> str:
    match = re.match(r"^[A-Z]+", code or "")
    return match.group(0) if match else ""


def normalize_name(value: str) -> str:
    text = (value or "").lower()
    text = text.replace("hunter's", "hunters").replace("hunter\u2019s", "hunters")
    text = re.sub(r"\bpage\s+\d+\b", " ", text)
    text = re.sub(r"\bcwmu\b", " ", text)
    text = re.sub(r"\blimited[- ]entry\b|\bpremium\b|\bmanagement\b|\bcactus\b|\bexpo\b", " ", text)
    text = re.sub(r"\bbuck deer\b|\btwo doe antlerless deer\b|\bantlerless elk\b|\bbull elk\b|\bbull moose\b", " ", text)
    text = re.sub(r"\bbison\s*\([^)]*\)\b|\bdesert bighorn sheep\b|\brocky mountain bighorn sheep\b", " ", text)
    text = re.sub(r"\bmountain goat\b|\bbuck pronghorn\b|\bdoe pronghorn\b", " ", text)
    text = re.sub(
        r"\b(any legal weapon|muzzleloader|archery|multiseason|restricted rifle|restricted muzzleloader|restricted archery)\b",
        " ",
        text,
    )
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def weapon_group(value: str) -> str:
    text = (value or "").lower()
    if "muzzle" in text:
        return "muzzleloader"
    if "archery" in text:
        return "archery"
    if "multi" in text:
        return "multiseason"
    if "rifle" in text or "legal weapon" in text or "alw" in text:
        return "any legal weapon"
    return text.strip()


def is_historical_only(row: dict[str, str]) -> bool:
    return row.get("NOTES", "").strip() == HISTORICAL_ONLY_NOTE or row.get("permit_allotment_2026_status", "").strip() == "HISTORICAL_2025_ONLY_NOT_ACTIVE_2026"


def metadata_from_source(source: dict[str, str], db: dict[str, str]) -> dict[str, str]:
    return {
        "hunt_name": db.get("hunt_name") or source.get("database_hunt_name") or source.get("hunt_name", ""),
        "species": db.get("species", ""),
        "sex_type": db.get("sex_type", ""),
        "weapon": db.get("weapon", ""),
        "hunt_type": db.get("hunt_type", ""),
        "boundary_id": db.get("boundary_id") or source.get("boundary_id", ""),
    }


def row_key(row: dict[str, str]) -> tuple[str, str, str, str]:
    return (
        normalize_name(row.get("hunt_name", "")),
        row.get("species", "").lower(),
        row.get("sex_type", "").lower(),
        weapon_group(row.get("weapon", "")),
    )


def name_tokens(value: str) -> set[str]:
    stop = {
        "north",
        "south",
        "east",
        "west",
        "mtn",
        "mtns",
        "mountain",
        "mountains",
        "canyon",
        "creek",
        "valley",
        "desert",
        "bear",
        "springs",
        "peak",
        "ranch",
        "willow",
    }
    return {token for token in normalize_name(value).split() if len(token) >= 4 and token not in stop}


def parse_historical_code_list(value: str) -> list[str]:
    return [part.strip().upper() for part in (value or "").split("|") if part.strip()]


def split_crosswalk_codes(row: dict[str, str]) -> list[str]:
    codes: list[str] = []
    codes.extend(parse_historical_code_list(row.get("historical_hunt_code", "")))
    for code in parse_historical_code_list(row.get("candidate_historical_codes", "")):
        if code not in codes:
            codes.append(code)
    return codes


def crosswalk_rank(confidence: str) -> int:
    confidence = (confidence or "").upper().strip()
    if confidence == "HIGH":
        return 3
    if confidence == "MEDIUM":
        return 2
    if confidence == "LOW":
        return 1
    return 0


def build_trusted_crosswalk_index(database_by_code: dict[str, dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    if not TRUSTED_CROSSWALK.exists():
        return {}

    index: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(TRUSTED_CROSSWALK):
        source_codes = split_crosswalk_codes(row)
        current_code = (row.get("current_hunt_code") or "").strip().upper()
        if not source_codes or not current_code:
            continue

        db_row = database_by_code.get(current_code, {})
        if not db_row:
            continue

        payload = {
            "current_hunt_code": current_code,
            "current_hunt_name": row.get("current_hunt_name", ""),
            "current_boundary_id": (db_row.get("boundary_id") or "").strip(),
            "mapping_confidence": row.get("mapping_confidence", ""),
            "mapping_method": row.get("mapping_method", ""),
            "crosswalk_status": row.get("crosswalk_status", ""),
            "data_quality_grade": row.get("data_quality_grade", ""),
            "historical_hunt_code": row.get("historical_hunt_code", ""),
        }

        for source_code in source_codes:
            index.setdefault(source_code, []).append(payload)

    for rows in index.values():
        rows.sort(
            key=lambda payload: (
                crosswalk_rank(payload.get("mapping_confidence", "")),
                1 if payload.get("current_hunt_code") else 0,
            ),
            reverse=True,
        )
    return index


def mapped_from_crosswalk(
    source_code: str,
    crosswalk_index: dict[str, list[dict[str, str]]],
    active_db_by_code: dict[str, dict[str, str]],
    db_by_code: dict[str, dict[str, str]],
) -> tuple[dict[str, str] | None, str]:
    source_code = (source_code or "").upper().strip()
    if not source_code:
        return None, ""

    rows = crosswalk_index.get(source_code, [])
    if not rows:
        return None, ""

    active_rows: list[dict[str, str]] = []
    inactive_rows: list[dict[str, str]] = []
    for row in rows:
        target_code = row["current_hunt_code"]
        if target_code in active_db_by_code:
            active_rows.append(row)
        elif target_code in db_by_code:
            inactive_rows.append(row)

    preferred_rows = active_rows if active_rows else inactive_rows
    if not preferred_rows:
        return None, ""

    mapped_row = preferred_rows[0]
    target_code = mapped_row["current_hunt_code"]
    target_db = db_by_code.get(target_code, {})
    source = (
        "TRUSTED_CURRENT_TO_HISTORICAL_CROSSWALK_ACTIVE_DB"
        if active_rows
        else "TRUSTED_CURRENT_TO_HISTORICAL_CROSSWALK_DB"
    )
    return (
        {
            "mapped_hunt_code": target_code,
            "mapped_hunt_name": target_db.get("hunt_name", mapped_row.get("current_hunt_name", "")),
            "mapped_boundary_id": target_db.get("boundary_id", mapped_row.get("current_boundary_id", "")),
            "mapped_source": source,
            "mapped_confidence": mapped_row.get("mapping_confidence", "HIGH"),
            "candidate_reason": (
                f"trusted current-to-historical mapping via {source} "
                f"(historical source: {mapped_row.get('historical_hunt_code','')})"
            ),
        },
        source,
    )


def candidate_payload(row: dict[str, str], source: str, confidence: str, reason: str) -> dict[str, str]:
    return {
        "mapped_hunt_code": row.get("hunt_code", ""),
        "mapped_hunt_name": row.get("hunt_name", ""),
        "mapped_boundary_id": row.get("boundary_id", ""),
        "mapped_source": source,
        "mapped_confidence": confidence,
        "candidate_reason": reason,
    }


def find_candidates(
    source_row: dict[str, str],
    pools: list[tuple[str, list[dict[str, str]]]],
) -> list[dict[str, str]]:
    source_key = row_key(source_row)
    source_name, source_species, source_sex, source_weapon = source_key
    source_tokens = name_tokens(source_row.get("hunt_name", ""))
    source_boundary = source_row.get("boundary_id", "")
    candidates: list[dict[str, str]] = []

    for pool_name, rows in pools:
        for row in rows:
            target_key = row_key(row)
            target_name, target_species, target_sex, target_weapon = target_key
            if source_boundary and row.get("boundary_id") == source_boundary and (source_species, source_sex, source_weapon) == (target_species, target_sex, target_weapon):
                candidates.append(candidate_payload(row, pool_name, "HIGH", "same boundary/species/sex/weapon group"))
            elif source_key == target_key:
                candidates.append(candidate_payload(row, pool_name, "HIGH", "same normalized name/species/sex/weapon group"))
            elif source_species == target_species and source_sex == target_sex and source_weapon == target_weapon and source_name:
                if source_name in target_name or target_name in source_name:
                    candidates.append(candidate_payload(row, pool_name, "MEDIUM", "partial normalized name/species/sex/weapon group"))
                elif source_tokens & name_tokens(row.get("hunt_name", "")):
                    candidates.append(candidate_payload(row, pool_name, "MEDIUM", "shared distinctive name token/species/sex/weapon group"))

    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for candidate in candidates:
        code = candidate["mapped_hunt_code"]
        if code in seen:
            continue
        seen.add(code)
        unique.append(candidate)
    return unique[:5]


def build() -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    source_rows = read_csv(SOURCE_2024)
    database_rows = read_csv(DATABASE)
    db_by_code = {row["hunt_code"]: row for row in database_rows if row.get("hunt_code")}
    active_db_rows = [row for row in database_rows if row.get("hunt_code") and not is_historical_only(row)]
    active_db_by_code = {row["hunt_code"]: row for row in active_db_rows}
    crosswalk_index = build_trusted_crosswalk_index(db_by_code)

    next_rows: list[dict[str, str]] = []
    for path in NEXT_YEAR_SOURCES:
        for row in read_csv(path):
            row["next_year_source_file"] = path.relative_to(ROOT).as_posix()
            next_rows.append(row)
    next_by_code = {row["hunt_code"]: row for row in next_rows if row.get("hunt_code")}

    output: list[dict[str, Any]] = []
    dropped: list[dict[str, Any]] = []
    for source in source_rows:
        code = source["hunt_code"]
        db = db_by_code.get(code, {})
        meta = metadata_from_source(source, db)
        row_for_match = {
            "hunt_code": code,
            "hunt_name": meta["hunt_name"],
            "species": meta["species"],
            "sex_type": meta["sex_type"],
            "weapon": meta["weapon"],
            "boundary_id": meta["boundary_id"],
        }
        coverage = "NEXT_YEAR_PDF_FAMILY_AVAILABLE" if prefix(code) in NEXT_YEAR_PDF_PREFIXES else "NO_NEXT_YEAR_PDF_FAMILY_AVAILABLE"
        same_next = next_by_code.get(code)
        active_same = active_db_by_code.get(code)
        mapped_crosswalk, mapped_crosswalk_source = mapped_from_crosswalk(
            code,
            crosswalk_index,
            active_db_by_code,
            db_by_code,
        )
        database_presence = "CURRENT_ACTIVE" if active_same else ("HISTORICAL_ONLY" if db else "NOT_IN_DATABASE")
        candidates = find_candidates(row_for_match, [("2025_PDF_MODEL_TARGET_2026", next_rows), ("CURRENT_ACTIVE_DATABASE_2026", active_db_rows)])

        if same_next and active_same:
            status = "SAME_CODE_IN_2025_PDF_AND_CURRENT_ACTIVE"
            mapped = candidate_payload(active_same, "CURRENT_ACTIVE_DATABASE_2026", "HIGH", "same hunt code retained")
        elif same_next:
            status = "SAME_CODE_IN_2025_PDF_BUT_DATABASE_MARKED_HISTORICAL_ONLY_REVIEW"
            mapped = candidate_payload(same_next, "2025_PDF_MODEL_TARGET_2026", "HIGH", "same hunt code appears in next-year PDF")
        elif active_same:
            status = "SAME_CODE_CURRENT_ACTIVE_NO_NEXT_YEAR_PDF_MATCH"
            mapped = candidate_payload(active_same, "CURRENT_ACTIVE_DATABASE_2026", "HIGH", "same hunt code remains current active")
        elif mapped_crosswalk:
            mapped = mapped_crosswalk
            if mapped_crosswalk_source.endswith("_ACTIVE_DB"):
                status = "MAPPED_BY_TRUSTED_CURRENT_HISTORICAL_CROSSWALK_TO_CURRENT_ACTIVE"
            else:
                status = "MAPPED_BY_TRUSTED_CURRENT_HISTORICAL_CROSSWALK_DB_ONLY"
        elif candidates:
            mapped = candidates[0]
            status = "REPLACED_BY_NEXT_YEAR_OR_CURRENT_CANDIDATE"
        elif coverage == "NEXT_YEAR_PDF_FAMILY_AVAILABLE":
            status = "DROPPED_NO_NEXT_YEAR_PDF_OR_CURRENT_ACTIVE_MATCH"
            mapped = {"mapped_hunt_code": "", "mapped_hunt_name": "", "mapped_boundary_id": "", "mapped_source": "", "mapped_confidence": "HIGH", "candidate_reason": "covered by next-year PDF family but no next-year/current-active match"}
        else:
            status = "DROPPED_NO_CURRENT_ACTIVE_MATCH_NO_NEXT_YEAR_PDF_FAMILY"
            mapped = {"mapped_hunt_code": "", "mapped_hunt_name": "", "mapped_boundary_id": "", "mapped_source": "", "mapped_confidence": "MEDIUM", "candidate_reason": "no current active match; no next-year PDF family available for direct confirmation"}

        candidate_codes = [candidate["mapped_hunt_code"] for candidate in candidates]
        candidate_boundaries = [candidate["mapped_boundary_id"] for candidate in candidates]
        if mapped_crosswalk and mapped.get("mapped_hunt_code"):
            if mapped["mapped_hunt_code"] not in candidate_codes:
                candidate_codes.insert(0, mapped["mapped_hunt_code"])
                candidate_boundaries.insert(0, mapped.get("mapped_boundary_id", ""))
        out = {
            "source_hunt_code": code,
            "source_model_target_year": source.get("model_target_year", "2025"),
            "source_hunt_name": meta["hunt_name"],
            "source_species": meta["species"],
            "source_sex_type": meta["sex_type"],
            "source_weapon": meta["weapon"],
            "source_hunt_type": meta["hunt_type"],
            "source_boundary_id": meta["boundary_id"],
            "source_total_public_draw_permits": source.get("total_public_draw_permits", ""),
            "next_year_pdf_coverage_status": coverage,
            "same_code_in_2025_pdf": "YES" if same_next else "NO",
            "same_code_current_database_presence": database_presence,
            "crosswalk_status": status,
            **mapped,
            "candidate_hunt_codes": ";".join(candidate_codes),
            "candidate_boundary_ids": ";".join(candidate_boundaries),
        }
        output.append(out)
        if status.startswith("DROPPED_") or status.endswith("_REVIEW"):
            dropped.append(out)

    summary = {
        "artifact": "hunt_code_crosswalk_2024_pdf_to_2025_pdf_model_years",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_2024_model_target_2025_rows": len(source_rows),
        "next_year_pdf_model_target_2026_rows": len(next_rows),
        "database_rows": len(database_rows),
        "current_active_database_rows": len(active_db_rows),
        "crosswalk_rows": len(output),
        "dropped_or_review_rows": len(dropped),
        "status_counts": dict(sorted(Counter(row["crosswalk_status"] for row in output).items())),
        "coverage_counts": dict(sorted(Counter(row["next_year_pdf_coverage_status"] for row in output).items())),
        "dropped_status_counts": dict(sorted(Counter(row["crosswalk_status"] for row in dropped).items())),
        "guardrail": "Read-only crosswalk. Dropped/replaced statuses are review evidence and do not modify DATABASE.csv or website feeds.",
        "outputs": {
            "crosswalk_csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "dropped_review_csv": DROPPED_CSV.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix(),
            "report_md": REPORT_MD.relative_to(ROOT).as_posix(),
        },
    }
    return output, dropped, summary


def write_report(summary: dict[str, Any], dropped: list[dict[str, Any]]) -> None:
    lines = [
        "# Hunt Code Crosswalk: 2024 PDF To 2025 PDF Model Years",
        "",
        "This read-only report maps 2024 PDF draw evidence for model year 2025 to the available 2025 PDF evidence for model year 2026 and the current active database universe.",
        "",
        f"- Source rows: `{summary['source_2024_model_target_2025_rows']}`",
        f"- Next-year PDF rows available: `{summary['next_year_pdf_model_target_2026_rows']}`",
        f"- Current active database rows: `{summary['current_active_database_rows']}`",
        f"- Dropped/review rows: `{summary['dropped_or_review_rows']}`",
        "",
        "## Status Counts",
        "",
    ]
    for status, count in summary["status_counts"].items():
        lines.append(f"- `{status}`: `{count}`")

    lines.extend(["", "## Dropped/Review Rows", "", "| Code | Status | Hunt | Species | Weapon | Candidate | Reason |", "|---|---|---|---|---|---|---|"])
    for row in dropped[:80]:
        lines.append(
            f"| {row['source_hunt_code']} | {row['crosswalk_status']} | {row['source_hunt_name']} | "
            f"{row['source_species']} | {row['source_weapon']} | {row['mapped_hunt_code']} | {row['candidate_reason']} |"
        )
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    rows, dropped, summary = build()
    write_csv(OUT_CSV, rows, FIELDS)
    write_csv(DROPPED_CSV, dropped, FIELDS)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_report(summary, dropped)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
