"""Youth draw strategy helpers."""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.rules import MODEL_VERSION

from . import (
    ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
    ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    ALGORITHM_STATUS_MODELED_PREFERENCE,
    ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
    StrategySpec,
    TARGET_SCOPE_TARGET,
)
from .taxonomy import effective_draw_design


REPO = Path(__file__).resolve().parents[2]

YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE = "YOUTH_GENERAL_DEER_RESERVE"
YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE = "YOUTH_ANTLERLESS_OR_DOE_RESERVE"
YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE = "YOUTH_GENERAL_ANY_BULL_ELK"
YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
YOUTH_RANDOM_ELK_GENERAL_BULL_DRAW_SYSTEM_TYPE = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE = "YOUTH_OTC_OR_AVAILABILITY"
# Legacy names kept for older imports/tests; the classifier now emits the
# canonical split family names above.
YOUTH_GENERAL_DEER_DRAW_SYSTEM_TYPE = YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE
YOUTH_DRAW_SYSTEM_TYPES = {
    YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
    YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE,
    YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE,
    YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE,
}

YOUTH_DEER_MODEL_STRATEGY_NAME = "youth_general_deer_reserve_preference_v1"
YOUTH_ANTLERLESS_OR_DOE_MODEL_STRATEGY_NAME = "youth_antlerless_or_doe_reserve_preference_v1"
YOUTH_ELK_MODEL_STRATEGY_NAME = "youth_general_any_bull_elk_random_v1"
RULE_VERSION = "utah_youth_strategy_phase17_v1.0.0"

YOUTH_ELK_SOURCE_PATH = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "2026_elk_general_anybull_youth.csv"
YOUTH_ELK_HISTORY_PATH = REPO / "processed_data" / "eb1007_youth_general_bull_history.csv"
YOUTH_GENERAL_ANY_BULL_ELK_TREND_DAMPING = 0.25

YOUTH_DEER_SOURCE_FILES = {
    "21_youth_deer.pdf",
    "22_youth_deer.pdf",
    "2025 youth g.s. deer draw results.pdf",
}
YOUTH_ELK_SOURCE_FILES = {
    "20_youth_bull_elk.pdf",
    "21_youth_bull_elk.pdf",
    "22_youth_bull_elk.pdf",
    "24_youth_elk.pdf",
    "2025 youth g.s.. mature bull draw.pdf",
}


STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type="GENERAL_BIG_GAME_OTHER",
        module_name="engine.utah_draw_predictive.youth",
        algorithm_status=ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        target_scope=TARGET_SCOPE_TARGET,
        reason="This target-scope big-game draw category is not yet assigned to an accepted production strategy.",
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type=YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.youth",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Youth general deer reserve rows use a youth-reserve preference model (up to 20% youth reserve plus rollover to the main preference draw).",
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type=YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.youth",
        algorithm_status=ALGORITHM_STATUS_MODELED_PREFERENCE,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Youth antlerless/doe reserve rows use a youth-reserve preference model (up to 20% youth reserve plus rollover to the main preference draw).",
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type=YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.youth",
        algorithm_status=ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Youth general any-bull elk (EB1007) is a dedicated youth set-aside random draw and uses its own modeled random-only lane when official source rows are available.",
        legacy_logic_present=True,
    ),
    StrategySpec(
        draw_system_type=YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.youth",
        algorithm_status=ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Youth OTC or availability rows are target-scope availability/purchase rows, not predictive draw-odds rows.",
        legacy_logic_present=True,
    ),
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _to_int(value: object) -> int:
    text = _clean(value).replace(",", "")
    if not text:
        return 0
    try:
        return int(float(text))
    except Exception:
        return 0


def _history_years_or_bootstrap(history_years: list[int], truth_rows: list[Mapping[str, object]]) -> list[int]:
    if history_years:
        return [int(year) for year in history_years]
    inferred = sorted({_to_int(row.get("actual_draw_year") or row.get("source_year") or row.get("draw_year") or row.get("year")) for row in truth_rows})
    inferred = [year for year in inferred if year > 0]
    return [inferred[-1]] if inferred else []


def _to_float_optional(value: object) -> float | None:
    text = _clean(value).replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, value))


def _format_odds_text(probability: float) -> str:
    probability = _clamp01(probability)
    if probability <= 0:
        return "0%"
    return f"~1 in {1.0 / probability:.1f} or {probability * 100.0:.1f}%"


def _format_probability(value: float | None) -> str:
    return "" if value is None else f"{_clamp01(value):.6f}"


def _format_probability_pct(value: float | None) -> str:
    return "" if value is None else f"{_clamp01(value) * 100.0:.3f}"


def _split_youth_reserve_permits(total_permits: int) -> tuple[int, int]:
    if total_permits <= 0:
        return 0, 0
    youth_reserved = int(total_permits * 0.20)
    youth_reserved = max(0, min(total_permits, youth_reserved))
    main_pool = max(0, total_permits - youth_reserved)
    return youth_reserved, main_pool


def _row_probability(row: Mapping[str, object]) -> float | None:
    for key in ("p_preference_draw", "p_draw", "p_draw_mean", "odds_2026_projected", "display_odds_pct"):
        value = _to_float_optional(row.get(key))
        if value is None:
            continue
        if key in {"odds_2026_projected", "display_odds_pct"}:
            value = value / 100.0
        if 0.0 <= value <= 1.0:
            return value
    return None


def _quota_applicant_probability(row: Mapping[str, object]) -> float | None:
    quota = _to_int(row.get("total_permits") or row.get("quota"))
    eligible = _to_int(row.get("eligible_applicants"))
    if quota <= 0 or eligible <= 0:
        return None
    return _clamp01(quota / eligible)


def _historical_youth_general_any_bull_elk_rows(
    truth_rows: list[Mapping[str, object]],
    forecast_year: int,
) -> tuple[dict[str, list[dict[str, object]]], list[str]]:
    history_by_residency: dict[str, dict[int, dict[str, object]]] = {"Resident": {}, "Nonresident": {}}
    source_files_used: list[str] = []

    def add_history(
        residency: str,
        year: int,
        eligible: int,
        quota: int,
        source_file: str,
    ) -> None:
        if residency not in history_by_residency or year <= 0 or year >= forecast_year:
            return
        if eligible <= 0 or quota <= 0:
            return
        history_by_residency[residency][year] = {
            "year": year,
            "eligible_applicants": eligible,
            "quota": quota,
            "source_file": source_file,
        }
        if source_file:
            source_files_used.append(source_file)

    for raw in truth_rows:
        row = dict(raw)
        if _clean(row.get("hunt_code")).upper() != "EB1007":
            continue
        residency = _clean(row.get("residency"))
        year = _to_int(row.get("actual_draw_year") or row.get("year"))
        source_file = _clean(row.get("source_file"))
        if residency:
            add_history(
                residency,
                year,
                _to_int(row.get("eligible_applicants")),
                _to_int(row.get("total_permits")),
                source_file,
            )
            continue
        add_history(
            "Resident",
            year,
            _to_int(row.get("resident_eligible_applicants")),
            _to_int(row.get("resident_total_permits")),
            source_file,
        )
        add_history(
            "Nonresident",
            year,
            _to_int(row.get("nonresident_eligible_applicants")),
            _to_int(row.get("nonresident_total_permits")),
            source_file,
        )

    if YOUTH_ELK_HISTORY_PATH.exists():
        with YOUTH_ELK_HISTORY_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                if _clean(row.get("hunt_code")).upper() != "EB1007":
                    continue
                residency = _clean(row.get("residency"))
                year = _to_int(row.get("actual_draw_year"))
                eligible = _to_int(row.get("eligible_applicants"))
                quota = _to_int(row.get("quota"))
                if residency not in history_by_residency or year <= 0 or year >= forecast_year:
                    continue
                if eligible <= 0 or quota <= 0:
                    continue
                history_by_residency[residency].setdefault(
                    year,
                    {
                        "year": year,
                        "eligible_applicants": eligible,
                        "quota": quota,
                        "source_file": _clean(row.get("source_file")),
                    },
                )
                if _clean(row.get("source_file")):
                    source_files_used.append(_clean(row.get("source_file")))
        source_files_used.append(str(YOUTH_ELK_HISTORY_PATH.relative_to(REPO)))

    normalized = {
        residency: [history_by_residency[residency][year] for year in sorted(history_by_residency[residency])]
        for residency in history_by_residency
    }
    return normalized, sorted({path for path in source_files_used if path})


def _forecast_youth_general_any_bull_elk_applicants(history_rows: list[dict[str, object]]) -> int:
    if not history_rows:
        return 0
    latest = int(history_rows[-1]["eligible_applicants"])
    if len(history_rows) == 1:
        return latest
    previous = int(history_rows[-2]["eligible_applicants"])
    projected = latest + (YOUTH_GENERAL_ANY_BULL_ELK_TREND_DAMPING * (latest - previous))
    return max(1, int(round(projected)))


def _youth_general_any_bull_elk_quota_for_residency(
    db_row: Mapping[str, object],
    residency: str,
    history_rows_for_residency: list[dict[str, object]],
    forecast_year: int,
) -> int:
    if history_rows_for_residency and forecast_year < 2026:
        return int(history_rows_for_residency[-1]["quota"])
    if residency == "Resident":
        explicit = _to_int(db_row.get("permits_2026_res")) or _to_int(db_row.get("public_permits_2026_res"))
    else:
        explicit = _to_int(db_row.get("permits_2026_nr")) or _to_int(db_row.get("public_permits_2026_nr"))
    if explicit > 0:
        return explicit
    if history_rows_for_residency:
        return int(history_rows_for_residency[-1]["quota"])
    return 0


def _rollover_probability(youth_reserve_probability: float, main_draw_probability: float) -> float:
    return _clamp01(youth_reserve_probability + ((1.0 - youth_reserve_probability) * main_draw_probability))


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type",
            "hunt_class",
            "weapon",
            "draw_pool",
            "source_file",
            "NOTES",
            "notes",
        )
    )


def _source_file_name(row: Mapping[str, object]) -> str:
    raw = _clean(row.get("source_file"))
    if not raw:
        return ""
    return Path(raw).name.lower()


def is_youth_general_deer_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    if "deer" not in text or "antlerless" in text or "doe" in text or "dedicated hunter" in text:
        return False
    source_name = _source_file_name(row)
    draw_pool = _clean_lower(row.get("draw_pool"))
    if source_name in YOUTH_DEER_SOURCE_FILES:
        return True
    if "youth" in text and any(token in text for token in ("general season", "general-season", "extended archery", "hunters choice", "hunters choice")):
        return True
    if draw_pool == "youth" and any(token in text for token in ("general season", "general-season", "extended archery")):
        return True
    return False


def is_youth_antlerless_or_doe_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    draw_pool = _clean_lower(row.get("draw_pool"))
    source_name = _source_file_name(row)
    if not any(token in text for token in ("antlerless", "doe")):
        return False
    if "youth" in text or draw_pool == "youth" or "youth_antlerless" in draw_pool:
        return True
    return "youth antlerless" in source_name


def is_youth_draw_only_elk_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    if "elk" not in text or "antlerless" in text:
        return False
    source_name = _source_file_name(row)
    hunt_code = _clean(row.get("hunt_code")).upper()
    if hunt_code == "EB1007":
        return True
    if hunt_code == "EB1011":
        return False
    if source_name in YOUTH_ELK_SOURCE_FILES and "youth" in text and "draw-only" in text:
        return True
    if "draw-only" in text and "youth" in text and any(token in text for token in ("any bull", "any-bull", "hunters choice", "hunter's choice")):
        return True
    return False


def is_youth_otc_or_availability_row(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    hunt_code = _clean(row.get("hunt_code")).upper()
    if hunt_code == "EB1011":
        return True
    return "elk" in text and ("youth general season bull elk" in text or "general season - youth" in text)


def is_youth_general_any_bull_elk_row(row: Mapping[str, object]) -> bool:
    return is_youth_draw_only_elk_row(row)


def is_modeled_youth_general_any_bull_elk_row(row: Mapping[str, object]) -> bool:
    if effective_draw_design(row) != YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE:
        return False
    if _clean_lower(row.get("model_strategy")) != YOUTH_ELK_MODEL_STRATEGY_NAME.lower():
        return False
    if _clean_lower(row.get("youth_general_any_bull_elk_valid")) not in {"1", "true", "yes", "y"}:
        return False
    return _clean(row.get("p_draw")) != ""


def resolve_youth_algorithm_status(row: Mapping[str, object], draw_system_type: str) -> str:
    if draw_system_type in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        draw_system_type = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
    existing = _clean(row.get("algorithm_status"))
    if existing:
        return existing
    if draw_system_type == YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW
    if draw_system_type in {YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE, YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE}:
        reserve_valid = _clean_lower(row.get("youth_reserve_model_valid")) in {"1", "true", "yes", "y"}
        has_probability = _row_probability(row) is not None
        if reserve_valid and has_probability:
            return ALGORITHM_STATUS_MODELED_PREFERENCE
        return ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE:
        if is_modeled_youth_general_any_bull_elk_row(row):
            return ALGORITHM_STATUS_MODELED_RANDOM_ONLY
        return ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type in YOUTH_DRAW_SYSTEM_TYPES:
        return ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    return existing


def build_youth_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    truth_rows = [dict(row) for row in truth_rows]
    history_years = _history_years_or_bootstrap(history_years, truth_rows)
    latest_history_year = max(history_years) if history_years else forecast_year - 1
    earliest_history_year = min(history_years) if history_years else forecast_year - 1
    youth_deer_history = [dict(row) for row in truth_rows if is_youth_general_deer_row(row)]
    youth_antlerless_history = [dict(row) for row in truth_rows if is_youth_antlerless_or_doe_row(row)]
    youth_elk_history = [dict(row) for row in truth_rows if is_youth_draw_only_elk_row(row)]
    youth_elk_history_by_residency, youth_elk_history_sources = _historical_youth_general_any_bull_elk_rows(truth_rows, forecast_year)

    source_files_used: set[str] = {
        _clean(row.get("source_file"))
        for row in youth_deer_history + youth_antlerless_history + youth_elk_history
        if _clean(row.get("source_file"))
    }
    source_files_used.update(youth_elk_history_sources)
    data_quality_counter: Counter[str] = Counter()
    rows: list[dict[str, object]] = []

    deer_predictive_rows = [dict(row) for row in db_rows if is_youth_general_deer_row(row)]
    antlerless_predictive_rows = [dict(row) for row in db_rows if is_youth_antlerless_or_doe_row(row)]
    if not deer_predictive_rows and not antlerless_predictive_rows:
        data_quality_counter["YOUTH_DEER_ACTIVE_2026_SOURCE_MISSING_OR_SHARED_POOL_AMBIGUOUS"] += 1
        data_quality_counter["YOUTH_RESERVE_MODEL_INPUTS_MISSING"] += 1

    def _build_reserve_rows(
        predictive_rows: list[dict[str, object]],
        draw_system_type: str,
        strategy_name: str,
        permit_type: str,
    ) -> None:
        for row in predictive_rows:
            hunt_code = _clean(row.get("hunt_code")).upper()
            if not hunt_code:
                continue
            residency = _clean(row.get("residency")) or "Resident"
            points = _clean(row.get("points")) or "0"
            permits_total = _to_int(row.get("public_permits_2026")) or _to_int(row.get("permits_2026_total")) or _to_int(row.get("permits_allotted"))
            youth_reserved_permits, main_draw_permits = _split_youth_reserve_permits(permits_total)

            youth_reserve_probability = _row_probability(row)
            main_draw_probability = _row_probability(
                {
                    "p_preference_draw": row.get("p_random_pool"),
                    "p_draw": row.get("p_random_mean"),
                    "p_draw_mean": row.get("random_draw_projection_2026"),
                    "odds_2026_projected": row.get("random_draw_odds_2026"),
                    "display_odds_pct": row.get("random_draw_odds_2026"),
                }
            )
            if main_draw_probability is None:
                main_draw_probability = youth_reserve_probability or 0.0

            if youth_reserve_probability is not None:
                modeled_probability = _rollover_probability(youth_reserve_probability, main_draw_probability)
                algorithm_status = ALGORITHM_STATUS_MODELED_PREFERENCE
                valid_flag = "TRUE"
                flags = [
                    "YOUTH_RESERVE_20_PERCENT_APPLIED",
                    "YOUTH_RESERVE_UNSUCCESSFUL_ROLLOVER_TO_MAIN_DRAW",
                    "YOUTH_RESERVE_MODELLED_FROM_AVAILABLE_PUBLIC_FIELDS",
                ]
            else:
                modeled_probability = None
                algorithm_status = ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
                valid_flag = "FALSE"
                flags = ["YOUTH_RESERVE_PROBABILITY_INPUT_MISSING"]

            data_quality_counter.update(flags)
            rows.append(
                {
                    "model_version": MODEL_VERSION,
                    "rule_version": RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": _clean(row.get("hunt_name")),
                    "species": _clean(row.get("species")),
                    "sex_type": _clean(row.get("sex_type")),
                    "hunt_type": _clean(row.get("hunt_type")),
                    "hunt_class": _clean(row.get("hunt_class")) or "Public",
                    "residency": residency,
                    "points": points,
                    "draw_pool": "youth",
                    "public_permits_2025": _clean(row.get("public_permits_2025")),
                    "public_permits_2026": str(permits_total) if permits_total > 0 else "",
                    "source_years_used": _clean(row.get("source_years_used")) or ",".join(str(year) for year in history_years),
                    "source_year_count": _clean(row.get("source_year_count")) or len(history_years),
                    "latest_source_year": _clean(row.get("latest_source_year")) or latest_history_year,
                    "earliest_source_year": _clean(row.get("earliest_source_year")) or earliest_history_year,
                    "source_dataset": "predictive",
                    "model_strategy": strategy_name,
                    "draw_system_type": draw_system_type,
                    "algorithm_status": algorithm_status,
                    "draw_outlook": "MODEL PENDING" if modeled_probability is None else _clean(row.get("draw_outlook")) or "MODELED YOUTH RESERVE",
                    "permit_type": permit_type,
                    "quota_2026_total": str(permits_total) if permits_total > 0 else "",
                    "quota_2026_youth_reserve": str(youth_reserved_permits),
                    "quota_2026_main_draw": str(main_draw_permits),
                    "youth_reserve_ratio": "0.20",
                    "youth_reserve_model_valid": valid_flag,
                    "youth_reserve_probability": "" if youth_reserve_probability is None else f"{_clamp01(youth_reserve_probability):.6f}",
                    "youth_rollover_main_draw_probability": "" if main_draw_probability is None else f"{_clamp01(main_draw_probability):.6f}",
                    "p_preference_draw": "" if youth_reserve_probability is None else f"{_clamp01(youth_reserve_probability):.6f}",
                    "p_draw": "" if modeled_probability is None else f"{_clamp01(modeled_probability):.6f}",
                    "p_draw_pct": "" if modeled_probability is None else f"{_clamp01(modeled_probability) * 100.0:.3f}",
                    "p_bonus_pool": "",
                    "p_bonus_pool_pct": "",
                    "p_random_pool": "" if main_draw_probability is None else f"{_clamp01(main_draw_probability):.6f}",
                    "p_random_pool_pct": "" if main_draw_probability is None else f"{_clamp01(main_draw_probability) * 100.0:.3f}",
                    "availability_status": "",
                    "p_availability": "",
                    "availability_pct": "",
                    "data_quality_flags": "|".join(flags),
                    "preference_model_valid": valid_flag,
                    "preference_model_note": "Youth reserve pool uses up to 20% permit reservation; unsuccessful youth reserve probability rolls into main draw probability.",
                }
            )

    _build_reserve_rows(
        predictive_rows=deer_predictive_rows,
        draw_system_type=YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
        strategy_name=YOUTH_DEER_MODEL_STRATEGY_NAME,
        permit_type="Youth General Deer Reserve",
    )
    _build_reserve_rows(
        predictive_rows=antlerless_predictive_rows,
        draw_system_type=YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE,
        strategy_name=YOUTH_ANTLERLESS_OR_DOE_MODEL_STRATEGY_NAME,
        permit_type="Youth Antlerless/Doe Reserve",
    )

    youth_elk_source_rows: dict[str, dict[str, str]] = {}
    if YOUTH_ELK_SOURCE_PATH.exists():
        with YOUTH_ELK_SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                hunt_code = _clean(row.get("hunt_code")).upper()
                if hunt_code:
                    youth_elk_source_rows[hunt_code] = dict(row)
        source_files_used.add(str(YOUTH_ELK_SOURCE_PATH.relative_to(REPO)))

    elk_predictive_candidates = [dict(row) for row in db_rows if is_youth_draw_only_elk_row(row)]
    elk_by_code: dict[str, dict[str, str]] = {}
    for row in elk_predictive_candidates:
        hunt_code = _clean(row.get("hunt_code")).upper()
        if hunt_code and hunt_code not in elk_by_code:
            elk_by_code[hunt_code] = row

    for hunt_code, db_row in sorted(elk_by_code.items()):
        source_row = youth_elk_source_rows.get(hunt_code, {})
        season_dates = _clean(source_row.get("season")) or _clean(db_row.get("season"))
        weapon = _clean(source_row.get("weapon")) or _clean(db_row.get("weapon"))
        permits_total = _to_int(source_row.get("permits_2026_total")) or _to_int(db_row.get("permits_2026_total"))
        target_truth_by_residency = {
            _clean(row.get("residency")): dict(row)
            for row in youth_elk_history
            if _clean(row.get("hunt_code")).upper() == hunt_code
            and _to_int(row.get("actual_draw_year") or row.get("year")) == forecast_year
            and _clean(row.get("residency")) in {"Resident", "Nonresident"}
        }

        for residency in ("Resident", "Nonresident"):
            truth_row = target_truth_by_residency.get(residency, {})
            target_probability = _row_probability(truth_row)
            target_eligible = _to_int(truth_row.get("eligible_applicants"))
            target_quota = _to_int(truth_row.get("total_permits"))
            if target_probability is None:
                target_probability = _quota_applicant_probability(truth_row)
            has_actual_target_row = target_probability is not None and target_eligible > 0 and target_quota > 0

            if has_actual_target_row:
                flags = [
                    "YOUTH_SET_ASIDE_RANDOM_DRAW",
                    "OFFICIAL_DRAW_RESULT_USED",
                    "SET_ASIDE_20_PERCENT",
                    "POINT_0_ONLY",
                    "NOT_MAX_WEIGHTED",
                    "NOT_PREFERENCE",
                    "NOT_HARVEST_DERIVED",
                ]
                algorithm_status = ALGORITHM_STATUS_MODELED_RANDOM_ONLY
                draw_outlook = "RANDOM ONLY"
                valid_flag = "TRUE"
                row_permits_total = target_quota
                source_years_used = str(forecast_year)
                source_year_count = 1
                latest_source_year = forecast_year
                earliest_source_year = forecast_year
                eligible_applicants = str(target_eligible)
                p_draw_probability = _clamp01(target_probability)
                p_draw = _format_probability(p_draw_probability)
                p_draw_pct = _format_probability_pct(p_draw_probability)
                display_odds_text = _format_odds_text(target_probability)
                probability_note = (
                    "Modeled from official target-year EB1007 youth set-aside random draw results; "
                    "public odds use residency quota divided by official eligible applicants."
                )
                projected_applicants = str(target_eligible)
                projected_applicants_source = "official_target_year_draw_results"
            else:
                history_rows_for_residency = youth_elk_history_by_residency.get(residency, [])
                forecast_quota = _youth_general_any_bull_elk_quota_for_residency(db_row, residency, history_rows_for_residency, forecast_year)
                projected_eligible = _forecast_youth_general_any_bull_elk_applicants(history_rows_for_residency)
                if projected_eligible > 0 and forecast_quota > 0:
                    projected_probability = _clamp01(forecast_quota / projected_eligible)
                    flags = [
                        "YOUTH_SET_ASIDE_RANDOM_DRAW",
                        "FORECASTED_FROM_HISTORY",
                        "POINT_0_ONLY",
                        "NOT_MAX_WEIGHTED",
                        "NOT_PREFERENCE",
                        "NOT_HARVEST_DERIVED",
                        "APPLICANT_FORECAST_DAMPED_TREND_LAST2_DELTA_25",
                    ]
                    algorithm_status = ALGORITHM_STATUS_MODELED_RANDOM_ONLY
                    draw_outlook = "RANDOM ONLY"
                    valid_flag = "TRUE"
                    row_permits_total = forecast_quota
                    source_years_used = ",".join(str(item["year"]) for item in history_rows_for_residency)
                    source_year_count = len(history_rows_for_residency)
                    latest_source_year = history_rows_for_residency[-1]["year"]
                    earliest_source_year = history_rows_for_residency[0]["year"]
                    eligible_applicants = str(projected_eligible)
                    p_draw_probability = _clamp01(projected_probability)
                    p_draw = _format_probability(p_draw_probability)
                    p_draw_pct = _format_probability_pct(p_draw_probability)
                    display_odds_text = _format_odds_text(projected_probability)
                    probability_note = (
                        "Forecasted from historical EB1007 youth set-aside random applicants using the latest "
                        "year plus one-quarter of the latest year-over-year applicant delta."
                    )
                    projected_applicants = str(projected_eligible)
                    projected_applicants_source = "eb1007_damped_trend_last2_delta_25"
                else:
                    flags = ["YOUTH_GENERAL_ANY_BULL_ELK_PENDING_NO_TARGET_YEAR_SOURCE"]
                    if forecast_quota <= 0 and permits_total <= 0:
                        flags.append("YOUTH_ELK_QUOTA_NOT_PUBLISHED")
                    flags.append("YOUTH_ELK_FORECAST_HISTORY_INSUFFICIENT")
                    algorithm_status = ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
                    draw_outlook = "MODEL PENDING"
                    valid_flag = "FALSE"
                    row_permits_total = forecast_quota or permits_total
                    source_years_used = ",".join(str(year) for year in history_years)
                    source_year_count = len(history_years)
                    latest_source_year = latest_history_year
                    earliest_source_year = earliest_history_year
                    eligible_applicants = ""
                    p_draw = ""
                    p_draw_pct = ""
                    display_odds_text = ""
                    probability_note = (
                        "Dedicated EB1007 youth set-aside random family is source-classified, but forecasting "
                        "remains pending until usable historical applicant history and quota are both available."
                    )
                    projected_applicants = ""
                    projected_applicants_source = ""
                    p_draw_probability = None

            for flag in flags:
                data_quality_counter[flag] += 1

            rows.append(
                {
                    "model_version": MODEL_VERSION,
                    "rule_version": RULE_VERSION,
                    "year": str(forecast_year),
                    "forecast_year": str(forecast_year),
                    "hunt_code": hunt_code,
                    "hunt_name": _clean(db_row.get("hunt_name")),
                    "species": _clean(db_row.get("species")) or "Elk",
                    "sex_type": "Hunter's Choice",
                    "hunt_type": "General Season - Youth",
                    "hunt_class": "Youth Random",
                    "residency": residency,
                    "points": "0",
                    "draw_pool": "youth",
                    "draw_design": YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE,
                    "draw_method": "Strict random",
                    "point_system": "none",
                    "public_permits_2025": "",
                    "public_permits_2026": str(row_permits_total) if row_permits_total > 0 else "",
                    "source_years_used": source_years_used,
                    "source_year_count": source_year_count,
                    "latest_source_year": latest_source_year,
                    "earliest_source_year": earliest_source_year,
                    "source_dataset": "predictive",
                    "model_strategy": YOUTH_ELK_MODEL_STRATEGY_NAME,
                    "weapon": weapon,
                    "season_dates": season_dates,
                    "season_status": "SEASON DATES PRESENT" if season_dates else "SEASON DATES MISSING",
                    "draw_system_type": YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE,
                    "algorithm_status": algorithm_status,
                    "classification_status": algorithm_status,
                    "reason_codes": "FAMILY_ENGINE_MODELED_YOUTH_GENERAL_ANY_BULL_RANDOM" if valid_flag == "TRUE" else "YOUTH_GENERAL_ANY_BULL_PENDING",
                    "draw_outlook": draw_outlook,
                    "availability_status": "",
                    "p_availability": "",
                    "availability_pct": "",
                    "permit_type": "Youth General Any Bull Elk",
                    "permit_status": "",
                    "rule_status": "",
                    "data_quality_flags": "|".join(flags),
                    "youth_general_any_bull_elk_valid": valid_flag,
                    "eligible_applicants": eligible_applicants,
                    "projected_applicants": projected_applicants,
                    "projected_applicants_source": projected_applicants_source,
                    "projected_applicants_2026": projected_applicants if forecast_year == 2026 else "",
                    "projected_applicants_2026_source": projected_applicants_source if forecast_year == 2026 else "",
                    "display_odds_text": display_odds_text,
                    "p_draw_mean": _format_probability(p_draw_probability),
                    "p_draw_p10": _format_probability(p_draw_probability),
                    "p_draw_p50": _format_probability(p_draw_probability),
                    "p_draw_p90": _format_probability(p_draw_probability),
                    "p_draw": p_draw,
                    "p_draw_pct": p_draw_pct,
                    "p_preference_draw": "",
                    "p_bonus_pool": "",
                    "p_bonus_pool_pct": "",
                    "p_random_pool": "",
                    "p_random_pool_pct": "",
                    "youth_general_any_bull_elk_note": probability_note,
                }
            )

    youth_rows = rows
    modeled_preference_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == "MODELED_PREFERENCE"]
    modeled_random_only_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == ALGORITHM_STATUS_MODELED_RANDOM_ONLY]
    modeled_allocation_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == "MODELED_ALLOCATION"]
    modeled_availability_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == "MODELED_AVAILABILITY"]
    pending_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING]
    excluded_rows = [row for row in youth_rows if _clean(row.get("algorithm_status")) == "EXCLUDED_NOT_PREDICTIVE_DRAW"]

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_youth_rows_reviewed": (
            len(youth_deer_history)
            + len(youth_antlerless_history)
            + len(youth_elk_history)
            + len(deer_predictive_rows)
            + len(antlerless_predictive_rows)
            + len(elk_predictive_candidates)
        ),
        "youth_antlerless_or_doe_rows_reviewed": len(youth_antlerless_history) + len(antlerless_predictive_rows),
        "youth_general_deer_rows_reviewed": len(youth_deer_history) + len(deer_predictive_rows),
        "youth_draw_only_elk_rows_reviewed": len(youth_elk_history) + len(elk_predictive_candidates),
        "youth_general_any_bull_elk_rows_reviewed": len(youth_elk_history) + len(elk_predictive_candidates),
        "active_predictive_youth_row_count": len(youth_rows),
        "youth_general_deer_reserve_row_count": len([row for row in youth_rows if row.get("draw_system_type") == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE]),
        "youth_antlerless_or_doe_reserve_row_count": len([row for row in youth_rows if row.get("draw_system_type") == YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE]),
        "youth_general_deer_row_count": len([row for row in youth_rows if row.get("draw_system_type") == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE]),
        "youth_draw_only_elk_row_count": len([row for row in youth_rows if row.get("draw_system_type") == YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE]),
        "youth_general_any_bull_elk_row_count": len([row for row in youth_rows if row.get("draw_system_type") == YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE]),
        "youth_hunt_code_count": len({row.get("hunt_code", "") for row in youth_rows if _clean(row.get("hunt_code"))}),
        "rows_by_algorithm_status": {
            "MODELED_PREFERENCE": len(modeled_preference_rows),
            "MODELED_RANDOM_ONLY": len(modeled_random_only_rows),
            "MODELED_ALLOCATION": len(modeled_allocation_rows),
            "MODELED_AVAILABILITY": len(modeled_availability_rows),
            "IN_SCOPE_MODEL_PENDING": len(pending_rows),
            "EXCLUDED_NOT_PREDICTIVE_DRAW": len(excluded_rows),
        },
        "modeled_preference_row_count": len(modeled_preference_rows),
        "modeled_random_only_row_count": len(modeled_random_only_rows),
        "modeled_allocation_row_count": len(modeled_allocation_rows),
        "modeled_availability_row_count": len(modeled_availability_rows),
        "in_scope_model_pending_row_count": len(pending_rows),
        "excluded_not_predictive_draw_row_count": len(excluded_rows),
        "p_draw_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_draw"))),
        "p_draw_pct_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_draw_pct"))),
        "p_preference_draw_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_preference_draw"))),
        "p_bonus_pool_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_bonus_pool"))),
        "p_random_pool_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_random_pool"))),
        "p_availability_non_null_count": sum(1 for row in youth_rows if _clean(row.get("p_availability"))),
        "availability_pct_non_null_count": sum(1 for row in youth_rows if _clean(row.get("availability_pct"))),
        "p_draw_outside_0_1_count": 0,
        "p_draw_pct_outside_0_100_count": 0,
        "duplicate_key_count": len(youth_rows) - len({(row.get("hunt_code", ""), row.get("residency", ""), row.get("points", "")) for row in youth_rows}),
        "source_files_used": sorted(source_files_used),
        "data_quality_flags_summary": dict(sorted(data_quality_counter.items())),
    }
    return rows, report
