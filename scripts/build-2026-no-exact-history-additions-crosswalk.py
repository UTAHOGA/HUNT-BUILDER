#!/usr/bin/env python3
"""Build the source disposition for 2026 additions without exact draw history.

This is deliberately a *non-prediction* crosswalk.  It proves only that these
official 2026 draw-result codes have no exact-code row in the retained
2018-2025 canonical draw-result series.  It must not substitute a same-unit or
similar hunt as a historical predecessor, and the resulting rows remain out of
blind scoring until DWR-published predecessor evidence is retained.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
OUT = ROOT / "data_truth" / "crosswalk_truth" / "normalized" / "2026_no_exact_history_additions_crosswalk.csv"
SUMMARY = ROOT / "data_truth" / "crosswalk_truth" / "validation" / "2026_no_exact_history_additions_crosswalk_summary.json"
REPORT = ROOT / "data_truth" / "crosswalk_truth" / "validation" / "2026_no_exact_history_additions_crosswalk.md"

TARGET_NOTES = {
    "BI6539": "The official 2026 Female Only Henry Mtns bison result uses a code absent from the retained 2018-2025 canonical draw series. Older Henry Mtns bison codes are not a DWR-published successor mapping and cannot supply probability history.",
    "BR7021": "The official 2026 Dolores Triangle bear-season result uses a code absent from the retained 2018-2025 canonical draw series. No official predecessor mapping is retained, so it remains unscored rather than borrowing another bear season's odds.",
    "BR7126": "The official 2026 Dolores Triangle bear-season result uses a code absent from the retained 2018-2025 canonical draw series. No official predecessor mapping is retained, so it remains unscored rather than borrowing another bear season's odds.",
    "BR7238": "The official 2026 Dolores Triangle bear-season result uses a code absent from the retained 2018-2025 canonical draw series. No official predecessor mapping is retained, so it remains unscored rather than borrowing another bear season's odds.",
    "DB1109": "DWR first labels this Thousand Lakes restricted multiseason deer hunt new in the 2025 application guidebook. It has no exact 2018-2025 canonical draw-result ladder, so guidebook identity alone cannot be used as a forecast source.",
    "DB1121": "The official 2026 Antelope Island limited-entry deer result uses a code absent from the retained 2018-2025 canonical draw series. A same-unit premium hunt is not an official successor mapping and cannot be used as a forecast source.",
}

# Hunt numbers appear in DWR's application guidebooks, not in the separate
# field-regulation PDFs. The dated page evidence below was verified against the
# retained official guidebooks.  The field-regulation PDFs for 2018-2026 were
# also searched for these codes and contained no hunt-number occurrence.
GUIDEBOOK_EVIDENCE = {
    "BI6539": ("2026", "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf", "65", "NEW", "65"),
    "BR7021": ("2026", "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/black-bear-cougar-furbearer-guidebook.pdf", "73", "NEW", "73"),
    "BR7126": ("2026", "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/black-bear-cougar-furbearer-guidebook.pdf", "74", "NEW", "74"),
    "BR7238": ("2026", "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/black-bear-cougar-furbearer-guidebook.pdf", "75", "NEW", "75"),
    "DB1109": ("2025", "pipeline/RAW/hunt_unit_database/2025/pdf/guidebooks/2025_biggameapp.pdf", "49", "NEW", "53"),
    "DB1121": ("2026", "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf", "50", "NEW", "50"),
}

FIELDNAMES = [
    "current_hunt_code",
    "current_hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "weapon",
    "boundary_id",
    "actual_draw_year",
    "draw_system_type",
    "guidebook_first_listed_year",
    "guidebook_first_listed_file",
    "guidebook_first_listed_page",
    "guidebook_first_listing_label",
    "guidebook_last_checked_year",
    "guidebook_last_checked_file",
    "guidebook_last_checked_page",
    "guidebook_current_status",
    "field_regulation_code_search_2018_2026",
    "history_exact_code_years",
    "historical_hunt_code",
    "relationship_type",
    "predecessor_status",
    "crosswalk_status",
    "mapping_confidence",
    "recommended_model_behavior",
    "mapping_method",
    "source_files",
    "source_scopes",
    "source_note",
]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def one_value(rows: list[dict[str, str]], field: str, code: str) -> str:
    values = sorted({clean(row.get(field)) for row in rows if clean(row.get(field))})
    if len(values) != 1:
        raise RuntimeError(f"{code}: expected one {field!r} value, found {values!r}")
    return values[0]


def main() -> None:
    current_path = CANONICAL_DIR / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
    if not current_path.exists():
        raise FileNotFoundError(current_path)

    historical_paths = [
        CANONICAL_DIR / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
        for year in range(2018, 2026)
    ]
    missing = [str(path) for path in historical_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Missing historical canonical inputs: {missing}")

    current_rows = read_rows(current_path)
    current_by_code: dict[str, list[dict[str, str]]] = {}
    for row in current_rows:
        code = clean(row.get("hunt_code")).upper()
        if code in TARGET_NOTES:
            current_by_code.setdefault(code, []).append(row)
    if set(current_by_code) != set(TARGET_NOTES):
        raise RuntimeError(f"2026 target identity mismatch: found {sorted(current_by_code)}, expected {sorted(TARGET_NOTES)}")

    exact_history_years: dict[str, list[int]] = {code: [] for code in TARGET_NOTES}
    for path in historical_paths:
        year = int(path.name.split("_")[2])
        seen = {clean(row.get("hunt_code")).upper() for row in read_rows(path)}
        for code in TARGET_NOTES:
            if code in seen:
                exact_history_years[code].append(year)
    unexpected_history = {code: years for code, years in exact_history_years.items() if years}
    if unexpected_history:
        raise RuntimeError(f"Expected no exact 2018-2025 history; found {unexpected_history}")

    output_rows: list[dict[str, str]] = []
    for code in sorted(TARGET_NOTES):
        rows = current_by_code[code]
        first_year, first_file, first_page, first_label, current_page = GUIDEBOOK_EVIDENCE[code]
        current_file = (
            "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/black-bear-cougar-furbearer-guidebook.pdf"
            if code.startswith("BR")
            else "pipeline/RAW/hunt_unit_database/2026/pdf/guidebooks/biggameapp.pdf"
        )
        output_rows.append(
            {
                "current_hunt_code": code,
                "current_hunt_name": one_value(rows, "hunt_name", code),
                "species": one_value(rows, "species", code),
                "sex_type": one_value(rows, "sex_type", code),
                "hunt_type": one_value(rows, "hunt_type", code),
                "weapon": one_value(rows, "weapon", code),
                "boundary_id": one_value(rows, "boundary_id", code),
                "actual_draw_year": "2026",
                "draw_system_type": one_value(rows, "draw_system_type", code),
                "guidebook_first_listed_year": first_year,
                "guidebook_first_listed_file": first_file,
                "guidebook_first_listed_page": first_page,
                "guidebook_first_listing_label": first_label,
                "guidebook_last_checked_year": "2026",
                "guidebook_last_checked_file": current_file,
                "guidebook_last_checked_page": current_page,
                "guidebook_current_status": "LISTED_ACTIVE_NOT_DISCONTINUED_THROUGH_2026",
                "field_regulation_code_search_2018_2026": "NO_HUNT_NUMBER_HITS; APPLICATION_GUIDEBOOK_IS_CODE_AUTHORITY",
                "history_exact_code_years": "",
                "historical_hunt_code": "",
                "relationship_type": "CURRENT_CODE_WITHOUT_EXACT_HISTORICAL_DRAW_HISTORY",
                "predecessor_status": "NO_OFFICIAL_PREDECESSOR_MAPPING_RETAINED",
                "crosswalk_status": "SOURCE_VERIFIED_UNSCORED_NO_EXACT_HISTORY",
                "mapping_confidence": "HIGH",
                "recommended_model_behavior": "DO_NOT_EMIT_PROBABILITY_OR_SCORE_UNTIL_OFFICIAL_PREDECESSOR_EXISTS",
                "mapping_method": "OFFICIAL_2026_CANONICAL_IDENTITY_PLUS_2018_2025_EXACT_CODE_ABSENCE",
                "source_files": "|".join(sorted({clean(row.get("source_file")) for row in rows if clean(row.get("source_file"))})),
                "source_scopes": "|".join(sorted({clean(row.get("source_scope")) for row in rows if clean(row.get("source_scope"))})),
                "source_note": TARGET_NOTES[code],
            }
        )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(output_rows)

    summary = {
        "artifact": str(OUT.relative_to(ROOT)).replace("\\", "/"),
        "artifact_sha256": sha256(OUT),
        "source_current_canonical": str(current_path.relative_to(ROOT)).replace("\\", "/"),
        "source_current_canonical_sha256": sha256(current_path),
        "historical_exact_code_search_years": list(range(2018, 2026)),
        "records": len(output_rows),
        "codes": [row["current_hunt_code"] for row in output_rows],
        "status": "PASS_SOURCE_VERIFIED_UNSCORED_NO_EXACT_HISTORY",
        "policy": "No same-unit, same-species, or similar-season row is promoted as a predecessor without an official DWR source mapping. These rows remain outside prediction scoring and no probability is emitted from this artifact. DWR field-regulation PDFs do not carry these hunt-number rows; the dated DWR application guidebook is the retained code authority.",
    }
    with SUMMARY.open("w", encoding="utf-8", newline="") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")

    lines = [
        "# 2026 Additions Without Exact Historical Draw History",
        "",
        "This source crosswalk verifies the absence of an exact 2018-2025 canonical draw-history code for each listed official 2026 result. It is an exclusion artifact, not a probability or proxy-history table. The code-presence evidence comes from DWR application guidebooks; the separate 2018-2026 field-regulation PDFs contain no hunt-number hit for these codes.",
        "",
        "| 2026 code | Hunt | First listed | Current 2026 status | Status |",
        "| --- | --- | --- | --- | --- |",
    ]
    lines.extend(
        f"| {row['current_hunt_code']} | {row['current_hunt_name']} | {row['guidebook_first_listed_year']} ({row['guidebook_first_listing_label']}) | {row['guidebook_current_status']} | {row['crosswalk_status']} |"
        for row in output_rows
    )
    lines.extend(
        [
            "",
            "No code in this table is modeled or added to blind scoring until a time-aligned official DWR predecessor mapping is retained.",
            "",
        ]
    )
    REPORT.write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
