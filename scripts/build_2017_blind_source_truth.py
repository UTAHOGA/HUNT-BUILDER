"""Reconstruct an audit-local 2017 draw-truth input from official DWR PDFs.

This intentionally produces only a source-side input for a 2017-to-2018
blind forecast.  It never opens the 2018 canonical, the normalized long file,
the runtime database, or prediction outputs.  Each emitted row retains its
official PDF, page, and residency lane.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from extract_2020_draw_results_from_pdfs import HEADER, classify, sex_metadata_for, species_for
from extract_draw_reality import parse_pdf


REPO = Path(__file__).resolve().parents[1]
PDF_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds"
SOURCE_CONFIG = (
    ("official_dwr_archive/big_game/17_big_game_odds_report.pdf", "BIG_GAME"),
    ("official_dwr_archive/big_game_antlerless/17_antlerless_points.pdf", "ANTLERLESS"),
    ("official_dwr_archive/big_game/17_general_deer.pdf", "GENERAL_SEASON_DEER"),
    ("official_dwr_archive/big_game/17_dedicated_hunter_deer.pdf", "DEDICATED_HUNTER"),
    ("official_dwr_archive/big_game/17_youth_any_bull_elk.pdf", "YOUTH_ANY_BULL_ELK"),
    ("official_dwr_archive/big_game/17_youth_general_deer.pdf", "YOUTH_GENERAL_SEASON_DEER"),
    ("official_dwr_archive/big_game_antlerless/17_antlerless_youth_points.pdf", "YOUTH_ANTLERLESS"),
    ("official_dwr_archive/turkey/2017_turkey_bonus_points_and_draw_results.pdf", "TURKEY"),
)
EXCLUDED_SOURCE_SCOPES = {
    "official_dwr_archive/black_bear/17_drawing_odds.pdf": "NO_HUNT_CODE_IN_OFFICIAL_2017_NAME_ONLY_TABLE",
    "official_dwr_archive/big_game/2017_sportsman_odds.pdf": "SOURCE_CODE_TEXT_GARBLED_REQUIRES_SEPARATE_SOURCE_CROSSWALK",
    "official_dwr_archive/big_game/17_lifetime_general_deer.pdf": "REFERENCE_LIFETIME_PERMIT_HOLDER_NOT_PREDICTIVE_DRAW",
}


def clean(value: object) -> str:
    return "" if value is None else " ".join(str(value).strip().split())


def as_int(value: object) -> int:
    try:
        return int(float(clean(value).replace(",", "")))
    except ValueError:
        return 0


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def probability(numerator: int, denominator: int) -> tuple[str, str]:
    if denominator <= 0:
        return "0", "0"
    value = min(1.0, max(0.0, numerator / denominator))
    return f"{value:.10f}".rstrip("0").rstrip("."), f"{value * 100:.8f}".rstrip("0").rstrip(".")


def canonical_row(raw: dict[str, object], source_file: str, scope: str) -> dict[str, str]:
    code = clean(raw["hunt_code"]).upper()
    name = clean(raw["hunt_name"])
    residency = clean(raw["residency"])
    applicants = as_int(raw["eligible_applicants"])
    bonus = as_int(raw["bonus_permits"])
    regular = as_int(raw["regular_permits"])
    permits = as_int(raw["total_permits"])
    p_draw, p_draw_pct = probability(permits, applicants)
    hunt_class, hunt_type, draw_design, algorithm_status = classify(scope, code, name)
    sex, sex_type = sex_metadata_for(code, name)
    row = {field: "" for field in HEADER}
    row.update(
        {
            "actual_draw_year": "2017",
            "model_target_year": "2018",
            "hunt_code": code,
            "hunt_name": name,
            "raw_hunt_name": name,
            "species": species_for(code, name),
            "sex": sex,
            "sex_type": sex_type,
            "hunt_type": hunt_type,
            "draw_design": draw_design,
            "hunt_draw_class": hunt_class,
            "hunt_class": hunt_class,
            "points": str(raw["points"]),
            "residency": residency,
            "row_type": "POINT_ROW",
            "record_type": "point_level_draw_result",
            "eligible_applicants": str(applicants),
            "bonus_permits": str(bonus),
            "regular_permits": str(regular),
            "total_permits": str(permits),
            "success_ratio": clean(raw["success_ratio"]),
            "p_draw": p_draw,
            "p_draw_percent": p_draw_pct,
            "successful_applicants": str(permits),
            "unsuccessful_applicants": str(max(0, applicants - permits)),
            "source_scope": scope,
            "source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2017",
            "draw_source_namespace": "OFFICIAL_DWR_DRAW_RESULTS_2017",
            "source_file": source_file,
            "draw_source_file": source_file,
            "source_path": str((PDF_ROOT / source_file).relative_to(REPO)).replace("\\", "/"),
            "source_pdf": Path(source_file).name,
            "pdf_page": str(raw["page_number"]),
            "official_page": str(raw["page_number"]),
            "page_kind": "HUNT_PAGE",
            "source_dataset": "DWR_2017_DRAW_RESULTS_PDF",
            "extraction_status": "OK",
            "parse_method": "PDFPLUMBER_LINE_LADDER",
            "qa_status": "SOURCE_TABLE_PARSED",
            "algorithm_status": algorithm_status,
            "source_residencies": residency.lower(),
            "source_row_count": "1",
            "collapse_conflict_count": "0",
            "candidate_promotion_status": "AUDIT_LOCAL_SOURCE_ONLY",
            "draw_system_type": draw_design,
            "draw_pool": hunt_class,
            "draw_system_type_source": "2017_OFFICIAL_PDF_SOURCE_SCOPE",
            "draw_system_type_confidence": "high",
            "metric_scope": residency.lower(),
        }
    )
    prefix = "resident" if residency.lower().startswith("res") else "nonresident"
    row[f"{prefix}_eligible_applicants"] = str(applicants)
    row[f"{prefix}_bonus_permits"] = str(bonus)
    row[f"{prefix}_regular_permits"] = str(regular)
    row[f"{prefix}_total_permits"] = str(permits)
    row[f"{prefix}_success_ratio"] = clean(raw["success_ratio"])
    row[f"{prefix}_p_draw"] = p_draw
    row[f"{prefix}_p_draw_percent"] = p_draw_pct
    return row


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=HEADER, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    rows: list[dict[str, str]] = []
    source_counts: dict[str, int] = {}
    source_hashes: dict[str, str] = {}
    for source_file, scope in SOURCE_CONFIG:
        path = PDF_ROOT / source_file
        if not path.exists():
            raise FileNotFoundError(path)
        print(f"Extracting {source_file}", flush=True)
        extracted = parse_pdf(path, 2017)
        converted = [canonical_row(row, source_file, scope) for row in extracted]
        rows.extend(converted)
        source_counts[source_file] = len(converted)
        source_hashes[source_file] = sha256(path)
        print(f"  parsed rows: {len(converted)}", flush=True)

    rows.sort(key=lambda row: (row["source_file"], int(row["pdf_page"]), row["hunt_code"], row["residency"], -as_int(row["points"])))
    duplicate_keys = Counter((row["source_file"], row["pdf_page"], row["hunt_code"], row["residency"], row["points"]) for row in rows)
    duplicate_count = sum(count - 1 for count in duplicate_keys.values() if count > 1)
    if duplicate_count:
        raise ValueError(f"Source parser produced {duplicate_count} duplicate page/hunt/lane/point rows")

    out_csv = args.out_dir / "official_2017_pdf_reconstructed_source_truth.csv"
    out_summary = args.out_dir / "official_2017_pdf_reconstructed_source_manifest.json"
    write_csv(out_csv, rows)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "2017_source_only_input_for_2018_blind_forecast",
        "truth_boundary": {
            "opened_2018_actual_canonical": False,
            "opened_normalized_long_file": False,
            "opened_runtime_database": False,
            "opened_prediction_outputs": False,
        },
        "source_pdf_sha256": source_hashes,
        "source_row_counts": source_counts,
        "rows": len(rows),
        "unique_hunt_codes": len({row["hunt_code"] for row in rows}),
        "residency_rows": dict(Counter(row["residency"] for row in rows)),
        "source_scopes": dict(Counter(row["source_scope"] for row in rows)),
        "excluded_official_source_scopes": EXCLUDED_SOURCE_SCOPES,
        "output_sha256": sha256(out_csv),
        "status": "PASS_SOURCE_ONLY_RECONSTRUCTION",
    }
    out_summary.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
