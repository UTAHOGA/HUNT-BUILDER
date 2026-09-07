#!/usr/bin/env python3
"""Quarantine derived probability fields on structural 2020 official lanes.

Some retained DWR table rows publish zero applicants together with positive
permits and a success ratio. The canonical preserves that source text and
counts. It clears only derived probability fields for the affected lane so
scoring cannot silently treat a structural zero-applicant row as an
applicant-level probability.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
AUDIT = ROOT / "audits/database_alignment/draw_2020_full_pdf_reconstruction_20260902"
MARKER = "OFFICIAL_SOURCE_ZERO_APPLICANT_STRUCTURAL_ROW_WITH_DISPLAYED_PERMIT"
LEGACY_MARKER = "OFFICIAL_SOURCE_INTERNAL_COUNT_CONFLICT_ZERO_APPLICANTS_WITH_PERMITS"


def number(value: object) -> int | None:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else None


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def conflicts(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for line, row in enumerate(rows, start=2):
        if "DRAW_RESULT" not in str(row.get("record_type") or "").upper():
            continue
        for lane in ("resident", "nonresident"):
            applicants = number(row.get(f"{lane}_eligible_applicants"))
            permits = number(row.get(f"{lane}_total_permits"))
            if applicants == 0 and permits is not None and permits > 0:
                output.append(
                    {
                        "line": str(line),
                        "hunt_code": row.get("hunt_code", ""),
                        "points": row.get("points", ""),
                        "lane": lane,
                        "eligible_applicants": str(applicants),
                        "total_permits": str(permits),
                        "success_ratio": row.get(f"{lane}_success_ratio", ""),
                        "source_file": row.get("source_file", ""),
                        "pdf_page": row.get("pdf_page", ""),
                    }
                )
    return output


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    fields, rows = read_csv(CANONICAL)
    rows_to_flag = conflicts(rows)
    audit_path = AUDIT / "official_pdf_internal_count_conflicts.csv"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    with audit_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows_to_flag[0]) if rows_to_flag else ["line"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_to_flag)

    changed_notes = 0
    cleared_probability_cells = 0
    if args.apply:
        by_line = {int(item["line"]): item for item in rows_to_flag}
        for line, row in enumerate(rows, start=2):
            item = by_line.get(line)
            if not item:
                continue
            note = str(row.get("qa_notes") or "").strip()
            note = "|".join(part for part in note.split("|") if part and not part.startswith(LEGACY_MARKER))
            lane_marker = f"{MARKER}:{item['lane']}"
            if lane_marker not in note.split("|"):
                row["qa_notes"] = "|".join(part for part in (note, lane_marker) if part)
                changed_notes += 1
            for column in (f"{item['lane']}_p_draw", f"{item['lane']}_p_draw_percent"):
                if row.get(column, ""):
                    row[column] = ""
                    cleared_probability_cells += 1
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT / "backups" / f"{CANONICAL.stem}.before_internal_count_conflict_flag_{stamp}.csv"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CANONICAL, backup)
        write_csv(CANONICAL, fields, rows)
    report = {
        "canonical": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "marker": MARKER,
        "conflict_lanes": len(rows_to_flag),
        "changed_note_rows": changed_notes,
        "cleared_derived_probability_cells": cleared_probability_cells,
        "audit": str(audit_path.relative_to(ROOT)).replace("\\", "/"),
        "applied": args.apply,
    }
    (AUDIT / "official_pdf_internal_count_conflicts_summary.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
