"""Cross-compare black bear BR codes across 2024 draw, 2025 draw, and 2026 permits.

This script treats the draw-odds PDFs as completed draw-results evidence and the
2026 permit CSV overlay as current DWR Hunt Planner evidence. It does not modify
DATABASE.csv or promote historical values into protected current-year cells.
"""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

SOURCE_2024_PDF = ROOT / "pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/24 bear draw odds complete.pdf"
SOURCE_2025_PDF = ROOT / "pipeline/RAW/hunt_unit_database/2026/pdf/draw_odds/2025 Black Bear Draw odds.pdf"
PERMITS_2026 = ROOT / "data_truth/permit_overlay_truth/normalized/black_bear_permits_2026_canonical.csv"

NORMALIZED_2025_OUT = ROOT / "data_truth/draw_results_truth/normalized/black_bear_2025_draw_odds_model_target_2026_permit_totals.csv"
CROSSWALK_OUT = ROOT / "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
SUMMARY_OUT = ROOT / "data_truth/crosswalk_truth/validation/black_bear_BR_2024_2025_2026_crosswalk_summary.json"
REPORT_OUT = ROOT / "processed_data/black_bear_BR_2024_2025_2026_crosswalk.md"

DRAW_FIELDS = [
    "hunt_code",
    "hunt_name",
    "raw_hunt_name",
    "reported_draw_year",
    "model_target_year",
    "source_file",
    "source_sha256",
    "page_number",
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "total_public_permits",
    "source_classification",
]

CROSSWALK_FIELDS = [
    "historical_2024_code",
    "historical_2025_code",
    "current_2026_code",
    "mapping_status",
    "mapping_confidence",
    "hunt_name_2024",
    "hunt_name_2025",
    "hunt_name_2026",
    "hunt_type_2026",
    "weapon_2026",
    "permits_2024_res",
    "permits_2024_nr",
    "permits_2024_total",
    "permits_2025_res",
    "permits_2025_nr",
    "permits_2025_total",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "source_2024_page",
    "source_2025_page",
    "numeric_comparison_2024_to_2025",
    "numeric_comparison_2025_to_2026",
    "review_note",
]

# High-confidence code-reuse correction supported by the 2025 draw PDF and
# 2026 permit source. La Sal (`BR7008`, `BR7108`, `BR7208`) continues as the
# same official hunt codes in the live Hunt Planner and must not be collapsed
# into the separate La Sal Mtns code family.
CURRENT_RECODE_BY_2025_CODE = {
    "BR7307": ("BR7326", "Old La Sal limited-entry multiseason row moved; BR7307 is reused for conservation in 2026."),
}


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        return [{(k or "").strip(): (v or "").strip() for k, v in row.items()} for row in reader]


def write_csv(path: Path, rows: Iterable[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def parse_pdf(source_pdf: Path, reported_draw_year: int) -> list[dict[str, object]]:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required to extract black bear draw-odds PDFs.") from exc

    rows: list[dict[str, object]] = []
    source_hash = sha256(source_pdf)
    source_rel = str(source_pdf.relative_to(ROOT)).replace("\\", "/")
    with pdfplumber.open(source_pdf) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            hunt_match = re.search(r"Hunt:\s*(BR\d{4})\s+(.+?)\nResident Applicants", text, re.S)
            if not hunt_match:
                continue
            totals = re.findall(r"Totals\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text)
            if len(totals) < 2:
                raise RuntimeError(f"Could not extract resident/nonresident totals from {source_pdf} page {page_number}")

            raw_name = " ".join(hunt_match.group(2).split()).strip()
            hunt_name = re.sub(r"\s+-\s*.*$", "", raw_name).strip()
            resident = tuple(int(value) for value in totals[0])
            nonresident = tuple(int(value) for value in totals[1])
            rows.append(
                {
                    "hunt_code": hunt_match.group(1).strip().upper(),
                    "hunt_name": hunt_name,
                    "raw_hunt_name": raw_name,
                    "reported_draw_year": reported_draw_year,
                    "model_target_year": reported_draw_year + 1,
                    "source_file": source_rel,
                    "source_sha256": source_hash,
                    "page_number": page_number,
                    "resident_eligible_applicants": resident[0],
                    "resident_bonus_permits": resident[1],
                    "resident_regular_permits": resident[2],
                    "resident_total_permits": resident[3],
                    "nonresident_eligible_applicants": nonresident[0],
                    "nonresident_bonus_permits": nonresident[1],
                    "nonresident_regular_permits": nonresident[2],
                    "nonresident_total_permits": nonresident[3],
                    "total_public_permits": resident[3] + nonresident[3],
                    "source_classification": "BEAR_PURSUIT_BONUS_DRAW" if "pursuit" in raw_name.lower() else "TRUE_BEAR_BONUS_DRAW",
                }
            )
    return rows


def keyed(rows: Iterable[dict[str, object]]) -> dict[str, dict[str, object]]:
    output: dict[str, dict[str, object]] = {}
    for row in rows:
        code = str(row["hunt_code"]).upper()
        if code in output:
            raise RuntimeError(f"Duplicate hunt code found while keying rows: {code}")
        output[code] = row
    return output


def permit_tuple(row: dict[str, object] | None, year: int) -> tuple[str, str, str]:
    if not row:
        return ("", "", "")
    if year == 2026:
        return (
            str(row.get("permits_2026_res", "")),
            str(row.get("permits_2026_nr", "")),
            str(row.get("permits_2026_total", "")),
        )
    return (
        str(row.get("resident_total_permits", "")),
        str(row.get("nonresident_total_permits", "")),
        str(row.get("total_public_permits", "")),
    )


def compare_tuple(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    if not any(left) and not any(right):
        return "NO_SOURCE_ON_EITHER_SIDE"
    if not any(left):
        return "LEFT_SOURCE_MISSING"
    if not any(right):
        return "RIGHT_SOURCE_MISSING"
    if left == right:
        return "MATCH"
    return "DIFFERS"


def add_crosswalk_row(
    rows: list[dict[str, object]],
    row_2024: dict[str, object] | None,
    row_2025: dict[str, object] | None,
    row_2026: dict[str, str] | None,
    status: str,
    confidence: str,
    note: str,
) -> None:
    p2024 = permit_tuple(row_2024, 2024)
    p2025 = permit_tuple(row_2025, 2025)
    p2026 = permit_tuple(row_2026, 2026)
    rows.append(
        {
            "historical_2024_code": row_2024.get("hunt_code", "") if row_2024 else "",
            "historical_2025_code": row_2025.get("hunt_code", "") if row_2025 else "",
            "current_2026_code": row_2026.get("hunt_code", "") if row_2026 else "",
            "mapping_status": status,
            "mapping_confidence": confidence,
            "hunt_name_2024": row_2024.get("raw_hunt_name", "") if row_2024 else "",
            "hunt_name_2025": row_2025.get("raw_hunt_name", "") if row_2025 else "",
            "hunt_name_2026": row_2026.get("hunt_name", "") if row_2026 else "",
            "hunt_type_2026": row_2026.get("hunt_type", "") if row_2026 else "",
            "weapon_2026": row_2026.get("weapon", "") if row_2026 else "",
            "permits_2024_res": p2024[0],
            "permits_2024_nr": p2024[1],
            "permits_2024_total": p2024[2],
            "permits_2025_res": p2025[0],
            "permits_2025_nr": p2025[1],
            "permits_2025_total": p2025[2],
            "permits_2026_res": p2026[0],
            "permits_2026_nr": p2026[1],
            "permits_2026_total": p2026[2],
            "source_2024_page": row_2024.get("page_number", "") if row_2024 else "",
            "source_2025_page": row_2025.get("page_number", "") if row_2025 else "",
            "numeric_comparison_2024_to_2025": compare_tuple(p2024, p2025),
            "numeric_comparison_2025_to_2026": compare_tuple(p2025, p2026),
            "review_note": note,
        }
    )


def current_only_status(code: str, current_row: dict[str, str]) -> tuple[str, str]:
    if code in {"BR7021", "BR7126", "BR7238"}:
        return (
            "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW",
            "Dolores Triangle current row appears as a 2026 split/addition from the old La Sal family; keep as current-only evidence.",
        )
    if code == "BR7307":
        return (
            "CURRENT_CODE_REUSED_FOR_CONSERVATION_PERMIT",
            "BR7307 was a 2025 La Sal limited-entry multiseason draw row; in 2026 it is the La Sal conservation package.",
        )
    if "conservation" in current_row.get("hunt_type", "").lower():
        return (
            "CURRENT_CONSERVATION_NO_DRAW_SOURCE",
            "Current conservation row does not appear as a public draw-odds row; do not force a draw-results match.",
        )
    return (
        "CURRENT_ADMIN_OR_NON_DRAW_ROW",
        "Current 2026 row is present in the permit source but absent from public bonus-draw rows.",
    )


def build_crosswalk(
    draw_2024: dict[str, dict[str, object]],
    draw_2025: dict[str, dict[str, object]],
    current_2026: dict[str, dict[str, str]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    mapped_current_codes: set[str] = set()

    for code in sorted(draw_2025):
        row_2025 = draw_2025[code]
        row_2024 = draw_2024.get(code)
        if code in CURRENT_RECODE_BY_2025_CODE:
            current_code, note = CURRENT_RECODE_BY_2025_CODE[code]
            row_2026 = current_2026.get(current_code)
            if not row_2026:
                raise RuntimeError(f"Expected recoded current code {current_code} for historical {code} is missing")
            status = "HISTORICAL_CODE_RECODED_TO_CURRENT"
            if code == "BR7307":
                status = "HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED"
            add_crosswalk_row(rows, row_2024, row_2025, row_2026, status, "HIGH", note)
            mapped_current_codes.add(current_code)
            continue

        row_2026 = current_2026.get(code)
        if row_2026:
            status = "EXACT_CODE_CURRENT"
            note = "Code exists in 2024/2025 draw evidence and 2026 current permit evidence."
            if not row_2024:
                status = "NEW_IN_2025_AND_CURRENT_2026"
                note = "Code is absent from 2024 draw evidence but present in 2025 draw evidence and current 2026 permits."
            add_crosswalk_row(rows, row_2024, row_2025, row_2026, status, "HIGH", note)
            mapped_current_codes.add(code)
        else:
            add_crosswalk_row(
                rows,
                row_2024,
                row_2025,
                None,
                "HISTORICAL_2025_CODE_MISSING_CURRENT",
                "LOW",
                "Historical draw row has no exact current code and no reviewed recode rule.",
            )

    for code in sorted(set(draw_2024) - set(draw_2025)):
        add_crosswalk_row(
            rows,
            draw_2024[code],
            None,
            current_2026.get(code),
            "RETIRED_AFTER_2024_NO_2025_OR_2026_MATCH",
            "HIGH" if code == "BR7019" else "MEDIUM",
            "Present in 2024 draw evidence but absent from 2025 draw odds. BR7019 has no same-season current 2026 equivalent.",
        )

    for code in sorted(set(current_2026) - mapped_current_codes):
        if code in draw_2025 and code != "BR7307":
            continue
        status, note = current_only_status(code, current_2026[code])
        add_crosswalk_row(rows, None, None, current_2026[code], status, "HIGH", note)

    return sorted(rows, key=lambda row: (str(row.get("current_2026_code") or "ZZZZ"), str(row.get("historical_2025_code") or row.get("historical_2024_code") or "")))


def build_report(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Black Bear BR 2024-2025-2026 Crosswalk",
            "",
            f"- 2024 draw rows: `{summary['draw_2024_rows']}`.",
            f"- 2025 draw rows: `{summary['draw_2025_rows']}`.",
            f"- 2026 current permit rows: `{summary['current_2026_rows']}`.",
            f"- 2025 draw total public permits: `{summary['draw_2025_total_public_permits']}`.",
            f"- 2026 current numeric permit total: `{summary['current_2026_total_numeric_permits']}`.",
            f"- High-confidence historical recodes: `{summary['high_confidence_recode_count']}`.",
            f"- 2025 draw codes missing exact current code before crosswalk: `{summary['draw_2025_codes_missing_exact_current']}`.",
            f"- 2025 draw rows mapped to current codes after crosswalk: `{summary['draw_2025_rows_mapped_to_current_after_crosswalk']}`.",
            "",
            "Key recodes:",
            "",
            "- `BR7307` -> `BR7326`: historical La Sal limited-entry multiseason; `BR7307` is reused for 2026 conservation.",
            "",
            "Current-only rows such as Dolores Triangle split children and conservation permits are preserved as current evidence, not forced historical draw matches.",
            "",
        ]
    )


def main() -> None:
    rows_2024 = parse_pdf(SOURCE_2024_PDF, 2024)
    rows_2025 = parse_pdf(SOURCE_2025_PDF, 2025)
    current_rows = read_csv(PERMITS_2026)

    draw_2024 = keyed(rows_2024)
    draw_2025 = keyed(rows_2025)
    current_2026 = {row["hunt_code"].upper(): row for row in current_rows}

    crosswalk = build_crosswalk(draw_2024, draw_2025, current_2026)
    status_counts = Counter(str(row["mapping_status"]) for row in crosswalk)
    mapped_2025_rows = [row for row in crosswalk if row.get("historical_2025_code") and row.get("current_2026_code")]
    exact_current_missing = sorted(set(draw_2025) - set(current_2026))
    common_2024_2025 = set(draw_2024) & set(draw_2025)
    changed_2024_to_2025 = [
        code
        for code in common_2024_2025
        if permit_tuple(draw_2024[code], 2024) != permit_tuple(draw_2025[code], 2025)
    ]
    differing_2025_to_2026 = [
        row
        for row in mapped_2025_rows
        if row.get("numeric_comparison_2025_to_2026") == "DIFFERS"
    ]

    if len(rows_2025) != 97:
        raise RuntimeError(f"Expected 97 2025 black bear draw rows, got {len(rows_2025)}")
    if len(set(draw_2025)) != len(rows_2025):
        raise RuntimeError("Duplicate 2025 BR hunt codes found")
    if exact_current_missing:
        raise RuntimeError(f"Unexpected 2025 draw codes missing exact current code: {exact_current_missing}")
    if len(mapped_2025_rows) != len(rows_2025):
        raise RuntimeError("Every 2025 draw row should map to a current code after reviewed recodes")

    write_csv(NORMALIZED_2025_OUT, rows_2025, DRAW_FIELDS)
    write_csv(CROSSWALK_OUT, crosswalk, CROSSWALK_FIELDS)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_2024_file": str(SOURCE_2024_PDF.relative_to(ROOT)).replace("\\", "/"),
        "source_2024_sha256": sha256(SOURCE_2024_PDF),
        "source_2025_file": str(SOURCE_2025_PDF.relative_to(ROOT)).replace("\\", "/"),
        "source_2025_sha256": sha256(SOURCE_2025_PDF),
        "current_2026_file": str(PERMITS_2026.relative_to(ROOT)).replace("\\", "/"),
        "draw_2024_rows": len(rows_2024),
        "draw_2025_rows": len(rows_2025),
        "current_2026_rows": len(current_rows),
        "draw_2024_total_public_permits": sum(int(row["total_public_permits"]) for row in rows_2024),
        "draw_2025_total_public_permits": sum(int(row["total_public_permits"]) for row in rows_2025),
        "current_2026_total_numeric_permits": sum(int(row["permits_2026_total"]) for row in current_rows if row.get("permits_2026_total", "").isdigit()),
        "draw_2024_codes_missing_2025": sorted(set(draw_2024) - set(draw_2025)),
        "draw_2025_codes_missing_2024": sorted(set(draw_2025) - set(draw_2024)),
        "draw_2024_to_2025_changed_total_count": len(changed_2024_to_2025),
        "draw_2025_codes_missing_exact_current": exact_current_missing,
        "draw_2025_rows_mapped_to_current_after_crosswalk": len(mapped_2025_rows),
        "draw_2025_to_2026_mapped_numeric_difference_count": len(differing_2025_to_2026),
        "draw_2025_to_2026_mapped_numeric_difference_codes": [
            str(row["historical_2025_code"]) + "->" + str(row["current_2026_code"])
            for row in differing_2025_to_2026
        ],
        "high_confidence_recode_count": status_counts.get("HISTORICAL_CODE_RECODED_TO_CURRENT", 0)
        + status_counts.get("HISTORICAL_CODE_RECODED_BECAUSE_CODE_REUSED", 0),
        "mapping_status_counts": dict(status_counts),
        "normalized_2025_csv": str(NORMALIZED_2025_OUT.relative_to(ROOT)).replace("\\", "/"),
        "crosswalk_csv": str(CROSSWALK_OUT.relative_to(ROOT)).replace("\\", "/"),
    }

    SUMMARY_OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_OUT.write_text(build_report(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
