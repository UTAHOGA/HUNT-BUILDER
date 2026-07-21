#!/usr/bin/env python3
"""Build a score-key-v2 truth comparable from canonical truth and predictions.

This does not change canonical probabilities or counts. It uses the prediction
surface only as the public key vocabulary, then copies actual probabilities
from the canonical truth rows onto matching score-key-v2 rows.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REQUIRED_KEY_COLUMNS = [
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "official_score_key_v2",
]

PARENT_STYLE_DRAW_POOLS = {"max_weighted_split"}
SOURCE_PARTITIONED_FAMILIES = {
    "LE_BIG_GAME",
    "PLE_BIG_GAME",
    "OIL_BIG_GAME",
    "CWMU_BIG_GAME",
}
REBUILT_BUCKET_TO_FAMILY = {
    "ANTLERLESS_DEER": "ADULT_ANTLERLESS",
    "ANTLERLESS_ELK": "ADULT_ANTLERLESS",
    "ANTLERLESS_PRONGHORN": "ADULT_ANTLERLESS",
    "YOUTH_ANTLERLESS_DEER": "YOUTH_ANTLERLESS",
    "YOUTH_ANTLERLESS_ELK": "YOUTH_ANTLERLESS",
    "YOUTH_ANTLERLESS_PRONGHORN": "YOUTH_ANTLERLESS",
    "GENERAL_SEASON_DEER": "GENERAL_SEASON_DEER",
    "YOUTH_DEER": "YOUTH_GENERAL_SEASON_DEER",
    "DEDICATED_HUNTER_DEER": "DEDICATED_HUNTER_DEER",
    "YOUTH_DEDICATED_HUNTER_DEER": "YOUTH_DEDICATED_HUNTER_DEER",
    "LIFETIME_DEER": "LIFETIME_GENERAL_SEASON_DEER",
    "TURKEY": "TURKEY",
    "YOUTH_TURKEY": "TURKEY",
}
REBUILT_BUCKET_TO_DRAW = {
    "ANTLERLESS_DEER": ("PREFERENCE_ANTLERLESS_DEER", "general_season_antlerless_deer"),
    "ANTLERLESS_ELK": ("PREFERENCE_ANTLERLESS_ELK", "general_season_antlerless_elk"),
    "ANTLERLESS_PRONGHORN": ("PREFERENCE_DOE_PRONGHORN", "general_season_doe_pronghorn"),
    "YOUTH_ANTLERLESS_DEER": ("PREFERENCE_ANTLERLESS_DEER", "youth_antlerless_deer"),
    "YOUTH_ANTLERLESS_ELK": ("PREFERENCE_ANTLERLESS_ELK", "youth_antlerless_elk"),
    "YOUTH_ANTLERLESS_PRONGHORN": ("PREFERENCE_DOE_PRONGHORN", "youth_doe_pronghorn"),
    "GENERAL_SEASON_DEER": ("PREFERENCE_GENERAL_SEASON_BUCK_DEER", "adult_general_deer"),
    "DEDICATED_HUNTER_DEER": ("PREFERENCE_DEDICATED_HUNTER_DEER", "dedicated_hunter"),
    "TURKEY": ("BONUS_TURKEY", "preference_point"),
    "YOUTH_TURKEY": ("YOUTH_TURKEY_SET_ASIDE", "youth_turkey"),
}

def clean(value: Any) -> str:
    return "" if value is None else str(value).strip()


def upper(value: Any) -> str:
    return clean(value).upper()


def lower(value: Any) -> str:
    return clean(value).lower()


def pool_key_token(value: Any) -> str:
    text = lower(value)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text or "na"


def rebuilt_bucket(row: dict[str, str]) -> str:
    for token in clean(row.get("qa_notes")).split(";"):
        name, separator, value = token.strip().partition("=")
        if separator and name.strip().lower() == "rebuilt_bucket":
            return value.strip().upper()
    return ""


def is_cwmu_source_row(row: dict[str, str]) -> bool:
    text = " ".join(
        lower(row.get(field))
        for field in ("source_file", "draw_source_file", "source_pdf", "source_path", "hunt_type", "hunt_class", "hunt_name", "draw_pool")
    )
    return "cwmu" in text and not any(token in text for token in ("private", "landowner", "voucher"))


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    os.replace(tmp, path)


def normalize_points(value: Any) -> str:
    text = clean(value)
    if text == "":
        return ""
    try:
        number = float(text)
    except ValueError:
        return text.upper()
    if number.is_integer():
        return str(int(number))
    return text


def truth_target_year(row: dict[str, str]) -> str:
    return clean(row.get("target_year")) or clean(row.get("model_target_year"))


def normalized_score_scope(row: dict[str, str]) -> str:
    scope = upper(row.get("score_scope"))
    if scope:
        return scope
    residency = upper(row.get("residency")).replace("-", "").replace(" ", "")
    if residency in {"RESIDENT", "RES"}:
        return "RESIDENT"
    if residency in {"NONRESIDENT", "NONRES", "NR"}:
        return "NONRESIDENT"
    return "TOTAL"


def source_file_route(row: dict[str, str]) -> dict[str, str]:
    source_text = " ".join(
        clean(row.get(field)).lower().replace("\\", "/")
        for field in ("source_file", "draw_source_file", "source_pdf", "source_path")
    )
    compact = re.sub(r"[^a-z0-9]+", "_", source_text).strip("_")
    if not compact:
        return {}

    def route(source_family: str, draw_system_type: str, draw_pool: str) -> dict[str, str]:
        return {"source_family": source_family, "draw_system_type": draw_system_type, "draw_pool": draw_pool}

    if "cwmu" in compact:
        if "youth_antlerless_elk" in compact:
            draw_pool = "cwmu_youth_antlerless_elk"
        elif "youth_antlerless_deer" in compact:
            draw_pool = "cwmu_youth_antlerless_deer"
        elif "youth_antlerless_pronghorn" in compact or "youth_doe_pronghorn" in compact:
            draw_pool = "cwmu_youth_doe_pronghorn"
        elif "antlerless_elk" in compact:
            draw_pool = "cwmu_antlerless_elk"
        elif "antlerless_deer" in compact:
            draw_pool = "cwmu_antlerless_deer"
        elif "doe_pronghorn" in compact or "antlerless_pronghorn" in compact:
            draw_pool = "cwmu_doe_pronghorn"
        elif "deer_buck" in compact:
            draw_pool = "cwmu_big_game_deer_buck"
        elif "elk_bull" in compact:
            draw_pool = "cwmu_big_game_elk_bull"
        elif "pronghorn_buck" in compact:
            draw_pool = "cwmu_big_game_pronghorn_buck"
        elif "moose_bull" in compact:
            draw_pool = "cwmu_big_game_moose_bull"
        else:
            draw_pool = "cwmu_big_game"
        return route("CWMU_BIG_GAME", "BONUS_CWMU_BIG_GAME", draw_pool)
    if "sportsman" in compact:
        return route("SPORTSMAN", "SPORTSMAN_RANDOM_ONLY", "random")
    if "youth_turkey" in compact:
        return route("TURKEY", "YOUTH_TURKEY_SET_ASIDE", "youth_turkey")
    if "turkey" in compact:
        return route("TURKEY", "BONUS_TURKEY", "preference_point")
    if "black_bear" in compact or compact.endswith("bear_draw_results"):
        return route("BEAR_DRAW_RESULTS", "BLACK_BEAR", "black_bear")
    if "cougar" in compact:
        return route("COUGAR", "COUGAR", "cougar")
    if "youth_any_bull_elk" in compact:
        return route("YOUTH_ANY_BULL_ELK", "YOUTH_GENERAL_ANY_BULL_ELK", "youth_general_any_bull_elk")
    if "youth_d_h_deer" in compact or "youth_dedicated_hunter_deer" in compact:
        return route("YOUTH_DEDICATED_HUNTER_DEER", "PREFERENCE_DEDICATED_HUNTER_DEER", "youth_dedicated_hunter")
    if "d_h_deer" in compact or "dedicated_hunter_deer" in compact:
        return route("DEDICATED_HUNTER_DEER", "PREFERENCE_DEDICATED_HUNTER_DEER", "dedicated_hunter")
    if "youth_g_s_deer" in compact or "youth_general_deer" in compact:
        return route("YOUTH_GENERAL_SEASON_DEER", "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "youth_general_deer")
    if "lifetime_g_s_deer" in compact or "lifetime_general_deer" in compact:
        return route("LIFETIME_GENERAL_SEASON_DEER", "REFERENCE_ONLY", "lifetime_general_deer")
    if "g_s_buck_deer" in compact or "general_deer" in compact:
        return route("GENERAL_SEASON_DEER", "PREFERENCE_GENERAL_SEASON_BUCK_DEER", "adult_general_deer")
    if "youth_antlerless_elk" in compact:
        return route("YOUTH_ANTLERLESS", "PREFERENCE_ANTLERLESS_ELK", "youth_antlerless_elk")
    if "youth_antlerless_deer" in compact:
        return route("YOUTH_ANTLERLESS", "PREFERENCE_ANTLERLESS_DEER", "youth_antlerless_deer")
    if "youth_antlerless_pronghorn" in compact or "youth_doe_pronghorn" in compact:
        return route("YOUTH_ANTLERLESS", "PREFERENCE_DOE_PRONGHORN", "youth_doe_pronghorn")
    if "antlerless_elk" in compact:
        return route("ADULT_ANTLERLESS", "PREFERENCE_ANTLERLESS_ELK", "general_season_antlerless_elk")
    if "antlerless_deer" in compact:
        return route("ADULT_ANTLERLESS", "PREFERENCE_ANTLERLESS_DEER", "general_season_antlerless_deer")
    if "doe_pronghorn" in compact or "antlerless_pronghorn" in compact:
        return route("ADULT_ANTLERLESS", "PREFERENCE_DOE_PRONGHORN", "general_season_doe_pronghorn")
    if "p_l_e_deer" in compact or "premium_limited_entry_deer" in compact:
        return route("PLE_BIG_GAME", "BONUS_PLE_BIG_GAME", "max_weighted_split")
    if "management_deer" in compact or "cactus_deer" in compact:
        return route("LE_BIG_GAME", "BONUS_LE_BIG_GAME", "limited_entry_deer")
    if "l_e_elk" in compact or "limited_entry_elk" in compact:
        return route("LE_BIG_GAME", "BONUS_LE_BIG_GAME", "limited_entry_elk")
    if "l_e_deer" in compact or "limited_entry_deer" in compact:
        return route("LE_BIG_GAME", "BONUS_LE_BIG_GAME", "limited_entry_deer")
    if "l_e_pronghorn" in compact or "l_e_proghorn" in compact or "limited_entry_pronghorn" in compact:
        return route("LE_BIG_GAME", "BONUS_LE_BIG_GAME", "limited_entry_pronghorn")
    if "o_i_l" in compact or "once_in_a_lifetime" in compact:
        return route("OIL_BIG_GAME", "BONUS_OIL_BIG_GAME", "max_weighted_split")
    return {}


def comparable_source_family(row: dict[str, str]) -> str:
    if is_cwmu_source_row(row):
        return "CWMU_BIG_GAME"

    route = source_file_route(row)
    if route.get("source_family"):
        return route["source_family"]

    bucket_family = REBUILT_BUCKET_TO_FAMILY.get(rebuilt_bucket(row))
    if bucket_family:
        return bucket_family

    family = upper(row.get("source_family"))
    draw_system_type = upper(row.get("draw_system_type"))
    draw_pool = lower(row.get("draw_pool"))
    hunt_code = upper(row.get("hunt_code"))
    hunt_type = lower(row.get("hunt_type"))
    source_file = lower(row.get("source_file") or row.get("draw_source_file") or row.get("source_pdf"))
    text = " ".join(
        [
            draw_system_type.lower(),
            draw_pool,
            hunt_type,
            source_file,
            lower(row.get("hunt_name")),
            lower(row.get("species")),
            lower(row.get("hunt_class")),
            lower(row.get("hunt_draw_class")),
        ]
    )
    if draw_system_type == "SPORTSMAN_RANDOM_ONLY" or "sportsman" in text:
        return "SPORTSMAN"
    if draw_system_type == "BONUS_CWMU_BIG_GAME":
        if family == "YOUTH_ANTLERLESS" or draw_pool.startswith("youth_") or "youth" in source_file:
            return "YOUTH_ANTLERLESS"
        return "CWMU_BIG_GAME"
    if draw_system_type in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}:
        if "cwmu" in draw_pool or "cwmu" in hunt_type:
            return "CWMU_BIG_GAME"
        if draw_pool.startswith("youth_") or "youth" in source_file:
            return "YOUTH_ANTLERLESS"
        return "ADULT_ANTLERLESS"
    if family == "BLACK_BEAR" or hunt_code.startswith("BR") or "black bear" in text:
        return "BEAR_DRAW_RESULTS"
    if draw_system_type == "YOUTH_GENERAL_ANY_BULL_ELK":
        return "YOUTH_ANY_BULL_ELK"
    if "antlerless_moose" in draw_pool or "antlerless moose" in text or hunt_code.startswith("MA"):
        return "ADULT_ANTLERLESS"
    if hunt_code in {"DB1009", "DB1010"}:
        return "LE_BIG_GAME"
    if family == "BIG_GAME_DRAWING_ODDS":
        if draw_system_type == "BONUS_PLE_BIG_GAME":
            return "PLE_BIG_GAME"
        if draw_system_type == "BONUS_OIL_BIG_GAME":
            return "OIL_BIG_GAME"
        if draw_system_type == "BONUS_LE_BIG_GAME":
            return "LE_BIG_GAME"
    if draw_system_type == "BONUS_CWMU_BIG_GAME" and family == "ADULT_ANTLERLESS":
        return "CWMU_BIG_GAME"
    if family == "LE_BIG_GAME" and "premium" in hunt_type:
        return "PLE_BIG_GAME"
    if family:
        return family

    if draw_system_type in {"BLACK_BEAR", "BEAR_DRAW"} or "bear" in source_file:
        return "BEAR_DRAW_RESULTS"
    if "cougar" in source_file or "cougar" in text:
        return "COUGAR"
    if "turkey" in text:
        return "TURKEY"
    if draw_system_type == "PREFERENCE_GENERAL_SEASON_BUCK_DEER":
        if draw_pool == "youth_general_deer" or "youth" in source_file:
            return "YOUTH_GENERAL_SEASON_DEER"
        return "GENERAL_SEASON_DEER"
    if draw_system_type == "PREFERENCE_DEDICATED_HUNTER_DEER":
        if "youth_dedicated" in draw_pool or ("youth" in source_file and ("d.h" in source_file or "dedicated" in source_file)):
            return "YOUTH_DEDICATED_HUNTER_DEER"
        return "DEDICATED_HUNTER_DEER"
    if draw_system_type in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}:
        if "cwmu" in draw_pool or "cwmu" in hunt_type:
            return "CWMU_BIG_GAME"
        if draw_pool.startswith("youth_") or "youth" in source_file:
            return "YOUTH_ANTLERLESS"
        return "ADULT_ANTLERLESS"
    if draw_system_type in {"BONUS_ANTLERLESS_MOOSE"} or "antlerless_moose" in draw_pool:
        return "ADULT_ANTLERLESS"
    if draw_system_type == "REFERENCE_ONLY":
        if "lifetime" in draw_pool or "lifetime" in text:
            return "LIFETIME_GENERAL_SEASON_DEER"
        if "youth_general_deer" in draw_pool:
            return "YOUTH_GENERAL_SEASON_DEER"
        if "youth_dedicated" in draw_pool:
            return "YOUTH_DEDICATED_HUNTER_DEER"
        if draw_pool.startswith("youth_"):
            return "YOUTH_ANTLERLESS"
        if "cougar" in source_file:
            return "COUGAR"
    if draw_system_type in {"MAX_WEIGHTED_SPLIT", "BONUS_LE_BIG_GAME", "BONUS_PLE_BIG_GAME", "BONUS_OIL_BIG_GAME", "BONUS_CWMU_BIG_GAME"}:
        if "cwmu" in hunt_type or "cwmu" in draw_pool:
            return "CWMU_BIG_GAME"
        if "premium" in hunt_type or "p.l.e" in text or "ple" in source_file:
            return "PLE_BIG_GAME"
        if "once" in hunt_type or "o.i.l" in text or "oil" in source_file:
            return "OIL_BIG_GAME"
        if "bear" in source_file:
            return "BEAR_DRAW_RESULTS"
        return "LE_BIG_GAME"
    return family


def comparable_draw_system_type(row: dict[str, str]) -> str:
    route = source_file_route(row)
    if route.get("draw_system_type"):
        return route["draw_system_type"]
    bucket_draw = REBUILT_BUCKET_TO_DRAW.get(rebuilt_bucket(row))
    if bucket_draw:
        return bucket_draw[0]
    return clean(row.get("draw_system_type"))


def comparable_draw_pool(row: dict[str, str]) -> str:
    route = source_file_route(row)
    if route.get("draw_pool"):
        return route["draw_pool"]
    bucket_draw = REBUILT_BUCKET_TO_DRAW.get(rebuilt_bucket(row))
    if bucket_draw:
        return bucket_draw[1]
    return clean(row.get("draw_pool"))


def comparable_draw_pool_key(row: dict[str, str]) -> str:
    family = comparable_source_family(row)
    draw_pool = comparable_draw_pool(row)
    if family not in SOURCE_PARTITIONED_FAMILIES:
        return draw_pool
    draw_design = clean(row.get("draw_design") or comparable_draw_system_type(row))
    hunt_draw_class = clean(row.get("hunt_draw_class") or row.get("hunt_class"))
    parts = [
        ("design", draw_design),
        ("class", hunt_draw_class),
        ("pool", draw_pool),
        ("species", row.get("species")),
        ("hunt", row.get("hunt_type")),
        ("sex", row.get("sex_type")),
    ]
    return "__".join(f"{name}_{pool_key_token(value)}" for name, value in parts)


def truth_exclusion_reason(row: dict[str, str]) -> str:
    family = upper(row.get("source_family"))
    text = " ".join(
        lower(row.get(field))
        for field in ("source_family", "hunt_name", "hunt_type", "hunt_class", "hunt_draw_class", "draw_pool", "source_file")
    )
    if family == "LIFETIME_GENERAL_SEASON_DEER" or ("lifetime" in text and "deer" in text):
        return "GUARANTEED_LIFETIME_PERMIT_NOT_DRAW"
    if upper(row.get("draw_system_type")) == "REFERENCE_ONLY" or lower(row.get("draw_pool")) == "reference_only":
        return "REFERENCE_ONLY_NOT_DRAW"
    if upper(row.get("draw_system_type")) == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK" or (
        "antlerless" in text and "elk" in text and "private lands only" in text
    ):
        return "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK_OTC_NOT_DRAW"
    return ""


def truth_summary_reason(row: dict[str, str]) -> str:
    if comparable_source_family(row) == "SPORTSMAN":
        return ""
    if normalize_points(row.get("points")) == "TOTAL":
        return "PDF_BOTTOM_CUMULATIVE_TOTAL_ROW_NOT_LADDER"
    return ""


def truth_match_partition(row: dict[str, str]) -> str:
    bucket = rebuilt_bucket(row)
    if bucket in {"TURKEY", "YOUTH_TURKEY"} or comparable_source_family(row) in SOURCE_PARTITIONED_FAMILIES:
        return "|".join([comparable_draw_system_type(row), comparable_draw_pool_key(row)])
    return ""


def prediction_match_partition(row: dict[str, str]) -> str:
    if upper(row.get("source_family")) == "TURKEY" or upper(row.get("source_family")) in SOURCE_PARTITIONED_FAMILIES:
        return "|".join([clean(row.get("draw_system_type")), clean(row.get("draw_pool_key") or row.get("draw_pool"))])
    return ""


def relaxed_truth_keys(row: dict[str, str]) -> list[tuple[str, str, str, str, str]]:
    points = normalize_points(row.get("points"))
    if comparable_source_family(row) == "SPORTSMAN" and points == "TOTAL":
        points = ""
    points_options = [points]
    if points == "0":
        points_options.append("")
    return [
        (
            truth_target_year(row),
            comparable_source_family(row),
            truth_match_partition(row),
            upper(row.get("hunt_code")),
            point,
        )
        for point in dict.fromkeys(points_options)
    ]


def prediction_relaxed_key(row: dict[str, str]) -> tuple[str, str, str, str, str]:
    return (
        clean(row.get("target_year")),
        upper(row.get("source_family")),
        prediction_match_partition(row),
        upper(row.get("hunt_code")),
        normalize_points(row.get("points")),
    )


def official_key(row: dict[str, str]) -> str:
    values = []
    for field in REQUIRED_KEY_COLUMNS[:-1]:
        if field == "draw_pool":
            values.append(clean(row.get("draw_pool_key") or row.get("draw_pool")))
        else:
            values.append(clean(row.get(field)))
    return "|".join(values)


def source_partition_signature(row: dict[str, Any]) -> tuple[str, ...]:
    return source_partition_signature_for_point(row, normalize_points(row.get("points")))


def source_partition_signature_for_point(row: dict[str, Any], point: str) -> tuple[str, ...]:
    return (
        clean(row.get("target_year")),
        clean(row.get("source_family")),
        clean(row.get("draw_system_type")),
        upper(row.get("hunt_code")),
        clean(row.get("score_scope")),
        clean(row.get("residency")),
        point,
        clean(row.get("probability_metric")),
    )


def is_parent_style_partition_row(row: dict[str, Any]) -> bool:
    return (
        upper(row.get("source_family")) in SOURCE_PARTITIONED_FAMILIES
        and lower(row.get("draw_pool")) in PARENT_STYLE_DRAW_POOLS
    )


def _parse_number(value: Any) -> float | None:
    text = clean(value)
    if text == "":
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:.10f}".rstrip("0").rstrip(".")


def apply_prediction_lane_actuals(output: dict[str, Any], truth_row: dict[str, str], prediction_row: dict[str, str]) -> None:
    scope = upper(prediction_row.get("score_scope"))
    if scope == "RESIDENT":
        prefix = "resident"
    elif scope == "NONRESIDENT":
        prefix = "nonresident"
    else:
        prefix = "total"

    lane_fields = {
        "eligible_applicants": f"{prefix}_eligible_applicants",
        "bonus_permits": f"{prefix}_bonus_permits",
        "regular_permits": f"{prefix}_regular_permits",
        "total_permits": f"{prefix}_total_permits",
        "success_ratio": f"{prefix}_success_ratio",
        "p_draw": f"{prefix}_p_draw",
        "p_draw_percent": f"{prefix}_p_draw_percent",
    }
    for output_field, source_field in lane_fields.items():
        value = clean(truth_row.get(source_field))
        if value != "":
            output[output_field] = value

    successful = _parse_number(output.get("total_permits"))
    eligible = _parse_number(output.get("eligible_applicants"))
    if successful is not None:
        output["successful_applicants"] = _format_number(successful)
    if eligible is not None and successful is not None:
        output["unsuccessful_applicants"] = _format_number(max(eligible - successful, 0))


TRUTH_DUPLICATE_PAYLOAD_FIELDS = [
    "target_year",
    "source_family",
    "draw_system_type",
    "draw_pool",
    "draw_pool_key",
    "hunt_code",
    "score_scope",
    "residency",
    "points",
    "probability_metric",
    "eligible_applicants",
    "successful_applicants",
    "unsuccessful_applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "p_draw",
    "p_draw_normalized",
    "p_draw_percent",
]


def truth_duplicate_payload_signature(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(clean(row.get(field)) for field in TRUTH_DUPLICATE_PAYLOAD_FIELDS)


def build(args: argparse.Namespace) -> dict[str, Any]:
    truth_fields, truth_rows = read_csv(args.truth)
    prediction_fields, prediction_rows = read_csv(args.predictions)
    missing_prediction_columns = [field for field in REQUIRED_KEY_COLUMNS if field not in prediction_fields]
    if missing_prediction_columns:
        raise SystemExit(f"Prediction file is missing required columns: {missing_prediction_columns}")

    prediction_by_relaxed: dict[tuple[str, str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in prediction_rows:
        if clean(row.get("probability_metric")) == "p_draw":
            prediction_by_relaxed[prediction_relaxed_key(row)].append(row)

    comparable_rows: list[dict[str, Any]] = []
    unmatched_truth_rows: list[dict[str, Any]] = []
    excluded_truth_rows: list[dict[str, Any]] = []
    summary_truth_rows: list[dict[str, Any]] = []
    duplicate_counter: Counter[str] = Counter()
    family_rows: Counter[str] = Counter()
    excluded_reason_rows: Counter[str] = Counter()
    summary_reason_rows: Counter[str] = Counter()

    for truth_row in truth_rows:
        summary_reason = truth_summary_reason(truth_row)
        if summary_reason:
            summary = dict(truth_row)
            summary["truth_summary_reason"] = summary_reason
            summary_truth_rows.append(summary)
            summary_reason_rows[summary_reason] += 1
            continue

        exclusion_reason = truth_exclusion_reason(truth_row)
        if exclusion_reason:
            excluded = dict(truth_row)
            excluded["scoring_exclusion_reason"] = exclusion_reason
            excluded_truth_rows.append(excluded)
            excluded_reason_rows[exclusion_reason] += 1
            continue

        matches: list[dict[str, str]] = []
        for key in relaxed_truth_keys(truth_row):
            matches.extend(prediction_by_relaxed.get(key, []))
        if not matches:
            unmatched = dict(truth_row)
            unmatched["canonical_source_family"] = clean(truth_row.get("source_family"))
            unmatched["canonical_draw_system_type"] = clean(truth_row.get("draw_system_type"))
            unmatched["canonical_draw_pool"] = clean(truth_row.get("draw_pool"))
            unmatched["canonical_score_scope"] = normalized_score_scope(truth_row)
            unmatched["canonical_residency"] = clean(truth_row.get("residency"))
            unmatched["canonical_points"] = clean(truth_row.get("points"))
            unmatched["target_year"] = truth_target_year(truth_row)
            unmatched["source_family"] = comparable_source_family(truth_row)
            unmatched["draw_system_type"] = comparable_draw_system_type(truth_row)
            unmatched["draw_pool"] = comparable_draw_pool(truth_row)
            unmatched["draw_pool_key"] = comparable_draw_pool_key(truth_row)
            unmatched["hunt_code"] = upper(truth_row.get("hunt_code"))
            unmatched["score_scope"] = normalized_score_scope(truth_row)
            unmatched["residency"] = clean(truth_row.get("residency"))
            unmatched_points = normalize_points(truth_row.get("points"))
            if comparable_source_family(truth_row) == "SPORTSMAN" and unmatched_points == "TOTAL":
                unmatched_points = ""
            unmatched["points"] = unmatched_points
            unmatched["probability_metric"] = "p_draw"
            unmatched["comparable_unmatched_reason"] = "NO_PREDICTION_KEY_MATCH"
            unmatched_truth_rows.append(unmatched)
            continue

        seen_keys: set[str] = set()
        for prediction_row in matches:
            output = dict(truth_row)
            output["canonical_source_family"] = clean(truth_row.get("source_family"))
            output["canonical_draw_system_type"] = clean(truth_row.get("draw_system_type"))
            output["canonical_draw_pool"] = clean(truth_row.get("draw_pool"))
            output["canonical_score_scope"] = normalized_score_scope(truth_row)
            output["canonical_residency"] = clean(truth_row.get("residency"))
            output["canonical_points"] = clean(truth_row.get("points"))
            for field in REQUIRED_KEY_COLUMNS[:-1]:
                output[field] = clean(prediction_row.get(field))
            output["draw_pool_key"] = clean(prediction_row.get("draw_pool_key"))
            apply_prediction_lane_actuals(output, truth_row, prediction_row)
            output["official_score_key_v2"] = clean(prediction_row.get("official_score_key_v2")) or official_key(output)
            output["row_status"] = "SCORABLE"
            output["scoring_comparable_source"] = "prediction_surface_key_vocabulary"
            if output["official_score_key_v2"] in seen_keys:
                continue
            seen_keys.add(output["official_score_key_v2"])
            duplicate_counter[output["official_score_key_v2"]] += 1
            family_rows[output["source_family"]] += 1
            comparable_rows.append(output)

    comparable_by_key: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in comparable_rows:
        comparable_by_key[row["official_score_key_v2"]].append(row)

    duplicate_rows: list[dict[str, Any]] = []
    duplicate_truth_key_rows: list[dict[str, Any]] = []
    exact_duplicate_truth_key_rows: list[dict[str, Any]] = []
    deduped_comparable_rows: list[dict[str, Any]] = []
    duplicate_excess_rows = 0
    exact_duplicate_excess_rows = 0
    conflicting_duplicate_excess_rows = 0
    for key, rows_for_key in sorted(comparable_by_key.items()):
        if len(rows_for_key) == 1:
            deduped_comparable_rows.extend(rows_for_key)
            continue

        signatures = {truth_duplicate_payload_signature(row) for row in rows_for_key}
        duplicate_excess_rows += len(rows_for_key) - 1
        if len(signatures) == 1:
            deduped_comparable_rows.append(rows_for_key[0])
            exact_duplicate_truth_key_rows.extend(rows_for_key[1:])
            exact_duplicate_excess_rows += len(rows_for_key) - 1
            continue

        duplicate_rows.append({"official_score_key_v2": key, "duplicate_row_count": len(rows_for_key)})
        duplicate_truth_key_rows.extend(rows_for_key)
        conflicting_duplicate_excess_rows += len(rows_for_key) - 1

    comparable_rows = deduped_comparable_rows

    child_partition_signatures = {
        source_partition_signature(row)
        for row in comparable_rows
        if upper(row.get("source_family")) in SOURCE_PARTITIONED_FAMILIES
        and lower(row.get("draw_pool")) not in PARENT_STYLE_DRAW_POOLS
    }
    parent_pool_duplicate_rows = [
        row
        for row in comparable_rows
        if is_parent_style_partition_row(row)
        and (
            source_partition_signature(row) in child_partition_signatures
            or (
                normalize_points(row.get("points")) == ""
                and source_partition_signature_for_point(row, "0") in child_partition_signatures
            )
        )
    ]
    parent_pool_duplicate_keys = {row["official_score_key_v2"] for row in parent_pool_duplicate_rows}
    comparable_rows = [
        row for row in comparable_rows if row["official_score_key_v2"] not in parent_pool_duplicate_keys
    ]

    fields = list(dict.fromkeys(truth_fields + [
        "canonical_source_family",
        "canonical_draw_system_type",
        "canonical_draw_pool",
        "draw_pool_key",
        "canonical_score_scope",
        "canonical_residency",
        "canonical_points",
        "scoring_comparable_source",
        "comparable_unmatched_reason",
    ] + REQUIRED_KEY_COLUMNS))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "truth_scorable_multiscope_long_score_key_v2.csv", comparable_rows, fields)
    write_csv(args.output_dir / "truth_duplicate_score_key_v2_rows_excluded_from_scoring.csv", duplicate_truth_key_rows, fields)
    write_csv(args.output_dir / "truth_exact_duplicate_score_key_v2_rows_dropped.csv", exact_duplicate_truth_key_rows, fields)
    write_csv(args.output_dir / "truth_parent_pool_duplicate_rows_excluded_from_scoring.csv", parent_pool_duplicate_rows, fields)
    write_csv(args.output_dir / "truth_scorable_unmatched_to_prediction_surface.csv", unmatched_truth_rows, fields)
    write_csv(args.output_dir / "truth_excluded_from_score_key_alignment.csv", excluded_truth_rows, fields + ["scoring_exclusion_reason"])
    write_csv(args.output_dir / "truth_summary_rows_not_ladder.csv", summary_truth_rows, fields + ["truth_summary_reason"])
    write_csv(args.output_dir / "truth_score_key_v2_duplicates.csv", duplicate_rows, ["official_score_key_v2", "duplicate_row_count"])
    family_summary = [
        {"source_family": family, "scorable_rows": count}
        for family, count in sorted(family_rows.items())
    ]
    write_csv(args.output_dir / "source_family_summary.csv", family_summary, ["source_family", "scorable_rows"])

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_year": args.source_year,
        "target_year": args.target_year,
        "truth_rows_in": len(truth_rows),
        "prediction_rows_in": len(prediction_rows),
        "multiscope_scorable_rows": len(comparable_rows),
        "unmatched_truth_rows": len(unmatched_truth_rows),
        "excluded_truth_rows": len(excluded_truth_rows),
        "excluded_reason_counts": dict(sorted(excluded_reason_rows.items())),
        "summary_truth_rows": len(summary_truth_rows),
        "summary_reason_counts": dict(sorted(summary_reason_rows.items())),
        "duplicate_score_key_v2_rows": len(duplicate_truth_key_rows),
        "duplicate_score_key_v2_excess_rows": duplicate_excess_rows,
        "exact_duplicate_score_key_v2_rows_dropped": len(exact_duplicate_truth_key_rows),
        "exact_duplicate_score_key_v2_excess_rows": exact_duplicate_excess_rows,
        "conflicting_duplicate_score_key_v2_rows": len(duplicate_truth_key_rows),
        "conflicting_duplicate_score_key_v2_excess_rows": conflicting_duplicate_excess_rows,
        "duplicate_score_key_v2_groups": len(duplicate_rows),
        "parent_pool_duplicate_rows_excluded": len(parent_pool_duplicate_rows),
        "score_key_v2_clean": not duplicate_rows,
        "calibration_applied": False,
        "canonical_truth_modified": False,
        "files_staged": 0,
    }
    (args.output_dir / "status.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--truth", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    parser.add_argument("--source-year", required=True, type=int)
    parser.add_argument("--target-year", required=True, type=int)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    status = build(parse_args())
    print(json.dumps(status, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
