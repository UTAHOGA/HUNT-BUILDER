#!/usr/bin/env python3
"""Deep-dive permit consistency audit for hunt_master_canonical_2026_built.csv.

This script is read-only. It compares the target file's duplicate permit triples
against the canonical DATABASE fields, direct RAC/current-year CSV evidence, and
2026 total-scan evidence. It does not promote values into any runtime/database
surface.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
HUNTS_ROOT = Path(str(_repo_root()))
CSV_DIR = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv"

TARGET = CSV_DIR / "hunt_master_canonical_2026_built.csv"
DATABASE = HUNTS_ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
LOCAL_DATABASE = CSV_DIR / "DATABASE.csv"
TOTALSCAN_HIGH_CONF = CSV_DIR / "current_year_permit_numbers_compare_snapshot_totalscan_high_conf.csv"

OUTPUT = ROOT / "processed_data/hunt_master_canonical_2026_built_permit_deep_dive.csv"
SUMMARY_JSON = ROOT / "processed_data/hunt_master_canonical_2026_built_permit_deep_dive_summary.json"
SUMMARY_MD = ROOT / "processed_data/hunt_master_canonical_2026_built_permit_deep_dive.md"
VALIDATION_JSON = (
    ROOT
    / "data_truth/comparison_outputs/validation/hunt_master_canonical_2026_built_permit_deep_dive_summary.json"
)

EXCLUDED_RAC_PROMOTION_TOKENS = (
    "metadata",
    "comparison",
    "verification",
    "control_units",
    "supplemental",
    "permit_rows_from_pdf",
)

TRIPLE_FIELDS = ("res", "nr", "total")

OUTPUT_FIELDS = [
    "hunt_code",
    "target_hunt_name",
    "target_species",
    "target_hunt_type",
    "target_weapon",
    "target_boundary_id",
    "database_present",
    "database_hunt_name",
    "database_species",
    "database_boundary_id",
    "target_2025_res",
    "target_2025_nr",
    "target_2025_total",
    "target_2026_res",
    "target_2026_nr",
    "target_2026_total",
    "database_2025_res",
    "database_2025_nr",
    "database_2025_total",
    "database_2025_draw_res",
    "database_2025_draw_nr",
    "database_2025_draw_total",
    "database_2026_res",
    "database_2026_nr",
    "database_2026_total",
    "database_allotment_2026_res",
    "database_allotment_2026_nr",
    "database_allotment_2026_total",
    "direct_rac_2026_res",
    "direct_rac_2026_nr",
    "direct_rac_2026_total",
    "direct_rac_source_file",
    "totalscan_high_conf_total",
    "target_2025_vs_database_2025_status",
    "target_2025_vs_database_2025_draw_status",
    "target_2026_vs_database_2026_status",
    "target_2026_vs_database_allotment_status",
    "target_2026_vs_direct_rac_status",
    "target_2026_vs_totalscan_status",
    "database_2026_vs_direct_rac_status",
    "database_allotment_vs_direct_rac_status",
    "target_2025_to_2026_delta_total",
    "database_2025_to_2026_delta_total",
    "change_review_status",
    "evidence_confidence",
    "audit_notes",
]


def clean(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip().replace("\ufeff", "")
    if text in {"-", "–", "—", "nan", "None"}:
        return ""
    return text


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return ""
    return str(int(number)) if number.is_integer() else str(number)


def maybe_int(value: str) -> int | None:
    text = int_text(value)
    if text == "":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return [{key: clean(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def read_target_rows() -> list[dict[str, str]]:
    with TARGET.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        rows: list[dict[str, str]] = []
        for raw in reader:
            # The target has duplicate permits_2026_* headers. Preserve both triples by position.
            rows.append(
                {
                    "hunt_code": clean(raw[0] if len(raw) > 0 else "").upper(),
                    "species": clean(raw[1] if len(raw) > 1 else ""),
                    "sex_type": clean(raw[2] if len(raw) > 2 else ""),
                    "hunt_type": clean(raw[3] if len(raw) > 3 else ""),
                    "weapon": clean(raw[4] if len(raw) > 4 else ""),
                    "hunt_name": clean(raw[6] if len(raw) > 6 else ""),
                    "target_2025_res": int_text(raw[12] if len(raw) > 12 else ""),
                    "target_2025_nr": int_text(raw[13] if len(raw) > 13 else ""),
                    "target_2025_total": int_text(raw[14] if len(raw) > 14 else ""),
                    "target_2026_res": int_text(raw[15] if len(raw) > 15 else ""),
                    "target_2026_nr": int_text(raw[16] if len(raw) > 16 else ""),
                    "target_2026_total": int_text(raw[17] if len(raw) > 17 else ""),
                    "boundary_id": clean(raw[31] if len(raw) > 31 else ""),
                    "_raw_header_count": str(len(header)),
                }
            )
        return rows


def source_files() -> list[Path]:
    files: list[Path] = []
    for path in sorted(CSV_DIR.glob("2026_rac_*.csv")):
        lower = path.name.lower()
        if any(token in lower for token in EXCLUDED_RAC_PROMOTION_TOKENS):
            continue
        files.append(path)
    return files


def load_direct_rac_rows() -> dict[str, dict[str, str]]:
    direct: dict[str, dict[str, str]] = {}
    for path in source_files():
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "hunt_code" not in reader.fieldnames:
                continue
            for row_number, row in enumerate(reader, start=2):
                code = clean(row.get("hunt_code")).upper()
                if not code:
                    continue
                res = int_text(row.get("permits_2026_res"))
                nr = int_text(row.get("permits_2026_nr"))
                total = int_text(row.get("permits_2026_total"))
                if not total and (res or nr):
                    total = str((maybe_int(res) or 0) + (maybe_int(nr) or 0))
                if not (res or nr or total):
                    continue
                candidate = {
                    "res": res,
                    "nr": nr,
                    "total": total,
                    "source_file": path.relative_to(ROOT).as_posix(),
                    "source_row_number": str(row_number),
                }
                existing = direct.get(code)
                if existing is None:
                    direct[code] = candidate
                    continue
                existing_has_split = bool(existing.get("res") or existing.get("nr"))
                candidate_has_split = bool(res or nr)
                if candidate_has_split and not existing_has_split:
                    direct[code] = candidate
                elif total and not existing.get("total"):
                    direct[code] = candidate
    return direct


def load_totalscan_high_conf() -> dict[str, str]:
    if not TOTALSCAN_HIGH_CONF.exists():
        return {}
    output: dict[str, str] = {}
    for row in read_csv(TOTALSCAN_HIGH_CONF):
        code = clean(row.get("hunt_code")).upper()
        total = int_text(row.get("source_2026_total_high_conf"))
        if code and total:
            output[code] = total
    return output


def triple(row: dict[str, str], prefix: str) -> tuple[str, str, str]:
    return tuple(int_text(row.get(f"{prefix}_{field}", "")) for field in TRIPLE_FIELDS)  # type: ignore[return-value]


def db_triple(row: dict[str, str], prefix: str) -> tuple[str, str, str]:
    return tuple(int_text(row.get(f"{prefix}_{field}", "")) for field in TRIPLE_FIELDS)  # type: ignore[return-value]


def compare_triple(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    left_has = any(left)
    right_has = any(right)
    if not left_has and not right_has:
        return "BOTH_BLANK"
    if left_has and not right_has:
        if left[2] == "0":
            return "LEFT_ZERO_RIGHT_BLANK"
        return "LEFT_ONLY"
    if right_has and not left_has:
        return "RIGHT_ONLY"
    if left == right:
        return "MATCH"
    if left[2] and right[2] and left[2] == right[2]:
        return "TOTAL_MATCH_SPLIT_DIFFERS"
    return "MISMATCH"


def compare_total(left: str, right: str) -> str:
    left = int_text(left)
    right = int_text(right)
    if not left and not right:
        return "BOTH_BLANK"
    if left and not right:
        return "LEFT_ONLY"
    if right and not left:
        return "RIGHT_ONLY"
    return "MATCH" if left == right else "MISMATCH"


def total_delta(left: str, right: str) -> str:
    left_i = maybe_int(left)
    right_i = maybe_int(right)
    if left_i is None or right_i is None:
        return ""
    return str(right_i - left_i)


def change_review_status(delta_text: str, start_total: str, end_total: str) -> str:
    delta = maybe_int(delta_text)
    start = maybe_int(start_total)
    end = maybe_int(end_total)
    if delta is None or start is None or end is None:
        return "INSUFFICIENT_DATA"
    if delta == 0:
        return "NO_CHANGE"
    if abs(delta) <= 5:
        return "SMALL_CHANGE_ABS_5_OR_LESS"
    baseline = max(abs(start), 1)
    if abs(delta) / baseline <= 0.25:
        return "MODERATE_CHANGE_ABS_GT_5_PCT_25_OR_LESS"
    return "LARGE_CHANGE_REVIEW"


def confidence_for(row: dict[str, str]) -> str:
    if (
        row["target_2025_vs_database_2025_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS"}
        and row["target_2026_vs_database_2026_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS"}
        and row["target_2026_vs_database_allotment_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}
        and row["target_2026_vs_direct_rac_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}
    ):
        return "HIGH"
    if row["target_2026_vs_database_2026_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS"}:
        return "MEDIUM_2026_MATCHES_DATABASE"
    if row["target_2025_vs_database_2025_status"] in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS"}:
        return "LOW_2025_MATCH_ONLY"
    return "REVIEW_REQUIRED"


def build_audit_rows() -> tuple[list[dict[str, str]], dict]:
    target_rows = read_target_rows()
    database_rows = {row["hunt_code"].upper(): row for row in read_csv(DATABASE) if row.get("hunt_code")}
    local_database_rows = {row["hunt_code"].upper(): row for row in read_csv(LOCAL_DATABASE) if row.get("hunt_code")}
    direct_rac = load_direct_rac_rows()
    totalscan = load_totalscan_high_conf()

    output_rows: list[dict[str, str]] = []
    for row in target_rows:
        code = row["hunt_code"]
        db = database_rows.get(code, {})
        local_db = local_database_rows.get(code, {})
        rac = direct_rac.get(code, {})
        target_2025 = triple(row, "target_2025")
        target_2026 = triple(row, "target_2026")
        db_2025 = db_triple(db, "permits_2025")
        db_2025_draw = db_triple(db, "permits_2025_draw")
        db_2026 = db_triple(db, "permits_2026")
        db_allotment = db_triple(db, "permit_allotment_2026")
        rac_2026 = (rac.get("res", ""), rac.get("nr", ""), rac.get("total", ""))
        totalscan_total = totalscan.get(code, "")

        row_out = {
            "hunt_code": code,
            "target_hunt_name": row.get("hunt_name", ""),
            "target_species": row.get("species", ""),
            "target_hunt_type": row.get("hunt_type", ""),
            "target_weapon": row.get("weapon", ""),
            "target_boundary_id": row.get("boundary_id", ""),
            "database_present": "YES" if db else "NO",
            "database_hunt_name": db.get("hunt_name", ""),
            "database_species": db.get("species", ""),
            "database_boundary_id": db.get("boundary_id", ""),
            "target_2025_res": target_2025[0],
            "target_2025_nr": target_2025[1],
            "target_2025_total": target_2025[2],
            "target_2026_res": target_2026[0],
            "target_2026_nr": target_2026[1],
            "target_2026_total": target_2026[2],
            "database_2025_res": db_2025[0],
            "database_2025_nr": db_2025[1],
            "database_2025_total": db_2025[2],
            "database_2025_draw_res": db_2025_draw[0],
            "database_2025_draw_nr": db_2025_draw[1],
            "database_2025_draw_total": db_2025_draw[2],
            "database_2026_res": db_2026[0],
            "database_2026_nr": db_2026[1],
            "database_2026_total": db_2026[2],
            "database_allotment_2026_res": db_allotment[0],
            "database_allotment_2026_nr": db_allotment[1],
            "database_allotment_2026_total": db_allotment[2],
            "direct_rac_2026_res": rac_2026[0],
            "direct_rac_2026_nr": rac_2026[1],
            "direct_rac_2026_total": rac_2026[2],
            "direct_rac_source_file": rac.get("source_file", ""),
            "totalscan_high_conf_total": totalscan_total,
            "target_2025_vs_database_2025_status": compare_triple(target_2025, db_2025),
            "target_2025_vs_database_2025_draw_status": compare_triple(target_2025, db_2025_draw),
            "target_2026_vs_database_2026_status": compare_triple(target_2026, db_2026),
            "target_2026_vs_database_allotment_status": compare_triple(target_2026, db_allotment),
            "target_2026_vs_direct_rac_status": compare_triple(target_2026, rac_2026),
            "target_2026_vs_totalscan_status": compare_total(target_2026[2], totalscan_total),
            "database_2026_vs_direct_rac_status": compare_triple(db_2026, rac_2026),
            "database_allotment_vs_direct_rac_status": compare_triple(db_allotment, rac_2026),
            "target_2025_to_2026_delta_total": total_delta(target_2025[2], target_2026[2]),
            "database_2025_to_2026_delta_total": total_delta(db_2025[2], db_2026[2]),
            "change_review_status": "",
            "evidence_confidence": "",
            "audit_notes": "",
        }
        row_out["change_review_status"] = change_review_status(
            row_out["target_2025_to_2026_delta_total"],
            row_out["target_2025_total"],
            row_out["target_2026_total"],
        )
        row_out["evidence_confidence"] = confidence_for(row_out)
        notes: list[str] = []
        if not db:
            notes.append("target code missing from canonical HUNTS DATABASE")
        if local_db and db and db_triple(local_db, "permits_2026") != db_2026:
            notes.append("local DATABASE 2026 permits differ from HUNTS DATABASE")
        if row_out["target_2026_vs_database_2026_status"] not in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}:
            notes.append("target second permit triple does not cleanly match DATABASE 2026 permits")
        if row_out["target_2025_vs_database_2025_status"] not in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}:
            notes.append("target first permit triple does not cleanly match DATABASE 2025 permits")
        if row_out["change_review_status"] == "LARGE_CHANGE_REVIEW":
            notes.append("large target 2025-to-2026 total change")
        row_out["audit_notes"] = "; ".join(notes)
        output_rows.append(row_out)

    target_codes = {row["hunt_code"] for row in target_rows if row["hunt_code"]}
    db_codes = set(database_rows)
    duplicate_target_codes = [
        code for code, count in Counter(row["hunt_code"] for row in target_rows if row["hunt_code"]).items() if count > 1
    ]

    summary = {
        "artifact": "hunt_master_canonical_2026_built_permit_deep_dive",
        "target_file": TARGET.relative_to(ROOT).as_posix(),
        "database_file": str(DATABASE).replace("\\", "/"),
        "target_row_count": len(target_rows),
        "target_unique_hunt_codes": len(target_codes),
        "target_duplicate_hunt_codes": duplicate_target_codes,
        "database_row_count": len(database_rows),
        "database_unique_hunt_codes": len(db_codes),
        "target_codes_missing_database": sorted(target_codes - db_codes),
        "database_codes_missing_target": sorted(db_codes - target_codes),
        "direct_rac_source_file_count": len(source_files()),
        "direct_rac_hunt_code_count": len(direct_rac),
        "totalscan_high_conf_hunt_code_count": len(totalscan),
        "status_counts": {
            "target_2025_vs_database_2025": dict(
                sorted(Counter(row["target_2025_vs_database_2025_status"] for row in output_rows).items())
            ),
            "target_2025_vs_database_2025_draw": dict(
                sorted(Counter(row["target_2025_vs_database_2025_draw_status"] for row in output_rows).items())
            ),
            "target_2026_vs_database_2026": dict(
                sorted(Counter(row["target_2026_vs_database_2026_status"] for row in output_rows).items())
            ),
            "target_2026_vs_database_allotment": dict(
                sorted(Counter(row["target_2026_vs_database_allotment_status"] for row in output_rows).items())
            ),
            "target_2026_vs_direct_rac": dict(
                sorted(Counter(row["target_2026_vs_direct_rac_status"] for row in output_rows).items())
            ),
            "target_2026_vs_totalscan": dict(
                sorted(Counter(row["target_2026_vs_totalscan_status"] for row in output_rows).items())
            ),
            "change_review": dict(sorted(Counter(row["change_review_status"] for row in output_rows).items())),
            "evidence_confidence": dict(sorted(Counter(row["evidence_confidence"] for row in output_rows).items())),
        },
        "high_confidence_rows": sum(1 for row in output_rows if row["evidence_confidence"] == "HIGH"),
        "review_required_rows": sum(1 for row in output_rows if row["evidence_confidence"] == "REVIEW_REQUIRED"),
        "large_change_review_rows": sum(1 for row in output_rows if row["change_review_status"] == "LARGE_CHANGE_REVIEW"),
        "target_2026_mismatch_rows": sum(
            1
            for row in output_rows
            if row["target_2026_vs_database_2026_status"] not in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}
        ),
        "target_2025_mismatch_rows": sum(
            1
            for row in output_rows
            if row["target_2025_vs_database_2025_status"] not in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS", "BOTH_BLANK"}
        ),
        "guardrail": (
            "This audit is evidence only. It does not promote 2025 permit values into 2026 available allotment. "
            "Promotion still requires reviewed source-date context. Populated numeric 2026 permit/allotment cells "
            "in canonical DATABASE.csv are treated as direct Utah DWR Hunt Planner truth and must not be overwritten "
            "by comparison files, inferred values, draw reports, RAC files, or audit outputs. Populated 2025 or older "
            "permit fields with reviewed source lineage are canonical historical source truth and must not drift."
        ),
        "outputs": {
            "csv": OUTPUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_JSON.relative_to(ROOT).as_posix(),
            "summary_md": SUMMARY_MD.relative_to(ROOT).as_posix(),
            "validation_json": VALIDATION_JSON.relative_to(ROOT).as_posix(),
        },
    }
    return output_rows, summary


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUTPUT_FIELDS})


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_markdown(summary: dict) -> None:
    lines = [
        "# Hunt Master Canonical 2026 Built Permit Deep Dive",
        "",
        "Read-only audit comparing the target file against DATABASE, direct RAC CSV evidence, and current-year total-scan evidence.",
        "",
        "## Summary",
        "",
        f"- Target rows: `{summary['target_row_count']}`",
        f"- Target unique hunt codes: `{summary['target_unique_hunt_codes']}`",
        f"- DATABASE rows: `{summary['database_row_count']}`",
        f"- Target codes missing DATABASE: `{len(summary['target_codes_missing_database'])}`",
        f"- DATABASE codes missing target: `{len(summary['database_codes_missing_target'])}`",
        f"- Direct RAC hunt codes: `{summary['direct_rac_hunt_code_count']}`",
        f"- Total-scan high-confidence hunt codes: `{summary['totalscan_high_conf_hunt_code_count']}`",
        f"- High-confidence rows: `{summary['high_confidence_rows']}`",
        f"- Review-required rows: `{summary['review_required_rows']}`",
        f"- Target 2026 mismatch rows: `{summary['target_2026_mismatch_rows']}`",
        f"- Target 2025 mismatch rows: `{summary['target_2025_mismatch_rows']}`",
        f"- Large 2025-to-2026 change review rows: `{summary['large_change_review_rows']}`",
        "",
        "## Guardrail",
        "",
        summary["guardrail"],
        "",
        "## Status Counts",
        "",
    ]
    for bucket, counts in summary["status_counts"].items():
        lines.append(f"### {bucket}")
        lines.append("")
        for key, value in counts.items():
            lines.append(f"- `{key}`: `{value}`")
        lines.append("")
    SUMMARY_MD.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    rows, summary = build_audit_rows()
    write_csv(OUTPUT, rows)
    write_json(SUMMARY_JSON, summary)
    write_json(VALIDATION_JSON, summary)
    write_markdown(summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
