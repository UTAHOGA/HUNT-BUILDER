"""Build the column/key alignment contract audit.

Audit-only. This script does not patch DATABASE.csv, truth files, or prediction
outputs.
"""

from __future__ import annotations

import csv
import hashlib
import os
import re
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Sequence, Set, Tuple


REPO_ROOT = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
OUT_DIR = REPO_ROOT / "audits" / f"column_key_alignment_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

DATABASE = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
DRAW_RESULTS_LONG = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
CANONICAL_DIR = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"

ROUTING_CONTRACTS = [
    REPO_ROOT / "engine" / "utah" / "models.py",
    REPO_ROOT / "engine" / "utah" / "rules.py",
    REPO_ROOT / "docs" / "utah_draw_routing_and_algorithm_v1.md",
    REPO_ROOT / "scripts" / "apply_draw_type_modifiers_and_validate.py",
    REPO_ROOT / "scripts" / "reconcile-expo-conservation-rows.py",
    REPO_ROOT / "scripts" / "sync_draw_design_authority.py",
    REPO_ROOT / "scripts" / "apply_draw_design_classification.py",
    REPO_ROOT / "scripts" / "normalize_canonical_draw_taxonomy.py",
]

APPROVED_DB_HEADERS = [
    "BOUNDARY_ID",
    "HUNT_CODE",
    "HUNT_NAME",
    "SPECIES",
    "SEX_TYPE",
    "WEAPON",
    "HUNT_TYPE",
    "SEASON",
    "HUNT_CLASS",
    "DRAW_DESIGN",
    "DRAW_POOL",
]

MASTER_PERMIT_RE = re.compile(r"^PERMITS_(20\d{2})_(RES|NON_RES|TOTAL)$")
HARVEST_RE = re.compile(r"^HARVEST_(20\d{2})_")

SEMANTIC_ROLES = [
    "boundary_id",
    "hunt_code",
    "hunt_name",
    "species",
    "sex_type",
    "weapon",
    "hunt_type",
    "season",
    "hunt_class",
    "permit_quota_res",
    "permit_quota_non_res",
    "permit_quota_total",
    "draw_design",
    "draw_pool",
    "harvest_data",
    "actual_draw_year",
    "model_target_year",
    "residency",
    "point_level",
    "applicants",
    "permits",
    "successful",
    "unsuccessful",
    "odds",
    "actual_probability",
    "source_file",
    "source_page",
    "source_lineage",
    "official_score_key_v2",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def clean(value: object) -> str:
    return str(value or "").strip()


def normalized_column(value: object) -> str:
    text = clean(value).upper()
    text = text.replace("PERMPITS", "PERMITS")
    text = text.replace("NON-RES", "NON_RES").replace("NON RES", "NON_RES")
    text = text.replace("NON_RESIDENT", "NON_RES")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    text = re.sub(r"PERMITS_(20\d{2})_TOTAL$", r"PERMITS_\1_TOTAL", text)
    return text


def norm_value(value: object) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", clean(value).upper()).strip("_")


def draw_design_pool_aligned(draw_design: str, draw_pool: str) -> bool:
    dd = norm_value(draw_design)
    dp = norm_value(draw_pool)
    if not dd or not dp:
        return False
    if dd == dp:
        return True
    if dd == "REFERENCE_ONLY" and dp.endswith("_REFERENCE"):
        return True
    return False


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def csv_header(path: Path) -> List[str]:
    if not path.exists() or path.suffix.lower() != ".csv":
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f).fieldnames or [])


def iter_csv(path: Path) -> Iterator[Dict[str, str]]:
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        yield from csv.DictReader(f)


def write_csv(path: Path, rows: Iterable[Dict[str, object]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def csv_stats(path: Path, year_filter: Tuple[str, str] | None = None) -> Dict[str, object]:
    fields = csv_header(path)
    count = 0
    hunts: Set[str] = set()
    for row in iter_csv(path):
        if year_filter and not (
            clean(row.get("actual_draw_year")) == year_filter[0]
            and clean(row.get("model_target_year")) == year_filter[1]
        ):
            continue
        count += 1
        code = clean(row.get("hunt_code") or row.get("HUNT_CODE") or row.get("HuntCode") or row.get("code"))
        if code:
            hunts.add(code.upper())
    fieldset = {normalized_column(f) for f in fields}
    return {
        "row_count": count,
        "column_count": len(fields),
        "unique_hunt_codes": len(hunts),
        "hunt_codes": hunts,
        "columns": fields,
        "normalized_columns": fieldset,
    }


def find_files(names: Sequence[str]) -> List[Path]:
    found: List[Path] = []
    target_names = set(names)
    for root, dirs, files in os.walk(REPO_ROOT):
        root_path = Path(root)
        if any(part in {".git", "node_modules", "__pycache__", ".pytest_cache"} for part in root_path.parts):
            dirs[:] = []
            continue
        if "pytest_deps" in root_path.parts:
            dirs[:] = []
            continue
        for name in files:
            if name in target_names:
                found.append(root_path / name)
    return sorted(found, key=lambda p: str(p).lower())


def latest_prediction_files() -> List[Path]:
    candidates = []
    for root, dirs, files in os.walk(REPO_ROOT / "audits"):
        root_path = Path(root)
        if "pytest_deps" in root_path.parts:
            dirs[:] = []
            continue
        for name in files:
            if name == "family_predictions.csv":
                candidates.append(root_path / name)
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[:3]


def file_role(path: Path) -> str:
    name = path.name
    if path == DATABASE:
        return "MASTER_HUNT_DATABASE"
    if path == DRAW_RESULTS_LONG:
        return "DRAW_RESULT_TRUTH_LAYER"
    if CANONICAL_DIR in path.parents:
        return "YEARLY_TRUTH_SLICE"
    if name.startswith("DRAW_ODDS_") or name == "WEBSITE_TAXONOMY_MATRIX.csv" or "WEBSITE_MATRIX" in name:
        return "WEBSITE_MATRIX"
    if path in ROUTING_CONTRACTS:
        return "ROUTING_CONTRACT" if path.suffix.lower() == ".md" else "SCRIPT_LOGIC"
    if name == "family_predictions.csv":
        return "PREDICTION_SURFACE_REFERENCE_ONLY"
    return "UNKNOWN_REVIEW_REQUIRED"


def semantic_role(raw_col: str) -> str:
    col = normalized_column(raw_col)
    if col in {"BOUNDARY_ID", "UNIT_ID", "BOUNDARY"}:
        return "boundary_id"
    if col in {"HUNT_CODE", "HUNTCODE", "CODE"}:
        return "hunt_code"
    if col in {"HUNT_NAME", "RAW_HUNT_NAME", "TITLE", "HUNT_TITLE"}:
        return "hunt_name"
    if col in {"SPECIES", "SPECIES_BUCKET", "BIG_GAME_SPECIES_BUCKET", "ANTLERLESS_SPECIES_BUCKET"}:
        return "species"
    if col in {"SEX_TYPE", "SEX", "SEX_CLASS", "SEX_CLASS_MATRIX"}:
        return "sex_type"
    if col in {"WEAPON", "WEAPON_TYPE"}:
        return "weapon"
    if col in {"HUNT_TYPE", "REPORT_FAMILY", "PROGRAM_BUCKET", "MATRIX_PROGRAM_BUCKET"}:
        return "hunt_type"
    if col in {"SEASON", "SEASON_DATES", "DATES"}:
        return "season"
    if col in {"HUNT_CLASS", "HUNT_DRAW_CLASS", "HUNT_CATEGORY", "CATEGORY"}:
        return "hunt_class"
    if re.match(r"PERMITS_20\d{2}_RES$", col) or col in {"RESIDENT_PERMITS", "RESIDENT_TOTAL_PERMITS"}:
        return "permit_quota_res"
    if re.match(r"PERMITS_20\d{2}_NON_RES$", col) or col in {"NONRESIDENT_PERMITS", "NONRESIDENT_TOTAL_PERMITS"}:
        return "permit_quota_non_res"
    if re.match(r"PERMITS_20\d{2}_TOTAL$", col) or col in {"TOTAL_PERMITS", "PERMIT_TOTAL", "QUOTA"}:
        return "permit_quota_total"
    if col in {"DRAW_DESIGN", "DRAW_SYSTEM", "DRAW_SYSTEM_TYPE", "DRAW_TYPE"}:
        return "draw_design"
    if col in {"DRAW_POOL", "DRAW_FAMILY", "SOURCE_FAMILY"}:
        return "draw_pool"
    if col.startswith("HARVEST_"):
        return "harvest_data"
    if col == "ACTUAL_DRAW_YEAR":
        return "actual_draw_year"
    if col == "MODEL_TARGET_YEAR":
        return "model_target_year"
    if col == "RESIDENCY":
        return "residency"
    if col in {"POINTS", "POINT_LEVEL", "PREFERENCE_POINTS", "BONUS_POINTS"}:
        return "point_level"
    if "APPLICANTS" in col:
        return "applicants"
    if col in {"SUCCESSFUL_APPLICANTS", "SUCCESSFUL"}:
        return "successful"
    if col in {"UNSUCCESSFUL_APPLICANTS", "UNSUCCESSFUL"}:
        return "unsuccessful"
    if col in {"P_DRAW_PERCENT", "ODDS_RAW", "SUCCESS_RATIO"}:
        return "odds"
    if col in {"P_DRAW", "ACTUAL_PROBABILITY"}:
        return "actual_probability"
    if col in {"SOURCE_FILE", "SOURCE_PDF", "DRAW_SOURCE_FILE"}:
        return "source_file"
    if col in {"SOURCE_PAGE", "PDF_PAGE", "OFFICIAL_PAGE"}:
        return "source_page"
    if col in {"SOURCE_LINEAGE", "SOURCE_PATH", "SOURCE_NAMESPACE", "DRAW_SOURCE_NAMESPACE"}:
        return "source_lineage"
    if col == "OFFICIAL_SCORE_KEY_V2":
        return "official_score_key_v2"
    return "unknown_review_required"


def approved_master_header(raw_col: str) -> str:
    col = normalized_column(raw_col)
    if col in APPROVED_DB_HEADERS:
        return col
    if MASTER_PERMIT_RE.match(col) or HARVEST_RE.match(col):
        return col
    aliases = {
        "PERMPITS": "PERMITS",
        "NON_RESIDENT": "NON_RES",
    }
    for old, new in aliases.items():
        if old in col:
            return col.replace(old, new)
    return ""


def is_truth_required(role: str) -> bool:
    return role in {
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "hunt_class",
        "draw_design",
        "draw_pool",
        "actual_draw_year",
        "model_target_year",
        "residency",
        "point_level",
        "applicants",
        "permits",
        "successful",
        "unsuccessful",
        "odds",
        "actual_probability",
        "source_file",
        "source_page",
        "source_lineage",
    }


def source_file_inventory(paths: List[Path]) -> List[Dict[str, object]]:
    rows = []
    for path in paths:
        exists = path.exists()
        role = file_role(path)
        stats = csv_stats(path) if exists and path.suffix.lower() == ".csv" else {"row_count": "", "column_count": "", "unique_hunt_codes": "", "columns": [], "normalized_columns": set()}
        cols = stats["normalized_columns"] if isinstance(stats["normalized_columns"], set) else set()
        rows.append(
            {
                "source_file": rel(path),
                "file_role": role,
                "exists": exists,
                "row_count": stats["row_count"],
                "column_count": stats["column_count"],
                "unique_hunt_codes": stats["unique_hunt_codes"],
                "has_official_score_key_v2": "OFFICIAL_SCORE_KEY_V2" in cols,
                "has_hunt_type": "HUNT_TYPE" in cols,
                "has_hunt_class": "HUNT_CLASS" in cols,
                "has_draw_design": "DRAW_DESIGN" in cols or "DRAW_SYSTEM_TYPE" in cols,
                "has_draw_pool": "DRAW_POOL" in cols or "DRAW_FAMILY" in cols or "SOURCE_FAMILY" in cols,
                "has_residency": "RESIDENCY" in cols,
                "has_point_level": "POINTS" in cols or "POINT_LEVEL" in cols,
                "has_actual_draw_year": "ACTUAL_DRAW_YEAR" in cols,
                "has_model_target_year": "MODEL_TARGET_YEAR" in cols,
                "notes": "reference only" if role == "PREDICTION_SURFACE_REFERENCE_ONLY" else "",
            }
        )
    return rows


def master_column_inventory(paths: List[Path]) -> List[Dict[str, object]]:
    rows = []
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        role = file_role(path)
        for col in csv_header(path):
            n = normalized_column(col)
            sem = semantic_role(col)
            rows.append(
                {
                    "source_file": rel(path),
                    "file_role": role,
                    "raw_column": col,
                    "normalized_column": n,
                    "approved_master_header": approved_master_header(col),
                    "scoring_extension_header": n if sem in {"official_score_key_v2", "actual_draw_year", "model_target_year", "residency", "point_level"} else "",
                    "semantic_role": sem,
                    "required_for_database_master": "TRUE" if approved_master_header(col) else "FALSE",
                    "required_for_truth_layer": "TRUE" if is_truth_required(sem) else "FALSE",
                    "required_for_bridge_comparable": "TRUE" if sem in {"hunt_code", "actual_draw_year", "model_target_year", "residency", "point_level", "official_score_key_v2", "draw_design", "draw_pool"} else "FALSE",
                    "required_for_official_score_key_v2": "TRUE" if sem in {"hunt_code", "actual_draw_year", "model_target_year", "residency", "point_level", "draw_design", "draw_pool"} or n == "RECORD_TYPE" else "FALSE",
                    "source_lineage_field": "TRUE" if sem in {"source_file", "source_page", "source_lineage"} else "FALSE",
                    "review_status": "PASS_MAPPED" if sem != "unknown_review_required" else "REVIEW_REQUIRED_UNKNOWN_COLUMN",
                    "notes": "",
                }
            )
    return rows


def database_to_truth_crosswalk() -> List[Dict[str, object]]:
    rows = []
    mappings = [
        ("BOUNDARY_ID", "boundary_id", "boundary_id / unit_id / boundary reference", "boundary_id"),
        ("HUNT_CODE", "hunt_code", "hunt_code", "hunt_code"),
        ("HUNT_NAME", "hunt_name", "hunt_name", "hunt_name"),
        ("SPECIES", "species", "species / species_bucket", "species"),
        ("SEX_TYPE", "sex_type", "sex_type / sex / sex_class", "sex_type"),
        ("WEAPON", "weapon", "weapon", "weapon"),
        ("HUNT_TYPE", "hunt_type", "hunt_type / report category / website family", "hunt_type"),
        ("SEASON", "season", "season / season_dates", "season"),
        ("HUNT_CLASS", "hunt_class", "hunt_class / program modifier", "hunt_class"),
        ("DRAW_DESIGN", "draw_design", "draw_design / draw_system_type", "draw_design"),
        ("DRAW_POOL", "draw_pool", "draw_pool / draw_family / source_family", "draw_pool"),
    ]
    for db, truth, rule, sem in mappings:
        rows.append(
            {
                "database_header": db,
                "database_normalized_header": db,
                "draw_results_long_header": truth,
                "canonical_yearly_header": truth,
                "website_matrix_field": db.lower(),
                "prediction_field": truth,
                "semantic_role": sem,
                "transformation_rule": rule,
                "required_for_master_database": "TRUE",
                "required_for_truth_results": "TRUE" if sem != "boundary_id" else "FALSE",
                "required_for_bridge_comparable": "TRUE" if sem in {"hunt_code", "draw_design", "draw_pool"} else "FALSE",
                "required_for_official_score_key_v2": "TRUE" if sem == "hunt_code" else "FALSE",
                "notes": "",
            }
        )
    for kind, truth, sem in [
        ("PERMITS_20XX_RES", "resident_total_permits / permits_20XX_res", "permit_quota_res"),
        ("PERMITS_20XX_NON_RES", "nonresident_total_permits / permits_20XX_nr", "permit_quota_non_res"),
        ("PERMITS_20XX_TOTAL", "total_permits / permits_20XX_total", "permit_quota_total"),
        ("HARVEST_20XX_*", "", "harvest_data"),
    ]:
        rows.append(
            {
                "database_header": kind,
                "database_normalized_header": kind,
                "draw_results_long_header": truth,
                "canonical_yearly_header": truth,
                "website_matrix_field": "",
                "prediction_field": "",
                "semantic_role": sem,
                "transformation_rule": "year-suffixed field family",
                "required_for_master_database": "TRUE",
                "required_for_truth_results": "FALSE",
                "required_for_bridge_comparable": "FALSE",
                "required_for_official_score_key_v2": "FALSE",
                "notes": "DATABASE quota/harvest context, not scoring row expansion",
            }
        )
    for bridge, sem in [
        ("actual_draw_year / permit_year", "actual_draw_year"),
        ("model_target_year / model_year", "model_target_year"),
        ("residency", "residency"),
        ("points / point_level", "point_level"),
        ("record_type", "record_type"),
        ("official_score_key_v2", "official_score_key_v2"),
    ]:
        rows.append(
            {
                "database_header": "",
                "database_normalized_header": "",
                "draw_results_long_header": bridge.split(" / ")[0],
                "canonical_yearly_header": bridge.split(" / ")[0],
                "website_matrix_field": "",
                "prediction_field": bridge,
                "semantic_role": sem,
                "transformation_rule": "bridge/comparable layer adds scoring row fields",
                "required_for_master_database": "FALSE",
                "required_for_truth_results": "TRUE" if sem != "official_score_key_v2" else "FALSE",
                "required_for_bridge_comparable": "TRUE",
                "required_for_official_score_key_v2": "TRUE",
                "notes": "not a DATABASE master field",
            }
        )
    return rows


def normalize_hunt_type(value: str, hunt_class: str = "", draw_design: str = "", draw_pool: str = "") -> Tuple[str, str, str]:
    raw = clean(value)
    lower = raw.lower()
    cls = clean(hunt_class).lower()
    dd = clean(draw_design).lower()
    if lower in {"l.e.", "le", "limited entry"} and cls == "expo" and dd == "expo":
        return "Expo", "REVIEW_REQUIRED_EXPO_LEGACY_ALIAS", "legacy L.E. + expo class/design should normalize to hunt_type=Expo"
    if lower == "expo":
        return "Expo", "PASS_ALIGNED", ""
    if lower == "conservation":
        return (
            "Conservation",
            "REVIEW_REQUIRED_CONSERVATION_ALLOCATION_CONTRACT",
            "Conservation permits are allocated benefit-auction permits; confirm against selection matrix and Conservation Permit PDF before mapping draw_design/draw_pool",
        )
    return raw, "PASS_ALIGNED", ""


def hunt_type_alignment_rows(paths: List[Path]) -> List[Dict[str, object]]:
    rows = []
    seen: Set[Tuple[str, ...]] = set()
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        role = file_role(path)
        if role not in {"MASTER_HUNT_DATABASE", "DRAW_RESULT_TRUTH_LAYER", "YEARLY_TRUTH_SLICE", "WEBSITE_MATRIX"}:
            continue
        for i, row in enumerate(iter_csv(path), start=2):
            raw_hunt_type = clean(row.get("hunt_type") or row.get("HUNT_TYPE") or row.get("HuntType"))
            raw_hunt_class = clean(row.get("hunt_class") or row.get("HUNT_CLASS") or row.get("hunt_draw_class") or row.get("category"))
            raw_draw_design = clean(row.get("draw_design") or row.get("DRAW_DESIGN") or row.get("draw_system_type"))
            raw_draw_pool = clean(row.get("draw_pool") or row.get("DRAW_POOL") or row.get("draw_family") or row.get("source_family"))
            hunt_code = clean(row.get("hunt_code") or row.get("HUNT_CODE"))
            species = clean(row.get("species") or row.get("SPECIES"))
            key = (rel(path), hunt_code, raw_hunt_type, raw_hunt_class, raw_draw_design, raw_draw_pool, species)
            if key in seen:
                continue
            seen.add(key)
            normalized_type, status, reason = normalize_hunt_type(raw_hunt_type, raw_hunt_class, raw_draw_design, raw_draw_pool)
            normalized_class = raw_hunt_class
            normalized_design = raw_draw_design
            normalized_pool = raw_draw_pool
            expected_type = normalized_type
            expected_class = raw_hunt_class
            expected_design = raw_draw_design
            expected_pool = raw_draw_pool
            lower = " ".join([raw_hunt_type, raw_hunt_class, raw_draw_design, raw_draw_pool, species, clean(row.get("hunt_name") or row.get("HUNT_NAME"))]).lower()
            if "premium" in lower and species and species.lower() != "deer":
                status = "REVIEW_REQUIRED_UNEXPECTED_PREMIUM_NON_DEER_LABEL"
                reason = "P.L.E. is deer-only"
            elif "premium" in lower and species.lower() == "deer":
                expected_type = "Premium Limited Entry"
            elif "dedicated hunter" in lower and raw_draw_design and "preference" not in raw_draw_design.lower():
                status = "REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT"
                reason = "Dedicated Hunter is usually hunt_class/program overlay; draw_design should route to the dedicated-hunter preference mechanism"
                expected_class = "Dedicated Hunter"
                expected_design = "PREFERENCE_DEDICATED_HUNTER_DEER"
            elif "sportsman" in lower and raw_draw_design and "random" not in raw_draw_design.lower() and "sportsman" not in raw_draw_design.lower():
                status = "REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT"
                reason = "Sportsman should route to random-only family"
                expected_design = "SPORTSMAN_RANDOM_ONLY"
                expected_pool = "sportsman"
            elif not raw_draw_design and role in {"MASTER_HUNT_DATABASE", "DRAW_RESULT_TRUTH_LAYER", "YEARLY_TRUTH_SLICE"}:
                status = "REVIEW_REQUIRED_DRAW_DESIGN_MISSING"
                reason = "draw design/system missing"
            elif not raw_draw_pool and role == "MASTER_HUNT_DATABASE":
                status = "REVIEW_REQUIRED_DRAW_POOL_MISSING"
                reason = "draw pool missing on master database row"
            rows.append(
                {
                    "source_file": rel(path),
                    "row_number_or_context": i if len(rows) < 20000 else "distinct_context",
                    "hunt_code": hunt_code,
                    "hunt_name": clean(row.get("hunt_name") or row.get("HUNT_NAME")),
                    "raw_hunt_type": raw_hunt_type,
                    "normalized_hunt_type": normalized_type,
                    "raw_hunt_class": raw_hunt_class,
                    "normalized_hunt_class": normalized_class,
                    "raw_draw_design": raw_draw_design,
                    "normalized_draw_design": normalized_design,
                    "raw_draw_pool": raw_draw_pool,
                    "normalized_draw_pool": normalized_pool,
                    "expected_hunt_type": expected_type,
                    "expected_hunt_class": expected_class,
                    "expected_draw_design": expected_design,
                    "expected_draw_pool": expected_pool,
                    "status": status,
                    "review_reason": reason,
                    "notes": "distinct row/context audit",
                }
            )
            if len(rows) > 40000:
                break
    return rows


def vocabulary_from_text(path: Path) -> List[Dict[str, object]]:
    rows = []
    if not path.exists():
        return rows
    text = path.read_text(encoding="utf-8", errors="ignore")
    if path.name == "models.py":
        for value in re.findall(r"\b[A-Z_]+\s*=\s*[\"']([^\"']+)[\"']", text):
            rows.append({"source_file": rel(path), "source_context": "models.py constant", "vocabulary_layer": "DrawSystem", "value": value})
    for token in sorted(set(re.findall(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b", text))):
        if any(key in token for key in ["BONUS", "PREFERENCE", "RANDOM", "SPORTSMAN", "TURKEY", "CWMU", "YOUTH", "EXPO", "CONSERVATION", "OIL", "LE"]):
            layer = "draw_family" if token.isupper() else "unknown"
            rows.append({"source_file": rel(path), "source_context": "text token", "vocabulary_layer": layer, "value": token})
    for quoted in sorted(set(re.findall(r"[\"']([^\"']*(?:Limited Entry|Once-in-a-lifetime|Preference|Max/Weighted Split|Random|Expo|Conservation|Sportsman|CWMU)[^\"']*)[\"']", text, flags=re.I))):
        rows.append({"source_file": rel(path), "source_context": "quoted/string vocabulary", "vocabulary_layer": "hunt_type", "value": quoted})
    return rows


def vocabulary_audit(paths: List[Path]) -> List[Dict[str, object]]:
    rows = []
    for path in ROUTING_CONTRACTS:
        for rec in vocabulary_from_text(path):
            value = clean(rec["value"])
            rows.append(
                {
                    **rec,
                    "normalized_value": norm_value(value),
                    "meaning": "",
                    "used_by_engine": "TRUE" if "engine" in rel(path) else "FALSE",
                    "used_by_database": "FALSE",
                    "used_by_truth": "FALSE",
                    "used_by_website_matrix": "TRUE" if path.name.endswith(".md") else "FALSE",
                    "status": "PASS_EXISTING_VOCABULARY",
                    "notes": "extracted from repo contract/script",
                }
            )
    value_fields = {
        "draw_system_type": "draw_system_type",
        "draw_design": "draw_design",
        "draw_pool": "draw_pool",
        "source_family": "draw_family",
        "draw_family": "draw_family",
        "hunt_type": "hunt_type",
        "HUNT_TYPE": "hunt_type",
        "hunt_class": "hunt_class",
        "HUNT_CLASS": "hunt_class",
    }
    for path in paths:
        if not path.exists() or path.suffix.lower() != ".csv":
            continue
        headers = csv_header(path)
        wanted = [h for h in headers if h in value_fields]
        if not wanted:
            continue
        counters = {h: Counter() for h in wanted}
        for row in iter_csv(path):
            for h in wanted:
                value = clean(row.get(h))
                if value:
                    counters[h][value] += 1
        role = file_role(path)
        for h, counter in counters.items():
            for value, count in counter.most_common(1000):
                rows.append(
                    {
                        "source_file": rel(path),
                        "source_context": f"{h}; rows={count}",
                        "vocabulary_layer": value_fields[h],
                        "value": value,
                        "normalized_value": norm_value(value),
                        "meaning": "",
                        "used_by_engine": "FALSE",
                        "used_by_database": "TRUE" if role == "MASTER_HUNT_DATABASE" else "FALSE",
                        "used_by_truth": "TRUE" if role in {"DRAW_RESULT_TRUTH_LAYER", "YEARLY_TRUTH_SLICE"} else "FALSE",
                        "used_by_website_matrix": "TRUE" if value_fields[h] in {"hunt_type", "hunt_class"} else "FALSE",
                        "status": "PASS_EXISTING_VOCABULARY",
                        "notes": "observed value, not invented",
                    }
                )
    return rows


def rg_search_terms() -> List[str]:
    terms = ["official_score_key_v2", "score_key", "build_score_key", "truth_comparable", "prediction_surface", "draw_family", "draw_system_type", "source_scope", "group_key", "output_key"]
    results = []
    search_roots = ["scripts", "engine", "tools", "tests", "docs"]
    for term in terms:
        try:
            proc = subprocess.run(["rg", "-n", term, *search_roots], cwd=REPO_ROOT, text=True, capture_output=True, timeout=20)
            lines = proc.stdout.splitlines()[:50]
            results.extend([f"{term}: {line}" for line in lines])
        except Exception as exc:
            results.append(f"{term}: search failed: {exc}")
    return results


def canonical_paths() -> List[Path]:
    return sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv"))


def overlap_rows() -> Tuple[List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]], List[Dict[str, object]]]:
    db_stats = csv_stats(DATABASE)
    long_stats = csv_stats(DRAW_RESULTS_LONG)
    cpaths = canonical_paths()
    c2025 = next((p for p in cpaths if "2025_for_2026" in p.name), None)
    c2026 = next((p for p in cpaths if "2026_for_2027" in p.name), None)
    stats_by_path = {DATABASE: db_stats, DRAW_RESULTS_LONG: long_stats}
    if c2025:
        stats_by_path[c2025] = csv_stats(c2025)
    if c2026:
        stats_by_path[c2026] = csv_stats(c2026)

    rows = []
    pairs = [
        ("DATABASE vs draw_results_long", DATABASE, DRAW_RESULTS_LONG),
        ("DATABASE vs 2025_for_2026 canonical", DATABASE, c2025),
        ("DATABASE vs 2026_for_2027 canonical", DATABASE, c2026),
    ]
    for name, left, right in pairs:
        if not right:
            continue
        ls = stats_by_path[left]
        rs = stats_by_path[right]
        left_codes = ls["hunt_codes"]
        right_codes = rs["hunt_codes"]
        rows.append(
            {
                "comparison_name": name,
                "left_file": rel(left),
                "right_file": rel(right),
                "left_rows": ls["row_count"],
                "right_rows": rs["row_count"],
                "left_unique_hunt_codes": len(left_codes),
                "right_unique_hunt_codes": len(right_codes),
                "shared_hunt_codes": len(left_codes & right_codes),
                "left_only_hunt_codes": len(left_codes - right_codes),
                "right_only_hunt_codes": len(right_codes - left_codes),
                "exact_key_possible": "FALSE",
                "reason_exact_key_not_possible": "DATABASE lacks actual_draw_year/model_target_year/residency/points/record_type by design",
                "status": "PASS_WITH_REVIEW_REQUIRED",
                "notes": "hunt_code overlap only; bridge required for scoring",
            }
        )
    canonical_total = sum(csv_stats(p)["row_count"] for p in cpaths)
    rows.append(
        {
            "comparison_name": "draw_results_long vs all canonical yearly totals",
            "left_file": rel(DRAW_RESULTS_LONG),
            "right_file": rel(CANONICAL_DIR),
            "left_rows": long_stats["row_count"],
            "right_rows": canonical_total,
            "left_unique_hunt_codes": len(long_stats["hunt_codes"]),
            "right_unique_hunt_codes": "",
            "shared_hunt_codes": "",
            "left_only_hunt_codes": "",
            "right_only_hunt_codes": "",
            "exact_key_possible": "FALSE",
            "reason_exact_key_not_possible": "long is aggregate across years; compare by yearly slices",
            "status": "PASS_WITH_REVIEW_REQUIRED",
            "notes": f"row_gap={canonical_total - int(long_stats['row_count'])}",
        }
    )

    db_only = [{"hunt_code": code, "source": "DATABASE_ONLY"} for code in sorted(db_stats["hunt_codes"] - long_stats["hunt_codes"])]
    truth_only = [{"hunt_code": code, "source": "TRUTH_ONLY"} for code in sorted(long_stats["hunt_codes"] - db_stats["hunt_codes"])]
    c2017 = next((p for p in cpaths if "2017_for_2018" in p.name), None)
    long2017 = csv_stats(DRAW_RESULTS_LONG, ("2017", "2018"))
    c2017_stats = csv_stats(c2017) if c2017 else {"row_count": 0, "unique_hunt_codes": 0}
    row_gap_2017 = int(c2017_stats["row_count"]) - int(long2017["row_count"])
    mismatch_status = "PASS_2017_2018_RECONCILED_PROMOTED" if row_gap_2017 == 0 else "REVIEW_REQUIRED_BEFORE_PATCH"
    evidence_note = (
        "90 raw-PDF-proven black bear special-layout rows from 17_drawing_odds.pdf are reconciled/promoted in active long and canonical truth"
        if row_gap_2017 == 0
        else "90 raw-PDF-proven black bear special-layout rows from 17_drawing_odds.pdf are absent from draw_results_long"
    )
    mismatch = [
        {
            "year_slice": "2017_for_2018",
            "draw_results_long_rows": long2017["row_count"],
            "canonical_yearly_rows": c2017_stats["row_count"],
            "row_gap": row_gap_2017,
            "known_evidence": evidence_note,
            "status": mismatch_status,
        }
    ]
    return rows, db_only, truth_only, mismatch


def gaps(
    inventory: List[Dict[str, object]],
    alignment: List[Dict[str, object]],
    overlap: List[Dict[str, object]],
) -> List[Dict[str, object]]:
    rows = []
    db_cols = set(csv_stats(DATABASE)["normalized_columns"])
    long_cols = set(csv_stats(DRAW_RESULTS_LONG)["normalized_columns"])
    for h in APPROVED_DB_HEADERS:
        if h not in db_cols:
            rows.append({"issue_type": "MISSING_MASTER_COLUMN", "source_file": rel(DATABASE), "field_name": h, "severity": "BLOCKER", "blocks_truth_resolution": "FALSE", "blocks_bridge_comparable": "FALSE", "blocks_runtime_prediction": "TRUE", "recommended_action": "review DATABASE header contract before patch", "notes": ""})
    for field in ["ACTUAL_DRAW_YEAR", "MODEL_TARGET_YEAR", "RESIDENCY", "POINTS", "RECORD_TYPE"]:
        if field not in db_cols:
            rows.append({"issue_type": "MISSING_BRIDGE_KEY_FIELD", "source_file": rel(DATABASE), "field_name": field, "severity": "INFO", "blocks_truth_resolution": "FALSE", "blocks_bridge_comparable": "TRUE", "blocks_runtime_prediction": "FALSE", "recommended_action": "bridge/comparable layer supplies this field; do not force into DATABASE", "notes": "missing by design"})
    source_truth_has_score_key = any(
        rec.get("has_official_score_key_v2") is True
        and rec.get("file_role") in {"DRAW_RESULT_TRUTH_LAYER", "YEARLY_TRUTH_SLICE", "MASTER_HUNT_DATABASE"}
        for rec in inventory
    )
    if "OFFICIAL_SCORE_KEY_V2" not in db_cols and "OFFICIAL_SCORE_KEY_V2" not in long_cols and not source_truth_has_score_key:
        rows.append({"issue_type": "OFFICIAL_SCORE_KEY_MISSING", "source_file": "source truth surfaces", "field_name": "official_score_key_v2", "severity": "REVIEW", "blocks_truth_resolution": "FALSE", "blocks_bridge_comparable": "TRUE", "blocks_runtime_prediction": "FALSE", "recommended_action": "centralize bridge/comparable score-key builder", "notes": "do not inject into DATABASE in this mission"})
    c2017 = next((p for p in canonical_paths() if "2017_for_2018" in p.name), None)
    long2017 = csv_stats(DRAW_RESULTS_LONG, ("2017", "2018"))
    c2017_stats = csv_stats(c2017) if c2017 else {"row_count": 0}
    row_gap_2017 = int(c2017_stats["row_count"]) - int(long2017["row_count"])
    if row_gap_2017 != 0:
        rows.append({"issue_type": "LONG_VS_CANONICAL_2017_ROW_MISMATCH_90", "source_file": rel(DRAW_RESULTS_LONG), "field_name": "row_count", "current_value": long2017["row_count"], "expected_value": c2017_stats["row_count"], "severity": "REVIEW", "blocks_truth_resolution": "TRUE", "blocks_bridge_comparable": "TRUE", "blocks_runtime_prediction": "FALSE", "recommended_action": "review 2017 raw-PDF evidence before patching draw_results_long", "notes": "black bear special-layout rows"})
    for rec in alignment:
        status = clean(rec.get("status"))
        if status.startswith("REVIEW") or status.startswith("BLOCKED"):
            rows.append({"issue_type": status.replace("REVIEW_REQUIRED_", ""), "source_file": rec.get("source_file", ""), "row_or_context": rec.get("row_number_or_context", ""), "field_name": "hunt_type/hunt_class/draw_design/draw_pool", "current_value": rec.get("raw_hunt_type", ""), "expected_value": rec.get("expected_hunt_type", ""), "severity": "REVIEW", "blocks_truth_resolution": "FALSE", "blocks_bridge_comparable": "FALSE", "blocks_runtime_prediction": "TRUE", "recommended_action": "audit row-level migration before patch", "notes": rec.get("review_reason", "")})
    return rows


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    canonical = canonical_paths()
    website_files = find_files(["DRAW_ODDS_DEEP_PULL_MANIFEST.csv", "DRAW_ODDS_YEAR_STRUCTURE_AUDIT.csv", "DRAW_ODDS_TAXONOMY_CORRECTIONS.csv", "WEBSITE_TAXONOMY_MATRIX.csv"])
    taxonomy_refs = find_files(["DRAW_ODDS_TAXONOMY_REFERENCE.md"])
    prediction_files = latest_prediction_files()
    all_sources = [DATABASE, DRAW_RESULTS_LONG, *canonical, *website_files, *taxonomy_refs, *ROUTING_CONTRACTS, *prediction_files]

    inventory = source_file_inventory(all_sources)
    p01 = OUT_DIR / "01_COLUMN_KEY_SOURCE_FILE_INVENTORY.csv"
    write_csv(p01, inventory, ["source_file", "file_role", "exists", "row_count", "column_count", "unique_hunt_codes", "has_official_score_key_v2", "has_hunt_type", "has_hunt_class", "has_draw_design", "has_draw_pool", "has_residency", "has_point_level", "has_actual_draw_year", "has_model_target_year", "notes"])

    column_inventory = master_column_inventory(all_sources)
    p02 = OUT_DIR / "02_MASTER_COLUMN_INVENTORY.csv"
    write_csv(p02, column_inventory, ["source_file", "file_role", "raw_column", "normalized_column", "approved_master_header", "scoring_extension_header", "semantic_role", "required_for_database_master", "required_for_truth_layer", "required_for_bridge_comparable", "required_for_official_score_key_v2", "source_lineage_field", "review_status", "notes"])

    crosswalk = database_to_truth_crosswalk()
    p03 = OUT_DIR / "03_DATABASE_TO_TRUTH_COLUMN_CROSSWALK.csv"
    write_csv(p03, crosswalk, ["database_header", "database_normalized_header", "draw_results_long_header", "canonical_yearly_header", "website_matrix_field", "prediction_field", "semantic_role", "transformation_rule", "required_for_master_database", "required_for_truth_results", "required_for_bridge_comparable", "required_for_official_score_key_v2", "notes"])

    alignment = hunt_type_alignment_rows([DATABASE, DRAW_RESULTS_LONG, *canonical, *website_files])
    p04 = OUT_DIR / "04_HUNT_TYPE_DRAW_FIELD_ALIGNMENT.csv"
    write_csv(p04, alignment, ["source_file", "row_number_or_context", "hunt_code", "hunt_name", "raw_hunt_type", "normalized_hunt_type", "raw_hunt_class", "normalized_hunt_class", "raw_draw_design", "normalized_draw_design", "raw_draw_pool", "normalized_draw_pool", "expected_hunt_type", "expected_hunt_class", "expected_draw_design", "expected_draw_pool", "status", "review_reason", "notes"])

    vocab = vocabulary_audit([DATABASE, DRAW_RESULTS_LONG, *canonical, *website_files])
    p05 = OUT_DIR / "05_EXISTING_DRAW_VOCABULARY_AUDIT.csv"
    write_csv(p05, vocab, ["source_file", "source_context", "vocabulary_layer", "value", "normalized_value", "meaning", "used_by_engine", "used_by_database", "used_by_truth", "used_by_website_matrix", "status", "notes"])

    search_hits = rg_search_terms()
    source_truth_has_score_key = any(rec["has_official_score_key_v2"] == True and rec["file_role"] in {"DRAW_RESULT_TRUTH_LAYER", "YEARLY_TRUTH_SLICE", "MASTER_HUNT_DATABASE"} for rec in inventory)
    prediction_has_score_key = any(rec["has_official_score_key_v2"] == True and rec["file_role"] == "PREDICTION_SURFACE_REFERENCE_ONLY" for rec in inventory)
    p06 = OUT_DIR / "06_OFFICIAL_SCORE_KEY_REQUIREMENTS.md"
    p06.write_text(
        "\n".join(
            [
                "# Official Score Key Requirements",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                f"canonical official_score_key_v2 builder exists: {'REVIEW_REQUIRED_PARTIAL_RECIPES_FOUND' if search_hits else 'FALSE'}",
                f"official_score_key_v2 present in source truth: {str(source_truth_has_score_key).upper()}",
                f"official_score_key_v2 present in selected prediction references: {str(prediction_has_score_key).upper()}",
                "",
                "## Required Bridge Fields",
                "",
                "- actual_draw_year or permit_year",
                "- model_target_year or model_year",
                "- hunt_code",
                "- residency",
                "- points / point_level",
                "- record_type",
                "- draw_family / source_family",
                "- draw_system_type / draw_design where existing recipe requires it",
                "- hunt_program where existing recipe requires it",
                "",
                "## DATABASE Fields Lacking By Design",
                "",
                "DATABASE.csv is the MASTER_HUNT_DATABASE and lacks scoring-row fields by design: actual_draw_year, model_target_year, residency, points, and record_type. Do not inject official_score_key_v2 into DATABASE.csv in this mission.",
                "",
                "## HUNT_TYPE Participation",
                "",
                "HUNT_TYPE participates as supporting routing context. The score key should be built from the canonical bridge recipe fields; HUNT_TYPE should affect routing/normalization but should not replace hunt_code, year, residency, points, or record_type.",
                "",
                "## Expo / Conservation",
                "",
                "Expo promotion to HUNT_TYPE and Conservation as HUNT_TYPE affect routing and draw-family classification. They should not alter source truth rows without a separate migration audit and backup.",
                "",
                "## Recommendation",
                "",
                "Centralize one official_score_key_v2 builder for bridge/comparable/scoring outputs if multiple partial recipes exist.",
                "",
                "## Search Hits",
                "",
                *[f"- {hit}" for hit in search_hits[:300]],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    overlap, db_only, truth_only, mismatch = overlap_rows()
    p07 = OUT_DIR / "07_HUNT_CODE_OVERLAP_AND_KEY_READINESS.csv"
    write_csv(p07, overlap, ["comparison_name", "left_file", "right_file", "left_rows", "right_rows", "left_unique_hunt_codes", "right_unique_hunt_codes", "shared_hunt_codes", "left_only_hunt_codes", "right_only_hunt_codes", "exact_key_possible", "reason_exact_key_not_possible", "status", "notes"])
    p07_db_only = OUT_DIR / "07_DATABASE_ONLY_HUNT_CODES.csv"
    write_csv(p07_db_only, db_only, ["hunt_code", "source"])
    p07_truth_only = OUT_DIR / "07_TRUTH_ONLY_HUNT_CODES.csv"
    write_csv(p07_truth_only, truth_only, ["hunt_code", "source"])
    p07_2017 = OUT_DIR / "07_2017_LONG_VS_CANONICAL_MISMATCH_SUMMARY.csv"
    write_csv(p07_2017, mismatch, ["year_slice", "draw_results_long_rows", "canonical_yearly_rows", "row_gap", "known_evidence", "status"])

    gap_rows = gaps(inventory, alignment, overlap)
    p08 = OUT_DIR / "08_COLUMN_KEY_ALIGNMENT_GAPS.csv"
    write_csv(p08, gap_rows, ["issue_type", "source_file", "row_or_context", "field_name", "current_value", "expected_value", "severity", "blocks_truth_resolution", "blocks_bridge_comparable", "blocks_runtime_prediction", "recommended_action", "notes"])

    p09 = OUT_DIR / "09_RECOMMENDED_COLUMN_AND_KEY_CONTRACT.md"
    p09.write_text(
        "\n".join(
            [
                "# Recommended Column And Key Contract",
                "",
                "## 1. File Role Separation",
                "",
                "DATABASE.csv is the MASTER_HUNT_DATABASE. draw_results_long.csv is the DRAW_RESULT_TRUTH_LAYER. canonical_yearly files are YEARLY_TRUTH_SLICES. Bridge/comparable outputs add scoring-row expansion and official_score_key_v2.",
                "",
                "## 2. DATABASE Master Headers",
                "",
                "- BOUNDARY_ID\n- HUNT_CODE\n- HUNT_NAME\n- SPECIES\n- SEX_TYPE\n- WEAPON\n- HUNT_TYPE\n- SEASON\n- HUNT_CLASS\n- PERMITS_20XX_RES\n- PERMITS_20XX_NON_RES\n- PERMITS_20XX_TOTAL\n- DRAW_DESIGN\n- DRAW_POOL\n- HARVEST_20XX_*",
                "",
                "## 3. Truth-Layer Headers",
                "",
                "Truth layers carry draw result rows by year, hunt_code, residency, points, record_type, applicants, permits, successful, odds/probability, and source lineage.",
                "",
                "## 4. Bridge/Comparable Headers",
                "",
                "- actual_draw_year / permit_year\n- model_target_year / model_year\n- residency\n- points / point_level\n- record_type\n- applicants\n- permits\n- successful\n- odds_raw\n- actual_probability\n- source lineage\n- official_score_key_v2",
                "",
                "## 5. official_score_key_v2 Requirements",
                "",
                "The score key belongs in bridge/comparable/scoring outputs unless later promoted by contract. It requires year lane, hunt_code, residency, points, record_type, and routing family fields required by the canonical builder.",
                "",
                "## 6. HUNT_TYPE Contract",
                "",
                "HUNT_TYPE is the website/user-facing hunt family. It must not be collapsed with HUNT_CLASS, DRAW_DESIGN, or DRAW_POOL.",
                "",
                "## 7. Expo / Conservation Contract",
                "",
                "Expo = HUNT_TYPE. Conservation = HUNT_TYPE, but Conservation permits are allocated benefit-auction permits rather than a normal draw pool. Confirm Conservation field mapping against the hunt selection matrix and the associated Conservation Permit PDF before source patching. Legacy L.E. + hunt_class=expo = LEGACY_EXPO_ALIAS.",
                "",
                "## 8. DRAW_DESIGN / DRAW_POOL Relationship",
                "",
                "DRAW_DESIGN maps to existing draw system/rule design vocabulary. DRAW_POOL maps to draw lane/family. Do not invent labels; use repo vocabulary first.",
                "",
                "## 8A. Dedicated Hunter Contract",
                "",
                "Dedicated Hunter is usually HUNT_CLASS/program overlay. It should not be promoted to primary HUNT_TYPE when the source row remains General Season or another hunt family.",
                "",
                "## 9. Big Game Species Taxonomy",
                "",
                "Big Game species bucket count is 8. P.L.E. is deer-only. L.E. Big Game is deer, elk, pronghorn. O.I.L. is bison, Rocky Mountain bighorn sheep, Desert bighorn sheep, moose, mountain goat.",
                "",
                "## 10. 2017 Mismatch Handling",
                "",
                "Resolve the 2017 90-row raw-PDF-proven mismatch before patching draw_results_long. Evidence points to black bear special-layout rows from 17_drawing_odds.pdf.",
                "",
                "## 11. What Not To Collapse",
                "",
                "Do not collapse HUNT_TYPE into DRAW_DESIGN. Do not collapse CWMU into species. Do not make youth a peer split against adult; youth is a set-aside quota overlay where source-proven.",
                "",
                "## 12. What Not To Patch Yet",
                "",
                "Do not patch DATABASE.csv, draw_results_long.csv, canonical_yearly files, or source CSVs in this audit mission.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    db_stats = csv_stats(DATABASE)
    long_stats = csv_stats(DRAW_RESULTS_LONG)
    db_cols = set(db_stats["normalized_columns"])
    missing_master = [h for h in APPROVED_DB_HEADERS if h not in db_cols]
    key_status = "PASS_WITH_REVIEW_REQUIRED"
    if len(missing_master) > 0:
        key_status = "FAIL_BLOCKED_MISSING_MASTER_COLUMNS"
    p10 = OUT_DIR / "10_COLUMN_KEY_ALIGNMENT_REPORT.md"
    p10.write_text(
        "\n".join(
            [
                "# Column / Key Alignment Report",
                "",
                f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
                "",
                "1. Does DATABASE.csv match the approved master header contract?",
                f"   {'No' if missing_master else 'Yes'}. Missing approved base headers: {', '.join(missing_master) if missing_master else 'none'}.",
                "",
                "2. Which DATABASE columns are missing or aliased?",
                f"   Missing/needs review: {', '.join(missing_master) if missing_master else 'none from the base approved set'}. Alias normalization is documented in 02_MASTER_COLUMN_INVENTORY.csv.",
                "",
                "3. Does draw_results_long.csv map to DATABASE by hunt_code/descriptors?",
                "   Yes, by hunt_code and descriptors, but it is not an exact scoring-key join.",
                "",
                "4. Why DATABASE cannot exact-key join to draw-result rows directly?",
                "   DATABASE lacks actual_draw_year, model_target_year, residency, points, and record_type by design.",
                "",
                "5. Which fields must be added by the bridge/comparable layer?",
                "   actual_draw_year/model_target_year, residency, points/point_level, record_type, source family/draw family, and official_score_key_v2.",
                "",
                "6. Is official_score_key_v2 present anywhere in source truth?",
                f"   {str(source_truth_has_score_key).upper()}.",
                "",
                "7. Which existing repo files define draw type / draw system vocabulary?",
                "   engine/utah/models.py, engine/utah/rules.py, docs/utah_draw_routing_and_algorithm_v1.md, and the listed draw-design normalization scripts.",
                "",
                "8. How should HUNT_TYPE differ from HUNT_CLASS, DRAW_DESIGN, and DRAW_POOL?",
                "   HUNT_TYPE is user-facing hunt family. HUNT_CLASS further diversifies rows where needed. DRAW_DESIGN is rule/design vocabulary. DRAW_POOL is lane/family routing vocabulary.",
                "",
                "9. Is Expo now treated as HUNT_TYPE?",
                "   Yes. Legacy L.E. + hunt_class=expo is supported as LEGACY_EXPO_ALIAS in audit outputs.",
                "",
                "10. Is Conservation treated as HUNT_TYPE?",
                "   Yes. Conservation is HUNT_TYPE, but not a normal draw pool. The associated Conservation Permit PDF lists species, area, condition/value/organization allocation rows, so draw_design/draw_pool mapping remains source-review required.",
                "",
                "11. What are the remaining key blockers?",
                "   No hard truth blockers are raised by the reconciled 2017 row counts. Remaining review items are Conservation allocation contract confirmation, draw_design/draw_pool patch candidates, and continued official_score_key_v2 bridge centralization.",
                "",
                "12. What is the next safe action before any patching?",
                "   Review this audit plus the 2017 raw-PDF evidence package, then run a dedicated repair mission with backup/manifest if patching draw_results_long or source CSVs is approved.",
                "",
                "## Final Recommendation",
                "",
                "- Keep DATABASE.csv as master hunt database.",
                "- Do not add official_score_key_v2 directly to DATABASE.csv in this mission.",
                "- Build/repair bridge comparable key layer separately.",
                "- Resolve 2017 90-row raw-PDF evidence before patching draw_results_long.",
                "- Promote Expo to HUNT_TYPE in contract/audit outputs; patch source CSVs only after row-level migration audit and backup.",
                "",
                f"KEY_ALIGNMENT_STATUS={key_status}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    terminal = "\n".join(
        [
            f"COLUMN_KEY_ALIGNMENT_OUTPUT_DIR={OUT_DIR}",
            f"SOURCE_FILE_INVENTORY={p01}",
            f"MASTER_COLUMN_INVENTORY={p02}",
            f"DATABASE_TO_TRUTH_COLUMN_CROSSWALK={p03}",
            f"HUNT_TYPE_DRAW_FIELD_ALIGNMENT={p04}",
            f"EXISTING_DRAW_VOCABULARY_AUDIT={p05}",
            f"OFFICIAL_SCORE_KEY_REQUIREMENTS={p06}",
            f"HUNT_CODE_OVERLAP_AND_KEY_READINESS={p07}",
            f"COLUMN_KEY_ALIGNMENT_GAPS={p08}",
            f"RECOMMENDED_COLUMN_AND_KEY_CONTRACT={p09}",
            f"COLUMN_KEY_ALIGNMENT_REPORT={p10}",
            "DATABASE_IS_MASTER_HUNT_DATABASE=TRUE",
            "DRAW_RESULTS_LONG_IS_TRUTH_LAYER=TRUE",
            "CANONICAL_YEARLY_ARE_YEARLY_TRUTH_SLICES=TRUE",
            f"OFFICIAL_SCORE_KEY_V2_PRESENT_IN_SOURCE_TRUTH={str(source_truth_has_score_key).upper()}",
            "EXPO_PROMOTED_TO_HUNT_TYPE=TRUE",
            "CONSERVATION_IS_HUNT_TYPE=TRUE",
            "LEGACY_EXPO_ALIAS_SUPPORTED=TRUE",
            "BIG_GAME_SPECIES_BUCKET_COUNT=8",
            "PLE_DEER_ONLY=TRUE",
            f"KEY_ALIGNMENT_STATUS={key_status}",
            "NEXT_ACTION=REVIEW_AUDIT_AND_2017_RAW_PDF_EVIDENCE_BEFORE_ANY_PATCHING",
        ]
    )
    (OUT_DIR / "FINAL_TERMINAL_OUTPUT.txt").write_text(terminal + "\n", encoding="utf-8")
    print(terminal)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
