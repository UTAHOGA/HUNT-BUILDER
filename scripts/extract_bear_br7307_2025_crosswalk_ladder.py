"""Extract the 2025 BR7307 public bear draw ladder used by BR7326 crosswalk.

The main yearly canonical currently contains 2025 BR7307 conservation reference
rows, but the official 2025 Black Bear draw odds PDF also has BR7307 as the
public limited-entry multiseason draw ladder.  This script extracts that narrow
truth patch so the bear prediction engine can use the direct BR7307 -> BR7326
crosswalk without falling back to 2024.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "pdf" / "draw_odds" / "2025 Black Bear Draw odds.pdf"
OUT_CSV = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "black_bear_2025_BR7307_crosswalk_ladder.csv"
OUT_ROWS_JSON = ROOT / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2025_BR7307_crosswalk_ladder_rows.json"
OUT_JSON = ROOT / "data_truth" / "draw_results_truth" / "validation" / "black_bear_2025_BR7307_crosswalk_ladder_summary.json"

FIELDS = [
    "actual_draw_year",
    "model_target_year",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "weapon",
    "season",
    "draw_pool",
    "residency",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "source_file",
    "source_sha256",
    "pdf_page",
    "source_note",
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def to_int(value: object) -> int:
    text = str(value or "").strip()
    if not text:
        return 0
    return int(float(text.replace(",", "")))


def is_int_text(value: object) -> bool:
    text = str(value or "").strip().replace(",", "")
    if not text:
        return False
    try:
        int(float(text))
    except Exception:
        return False
    return True


def main() -> None:
    try:
        import pdfplumber
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("pdfplumber is required to extract the BR7307 bear ladder.") from exc

    source_hash = sha256(SOURCE_PDF)
    source_rel = str(SOURCE_PDF.relative_to(ROOT)).replace("\\", "/")
    rows: list[dict[str, object]] = []
    with pdfplumber.open(SOURCE_PDF) as pdf:
        page = pdf.pages[82]  # Report page 81, PDF page index 82.
        tables = page.extract_tables()
        if not tables:
            raise RuntimeError("No extractable table found for BR7307 on page 83.")
        for cells in tables[0]:
            if len(cells) < 12:
                continue
            if not is_int_text(cells[0]) or not is_int_text(cells[6]):
                continue
            res_points = to_int(cells[0])
            nr_points = to_int(cells[6])
            common = {
                "actual_draw_year": 2025,
                "model_target_year": 2026,
                "hunt_code": "BR7307",
                "hunt_name": "La Sal",
                "species": "Black Bear",
                "sex_type": "Either Sex",
                "hunt_type": "Limited Entry",
                "hunt_class": "Max/Weighted Split",
                "weapon": "Multiseason",
                "season": "Multi-season",
                "draw_pool": "standard",
                "source_file": source_rel,
                "source_sha256": source_hash,
                "pdf_page": 83,
                "source_note": "Official 2025 DWR Black Bear Bonus Point Draw Results; BR7307 public draw row used as BR7326 crosswalk history.",
            }
            rows.append(
                {
                    **common,
                    "residency": "Resident",
                    "points": res_points,
                    "eligible_applicants": to_int(cells[1]),
                    "bonus_permits": to_int(cells[2]),
                    "regular_permits": to_int(cells[3]),
                    "total_permits": to_int(cells[4]),
                }
            )
            rows.append(
                {
                    **common,
                    "residency": "Nonresident",
                    "points": nr_points,
                    "eligible_applicants": to_int(cells[7]),
                    "bonus_permits": to_int(cells[8]),
                    "regular_permits": to_int(cells[9]),
                    "total_permits": to_int(cells[10]),
                }
            )

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    OUT_ROWS_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_ROWS_JSON.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_pdf": source_rel,
        "source_sha256": source_hash,
        "output_csv": str(OUT_CSV.relative_to(ROOT)).replace("\\", "/"),
        "output_rows_json": str(OUT_ROWS_JSON.relative_to(ROOT)).replace("\\", "/"),
        "row_count": len(rows),
        "resident_eligible_applicants": sum(int(row["eligible_applicants"]) for row in rows if row["residency"] == "Resident"),
        "resident_total_permits": sum(int(row["total_permits"]) for row in rows if row["residency"] == "Resident"),
        "nonresident_eligible_applicants": sum(int(row["eligible_applicants"]) for row in rows if row["residency"] == "Nonresident"),
        "nonresident_total_permits": sum(int(row["total_permits"]) for row in rows if row["residency"] == "Nonresident"),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
