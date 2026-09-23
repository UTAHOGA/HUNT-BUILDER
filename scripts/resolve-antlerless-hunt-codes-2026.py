from __future__ import annotations

import csv
import hashlib
import json
import os
import tempfile
import re
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber


ROOT = Path(__file__).resolve().parents[1]

SOURCE_PDF = ROOT / "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
HUNT_MASTER = ROOT / "processed_data/hunt_master_enriched.csv"
HUNT_MASTER_FALLBACKS = [
    ROOT / "data/hunt-master-canonical-2026-source-of-truth.csv",
    ROOT / "data/hunt-master-canonical-2026-foundation.csv",
    ROOT / "processed_data/hunt-master-canonical-2026-source-of-truth.csv",
]
def resolve_hunt_master_path():
    if HUNT_MASTER.exists():
        return HUNT_MASTER
    for fb in HUNT_MASTER_FALLBACKS:
        if fb.exists():
            print(f"Using fallback hunt master: {fb}")
            return fb
    return HUNT_MASTER

POINT_LADDER = ROOT / "processed_data/point_ladder_view.csv"
DRAW_REALITY = ROOT / "processed_data/draw_reality_engine.csv"
PREDICTIVE = ROOT / "processed_data/draw_reality_engine_predictive_v2.csv"
GAP_SCAN = ROOT / "processed_data/2026_hunt_code_family_gap_scan.csv"

DRAW_EXTRACT_DIR = ROOT / "data_truth/draw_results_truth/extracted"
VALIDATION_DIR = ROOT / "data_truth/draw_results_truth/validation"
REPORT_DIR = ROOT / "processed_data"

TEXT_LINES_CSV = DRAW_EXTRACT_DIR / "2024_antlerless_draw_results_text_lines.csv"
DRAW_ROWS_CSV = DRAW_EXTRACT_DIR / "2024_antlerless_draw_results_hunt_rows.csv"
CODE_RECONCILIATION_CSV = VALIDATION_DIR / "2026_antlerless_hunt_code_reconciliation.csv"
PROMOTION_DETAIL_CSV = REPORT_DIR / "2026_antlerless_predictive_v2_reference_promotion.csv"
AUDIT_JSON = REPORT_DIR / "2024_antlerless_draw_results_audit.json"
AUDIT_MD = REPORT_DIR / "2024_antlerless_draw_results_audit.md"
PROMOTION_JSON = REPORT_DIR / "2026_antlerless_predictive_v2_reference_promotion_summary.json"
RECONCILIATION_JSON = REPORT_DIR / "2026_antlerless_hunt_code_reconciliation_summary.json"
RECONCILIATION_MD = REPORT_DIR / "2026_antlerless_hunt_code_reconciliation.md"

SOURCE_PATH = "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/official_dwr_archive/big_game_antlerless/24_antlerless_drawing_odds_report.pdf"
# Fail-closed: real PDF signature 2b1b... from 55fbe7f6__Antlerless big game draw results.pdf
EXPECTED_SHA256 = "2b1b19782089732b9cacc2fd9ce00e60e1093acda6f3ed70d29e8d6e3ae83b08"
EXPECTED_SIZE_BYTES = 774859
EXPECTED_PAGES = 203

TARGET_PREFIXES = {"EA", "DA", "PD", "RE"}
REFERENCE_MODEL_VERSION = "antlerless_reference_v1.0.0"
REFERENCE_RULE_VERSION = "utah_antlerless_code_resolution_v1.0.0"
DATA_CUTOFF_DATE = "2026-05-24"

HUNT_RE = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+)")
TOTALS_RE = re.compile(
    r"Totals\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(?:1 in [\d.,]+|N/A)\s+"
    r"Totals\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+([\d,]+)\s+(?:1 in [\d.,]+|N/A)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DrawResultRow:
    source_file: str
    source_sha256: str
    source_page: int
    hunt_code: str
    hunt_name: str
    species_category: str
    resident_applicants: int
    resident_bonus_permits: int
    resident_regular_permits: int
    resident_total_permits: int
    nonresident_applicants: int
    nonresident_bonus_permits: int
    nonresident_regular_permits: int
    nonresident_total_permits: int
    total_permits: int
    raw_hunt_line: str
    raw_totals_line: str


def normalized(text: str) -> str:
    text = text.replace("\u2013", "-").replace("\u2014", "-").replace("\u00a0", " ")
    text = text.replace("\u2019", "'").replace("\u201c", '"').replace("\u201d", '"')
    return re.sub(r"\s+", " ", text).strip()


def sha256(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def code_prefix(code: str) -> str:
    match = re.match(r"^[A-Z]+", code or "")
    return match.group(0) if match else ""


def parse_species_from_name(hunt_name: str) -> str:
    name = hunt_name.lower()
    if "antlerless deer" in name:
        return "Antlerless Deer"
    if "antlerless elk" in name:
        return "Antlerless Elk"
    if "doe pronghorn" in name:
        return "Doe Pronghorn"
    if "antlerless moose" in name:
        return "Antlerless Moose"
    if "ewe" in name:
        return "Rocky Mountain Bighorn Ewe"
    return "Other Antlerless"


def to_int(value: str) -> int:
    return int(str(value).replace(",", "").strip())


def extract_pdf_text_lines(source_sha256: str | None = None) -> list[dict[str, object]]:
    source_sha256 = source_sha256 or sha256(SOURCE_PDF)
    rows: list[dict[str, object]] = []
    with pdfplumber.open(SOURCE_PDF) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            for line_number, line in enumerate((page.extract_text() or "").splitlines(), start=1):
                text = normalized(line)
                if text:
                    rows.append({
                        "source_file": SOURCE_PATH,
                        "source_sha256": source_sha256,
                        "source_page": page_number,
                        "line_number": line_number,
                        "text": text,
                    })
    return rows


def parse_draw_results(source_sha256: str | None = None) -> list[DrawResultRow]:
    source_sha256 = source_sha256 or sha256(SOURCE_PDF)
    rows: list[DrawResultRow] = []
    with pdfplumber.open(SOURCE_PDF) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            if "Hunt:" not in text:
                continue
            hunt_match = HUNT_RE.search(text)
            totals_match = TOTALS_RE.search(" ".join(text.split()))
            if not hunt_match or not totals_match:
                raise ValueError(f"unparsed_hunt_page:{page_number}")
            hunt_code = hunt_match.group(1).strip().upper()
            hunt_name = normalized(hunt_match.group(2))
            resident_total = to_int(totals_match.group(4))
            nonresident_total = to_int(totals_match.group(8))
            rows.append(DrawResultRow(
                source_file=SOURCE_PATH,
                source_sha256=source_sha256,
                source_page=page_number,
                hunt_code=hunt_code,
                hunt_name=hunt_name,
                species_category=parse_species_from_name(hunt_name),
                resident_applicants=to_int(totals_match.group(1)),
                resident_bonus_permits=to_int(totals_match.group(2)),
                resident_regular_permits=to_int(totals_match.group(3)),
                resident_total_permits=resident_total,
                nonresident_applicants=to_int(totals_match.group(5)),
                nonresident_bonus_permits=to_int(totals_match.group(6)),
                nonresident_regular_permits=to_int(totals_match.group(7)),
                nonresident_total_permits=nonresident_total,
                total_permits=resident_total + nonresident_total,
                raw_hunt_line=hunt_match.group(0),
                raw_totals_line=totals_match.group(0),
            ))
    return rows


def rows_by_code(path: Path, prefixes: set[str] | None = None) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in read_rows(path):
        code = row.get("hunt_code", "").strip()
        if not code:
            continue
        if prefixes and code_prefix(code) not in prefixes:
            continue
        grouped.setdefault(code, []).append(row)
    return grouped


def choose_residency(database_row: dict[str, str]) -> str:
    res = database_row.get("permits_2026_res", "").strip()
    nr = database_row.get("permits_2026_nr", "").strip()
    if nr and not res:
        return "Nonresident"
    return "Resident"


def build_reference_row(fieldnames: list[str], database_row: dict[str, str], source_basis: str) -> dict[str, str]:
    row = {fieldname: "" for fieldname in fieldnames}
    total_permits = database_row.get("permits_2026_total", "")
    species = database_row.get("species", "")
    prefix = code_prefix(database_row["hunt_code"])
    draw_system_type = {
        "EA": "PREFERENCE_ANTLERLESS_ELK_REFERENCE",
        "DA": "PREFERENCE_ANTLERLESS_DEER_REFERENCE",
        "PD": "PREFERENCE_DOE_PRONGHORN_REFERENCE",
        "RE": "PREFERENCE_EWE_BIGHORN_REFERENCE",
    }.get(prefix, "ANTLERLESS_REFERENCE")
    reason = (
        "Promoted from current 2026 DATABASE/draw-reality antlerless reference coverage"
        f" with source basis {source_basis}; no draw-odds probability was invented."
    )
    row.update(
        {
            "year": "2026",
            "forecast_year": "2026",
            "hunt_code": database_row["hunt_code"],
            "hunt_name": database_row.get("hunt_name", ""),
            "species": species,
            "sex_type": database_row.get("sex_type", ""),
            "hunt_type": database_row.get("hunt_type", ""),
            "hunt_class": "Antlerless Reference",
            "residency": choose_residency(database_row),
            "points": "0",
            "draw_pool": "antlerless_reference",
            "source_years_used": "2024;2026",
            "source_year_count": "2",
            "latest_source_year": "2026",
            "earliest_source_year": "2024",
            "source_dataset": "2026_antlerless_hunt_code_reconciliation",
            "model_strategy": "ANTLERLESS_REFERENCE",
            "draw_system_type": draw_system_type,
            "season_dates": database_row.get("season", ""),
            "weapon": database_row.get("weapon", ""),
            "algorithm_status": "ANTLERLESS_REFERENCE",
            "target_scope": "TARGET",
            "modeled_by_engine": "False",
            "reason": reason,
            "model_version": REFERENCE_MODEL_VERSION,
            "rule_version": REFERENCE_RULE_VERSION,
            "public_permits_2026": total_permits,
            "quota_source_status": "official_database_reference",
            "quota_source_year": "2026",
            "quota_source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "quota_2026_total": total_permits,
            "permit_allotment_2026_res": database_row.get("permits_2026_res", ""),
            "permit_allotment_2026_nr": database_row.get("permits_2026_nr", ""),
            "permit_allotment_2026_total": total_permits,
            "permit_allotment_2026_source": "DATABASE",
            "permit_allotment_2026_source_file": "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
            "permit_allotment_2026_status": "official_database_reference",
            "data_cutoff_date": DATA_CUTOFF_DATE,
            "reason_codes": "ANTLERLESS_CURRENT_DATABASE_REFERENCE|NO_PREDICTIVE_DRAW_MODEL_ROW|NO_DRAW_PROBABILITY_INVENTED",
            "status": "antlerless_reference_no_draw_odds",
            "trend": "not_modeled",
            "permit_availability_type": "antlerless_reference",
            "probability_model": "NONE",
            "rule_status": "antlerless_reference",
            "availability_status": "antlerless_reference",
            "data_quality_flags": "PROMOTED_ANTLERLESS_REFERENCE_CODE;NO_DRAW_PROBABILITY_MODELED",
            "prediction_year": "2026",
            "source_year": "2026",
            "applicant_forecast_method": "not_modeled_antlerless_reference",
            "display_odds_text": "Antlerless reference only; odds not modeled",
            "data_quality_grade": "A",
        }
    )
    if not total_permits:
        row["public_permits_2026"] = ""
        row["quota_2026_total"] = ""
        row["permit_allotment_2026_total"] = ""
    return row


def build_reconciliation_rows(draw_rows: list[DrawResultRow], planned_predictive: list[dict[str, str]] | None = None) -> list[dict[str, object]]:
    draw_codes = {row.hunt_code for row in draw_rows if code_prefix(row.hunt_code) in TARGET_PREFIXES}
    database_rows = rows_by_code(DATABASE, TARGET_PREFIXES)
    hunt_master_rows = rows_by_code(resolve_hunt_master_path(), TARGET_PREFIXES)
    point_ladder_rows = rows_by_code(POINT_LADDER, TARGET_PREFIXES)
    draw_reality_rows = rows_by_code(DRAW_REALITY, TARGET_PREFIXES)
    predictive_rows = (
        rows_by_code(PREDICTIVE, TARGET_PREFIXES)
        if planned_predictive is None
        else {row.get("hunt_code", "") for row in planned_predictive}
    )
    codes = sorted(set(database_rows) | draw_codes)
    rows: list[dict[str, object]] = []
    for code in codes:
        database_row = (database_rows.get(code) or [{}])[0]
        current_database = bool(database_row)
        source_basis = "prior_2024_antlerless_draw_results" if code in draw_codes else "current_2026_database_reference_only"
        current_failure = current_database and not (
            code in hunt_master_rows and code in point_ladder_rows and code in draw_reality_rows and code in predictive_rows
        )
        rows.append(
            {
                "hunt_code": code,
                "code_prefix": code_prefix(code),
                "hunt_name": database_row.get("hunt_name", ""),
                "species": database_row.get("species", ""),
                "hunt_type": database_row.get("hunt_type", ""),
                "weapon": database_row.get("weapon", ""),
                "season": database_row.get("season", ""),
                "permits_2026_total": database_row.get("permits_2026_total", ""),
                "present_in_2024_antlerless_draw_results": str(code in draw_codes).lower(),
                "database_present": str(current_database).lower(),
                "hunt_master_present": str(code in hunt_master_rows).lower(),
                "point_ladder_present": str(code in point_ladder_rows).lower(),
                "draw_reality_present": str(code in draw_reality_rows).lower(),
                "predictive_v2_present": str(code in predictive_rows).lower(),
                "source_basis": source_basis,
                "current_database_reconciliation_status": "FAIL" if current_failure else "PASS",
            }
        )
    return rows


def prepare_reference_promotion(reconciliation_rows: list[dict[str, object]]):
    """Compute missing coverage; never replace any owning engine's rows."""
    database_rows = {
        row["hunt_code"]: row for row in read_rows(DATABASE)
        if code_prefix(row.get("hunt_code", "")) in TARGET_PREFIXES
    }
    source_basis = {str(row["hunt_code"]): str(row["source_basis"]) for row in reconciliation_rows}
    original_rows = read_rows(PREDICTIVE)
    with PREDICTIVE.open(newline="", encoding="utf-8-sig") as handle:
        fieldnames = csv.DictReader(handle).fieldnames or []
    if not fieldnames or "hunt_code" not in fieldnames:
        raise ValueError("predictive_schema_missing_hunt_code")
    owned_reference = lambda row: (
        row.get("model_version") == REFERENCE_MODEL_VERSION
        and code_prefix(row.get("hunt_code", "")) in TARGET_PREFIXES
    )
    retained_rows = [row for row in original_rows if not owned_reference(row)]
    retained_codes = {row.get("hunt_code", "") for row in retained_rows}
    missing_codes = sorted(set(database_rows) - retained_codes)
    reference_rows = [
        build_reference_row(fieldnames, database_rows[code],
                            source_basis.get(code, "current_2026_database_reference_only"))
        for code in missing_codes
    ]
    # Include the reference contract fields even if a small input omitted them.
    for row in reference_rows:
        fieldnames.extend(key for key in row if key not in fieldnames)
    final_rows = retained_rows + reference_rows
    final_codes = {row.get("hunt_code", "") for row in final_rows}
    still_missing = sorted(set(database_rows) - final_codes)
    reference_keys = Counter(
        (row["hunt_code"], row["residency"], row["points"], row["draw_pool"], row["model_version"])
        for row in reference_rows
    )
    duplicates = [key for key, count in reference_keys.items() if count > 1]
    original_codes = {row.get("hunt_code", "") for row in original_rows}
    newly_promoted = sorted(set(missing_codes) - original_codes)
    summary = {
        "classification": "ANTLERLESS_REFERENCE_PROMOTION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "target_prefixes": sorted(TARGET_PREFIXES),
        "initial_missing_predictive_hunt_code_count": len(set(database_rows) - original_codes),
        "newly_promoted_hunt_code_count": len(newly_promoted),
        "promoted_reference_hunt_code_count": len(missing_codes),
        "still_missing_predictive_hunt_code_count": len(still_missing),
        "duplicate_reference_key_count": len(duplicates),
        "newly_promoted_hunt_codes": newly_promoted,
        "promoted_reference_hunt_codes": missing_codes,
        "still_missing_predictive_hunt_codes": still_missing,
        "duplicate_reference_keys": duplicates,
        "guardrail": "Reference coverage only; no draw probability is invented.",
    }
    details = [{
        "hunt_code": row["hunt_code"],
        "hunt_name": row["hunt_name"],
        "species": row["species"],
        "hunt_type": row["hunt_type"],
        "residency": row["residency"],
        "permits_2026_total": row["permit_allotment_2026_total"],
        "promotion_status": "REFERENCE_ONLY",
        "reason": row["reason"],
    } for row in reference_rows]
    return summary, fieldnames, final_rows, details


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def publish_tables(
    tables: list[tuple[Path, list[str], list[dict]]],
    json_files: list[tuple[Path, dict]] | None = None,
) -> None:
    """Stage complete tables before replacement; roll back on a write failure."""
    staged = []
    replaced = []
    try:
        for path, fields, rows in tables:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            os.close(descriptor)
            temporary = Path(name)
            staged.append((path, temporary, path.read_bytes() if path.exists() else None))
            write_rows(temporary, fields, rows)
        for path, value in json_files or []:
            path.parent.mkdir(parents=True, exist_ok=True)
            descriptor, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
            os.close(descriptor)
            temporary = Path(name)
            staged.append((path, temporary, path.read_bytes() if path.exists() else None))
            write_json(temporary, value)
        for path, temporary, previous in staged:
            os.replace(temporary, path)
            replaced.append((path, previous))
    except Exception:
        for path, previous in reversed(replaced):
            if previous is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(previous)
        raise
    finally:
        for _, temporary, _ in staged:
            temporary.unlink(missing_ok=True)


def promote_missing_reference_rows(reconciliation_rows: list[dict[str, object]]) -> dict[str, object]:
    summary, fields, rows, details = prepare_reference_promotion(reconciliation_rows)
    if summary["still_missing_predictive_hunt_code_count"] or summary["duplicate_reference_key_count"]:
        raise ValueError("reference_coverage_validation_failed")
    publish_tables([
        (PREDICTIVE, fields, rows),
        (PROMOTION_DETAIL_CSV, list(details[0]) if details else ["hunt_code"], details),
    ], [(PROMOTION_JSON, summary)])
    return summary


def main() -> int:
    blockers: list[str] = []
    failures: list[dict[str, object]] = []
    real_sha_actual = None
    real_size_actual = None
    real_pages = None
    text_lines = []
    draw_rows = []
    if not SOURCE_PDF.exists():
        blockers.append("source_pdf_missing")
    else:
        try:
            real_size_actual = SOURCE_PDF.stat().st_size
            real_sha_actual = sha256(SOURCE_PDF)
            with pdfplumber.open(SOURCE_PDF) as pdf:
                real_pages = len(pdf.pages)
            text_lines = extract_pdf_text_lines(real_sha_actual)
            draw_rows = parse_draw_results(real_sha_actual)
            if sha256(SOURCE_PDF) != real_sha_actual:
                blockers.append("source_pdf_changed_during_extraction")
        except Exception as exc:
            blockers.append(f"source_pdf_read_or_parse_failed:{type(exc).__name__}:{exc}")
    if real_sha_actual is not None and real_sha_actual != EXPECTED_SHA256:
        blockers.append("source_sha256_mismatch")
    if real_size_actual is not None and real_size_actual != EXPECTED_SIZE_BYTES:
        blockers.append("source_size_mismatch")
    if real_pages is not None and real_pages != EXPECTED_PAGES:
        blockers.append("source_page_count_mismatch")
    real_lines = len(text_lines)
    real_rows = len(draw_rows)
    if real_lines == 0:
        blockers.append("source_text_lines_empty")
    if real_rows == 0:
        blockers.append("source_draw_rows_empty")
    unique_codes = {row.hunt_code for row in draw_rows}
    if len(unique_codes) != real_rows:
        blockers.append("duplicate_source_hunt_codes")
    prefixes = Counter(code_prefix(row.hunt_code) for row in draw_rows)
    audit_summary = {
        "classification": "ANTLERLESS_DRAW_RESULTS_TRUTH_SOURCE_AUDIT",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "source_pdf": str(SOURCE_PDF),
        "source_sha256": real_sha_actual,
        "expected_sha256": EXPECTED_SHA256,
        "source_size_bytes": real_size_actual,
        "expected_size_bytes": EXPECTED_SIZE_BYTES,
        "pdf_pages": real_pages,
        "expected_pages": EXPECTED_PAGES,
        "text_lines": real_lines,
        "draw_result_rows": real_rows,
        "unique_draw_result_hunt_codes": len(unique_codes),
        "draw_result_prefix_counts": dict(sorted(prefixes.items())),
        "guardrail": "Measured prior draw truth; not prediction certification.",
    }
    promotion_summary = None
    reconciliation_rows = []
    if not blockers:
        try:
            pre_reconciliation = build_reconciliation_rows(draw_rows)
            promotion_summary, fields, planned_rows, details = prepare_reference_promotion(pre_reconciliation)
            reconciliation_rows = build_reconciliation_rows(draw_rows, planned_rows)
            failures = [
                row for row in reconciliation_rows
                if row["database_present"] == "true"
                and row["current_database_reconciliation_status"] != "PASS"
            ]
            if promotion_summary["still_missing_predictive_hunt_code_count"]:
                blockers.append("predictive_reference_coverage_missing")
            if promotion_summary["duplicate_reference_key_count"]:
                blockers.append("duplicate_reference_keys")
        except Exception as exc:
            blockers.append(f"reconciliation_failed:{type(exc).__name__}:{exc}")

    if not blockers and not failures:
        try:
            # No source, reconciliation or coverage failure may overwrite these tables.
            publish_tables([
                (TEXT_LINES_CSV, list(text_lines[0]), text_lines),
                (DRAW_ROWS_CSV, list(asdict(draw_rows[0])), [asdict(row) for row in draw_rows]),
                (PREDICTIVE, fields, planned_rows),
                (CODE_RECONCILIATION_CSV, list(reconciliation_rows[0]), reconciliation_rows),
                (PROMOTION_DETAIL_CSV, list(details[0]) if details else ["hunt_code"], details),
            ], [(PROMOTION_JSON, promotion_summary)])
        except Exception as exc:
            blockers.append(f"output_write_failed:{type(exc).__name__}:{exc}")

    audit_summary.update(
        blockers=len(blockers), blocker_reasons=blockers,
        reconciliation_failure_count=len(failures),
        reconciliation_failures=[row["hunt_code"] for row in failures],
    )
    # Always publish diagnostic evidence, including missing/unreadable source runs.
    write_json(AUDIT_JSON, audit_summary)
    AUDIT_MD.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_MD.write_text(
        "# 2024 Antlerless Draw Results Audit\n\n"
        + "\n".join(f"- {key}: {value}" for key, value in audit_summary.items()) + "\n",
        encoding="utf-8",
    )
    if reconciliation_rows:
        current_rows = [row for row in reconciliation_rows if row["database_present"] == "true"]
        summary = {
            "classification": "ANTLERLESS_HUNT_CODE_RECONCILIATION",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_prefixes": sorted(TARGET_PREFIXES),
            "current_database_code_count": len(current_rows),
            "draw_results_2024_code_count": sum(
                code_prefix(code) in TARGET_PREFIXES for code in unique_codes
            ),
            "current_database_codes_present_in_2024_draw_results_count": sum(
                row["present_in_2024_antlerless_draw_results"] == "true" for row in current_rows
            ),
            "current_database_reconciliation_failure_count": len(failures),
            "current_database_reconciliation_failures": [row["hunt_code"] for row in failures],
            "promotion_summary": promotion_summary,
            "blockers": len(blockers),
            "blocker_reasons": blockers,
        }
        write_json(RECONCILIATION_JSON, summary)
        RECONCILIATION_MD.parent.mkdir(parents=True, exist_ok=True)
        RECONCILIATION_MD.write_text(
            "# 2026 Antlerless Hunt-Code Reconciliation\n\n"
            + "\n".join(f"- {key}: {value}" for key, value in summary.items()) + "\n",
            encoding="utf-8",
        )
    return 1 if blockers or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
