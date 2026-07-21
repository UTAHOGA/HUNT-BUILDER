from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
YEAR_PAIR = "2018_PERMITS=2019_MODEL"
CANONICAL = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
CWMU_KEYED = REPO / "audits" / "2018_prediction_repair_blind20260721_020854" / "2018_CWMU_TRUTH_KEYED_DEDUPED.csv"
CWMU_LOCK = REPO / "audits" / "2018_prediction_repair_blind20260721_020854" / "2018_CWMU_TRUTH_LOCK_MANIFEST.md"
ARCGIS_HUNT_BOUNDARY = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "arcgis" / "udwr_huntnumber_boundary_table1_full.csv"
HUNT_UNITS_GEOJSON = REPO / "processed_data" / "public_contracts" / "hunt_units.geojson"
AUDIT_ROOT = REPO / "audits"
CWMU_BLIND_KEY_SOURCE = "2018_CWMU_BLIND_LOCKED_REKEYED_TO_2019_MODEL_TARGET"

BRIDGE_COLUMNS = [
    "hunt_type",
    "species",
    "hunt_class",
    "draw_pool",
    "sex_type",
    "weapon_type",
    "hunt_code",
    "boundary_id",
    "target_year",
    "source_family",
    "draw_pool_key",
    "score_scope",
    "probability_metric",
    "probability_value",
    "official_score_key_v2",
    "official_score_key_v2_source",
    "scoring_disposition",
    "score_exclusion_reason",
    "cwmu_blind_embed_status",
]


def clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def token(value: object, default: str = "na") -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or default


def upper(value: object) -> str:
    return clean(value).upper()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def row_hash(row: dict[str, str], fields: list[str]) -> str:
    return hashlib.sha256("\x1f".join(clean(row.get(field)) for field in fields).encode("utf-8")).hexdigest().upper()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def source_family_for_canonical(row: dict[str, str]) -> str:
    draw_system = upper(row.get("draw_system_type") or row.get("draw_design"))
    draw_pool = clean(row.get("draw_pool")).lower()
    hunt_type = clean(row.get("hunt_type"))
    hunt_class = upper(row.get("hunt_draw_class") or row.get("hunt_class"))
    source_file = clean(row.get("source_file") or row.get("draw_source_file") or row.get("source_pdf")).lower()
    text = " ".join(clean(row.get(field)).lower() for field in ("notes", "hunt_name", "hunt_class", "hunt_draw_class", "source_file", "draw_pool"))

    if "cwmu" in text:
        return "CANONICAL_CWMU_LEGACY_GRAIN"
    if draw_system == "SPORTSMAN_RANDOM_ONLY" or "sportsman" in source_file:
        return "SPORTSMAN"
    if "bear" in source_file or hunt_class == "BLACK_BEAR":
        return "BEAR_DRAW_RESULTS"
    if "cougar" in source_file or hunt_class == "COUGAR":
        return "COUGAR"
    if "turkey" in source_file or "TURKEY" in hunt_class:
        return "TURKEY"
    if draw_system == "YOUTH_GENERAL_ANY_BULL_ELK":
        return "YOUTH_ANY_BULL_ELK"
    if draw_system == "PREFERENCE_DEDICATED_HUNTER_DEER":
        return "DEDICATED_HUNTER_DEER"
    if draw_system == "PREFERENCE_GENERAL_SEASON_BUCK_DEER":
        if draw_pool == "youth_general_deer":
            return "YOUTH_GENERAL_SEASON_DEER"
        if draw_pool == "lifetime_general_deer":
            return "LIFETIME_GENERAL_SEASON_DEER"
        return "GENERAL_SEASON_DEER"
    if draw_system in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}:
        if draw_pool.startswith("youth_"):
            return "YOUTH_ANTLERLESS"
        return "ADULT_ANTLERLESS"
    if draw_system == "REFERENCE_ONLY":
        return "REFERENCE_ONLY"
    if draw_system == "MAX_WEIGHTED_SPLIT":
        if hunt_type == "Premium Limited Entry":
            return "PLE_BIG_GAME"
        if hunt_type == "Once-in-a-lifetime":
            return "OIL_BIG_GAME"
        return "LE_BIG_GAME"
    return draw_system or "UNKNOWN"


def draw_pool_key_for(row: dict[str, str], source_family: str) -> str:
    draw_pool = clean(row.get("draw_pool_key") or row.get("draw_pool")).lower()
    if source_family in {"LE_BIG_GAME", "PLE_BIG_GAME", "OIL_BIG_GAME", "CWMU_BIG_GAME"}:
        parts = [
            ("design", row.get("draw_design") or row.get("draw_system_type")),
            ("class", row.get("hunt_draw_class") or row.get("hunt_class")),
            ("pool", draw_pool),
            ("species", row.get("species")),
            ("hunt", row.get("hunt_type")),
            ("sex", row.get("sex_type") or row.get("sex")),
        ]
        return "__".join(f"{name}_{token(value)}" for name, value in parts)
    return draw_pool or "standard"


def score_scope_and_residency(value: object) -> tuple[str, str]:
    text = clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"resident", "res", "r"}:
        return "RESIDENT", "Resident"
    if text in {"nonresident", "nonres", "nr", "n"}:
        return "NONRESIDENT", "Nonresident"
    return "TOTAL", ""


def points_for(row: dict[str, str], source_family: str) -> str:
    points = clean(row.get("points") or row.get("point_level"))
    if source_family == "SPORTSMAN" and points.upper() == "TOTAL":
        return ""
    return points


def probability_value(row: dict[str, str]) -> str:
    for field in ("p_draw", "actual_probability", "total_p_draw", "resident_p_draw", "nonresident_p_draw"):
        value = clean(row.get(field))
        if value:
            return value
    return ""


def official_key(target_year: str, source_family: str, draw_system_type: str, draw_pool_key: str, hunt_code: str, score_scope: str, residency: str, points: str, probability_metric: str) -> str:
    return "|".join(
        [
            clean(target_year),
            upper(source_family),
            upper(draw_system_type),
            clean(draw_pool_key).lower(),
            upper(hunt_code),
            upper(score_scope),
            clean(residency),
            clean(points),
            clean(probability_metric),
        ]
    )


def is_cwmu_legacy_canonical(row: dict[str, str]) -> bool:
    if clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE:
        return False
    text = " ".join(clean(row.get(field)).lower() for field in ("notes", "hunt_name", "source_file", "draw_pool", "hunt_class", "hunt_draw_class"))
    return "cwmu" in text


def boundary_name(value: object) -> str:
    text = clean(value).lower()
    text = re.sub(r"\s+cwmu$", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return text


def build_cwmu_boundary_lookup(rows: list[dict[str, str]]) -> tuple[dict[str, str], dict[str, str]]:
    candidates: dict[str, set[str]] = {}
    source_by_code: dict[str, str] = {}
    for row in rows:
        if not is_cwmu_legacy_canonical(row):
            continue
        hunt_code = upper(row.get("hunt_code"))
        boundary_id = clean(row.get("boundary_id"))
        if hunt_code and boundary_id:
            candidates.setdefault(hunt_code, set()).add(boundary_id)
    lookup = {hunt_code: next(iter(values)) for hunt_code, values in candidates.items() if len(values) == 1}
    for hunt_code in lookup:
        source_by_code[hunt_code] = "2018_CANONICAL_LEGACY_UNIQUE_HUNT_CODE_BOUNDARY"

    if ARCGIS_HUNT_BOUNDARY.exists():
        _, boundary_rows = read_csv(ARCGIS_HUNT_BOUNDARY)
        for row in boundary_rows:
            hunt_code = upper(row.get("HUNT_NUMBER") or row.get("hunt_code"))
            boundary_id = clean(row.get("BOUNDARYID") or row.get("boundary_id"))
            if hunt_code and boundary_id and hunt_code not in lookup:
                lookup[hunt_code] = boundary_id
                source_by_code[hunt_code] = "2026_ARCGIS_HUNTNUMBER_BOUNDARY_TABLE_EXACT_HUNT_CODE"

    name_lookup: dict[str, tuple[str, str]] = {}
    if HUNT_UNITS_GEOJSON.exists():
        geo = read_json(HUNT_UNITS_GEOJSON)
        if isinstance(geo, dict):
            for feature in geo.get("features", []):
                props = feature.get("properties", {}) if isinstance(feature, dict) else {}
                name = boundary_name(props.get("boundary_name") or props.get("Boundary_Name"))
                boundary_id = clean(props.get("boundary_id") or props.get("BoundaryID"))
                if name and boundary_id and name not in name_lookup:
                    name_lookup[name] = (boundary_id, "HUNT_UNITS_GEOJSON_EXACT_BOUNDARY_NAME")
    for row in rows:
        if clean(row.get("official_score_key_v2_source")) != CWMU_BLIND_KEY_SOURCE:
            continue
        hunt_code = upper(row.get("hunt_code"))
        if not hunt_code or hunt_code in lookup:
            continue
        name = boundary_name(row.get("hunt_name"))
        match = name_lookup.get(name)
        if match:
            lookup[hunt_code] = match[0]
            source_by_code[hunt_code] = match[1]

    return lookup, source_by_code


def canonical_bridge_row(row: dict[str, str], cwmu_boundary_by_hunt_code: dict[str, str]) -> dict[str, str]:
    output = dict(row)
    target_year = clean(row.get("target_year") or row.get("model_target_year"))
    embedded_cwmu = clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE
    source_family = clean(row.get("source_family")) if embedded_cwmu else source_family_for_canonical(row)
    draw_system_type = upper(row.get("draw_system_type") or row.get("draw_design"))
    draw_pool_key = draw_pool_key_for(row, source_family)
    score_scope, residency = score_scope_and_residency(row.get("residency"))
    if embedded_cwmu:
        score_scope = clean(row.get("score_scope") or score_scope)
        residency = clean(row.get("residency") or residency)
    points = points_for(row, source_family)
    probability_metric = "p_draw"
    key = official_key(target_year, source_family, draw_system_type, draw_pool_key, row.get("hunt_code", ""), score_scope, residency, points, probability_metric)
    legacy_cwmu = is_cwmu_legacy_canonical(row)
    boundary_id = clean(row.get("boundary_id"))
    if embedded_cwmu and not boundary_id:
        boundary_id = cwmu_boundary_by_hunt_code.get(upper(row.get("hunt_code")), "")
    output.update(
        {
            "hunt_type": clean(row.get("hunt_type")),
            "species": clean(row.get("species")),
            "hunt_class": clean(row.get("hunt_class") or row.get("hunt_draw_class")),
            "draw_pool": clean(row.get("draw_pool")),
            "sex_type": clean(row.get("sex_type") or row.get("sex")),
            "weapon_type": clean(row.get("weapon_type") or row.get("weapon")),
            "hunt_code": clean(row.get("hunt_code")),
            "boundary_id": boundary_id,
            "target_year": target_year,
            "source_family": source_family,
            "draw_pool_key": draw_pool_key,
            "score_scope": score_scope,
            "residency": residency if not clean(row.get("residency")) else clean(row.get("residency")),
            "points": points,
            "probability_metric": probability_metric,
            "probability_value": probability_value(row),
            "official_score_key_v2": key,
            "official_score_key_v2_source": clean(row.get("official_score_key_v2_source")) if embedded_cwmu else "DERIVED_FROM_2018_CANONICAL_YEARLY",
            "scoring_disposition": "SCORABLE_CWMU_BLIND_BRIDGE" if embedded_cwmu else ("EXCLUDED_SUPERSEDED_BY_CWMU_BLIND_BRIDGE" if legacy_cwmu else "SCORABLE_CANONICAL_BRIDGE"),
            "score_exclusion_reason": "Canonical CWMU-noted row retained for lineage but exact-key scoring uses embedded blind CWMU row grain." if legacy_cwmu else "",
            "cwmu_blind_embed_status": "EMBEDDED_FROM_LOCKED_BLIND_CWMU_TRUTH" if embedded_cwmu else ("CANONICAL_CWMU_LEGACY_RETAINED_SUPERSEDED" if legacy_cwmu else "NOT_CWMU"),
        }
    )
    return output


def short_cwmu_hunt_name(value: str) -> str:
    text = clean(value)
    for marker in (" - Any Legal Weapon", " Resident Applicants", " Non-Resident Applicants"):
        if marker in text:
            text = text.split(marker, 1)[0]
    return text


def cwmu_embedded_row(row: dict[str, str], canonical_fields: list[str]) -> dict[str, str]:
    output = {field: "" for field in canonical_fields}
    target_year = clean(row.get("model_year") or "2019")
    source_family = clean(row.get("source_family"))
    draw_system_type = clean(row.get("draw_system_type") or "CWMU_OFFICIAL_DRAW_RESULTS")
    draw_pool_key = clean(row.get("draw_pool_key") or row.get("draw_pool"))
    score_scope = clean(row.get("score_scope") or "RESIDENT")
    residency = clean(row.get("residency") or "Resident")
    points = clean(row.get("points") or row.get("point_level"))
    probability_metric = clean(row.get("probability_metric") or "p_draw")
    key = official_key(target_year, source_family, draw_system_type, draw_pool_key, row.get("hunt_code", ""), score_scope, residency, points, probability_metric)

    output.update(
        {
            "actual_draw_year": clean(row.get("permit_year") or "2018"),
            "model_target_year": target_year,
            "target_year": target_year,
            "hunt_code": clean(row.get("hunt_code")),
            "hunt_name": short_cwmu_hunt_name(row.get("hunt_name", "")),
            "raw_hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "sex": clean(row.get("sex")),
            "sex_type": clean(row.get("sex_type") or row.get("sex")),
            "hunt_type": clean(row.get("hunt_type") or "CWMU"),
            "weapon": clean(row.get("weapon")),
            "weapon_type": clean(row.get("weapon_type") or row.get("weapon")),
            "boundary_id": clean(row.get("boundary_id")),
            "draw_design": draw_system_type,
            "hunt_draw_class": clean(row.get("hunt_class") or "CWMU"),
            "hunt_class": clean(row.get("hunt_class") or "CWMU"),
            "points": points,
            "residency": residency,
            "score_scope": score_scope,
            "row_type": "cwmu_blind_resident_draw_result",
            "record_type": "hunt_total_draw_result" if points.upper() == "TOTAL" else "point_level_draw_result",
            "resident_eligible_applicants": clean(row.get("eligible_applicants") or row.get("applicants")),
            "resident_bonus_permits": clean(row.get("bonus_permits")),
            "resident_regular_permits": clean(row.get("regular_permits")),
            "resident_total_permits": clean(row.get("total_permits") or row.get("permits")),
            "resident_p_draw": clean(row.get("actual_probability")),
            "resident_p_draw_percent": "",
            "eligible_applicants": clean(row.get("eligible_applicants") or row.get("applicants")),
            "successful_applicants": clean(row.get("successful_applicants") or row.get("successful")),
            "unsuccessful_applicants": clean(row.get("unsuccessful_applicants") or row.get("unsuccessful")),
            "p_draw": clean(row.get("actual_probability")),
            "p_draw_percent": "",
            "source_scope": "2018_CWMU_BLIND_LOCKED",
            "source_namespace": "2018_CWMU_BLIND_LOCKED",
            "draw_source_namespace": "2018_CWMU_BLIND_LOCKED",
            "source_file": clean(row.get("source_file")),
            "draw_source_file": clean(row.get("source_file")),
            "source_path": clean(row.get("source_lineage")),
            "source_pdf": clean(row.get("source_file")),
            "pdf_page": clean(row.get("source_page")),
            "official_page": clean(row.get("source_page")),
            "page_kind": "cwmu_blind_pdf_row",
            "source_dataset": "2018_CWMU_TRUTH_KEYED_DEDUPED",
            "extraction_status": "LOCKED_BLIND_CWMU",
            "parse_method": clean(row.get("extraction_method")),
            "qa_status": "PASS_CWMU_BRIDGED_BLIND",
            "notes": "Embedded from clean blind CWMU repair run; original blind key target_year=2018 re-keyed to 2019 model target per 2018_PERMITS=2019_MODEL contract.",
            "candidate_promotion_status": "EMBEDDED_2018_CWMU_BLIND_KEYED_TRUTH",
            "unit": short_cwmu_hunt_name(row.get("hunt_name", "")),
            "draw_system_type": draw_system_type,
            "draw_pool": clean(row.get("draw_pool")),
            "draw_pool_key": draw_pool_key,
            "draw_system_type_source": "2018_CWMU_BLIND_LOCKED",
            "draw_system_type_confidence": "LOCKED_BLIND",
            "probability_metric": probability_metric,
            "probability_value": clean(row.get("actual_probability")),
            "official_score_key_v2": key,
            "official_score_key_v2_source": "2018_CWMU_BLIND_LOCKED_REKEYED_TO_2019_MODEL_TARGET",
            "scoring_disposition": "SCORABLE_CWMU_BLIND_BRIDGE",
            "score_exclusion_reason": "",
            "cwmu_blind_embed_status": "EMBEDDED_FROM_LOCKED_BLIND_CWMU_TRUTH",
        }
    )
    return output


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = AUDIT_ROOT / f"2018_full_year_official_score_key_v2_bridge_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=False)

    original_hash = sha256(CANONICAL)
    canonical_header, canonical_rows = read_csv(CANONICAL)
    cwmu_header, cwmu_rows = read_csv(CWMU_KEYED)
    all_fields = list(canonical_header)
    for column in BRIDGE_COLUMNS:
        if column not in all_fields:
            all_fields.append(column)

    already_embedded = any(
        clean(row.get("official_score_key_v2_source")) == "2018_CWMU_BLIND_LOCKED_REKEYED_TO_2019_MODEL_TARGET"
        for row in canonical_rows
    )

    cwmu_boundary_by_hunt_code, cwmu_boundary_source_by_hunt_code = build_cwmu_boundary_lookup(canonical_rows)
    embedded_rows_needing_boundary_backfill = [
        row for row in canonical_rows
        if clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE
        and not clean(row.get("boundary_id"))
        and upper(row.get("hunt_code")) in cwmu_boundary_by_hunt_code
    ]

    bridge_rows = [canonical_bridge_row(row, cwmu_boundary_by_hunt_code) for row in canonical_rows]
    embedded_rows: list[dict[str, str]] = []
    if not already_embedded:
        embedded_rows = [cwmu_embedded_row(row, all_fields) for row in cwmu_rows]
        bridge_rows.extend(embedded_rows)

    key_counts = Counter(clean(row.get("official_score_key_v2")) for row in bridge_rows if clean(row.get("official_score_key_v2")))
    duplicate_rows = [
        {
            "official_score_key_v2": key,
            "duplicate_count": count,
            "review_status": "DUPLICATE_KEY_REVIEW_REQUIRED",
        }
        for key, count in sorted(key_counts.items())
        if count > 1
    ]
    blank_key_rows = [row for row in bridge_rows if not clean(row.get("official_score_key_v2"))]

    key_audit_rows = []
    for row in bridge_rows:
        key = clean(row.get("official_score_key_v2"))
        key_audit_rows.append(
            {
                "official_score_key_v2": key,
                "hunt_type": clean(row.get("hunt_type")),
                "species": clean(row.get("species")),
                "hunt_class": clean(row.get("hunt_class") or row.get("hunt_draw_class")),
                "draw_pool": clean(row.get("draw_pool")),
                "sex_type": clean(row.get("sex_type") or row.get("sex")),
                "weapon_type": clean(row.get("weapon_type") or row.get("weapon")),
                "hunt_code": clean(row.get("hunt_code")),
                "boundary_id": clean(row.get("boundary_id")),
                "boundary_id_status": "PRESENT" if clean(row.get("boundary_id")) else "BLANK",
                "target_year": clean(row.get("target_year")),
                "source_family": clean(row.get("source_family")),
                "draw_system_type": clean(row.get("draw_system_type")),
                "draw_pool_key": clean(row.get("draw_pool_key")),
                "score_scope": clean(row.get("score_scope")),
                "residency": clean(row.get("residency")),
                "points": clean(row.get("points")),
                "probability_metric": clean(row.get("probability_metric")),
                "probability_value": clean(row.get("probability_value")),
                "scoring_disposition": clean(row.get("scoring_disposition")),
                "cwmu_blind_embed_status": clean(row.get("cwmu_blind_embed_status")),
                "duplicate_key_count": key_counts.get(key, 0),
            }
        )

    bridge_path = out_dir / "2018_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_BRIDGE.csv"
    key_audit_path = out_dir / "2018_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_KEY_AUDIT.csv"
    duplicate_path = out_dir / "2018_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_DUPLICATES.csv"
    embed_path = out_dir / "2018_CWMU_BLIND_CANONICAL_EMBED_AUDIT.csv"
    boundary_gap_path = out_dir / "2018_CWMU_BLIND_BOUNDARY_ID_GAPS.csv"
    boundary_repair_path = out_dir / "2018_CWMU_BLIND_BOUNDARY_ID_REPAIR_AUDIT.csv"
    manifest_path = out_dir / "2018_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_BRIDGE_MANIFEST.md"
    status_path = out_dir / "2018_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_BRIDGE_STATUS.json"

    write_csv(bridge_path, bridge_rows, all_fields)
    write_csv(
        key_audit_path,
        key_audit_rows,
        [
            "official_score_key_v2",
            "hunt_type",
            "species",
            "hunt_class",
            "draw_pool",
            "sex_type",
            "weapon_type",
            "hunt_code",
            "boundary_id",
            "boundary_id_status",
            "target_year",
            "source_family",
            "draw_system_type",
            "draw_pool_key",
            "score_scope",
            "residency",
            "points",
            "probability_metric",
            "probability_value",
            "scoring_disposition",
            "cwmu_blind_embed_status",
            "duplicate_key_count",
        ],
    )
    write_csv(duplicate_path, duplicate_rows, ["official_score_key_v2", "duplicate_count", "review_status"])
    boundary_gap_rows = [
        {
            "hunt_code": clean(row.get("hunt_code")),
            "hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class") or row.get("hunt_draw_class")),
            "draw_pool": clean(row.get("draw_pool")),
            "sex_type": clean(row.get("sex_type") or row.get("sex")),
            "weapon_type": clean(row.get("weapon_type") or row.get("weapon")),
            "points": clean(row.get("points")),
            "residency": clean(row.get("residency")),
            "official_score_key_v2": clean(row.get("official_score_key_v2")),
            "source_file": clean(row.get("source_file")),
            "gap_reason": "LOCKED_CWMU_SOURCE_HAS_NO_BOUNDARY_ID_AND_NO_UNIQUE_CANONICAL_LEGACY_BOUNDARY_MATCH",
        }
        for row in bridge_rows
        if clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE and not clean(row.get("boundary_id"))
    ]
    write_csv(
        boundary_gap_path,
        boundary_gap_rows,
        [
            "hunt_code",
            "hunt_name",
            "species",
            "hunt_type",
            "hunt_class",
            "draw_pool",
            "sex_type",
            "weapon_type",
            "points",
            "residency",
            "official_score_key_v2",
            "source_file",
            "gap_reason",
        ],
    )
    boundary_repair_rows = [
        {
            "hunt_code": clean(row.get("hunt_code")),
            "hunt_name": clean(row.get("hunt_name")),
            "species": clean(row.get("species")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class") or row.get("hunt_draw_class")),
            "draw_pool": clean(row.get("draw_pool")),
            "sex_type": clean(row.get("sex_type") or row.get("sex")),
            "weapon_type": clean(row.get("weapon_type") or row.get("weapon")),
            "boundary_id": clean(row.get("boundary_id")),
            "boundary_id_source": cwmu_boundary_source_by_hunt_code.get(upper(row.get("hunt_code")), "PREEXISTING_OR_UNRESOLVED"),
            "official_score_key_v2": clean(row.get("official_score_key_v2")),
        }
        for row in bridge_rows
        if clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE
    ]
    write_csv(
        boundary_repair_path,
        boundary_repair_rows,
        [
            "hunt_code",
            "hunt_name",
            "species",
            "hunt_type",
            "hunt_class",
            "draw_pool",
            "sex_type",
            "weapon_type",
            "boundary_id",
            "boundary_id_source",
            "official_score_key_v2",
        ],
    )
    write_csv(
        embed_path,
        [
            {
                "source_row_hash": row_hash(row, cwmu_header),
                "hunt_code": row.get("hunt_code", ""),
                "points": row.get("points", ""),
                "residency": row.get("residency", ""),
                "original_blind_official_score_key_v2": row.get("official_score_key_v2", ""),
                "embedded_official_score_key_v2": embedded_rows[index].get("official_score_key_v2", "") if index < len(embedded_rows) else "",
                "embed_status": "ALREADY_PRESENT" if already_embedded else "EMBEDDED",
            }
            for index, row in enumerate(cwmu_rows)
        ],
        ["source_row_hash", "hunt_code", "points", "residency", "original_blind_official_score_key_v2", "embedded_official_score_key_v2", "embed_status"],
    )

    backup_path = ""
    canonical_patched = False
    if not already_embedded or "official_score_key_v2" not in canonical_header or embedded_rows_needing_boundary_backfill:
        backup_dir = CANONICAL.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"draw_results_2018_for_2019_canonical_yearly_draw_results.before_official_score_key_v2_bridge_{stamp}.csv"
        shutil.copy2(CANONICAL, backup)
        write_csv(CANONICAL, bridge_rows, all_fields)
        backup_path = str(backup)
        canonical_patched = True

    patched_hash = sha256(CANONICAL)
    scorable_rows = [row for row in bridge_rows if clean(row.get("scoring_disposition")).startswith("SCORABLE")]
    excluded_rows = [row for row in bridge_rows if clean(row.get("scoring_disposition")).startswith("EXCLUDED")]
    status = {
        "YEAR_PAIR": YEAR_PAIR,
        "AUDIT_OUTPUT_DIR": str(out_dir),
        "CANONICAL_FILE": str(CANONICAL),
        "CANONICAL_ROWS_BEFORE": len(canonical_rows),
        "CWMU_BLIND_ROWS_AVAILABLE": len(cwmu_rows),
        "CWMU_BLIND_ROWS_EMBEDDED_THIS_RUN": 0 if already_embedded else len(embedded_rows),
        "CWMU_BOUNDARY_ID_BACKFILLED_FROM_CANONICAL_LEGACY_ROWS": len(embedded_rows_needing_boundary_backfill),
        "CWMU_BOUNDARY_ID_STILL_BLANK_ROWS": sum(
            1 for row in bridge_rows
            if clean(row.get("official_score_key_v2_source")) == CWMU_BLIND_KEY_SOURCE and not clean(row.get("boundary_id"))
        ),
        "CANONICAL_ROWS_AFTER": len(bridge_rows) if canonical_patched else len(canonical_rows),
        "BRIDGE_ROWS": len(bridge_rows),
        "SCORABLE_BRIDGE_ROWS": len(scorable_rows),
        "EXCLUDED_SUPERSEDED_CWMU_LEGACY_ROWS": len(excluded_rows),
        "OFFICIAL_SCORE_KEY_V2_PRESENT_IN_CANONICAL": True,
        "BLANK_OFFICIAL_SCORE_KEY_V2_ROWS": len(blank_key_rows),
        "DUPLICATE_OFFICIAL_SCORE_KEY_V2_GROUPS": len(duplicate_rows),
        "CWMU_BLIND_EMBED_STATUS": "ALREADY_EMBEDDED" if already_embedded else "EMBEDDED",
        "CWMU_BLIND_LOCK_MANIFEST": str(CWMU_LOCK),
        "ORIGINAL_CANONICAL_SHA256": original_hash,
        "PATCHED_CANONICAL_SHA256": patched_hash,
        "CANONICAL_BACKUP": backup_path,
        "CANONICAL_PATCHED": canonical_patched,
        "DATABASE_PATCHED": False,
        "PREDICTION_OUTPUTS_READ": False,
        "PREDICTION_OUTPUTS_PATCHED": False,
        "COMMIT_CREATED": False,
        "PUSH_PERFORMED": False,
        "BRIDGE_STATUS": "PASS_FULL_YEAR_OFFICIAL_SCORE_KEY_V2_BRIDGE" if not duplicate_rows and not blank_key_rows else "PASS_WITH_REVIEW_REQUIRED",
    }
    status_path.write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    manifest = [
        "# 2018 Full-Year official_score_key_v2 Bridge Manifest",
        "",
        f"YEAR_PAIR={YEAR_PAIR}",
        f"AUDIT_TIMESTAMP={stamp}",
        f"CANONICAL_FILE={CANONICAL}",
        f"CWMU_BLIND_KEYED_TRUTH={CWMU_KEYED}",
        f"CWMU_BLIND_LOCK_MANIFEST={CWMU_LOCK}",
        "KEY_RECIPE=target_year|source_family|draw_system_type|draw_pool_key|hunt_code|score_scope|residency|points|probability_metric",
        "TARGET_YEAR_RULE=model_target_year=2019 for 2018_PERMITS=2019_MODEL",
        "MATRIX_DESCRIPTOR_COLUMNS=hunt_type,species,hunt_class,draw_pool,sex_type,weapon_type,hunt_code,boundary_id",
        "PREDICTION_OUTPUTS_READ=FALSE",
        "DATABASE_PATCHED=FALSE",
        "",
        "## Counts",
        "",
        f"CANONICAL_ROWS_BEFORE={status['CANONICAL_ROWS_BEFORE']}",
        f"CWMU_BLIND_ROWS_AVAILABLE={status['CWMU_BLIND_ROWS_AVAILABLE']}",
        f"CWMU_BLIND_ROWS_EMBEDDED_THIS_RUN={status['CWMU_BLIND_ROWS_EMBEDDED_THIS_RUN']}",
        f"CWMU_BOUNDARY_ID_BACKFILLED_FROM_CANONICAL_LEGACY_ROWS={status['CWMU_BOUNDARY_ID_BACKFILLED_FROM_CANONICAL_LEGACY_ROWS']}",
        f"CWMU_BOUNDARY_ID_STILL_BLANK_ROWS={status['CWMU_BOUNDARY_ID_STILL_BLANK_ROWS']}",
        f"CANONICAL_ROWS_AFTER={status['CANONICAL_ROWS_AFTER']}",
        f"BRIDGE_ROWS={status['BRIDGE_ROWS']}",
        f"SCORABLE_BRIDGE_ROWS={status['SCORABLE_BRIDGE_ROWS']}",
        f"EXCLUDED_SUPERSEDED_CWMU_LEGACY_ROWS={status['EXCLUDED_SUPERSEDED_CWMU_LEGACY_ROWS']}",
        f"BLANK_OFFICIAL_SCORE_KEY_V2_ROWS={status['BLANK_OFFICIAL_SCORE_KEY_V2_ROWS']}",
        f"DUPLICATE_OFFICIAL_SCORE_KEY_V2_GROUPS={status['DUPLICATE_OFFICIAL_SCORE_KEY_V2_GROUPS']}",
        "",
        "## Outputs",
        "",
        f"BRIDGE={bridge_path}",
        f"KEY_AUDIT={key_audit_path}",
        f"DUPLICATES={duplicate_path}",
        f"CWMU_EMBED_AUDIT={embed_path}",
        f"CWMU_BOUNDARY_ID_GAPS={boundary_gap_path}",
        f"CWMU_BOUNDARY_ID_REPAIR_AUDIT={boundary_repair_path}",
        f"STATUS={status_path}",
        "",
        "## Hashes",
        "",
        f"ORIGINAL_CANONICAL_SHA256={original_hash}",
        f"PATCHED_CANONICAL_SHA256={patched_hash}",
        f"BRIDGE_SHA256={sha256(bridge_path)}",
        f"CWMU_BOUNDARY_ID_GAPS_SHA256={sha256(boundary_gap_path)}",
        f"CWMU_BOUNDARY_ID_REPAIR_AUDIT_SHA256={sha256(boundary_repair_path)}",
        f"CWMU_BLIND_KEYED_SHA256={sha256(CWMU_KEYED)}",
        "",
        f"BRIDGE_STATUS={status['BRIDGE_STATUS']}",
    ]
    manifest_path.write_text("\n".join(manifest) + "\n", encoding="utf-8")

    for key, value in status.items():
        print(f"{key}={str(value).upper() if isinstance(value, bool) else value}")
    print(f"BRIDGE_MANIFEST={manifest_path}")
    print(f"BRIDGE_FILE={bridge_path}")
    print(f"KEY_AUDIT={key_audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
