#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RAW_PDF = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "raw_pdfs"
    / "2025_PERMITS=2026_MODEL"
    / "2025_PERMITS=2026_MODEL__TURKEY DRAW RESULTS.pdf"
)
YOUTH_PDF = RAW_PDF.with_name("2025_PERMITS=2026_MODEL__YOUTH TURKEY DRAW RESULTS.pdf")
CANONICAL = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2025_for_2026_canonical_yearly_draw_results.csv"
)
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
AUDIT_DIR = ROOT / "audits" / "2025_canonical_finalization"
AUDIT_CSV = AUDIT_DIR / "2025_adult_turkey_pdf_patch_audit.csv"
AUDIT_JSON = AUDIT_DIR / "2025_adult_turkey_pdf_patch_summary.json"
EXTRACTOR = ROOT / "scripts" / "extract_draw_reality.py"

SOURCE_FILE = RAW_PDF.name
YOUTH_SOURCE_FILE = YOUTH_PDF.name
SOURCE_NAMESPACE = "official_2025_adult_turkey_raw_pdf_patch"
EXPECTED_YEAR = "2025"
EXPECTED_MODEL_YEAR = "2026"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_extractor():
    spec = importlib.util.spec_from_file_location("extract_draw_reality", EXTRACTOR)
    if not spec or not spec.loader:
        raise RuntimeError(f"Unable to load extractor: {EXTRACTOR}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def clean_int(value: object) -> int:
    text = str(value or "").replace(",", "").strip()
    if not text:
        return 0
    return int(float(text))


def success_probability(success_ratio: str) -> tuple[str, str]:
    ratio = (success_ratio or "").strip()
    match = re.search(r"1\s+in\s+([\d.]+)", ratio, flags=re.I)
    if not match:
        return "0.0", "0"
    denom = float(match.group(1))
    if denom <= 0:
        return "0.0", "0"
    probability = 1.0 / denom
    percent = probability * 100.0
    return f"{probability:.10f}".rstrip("0").rstrip("."), f"{percent:.6f}".rstrip("0").rstrip(".")


def source_scope_for(hunt_type: str) -> str:
    return "CWMU_TURKEY" if hunt_type == "CWMU" else "TURKEY"


def load_metadata() -> dict[str, dict[str, str]]:
    metadata: dict[str, dict[str, str]] = {}
    if DATABASE.exists():
        with DATABASE.open(newline="", encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                code = (row.get("hunt_code") or "").strip()
                if code.startswith("TK") and code not in metadata:
                    metadata[code] = {
                        "hunt_name": row.get("hunt_name", "").strip(),
                        "species": row.get("species", "").strip() or "Turkey",
                        "sex_type": row.get("sex_type", "").strip() or "Bearded",
                        "weapon": row.get("weapon", "").strip() or "Any Legal Weapon",
                        "hunt_type": row.get("hunt_type", "").strip(),
                        "season": row.get("season", "").strip(),
                        "boundary_id": row.get("boundary_id", "").strip(),
                    }
    return metadata


def extract_adult_rows() -> list[dict[str, str]]:
    if not RAW_PDF.exists():
        raise FileNotFoundError(RAW_PDF)
    if not YOUTH_PDF.exists():
        raise FileNotFoundError(YOUTH_PDF)

    adult_hash = sha256(RAW_PDF)
    youth_hash = sha256(YOUTH_PDF)
    if adult_hash == youth_hash:
        raise RuntimeError(
            "Adult turkey PDF is byte-identical to youth turkey PDF. Refusing to patch canonical."
        )

    extractor = load_extractor()
    rows = extractor.parse_pdf(RAW_PDF, 2025)
    if not rows:
        raise RuntimeError(f"No draw-result rows extracted from {RAW_PDF}")
    if not any(row.get("hunt_code", "").startswith("TK") for row in rows):
        raise RuntimeError("Extracted adult turkey rows did not include TK hunt codes.")
    return rows


def build_canonical_rows(
    extracted_rows: list[dict[str, str]],
    fieldnames: list[str],
    metadata: dict[str, dict[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    permit_totals: dict[str, dict[str, int]] = defaultdict(lambda: {"Resident": 0, "Nonresident": 0})
    for row in extracted_rows:
        permit_totals[row["hunt_code"]][row["residency"]] += clean_int(row.get("total_permits"))

    built: list[dict[str, str]] = []
    audit_rows: list[dict[str, str]] = []
    for row in extracted_rows:
        code = row["hunt_code"]
        meta = metadata.get(code, {})
        eligible = clean_int(row.get("eligible_applicants"))
        total_permits = clean_int(row.get("total_permits"))
        p_draw, p_draw_percent = success_probability(row.get("success_ratio", ""))
        successful = total_permits
        unsuccessful = max(eligible - successful, 0)
        res_total = permit_totals[code]["Resident"]
        nr_total = permit_totals[code]["Nonresident"]
        all_total = res_total + nr_total

        out = {field: "" for field in fieldnames}
        out.update(
            {
                "actual_draw_year": EXPECTED_YEAR,
                "model_target_year": EXPECTED_MODEL_YEAR,
                "source_scope": source_scope_for(meta.get("hunt_type", "")),
                "source_namespace": SOURCE_NAMESPACE,
                "draw_source_namespace": SOURCE_NAMESPACE,
                "source_file": SOURCE_FILE,
                "pdf_page": str(row.get("page_number", "")),
                "page_kind": "",
                "hunt_code": code,
                "hunt_name": meta.get("hunt_name") or row.get("hunt_name", ""),
                "species": meta.get("species") or "Turkey",
                "sex_type": meta.get("sex_type") or "Bearded",
                "draw_design": "Max/Weighted Split",
                "weapon": meta.get("weapon") or "Any Legal Weapon",
                "hunt_type": meta.get("hunt_type") or "Limited Entry",
                "season": meta.get("season", ""),
                "residency": row["residency"],
                "points": str(row["points"]),
                "eligible_applicants": str(eligible),
                "bonus_permits": str(clean_int(row.get("bonus_permits"))),
                "regular_permits": str(clean_int(row.get("regular_permits"))),
                "total_permits": str(total_permits),
                "successful_applicants": str(successful),
                "unsuccessful_applicants": str(unsuccessful),
                "success_ratio": "" if row.get("success_ratio", "").upper() == "N/A" else row.get("success_ratio", ""),
                "p_draw": p_draw,
                "p_draw_percent": p_draw_percent,
                "record_type": "point_level_draw_result",
                "boundary_id": meta.get("boundary_id", ""),
                "algorithm_status": "",
                "source_dataset": SOURCE_NAMESPACE,
                "extraction_status": "",
                "parse_method": "extract_draw_reality.parse_pdf",
                "qa_status": "",
                "notes": "Adult turkey draw-result rows extracted from corrected 2025 raw PDF; point-purchase page intentionally ignored.",
                "permits_2025_res": str(res_total),
                "permits_2025_nr": str(nr_total),
                "permits_2025_total": str(all_total),
            }
        )
        built.append(out)
        audit_rows.append(
            {
                "source_file": SOURCE_FILE,
                "hunt_code": code,
                "hunt_name": out["hunt_name"],
                "residency": row["residency"],
                "points": str(row["points"]),
                "eligible_applicants": str(eligible),
                "total_permits": str(total_permits),
                "permits_2025_res": str(res_total),
                "permits_2025_nr": str(nr_total),
                "permits_2025_total": str(all_total),
                "boundary_id": out["boundary_id"],
                "hunt_type": out["hunt_type"],
                "draw_design": out["draw_design"],
                "season": out["season"],
            }
        )
    return built, audit_rows


def replace_source_rows(
    rows: list[dict[str, str]],
    new_rows: list[dict[str, str]],
    fieldnames: list[str],
    *,
    year_only: bool = False,
) -> tuple[list[dict[str, str]], int]:
    kept: list[dict[str, str]] = []
    removed = 0
    for row in rows:
        is_target_source = row.get("source_file") == SOURCE_FILE
        if year_only:
            is_target_source = is_target_source and row.get("actual_draw_year") == EXPECTED_YEAR
        if is_target_source:
            removed += 1
            continue
        kept.append(row)

    normalized_new = [{field: row.get(field, "") for field in fieldnames} for row in new_rows]
    return kept + normalized_new, removed


def main() -> int:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    extracted = extract_adult_rows()
    metadata = load_metadata()

    canonical_fields, canonical_rows = read_csv(CANONICAL)
    adult_canonical_rows, audit_rows = build_canonical_rows(extracted, canonical_fields, metadata)
    updated_canonical, removed_canonical = replace_source_rows(
        canonical_rows, adult_canonical_rows, canonical_fields
    )
    write_csv(CANONICAL, canonical_fields, updated_canonical)

    long_fields, long_rows = read_csv(LONG)
    adult_long_rows = [{field: row.get(field, "") for field in long_fields} for row in adult_canonical_rows]
    updated_long, removed_long = replace_source_rows(
        long_rows, adult_long_rows, long_fields, year_only=True
    )
    write_csv(LONG, long_fields, updated_long)

    audit_fields = [
        "source_file",
        "hunt_code",
        "hunt_name",
        "residency",
        "points",
        "eligible_applicants",
        "total_permits",
        "permits_2025_res",
        "permits_2025_nr",
        "permits_2025_total",
        "boundary_id",
        "hunt_type",
        "draw_design",
        "season",
    ]
    write_csv(AUDIT_CSV, audit_fields, audit_rows)

    summary = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "adult_pdf": str(RAW_PDF.relative_to(ROOT)).replace("\\", "/"),
        "adult_pdf_sha256": sha256(RAW_PDF),
        "youth_pdf": str(YOUTH_PDF.relative_to(ROOT)).replace("\\", "/"),
        "youth_pdf_sha256": sha256(YOUTH_PDF),
        "extracted_rows": len(extracted),
        "inserted_rows": len(adult_canonical_rows),
        "unique_hunt_codes": len({row["hunt_code"] for row in adult_canonical_rows}),
        "removed_existing_canonical_rows_for_source": removed_canonical,
        "removed_existing_long_rows_for_source": removed_long,
        "canonical_rows_after": len(updated_canonical),
        "long_rows_after": len(updated_long),
        "audit_csv": str(AUDIT_CSV.relative_to(ROOT)).replace("\\", "/"),
        "status": "patched",
    }
    AUDIT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
