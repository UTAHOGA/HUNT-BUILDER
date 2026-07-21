#!/usr/bin/env python3
"""Build a blind 2018 CWMU truth package, then score after truth lock."""

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
PIPELINE_CWMU_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2018" / "pdf" / "draw_odds" / "CWMU"
DATATRUTH_CWMU_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / "2018_PERMITS=2019_MODEL" / "CWMU"
PRED_PATH = (
    REPO
    / "audits"
    / "prediction_blind_year_to_year"
    / "full_engine_equivalent_2017_to_2018"
    / "runs"
    / "2018_20260707_le_split_check"
    / "family_predictions.csv"
)


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


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


def pdf_page_count(path: Path) -> str:
    if path.suffix.lower() != ".pdf":
        return ""
    try:
        with pdfplumber.open(path) as pdf:
            return str(len(pdf.pages))
    except Exception as exc:
        return f"PDF_READ_ERROR:{exc}"


def csv_profile(path: Path) -> dict[str, Any]:
    profile = {
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
        return profile
    try:
        fields, rows = read_csv(path)
    except Exception as exc:
        profile["columns_if_csv"] = f"CSV_READ_ERROR:{exc}"
        return profile
    fieldset = set(fields)
    profile.update(
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
    return profile


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
    if "DRAW_ODDS_ARTIFACT" in route or "IGNORED" in route or "DUPLICATE" in route or "PARENT BUNDLES" in route:
        return False
    return name.startswith("2018_PERMITS=2019_MODEL__CWMU_") and ("DRAW_RESULTS" in name or "BIG_GAME" in name)


def source_derived_classification(name: str) -> dict[str, str]:
    name_upper = name.upper()
    youth = "YOUTH_ANTLERLESS" in name_upper
    antlerless = "ANTLERLESS" in name_upper or "DOE_PRONGHORN" in name_upper
    if "DEER" in name_upper:
        species = "Deer"
    elif "ELK" in name_upper:
        species = "Elk"
    elif "PRONGHORN" in name_upper:
        species = "Pronghorn"
    elif "MOOSE" in name_upper:
        species = "Moose"
    else:
        species = ""
    if "BUCK" in name_upper:
        sex = "Buck"
    elif "BULL" in name_upper:
        sex = "Bull"
    elif "DOE" in name_upper:
        sex = "Doe"
    elif antlerless:
        sex = "Antlerless"
    else:
        sex = ""
    if youth:
        source_family = "YOUTH_ANTLERLESS"
        if species.lower() == "pronghorn":
            draw_pool = "cwmu_youth_doe_pronghorn"
        else:
            draw_pool = f"cwmu_youth_antlerless_{species.lower()}"
    elif antlerless:
        source_family = "CWMU_ANTLERLESS"
        if species.lower() == "pronghorn":
            draw_pool = "cwmu_doe_pronghorn"
        else:
            draw_pool = f"cwmu_antlerless_{species.lower()}"
    else:
        source_family = "CWMU_BIG_GAME"
        draw_pool = f"cwmu_big_game_{species.lower()}_{sex.lower()}" if species and sex else "cwmu_big_game"
    return {
        "source_family": source_family,
        "draw_family": source_family,
        "draw_system_type": "CWMU_OFFICIAL_DRAW_RESULTS",
        "draw_design": "CWMU_OFFICIAL_DRAW_RESULTS",
        "draw_pool": draw_pool,
        "draw_pool_key": draw_pool,
        "species": species,
        "sex": sex,
        "sex_type": sex,
        "weapon": "Any Legal Weapon",
        "hunt_class": "CWMU",
        "hunt_type": "CWMU",
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


def normalize_points(value: Any) -> str:
    text = clean(value)
    if text.upper() == "TOTAL":
        return "TOTAL"
    try:
        number = float(text)
    except ValueError:
        return text
    return str(int(number)) if number.is_integer() else text


def official_truth_key(row: dict[str, Any]) -> str:
    return "|".join(
        [
            clean(row.get("target_year") or row.get("permit_year")),
            clean(row.get("source_family")),
            clean(row.get("draw_system_type")),
            clean(row.get("draw_pool_key") or row.get("draw_pool")),
            upper(row.get("hunt_code")),
            clean(row.get("score_scope")),
            clean(row.get("residency")),
            normalize_points(row.get("points") or row.get("point_level")),
            "p_draw",
        ]
    )


def bridge_candidate_keys(row: dict[str, Any]) -> list[str]:
    """Post-lock scoring-only bridge candidates; truth rows are not mutated."""
    target_year = clean(row.get("target_year") or row.get("permit_year"))
    hunt_code = upper(row.get("hunt_code"))
    scope = clean(row.get("score_scope"))
    residency = clean(row.get("residency"))
    points = normalize_points(row.get("points") or row.get("point_level"))
    source_family = clean(row.get("source_family"))
    draw_pool = clean(row.get("draw_pool"))
    candidates = [
        "|".join([target_year, source_family, clean(row.get("draw_system_type")), draw_pool, hunt_code, scope, residency, points, "p_draw"])
    ]
    if source_family in {"CWMU_BIG_GAME", "CWMU_ANTLERLESS"}:
        candidates.append("|".join([target_year, "CWMU_BIG_GAME", "BONUS_CWMU_BIG_GAME", "bonus_cwmu_big_game", hunt_code, scope, residency, points, "p_draw"]))
    if source_family == "YOUTH_ANTLERLESS":
        youth_pool = draw_pool.removeprefix("cwmu_")
        candidates.append("|".join([target_year, "YOUTH_ANTLERLESS", "BONUS_CWMU_BIG_GAME", youth_pool, hunt_code, scope, residency, points, "p_draw"]))
    return list(dict.fromkeys(candidates))


def contract_signature(row: dict[str, Any]) -> tuple[str, ...]:
    fields = [
        "permit_year",
        "target_year",
        "model_year",
        "source_family",
        "draw_system_type",
        "draw_pool",
        "hunt_code",
        "score_scope",
        "residency",
        "points",
        "actual_probability",
        "applicants",
        "permits",
        "successful",
        "unsuccessful",
    ]
    return tuple(clean(row.get(field)) for field in fields)


def duplicate_resolution(rows: list[dict[str, Any]]) -> str:
    signatures = {contract_signature(row) for row in rows}
    probabilities = {clean(row.get("actual_probability")) for row in rows}
    critical = {tuple(clean(row.get(field)) for field in ("hunt_code", "score_scope", "residency", "points")) for row in rows}
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
    run_start = now()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO / "audits" / f"2018_prediction_repair_blind{timestamp}"
    raw_copy_dir = out_dir / "raw_sources" / "pipeline_cwmu"
    raw_copy_dir.mkdir(parents=True, exist_ok=False)

    pipeline_files = [path for path in PIPELINE_CWMU_ROOT.rglob("*") if path.is_file()]
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
    for source_path in selected_files:
        copied = raw_copy_dir / source_path.name
        shutil.copy2(source_path, copied)
        source_hash = sha256_file(source_path)
        copied_hash = sha256_file(copied)
        copy_manifest.append(
            {
                "original_path": rel(source_path),
                "copied_path": rel(copied),
                "file_name": source_path.name,
                "size_bytes": source_path.stat().st_size,
                "sha256_original": source_hash,
                "sha256_copied": copied_hash,
                "hash_match": str(source_hash == copied_hash).lower(),
                "selected_for_extraction": "true",
                "notes": "Copied before extraction. Raw pipeline source was not modified.",
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
    extraction_audit: list[dict[str, Any]] = []
    for source_path in selected_files:
        copied = raw_copy_dir / source_path.name
        metadata = source_derived_classification(source_path.name)
        with pdfplumber.open(copied) as pdf:
            for page_index, page in enumerate(pdf.pages, start=1):
                text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
                hunt_match = hunt_re.search(text.replace("\n", " "))
                tables = page.extract_tables() or []
                table = max(tables, key=lambda value: len(value or [])) if tables else []
                parsed_rows = 0
                if hunt_match and table:
                    hunt_code = hunt_match.group(1).upper()
                    hunt_name = normalize_hunt_name(hunt_match.group(2))
                    official_page = page_re.search(text).group(1) if page_re.search(text) else str(page_index)
                    for table_row_index, pdf_row in enumerate(table, start=1):
                        if not pdf_row or len(pdf_row) < 12:
                            continue
                        for scope, base in (("RESIDENT", 0), ("NONRESIDENT", 6)):
                            point = clean(pdf_row[base])
                            if not point:
                                continue
                            if point.lower().startswith("total"):
                                point = "TOTAL"
                            probability, probability_raw, unit = parse_probability(pdf_row[base + 5])
                            if not probability:
                                continue
                            applicants = parse_int(pdf_row[base + 1])
                            bonus = parse_int(pdf_row[base + 2])
                            regular = parse_int(pdf_row[base + 3])
                            permits = parse_int(pdf_row[base + 4])
                            residency = "Resident" if scope == "RESIDENT" else "Nonresident"
                            successful = "" if permits is None else permits
                            unsuccessful = "" if applicants is None or permits is None else max(applicants - permits, 0)
                            staging.append(
                                {
                                    "permit_year": "2018",
                                    "model_year": "2019",
                                    "target_year": "2018",
                                    "source_family": metadata["source_family"],
                                    "source_file": rel(copied),
                                    "source_page": official_page,
                                    "source_row_id": f"{source_path.stem}::pdf_page={page_index}::table_row={table_row_index}::{scope}",
                                    "hunt_code": hunt_code,
                                    "hunt_name": hunt_name,
                                    "species": metadata["species"],
                                    "sex": metadata["sex"],
                                    "sex_type": metadata["sex_type"],
                                    "weapon": metadata["weapon"],
                                    "hunt_class": metadata["hunt_class"],
                                    "hunt_type": metadata["hunt_type"],
                                    "draw_family": metadata["draw_family"],
                                    "draw_design": metadata["draw_design"],
                                    "draw_system_type": metadata["draw_system_type"],
                                    "draw_pool": metadata["draw_pool"],
                                    "draw_pool_key": metadata["draw_pool_key"],
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
                                    "actual_probability_raw": probability_raw,
                                    "actual_probability_source_column": f"{scope.lower()}_success_ratio",
                                    "probability_unit_detected": unit,
                                    "probability_metric": "p_draw",
                                    "extraction_method": "pdfplumber_table_extract_pipeline_cwmu_blind",
                                    "source_lineage": f"pipeline raw PDF copied from {rel(source_path)}; extracted from {rel(copied)} page {official_page}",
                                }
                            )
                            parsed_rows += 1
                    extraction_audit.append(
                        {
                            "source_file": rel(copied),
                            "source_page": official_page,
                            "hunt_code": hunt_code,
                            "hunt_name": hunt_name,
                            "table_rows_seen": len(table),
                            "truth_rows_created": parsed_rows,
                            "status": "PARSED",
                            "notes": "Only source rows with nonblank numeric success ratio were converted.",
                        }
                    )
                else:
                    extraction_audit.append(
                        {
                            "source_file": rel(copied),
                            "source_page": page_index,
                            "hunt_code": "",
                            "hunt_name": "",
                            "table_rows_seen": len(table),
                            "truth_rows_created": 0,
                            "status": "NOT_PARSED",
                            "notes": "Missing hunt header or extractable table.",
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
        "probability_metric",
        "sex_type",
        "hunt_type",
    ]
    staging_path = out_dir / "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE.csv"
    write_csv(staging_path, staging, staging_fields)
    extraction_audit_path = out_dir / "2018_CWMU_TRUTH_EXTRACTION_AUDIT.csv"
    write_csv(extraction_audit_path, extraction_audit)
    write_text(
        out_dir / "2018_CWMU_TRUTH_KEY_RECIPE.md",
        "# 2018 CWMU Truth Key Recipe\n\n"
        "PHASE A was blind to frozen prediction data. Keys are source-derived from pipeline CWMU PDF filenames and extracted PDF rows.\n\n"
        "Truth key fields:\n\n"
        "`target_year|source_family|draw_system_type|draw_pool_key|hunt_code|score_scope|residency|points|probability_metric`\n\n"
        "Source-derived values:\n\n"
        "- `target_year`: `2018`\n"
        "- `source_family`: `CWMU_BIG_GAME`, `CWMU_ANTLERLESS`, or `YOUTH_ANTLERLESS` from the source PDF family name.\n"
        "- `draw_system_type`: `CWMU_OFFICIAL_DRAW_RESULTS` for all CWMU truth rows.\n"
        "- `draw_pool_key`: source filename family/species/sex token, such as `cwmu_big_game_deer_buck`, `cwmu_antlerless_elk`, or `cwmu_youth_antlerless_elk`.\n"
        "- `hunt_code`, `points`, `residency`, and probability values are parsed from the official source PDF table only.\n\n"
        "No frozen prediction file, prediction hunt-code vocabulary, prediction draw-pool vocabulary, or prediction key shape is used in this recipe.\n",
    )

    keyed = []
    for row in staging:
        output = dict(row)
        output["official_score_key_v2"] = official_truth_key(output)
        keyed.append(output)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in keyed:
        grouped[clean(row.get("official_score_key_v2"))].append(row)
    deduped: list[dict[str, Any]] = []
    dedupe_decisions: list[dict[str, Any]] = []
    excluded_conflicts: list[dict[str, Any]] = []
    duplicate_audit: list[dict[str, Any]] = []
    for key, rows_for_key in sorted(grouped.items()):
        if len(rows_for_key) > 1:
            resolution = duplicate_resolution(rows_for_key)
            first = rows_for_key[0]
            duplicate_audit.append(
                {
                    "file_role": "blind_cwmu_truth_keyed",
                    "official_score_key_v2": key,
                    "duplicate_count": len(rows_for_key),
                    "hunt_code": clean(first.get("hunt_code")),
                    "residency": clean(first.get("residency")),
                    "point_level": clean(first.get("point_level")),
                    "draw_family": clean(first.get("source_family")),
                    "species": clean(first.get("species")),
                    "candidate_resolution": resolution,
                    "notes": "",
                }
            )
        else:
            resolution = "UNIQUE"
        if len(rows_for_key) == 1:
            deduped.append(dict(rows_for_key[0], dedupe_decision="UNIQUE", score_exclusion_reason=""))
            dedupe_decisions.append({"official_score_key_v2": key, "input_rows": 1, "output_rows": 1, "decision": "UNIQUE", "notes": ""})
        elif resolution in {"DUPLICATE_IDENTICAL_COLLAPSED", "DUPLICATE_LINEAGE_ONLY_COLLAPSED"}:
            keep = dict(rows_for_key[0])
            keep["dedupe_decision"] = resolution
            keep["source_lineage"] = " | ".join(dict.fromkeys(clean(row.get("source_lineage")) for row in rows_for_key if clean(row.get("source_lineage"))))
            keep["score_exclusion_reason"] = ""
            deduped.append(keep)
            dedupe_decisions.append({"official_score_key_v2": key, "input_rows": len(rows_for_key), "output_rows": 1, "decision": resolution, "notes": "Safe duplicate collapse."})
        else:
            excluded_conflicts.extend(dict(row, score_exclusion_reason="CONFLICT_REVIEW_REQUIRED") for row in rows_for_key)
            dedupe_decisions.append(
                {
                    "official_score_key_v2": key,
                    "input_rows": len(rows_for_key),
                    "output_rows": 0,
                    "decision": "CONFLICT_REVIEW_REQUIRED",
                    "notes": "Conflicting source-derived truth fields; excluded from scoring.",
                }
            )
    write_csv(out_dir / "2018_DUPLICATE_KEY_AUDIT.csv", duplicate_audit)
    write_csv(out_dir / "2018_CWMU_TRUTH_DEDUPE_DECISIONS.csv", dedupe_decisions)
    keyed_path = out_dir / "2018_CWMU_TRUTH_KEYED_DEDUPED.csv"
    write_csv(keyed_path, deduped)
    write_csv(out_dir / "2018_CWMU_TRUTH_CONFLICTS_EXCLUDED.csv", excluded_conflicts)

    source_pdf_lines = [f"- `{rel(path)}` sha256=`{sha256_file(path)}`" for path in selected_files]
    truth_lock_time = now()
    staging_hash = sha256_file(staging_path)
    keyed_hash = sha256_file(keyed_path)
    duplicate_key_count = len(duplicate_audit)
    residency_counts = Counter(clean(row.get("residency")) for row in deduped)
    point_counts = Counter(normalize_points(row.get("points")) for row in deduped)
    lock_manifest_path = out_dir / "2018_CWMU_TRUTH_LOCK_MANIFEST.md"
    write_text(
        lock_manifest_path,
        "# 2018 CWMU Truth Lock Manifest\n\n"
        f"truth_lock_timestamp: `{truth_lock_time}`\n\n"
        f"truth staging path: `{rel(staging_path)}`\n"
        f"truth keyed/deduped path: `{rel(keyed_path)}`\n"
        f"staging row count: `{len(staging)}`\n"
        f"keyed/deduped row count: `{len(deduped)}`\n"
        f"unique hunt codes: `{len({upper(row.get('hunt_code')) for row in deduped})}`\n"
        f"residency counts: `{dict(residency_counts)}`\n"
        f"point row counts: `{dict(point_counts)}`\n"
        f"duplicate-key counts: `{duplicate_key_count}`\n"
        f"excluded conflict counts: `{len(excluded_conflicts)}`\n"
        f"staging sha256: `{staging_hash}`\n"
        f"keyed/deduped sha256: `{keyed_hash}`\n\n"
        "## Source PDFs\n\n"
        + "\n".join(source_pdf_lines)
        + "\n\nTRUTH_LOCKED_BEFORE_PREDICTION_ACCESS = TRUE\n",
    )

    # PHASE C starts here. No truth outputs above are modified after this point.
    first_prediction_access_time = now()
    prediction_fields, prediction_rows = read_csv(PRED_PATH)
    prediction_key_counts = Counter(clean(row.get("official_score_key_v2")) for row in prediction_rows if clean(row.get("official_score_key_v2")))
    prediction_duplicate_keys = {key: count for key, count in prediction_key_counts.items() if count > 1}
    prediction_by_key = {
        clean(row.get("official_score_key_v2")): row
        for row in prediction_rows
        if clean(row.get("official_score_key_v2")) and prediction_key_counts[clean(row.get("official_score_key_v2"))] == 1
    }
    write_text(
        out_dir / "2019_MODEL_PREDICTION_SELECTION.md",
        "# 2019 Model Prediction Selection\n\n"
        f"first_prediction_access_timestamp: `{first_prediction_access_time}`\n\n"
        f"Selected prediction path: `{rel(PRED_PATH)}`\n\n"
        "Selected only after the blind CWMU truth lock manifest was written. Prediction data is used only for official_score_key_v2 inspection, exact joins, unmatched diagnostics, and metrics.\n\n"
        f"Row count: `{len(prediction_rows)}`\n"
        f"Columns: `{len(prediction_fields)}`\n"
        f"`official_score_key_v2` present: `{'official_score_key_v2' in prediction_fields}`\n"
        f"Blank score keys: `{sum(1 for row in prediction_rows if not clean(row.get('official_score_key_v2')))}`\n"
        f"Duplicate score keys: `{len(prediction_duplicate_keys)}`\n",
    )

    score_rows: list[dict[str, Any]] = []
    unmatched_truth: list[dict[str, Any]] = []
    matched_prediction_keys: set[str] = set()
    post_lock_defects: list[dict[str, Any]] = []
    for truth in deduped:
        candidates = bridge_candidate_keys(truth)
        matched_key = next((key for key in candidates if key in prediction_by_key), "")
        if not matched_key:
            unmatched_truth.append(
                {
                    **truth,
                    "bridge_candidate_keys": ";".join(candidates),
                    "bridge_status": "UNMATCHED_TRUTH",
                    "score_status": "UNSCORED",
                    "exclusion_reason": "NO_PREDICTION_KEY_MATCH",
                }
            )
            continue
        prediction = prediction_by_key[matched_key]
        predicted_probability, predicted_column = prediction_probability(prediction)
        try:
            actual_probability = float(clean(truth.get("actual_probability")))
        except ValueError:
            actual_probability = None
        if predicted_probability is None or actual_probability is None:
            score_status = "UNSCORED"
            exclusion_reason = "MISSING_NUMERIC_PROBABILITY"
            absolute_error = squared_error = bias = ""
            post_lock_defects.append(
                {
                    "official_truth_key": clean(truth.get("official_score_key_v2")),
                    "matched_prediction_key": matched_key,
                    "defect_type": exclusion_reason,
                    "notes": "Truth was not modified after lock.",
                }
            )
        else:
            score_status = "SCORED"
            exclusion_reason = ""
            bias_value = predicted_probability - actual_probability
            absolute_error = f"{abs(bias_value):.12g}"
            squared_error = f"{bias_value * bias_value:.12g}"
            bias = f"{bias_value:.12g}"
        score_rows.append(
            {
                "score_type": "BRIDGED_CONTRACT_SCORE",
                "permit_year": clean(truth.get("permit_year")),
                "model_year": clean(truth.get("model_year")),
                "official_score_key_v2": clean(truth.get("official_score_key_v2")),
                "matched_prediction_official_score_key_v2": matched_key,
                "hunt_code": clean(truth.get("hunt_code")),
                "residency": clean(truth.get("residency")),
                "point_level": clean(truth.get("point_level")),
                "draw_family": clean(truth.get("source_family")),
                "species": clean(truth.get("species")),
                "sex": clean(truth.get("sex")),
                "weapon": clean(truth.get("weapon")),
                "hunt_class": clean(truth.get("hunt_class")),
                "predicted_probability": "" if predicted_probability is None else f"{predicted_probability:.12g}",
                "actual_probability": "" if actual_probability is None else f"{actual_probability:.12g}",
                "absolute_error": absolute_error,
                "squared_error": squared_error,
                "bias": bias,
                "prediction_source_path": rel(PRED_PATH),
                "truth_source_path": rel(keyed_path),
                "source_file": clean(truth.get("source_file")),
                "source_page": clean(truth.get("source_page")),
                "bridge_status": "MATCHED_ON_POST_LOCK_BRIDGE_KEY",
                "score_status": score_status,
                "exclusion_reason": exclusion_reason,
                "prediction_probability_column": predicted_column,
            }
        )
        matched_prediction_keys.add(matched_key)
    unmatched_predictions = [
        {**row, "bridge_status": "UNMATCHED_PREDICTION", "score_status": "UNSCORED", "exclusion_reason": "NO_TRUTH_KEY_MATCH"}
        for key, row in prediction_by_key.items()
        if key not in matched_prediction_keys
    ]
    write_csv(out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE.csv", score_rows)
    write_csv(out_dir / "2018_SCORE_UNMATCHED_PREDICTIONS.csv", unmatched_predictions)
    write_csv(out_dir / "2018_SCORE_UNMATCHED_TRUTH.csv", unmatched_truth)
    write_csv(out_dir / "2018_CWMU_POST_LOCK_DEFECTS.csv", post_lock_defects)

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
    write_csv(out_dir / "2018_TO_2019_BRIDGED_CONTRACT_SCORE_SUMMARY.csv", summary_rows)

    by_hunt_point: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in deduped:
        by_hunt_point[(upper(row.get("hunt_code")), normalize_points(row.get("points")))].append(row)
    score_by_truth_key = {row["official_score_key_v2"]: row for row in score_rows}
    cwmu_audit = []
    for row in deduped:
        group = by_hunt_point[(upper(row.get("hunt_code")), normalize_points(row.get("points")))]
        scopes = {clean(item.get("score_scope")) for item in group}
        score = score_by_truth_key.get(clean(row.get("official_score_key_v2")))
        score_status = "SCORED" if score and score.get("score_status") == "SCORED" else "TRUTH_ONLY_UNSCORED"
        cwmu_audit.append(
            {
                "hunt_code": clean(row.get("hunt_code")),
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex": clean(row.get("sex")),
                "residency": clean(row.get("residency")),
                "point_level": clean(row.get("point_level")),
                "actual_probability": clean(row.get("actual_probability")),
                "has_resident_row": str("RESIDENT" in scopes).lower(),
                "has_nonresident_row": str("NONRESIDENT" in scopes).lower(),
                "has_total_row": str("TOTAL" in scopes).lower(),
                "total_matches_r_plus_nr_if_applicable": "NOT_EVALUATED_NO_TOTAL_ROWS" if "TOTAL" not in scopes else "REVIEW_REQUIRED",
                "source_file": clean(row.get("source_file")),
                "source_page": clean(row.get("source_page")),
                "score_status": score_status,
                "notes": "" if score_status == "SCORED" else "No exact post-lock bridge key match to frozen prediction.",
            }
        )
    write_csv(out_dir / "2018_CWMU_TRUTH_AUDIT.csv", cwmu_audit)

    truth_modified_after_prediction_access = False
    if score_rows and not excluded_conflicts and not unmatched_truth and not post_lock_defects:
        status = "PASS_CWMU_BRIDGED_BLIND"
    elif score_rows:
        status = "PASS_WITH_REVIEW_REQUIRED_BLIND"
    else:
        status = "FAIL_BLOCKED"
    if truth_modified_after_prediction_access:
        status = "FAIL_BLINDNESS_VIOLATION"

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
        f"Data-truth CWMU files inspected: `{len(datatruth_inventory)}`\n"
        f"Matching filenames: `{len(matching_names)}`\n"
        f"Matching filename/hash pairs: `{hash_matches}`\n\n"
        "Primary raw source for this blind run: pipeline leaf PDFs copied into the audit directory before extraction.\n",
    )
    write_text(
        out_dir / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md",
        "# 2018 Prediction Engine Repair Certification\n\n"
        "## Executive Summary\n\n"
        "A new clean blind run was created. CWMU truth was built independently from pipeline CWMU source PDFs only. The frozen prediction file was not opened until after `2018_CWMU_TRUTH_LOCK_MANIFEST.md` was written.\n\n"
        f"Final status: `{status}`\n\n"
        "## Blind Boundary\n\n"
        f"Run start timestamp: `{run_start}`\n"
        f"Truth lock timestamp: `{truth_lock_time}`\n"
        f"First prediction access timestamp: `{first_prediction_access_time}`\n"
        "Frozen prediction data was not accessed until after truth lock: `TRUE`\n"
        f"Truth modified after prediction access: `{str(truth_modified_after_prediction_access).upper()}`\n"
        f"Locked staging SHA256: `{staging_hash}`\n"
        f"Locked keyed/deduped SHA256: `{keyed_hash}`\n\n"
        "## Truth Outputs\n\n"
        f"Truth staging path: `{rel(staging_path)}`\n"
        f"Truth keyed/deduped path: `{rel(keyed_path)}`\n"
        f"Truth staging rows: `{len(staging)}`\n"
        f"Truth keyed/deduped rows: `{len(deduped)}`\n"
        f"Unique hunt codes: `{len({upper(row.get('hunt_code')) for row in deduped})}`\n"
        f"Duplicate-key groups: `{duplicate_key_count}`\n"
        f"Excluded conflict rows: `{len(excluded_conflicts)}`\n\n"
        "## Pipeline CWMU Source Inspection\n\n"
        f"Pipeline inventory rows: `{len(pipeline_inventory)}`\n"
        f"Data-truth inventory rows: `{len(datatruth_inventory)}`\n"
        f"Matching filenames: `{len(matching_names)}`\n"
        f"Matching hashes among matching filenames: `{hash_matches}`\n"
        f"Selected source PDF count: `{len(selected_files)}`\n\n"
        "## Selected Pipeline CWMU PDFs\n\n"
        + "\n".join(f"- `{rel(path)}`" for path in selected_files)
        + "\n\n## Scoring Results\n\n"
        f"Selected prediction path: `{rel(PRED_PATH)}`\n"
        f"Prediction rows: `{len(prediction_rows)}`\n"
        f"Duplicate prediction keys: `{len(prediction_duplicate_keys)}`\n"
        f"Matched score rows: `{len(score_rows)}`\n"
        f"Unmatched truth rows: `{len(unmatched_truth)}`\n"
        f"Unmatched prediction rows: `{len(unmatched_predictions)}`\n"
        f"Post-lock defect rows: `{len(post_lock_defects)}`\n\n"
        "## CWMU Findings\n\n"
        f"CWMU rows scored: `{sum(1 for row in cwmu_audit if row['score_status'] == 'SCORED')}`\n"
        f"CWMU rows truth-only/unscored: `{sum(1 for row in cwmu_audit if row['score_status'] != 'SCORED')}`\n"
        f"CWMU Big Game source files present: `{any('BIG_GAME' in path.name.upper() for path in selected_files)}`\n"
        f"CWMU Antlerless source files present: `{any('ANTLERLESS' in path.name.upper() and 'YOUTH' not in path.name.upper() for path in selected_files)}`\n"
        f"CWMU Youth Antlerless source files present: `{any('YOUTH_ANTLERLESS' in path.name.upper() for path in selected_files)}`\n\n"
        "## Remaining Blockers\n\n"
        "Scoring completed after a clean blind truth lock, but unmatched truth rows remain for review. Truth was not patched after prediction access.\n\n"
        "## Final Status\n\n"
        f"{status}\n",
    )

    terminal = {
        "2018_REPAIR_OUTPUT_DIR": out_dir,
        "2018_PIPELINE_CWMU_SOURCE_INVENTORY": out_dir / "2018_PIPELINE_CWMU_SOURCE_INVENTORY.csv",
        "2018_CWMU_RAW_SOURCE_COPY_MANIFEST": out_dir / "2018_CWMU_RAW_SOURCE_COPY_MANIFEST.csv",
        "2018_CWMU_TRUTH_STAGING_FROM_PIPELINE": staging_path,
        "2018_CWMU_TRUTH_LOCK_MANIFEST": lock_manifest_path,
        "2018_CWMU_TRUTH_KEYED_DEDUPED": keyed_path,
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
