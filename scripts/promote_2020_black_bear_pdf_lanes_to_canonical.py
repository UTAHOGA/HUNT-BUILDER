#!/usr/bin/env python3
"""Promote a verified retained DWR Black Bear PDF into canonical truth.

The canonical remains one reversible point record with the published resident
and nonresident counts in its dedicated columns.  This promotion does not
create a split from totals: it requires both official lanes from the retained
PDF extraction to recombine exactly to every canonical Bear point record.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YEAR = 2020
CANONICAL = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_2020_for_2021_canonical_yearly_draw_results.csv"
LANES = ROOT / "data_truth/draw_results_truth/validation/black_bear_2018_2022_pdf_residency_ladders.csv"
PDF = ROOT / "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive/black_bear/20_drawing_odds.pdf"
AUDIT_ROOT = ROOT / "audits/database_alignment/black_bear_2020_canonical_promotion"

ADDED_FIELDS = [
    "bear_source_classification",
    "bear_source_identity_source",
    "bear_source_identity_file",
    "bear_source_sha256",
    "bear_source_page",
]

LANE_COUNT_FIELDS = (
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def int_value(value: object) -> int:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else 0


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def configure_report_year(year: int) -> None:
    """Select one of the retained 2018-2022 PDF/canonical pairs."""

    if year not in {2018, 2019, 2020, 2021, 2022}:
        raise ValueError("Only the retained 2018-2022 Black Bear PDF pairs are supported.")
    global YEAR, CANONICAL, PDF, AUDIT_ROOT
    YEAR = year
    suffix = str(year)[-2:]
    CANONICAL = ROOT / f"data_truth/draw_results_truth/normalized/canonical_yearly/draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    PDF = ROOT / f"pipeline/RAW/hunt_unit_database/{year}/pdf/draw_odds/official_dwr_archive/black_bear/{suffix}_drawing_odds.pdf"
    AUDIT_ROOT = ROOT / f"audits/database_alignment/black_bear_{year}_canonical_promotion"


def canonical_key(row: dict[str, str]) -> tuple[str, int] | None:
    code = str(row.get("hunt_code") or "").strip().upper()
    points = str(row.get("points") or "").strip()
    if not code.startswith("BR") or not points.isdigit():
        return None
    if str(row.get("metric_scope") or "").strip().lower() != "total":
        return None
    return code, int(points)


def official_lanes() -> dict[tuple[str, int], list[dict[str, str]]]:
    _, rows = read_csv(LANES)
    grouped: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if int_value(row.get("reported_draw_year")) != YEAR:
            continue
        grouped[(str(row["hunt_code"]).strip().upper(), int_value(row["points"]))].append(row)
    for key, values in grouped.items():
        if {str(row.get("residency") or "").strip() for row in values} != {"Resident", "Nonresident"}:
            raise RuntimeError(f"Official PDF extraction lacks an exact residency pair for {key}.")
    return grouped


def summed_lanes(lanes: list[dict[str, str]]) -> dict[str, int]:
    return {
        "eligible_applicants": sum(int_value(row.get("eligible_applicants")) for row in lanes),
        "bonus_permits": sum(int_value(row.get("bonus_permits")) for row in lanes),
        "regular_permits": sum(int_value(row.get("regular_permits")) for row in lanes),
        "total_permits": sum(int_value(row.get("total_permits")) for row in lanes),
    }


def canonical_counts(row: dict[str, str]) -> dict[str, int]:
    return {field: int_value(row.get(f"total_{field}") or row.get(field)) for field in (
        "eligible_applicants", "bonus_permits", "regular_permits", "total_permits"
    )}


def lane_probability(applicants: int, permits: int) -> str:
    """Return an exact stored probability without relying on rounded PDF text."""

    if applicants <= 0:
        return ""
    return f"{min(1.0, permits / applicants):.10f}".rstrip("0").rstrip(".")


def lane_success_ratio(applicants: int, permits: int) -> str:
    """Preserve the DWR-style odds display for a published residency lane."""

    if applicants <= 0 or permits <= 0:
        return "N/A"
    return f"1 in {applicants / permits:.1f}"


def residency_lane_columns(lanes: list[dict[str, str]]) -> dict[str, str]:
    """Materialize only the two PDF-published lanes; never derive a split."""

    by_residency = {str(lane.get("residency") or "").strip(): lane for lane in lanes}
    if set(by_residency) != {"Resident", "Nonresident"}:
        raise RuntimeError("Official Bear point record must contain one resident and one nonresident lane.")

    output: dict[str, str] = {}
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        lane = by_residency[residency]
        values = {field: int_value(lane.get(field)) for field in LANE_COUNT_FIELDS}
        for field, value in values.items():
            output[f"{prefix}_{field}"] = str(value)
        probability = lane_probability(values["eligible_applicants"], values["total_permits"])
        output[f"{prefix}_p_draw"] = probability
        output[f"{prefix}_p_draw_percent"] = (
            "" if not probability else f"{float(probability) * 100:.8f}".rstrip("0").rstrip(".")
        )
        output[f"{prefix}_success_ratio"] = lane_success_ratio(
            values["eligible_applicants"], values["total_permits"]
        )
    return output


def build_promoted_rows() -> tuple[list[str], list[dict[str, str]], dict[str, object]]:
    fields, rows = read_csv(CANONICAL)
    for field in ADDED_FIELDS:
        if field not in fields:
            fields.append(field)
    lanes_by_key = official_lanes()
    pdf_hash = sha256(PDF)
    canonical_keys: set[tuple[str, int]] = set()
    conflicts: list[dict[str, object]] = []
    changed = 0

    for row in rows:
        key = canonical_key(row)
        if not key:
            continue
        canonical_keys.add(key)
        lane_rows = lanes_by_key.get(key)
        if not lane_rows:
            conflicts.append({"key": key, "issue": "canonical_point_missing_from_official_pdf"})
            continue
        pdf_counts = summed_lanes(lane_rows)
        source_counts = canonical_counts(row)
        if source_counts != pdf_counts:
            conflicts.append({"key": key, "issue": "published_count_mismatch", "canonical": source_counts, "pdf": pdf_counts})
            continue
        metadata = lane_rows[0]
        source_file = relative(PDF)
        row.update(
            {
                "source_scope": "BLACK_BEAR",
                "source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{YEAR}",
                "draw_source_namespace": f"OFFICIAL_DWR_DRAW_RESULTS_{YEAR}",
                "source_file": source_file,
                "draw_source_file": source_file,
                "source_path": source_file,
                "source_pdf": PDF.name,
                "pdf_page": str(metadata["page_number"]),
                "official_page": str(metadata["page_number"]),
                "page_kind": "HUNT_PAGE",
                "source_dataset": f"DWR_{YEAR}_DRAW_RESULTS_PDF",
                "extraction_status": "OK",
                "parse_method": "PDFPLUMBER_TABLE_RECONCILED_TO_CANONICAL",
                "qa_status": "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL",
                "source_residencies": "nonresident; resident",
                "source_row_count": "1",
                "collapse_conflict_count": "0",
                "candidate_promotion_status": "OFFICIAL_SOURCE_PARSED",
                "draw_design": "BEAR_DRAW",
                "draw_system_type": "BEAR_DRAW",
                "draw_pool": "black_bear",
                "draw_system_type_source": "OFFICIAL_DWR_BLACK_BEAR_PDF_RESIDENCY_LADDER",
                "draw_system_type_confidence": "high",
                "bear_source_classification": str(metadata["source_classification"]),
                "bear_source_identity_source": "CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
                "bear_source_identity_file": source_file,
                "bear_source_sha256": pdf_hash,
                "bear_source_page": str(metadata["page_number"]),
                # These are the actual published residency-lane fields.  The
                # legacy 2018 parser retained correct combined totals but
                # misplaced the right-hand table in several per-lane columns.
                # Do not reconstruct values from the combined row: replace
                # them only with the retained PDF extraction above.
                **residency_lane_columns(lane_rows),
            }
        )
        changed += 1

    unexpected = sorted(set(lanes_by_key) - canonical_keys)
    if unexpected:
        conflicts.extend({"key": key, "issue": "official_pdf_point_missing_from_canonical"} for key in unexpected)
    manifest = {
        "reported_draw_year": YEAR,
        "canonical": relative(CANONICAL),
        "official_pdf": {"path": relative(PDF), "sha256": pdf_hash},
        "official_pdf_point_keys": len(lanes_by_key),
        "canonical_bear_point_keys": len(canonical_keys),
        "promoted_rows": changed,
        "conflicts": conflicts,
        "parity_status": "PASS" if not conflicts else "FAIL",
    }
    if conflicts:
        raise RuntimeError(json.dumps(manifest, indent=2))
    return fields, rows, manifest


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2020, help="official report year to promote (2018-2022)")
    parser.add_argument("--apply", action="store_true", help="write canonical only after exact PDF parity succeeds")
    args = parser.parse_args()
    configure_report_year(args.year)
    fields, rows, manifest = build_promoted_rows()
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = AUDIT_ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{CANONICAL.stem}.before_official_bear_lane_promotion_{stamp}.csv"
        shutil.copy2(CANONICAL, backup)
        temporary = CANONICAL.with_suffix(".csv.tmp")
        write_csv(temporary, fields, rows)
        temporary.replace(CANONICAL)
        manifest["applied"] = True
        manifest["rollback_backup"] = relative(backup)
        manifest["canonical_sha256_after"] = sha256(CANONICAL)
    else:
        preview = AUDIT_ROOT / f"draw_results_{YEAR}_for_{YEAR + 1}_canonical_preview.csv"
        write_csv(preview, fields, rows)
        manifest["applied"] = False
        manifest["preview"] = relative(preview)
    (AUDIT_ROOT / "promotion_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
