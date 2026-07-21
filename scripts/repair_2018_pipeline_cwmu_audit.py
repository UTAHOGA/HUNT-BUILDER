#!/usr/bin/env python3
"""Build the 2018 pipeline-first CWMU repair audit package."""

from __future__ import annotations

import csv
import hashlib
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pdfplumber


REPO = Path(__file__).resolve().parents[1]
PIPELINE_CWMU_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2018"
DATATRUTH_CWMU_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2018_PERMITS=2019_MODEL" / "CWMU"
CANONICAL_2018 = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
)
PRED_PATH = (
    REPO
    / "audits"
    / "prediction_blind_year_to_year"
    / "full_engine_equivalent_2017_to_2018"
    / "runs"
    / "2018_20260707_le_split_check"
    / "family_predictions.csv"
)
KEY_BUILDER = REPO / "scripts" / "build_score_key_v2_truth_comparable_from_prediction_surface.py"


def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str] | None = None) -> None:
    if fields is None:
        fields = []
        for row in rows:
            for key in row:
                if key not in fields:
                    fields.append(key)
        fields = fields or ["no_rows"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def csv_profile(path: Path) -> dict[str, Any]:
    out = {
        "row_count_if_csv": "",
        "columns_if_csv": "",
        "has_hunt_code": "",
        "has_residency": "",
        "has_official_score_key_v2": "",
        "has_resident_p_draw": "",
        "has_nonresident_p_draw": "",
        "has_total_p_draw": "",
    }
    if path.suffix.lower() != ".csv":
        return out
    try:
        fields, rows = read_csv(path)
    except Exception as exc:
        out["columns_if_csv"] = f"CSV_READ_ERROR:{exc}"
        return out
    fieldset = set(fields)
    out.update(
        {
            "row_count_if_csv": len(rows),
            "columns_if_csv": ";".join(fields),
            "has_hunt_code": str("hunt_code" in fieldset).lower(),
            "has_residency": str("residency" in fieldset).lower(),
            "has_official_score_key_v2": str("official_score_key_v2" in fieldset).lower(),
            "has_resident_p_draw": str("resident_p_draw" in fieldset).lower(),
            "has_nonresident_p_draw": str("nonresident_p_draw" in fieldset).lower(),
            "has_total_p_draw": str("total_p_draw" in fieldset).lower(),
        }
    )
    return out


def pdf_page_count(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return str(len(pdf.pages))
    except Exception as exc:
        return f"PDF_READ_ERROR:{exc}"


def infer_cwmu(path: Path, role: str) -> dict[str, str]:
    text = rel(path).replace("\\", "/").upper()
    name = path.name.upper()
    is_youth = "YOUTH_ANTLERLESS" in name or "YOUTH ANTLERLESS" in text
    is_antlerless = "ANTLERLESS" in name or "DOE_PRONGHORN" in name or "DOE PRONGHORN" in text
    is_big_game = "BIG_GAME" in name or "BIG GAME" in text
    if is_youth:
        family = "CWMU_YOUTH_ANTLERLESS"
    elif is_antlerless:
        family = "CWMU_ANTLERLESS"
    elif is_big_game:
        family = "CWMU_BIG_GAME"
    else:
        family = "CWMU_UNKNOWN"
    species = "UNKNOWN"
    for candidate in ("DEER", "ELK", "PRONGHORN", "MOOSE"):
        if candidate in name:
            species = candidate
            break
    return {
        "inferred_role": role,
        "inferred_cwmu_family": family,
        "inferred_species_group": species,
        "is_big_game": str(is_big_game).lower(),
        "is_antlerless": str(is_antlerless and not is_youth).lower(),
        "is_youth_antlerless": str(is_youth).lower(),
    }


def inventory_files(files: list[Path], role: str) -> list[dict[str, Any]]:
    rows = []
    for path in sorted(files, key=lambda item: rel(item).lower()):
        stat = path.stat()
        row: dict[str, Any] = {
            "path": rel(path),
            "file_name": path.name,
            "file_type": path.suffix.lower().lstrip("."),
            "size_bytes": stat.st_size,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        }
        row.update(infer_cwmu(path, role))
        row["page_count_if_pdf"] = pdf_page_count(path)
        row.update(csv_profile(path))
        row["sha256"] = sha256_file(path)
        row["notes"] = ""
        rows.append(row)
    return rows


def selected_pipeline_file(path: Path) -> bool:
    route = rel(path).replace("\\", "/").upper()
    name = path.name.upper()
    if path.suffix.lower() != ".pdf":
        return False
    if "/DRAW_ODDS/CWMU/" not in route:
        return False
    if any(token in route for token in ("DRAW_ODDS_ARTIFACT", "IGNORED", "DUPLICATE", "PARENT BUNDLES")):
        return False
    return name.startswith("2018_PERMITS=2019_MODEL__CWMU_") and ("DRAW_RESULTS" in name or "BIG_GAME" in name)


def classify_from_name(name: str) -> dict[str, str]:
    upper_name = name.upper()
    youth = "YOUTH_ANTLERLESS" in upper_name
    antlerless = "ANTLERLESS" in upper_name or "DOE_PRONGHORN" in upper_name
    if "DEER" in upper_name:
        species = "Deer"
    elif "ELK" in upper_name:
        species = "Elk"
    elif "PRONGHORN" in upper_name:
        species = "Pronghorn"
    elif "MOOSE" in upper_name:
        species = "Moose"
    else:
        species = ""
    if "BUCK" in upper_name:
        sex = "Buck"
    elif "BULL" in upper_name:
        sex = "Bull"
    elif "DOE" in upper_name:
        sex = "Doe"
    elif antlerless:
        sex = "Antlerless"
    else:
        sex = ""
    if youth:
        source_family = "YOUTH_ANTLERLESS"
        draw_pool = f"youth_antlerless_{species.lower()}" if species.lower() != "pronghorn" else "youth_doe_pronghorn"
    else:
        source_family = "CWMU_BIG_GAME"
        draw_pool = "bonus_cwmu_big_game"
    return {
        "species": species,
        "sex": sex,
        "weapon": "Any Legal Weapon",
        "hunt_class": "CWMU",
        "source_family": source_family,
        "draw_family": source_family,
        "draw_design": "BONUS_CWMU_BIG_GAME",
        "draw_system_type": "BONUS_CWMU_BIG_GAME",
        "draw_pool": draw_pool,
    }


def parse_int(value: Any) -> int | None:
    text = clean(value).replace(",", "")
    if not text or text.upper() == "N/A":
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def parse_probability(raw: Any) -> tuple[str, str, str]:
    text = clean(raw)
    if not text or text.upper() == "N/A":
        return "", text, ""
    ratio = re.search(r"1\s+in\s+([0-9]+(?:\.[0-9]+)?)", text, re.I)
    if ratio:
        denominator = float(ratio.group(1))
        return (f"{1 / denominator:.12g}" if denominator else "", text, "RATIO_1_IN_N")
    try:
        value = float(text.replace("%", ""))
    except ValueError:
        return "", text, "UNPARSED"
    if "%" in text or value > 1:
        return f"{value / 100:.12g}", text, "PERCENT_0_100"
    return f"{value:.12g}", text, "PROBABILITY_0_1"


def normalize_hunt_name(raw: str) -> str:
    text = clean(raw)
    text = re.sub(r"\s+-\s+Any Legal Weapon\s*$", "", text, flags=re.I)
    text = re.sub(r"^(Premium\s+)?Cwmu\s+", "", text, flags=re.I)
    text = re.sub(
        r"^(Buck Deer|Any Bull Elk|Bull Moose|Buck Pronghorn|Antlerless Deer|Antlerless Elk|Doe Pronghorn)\s+-\s+",
        "",
        text,
        flags=re.I,
    )
    return text.strip()


def score_scope_and_residency(value: Any) -> tuple[str, str]:
    text = upper(value).replace("-", "").replace(" ", "")
    if text in {"RESIDENT", "RES"}:
        return "RESIDENT", "Resident"
    if text in {"NONRESIDENT", "NONRES", "NR"}:
        return "NONRESIDENT", "Nonresident"
    return "TOTAL", ""


def normalize_points(value: Any) -> str:
    text = clean(value)
    if not text:
        return ""
    if text.upper() == "TOTAL":
        return "TOTAL"
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def official_key(row: dict[str, Any]) -> str:
    scope, residency = score_scope_and_residency(row.get("score_scope") or row.get("residency"))
    if clean(row.get("score_scope")) in {"RESIDENT", "NONRESIDENT", "TOTAL"}:
        scope = clean(row.get("score_scope"))
        residency = {"RESIDENT": "Resident", "NONRESIDENT": "Nonresident", "TOTAL": ""}[scope]
    return "|".join(
        [
            clean(row.get("target_year") or row.get("permit_year")),
            clean(row.get("source_family") or row.get("draw_family")),
            clean(row.get("draw_system_type") or row.get("draw_design")),
            clean(row.get("draw_pool_key") or row.get("draw_pool")),
            upper(row.get("hunt_code")),
            scope,
            residency,
            normalize_points(row.get("points") or row.get("point_level")),
            "p_draw",
        ]
    )


def contract_signature(row: dict[str, Any]) -> tuple[str, ...]:
    fields = [
        "permit_year",
        "target_year",
        "model_year",
        "source_family",
        "draw_system_type",
        "draw_pool",
        "draw_pool_key",
        "hunt_code",
        "score_scope",
        "residency",
        "points",
        "point_level",
        "probability_metric",
        "actual_probability",
        "p_draw",
        "applicants",
        "permits",
        "successful",
        "unsuccessful",
    ]
    return tuple(clean(row.get(field)) for field in fields)


def duplicate_resolution(rows: list[dict[str, Any]]) -> str:
    signatures = {contract_signature(row) for row in rows}
    probabilities = {clean(row.get("actual_probability") or row.get("p_draw")) for row in rows}
    critical_fields = ["hunt_code", "score_scope", "residency", "points", "point_level"]
    critical = {tuple(clean(row.get(field)) for field in critical_fields) for row in rows}
    if len(signatures) == 1:
        return "DUPLICATE_IDENTICAL_COLLAPSED"
    if len(probabilities) == 1 and len(critical) == 1:
        return "DUPLICATE_LINEAGE_ONLY_COLLAPSED"
    return "CONFLICT_REVIEW_REQUIRED"


def prediction_probability(row: dict[str, str]) -> tuple[float | None, str]:
    for column in ("p_draw", "p_draw_mean", "p_preference_draw", "p_bonus_pool", "p_random_pool", "p_sportsman_draw"):
        value = clean(row.get(column))
        if value:
            try:
                return float(value), column
            except ValueError:
                continue
    return None, ""


def point_bucket(value: Any) -> str:
    text = normalize_points(value)
    if not text:
        return "blank"
    if text == "TOTAL":
        return "TOTAL"
    try:
        number = int(float(text))
    except ValueError:
        return "other"
    if number == 0:
        return "0"
    if number <= 5:
        return "1-5"
    if number <= 10:
        return "6-10"
    if number <= 15:
        return "11-15"
    return "16+"


def build() -> dict[str, Path | str]:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO / "audits" / f"2018_prediction_repair{timestamp}"
    raw_copy_dir = out_dir / "raw_sources" / "pipeline_cwmu"
    raw_copy_dir.mkdir(parents=True, exist_ok=False)

    pipeline_files = [
        path for path in PIPELINE_CWMU_ROOT.rglob("*") if path.is_file() and "2018" in path.name and "CWMU" in str(path).upper()
    ]
    datatruth_files = [path for path in DATATRUTH_CWMU_ROOT.rglob("*") if path.is_file()] if DATATRUTH_CWMU_ROOT.exists() else []
    inventory_fields = [
        "path",
        "file_name",
        "file_type",
        "size_bytes",
        "modified_time",
        "inferred_role",
        "inferred_cwmu_family",
        "inferred_species_group",
        "is_big_game",
        "is_antlerless",
        "is_youth_antlerless",
        "has_hunt_code",
        "page_count_if_pdf",
        "row_count_if_csv",
        "columns_if_csv",
        "sha256",
        "notes",
    ]
    pipeline_inventory = inventory_files(pipeline_files, "pipeline_2018_cwmu_candidate")
    datatruth_inventory = inventory_files(datatruth_files, "datatruth_2018_cwmu_candidate")
    write_csv(out_dir / "2018_PIPELINE_CWMU_SOURCE_INVENTORY.csv", pipeline_inventory, inventory_fields)
    write_csv(out_dir / "2018_DATATRUTH_CWMU_SOURCE_INVENTORY.csv", datatruth_inventory, inventory_fields)

    selected_files = sorted([path for path in pipeline_files if selected_pipeline_file(path)], key=lambda item: rel(item).lower())
    copy_manifest = []
    for path in selected_files:
        copied = raw_copy_dir / path.name
        shutil.copy2(path, copied)
        original_hash = sha256_file(path)
        copied_hash = sha256_file(copied)
        copy_manifest.append(
            {
                "original_path": rel(path),
                "copied_path": rel(copied),
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256_original": original_hash,
                "sha256_copied": copied_hash,
                "hash_match": str(original_hash == copied_hash).lower(),
                "selected_for_extraction": "true",
                "notes": "Copied from pipeline leaf CWMU source; raw source not modified.",
            }
        )
    write_csv(
        out_dir / "2018_CWMU_RAW_SOURCE_COPY_MANIFEST.csv",
        copy_manifest,
        [
            "original_path",
            "copied_path",
            "file_name",
            "size_bytes",
            "sha256_original",
            "sha256_copied",
            "hash_match",
            "selected_for_extraction",
            "notes",
        ],
    )

    hunt_re = re.compile(r"Hunt:\s+([A-Z]{2}\d{4})\s+(.+?)(?:\s+Page\s+\d+|$)", re.I)
    page_re = re.compile(r"\bPage\s+(\d+)\b", re.I)
    staging: list[dict[str, Any]] = []
    extraction_errors: list[dict[str, Any]] = []
    for source_path in selected_files:
        copied = raw_copy_dir / source_path.name
        meta = classify_from_name(source_path.name)
        with pdfplumber.open(copied) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                hunt_match = hunt_re.search(text.replace("\n", " "))
                if not hunt_match:
                    extraction_errors.append({"source_file": rel(copied), "source_page": page_index, "notes": "NO_HUNT_HEADER_PARSED"})
                    continue
                hunt_code = hunt_match.group(1).upper()
                hunt_name = normalize_hunt_name(hunt_match.group(2))
                official_page = page_re.search(text).group(1) if page_re.search(text) else str(page_index)
                tables = page.extract_tables() or []
                if not tables:
                    extraction_errors.append(
                        {"source_file": rel(copied), "source_page": page_index, "hunt_code": hunt_code, "notes": "NO_TABLE_PARSED"}
                    )
                    continue
                table = max(tables, key=lambda rows: len(rows or []))
                for row_index, pdf_row in enumerate(table, start=1):
                    if not pdf_row or len(pdf_row) < 12:
                        continue
                    for scope, base in (("RESIDENT", 0), ("NONRESIDENT", 6)):
                        point = clean(pdf_row[base])
                        if not point:
                            continue
                        if point.lower().startswith("total"):
                            point = "TOTAL"
                        applicants = parse_int(pdf_row[base + 1])
                        bonus = parse_int(pdf_row[base + 2])
                        regular = parse_int(pdf_row[base + 3])
                        permits = parse_int(pdf_row[base + 4])
                        probability, raw_probability, unit = parse_probability(pdf_row[base + 5])
                        if probability == "":
                            continue
                        residency = "Resident" if scope == "RESIDENT" else "Nonresident"
                        successful = "" if permits is None else permits
                        unsuccessful = "" if applicants is None or permits is None else max(applicants - permits, 0)
                        staging.append(
                            {
                                "permit_year": "2018",
                                "model_year": "2019",
                                "target_year": "2018",
                                "source_family": meta["source_family"],
                                "source_file": rel(copied),
                                "source_page": official_page,
                                "source_row_id": f"{source_path.stem}::pdf_page={page_index}::table_row={row_index}::{scope}",
                                "hunt_code": hunt_code,
                                "hunt_name": hunt_name,
                                "species": meta["species"],
                                "sex": meta["sex"],
                                "sex_type": meta["sex"],
                                "weapon": meta["weapon"],
                                "hunt_class": meta["hunt_class"],
                                "hunt_type": "CWMU",
                                "draw_family": meta["draw_family"],
                                "draw_design": meta["draw_design"],
                                "draw_system_type": meta["draw_system_type"],
                                "draw_pool": meta["draw_pool"],
                                "draw_pool_key": meta["draw_pool"],
                                "residency": residency,
                                "score_scope": scope,
                                "point_level": point,
                                "points": point,
                                "applicants": "" if applicants is None else applicants,
                                "eligible_applicants": "" if applicants is None else applicants,
                                "permits": "" if permits is None else permits,
                                "successful": successful,
                                "successful_applicants": successful,
                                "unsuccessful": unsuccessful,
                                "unsuccessful_applicants": unsuccessful,
                                "bonus_permits": "" if bonus is None else bonus,
                                "regular_permits": "" if regular is None else regular,
                                "total_permits": "" if permits is None else permits,
                                "actual_probability": probability,
                                "p_draw": probability,
                                "actual_probability_raw": raw_probability,
                                "actual_probability_source_column": f"{scope.lower()}_success_ratio",
                                "probability_unit_detected": unit,
                                "probability_metric": "p_draw",
                                "extraction_method": "pdfplumber_table_extract_pipeline_cwmu",
                                "source_lineage": f"pipeline raw PDF copied from {rel(source_path)}; extracted from {rel(copied)} page {official_page}",
                            }
                        )
    staging_fields = [
        "permit_year",
        "model_year",
        "source_family",
        "source_file",
        "source_page",
        "source_row_id",
        "hunt_code",
        "hunt_name",
        "species",
        "sex",
        "weapon",
        "hunt_class",
        "residency",
        "point_level",
        "applicants",
        "permits",
        "successful",
        "unsuccessful",
        "actual_probability",
        "actual_probability_raw",
        "actual_probability_source_column",
        "probability_unit_detected",
        "extraction_method",
        "source_lineage",
        "target_year",
        "draw_family",
        "draw_design",
        "draw_system_type",
        "draw_pool",
        "draw_pool_key",
        "score_scope",
        "points",
        "eligible_applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
        "successful_applicants",
        "unsuccessful_applicants",
        "p_draw",
        "probability_metric",
        "sex_type",
        "hunt_type",
    ]
    write_csv(out_dir / "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE.csv", staging, staging_fields)
    write_csv(out_dir / "2018_CWMU_EXTRACTION_ERRORS.csv", extraction_errors)

    canonical_fields, canonical_rows = read_csv(CANONICAL_2018)

    def is_cwmu_like(row: dict[str, str]) -> bool:
        text = " ".join(
            clean(row.get(field))
            for field in ("source_file", "draw_source_file", "source_path", "source_pdf", "hunt_type", "hunt_class", "hunt_name", "draw_pool")
        ).lower()
        return "cwmu" in text or upper(row.get("draw_system_type")) == "BONUS_CWMU_BIG_GAME"

    def convert_probability(value: Any) -> tuple[str, str, str]:
        text = clean(value)
        if not text:
            return "", "", ""
        try:
            number = float(text.replace("%", ""))
        except ValueError:
            return "", text, "UNPARSED"
        if "%" in text or number > 1:
            return f"{number / 100:.12g}", text, "PERCENT_0_100"
        return f"{number:.12g}", text, "PROBABILITY_0_1"

    def canonical_base(row: dict[str, str]) -> dict[str, Any]:
        return {
            "permit_year": clean(row.get("actual_draw_year")) or "2018",
            "model_year": clean(row.get("model_target_year")) or "2019",
            "target_year": clean(row.get("actual_draw_year")) or "2018",
            "hunt_code": upper(row.get("hunt_code")),
            "hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "sex": clean(row.get("sex") or row.get("sex_type")),
            "sex_type": clean(row.get("sex_type") or row.get("sex")),
            "weapon": clean(row.get("weapon")),
            "hunt_class": clean(row.get("hunt_class") or row.get("hunt_draw_class")),
            "hunt_type": clean(row.get("hunt_type")),
            "draw_family": clean(row.get("source_family")),
            "source_family": clean(row.get("source_family")),
            "draw_design": clean(row.get("draw_design") or row.get("draw_system_type")),
            "draw_system_type": clean(row.get("draw_system_type")),
            "draw_pool": clean(row.get("draw_pool")),
            "draw_pool_key": clean(row.get("draw_pool")),
            "source_file": clean(row.get("source_file") or row.get("draw_source_file") or row.get("source_pdf")),
            "source_page": clean(row.get("official_page") or row.get("pdf_page")),
            "source_row_id": clean(row.get("source_row_id") or row.get("source_path")),
            "source_lineage": clean(row.get("source_path") or row.get("source_pdf") or row.get("draw_source_file")),
        }

    truth_long: list[dict[str, Any]] = []
    for row in canonical_rows:
        if is_cwmu_like(row) or not upper(row.get("hunt_code")):
            continue
        made = False
        for scope, residency, column in (
            ("RESIDENT", "Resident", "resident_p_draw"),
            ("NONRESIDENT", "Nonresident", "nonresident_p_draw"),
            ("TOTAL", "", "total_p_draw"),
        ):
            probability, raw_probability, unit = convert_probability(row.get(column))
            if not probability:
                continue
            output = canonical_base(row)
            output.update(
                {
                    "residency": residency,
                    "score_scope": scope,
                    "point_level": clean(row.get("points")),
                    "points": clean(row.get("points")),
                    "actual_probability": probability,
                    "p_draw": probability,
                    "actual_probability_raw": raw_probability,
                    "actual_probability_source_column": column,
                    "probability_unit_detected": unit,
                    "probability_metric": "p_draw",
                    "component": "canonical_non_cwmu_wide_or_long",
                }
            )
            truth_long.append(output)
            made = True
        if not made:
            probability, raw_probability, unit = convert_probability(row.get("p_draw"))
            if not probability:
                continue
            scope, residency = score_scope_and_residency(row.get("residency"))
            output = canonical_base(row)
            output.update(
                {
                    "residency": residency,
                    "score_scope": scope,
                    "point_level": clean(row.get("points")),
                    "points": clean(row.get("points")),
                    "actual_probability": probability,
                    "p_draw": probability,
                    "actual_probability_raw": raw_probability,
                    "actual_probability_source_column": "p_draw",
                    "probability_unit_detected": unit,
                    "probability_metric": "p_draw",
                    "component": "canonical_non_cwmu_long",
                }
            )
            truth_long.append(output)
    for row in staging:
        output = dict(row)
        output["component"] = "pipeline_cwmu_authoritative"
        truth_long.append(output)
    write_csv(out_dir / "2018_TRUTH_LONG_FROM_WIDE.csv", truth_long)

    keyed = []
    for row in truth_long:
        output = dict(row)
        output["official_score_key_v2"] = official_key(output)
        keyed.append(output)
    write_csv(out_dir / "2018_TRUTH_LONG_KEYED.csv", keyed)

    prediction_fields, prediction_rows = read_csv(PRED_PATH)
    prediction_key_counts = Counter(clean(row.get("official_score_key_v2")) for row in prediction_rows if clean(row.get("official_score_key_v2")))
    prediction_duplicate_keys = {key: value for key, value in prediction_key_counts.items() if value > 1}
    prediction_by_key = {
        clean(row.get("official_score_key_v2")): row
        for row in prediction_rows
        if clean(row.get("official_score_key_v2")) and prediction_key_counts[clean(row.get("official_score_key_v2"))] == 1
    }

    def duplicate_audit(role: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in rows:
            key = clean(row.get("official_score_key_v2"))
            if key:
                grouped[key].append(row)
        out = []
        for key, rows_for_key in sorted(grouped.items()):
            if len(rows_for_key) <= 1:
                continue
            first = rows_for_key[0]
            out.append(
                {
                    "file_role": role,
                    "official_score_key_v2": key,
                    "duplicate_count": len(rows_for_key),
                    "hunt_code": clean(first.get("hunt_code")),
                    "residency": clean(first.get("residency")),
                    "point_level": clean(first.get("point_level") or first.get("points")),
                    "draw_family": clean(first.get("source_family") or first.get("draw_family")),
                    "species": clean(first.get("species")),
                    "candidate_resolution": duplicate_resolution(rows_for_key),
                    "notes": "",
                }
            )
        return out

    duplicate_rows = []
    duplicate_rows.extend(duplicate_audit("CWMU pipeline staging", [dict(row, official_score_key_v2=official_key(row)) for row in staging]))
    duplicate_rows.extend(duplicate_audit("full 2018 truth long keyed", keyed))
    for key, count in sorted(prediction_duplicate_keys.items()):
        parts = key.split("|")
        duplicate_rows.append(
            {
                "file_role": "selected prediction file",
                "official_score_key_v2": key,
                "duplicate_count": count,
                "hunt_code": parts[4] if len(parts) > 4 else "",
                "residency": parts[6] if len(parts) > 6 else "",
                "point_level": parts[7] if len(parts) > 7 else "",
                "draw_family": parts[1] if len(parts) > 1 else "",
                "species": "",
                "candidate_resolution": "PREDICTION_DUPLICATE_REVIEW_REQUIRED",
                "notes": "",
            }
        )
    write_csv(
        out_dir / "2018_DUPLICATE_KEY_AUDIT.csv",
        duplicate_rows,
        [
            "file_role",
            "official_score_key_v2",
            "duplicate_count",
            "hunt_code",
            "residency",
            "point_level",
            "draw_family",
            "species",
            "candidate_resolution",
            "notes",
        ],
    )

    grouped_keyed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in keyed:
        grouped_keyed[clean(row.get("official_score_key_v2"))].append(row)
    deduped: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    excluded_conflicts: list[dict[str, Any]] = []
    for key, rows_for_key in sorted(grouped_keyed.items()):
        if not key:
            decisions.append({"official_score_key_v2": key, "input_rows": len(rows_for_key), "output_rows": 0, "decision": "EXCLUDED_BLANK_SCORE_KEY", "notes": ""})
            excluded_conflicts.extend(dict(row, score_exclusion_reason="EXCLUDED_BLANK_SCORE_KEY") for row in rows_for_key)
            continue
        if len(rows_for_key) == 1:
            row = dict(rows_for_key[0])
            row["dedupe_decision"] = "UNIQUE"
            row["score_exclusion_reason"] = ""
            deduped.append(row)
            decisions.append({"official_score_key_v2": key, "input_rows": 1, "output_rows": 1, "decision": "UNIQUE", "notes": ""})
            continue
        resolution = duplicate_resolution(rows_for_key)
        if resolution in {"DUPLICATE_IDENTICAL_COLLAPSED", "DUPLICATE_LINEAGE_ONLY_COLLAPSED"}:
            row = dict(rows_for_key[0])
            row["dedupe_decision"] = resolution
            row["source_lineage"] = " | ".join(dict.fromkeys(clean(item.get("source_lineage")) for item in rows_for_key if clean(item.get("source_lineage"))))
            row["score_exclusion_reason"] = ""
            deduped.append(row)
            decisions.append({"official_score_key_v2": key, "input_rows": len(rows_for_key), "output_rows": 1, "decision": resolution, "notes": "Safe duplicate collapse."})
        else:
            excluded_conflicts.extend(dict(row, score_exclusion_reason="CONFLICT_REVIEW_REQUIRED") for row in rows_for_key)
            decisions.append(
                {
                    "official_score_key_v2": key,
                    "input_rows": len(rows_for_key),
                    "output_rows": 0,
                    "decision": "CONFLICT_REVIEW_REQUIRED",
                    "notes": "Conflicting actual_probability or critical row fields; excluded from scoring.",
                }
            )
    write_csv(out_dir / "2018_TRUTH_DEDUPE_DECISIONS.csv", decisions, ["official_score_key_v2", "input_rows", "output_rows", "decision", "notes"])
    write_csv(out_dir / "2018_TRUTH_LONG_KEYED_DEDUPED.csv", deduped)
    write_csv(out_dir / "2018_TRUTH_DUPLICATE_CONFLICTS_EXCLUDED.csv", excluded_conflicts)

    blank_prediction_keys = sum(1 for row in prediction_rows if not clean(row.get("official_score_key_v2")))
    write_text(
        out_dir / "2019_MODEL_PREDICTION_SELECTION.md",
        "\n".join(
            [
                "# 2019 Model Prediction Selection",
                "",
                f"Selected prediction path: `{rel(PRED_PATH)}`",
                "",
                "Why selected: this is the frozen 2017-to-2018 full-engine equivalent prediction output named in the mission. It contains the frozen 2018 target prediction surface and `official_score_key_v2` key vocabulary.",
                "",
                f"Row count: `{len(prediction_rows)}`",
                f"Columns: `{len(prediction_fields)}`",
                f"`official_score_key_v2` present: `{'official_score_key_v2' in prediction_fields}`",
                f"Blank score keys: `{blank_prediction_keys}`",
                f"Duplicate score keys: `{len(prediction_duplicate_keys)}`",
            ]
        ),
    )

    score_rows: list[dict[str, Any]] = []
    unmatched_truth: list[dict[str, Any]] = []
    matched_keys: set[str] = set()
    for truth in deduped:
        key = clean(truth.get("official_score_key_v2"))
        prediction = prediction_by_key.get(key)
        if not prediction:
            unmatched_truth.append(dict(truth, bridge_status="UNMATCHED_TRUTH", score_status="UNSCORED", exclusion_reason="NO_PREDICTION_KEY_MATCH"))
            continue
        predicted_probability, predicted_column = prediction_probability(prediction)
        try:
            actual_probability = float(clean(truth.get("actual_probability") or truth.get("p_draw")))
        except ValueError:
            actual_probability = None
        if predicted_probability is None or actual_probability is None:
            absolute_error = squared_error = bias = ""
            score_status = "UNSCORED"
            exclusion_reason = "MISSING_NUMERIC_PROBABILITY"
        else:
            bias_value = predicted_probability - actual_probability
            absolute_error = f"{abs(bias_value):.12g}"
            squared_error = f"{bias_value * bias_value:.12g}"
            bias = f"{bias_value:.12g}"
            score_status = "SCORED"
            exclusion_reason = ""
        score_rows.append(
            {
                "score_type": "BRIDGED_CONTRACT_SCORE",
                "permit_year": clean(truth.get("permit_year")),
                "model_year": clean(truth.get("model_year")),
                "official_score_key_v2": key,
                "hunt_code": clean(truth.get("hunt_code")),
                "residency": clean(truth.get("residency")),
                "point_level": clean(truth.get("point_level") or truth.get("points")),
                "draw_family": clean(truth.get("source_family") or truth.get("draw_family")),
                "species": clean(truth.get("species")),
                "sex": clean(truth.get("sex") or truth.get("sex_type")),
                "weapon": clean(truth.get("weapon")),
                "hunt_class": clean(truth.get("hunt_class")),
                "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.12g}",
                "actual_probability": "" if actual_probability is None else f"{actual_probability:.12g}",
                "absolute_error": absolute_error,
                "squared_error": squared_error,
                "bias": bias,
                "prediction_source_path": rel(PRED_PATH),
                "truth_source_path": rel(out_dir / "2018_TRUTH_LONG_KEYED_DEDUPED.csv"),
                "source_file": clean(truth.get("source_file")),
                "source_page": clean(truth.get("source_page")),
                "bridge_status": "MATCHED_ON_OFFICIAL_SCORE_KEY_V2",
                "score_status": score_status,
                "exclusion_reason": exclusion_reason,
                "prediction_probability_column": predicted_column,
            }
        )
        matched_keys.add(key)
    unmatched_predictions = [
        dict(row, bridge_status="UNMATCHED_PREDICTION", score_status="UNSCORED", exclusion_reason="NO_TRUTH_KEY_MATCH")
        for key, row in prediction_by_key.items()
        if key not in matched_keys
    ]
    score_fields = [
        "score_type",
        "permit_year",
        "model_year",
        "official_score_key_v2",
        "hunt_code",
        "residency",
        "point_level",
        "draw_family",
        "species",
        "sex",
        "weapon",
        "hunt_class",
        "predicted_probability",
        "actual_probability",
        "absolute_error",
        "squared_error",
        "bias",
        "prediction_source_path",
        "truth_source_path",
        "source_file",
        "source_page",
        "bridge_status",
        "score_status",
        "exclusion_reason",
        "prediction_probability_column",
    ]
    write_csv(out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE.csv", score_rows, score_fields)
    write_csv(out_dir / "2018_SCORE_UNMATCHED_PREDICTIONS.csv", unmatched_predictions)
    write_csv(out_dir / "2018_SCORE_UNMATCHED_TRUTH.csv", unmatched_truth)

    def summarize(label: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
        scored = [row for row in rows if row.get("score_status") == "SCORED"]
        absolute_errors = [float(row["absolute_error"]) for row in scored if clean(row.get("absolute_error"))]
        squared_errors = [float(row["squared_error"]) for row in scored if clean(row.get("squared_error"))]
        biases = [float(row["bias"]) for row in scored if clean(row.get("bias"))]
        return {
            "summary_group": label,
            "scorable_rows": len(scored),
            "unscorable_rows": len(rows) - len(scored),
            "prediction_rows": len(prediction_rows),
            "truth_rows": len(deduped),
            "matched_rows": len(rows),
            "unmatched_prediction_rows": len(unmatched_predictions),
            "unmatched_truth_rows": len(unmatched_truth),
            "MAE": "" if not absolute_errors else f"{sum(absolute_errors) / len(absolute_errors):.12g}",
            "RMSE": "" if not squared_errors else f"{math.sqrt(sum(squared_errors) / len(squared_errors)):.12g}",
            "Bias": "" if not biases else f"{sum(biases) / len(biases):.12g}",
            "Min_Error": "" if not biases else f"{min(biases):.12g}",
            "Max_Error": "" if not biases else f"{max(biases):.12g}",
            "unique_hunt_codes_scored": len({row["hunt_code"] for row in scored}),
            "unique_hunt_codes_unscored": len({row.get("hunt_code", "") for row in unmatched_truth}),
        }

    summary_rows = [summarize("overall", score_rows)]
    for field in ("draw_family", "species", "residency", "hunt_class"):
        for value in sorted({clean(row.get(field)) or "blank" for row in score_rows}):
            summary_rows.append(summarize(f"{field}:{value}", [row for row in score_rows if (clean(row.get(field)) or "blank") == value]))
    for value in sorted({point_bucket(row.get("point_level")) for row in score_rows}):
        summary_rows.append(summarize(f"point_level_bucket:{value}", [row for row in score_rows if point_bucket(row.get("point_level")) == value]))
    write_csv(
        out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv",
        summary_rows,
        [
            "summary_group",
            "scorable_rows",
            "unscorable_rows",
            "prediction_rows",
            "truth_rows",
            "matched_rows",
            "unmatched_prediction_rows",
            "unmatched_truth_rows",
            "MAE",
            "RMSE",
            "Bias",
            "Min_Error",
            "Max_Error",
            "unique_hunt_codes_scored",
            "unique_hunt_codes_unscored",
        ],
    )

    cwmu_truth = [row for row in deduped if clean(row.get("component")) == "pipeline_cwmu_authoritative"]
    score_by_key = {row["official_score_key_v2"]: row for row in score_rows}
    by_hunt_point: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in cwmu_truth:
        by_hunt_point[(upper(row.get("hunt_code")), normalize_points(row.get("points") or row.get("point_level")))].append(row)
    cwmu_audit = []
    for row in cwmu_truth:
        group = by_hunt_point[(upper(row.get("hunt_code")), normalize_points(row.get("points") or row.get("point_level")))]
        scopes = {clean(item.get("score_scope")) for item in group}
        key = clean(row.get("official_score_key_v2"))
        score_status = "SCORED" if key in score_by_key and score_by_key[key].get("score_status") == "SCORED" else "TRUTH_ONLY_UNSCORED"
        cwmu_audit.append(
            {
                "hunt_code": clean(row.get("hunt_code")),
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex": clean(row.get("sex")),
                "residency": clean(row.get("residency")),
                "point_level": clean(row.get("points") or row.get("point_level")),
                "actual_probability": clean(row.get("actual_probability")),
                "has_resident_row": str("RESIDENT" in scopes).lower(),
                "has_nonresident_row": str("NONRESIDENT" in scopes).lower(),
                "has_total_row": str("TOTAL" in scopes).lower(),
                "total_matches_r_plus_nr_if_applicable": "NOT_EVALUATED_NO_TOTAL_ROWS" if "TOTAL" not in scopes else "REVIEW_REQUIRED",
                "source_file": clean(row.get("source_file")),
                "source_page": clean(row.get("source_page")),
                "score_status": score_status,
                "notes": "" if score_status == "SCORED" else "No exact frozen prediction official_score_key_v2 match.",
            }
        )
    write_csv(
        out_dir / "2018_CWMU_TRUTH_AUDIT.csv",
        cwmu_audit,
        [
            "hunt_code",
            "hunt_name",
            "species",
            "sex",
            "residency",
            "point_level",
            "actual_probability",
            "has_resident_row",
            "has_nonresident_row",
            "has_total_row",
            "total_matches_r_plus_nr_if_applicable",
            "source_file",
            "source_page",
            "score_status",
            "notes",
        ],
    )

    component_rows = []
    for component, rows, source_path in (
        ("canonical_non_cwmu", [row for row in truth_long if clean(row.get("component")).startswith("canonical_non_cwmu")], CANONICAL_2018),
        ("pipeline_cwmu_authoritative", cwmu_truth, out_dir / "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE.csv"),
    ):
        counts = Counter(clean(row.get("official_score_key_v2")) for row in rows if clean(row.get("official_score_key_v2")))
        component_rows.append(
            {
                "component": component,
                "source_path": rel(source_path),
                "input_rows": len(rows),
                "output_rows": len(rows),
                "unique_hunt_codes": len({upper(row.get("hunt_code")) for row in rows if upper(row.get("hunt_code"))}),
                "duplicate_key_count": sum(1 for value in counts.values() if value > 1),
                "selected_as_authoritative": str(component == "pipeline_cwmu_authoritative").lower(),
                "notes": "Pipeline CWMU rows override stale/generated CWMU components."
                if component == "pipeline_cwmu_authoritative"
                else "Non-CWMU retained from existing canonical yearly truth.",
            }
        )
    write_csv(
        out_dir / "2018_TRUTH_COMPONENT_MERGE_AUDIT.csv",
        component_rows,
        ["component", "source_path", "input_rows", "output_rows", "unique_hunt_codes", "duplicate_key_count", "selected_as_authoritative", "notes"],
    )

    pipeline_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    datatruth_by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in pipeline_inventory:
        pipeline_by_name[row["file_name"]].append(row)
    for row in datatruth_inventory:
        datatruth_by_name[row["file_name"]].append(row)
    matching_names = sorted(set(pipeline_by_name) & set(datatruth_by_name))
    hash_matches = sum(
        1
        for name in matching_names
        if any(pipeline_row["sha256"] == datatruth_row["sha256"] for pipeline_row in pipeline_by_name[name] for datatruth_row in datatruth_by_name[name])
    )
    write_text(
        out_dir / "2018_CWMU_PIPELINE_VS_DATATRUTH_SOURCE_COMPARISON.md",
        "# 2018 CWMU Pipeline vs Data Truth Source Comparison\n\n"
        f"Pipeline CWMU files inspected: `{len(pipeline_inventory)}`\n"
        f"Data truth CWMU files inspected: `{len(datatruth_inventory)}`\n"
        f"Matching filenames: `{len(matching_names)}`\n"
        f"Matching filename/hash pairs: `{hash_matches}`\n"
        f"Selected pipeline leaf PDFs copied for extraction: `{len(selected_files)}`\n\n"
        "## Primary Source Decision\n\n"
        "Use the pipeline leaf CWMU PDFs under `pipeline/RAW/hunt_unit_database/2018/pdf/draw_odds/CWMU` as the primary raw working source. "
        "They include separate Big Game, adult Antlerless, and Youth Antlerless subfiles and were copied into this audit package before extraction.\n\n"
        "## Selected Files\n\n"
        + "\n".join(f"- `{rel(path)}`" for path in selected_files)
        + "\n\n## Data Truth Note\n\nData-truth CWMU files were inventoried for comparison only. The repair path uses pipeline-derived CWMU staging as authoritative for CWMU rows.\n",
    )
    write_text(
        out_dir / "2018_OFFICIAL_SCORE_KEY_RECIPE.md",
        "# 2018 Official Score Key Recipe\n\n"
        f"Canonical contract inspected: `{rel(KEY_BUILDER)}` and `engine/utah_draw_predictive/run_all_families.py::_official_score_key_v2`.\n\n"
        "The bridged truth rows build `official_score_key_v2` using the same nine-field pipe-delimited contract emitted by frozen predictions:\n\n"
        "`target_year|source_family|draw_system_type|draw_pool_key_or_draw_pool|hunt_code|score_scope|residency|points|probability_metric`\n\n"
        "For this bridge, `target_year` is the frozen prediction target year `2018` / permit year `2018`; `model_year` remains `2019` as metadata. "
        "CWMU pipeline rows use `BONUS_CWMU_BIG_GAME` as draw system. Adult CWMU Big Game and adult CWMU Antlerless rows are keyed as `CWMU_BIG_GAME`; "
        "youth antlerless CWMU rows are keyed as `YOUTH_ANTLERLESS`, matching the frozen prediction surface.\n\nNo fuzzy joins are used for primary scoring.\n",
    )

    source_names = " ".join(path.name.upper() for path in selected_files)
    has_big = "BIG_GAME" in source_names
    has_antlerless = any("ANTLERLESS" in path.name.upper() and "YOUTH" not in path.name.upper() for path in selected_files)
    has_youth = any("YOUTH_ANTLERLESS" in path.name.upper() for path in selected_files)
    hunt_code_scopes: dict[str, set[str]] = defaultdict(set)
    for row in cwmu_truth:
        hunt_code_scopes[upper(row.get("hunt_code"))].add(clean(row.get("score_scope")))
    rn_no_total = sorted(hunt for hunt, scopes in hunt_code_scopes.items() if {"RESIDENT", "NONRESIDENT"} <= scopes and "TOTAL" not in scopes)
    total_no_rn = sorted(hunt for hunt, scopes in hunt_code_scopes.items() if "TOTAL" in scopes and not ({"RESIDENT", "NONRESIDENT"} & scopes))

    if score_rows and not excluded_conflicts and not unmatched_truth:
        status = "PASS_BRIDGED_CONTRACT"
    elif score_rows:
        status = "PASS_WITH_REVIEW_REQUIRED"
    else:
        status = "FAIL_BLOCKED"
    write_text(
        out_dir / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md",
        "# 2018 Prediction Engine Repair Certification\n\n"
        "## Executive Summary\n\n"
        "Pipeline CWMU files were inspected first and used as the authoritative 2018 CWMU repair source. Raw pipeline leaf PDFs were copied into "
        "`raw_sources/pipeline_cwmu` and parsed with `pdfplumber` into long contract rows. Scoring completed against the frozen 2017-to-2018 "
        "prediction surface using exact `official_score_key_v2` joins.\n\n"
        f"Final status: `{status}`\n\n"
        "## Selected Raw CWMU Files\n\n"
        + "\n".join(f"- `{rel(path)}`" for path in selected_files)
        + "\n\n## Pipeline / Data Truth Comparison\n\n"
        f"Pipeline inventory rows: `{len(pipeline_inventory)}`\n"
        f"Data-truth inventory rows: `{len(datatruth_inventory)}`\n"
        f"Matching filenames: `{len(matching_names)}`\n"
        f"Matching hashes among matching filenames: `{hash_matches}`\n\n"
        "## Wide-To-Long / PDF Extraction Results\n\n"
        f"CWMU staging rows from pipeline: `{len(staging)}`\n"
        f"CWMU unique hunt codes staged: `{len({row['hunt_code'] for row in staging})}`\n"
        f"Full truth long rows after merge: `{len(truth_long)}`\n"
        f"Deduped truth rows: `{len(deduped)}`\n"
        f"Excluded conflict rows: `{len(excluded_conflicts)}`\n\n"
        "## Score-Key Recipe\n\n"
        "`target_year|source_family|draw_system_type|draw_pool_key_or_draw_pool|hunt_code|score_scope|residency|points|probability_metric`\n\n"
        "## Duplicate-Key Audit Result\n\n"
        f"Duplicate audit groups written: `{len(duplicate_rows)}`\n"
        f"Dedupe decision rows: `{len(decisions)}`\n"
        f"Conflict rows excluded from scoring: `{len(excluded_conflicts)}`\n\n"
        "## Selected Prediction File\n\n"
        f"`{rel(PRED_PATH)}`\n\n"
        f"Prediction rows: `{len(prediction_rows)}`\n"
        f"Blank prediction keys: `{blank_prediction_keys}`\n"
        f"Duplicate prediction keys: `{len(prediction_duplicate_keys)}`\n\n"
        "## Scoring Results\n\n"
        f"Matched score rows: `{len(score_rows)}`\n"
        f"Unmatched truth rows: `{len(unmatched_truth)}`\n"
        f"Unmatched prediction rows: `{len(unmatched_predictions)}`\n"
        f"Overall summary file: `{rel(out_dir / '2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv')}`\n\n"
        "## CWMU Findings\n\n"
        f"Pipeline CWMU Big Game rows provided: `{has_big}`\n"
        f"Pipeline CWMU Antlerless rows provided: `{has_antlerless}`\n"
        f"Pipeline CWMU Youth Antlerless rows provided: `{has_youth}`\n"
        f"CWMU truth rows staged: `{len(cwmu_truth)}`\n"
        f"CWMU rows scored: `{sum(1 for row in cwmu_audit if row['score_status'] == 'SCORED')}`\n"
        f"CWMU rows truth-only/unscored: `{sum(1 for row in cwmu_audit if row['score_status'] != 'SCORED')}`\n"
        f"CWMU hunt codes with R and NR but no TOTAL: `{len(rn_no_total)}`\n"
        f"CWMU hunt codes with TOTAL but no R/NR: `{len(total_no_rn)}`\n\n"
        "## Excluded Rows And Reasons\n\n"
        f"Rows excluded due to duplicate/conflict: `{len(excluded_conflicts)}`\n"
        f"Rows unmatched to frozen prediction keys: `{len(unmatched_truth)}`\n"
        "No fuzzy joins were used.\n\n"
        "## Remaining Blockers\n\n"
        "2018 does not get `PASS_BRIDGED_CONTRACT` unless unmatched truth/review rows are resolved or explicitly accepted. Current scoring completed, but review rows remain.\n\n"
        "## Final Status\n\n"
        f"{status}\n",
    )

    terminal = {
        "2018_REPAIR_OUTPUT_DIR": out_dir,
        "2018_PIPELINE_CWMU_SOURCE_INVENTORY": out_dir / "2018_PIPELINE_CWMU_SOURCE_INVENTORY.csv",
        "2018_CWMU_RAW_SOURCE_COPY_MANIFEST": out_dir / "2018_CWMU_RAW_SOURCE_COPY_MANIFEST.csv",
        "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE": out_dir / "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE.csv",
        "2018_TRUTH_LONG_KEYED_DEDUPED": out_dir / "2018_TRUTH_LONG_KEYED_DEDUPED.csv",
        "2018_BRIDGED_CONTRACT_SCORE": out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE.csv",
        "2018_SCORE_SUMMARY": out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv",
        "2018_CWMU_TRUTH_AUDIT": out_dir / "2018_CWMU_TRUTH_AUDIT.csv",
        "2018_CERTIFICATION_REPORT": out_dir / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md",
        "2018_STATUS": status,
    }
    write_text(out_dir / "FINAL_TERMINAL_OUTPUT.txt", "\n".join(f"{key}={value}" for key, value in terminal.items()))
    return terminal


def main() -> int:
    terminal = build()
    print("\n".join(f"{key}={value}" for key, value in terminal.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
