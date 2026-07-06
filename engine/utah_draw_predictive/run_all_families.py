"""Run Utah draw predictive families for a source-year/target-year pair."""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from engine.utah.current_year_allotments import apply_current_year_allotments_to_rows
from scripts.build_predictive_bonus_engine_v1 import (
    build_predictions as build_big_game_bonus_predictions,
    is_target_bonus_hunt as is_target_big_game_bonus_hunt,
    normalize_bonus_hunt_type as normalize_big_game_bonus_hunt_type,
)

from .bear import BEAR_DRAW_SYSTEM_TYPE, build_bear_bonus_predictions
from .calibration import (
    CALIBRATION_FAMILY,
    CALIBRATION_GUARDRAIL_VERSION,
    CALIBRATION_INTERCEPT,
    CALIBRATION_METHOD,
    CALIBRATION_SLOPE,
    apply_family_calibration,
)
from .classifier import classify_draw_system_type
from .taxonomy import effective_draw_design
from .dedicated_hunter import build_preference_dedicated_hunter_predictions
from .permit_accessors import target_permit_total
from .preference_antlerless import build_preference_antlerless_predictions
from .preference_general_deer import build_preference_general_deer_predictions
from .preference_ladder_normalizer import normalize_preference_ladder_rows
from .sportsman import build_sportsman_predictions
from .turkey import TURKEY_DRAW_SYSTEM_TYPE, YOUTH_TURKEY_DRAW_SYSTEM_TYPE, build_turkey_bonus_predictions, build_youth_turkey_predictions
from .youth import build_youth_predictions


REPO = Path(__file__).resolve().parents[2]
TRUTH_PATH = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
AUTHORITY_PATH = REPO / "data_truth" / "crosswalk_truth" / "normalized" / "hunt_code_crosswalk_authority_2020_2026.csv"
DATABASE_2026_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
MODELED_FAMILIES = (
    "preference_general_deer",
    "dedicated_hunter",
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
)
RUNTIME_MATERIALIZER_FAMILIES = (
    "bonus_le_big_game",
    "bonus_ple_big_game",
    "bonus_oil_big_game",
    "bonus_bear",
    "bonus_turkey",
    "youth_turkey",
    "youth_draw",
)
UNRELEASED_ACTUAL_HOLDOUT_FAMILIES = {
    "preference_antlerless_deer",
    "preference_antlerless_elk",
    "preference_doe_pronghorn",
}
BIG_GAME_BONUS_RUNTIME_FAMILIES = {
    "bonus_le_big_game",
    "bonus_ple_big_game",
    "bonus_oil_big_game",
}

AUTHORITY_TO_FAMILY = {
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER": "preference_general_deer",
    "PREFERENCE_DEDICATED_HUNTER_DEER": "preference_dedicated_hunter_deer",
    "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
    "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
    "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
}
PREFERENCE_DRAW_SYSTEM_TYPES = set(AUTHORITY_TO_FAMILY)
AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES = {
    "ANTLERLESS_ELK_CONTROL",
    "AVAILABILITY_ONLY",
    "BEAR_HARVEST_OBJECTIVE",
    "BEAR_PURSUIT_ONLY",
    "BEAR_RESTRICTED_PURSUIT",
    "COUGAR_LICENSE_BASED",
    "CWMU_PRIVATE_VOUCHER",
    "FURBEARER_TAG_OR_LICENSE_ONLY",
    "GUARANTEED_LIFETIME_PERMIT",
    "OTC_CAPPED",
    "OTC_UNLIMITED",
    "PRIVATE_LANDS_ONLY",
    "PTARMIGAN_FREE_AVAILABILITY",
    "REFERENCE_ONLY",
    "TURKEY_CONTROL_VOUCHER",
    "TURKEY_CWMU",
    "TURKEY_FALL_MANAGEMENT",
}


def _clean(value: object) -> str:
    return str(value or "").strip()


def _text(value: object) -> str:
    return str(value if value is not None else "").strip()


def _draw_system(row: Mapping[str, object]) -> str:
    return effective_draw_design(row)


def _hunt_class(row: Mapping[str, object]) -> str:
    """Effective hunt-class/qualifier label.

    hunt_class is the preferred qualifier field. Legacy hunt_draw_class and
    draw_class_type are intentionally not routing authority.
    """

    return _clean(row.get("hunt_class"))


def _to_int(value: object) -> int | None:
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(float(text))
    except Exception:
        return None


def _to_number(value: object) -> float:
    text = _clean(value).replace(",", "")
    if not text:
        return 0.0
    try:
        return float(text)
    except Exception:
        return 0.0


def _to_probability(value: object) -> float | None:
    text = _text(value).replace(",", "").replace("%", "")
    if text.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None
    if not text:
        return None
    try:
        number = float(text)
    except Exception:
        return None
    if number > 1.0 and number <= 100.0:
        number = number / 100.0
    if 0.0 <= number <= 1.0:
        return number
    return None


def _family_prediction_status(
    family: str,
    rows: Sequence[Mapping[str, object]],
    report: Mapping[str, object] | None = None,
) -> tuple[str, str]:
    if rows:
        return "PASS", ""
    if family == "youth_turkey":
        observed_history = _to_int((report or {}).get("youth_turkey_rows_seen_observed_history")) or 0
        if observed_history <= 0:
            return "CLASSIFIED", "SOURCE_NOT_AVAILABLE_NO_PROVEN_YOUTH_TURKEY_HISTORY"
    return "FAIL", "NO_ROWS"


def _best_number(row: Mapping[str, object], *fields: str) -> float:
    for field in fields:
        value = _to_number(row.get(field))
        if value > 0:
            return value
    return 0.0


def _row_year(row: Mapping[str, object]) -> int | None:
    for key in ("actual_draw_year", "source_year", "draw_year", "year"):
        value = _to_int(row.get(key))
        if value is not None:
            return value
    return None


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _read_runtime_database_rows() -> list[dict[str, str]]:
    if not DATABASE_2026_PATH.exists():
        return []
    return apply_current_year_allotments_to_rows(_read_csv(DATABASE_2026_PATH))


def _joined_lower(row: Mapping[str, object], *fields: str) -> str:
    return " ".join(_clean(row.get(field)).lower() for field in fields)


BIG_GAME_BONUS_DB_DRAW_SYSTEM_TYPES = {
    "MAX_WEIGHTED_SPLIT",
    "BONUS_LE_BIG_GAME",
    "BONUS_PLE_BIG_GAME",
    "BONUS_OIL_BIG_GAME",
}
BIG_GAME_BONUS_EXCLUDED_TOKENS = (
    "cwmu",
    "conservation",
    "sportsman",
    "expo",
    "private land",
    "private-land",
    "private lands",
    "landowner",
    "voucher",
    "lifetime license",
    "guaranteed lifetime",
    "guaranteed permit",
    "tribal",
    "over the counter",
    " o.t.c",
    " otc",
    "availability",
    "remaining permit",
)


def _is_public_big_game_bonus_db_row(row: Mapping[str, object]) -> bool:
    draw_system_type = _draw_system(row).upper()
    classified_draw_system_type = classify_draw_system_type(row)
    if draw_system_type not in BIG_GAME_BONUS_DB_DRAW_SYSTEM_TYPES and classified_draw_system_type not in {
        "BONUS_LE_BIG_GAME",
        "BONUS_PLE_BIG_GAME",
        "BONUS_OIL_BIG_GAME",
    }:
        return False
    text = _joined_lower(row, "hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool", "draw_system_type")
    if any(token in text for token in BIG_GAME_BONUS_EXCLUDED_TOKENS):
        return False
    if _clean(row.get("hunt_code")).upper().startswith(("BR", "TK", "CG")):
        return False
    return (
        classified_draw_system_type in {"BONUS_LE_BIG_GAME", "BONUS_PLE_BIG_GAME", "BONUS_OIL_BIG_GAME"}
        or is_target_big_game_bonus_hunt(_clean(row.get("hunt_type")))
    )


def _big_game_bonus_db_by_code(db_rows: Sequence[Mapping[str, object]]) -> dict[str, dict[str, object]]:
    out: dict[str, dict[str, object]] = {}
    for row in db_rows:
        if not _is_public_big_game_bonus_db_row(row):
            continue
        hunt_code = _clean(row.get("hunt_code")).upper()
        if hunt_code:
            out[hunt_code] = dict(row)
    return out


def _prepare_big_game_bonus_history_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    prepared: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        if not _clean(item.get("year")):
            for year_field in ("actual_draw_year", "source_year", "draw_year"):
                if _clean(item.get(year_field)):
                    item["year"] = _clean(item.get(year_field))
                    break
        if not _clean(item.get("draw_pool")):
            item["draw_pool"] = "standard"
        prepared.append(item)
    return prepared


def _draw_system_for_big_game_bonus_kind(kind: str) -> str:
    return {
        "LE": "BONUS_LE_BIG_GAME",
        "PLE": "BONUS_PLE_BIG_GAME",
        "OIL": "BONUS_OIL_BIG_GAME",
    }.get(kind.upper(), "BONUS_LE_BIG_GAME")


def _family_for_big_game_bonus_kind(kind: str) -> str:
    return {
        "LE": "bonus_le_big_game",
        "PLE": "bonus_ple_big_game",
        "OIL": "bonus_oil_big_game",
    }.get(kind.upper(), "bonus_le_big_game")


def _big_game_bonus_kind_for_db_row(row: Mapping[str, object], hunt_code: str) -> str:
    classified = classify_draw_system_type(row)
    if classified == "BONUS_PLE_BIG_GAME":
        return "PLE"
    if classified == "BONUS_OIL_BIG_GAME":
        return "OIL"
    if classified == "BONUS_LE_BIG_GAME":
        species = _clean(row.get("species")).lower()
        sex_type = _clean(row.get("sex_type")).lower()
        text = _joined_lower(row, "hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon")
        if species in {"bison", "mountain goat"}:
            return "OIL"
        if species == "moose" and not any(token in sex_type or token in text for token in ("antlerless", "cow")):
            return "OIL"
        if "bighorn" in species or "bighorn sheep" in text:
            if not any(token in sex_type or token in text for token in ("ewe", "antlerless")):
                return "OIL"
        return "LE"
    draw_system_type = _draw_system(row).upper()
    if draw_system_type == "BONUS_PLE_BIG_GAME":
        return "PLE"
    if draw_system_type == "BONUS_OIL_BIG_GAME":
        return "OIL"
    if draw_system_type == "BONUS_LE_BIG_GAME":
        return "LE"
    species = _clean(row.get("species")).lower()
    sex_type = _clean(row.get("sex_type")).lower()
    text = _joined_lower(row, "hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon")
    if species in {"bison", "mountain goat"}:
        return "OIL"
    if species == "moose" and not any(token in sex_type or token in text for token in ("antlerless", "cow")):
        return "OIL"
    if "bighorn" in species or "bighorn sheep" in text:
        if not any(token in sex_type or token in text for token in ("ewe", "antlerless")):
            return "OIL"
    return "PLE" if hunt_code in {"DB0009", "DB1000", "DB1001", "DB1002", "DB1003", "DB1004", "DB1005", "DB1006", "DB1007", "DB1008"} else "LE"


def _split_big_game_bonus_rows(rows: Sequence[Mapping[str, object]], db_by_code: Mapping[str, Mapping[str, object]]) -> dict[str, list[dict[str, object]]]:
    split: dict[str, list[dict[str, object]]] = {
        "bonus_le_big_game": [],
        "bonus_ple_big_game": [],
        "bonus_oil_big_game": [],
    }
    for row in rows:
        item = dict(row)
        hunt_code = _clean(item.get("hunt_code")).upper()
        db_row = db_by_code.get(hunt_code, {})
        raw_hunt_type = _clean(db_row.get("hunt_type") or item.get("hunt_type"))
        normalized_hunt_type = normalize_big_game_bonus_hunt_type(raw_hunt_type, hunt_code)
        kind = _big_game_bonus_kind_for_db_row(db_row, hunt_code)
        family = _family_for_big_game_bonus_kind(kind)
        item["hunt_type"] = normalized_hunt_type
        item["draw_system_type"] = _draw_system_for_big_game_bonus_kind(kind)
        item["engine_family"] = item["draw_system_type"]
        item["algorithm_status"] = "MODELED_BONUS" if _clean(item.get("p_draw_mean")) else "IN_SCOPE_MODEL_PENDING"
        item["model_strategy"] = _clean(item.get("model_strategy")) or "generic_big_game_bonus"
        item["bonus_big_game_kind"] = kind
        split[family].append(item)
    return split


@lru_cache(maxsize=1)
def _crosswalk_authority_by_year_code() -> dict[tuple[int, str], dict[str, str]]:
    if not AUTHORITY_PATH.exists():
        return {}

    priority = {
        "GUIDEBOOK_AUTHORITY": 0,
        "SOURCE_BACKED": 1,
        "SOURCE_BACKED_NOT_IN_LEGACY_CROSSWALK": 2,
        "AUDIT_DERIVED": 3,
    }
    authority: dict[tuple[int, str], dict[str, str]] = {}
    with AUTHORITY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            hunt_code = _clean(raw.get("hunt_code")).upper()
            draw_system_type = _clean(raw.get("draw_system_type")).upper()
            if not hunt_code or not draw_system_type:
                continue
            year = None
            for year_field in ("source_year", "actual_draw_year", "hunt_year"):
                year = _to_int(raw.get(year_field))
                if year is not None:
                    break
            if year is None:
                continue
            key = (year, hunt_code)
            current = authority.get(key)
            if current is None or priority.get(_clean(raw.get("authority_status")).upper(), 99) < priority.get(
                _clean(current.get("authority_status")).upper(),
                99,
            ):
                authority[key] = dict(raw)
    return authority


def _authority_row_for_legacy_row(row: Mapping[str, object]) -> dict[str, str] | None:
    hunt_code = _clean(row.get("hunt_code")).upper()
    year = _row_year(row)
    if not hunt_code or year is None:
        return None
    return _crosswalk_authority_by_year_code().get((year, hunt_code))


def _authority_family_for_legacy_row(row: Mapping[str, object]) -> str | None:
    authority = _authority_row_for_legacy_row(row)
    if not authority:
        return None
    draw_system_type = _clean(authority.get("draw_system_type")).upper()
    if draw_system_type in AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES:
        return ""
    return AUTHORITY_TO_FAMILY.get(draw_system_type)


def _authority_draw_system_type_for_legacy_row(row: Mapping[str, object]) -> str:
    authority = _authority_row_for_legacy_row(row)
    return _clean(authority.get("draw_system_type")).upper() if authority else ""


def _fieldnames(rows: Sequence[Mapping[str, object]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields or ["no_rows"]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _family_for_legacy_row(row: Mapping[str, object]) -> str:
    draw_system_type = _draw_system(row).upper()
    if draw_system_type in AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES:
        return ""
    if draw_system_type in AUTHORITY_TO_FAMILY:
        return AUTHORITY_TO_FAMILY[draw_system_type]

    authority_family = _authority_family_for_legacy_row(row)
    if authority_family is not None:
        return authority_family

    model_strategy = _clean(row.get("model_strategy"))
    hunt_code = _clean(row.get("hunt_code")).upper()
    if draw_system_type in {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL"}:
        return ""
    if model_strategy in {
        "preference_general_deer",
        "preference_antlerless_deer",
        "preference_antlerless_elk",
        "preference_doe_pronghorn",
        "preference_dedicated_hunter_deer",
    }:
        return model_strategy
    if model_strategy == "preference_antlerless":
        return {
            "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
            "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
            "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
        }.get(draw_system_type, "")
    if model_strategy == "preference_dedicated_hunter_deer":
        return "preference_dedicated_hunter_deer"
    if draw_system_type:
        mapped_draw_system = {
            "PREFERENCE_GENERAL_SEASON_BUCK_DEER": "preference_general_deer",
            "PREFERENCE_DEDICATED_HUNTER_DEER": "preference_dedicated_hunter_deer",
            "PREFERENCE_ANTLERLESS_DEER": "preference_antlerless_deer",
            "PREFERENCE_ANTLERLESS_ELK": "preference_antlerless_elk",
            "PREFERENCE_DOE_PRONGHORN": "preference_doe_pronghorn",
        }.get(draw_system_type, "")
        if mapped_draw_system:
            return mapped_draw_system

    hunt_class = _hunt_class(row).upper()
    effective_hunt_class = hunt_class
    species = _clean(row.get("species")).lower()
    sex_type = _clean(row.get("sex_type")).lower()
    hunt_type = _clean(row.get("hunt_type")).lower()
    draw_system = _draw_system(row)
    draw_system_lower = draw_system.lower()
    is_preference = draw_system_lower == "preference" or draw_system.upper() in PREFERENCE_DRAW_SYSTEM_TYPES or hunt_class == "PREFERENCE"
    if not is_preference:
        return ""
    if effective_hunt_class == "GENERAL_SEASON_DEER" and species == "deer" and hunt_code.startswith("DB") and not hunt_code.startswith(("DB17", "DB18")):
        if str(row.get("draw_system_type") or "").strip().upper() == "REFERENCE_ONLY":
            return ""
    if str(row.get("draw_design") or "").strip().upper() == "REFERENCE_ONLY":
        return ""
    if str(row.get("hunt_class") or row.get("hunt_draw_class") or "").strip().upper() in {"LIFETIME_DEER", "LIFETIME_GENERAL_SEASON_DEER", "LIFETIME_GS_DEER"}:
        return ""
    return "preference_general_deer"
    if hunt_code.startswith(("DB15", "DB16")) and species == "deer":
        return "preference_general_deer"
    if effective_hunt_class == "DEDICATED_HUNTER_DEER" and species == "deer" and sex_type == "buck":
        return "preference_dedicated_hunter_deer"
    if effective_hunt_class == "ANTLERLESS_DEER" and species == "deer":
        return "preference_antlerless_deer"
    if effective_hunt_class == "ANTLERLESS_ELK" and species == "elk":
        return "preference_antlerless_elk"
    if effective_hunt_class == "DOE_PRONGHORN" and species == "pronghorn":
        return "preference_doe_pronghorn"
    if hunt_code.startswith("DA") and species == "deer":
        return "preference_antlerless_deer"
    if hunt_code.startswith("EA") and species == "elk":
        return "preference_antlerless_elk"
    if hunt_code.startswith("PD") and species == "pronghorn":
        return "preference_doe_pronghorn"
    if "dedicated hunter" in hunt_type and species == "deer" and sex_type == "buck":
        return "preference_dedicated_hunter_deer"
    return ""


def _family_match(row: Mapping[str, object], family: str) -> bool:
    legacy_family = _family_for_legacy_row(row)
    if family == "dedicated_hunter":
        return legacy_family == "preference_dedicated_hunter_deer"
    return legacy_family == family


def _draw_system_for_family(family: str) -> str:
    return {
        "bonus_bear": BEAR_DRAW_SYSTEM_TYPE,
        "bonus_le_big_game": "BONUS_LE_BIG_GAME",
        "bonus_oil_big_game": "BONUS_OIL_BIG_GAME",
        "bonus_ple_big_game": "BONUS_PLE_BIG_GAME",
        "bonus_turkey": TURKEY_DRAW_SYSTEM_TYPE,
        "preference_general_deer": "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
        "preference_dedicated_hunter_deer": "PREFERENCE_DEDICATED_HUNTER_DEER",
        "preference_antlerless_deer": "PREFERENCE_ANTLERLESS_DEER",
        "preference_antlerless_elk": "PREFERENCE_ANTLERLESS_ELK",
        "preference_doe_pronghorn": "PREFERENCE_DOE_PRONGHORN",
        "youth_turkey": YOUTH_TURKEY_DRAW_SYSTEM_TYPE,
    }.get(family, "")


def _runner_strategy_for_family(family: str) -> str:
    if family in {"preference_antlerless_deer", "preference_antlerless_elk", "preference_doe_pronghorn"}:
        return "preference_antlerless"
    return family


def _render_odds_text(probability: float) -> str:
    if probability <= 0:
        return "No modeled chance"
    capped = min(1.0, max(0.0, probability))
    pct = capped * 100.0
    if capped >= 0.999:
        return f"~1 in 1 or {pct:.1f}%"
    denominator = 1.0 / capped
    denominator_text = f"{denominator:.1f}".rstrip("0").rstrip(".") if denominator < 10 else str(round(denominator))
    pct_text = f"{pct:.1f}".rstrip("0").rstrip(".")
    return f"~1 in {denominator_text} or {pct_text}%"


def _apply_antlerless_deer_production_calibration(
    rows: Iterable[Mapping[str, object]],
    *,
    enabled: bool = False,
    mode: str = "off",
    calibrate_family: str = CALIBRATION_FAMILY,
) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        out.append(item)
        if not enabled:
            continue
        if mode != "production":
            raise ValueError("Antlerless Deer calibration can only write active probabilities in production mode.")
        raw_value = _clean(item.get("p_draw") or item.get("p_preference_draw") or item.get("p_draw_mean"))
        raw_probability = _to_probability(raw_value)
        calibrated = apply_family_calibration(
            item,
            raw_value,
            enabled=True,
            mode=mode,
            calibrate_family=calibrate_family,
        )
        calibrated_probability = _to_probability(calibrated)
        family_matches = _clean(item.get("draw_system_type")).upper() == CALIBRATION_FAMILY

        item["p_draw_raw"] = raw_value
        item["p_draw_calibrated"] = "" if calibrated_probability is None else f"{calibrated_probability:.6f}"
        item["calibration_family"] = CALIBRATION_FAMILY if family_matches else ""
        item["calibration_method"] = CALIBRATION_METHOD if family_matches else ""
        item["calibration_applied"] = (
            "true"
            if family_matches
            and raw_probability is not None
            and calibrated_probability is not None
            and raw_probability > 0
            and calibrated_probability != raw_probability
            else "false"
        )
        item["calibration_zero_preserved"] = (
            "true"
            if family_matches
            and raw_probability is not None
            and raw_probability <= 0
            and calibrated_probability == 0.0
            else "false"
        )
        item["calibration_intercept"] = CALIBRATION_INTERCEPT if family_matches else ""
        item["calibration_slope"] = CALIBRATION_SLOPE if family_matches else ""
        item["calibration_guardrail_version"] = CALIBRATION_GUARDRAIL_VERSION if family_matches else ""

        if not family_matches or calibrated_probability is None:
            continue

        item["p_draw"] = f"{calibrated_probability:.6f}"
        item["p_preference_draw"] = f"{calibrated_probability:.6f}"
        item["p_draw_mean"] = f"{calibrated_probability:.6f}"
        item["p_draw_p10"] = f"{max(0.0, calibrated_probability - 0.05):.6f}"
        item["p_draw_p50"] = f"{calibrated_probability:.6f}"
        item["p_draw_p90"] = f"{min(1.0, calibrated_probability + 0.05):.6f}"
        item["p_draw_pct"] = f"{calibrated_probability * 100.0:.3f}"
        item["display_odds_pct"] = f"{calibrated_probability * 100.0:.3f}"
        item["display_odds_text"] = _render_odds_text(calibrated_probability)
    return out


def _family_draw_system(family: str) -> str:
    if family == "sportsman":
        return "SPORTSMAN_RANDOM_ONLY"
    if family == "dedicated_hunter":
        return "PREFERENCE_DEDICATED_HUNTER_DEER"
    return _draw_system_for_family(family)


def _source_backed_family_for_row(row: Mapping[str, object]) -> str:
    hunt_code = _clean(row.get("hunt_code")).upper()
    prefix = "".join(ch for ch in hunt_code if ch.isalpha())
    species = _clean(row.get("species")).lower()
    text = _joined_lower(row, "hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_design", "draw_pool", "source_file")
    draw_system = _draw_system(row).upper()

    if "youth" in text:
        return "youth_draw"
    if prefix == "BR" or "black bear" in text:
        return "bonus_bear"
    if prefix == "CG" or "cougar" in species or "mountain lion" in text:
        return "cougar"
    if "turkey" in species or prefix == "TK":
        return "youth_turkey" if "youth" in text else "bonus_turkey"
    if prefix in {"DA"}:
        return "preference_antlerless_deer"
    if prefix in {"EA"}:
        return "preference_antlerless_elk"
    if prefix in {"PD"}:
        return "preference_doe_pronghorn"
    if prefix in {"PB"}:
        return "bonus_ple_big_game"
    if prefix in {"BI", "GO", "MA", "MB", "RE", "RS", "DS"}:
        return "bonus_oil_big_game"
    if prefix in {"EB", "EL", "LO", "LP"}:
        return "bonus_le_big_game"
    if prefix == "DB":
        if draw_system in {"MAX_WEIGHTED_SPLIT", "BONUS_LE_BIG_GAME", "BONUS_CWMU_BIG_GAME"} or "limited entry" in text or "cwmu" in text:
            return "bonus_le_big_game"
        if "deer" in species and "buck" in text:
            return "preference_general_deer"
    return ""


def _source_backed_probability_values(row: Mapping[str, object]) -> list[tuple[str, float]]:
    if _clean(row.get("residency")):
        probability = _to_probability(row.get("p_draw") or row.get("p_draw_percent") or row.get("success_ratio"))
        if probability is None and _to_number(row.get("eligible_applicants")) == 0:
            probability = 0.0
        if probability is None:
            return []
        return [(_clean(row.get("residency")), probability)]

    values: list[tuple[str, float]] = []
    for residency, fields, eligible_field in (
        ("Resident", ("resident_p_draw", "resident_p_draw_percent", "resident_success_ratio"), "resident_eligible_applicants"),
        ("Nonresident", ("nonresident_p_draw", "nonresident_p_draw_percent", "nonresident_success_ratio"), "nonresident_eligible_applicants"),
    ):
        probability = None
        for field in fields:
            probability = _to_probability(row.get(field))
            if probability is not None:
                break
        if probability is None and _to_number(row.get(eligible_field)) == 0:
            probability = 0.0
        if probability is not None:
            values.append((residency, probability))
    return values


def _source_backed_probability_rows(
    source_rows: Sequence[Mapping[str, object]],
    modeled: Mapping[str, Sequence[Mapping[str, object]]],
    source_year: int,
    target_year: int,
) -> dict[str, list[dict[str, object]]]:
    existing_keys = {
        (
            family,
            _clean(row.get("hunt_code")).upper(),
            _metric_scope_for_residency(row.get("residency") or row.get("metric_scope")),
            _text(row.get("points")),
        )
        for family, rows in modeled.items()
        for row in rows
        if _clean(row.get("hunt_code"))
    }
    rows_by_family: dict[str, list[dict[str, object]]] = defaultdict(list)
    added_keys: set[tuple[str, str, str, str]] = set()

    for source_row in source_rows:
        if "POINT" not in _clean(source_row.get("record_type") or source_row.get("row_type")).upper():
            continue
        family = _source_backed_family_for_row(source_row)
        if not family:
            continue
        hunt_code = _clean(source_row.get("hunt_code")).upper()
        points = _text(source_row.get("points"))
        if not hunt_code or not points:
            continue
        for residency, probability in _source_backed_probability_values(source_row):
            metric_scope = _metric_scope_for_residency(residency)
            key = (family, hunt_code, metric_scope, points)
            if key in existing_keys or key in added_keys:
                continue
            added_keys.add(key)
            rows_by_family[family].append(
                {
                    "model_version": "source_backed_roll_forward_v1",
                    "rule_version": "published_point_probability_roll_forward_v1",
                    "year": str(target_year),
                    "forecast_year": str(target_year),
                    "hunt_code": hunt_code,
                    "hunt_name": _clean(source_row.get("hunt_name")),
                    "species": _clean(source_row.get("species")),
                    "sex_type": _clean(source_row.get("sex_type")),
                    "hunt_type": _clean(source_row.get("hunt_type")),
                    "hunt_class": _clean(source_row.get("hunt_class")) or ("CWMU" if "cwmu" in _joined_lower(source_row, "hunt_type", "hunt_name", "source_file") else ""),
                    "residency": residency,
                    "points": points,
                    "draw_pool": _effective_draw_pool_for_family(source_row, family),
                    "public_permits_2025": _clean(source_row.get("total_permits") or source_row.get("resident_total_permits") or source_row.get("nonresident_total_permits")),
                    "public_permits_2026": _clean(source_row.get("total_permits") or source_row.get("resident_total_permits") or source_row.get("nonresident_total_permits")),
                    "p_preference_draw": f"{probability:.6f}" if family.startswith("preference_") else "",
                    "p_bonus_pool": "" if family.startswith("preference_") else f"{probability:.6f}",
                    "p_random_pool": "",
                    "p_draw": f"{probability:.6f}",
                    "p_bonus_pool_pct": "" if family.startswith("preference_") else f"{probability * 100.0:.3f}",
                    "p_random_pool_pct": "",
                    "p_draw_pct": f"{probability * 100.0:.3f}",
                    "p_draw_mean": f"{probability:.6f}",
                    "p_draw_p10": f"{max(0.0, probability - 0.05):.6f}",
                    "p_draw_p50": f"{probability:.6f}",
                    "p_draw_p90": f"{min(1.0, probability + 0.05):.6f}",
                    "display_odds_pct": f"{probability * 100.0:.3f}",
                    "display_odds_text": _render_odds_text(probability),
                    "draw_outlook": _render_odds_text(probability),
                    "source_years_used": str(source_year),
                    "source_year_count": "1",
                    "latest_source_year": str(source_year),
                    "earliest_source_year": str(source_year),
                    "source_dataset": "predictive",
                    "model_strategy": f"{family}_source_backed_roll_forward",
                    "reason_codes": "SOURCE_BACKED_PUBLISHED_POINT_PROBABILITY_ROLL_FORWARD",
                    "weapon": _clean(source_row.get("weapon")),
                    "source_file": _clean(source_row.get("source_file") or source_row.get("draw_source_file") or source_row.get("source_scope")),
                    "source_year": str(source_year),
                    "target_year": str(target_year),
                    "prediction_year": str(target_year),
                    "family": family,
                    "draw_system_type": _family_draw_system(family) or _draw_system(source_row),
                    "engine_family": _family_draw_system(family) or _draw_system(source_row),
                    "metric_scope": metric_scope,
                    "draw_method": _default_draw_method_for_family(family),
                    "point_system": _default_point_system_for_family(family),
                    "algorithm_status": "MODELED_SOURCE_BACKED_ROLL_FORWARD",
                    "prediction_status": "MODELED",
                    "classification_status": "MODELED_SOURCE_BACKED_ROLL_FORWARD",
                    "public_permits_target": _clean(source_row.get("total_permits") or source_row.get("resident_total_permits") or source_row.get("nonresident_total_permits")),
                    "public_permits_source": f"source_year_{source_year}_published_point_probability",
                }
            )
    return rows_by_family


def _engine_family_for_row(family: str, row: Mapping[str, object]) -> str:
    if family == "sportsman":
        return "SPORTSMAN_RANDOM_ONLY"
    if family == "youth_draw":
        return _draw_system(row) or "YOUTH_DRAW"
    return _draw_system(row) or _family_draw_system(family) or family


def _default_draw_method_for_family(family: str) -> str:
    if family == "sportsman":
        return "Strict random"
    if family == "youth_draw":
        return "Youth draw"
    if family in {"bonus_bear", "bonus_turkey", "youth_turkey", "bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}:
        return "Bonus"
    return "Preference"


def _default_point_system_for_family(family: str) -> str:
    if family == "sportsman":
        return "none"
    if family == "youth_draw":
        return "none"
    if family in {"bonus_bear", "bonus_turkey", "youth_turkey", "bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}:
        return "bonus"
    return "preference"


def _default_algorithm_status_for_family(family: str, row: Mapping[str, object]) -> str:
    existing = _clean(row.get("algorithm_status"))
    if existing:
        return existing
    has_probability = bool(_clean(row.get("p_draw") or row.get("p_preference_draw") or row.get("p_draw_mean")))
    if family == "sportsman":
        return "MODELED_SPORTSMAN_DRAW"
    if family == "youth_draw":
        return "MODELED_RANDOM_ONLY" if has_probability else "IN_SCOPE_MODEL_PENDING"
    if family in {"bonus_turkey", "youth_turkey", "bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}:
        return "MODELED_BONUS" if has_probability else "IN_SCOPE_MODEL_PENDING"
    if family == "bonus_bear":
        if has_probability:
            return "MODELED_BONUS"
        if _clean(row.get("p_availability") or row.get("availability_pct")):
            return "MODELED_AVAILABILITY"
        draw_outlook = _clean(row.get("draw_outlook")).upper()
        if "PENDING" in draw_outlook:
            return "IN_SCOPE_MODEL_PENDING"
        return "EXCLUDED_NOT_PREDICTIVE_DRAW"
    return "MODELED_PREFERENCE"


def _default_reason_code_for_family(family: str, algorithm_status: str) -> str:
    if family == "sportsman":
        return "FAMILY_ENGINE_MODELED_SPORTSMAN_RANDOM_ONLY"
    if family == "bonus_bear":
        return "FAMILY_ENGINE_BEAR_DRAW"
    if family in {"bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}:
        return f"FAMILY_ENGINE_MODELED_{_family_draw_system(family)}"
    if family == "bonus_turkey":
        return "FAMILY_ENGINE_MODELED_TURKEY_BONUS"
    if family == "youth_turkey":
        return "FAMILY_ENGINE_MODELED_YOUTH_TURKEY_SET_ASIDE"
    if family == "youth_draw":
        return "FAMILY_ENGINE_YOUTH_DRAW"
    if algorithm_status == "MODELED_PREFERENCE":
        return "FAMILY_ENGINE_MODELED_PREFERENCE"
    return algorithm_status


def _effective_draw_pool_for_family(row: Mapping[str, object], family: str) -> str:
    draw_pool = _clean(row.get("draw_pool"))
    if draw_pool and draw_pool.lower() != "standard":
        return draw_pool
    return {
        "sportsman": "sportsman_random_only",
        "bonus_bear": "black_bear",
        "bonus_le_big_game": "max_weighted_split",
        "bonus_ple_big_game": "max_weighted_split",
        "bonus_oil_big_game": "max_weighted_split",
        "bonus_turkey": "preference_point",
        "youth_turkey": "youth_turkey",
        "youth_draw": "youth_general_any_bull_elk",
        "preference_general_deer": "adult_general_deer",
        "dedicated_hunter": "dedicated_hunter",
        "preference_dedicated_hunter_deer": "dedicated_hunter",
        "preference_antlerless_deer": "general_season_antlerless_deer",
        "preference_antlerless_elk": "general_season_antlerless_elk",
        "preference_doe_pronghorn": "general_season_doe_pronghorn",
    }.get(family, draw_pool or "standard")


def _metric_scope_for_residency(value: object) -> str:
    text = _clean(value).lower().replace("-", "").replace("_", "").replace(" ", "")
    if text in {"resident", "res", "r"}:
        return "resident"
    if text in {"nonresident", "nonres", "nr", "n"}:
        return "nonresident"
    return "total"


def _aggregate_target_permits(rows: Sequence[Mapping[str, object]]) -> dict[tuple[str, str, str], dict[str, float]]:
    aggregates: dict[tuple[str, str, str], dict[str, float]] = {}
    seen_point_rows: set[tuple[str, str, str, str]] = set()
    for row in rows:
        family = _family_for_legacy_row(row)
        hunt_code = _clean(row.get("hunt_code")).upper()
        draw_pool = _effective_draw_pool_for_family(row, family)
        points = _clean(row.get("points"))
        if not family or not hunt_code or (family, hunt_code, draw_pool, points) in seen_point_rows:
            continue
        seen_point_rows.add((family, hunt_code, draw_pool, points))
        key = (family, hunt_code, draw_pool)
        aggregate = aggregates.setdefault(key, {"res": 0.0, "nr": 0.0, "total": 0.0})
        res = _best_number(row, "resident_regular_permits", "resident_total_permits")
        nr = _best_number(row, "nonresident_regular_permits", "nonresident_total_permits")
        total = _best_number(row, "total_regular_permits", "total_permits")
        aggregate["res"] += res
        aggregate["nr"] += nr
        aggregate["total"] += total if total > 0 else res + nr
    return aggregates


def _with_historical_target_metadata(
    rows: Sequence[Mapping[str, object]],
    source_year: int,
    target_year: int,
) -> list[dict[str, object]]:
    aggregates = _aggregate_target_permits(rows)
    enriched: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        family = _family_for_legacy_row(item)
        hunt_code = _clean(item.get("hunt_code")).upper()
        draw_pool = _effective_draw_pool_for_family(item, family)
        if not family or not hunt_code:
            authority_draw_system_type = _authority_draw_system_type_for_legacy_row(item)
            if authority_draw_system_type:
                item["draw_system_type"] = authority_draw_system_type
                item["authority_excluded_from_public_draw_odds"] = str(
                    authority_draw_system_type in AUTHORITY_EXCLUDED_DRAW_SYSTEM_TYPES
                ).upper()
            enriched.append(item)
            continue

        draw_system_type = _draw_system_for_family(family)
        aggregate = aggregates.get((family, hunt_code, draw_pool), {})
        item["model_strategy"] = _runner_strategy_for_family(family)
        item["draw_system_type"] = draw_system_type
        item["preference_model_valid"] = "TRUE"
        item["target_permits_total"] = int(round(aggregate.get("total", 0.0)))
        item["target_permits_res"] = int(round(aggregate.get("res", 0.0)))
        item["target_permits_nr"] = int(round(aggregate.get("nr", 0.0)))
        item["target_permits_source"] = (
            f"source_year_{source_year}_split_truth_columns_for_target_{target_year}"
        )
        item["source_column_mapping"] = (
            "resident_regular_permits|resident_total_permits|"
            "nonresident_regular_permits|nonresident_total_permits|"
            "total_regular_permits|total_permits"
        )
        if family == "preference_dedicated_hunter_deer":
            item["draw_pool"] = draw_pool
            item["weapon"] = "Any Legal Weapon"
            item["hunt_type"] = "General Season"
            item["hunt_class"] = "Dedicated Hunter"
            item["sex_type"] = "Buck"
        elif family == "preference_general_deer":
            item["draw_pool"] = draw_pool
            item["hunt_type"] = "General Season"
            item["sex_type"] = "Buck"
            if not _clean(item.get("hunt_class")):
                item["hunt_class"] = "GENERAL_SEASON_DEER"
        elif family in {"preference_antlerless_deer", "preference_antlerless_elk", "preference_doe_pronghorn"}:
            item["draw_pool"] = draw_pool
            item["hunt_type"] = _clean(item.get("hunt_type")) or "General Season"
            item["sex_type"] = "Doe" if family == "preference_doe_pronghorn" else "Antlerless"
        elif not _clean(item.get("draw_pool")):
            item["draw_pool"] = "standard"
        enriched.append(item)
    return enriched


def _with_run_fields(rows: Iterable[Mapping[str, object]], source_year: int, target_year: int, family: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for row in rows:
        item = dict(row)
        is_sportsman = family == "sportsman"
        item["source_year"] = source_year
        item["target_year"] = target_year
        item["prediction_year"] = target_year
        item["family"] = family
        item["draw_system_type"] = _family_draw_system(family) or _draw_system(item)
        item["engine_family"] = _engine_family_for_row(family, item)
        if "draw_design" in item:
            item["draw_design"] = item["draw_system_type"]
        item["draw_pool"] = _effective_draw_pool_for_family(item, family)
        item["metric_scope"] = _clean(item.get("metric_scope")) or _metric_scope_for_residency(item.get("residency"))
        item["draw_method"] = _clean(item.get("draw_method")) or _default_draw_method_for_family(family)
        item["point_system"] = _clean(item.get("point_system")) or _default_point_system_for_family(family)
        item["algorithm_status"] = _default_algorithm_status_for_family(family, item)
        item["prediction_status"] = _clean(item.get("prediction_status")) or "MODELED"
        item["classification_status"] = _clean(item.get("classification_status")) or item["algorithm_status"]
        item["reason_codes"] = _clean(item.get("reason_codes")) or _default_reason_code_for_family(family, item["algorithm_status"])
        status_text = _joined_lower(item, "algorithm_status", "classification_status", "reason_codes", "data_quality_flags", "bear_bonus_note", "turkey_bonus_note")
        if (
            family in {"bonus_bear", "bonus_turkey"}
            and not _clean(item.get("p_draw") or item.get("p_draw_mean") or item.get("p_bonus_pool") or item.get("p_random_pool"))
            and any(
                token in status_text
                for token in (
                    "no_public_draw_probability",
                    "missing_forecast_quota",
                    "missing proven",
                    "missing_proven",
                    "missing_latest",
                    "missing_multiple_years",
                    "low_applicant_count",
                )
            )
        ):
            item["algorithm_status"] = "SOURCE_DATA_INCOMPLETE_NO_PUBLIC_DRAW_PROBABILITY"
            item["classification_status"] = item["algorithm_status"]
            item["prediction_status"] = "NOT_SCORED"
        probability_source = _clean(item.get("p_draw") or item.get("p_preference_draw") or item.get("p_draw_mean"))
        if probability_source:
            probability = _to_number(probability_source)
            item["p_draw_mean"] = _clean(item.get("p_draw_mean")) or f"{probability:.6f}"
            item["p_draw_p10"] = _clean(item.get("p_draw_p10")) or f"{probability if is_sportsman else max(0.0, probability - 0.05):.6f}"
            item["p_draw_p50"] = _clean(item.get("p_draw_p50")) or f"{probability:.6f}"
            item["p_draw_p90"] = _clean(item.get("p_draw_p90")) or f"{probability if is_sportsman else min(1.0, probability + 0.05):.6f}"
            item["display_odds_pct"] = _clean(item.get("display_odds_pct")) or f"{probability * 100.0:.3f}"
            item["display_odds_text"] = _clean(item.get("display_odds_text")) or (_clean(item.get("sportsman_odds_text")) if is_sportsman else _render_odds_text(probability))
        item["public_permits_target"] = _clean(item.get("public_permits_target")) or _clean(item.get("public_permits_2026"))
        item["public_permits_source"] = _clean(item.get("public_permits_source")) or (
            f"source_year_{source_year}_sportsman_raw_draw_results" if is_sportsman else f"source_year_{source_year}_split_truth_columns_for_target_{target_year}"
        )
        out.append(item)
    return out


def _sample_values(rows: Sequence[Mapping[str, object]], key: str, limit: int = 5) -> str:
    values: list[str] = []
    for row in rows:
        value = _clean(row.get(key))
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def _sample_columns_present(rows: Sequence[Mapping[str, object]], limit: int = 24) -> str:
    columns: list[str] = []
    for row in rows[:25]:
        for key, value in row.items():
            if key not in columns and _clean(value):
                columns.append(key)
            if len(columns) >= limit:
                return ";".join(columns)
    return ";".join(columns)


def _sample_hunt_draw_class(rows: Sequence[Mapping[str, object]], limit: int = 5) -> str:
    values: list[str] = []
    for row in rows:
        value = "|".join(
            part
            for part in (
                _clean(row.get("hunt_class")),
                _clean(row.get("draw_design")),
                _clean(row.get("hunt_type")),
                _clean(row.get("sex_type")),
            )
            if part
        )
        if value and value not in values:
            values.append(value)
        if len(values) >= limit:
            break
    return ";".join(values)


def _trace_row(
    source_year: int,
    target_year: int,
    family: str,
    stage: str,
    rows_before: int,
    rows_after: int,
    sample_rows: Sequence[Mapping[str, object]],
    blocker: str = "",
    notes: str = "",
) -> dict[str, object]:
    return {
        "source_year": source_year,
        "target_year": target_year,
        "family": family,
        "stage": stage,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "dropped_rows": max(rows_before - rows_after, 0),
        "blocker": blocker,
        "sample_hunt_codes": _sample_values(sample_rows, "hunt_code"),
        "sample_source_years": _sample_values(sample_rows, "source_year"),
        "sample_actual_draw_years": _sample_values(sample_rows, "actual_draw_year"),
        "sample_hunt_draw_class": _sample_hunt_draw_class(sample_rows),
        "sample_source_dataset": _sample_values(sample_rows, "source_dataset"),
        "sample_columns_present": _sample_columns_present(sample_rows),
        "notes": notes,
    }


def _family_rows(rows: Sequence[Mapping[str, object]], family: str) -> list[dict[str, object]]:
    return [dict(row) for row in rows if _family_match(row, family)]


def _normalized_family_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return normalize_preference_ladder_rows(rows)


def _permit_ok_rows(rows: Sequence[Mapping[str, object]], target_year: int, source_year: int) -> list[dict[str, object]]:
    return [dict(row) for row in rows if target_permit_total(row, target_year, source_year=source_year).value > 0]


def _joined_target_rows(
    target_rows: Sequence[Mapping[str, object]],
    normalized_rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    source_codes = {_clean(row.get("hunt_code")).upper() for row in normalized_rows if _clean(row.get("hunt_code"))}
    return [dict(row) for row in target_rows if _clean(row.get("hunt_code")).upper() in source_codes]


def _prefix_family_guess(row: Mapping[str, object]) -> str:
    # REFERENCE_ONLY_PREFIX_GUARD_FORCE
    draw_system_type = str(row.get("draw_system_type") or "").strip().upper()
    draw_design = str(row.get("draw_design") or "").strip().upper()
    hunt_class = str(row.get("hunt_class") or row.get("hunt_draw_class") or "").strip().upper()
    if draw_system_type == "REFERENCE_ONLY" or draw_design == "REFERENCE_ONLY":
        return ""
    if hunt_class in {"LIFETIME_DEER", "LIFETIME_GENERAL_SEASON_DEER", "LIFETIME_GS_DEER"}:
        return ""
    # END_REFERENCE_ONLY_PREFIX_GUARD_FORCE
    if _draw_system(row).upper() in {"REFERENCE_ONLY", "AVAILABILITY_ONLY", "TRIBAL"}:
        return ""
    hunt_code = _clean(row.get("hunt_code")).upper()
    species = _clean(row.get("species")).lower()
    draw_design = _draw_system(row).lower()
    hunt_class = _clean(row.get("hunt_class")).upper()
    if draw_design != "preference" and draw_design.upper() not in PREFERENCE_DRAW_SYSTEM_TYPES and hunt_class != "PREFERENCE":
        return ""
    if hunt_code.startswith(("DB15", "DB16")) and species == "deer":
        return "preference_general_deer"
    if hunt_code.startswith(("DB17", "DB18")) and species == "deer":
        return "dedicated_hunter"
    if hunt_code.startswith("DA") and species == "deer":
        return "preference_antlerless_deer"
    if hunt_code.startswith("EA") and species == "elk":
        return "preference_antlerless_elk"
    if hunt_code.startswith("PD") and species == "pronghorn":
        return "preference_doe_pronghorn"
    return ""


def _census_rows(
    rows: Sequence[Mapping[str, object]],
    source_year: int,
    target_year: int,
    census_type: str,
) -> list[dict[str, object]]:
    grouped: dict[tuple[str, str, str, str, str, str, str, str], dict[str, object]] = {}
    for row in rows:
        family = _family_for_legacy_row(row) or _prefix_family_guess(row) or "unclassified"
        key = (
            family,
            _clean(row.get("hunt_code")).upper()[:2],
            _clean(row.get("hunt_class")),
            _clean(row.get("draw_design")),
            _clean(row.get("species")),
            _clean(row.get("sex_type")),
            _clean(row.get("hunt_type")),
            _clean(row.get("source_dataset")),
        )
        item = grouped.setdefault(
            key,
            {
                "source_year": source_year,
                "target_year": target_year,
                "census_type": census_type,
                "family": family,
                "hunt_code_prefix": key[1],
                "hunt_class": key[2],
                "draw_design": key[3],
                "species": key[4],
                "sex_type": key[5],
                "hunt_type": key[6],
                "source_dataset": key[7],
                "row_count": 0,
                "sample_hunt_codes": [],
            },
        )
        item["row_count"] = int(item["row_count"]) + 1
        sample = item["sample_hunt_codes"]
        hunt_code = _clean(row.get("hunt_code")).upper()
        if hunt_code and hunt_code not in sample and len(sample) < 5:
            sample.append(hunt_code)
    out: list[dict[str, object]] = []
    for item in grouped.values():
        item = dict(item)
        item["sample_hunt_codes"] = ";".join(item["sample_hunt_codes"])
        out.append(item)
    return sorted(out, key=lambda row: (str(row["family"]), str(row["hunt_code_prefix"]), str(row["hunt_class"]), str(row["sex_type"])))


def _family_filter_diagnosis_rows(
    source_year: int,
    target_year: int,
    source_rows: Sequence[Mapping[str, object]],
    engine_rows: Sequence[Mapping[str, object]],
    family_metrics: Mapping[str, Mapping[str, object]],
    modeled: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for family in MODELED_FAMILIES:
        prefix_rows = [row for row in source_rows if _prefix_family_guess(row) == family]
        mapped_rows = _family_rows(source_rows, family)
        metrics = family_metrics.get(family, {})
        prediction_rows = modeled.get(family, [])
        if prediction_rows:
            diagnosis = "PASS"
        elif prefix_rows and not mapped_rows:
            diagnosis = "LEGACY_LABEL_MAPPING_GAP"
        elif mapped_rows and not metrics.get("permit_rows"):
            diagnosis = "NO_TARGET_PERMITS"
        elif mapped_rows and not metrics.get("joined_rows"):
            diagnosis = "NO_SOURCE_TARGET_JOIN"
        else:
            diagnosis = "NO_SOURCE_FAMILY_ROWS"
        rows.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "source_rows": len(mapped_rows),
                "prefix_candidate_rows": len(prefix_rows),
                "normalized_ladder_rows": len(metrics.get("normalized_rows", [])),
                "target_rows": len(metrics.get("family_target_rows", [])),
                "permit_accessor_rows_ok": len(metrics.get("permit_rows", [])),
                "joined_source_target_rows": len(metrics.get("joined_rows", [])),
                "prediction_rows": len(prediction_rows),
                "diagnosis": diagnosis,
                "sample_prefix_hunt_codes": _sample_values(prefix_rows, "hunt_code"),
                "sample_mapped_hunt_codes": _sample_values(mapped_rows, "hunt_code"),
                "notes": (
                    "2021 source labels can encode family by hunt-code prefix while hunt_class/sex_type are generic."
                    if source_year == 2021
                    else ""
                ),
            }
        )
    return rows


def _runtime_authority_source_status(
    source_year: int,
    target_year: int,
    family: str,
    source_file: str,
    permit_source_field: str,
) -> tuple[bool, bool, str]:
    if family not in BIG_GAME_BONUS_RUNTIME_FAMILIES:
        source_year_authority = source_year == 2026 and (
            "2026" in source_file or permit_source_field.startswith("permits_2026")
        )
        current_authority = (
            target_year != 2026
            and not source_year_authority
            and ("2026" in source_file or permit_source_field.startswith("permits_2026"))
        )
        return current_authority, current_authority, "not_runtime_bonus_authority"

    if not source_file and not permit_source_field:
        return False, False, "no_authority_source_field"

    normalized_source = source_file.replace("\\", "/").lower()
    is_runtime_authority = (
        "pipeline/raw/hunt_unit_database/2026/csv/database.csv" in normalized_source
        or "dwrapps.utah.gov/huntboundary/hunttabledata" in normalized_source
        or permit_source_field.startswith("permits_2026")
    )
    if is_runtime_authority:
        return True, False, "published_permit_authority_allowed_for_runtime_forecast"

    current_authority = target_year != 2026 and "2026" in source_file
    return current_authority, current_authority, "unknown_authority_source_review_required" if current_authority else "no_current_authority_source"


def _leakage_row(source_year: int, target_year: int, family: str, rows: Sequence[Mapping[str, object]]) -> dict[str, object]:
    future_year_detected = False
    current_year_authority_file_used = False
    hardcoded_2026_field_required = False
    authority_source_statuses: set[str] = set()
    source_years_used: set[str] = set()

    for row in rows:
        for part in _clean(row.get("source_years_used")).split(","):
            part = part.strip()
            if not part:
                continue
            source_years_used.add(part)
            year = _to_int(part)
            if year is not None and year > source_year:
                future_year_detected = True
        source_file = _clean(row.get("source_file") or row.get("quota_source_file") or row.get("permit_allotment_2026_source_file"))
        permit_source_field = _clean(row.get("permit_source_field"))
        current_authority, hardcoded_authority, authority_status = _runtime_authority_source_status(
            source_year,
            target_year,
            family,
            source_file,
            permit_source_field,
        )
        authority_source_statuses.add(authority_status)
        if current_authority:
            current_year_authority_file_used = True
        if target_year != 2026 and hardcoded_authority:
            hardcoded_2026_field_required = True

    leakage_status = "FAIL" if future_year_detected or hardcoded_2026_field_required else "PASS"
    return {
        "source_year": source_year,
        "target_year": target_year,
        "family": family,
        "source_years_used": ";".join(sorted(source_years_used)),
        "future_year_detected": str(future_year_detected).lower(),
        "current_year_authority_file_used": str(current_year_authority_file_used).lower(),
        "hardcoded_2026_field_required": str(hardcoded_2026_field_required).lower(),
        "authority_source_status": ";".join(sorted(authority_source_statuses)),
        "leakage_status": leakage_status,
    }


def run_all_families(
    source_year: int,
    target_year: int,
    audit_dir: Path,
    truth_path: Path = TRUTH_PATH,
    *,
    enable_antlerless_deer_calibration: bool = False,
    calibration_mode: str = "off",
    calibrate_family: str = CALIBRATION_FAMILY,
) -> dict[str, object]:
    if enable_antlerless_deer_calibration and (
        calibration_mode != "production" or _clean(calibrate_family).upper() != CALIBRATION_FAMILY
    ):
        raise ValueError(
            "Active calibration requires --calibration-mode production and "
            "--calibrate-family PREFERENCE_ANTLERLESS_DEER."
        )
    all_truth_rows = _read_csv(truth_path)
    source_rows = [row for row in all_truth_rows if _row_year(row) == source_year]
    engine_rows = _with_historical_target_metadata(source_rows, source_year, target_year)
    first_year_bootstrap = source_year == 2017 and target_year == 2018
    if first_year_bootstrap and source_rows:
        history_years = [source_year]
    else:
        history_years = list(range(2018, source_year + 1))
    history_year_set = set(history_years)
    history_rows = [row for row in all_truth_rows if (_row_year(row) or 0) in history_year_set]
    history_engine_rows = _with_historical_target_metadata(history_rows, source_year, target_year)
    limited_history = len(history_years) <= 1
    runtime_db_rows = _read_runtime_database_rows()
    runtime_history_years = history_years
    runtime_truth_rows = [row for row in all_truth_rows if (_row_year(row) or 0) in set(runtime_history_years)]
    big_game_bonus_db_by_code = _big_game_bonus_db_by_code(runtime_db_rows)
    big_game_bonus_raw_rows, big_game_bonus_audit_rows = build_big_game_bonus_predictions(
        history_rows=_prepare_big_game_bonus_history_rows(runtime_truth_rows),
        db_by_code=big_game_bonus_db_by_code,
        prediction_year=target_year,
        iterations=1,
        seed=20260701,
    )
    big_game_bonus_rows_by_family = {
        family: _with_run_fields(rows, source_year, target_year, family)
        for family, rows in _split_big_game_bonus_rows(big_game_bonus_raw_rows, big_game_bonus_db_by_code).items()
    }
    for rows in big_game_bonus_rows_by_family.values():
        for row in rows:
            row["source_years_used"] = _clean(row.get("source_years_used")) or ",".join(str(year) for year in runtime_history_years)

    general_rows = _with_run_fields(
        build_preference_general_deer_predictions(history_engine_rows, engine_rows, target_year, history_years),
        source_year,
        target_year,
        "preference_general_deer",
    )
    antlerless_all = build_preference_antlerless_predictions(history_engine_rows, engine_rows, target_year, history_years)
    antlerless_deer_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_ANTLERLESS_DEER"],
        source_year,
        target_year,
        "preference_antlerless_deer",
    )
    antlerless_elk_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_ANTLERLESS_ELK"],
        source_year,
        target_year,
        "preference_antlerless_elk",
    )
    doe_pronghorn_rows = _with_run_fields(
        [row for row in antlerless_all if row.get("draw_system_type") == "PREFERENCE_DOE_PRONGHORN"],
        source_year,
        target_year,
        "preference_doe_pronghorn",
    )
    dedicated_rows = _with_run_fields(
        build_preference_dedicated_hunter_predictions(history_engine_rows, engine_rows, target_year, history_years),
        source_year,
        target_year,
        "dedicated_hunter",
    )
    sportsman_rows, sportsman_report = build_sportsman_predictions(history_engine_rows, engine_rows, target_year, history_years)
    sportsman_rows = _with_run_fields(sportsman_rows, source_year, target_year, "sportsman")
    bear_rows, bear_report = build_bear_bonus_predictions(runtime_truth_rows, runtime_db_rows, target_year, runtime_history_years)
    bear_rows = _with_run_fields(bear_rows, source_year, target_year, "bonus_bear")
    turkey_rows, turkey_report = build_turkey_bonus_predictions(runtime_truth_rows, runtime_db_rows, target_year, runtime_history_years)
    turkey_rows = _with_run_fields(turkey_rows, source_year, target_year, "bonus_turkey")
    youth_turkey_rows, youth_turkey_report = build_youth_turkey_predictions(runtime_truth_rows, runtime_db_rows, target_year, runtime_history_years)
    youth_turkey_rows = _with_run_fields(youth_turkey_rows, source_year, target_year, "youth_turkey")
    youth_rows, youth_report = build_youth_predictions(runtime_truth_rows, runtime_db_rows, target_year, runtime_history_years)
    youth_rows = _with_run_fields(youth_rows, source_year, target_year, "youth_draw")

    modeled = {
        "bonus_le_big_game": big_game_bonus_rows_by_family["bonus_le_big_game"],
        "bonus_ple_big_game": big_game_bonus_rows_by_family["bonus_ple_big_game"],
        "bonus_oil_big_game": big_game_bonus_rows_by_family["bonus_oil_big_game"],
        "preference_general_deer": general_rows,
        "dedicated_hunter": dedicated_rows,
        "preference_antlerless_deer": antlerless_deer_rows,
        "preference_antlerless_elk": antlerless_elk_rows,
        "preference_doe_pronghorn": doe_pronghorn_rows,
        "sportsman": sportsman_rows,
        "bonus_bear": bear_rows,
        "bonus_turkey": turkey_rows,
        "youth_turkey": youth_turkey_rows,
        "youth_draw": youth_rows,
    }
    source_backed_rows_by_family = _source_backed_probability_rows(source_rows, modeled, source_year, target_year)
    for family, source_backed_rows in source_backed_rows_by_family.items():
        if not source_backed_rows:
            continue
        modeled.setdefault(family, [])
        modeled[family].extend(source_backed_rows)
    modeled["preference_antlerless_deer"] = _apply_antlerless_deer_production_calibration(
        modeled["preference_antlerless_deer"],
        enabled=enable_antlerless_deer_calibration,
        mode=calibration_mode,
        calibrate_family=calibrate_family,
    )
    runtime_family_reports = {
        "bonus_le_big_game": {
            "forecast_year": target_year,
            "source_years": runtime_history_years,
            "big_game_bonus_db_rows": len(big_game_bonus_db_by_code),
            "big_game_bonus_audit_rows": len(big_game_bonus_audit_rows),
            "prediction_rows": len(modeled["bonus_le_big_game"]),
            "source_backed_roll_forward_rows": len(source_backed_rows_by_family.get("bonus_le_big_game", [])),
            "draw_system_type": "BONUS_LE_BIG_GAME",
        },
        "bonus_ple_big_game": {
            "forecast_year": target_year,
            "source_years": runtime_history_years,
            "big_game_bonus_db_rows": len(big_game_bonus_db_by_code),
            "big_game_bonus_audit_rows": len(big_game_bonus_audit_rows),
            "prediction_rows": len(modeled["bonus_ple_big_game"]),
            "source_backed_roll_forward_rows": len(source_backed_rows_by_family.get("bonus_ple_big_game", [])),
            "draw_system_type": "BONUS_PLE_BIG_GAME",
        },
        "bonus_oil_big_game": {
            "forecast_year": target_year,
            "source_years": runtime_history_years,
            "big_game_bonus_db_rows": len(big_game_bonus_db_by_code),
            "big_game_bonus_audit_rows": len(big_game_bonus_audit_rows),
            "prediction_rows": len(modeled["bonus_oil_big_game"]),
            "source_backed_roll_forward_rows": len(source_backed_rows_by_family.get("bonus_oil_big_game", [])),
            "draw_system_type": "BONUS_OIL_BIG_GAME",
        },
        "sportsman": sportsman_report,
        "bonus_bear": bear_report,
        "bonus_turkey": turkey_report,
        "youth_turkey": youth_turkey_report,
        "youth_draw": youth_report,
    }
    deferred_families: dict[str, str] = {}

    audit_dir.mkdir(parents=True, exist_ok=True)
    run_metadata = {
        "source_year": source_year,
        "target_year": target_year,
        "truth_path": str(truth_path),
        "first_year_bootstrap": first_year_bootstrap,
        "limited_history": limited_history,
        "source_years_available": history_years,
        "source_rows": len(source_rows),
        "history_rows": len(history_rows),
        "calibration_applied": bool(enable_antlerless_deer_calibration),
        "calibration_mode": calibration_mode,
        "calibrate_family": calibrate_family,
    }
    (audit_dir / "run_metadata.json").write_text(json.dumps(run_metadata, indent=2), encoding="utf-8")
    predictions_dir = audit_dir / "predictions"
    counts: list[dict[str, object]] = []
    leakage: list[dict[str, object]] = []
    trace: list[dict[str, object]] = []
    all_prediction_rows: list[dict[str, object]] = []
    family_metrics: dict[str, dict[str, object]] = {}

    for family in MODELED_FAMILIES:
        family_truth_rows = _family_rows(history_rows, family)
        normalized_rows = _normalized_family_rows(family_truth_rows)
        family_target_rows = _family_rows(engine_rows, family)
        permit_rows = _permit_ok_rows(family_target_rows, target_year, source_year)
        joined_rows = _joined_target_rows(permit_rows, normalized_rows)
        prediction_rows = modeled.get(family, [])
        blocker = "" if prediction_rows else "NO_ROWS"
        family_metrics[family] = {
            "family_truth_rows": family_truth_rows,
            "normalized_rows": normalized_rows,
            "family_target_rows": family_target_rows,
            "permit_rows": permit_rows,
            "joined_rows": joined_rows,
        }
        trace.extend(
            [
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_truth_rows",
                    0,
                    len(all_truth_rows),
                    all_truth_rows,
                    notes=f"Loaded truth file {truth_path}",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_history_year_rows",
                    len(all_truth_rows),
                    len(history_rows),
                    history_rows,
                    blocker="" if history_rows else "NO_HISTORY_YEAR_ROWS",
                    notes=f"All-prior/source history window: {','.join(str(year) for year in history_years)}",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_family_truth_rows",
                    len(history_rows),
                    len(family_truth_rows),
                    family_truth_rows,
                    blocker="" if family_truth_rows else "NO_FAMILY_SOURCE_ROWS",
                    notes="Uses model_strategy/draw_system_type when present; otherwise legacy hunt_class/species/draw_design mapping.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "normalize_ladder_rows",
                    len(family_truth_rows),
                    len(normalized_rows),
                    normalized_rows,
                    blocker="" if normalized_rows else "NO_NORMALIZED_LADDER_ROWS",
                    notes="Uses split resident/nonresident eligible, permit, and p_draw columns; no eligibility default.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_target_rows",
                    0,
                    len(engine_rows),
                    engine_rows,
                    notes="Historical target rows are in-memory source rows enriched with target_permits_* from split truth columns.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_target_year_rows",
                    len(engine_rows),
                    len(engine_rows),
                    engine_rows,
                    notes="No future target-year authority required for historical validation.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "filter_family_target_rows",
                    len(engine_rows),
                    len(family_target_rows),
                    family_target_rows,
                    blocker="" if family_target_rows else "NO_FAMILY_TARGET_ROWS",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "permit_accessor_rows_ok",
                    len(family_target_rows),
                    len(permit_rows),
                    permit_rows,
                    blocker="" if permit_rows else "NO_TARGET_PERMITS",
                    notes="Uses target_permits_* or source-year fields through target-year-aware accessor; no 2026 requirement for non-2026 targets.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "join_source_to_target",
                    len(permit_rows),
                    len(joined_rows),
                    joined_rows,
                    blocker="" if joined_rows else "NO_SOURCE_TARGET_CODE_JOIN",
                    notes="Joined by hunt_code after normalization.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "build_predictions",
                    len(joined_rows),
                    len(prediction_rows),
                    prediction_rows,
                    blocker=blocker,
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "write_family_output",
                    len(prediction_rows),
                    len(prediction_rows),
                    prediction_rows,
                    blocker=blocker,
                ),
            ]
        )

    family_metrics["sportsman"] = {
        "family_truth_rows": sportsman_rows,
        "normalized_rows": sportsman_rows,
        "family_target_rows": sportsman_rows,
        "permit_rows": sportsman_rows,
        "joined_rows": sportsman_rows,
    }
    for family in RUNTIME_MATERIALIZER_FAMILIES:
        rows = modeled.get(family, [])
        family_metrics[family] = {
            "family_truth_rows": [
                dict(row)
                for row in runtime_truth_rows
                if (
                    _draw_system(row) == _family_draw_system(family)
                    or (
                        family in {"bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"}
                        and _clean(row.get("hunt_code")).upper() in big_game_bonus_db_by_code
                    )
                )
            ],
            "normalized_rows": rows,
            "family_target_rows": runtime_db_rows,
            "permit_rows": rows,
            "joined_rows": rows,
        }

    trace.extend(
        [
            _trace_row(
                source_year,
                target_year,
                "sportsman",
                "load_historical_sportsman_source",
                0,
                len(sportsman_rows),
                sportsman_rows,
                blocker="" if sportsman_rows else "NO_SPORTSMAN_SOURCE_ROWS",
                notes=(
                    "Sportsman uses resident-only random draw results from yearly raw Sportsman sources. "
                    f"Source report: {sportsman_report.get('sportsman_source_year')}; "
                    f"source code count: {sportsman_report.get('sportsman_source_code_count')}."
                ),
            ),
            _trace_row(
                source_year,
                target_year,
                "sportsman",
                "build_random_only_predictions",
                len(sportsman_rows),
                len(sportsman_rows),
                sportsman_rows,
                blocker="" if sportsman_rows else "NO_SPORTSMAN_PREDICTIONS",
                notes="p_sportsman_draw is resident_permit_count / eligible resident applicants; nonresident quota is always 0.",
            ),
        ]
    )
    for family in RUNTIME_MATERIALIZER_FAMILIES:
        rows = modeled.get(family, [])
        report = runtime_family_reports.get(family, {})
        status, blocker = _family_prediction_status(family, rows, report)
        trace.extend(
            [
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_runtime_target_database",
                    0,
                    len(big_game_bonus_db_by_code) if family in {"bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"} else len(runtime_db_rows),
                    list(big_game_bonus_db_by_code.values()) if family in {"bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"} else runtime_db_rows,
                    blocker="" if (big_game_bonus_db_by_code if family in {"bonus_le_big_game", "bonus_ple_big_game", "bonus_oil_big_game"} else runtime_db_rows) else "NO_RUNTIME_DATABASE_ROWS",
                    notes=f"Uses repo DATABASE.csv so rolling audit coverage matches runtime materializer family coverage. Report keys: {','.join(sorted(report.keys())[:12])}",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "load_runtime_history_window",
                    len(all_truth_rows),
                    len(runtime_truth_rows),
                    runtime_truth_rows,
                    blocker="" if runtime_truth_rows else "NO_RUNTIME_HISTORY_ROWS",
                    notes=f"Runtime family history years: {','.join(str(year) for year in runtime_history_years)}.",
                ),
                _trace_row(
                    source_year,
                    target_year,
                    family,
                    "build_runtime_materializer_family_predictions",
                    len(runtime_db_rows),
                    len(rows),
                    rows,
                    blocker=blocker,
                    notes="Family builder is shared with the runtime materializer; output remains audit-only in this harness.",
                ),
            ]
        )

    _write_csv(audit_dir / "source_truth_family_census.csv", _census_rows(history_rows, source_year, target_year, "all_prior_source_truth"))
    _write_csv(audit_dir / "target_family_census.csv", _census_rows(engine_rows, source_year, target_year, "target_rows"))
    _write_csv(
        audit_dir / "family_filter_diagnosis.csv",
        _family_filter_diagnosis_rows(source_year, target_year, history_rows, engine_rows, family_metrics, modeled),
    )

    for family, rows in modeled.items():
        output_path = predictions_dir / f"{source_year}_{target_year}_{family}.csv"
        _write_csv(output_path, rows)
        all_prediction_rows.extend(rows)
        metrics = family_metrics.get(family, {})
        status, blocker = _family_prediction_status(family, rows, runtime_family_reports.get(family, {}))
        intentional_holdout = (
            not rows
            and source_year >= 2026
            and target_year >= 2027
            and family in UNRELEASED_ACTUAL_HOLDOUT_FAMILIES
        )
        if intentional_holdout:
            status = "CLASSIFIED"
            blocker = "HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS"
        counts.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "readiness_status": "READY_TRUTH_AND_RAW_FILES",
                "input_truth_rows": len(metrics.get("family_truth_rows", [])),
                "current_target_rows": len(metrics.get("family_target_rows", [])),
                "normalized_ladder_rows": len(metrics.get("normalized_rows", [])),
                "permit_accessor_rows_ok": len(metrics.get("permit_rows", [])),
                "joined_source_target_rows": len(metrics.get("joined_rows", [])),
                "prediction_rows": len(rows),
                "output_path": str(output_path),
                "status": status,
                "blocker_if_failed": blocker,
            }
        )
        leakage.append(_leakage_row(source_year, target_year, family, rows))

    for family, report in runtime_family_reports.items():
        report_rows = [{"metric": key, "value": value} for key, value in sorted(report.items())]
        _write_csv(audit_dir / f"{family}_runtime_report.csv", report_rows)

    for family, reason in deferred_families.items():
        counts.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "readiness_status": reason.split(":", 1)[0],
                "input_truth_rows": 0,
                "current_target_rows": 0,
                "normalized_ladder_rows": "",
                "permit_accessor_rows_ok": "",
                "joined_source_target_rows": "",
                "prediction_rows": 0,
                "output_path": "",
                "status": "CLASSIFIED",
                "blocker_if_failed": reason,
            }
        )
        leakage.append(
            {
                "source_year": source_year,
                "target_year": target_year,
                "family": family,
                "source_years_used": str(source_year),
                "future_year_detected": "false",
                "current_year_authority_file_used": "false",
                "hardcoded_2026_field_required": "false",
                "leakage_status": "CLASSIFIED",
            }
        )

    _write_csv(audit_dir / "family_predictions.csv", all_prediction_rows)
    _write_csv(audit_dir / "all_year_family_prediction_counts.csv", counts)
    _write_csv(audit_dir / "per_family_year_prediction_counts.csv", counts)
    _write_csv(audit_dir / "leakage_check.csv", leakage)
    _write_csv(audit_dir / "zero_row_drop_trace.csv", trace)

    return {
        "source_year": source_year,
        "target_year": target_year,
        "audit_dir": str(audit_dir),
        "prediction_rows": len(all_prediction_rows),
        "family_counts": {family: len(rows) for family, rows in modeled.items()},
        "classified_families": deferred_families,
        "first_year_bootstrap": first_year_bootstrap,
        "limited_history": limited_history,
        "source_years_available": history_years,
        "antlerless_deer_calibration_enabled": enable_antlerless_deer_calibration,
        "antlerless_deer_calibration_mode": calibration_mode,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run all currently wired Utah predictive families for one target year.")
    parser.add_argument("--source-year", type=int, required=True)
    parser.add_argument("--target-year", type=int, required=True)
    parser.add_argument("--audit-dir", type=Path, required=True)
    parser.add_argument("--truth-path", type=Path, default=TRUTH_PATH)
    parser.add_argument("--enable-antlerless-deer-calibration", action="store_true")
    parser.add_argument("--calibration-mode", choices=["off", "production"], default="off")
    parser.add_argument("--calibrate-family", default=CALIBRATION_FAMILY)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_all_families(
        args.source_year,
        args.target_year,
        args.audit_dir,
        args.truth_path,
        enable_antlerless_deer_calibration=args.enable_antlerless_deer_calibration,
        calibration_mode=args.calibration_mode,
        calibrate_family=args.calibrate_family,
    )
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
