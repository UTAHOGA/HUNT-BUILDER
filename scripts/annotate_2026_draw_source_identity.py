#!/usr/bin/env python3
"""Restore source-row identity metadata for the 2026 UtahDraws canonical.

The official UtahDraws turkey endpoint emits adult and youth set-aside ladders
under the same public hunt code.  Earlier normalization retained the outcomes
but omitted the source's ``IsYouth`` dimension, making otherwise distinct
official rows look duplicated.  This script adds source-row identity only; it
does not change an applicant, permit, or probability value.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
)
CONSERVATION_CANONICAL = (
    ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
TURKEY_SOURCE = (
    ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results"
    / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_turkey_03_turkey.csv"
)
AUDIT = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_results_2026_source_identity_annotation.csv"
IDENTIFIER_FIELD = "source_row_identifier"
YOUTH_FIELD = "source_is_youth"
LIVE_TURKEY_DATASET = "UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH_20260618"
CONSERVATION_SCOPE = "BLACK_BEAR_CONSERVATION_ORGANIZATION_ALLOCATION"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def point(value: object) -> str:
    text = clean(value)
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_rows(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temp.replace(path)


def turkey_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("HuntCode") or row.get("hunt_code")).upper(),
        clean(row.get("residency_label") or row.get("residency")),
        point(row.get("Point") or row.get("points")),
        clean(row.get("ParticipantCount") or row.get("eligible_applicants")),
        clean(row.get("SuccessfulCount") or row.get("total_permits")),
    )


def conservation_identifier(notes: str) -> str:
    rows = re.findall(r"source row (\d+)", notes, flags=re.I)
    if not rows:
        raise ValueError(f"Could not retain the official conservation source row from: {notes}")
    return "conservation-permit-source-rows=" + ",".join(rows)


def main() -> int:
    canonical_fields, canonical_rows = read_rows(CANONICAL)
    conservation_fields, conservation_rows = read_rows(CONSERVATION_CANONICAL)
    _, turkey_rows = read_rows(TURKEY_SOURCE)
    turkey_index: dict[tuple[str, str, str, str, str], list[tuple[int, dict[str, str]]]] = defaultdict(list)
    for source_row_number, source_row in enumerate(turkey_rows, start=2):
        turkey_index[turkey_key(source_row)].append((source_row_number, source_row))

    audit_rows: list[dict[str, str]] = []
    represented_source_row_numbers: set[int] = set()
    matched_turkey_rows = 0
    matched_conservation_rows = 0
    unresolved: list[str] = []
    for canonical_row_number, row in enumerate(canonical_rows, start=2):
        if clean(row.get("source_dataset")) == LIVE_TURKEY_DATASET and clean(row.get("notes")) == "2026_turkey_03_turkey":
            candidates = turkey_index[turkey_key(row)]
            if len(candidates) == 1:
                source_row_number, source_row = candidates[0]
                row[IDENTIFIER_FIELD] = (
                    f"utahdraws:{source_row.get('source_json_file')}"
                    f":hunt-id={source_row.get('HuntID')}:is-youth={clean(source_row.get('IsYouth')).lower()}"
                    f":csv-row={source_row_number}"
                )
                row[YOUTH_FIELD] = clean(source_row.get("IsYouth")).lower()
                represented_source_row_numbers.add(source_row_number)
                status = "MATCHED_TURKEY_SOURCE_ROW"
            elif (
                len(candidates) == 2
                and clean(row.get("eligible_applicants")) == "0"
                and clean(row.get("total_permits")) == "0"
                and {clean(candidate.get("IsYouth")).lower() for _, candidate in candidates} == {"false", "true"}
            ):
                # The historical canonical coalesced this no-applicant/no-permit
                # CWMU adult/youth pair.  Preserve both exact official source
                # rows rather than guessing which lane the single zero row meant.
                identifiers = []
                for source_row_number, source_row in candidates:
                    identifiers.append(
                        f"utahdraws:{source_row.get('source_json_file')}"
                        f":hunt-id={source_row.get('HuntID')}:is-youth={clean(source_row.get('IsYouth')).lower()}"
                        f":csv-row={source_row_number}"
                    )
                    represented_source_row_numbers.add(source_row_number)
                row[IDENTIFIER_FIELD] = "coalesced-official-source-rows=" + "|".join(identifiers)
                row[YOUTH_FIELD] = "ambiguous_coalesced_true_false"
                status = "MATCHED_TURKEY_SOURCE_ROW_COALESCED_ZERO_OUTCOME"
            else:
                unresolved.append(
                    f"canonical row {canonical_row_number}: no safe official turkey identity for {turkey_key(row)}, found {len(candidates)} candidates"
                )
                continue
            matched_turkey_rows += 1
            audit_rows.append(
                {
                    "canonical_row": str(canonical_row_number), "status": status,
                    "hunt_code": row.get("hunt_code", ""), "residency": row.get("residency", ""),
                    "points": row.get("points", ""), IDENTIFIER_FIELD: row[IDENTIFIER_FIELD],
                }
            )

    # Turkey Bonus Point rows are point-purchase/reference rows (quota and
    # successful count are both zero), not draw probability outcomes.  Keep
    # their source exclusion explicit so coverage is never mistaken for loss.
    for source_row_number, source_row in enumerate(turkey_rows, start=2):
        if source_row_number in represented_source_row_numbers:
            continue
        if clean(source_row.get("HuntCategoryName")) == "Bonus Point" and clean(source_row.get("SuccessfulCount")) == "0":
            audit_rows.append(
                {
                    "canonical_row": "", "status": "EXCLUDED_BONUS_POINT_REFERENCE",
                    "hunt_code": clean(source_row.get("HuntCode")),
                    "residency": clean(source_row.get("residency_label")),
                    "points": point(source_row.get("Point")),
                    IDENTIFIER_FIELD: (
                        f"utahdraws:{source_row.get('source_json_file')}:hunt-id={source_row.get('HuntID')}"
                        f":is-youth={clean(source_row.get('IsYouth')).lower()}:csv-row={source_row_number}"
                    ),
                }
            )
        else:
            unresolved.append(
                f"official turkey source row {source_row_number} was neither represented nor a point-purchase reference"
            )

    for canonical_row_number, row in enumerate(conservation_rows, start=2):
        if clean(row.get("source_scope")) != CONSERVATION_SCOPE:
            continue
        row[IDENTIFIER_FIELD] = conservation_identifier(clean(row.get("notes")))
        matched_conservation_rows += 1
        audit_rows.append(
            {
                "canonical_row": f"2025:{canonical_row_number}", "status": "MATCHED_CONSERVATION_SOURCE_ROW",
                "hunt_code": row.get("hunt_code", ""), "residency": row.get("residency", ""),
                "points": row.get("points", ""), IDENTIFIER_FIELD: row[IDENTIFIER_FIELD],
            }
        )

    if unresolved:
        raise RuntimeError("\n".join(unresolved))
    fields = list(canonical_fields)
    for field in (IDENTIFIER_FIELD, YOUTH_FIELD):
        if field not in fields:
            fields.append(field)
    write_rows(CANONICAL, fields, canonical_rows)
    conservation_fields = list(conservation_fields)
    if IDENTIFIER_FIELD not in conservation_fields:
        conservation_fields.append(IDENTIFIER_FIELD)
    write_rows(CONSERVATION_CANONICAL, conservation_fields, conservation_rows)
    write_rows(AUDIT, ["canonical_row", "status", "hunt_code", "residency", "points", IDENTIFIER_FIELD], audit_rows)
    print(
        {
            "canonicals": [str(CANONICAL.relative_to(ROOT)), str(CONSERVATION_CANONICAL.relative_to(ROOT))],
            "matched_turkey_rows": matched_turkey_rows,
            "matched_conservation_rows": matched_conservation_rows,
            "identifier_counts": dict(Counter(row["status"] for row in audit_rows)),
            "status": "PASS",
        }
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
