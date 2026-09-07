#!/usr/bin/env python3
"""Verify and promote 2025 Black Bear PDF residency-lane provenance.

The 2025 canonical already holds the exact combined applicant and permit
counts.  This tool reads the retained official DWR report, proves every
ordinary public-draw point row has an exact resident/nonresident pair, and
only then attaches the source-lane metadata that Bear forecasting requires.

BR7307 deliberately remains outside this promotion.  Its public draw ladder
is retained in the dedicated BR7307-to-BR7326 crosswalk artifact, while the
normal 2025 canonical represents a separate conservation allocation scope.
No count, probability, hunt identity, or BR7307 row is changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
YEAR = 2025
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
PDF = (
    ROOT
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2025"
    / "pdf"
    / "draw_odds"
    / "official_dwr_archive"
    / "black_bear"
    / "25_drawing_odds.pdf"
)
AUDIT_ROOT = ROOT / "audits" / "database_alignment" / "black_bear_2025_canonical_lane_promotion"
EXCLUDED_PUBLIC_DRAW_CODE = "BR7307"


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_int(value: object) -> int:
    text = str(value or "").strip().replace(",", "")
    return int(text) if text.isdigit() else 0


def is_int(value: object) -> bool:
    return str(value or "").strip().replace(",", "").isdigit()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def source_classification(hunt_name: str) -> str:
    return "BEAR_PURSUIT_BONUS_DRAW" if "pursuit" in hunt_name.lower() else "TRUE_BEAR_BONUS_DRAW"


def official_pdf_lanes() -> tuple[dict[tuple[str, int], dict[str, object]], list[dict[str, object]]]:
    """Return verified two-lane PDF values, keyed by code and point rung."""

    try:
        import pdfplumber
    except ModuleNotFoundError as exc:  # pragma: no cover - environment error
        raise RuntimeError("pdfplumber is required to read retained official Bear PDFs.") from exc

    lanes: dict[tuple[str, int], dict[str, object]] = {}
    hunt_pages: list[dict[str, object]] = []
    with pdfplumber.open(PDF) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            match = re.search(r"Hunt:\s*(BR\d{4})\s+(.+?)\nResident Applicants", text, re.S | re.I)
            if not match:
                continue
            code = match.group(1).upper()
            hunt_name = " ".join(match.group(2).split())
            tables = page.extract_tables()
            if len(tables) != 1:
                raise RuntimeError(f"Expected one official point table on page {page_number} for {code}; found {len(tables)}.")
            point_rows = 0
            for cells in tables[0]:
                if len(cells) < 12 or not is_int(cells[0]) or not is_int(cells[6]):
                    continue
                resident_point, nonresident_point = as_int(cells[0]), as_int(cells[6])
                if resident_point != nonresident_point:
                    raise RuntimeError(
                        f"Official PDF residency point labels disagree on page {page_number} {code}: "
                        f"resident={resident_point}, nonresident={nonresident_point}."
                    )
                key = (code, resident_point)
                if key in lanes:
                    raise RuntimeError(f"Duplicate official PDF key: {key}.")
                lanes[key] = {
                    "hunt_name": hunt_name,
                    "page_number": page_number,
                    "source_classification": source_classification(hunt_name),
                    "resident": {
                        "eligible_applicants": as_int(cells[1]),
                        "bonus_permits": as_int(cells[2]),
                        "regular_permits": as_int(cells[3]),
                        "total_permits": as_int(cells[4]),
                    },
                    "nonresident": {
                        "eligible_applicants": as_int(cells[7]),
                        "bonus_permits": as_int(cells[8]),
                        "regular_permits": as_int(cells[9]),
                        "total_permits": as_int(cells[10]),
                    },
                }
                point_rows += 1
            if point_rows != 23:
                raise RuntimeError(f"Expected 23 point rows on official Bear page {page_number} {code}; found {point_rows}.")
            hunt_pages.append({"hunt_code": code, "hunt_name": hunt_name, "page_number": page_number, "point_rows": point_rows})
    if len(hunt_pages) != 97:
        raise RuntimeError(f"Expected 97 official 2025 Bear hunt pages; found {len(hunt_pages)}.")
    return lanes, hunt_pages


def canonical_key(row: dict[str, str]) -> tuple[str, int] | None:
    code = (row.get("hunt_code") or "").strip().upper()
    points = (row.get("points") or "").strip()
    if not code.startswith("BR") or not points.isdigit():
        return None
    if row.get("record_type") != "point_level_draw_result":
        return None
    if (row.get("metric_scope") or "").strip().lower() != "total":
        return None
    return code, int(points)


def canonical_counts(row: dict[str, str]) -> dict[str, int]:
    return {
        "eligible_applicants": as_int(row.get("total_eligible_applicants")),
        "bonus_permits": as_int(row.get("total_bonus_permits")),
        "regular_permits": as_int(row.get("total_regular_permits")),
        "total_permits": as_int(row.get("total_permits")),
    }


def combined_counts(lane: dict[str, object]) -> dict[str, int]:
    return {
        field: int(lane["resident"][field]) + int(lane["nonresident"][field])
        for field in ("eligible_applicants", "bonus_permits", "regular_permits", "total_permits")
    }


def build_promotion() -> dict[str, object]:
    fields, rows = read_csv(CANONICAL)
    lanes, hunt_pages = official_pdf_lanes()
    canonical_by_key = {key: row for row in rows if (key := canonical_key(row)) is not None}
    expected_lanes = {key: lane for key, lane in lanes.items() if key[0] != EXCLUDED_PUBLIC_DRAW_CODE}
    conflicts: list[dict[str, object]] = []
    parity_rows: list[dict[str, object]] = []

    for key in sorted(expected_lanes):
        lane = expected_lanes[key]
        canonical = canonical_by_key.get(key)
        if canonical is None:
            conflicts.append({"hunt_code": key[0], "points": key[1], "issue": "official_pdf_point_missing_from_canonical"})
            continue
        pdf_counts = combined_counts(lane)
        canon_counts = canonical_counts(canonical)
        if pdf_counts != canon_counts:
            conflicts.append(
                {"hunt_code": key[0], "points": key[1], "issue": "published_count_mismatch", "canonical": canon_counts, "pdf": pdf_counts}
            )
        parity_rows.append(
            {
                "hunt_code": key[0],
                "points": key[1],
                "pdf_page": lane["page_number"],
                "bear_source_classification": lane["source_classification"],
                "resident_eligible_applicants": lane["resident"]["eligible_applicants"],
                "resident_bonus_permits": lane["resident"]["bonus_permits"],
                "resident_regular_permits": lane["resident"]["regular_permits"],
                "resident_total_permits": lane["resident"]["total_permits"],
                "nonresident_eligible_applicants": lane["nonresident"]["eligible_applicants"],
                "nonresident_bonus_permits": lane["nonresident"]["bonus_permits"],
                "nonresident_regular_permits": lane["nonresident"]["regular_permits"],
                "nonresident_total_permits": lane["nonresident"]["total_permits"],
                "canonical_total_eligible_applicants": "" if canonical is None else canon_counts["eligible_applicants"],
                "canonical_total_permits": "" if canonical is None else canon_counts["total_permits"],
                "parity_status": "PASS" if canonical is not None and pdf_counts == canon_counts else "FAIL",
            }
        )

    for key in sorted(set(canonical_by_key) - set(expected_lanes)):
        conflicts.append({"hunt_code": key[0], "points": key[1], "issue": "canonical_point_missing_from_promotable_official_pdf"})

    if conflicts:
        raise RuntimeError(json.dumps({"parity_status": "FAIL", "conflicts": conflicts}, indent=2))

    pdf_hash = sha256(PDF)
    source_file = relative(PDF)
    promoted = 0
    for key, canonical in canonical_by_key.items():
        if key[0] == EXCLUDED_PUBLIC_DRAW_CODE:
            continue
        lane = expected_lanes[key]
        canonical.update(
            {
                "source_scope": "BLACK_BEAR",
                "source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2025",
                "draw_source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2025",
                "source_file": source_file,
                "draw_source_file": source_file,
                "source_path": source_file,
                "source_pdf": PDF.name,
                "pdf_page": str(lane["page_number"]),
                "official_page": str(lane["page_number"]),
                "page_kind": "HUNT_PAGE",
                "source_dataset": "DWR_2025_DRAW_RESULTS_PDF",
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
                "bear_source_classification": str(lane["source_classification"]),
                "bear_source_identity_source": "CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
                "bear_source_identity_file": source_file,
                "bear_source_sha256": pdf_hash,
                "bear_source_page": str(lane["page_number"]),
            }
        )
        promoted += 1

    return {
        "fields": fields,
        "rows": rows,
        "parity_rows": parity_rows,
        "manifest": {
            "reported_draw_year": YEAR,
            "canonical": relative(CANONICAL),
            "official_pdf": {"path": source_file, "sha256": pdf_hash},
            "official_pdf_hunt_pages": len(hunt_pages),
            "official_pdf_point_keys": len(lanes),
            "excluded_public_draw_code": EXCLUDED_PUBLIC_DRAW_CODE,
            "excluded_public_draw_point_keys": sum(1 for key in lanes if key[0] == EXCLUDED_PUBLIC_DRAW_CODE),
            "canonical_bear_point_keys": len(canonical_by_key),
            "promoted_rows": promoted,
            "promoted_hunt_codes": len({key[0] for key in expected_lanes}),
            "source_classification_counts": dict(sorted(Counter(str(row["bear_source_classification"]) for row in parity_rows).items())),
            "parity_status": "PASS",
            "count_changes": 0,
            "identity_changes": 0,
            "br7307_changes": 0,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write source metadata after exact official PDF parity passes")
    args = parser.parse_args()
    result = build_promotion()
    manifest = result["manifest"]
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    parity_path = AUDIT_ROOT / "canonical_2025_bear_pdf_lane_parity.csv"
    parity_fields = list(result["parity_rows"][0])
    write_csv(parity_path, parity_fields, result["parity_rows"])
    manifest["parity_detail"] = relative(parity_path)

    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup_dir = AUDIT_ROOT / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"{CANONICAL.stem}.before_official_bear_lane_promotion_{stamp}.csv"
        shutil.copy2(CANONICAL, backup)
        temporary = CANONICAL.with_suffix(".csv.tmp")
        write_csv(temporary, result["fields"], result["rows"])
        temporary.replace(CANONICAL)
        manifest["applied"] = True
        manifest["rollback_backup"] = relative(backup)
        manifest["canonical_sha256_after"] = sha256(CANONICAL)
    else:
        preview = AUDIT_ROOT / "draw_results_2025_for_2026_canonical_preview.csv"
        write_csv(preview, result["fields"], result["rows"])
        manifest["applied"] = False
        manifest["preview"] = relative(preview)

    (AUDIT_ROOT / "promotion_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
