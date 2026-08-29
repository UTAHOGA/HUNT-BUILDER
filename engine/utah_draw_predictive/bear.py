"""Bear subtype helpers and source-backed predictive logic for Utah bear rows."""

from __future__ import annotations

import re
import csv
import json
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from statistics import mean
from typing import Iterable, Mapping

from engine.utah_bonus_predictive.monte_carlo import combine_probabilities, compute_bonus_pool_probability
from engine.utah_bonus_predictive.rules import MODEL_VERSION
from engine.utah_bonus_predictive.split import split_utah_bonus_permits

from . import (
    ALGORITHM_STATUS_MODELED_BONUS,
    StrategySpec,
    TARGET_SCOPE_TARGET,
    append_reason_codes,
)
from .sportsman import is_sportsman_permit_row
from .permit_accessors import target_residency_permit_allocation


MODEL_STRATEGY_NAME = "bear_bonus_phase8"
BONUS_RULE_VERSION = "utah_bear_bonus_v1.0.0"
BEAR_DRAW_SYSTEM_TYPE = "BEAR_DRAW"
BEAR_NO_PRIOR_LADDER_REASON_CODE = "BEAR_CURRENT_TARGET_NO_PRIOR_LADDER_NO_PUBLIC_P_DRAW"
BEAR_NO_PUBLIC_PROBABILITY_REASON_CODES = {
    "KNOWN_ZERO_RESIDENCY_QUOTA",
    "NO_PUBLIC_DRAW_PROBABILITY_FOR_RESIDENCY",
    BEAR_NO_PRIOR_LADDER_REASON_CODE,
}
BEAR_NO_PUBLIC_PROBABILITY_FLAGS = {"MISSING_FORECAST_QUOTA"}
REPO = Path(__file__).resolve().parents[2]
# The durable report-year archive is the authoritative retained copy.  The
# former model-year-named path was an old staging convention and is no longer
# present in the repository.
BEAR_DRAW_ODDS_SOURCE_PDF = (
    REPO
    / "pipeline"
    / "RAW"
    / "hunt_unit_database"
    / "2025"
    / "pdf"
    / "draw_odds"
    / "official_dwr_archive"
    / "black_bear"
    / "25_drawing_odds.pdf"
)
BEAR_DRAW_ODDS_SOURCE_YEAR = 2025
BEAR_DRAW_ODDS_SOURCE_RELATIVE = "pipeline/RAW/hunt_unit_database/2025/pdf/draw_odds/official_dwr_archive/black_bear/25_drawing_odds.pdf"
BR7307_2025_SUPPLEMENTAL_LADDER = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "validation"
    / "black_bear_2025_BR7307_crosswalk_ladder_rows.json"
)

LIMITED_ENTRY_BEAR_HUNT = "LIMITED_ENTRY_BEAR_HUNT"
RESTRICTED_BEAR_PURSUIT = "RESTRICTED_BEAR_PURSUIT"
STATEWIDE_BEAR_PERMIT = "STATEWIDE_BEAR_PERMIT"
HARVEST_OBJECTIVE_AVAILABILITY = "HARVEST_OBJECTIVE_AVAILABILITY"
REMAINING_PERMIT_AVAILABILITY = "REMAINING_PERMIT_AVAILABILITY"
UNLIMITED_PURSUIT_PERMIT = "UNLIMITED_PURSUIT_PERMIT"
CONSERVATION_OR_NON_PUBLIC = "CONSERVATION_OR_NON_PUBLIC"
UNKNOWN_BEAR_SUBTYPE = "UNKNOWN_BEAR_SUBTYPE"

HISTORICAL_BEAR_PDF_CLASSIFICATIONS = {
    "TRUE_BEAR_BONUS_DRAW",
    "BEAR_PURSUIT_BONUS_DRAW",
}

MODELED_BEAR_SUBTYPES = {LIMITED_ENTRY_BEAR_HUNT, RESTRICTED_BEAR_PURSUIT}
EXCLUDED_BEAR_SUBTYPES = {
    HARVEST_OBJECTIVE_AVAILABILITY,
    REMAINING_PERMIT_AVAILABILITY,
    UNLIMITED_PURSUIT_PERMIT,
    CONSERVATION_OR_NON_PUBLIC,
}

# Keep bear draw history keyed by the official hunt code unless a reviewed
# crosswalk proves the historical public draw row moved.  Hand-audited 2026
# DWR/Hunt Planner evidence locks the La Sal public draw-code successors below:
# the old BR7008/BR7108/BR7208 season rows do not continue as 2026 public draw
# rows and move to the La Sal Mtns codes.  BR7307 is reused for conservation in
# 2026 while the public limited-entry multiseason row moves to BR7326.
BEAR_HISTORY_CODE_ALIASES_2026: dict[str, str] = {
    "BR7022": "BR7008",
    "BR7127": "BR7108",
    "BR7239": "BR7208",
    "BR7326": "BR7307",
}
BEAR_HISTORICAL_CODE_SUCCESSORS_2026 = {
    "BR7008": "BR7022",
    "BR7108": "BR7127",
    "BR7208": "BR7239",
}

STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=BEAR_DRAW_SYSTEM_TYPE,
        module_name="engine.utah_draw_predictive.bear",
        algorithm_status=ALGORITHM_STATUS_MODELED_BONUS,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Public limited-entry bear rows use the Utah bonus model only when the source history proves real draw status, valid quota, and modeled bonus probabilities; pursuit-only rows remain reference/allocation records without public harvest draw odds.",
        modeled_by_engine=True,
        legacy_logic_present=True,
    )
]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _to_int(value: object) -> int:
    text = _clean(value)
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


def _skipped_no_history_report(forecast_year: int) -> dict[str, object]:
    return {
        "forecast_year": forecast_year,
        "status": "SKIPPED_NO_HISTORY",
        "blocker": True,
        "production_ready": False,
        "calibration_ready": False,
        "source_years": [],
        "total_bear_rows_reviewed": 0,
        "bear_rows_seen_active_predictive": 0,
        "bear_draw_active_predictive_row_count": 0,
        "bear_draw_modeled_row_count": 0,
        "reason_codes": ["SKIPPED_NO_HISTORY"],
        "note": "No source history rows were available for bonus bear; no probability rows were fabricated.",
    }


def _round_count(value: float) -> int:
    return max(0, int(round(value)))


def _safe_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _band_for_points(points: int) -> str:
    if points <= 0:
        return "0"
    if points == 1:
        return "1"
    if points <= 3:
        return "2_3"
    if points <= 5:
        return "4_5"
    if points <= 9:
        return "6_9"
    return "10_plus"


def _joined_text(row: Mapping[str, object]) -> str:
    return " ".join(
        _clean_lower(row.get(key))
        for key in ("hunt_code", "hunt_name", "species", "sex_type", "hunt_type", "hunt_class", "weapon", "draw_pool", "source_file")
    )


def _species_is_black_bear(row: Mapping[str, object]) -> bool:
    species = _clean_lower(row.get("species"))
    return species in {"black bear", "bear"} or "black bear" in species


def _hunt_code_is_bear(row: Mapping[str, object]) -> bool:
    return _clean(row.get("hunt_code")).upper().startswith("BR")


def is_bear_row(row: Mapping[str, object]) -> bool:
    if _species_is_black_bear(row):
        return True
    text = _joined_text(row)
    if _hunt_code_is_bear(row) and "bear" in text and "bighorn" not in text:
        return True
    return False


@lru_cache(maxsize=1)
def _parse_official_bear_draw_odds_pdf() -> dict[str, dict[str, object]]:
    if not BEAR_DRAW_ODDS_SOURCE_PDF.exists():
        # A missing repo-external source is a hydration blocker, not permission
        # to guess bear pursuit subtype or crash unrelated classification work.
        return {}
    try:
        import pdfplumber
    except Exception as exc:
        raise RuntimeError("pdfplumber is required to audit official bear draw odds source rows.") from exc

    audit: dict[str, dict[str, object]] = {}
    with pdfplumber.open(BEAR_DRAW_ODDS_SOURCE_PDF) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            hunt_match = re.search(r"Hunt:\s*(BR\d{4})\s+(.+?)\nResident Applicants", text, re.S)
            if not hunt_match:
                continue
            hunt_code = hunt_match.group(1).strip().upper()
            hunt_name = " ".join(hunt_match.group(2).split()).strip()
            totals = re.findall(r"Totals\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)", text)
            resident_totals = totals[0] if len(totals) >= 1 else ("0", "0", "0", "0")
            nonresident_totals = totals[1] if len(totals) >= 2 else ("0", "0", "0", "0")
            is_pursuit = "pursuit" in hunt_name.lower()
            audit[hunt_code] = {
                "hunt_code": hunt_code,
                "hunt_name": hunt_name,
                "source_year": BEAR_DRAW_ODDS_SOURCE_YEAR,
                "source_file": BEAR_DRAW_ODDS_SOURCE_RELATIVE,
                "appears_in_draw_odds_pdf": True,
                "has_point_level_bonus_rows": True,
                "resident_bonus_permits_total": int(resident_totals[1]),
                "resident_regular_permits_total": int(resident_totals[2]),
                "resident_total_permits": int(resident_totals[3]),
                "nonresident_bonus_permits_total": int(nonresident_totals[1]),
                "nonresident_regular_permits_total": int(nonresident_totals[2]),
                "nonresident_total_permits": int(nonresident_totals[3]),
                "source_classification": "BEAR_PURSUIT_BONUS_DRAW" if is_pursuit else "TRUE_BEAR_BONUS_DRAW",
                "page_number": page_number,
            }
    return audit


def official_bear_draw_odds_hunt_codes() -> set[str]:
    return set(_parse_official_bear_draw_odds_pdf().keys())


def official_bear_pursuit_hunt_codes() -> set[str]:
    return {
        hunt_code
        for hunt_code, row in _parse_official_bear_draw_odds_pdf().items()
        if row.get("source_classification") == "BEAR_PURSUIT_BONUS_DRAW"
    }


def _historical_bear_pdf_classification(row: Mapping[str, object]) -> str:
    """Use retained-PDF identity only for an explicit audit lane projection.

    Some 2018-2020 canonical rows preserve a generic legacy draw label even
    though the retained official Black Bear PDF page identifies the program.
    The residency-lane audit projection carries that exact page classification
    forward in dedicated fields. Do not infer it from a code prefix, permit
    count, or generic legacy draw label.
    """

    classification = _clean(row.get("bear_source_classification")).upper()
    source = _clean(row.get("bear_source_identity_source")).upper()
    source_file = _clean_lower(row.get("bear_source_identity_file") or row.get("source_file")).replace("\\", "/")
    qa_status = _clean(row.get("qa_status")).upper()
    hunt_code = _clean(row.get("hunt_code")).upper()
    if (
        classification not in HISTORICAL_BEAR_PDF_CLASSIFICATIONS
        or source != "RETAINED_OFFICIAL_BLACK_BEAR_PDF"
        or not hunt_code.startswith("BR")
        or "/official_dwr_archive/black_bear/" not in f"/{source_file.lstrip('/')}"
        or qa_status != "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED"
    ):
        return ""
    return classification


def classify_bear_subtype_before_source_correction(row: Mapping[str, object]) -> str:
    if not is_bear_row(row):
        return UNKNOWN_BEAR_SUBTYPE
    if is_sportsman_permit_row(row):
        return STATEWIDE_BEAR_PERMIT
    text = _joined_text(row)
    hunt_type = _clean_lower(row.get("hunt_type"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    weapon = _clean_lower(row.get("weapon"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_code = _clean(row.get("hunt_code")).upper()

    if hunt_code == "BR1000":
        return STATEWIDE_BEAR_PERMIT
    if hunt_code in {"BR1007", "BR1018"}:
        return UNLIMITED_PURSUIT_PERMIT
    if (
        "cwmu" in text
        or any(token in text for token in ("conservation", "expo", "sportsman", "private land", "landowner", "private"))
        or hunt_class == "private"
        or draw_pool == "sportsman"
    ):
        return CONSERVATION_OR_NON_PUBLIC
    if "remaining permit" in text or " otc" in f" {text}" or "over the counter" in text:
        return REMAINING_PERMIT_AVAILABILITY
    if "harvest objective" in text:
        return HARVEST_OBJECTIVE_AVAILABILITY
    if "restricted pursuit" in text or hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":
        return UNLIMITED_PURSUIT_PERMIT
    if "spot and stalk" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    if "limited entry" in text or "limited-entry" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    return UNKNOWN_BEAR_SUBTYPE


def classify_bear_subtype(row: Mapping[str, object]) -> str:
    if not is_bear_row(row):
        return UNKNOWN_BEAR_SUBTYPE
    if is_sportsman_permit_row(row):
        return STATEWIDE_BEAR_PERMIT
    text = _joined_text(row)
    hunt_type = _clean_lower(row.get("hunt_type"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    weapon = _clean_lower(row.get("weapon"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_code = _clean(row.get("hunt_code")).upper()
    official_draw_codes = official_bear_draw_odds_hunt_codes()
    official_pursuit_codes = official_bear_pursuit_hunt_codes()

    if hunt_code == "BR1000":
        return STATEWIDE_BEAR_PERMIT
    if hunt_code == "BR1001":
        return HARVEST_OBJECTIVE_AVAILABILITY
    if hunt_code in {"BR1007", "BR1018"}:
        return UNLIMITED_PURSUIT_PERMIT
    if (
        "cwmu" in text
        or any(token in text for token in ("conservation", "expo", "sportsman", "private land", "landowner", "private"))
        or hunt_class == "private"
        or draw_pool == "sportsman"
    ):
        return CONSERVATION_OR_NON_PUBLIC
    if "harvest objective" in text:
        return HARVEST_OBJECTIVE_AVAILABILITY
    historical_pdf_classification = _historical_bear_pdf_classification(row)
    if historical_pdf_classification == "BEAR_PURSUIT_BONUS_DRAW":
        return RESTRICTED_BEAR_PURSUIT
    if historical_pdf_classification == "TRUE_BEAR_BONUS_DRAW":
        return LIMITED_ENTRY_BEAR_HUNT
    if hunt_code in official_pursuit_codes:
        return RESTRICTED_BEAR_PURSUIT
    if hunt_code in official_draw_codes:
        return LIMITED_ENTRY_BEAR_HUNT
    if "remaining permit" in text or " otc" in f" {text}" or "over the counter" in text:
        return REMAINING_PERMIT_AVAILABILITY
    if "restricted pursuit" in text:
        return UNKNOWN_BEAR_SUBTYPE
    if hunt_code not in official_draw_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):
        return UNLIMITED_PURSUIT_PERMIT
    if "spot and stalk" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    if "limited entry" in text or "limited-entry" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    return UNKNOWN_BEAR_SUBTYPE


def is_supported_bear_bonus_row(row: Mapping[str, object]) -> bool:
    return classify_bear_subtype(row) in MODELED_BEAR_SUBTYPES


def is_remaining_bear_row(row: Mapping[str, object]) -> bool:
    return classify_bear_subtype(row) == REMAINING_PERMIT_AVAILABILITY


def is_nonpublic_bear_row(row: Mapping[str, object]) -> bool:
    return classify_bear_subtype(row) == CONSERVATION_OR_NON_PUBLIC


def is_harvest_objective_bear_row(row: Mapping[str, object]) -> bool:
    return classify_bear_subtype(row) == HARVEST_OBJECTIVE_AVAILABILITY


def _pipe_tokens(value: object) -> set[str]:
    return {part.strip().upper() for part in _clean(value).split("|") if part.strip()}


def _has_no_public_bear_probability_path(row: Mapping[str, object]) -> bool:
    reason_codes = _pipe_tokens(row.get("reason_codes"))
    flags = _pipe_tokens(row.get("data_quality_flags"))
    return bool(
        reason_codes & BEAR_NO_PUBLIC_PROBABILITY_REASON_CODES
        or flags & BEAR_NO_PUBLIC_PROBABILITY_FLAGS
    )


def is_excluded_bear_row(row: Mapping[str, object]) -> bool:
    if _clean(row.get("draw_system_type")) == BEAR_DRAW_SYSTEM_TYPE and _has_no_public_bear_probability_path(row):
        return True
    subtype = classify_bear_subtype(row)
    if subtype == STATEWIDE_BEAR_PERMIT:
        text = _joined_text(row)
        hunt_code = _clean(row.get("hunt_code")).upper()
        return hunt_code == "BR1000" or "sportsman" in text or "no_draw_odds" in text
    return subtype in EXCLUDED_BEAR_SUBTYPES


def is_modeled_bear_row(row: Mapping[str, object]) -> bool:
    return (
        _clean_lower(row.get("model_strategy")) == MODEL_STRATEGY_NAME
        and _clean_lower(row.get("bear_bonus_valid")) in {"1", "true", "yes", "y"}
        and _clean(row.get("draw_system_type")) == BEAR_DRAW_SYSTEM_TYPE
        and classify_bear_subtype(row) in MODELED_BEAR_SUBTYPES
    )


def is_modeled_bear_availability_row(row: Mapping[str, object]) -> bool:
    if _clean(row.get("draw_system_type")) != BEAR_DRAW_SYSTEM_TYPE:
        return False
    subtype = classify_bear_subtype(row)
    if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
        return _clean_lower(row.get("harvest_objective_status")) in {"unknown", "open", "closed", "source missing"}
    if subtype == UNLIMITED_PURSUIT_PERMIT:
        return _clean_lower(row.get("permit_availability_type")) == "unlimited_pursuit"
    return False


def _is_proven_bonus_bear_truth_row(row: Mapping[str, object]) -> bool:
    if not is_bear_row(row):
        return False
    if classify_bear_subtype(row) not in MODELED_BEAR_SUBTYPES:
        return False
    historical_pdf_classification = _historical_bear_pdf_classification(row)
    if not historical_pdf_classification and _clean_lower(row.get("draw_pool")) not in {"", "standard", "black_bear", "max_weighted_split"}:
        return False
    source_file = _clean_lower(row.get("source_file"))
    if source_file in {"database.csv", "sportsman_permit_no_draw_odds"}:
        return False
    return True


def _build_truth_ladders(
    truth_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> tuple[
    dict[tuple[str, int, str, str], dict[int, dict[str, int]]],
    dict[str, dict[str, str]],
    dict[tuple[str, int], dict[str, int]],
]:
    ladders: dict[tuple[str, int, str, str], dict[int, dict[str, int]]] = defaultdict(
        lambda: defaultdict(lambda: {"eligible": 0, "bonus": 0, "regular": 0, "total": 0})
    )
    meta: dict[str, dict[str, str]] = {}
    total_drawn_by_code_year: dict[tuple[str, int], dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for row in truth_rows:
        year = _to_int(row.get("year") or row.get("actual_draw_year"))
        if year not in history_years or not _is_proven_bonus_bear_truth_row(row):
            continue
        subtype = classify_bear_subtype(row)
        hunt_code = _clean(row.get("hunt_code")).upper()
        metric_scope = _clean_lower(row.get("metric_scope"))
        residency = _clean(row.get("residency"))
        if metric_scope == "total" or not residency:
            residency = "All"
        points = _to_int(row.get("points"))
        if not hunt_code:
            continue

        eligible = _to_int(row.get("eligible_applicants"))
        bonus = _to_int(row.get("bonus_permits"))
        regular = _to_int(row.get("regular_permits"))
        total = _to_int(row.get("total_permits"))
        ladders[(subtype, year, hunt_code, residency)][points]["eligible"] += eligible
        ladders[(subtype, year, hunt_code, residency)][points]["bonus"] += bonus
        ladders[(subtype, year, hunt_code, residency)][points]["regular"] += regular
        ladders[(subtype, year, hunt_code, residency)][points]["total"] += total
        total_drawn_by_code_year[(hunt_code, year)][residency] += total

        if hunt_code not in meta:
            meta[hunt_code] = {
                "hunt_name": _clean(row.get("hunt_name")),
                "species": _clean(row.get("species")),
                "hunt_type": _clean(row.get("hunt_type")),
                "hunt_class": _clean(row.get("hunt_class")),
                "weapon": _clean(row.get("weapon")),
                "sex_type": _clean(row.get("sex_type")),
                "source_file": _clean(row.get("source_file")),
            }

    return ladders, meta, total_drawn_by_code_year


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> tuple[dict[str, float], float]:
    retention_samples: dict[str, list[float]] = defaultdict(list)
    zero_growth_samples: list[float] = []
    years_by_subtype_code_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for subtype, year, hunt_code, residency in ladders:
        years_by_subtype_code_res[(subtype, hunt_code, residency)].append(year)

    for (subtype, hunt_code, residency), years in years_by_subtype_code_res.items():
        for prior_year in sorted(years):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(subtype, prior_year, hunt_code, residency)]
            nxt = ladders[(subtype, next_year, hunt_code, residency)]
            prior_zero = prior.get(0, {}).get("eligible", 0)
            next_zero = nxt.get(0, {}).get("eligible", 0)
            if prior_zero > 0:
                zero_growth_samples.append(max(0.25, min(2.0, next_zero / prior_zero)))
            for points, values in prior.items():
                unsuccessful = max(values["eligible"] - values["bonus"] - values["regular"], 0)
                if unsuccessful <= 0:
                    continue
                band = _band_for_points(points)
                next_count = nxt.get(points + 1, {}).get("eligible", 0)
                retention_samples[band].append(max(0.0, min(1.25, next_count / unsuccessful)))

    default_retention = {
        "0": 0.78,
        "1": 0.83,
        "2_3": 0.87,
        "4_5": 0.91,
        "6_9": 0.95,
        "10_plus": 0.98,
    }
    retention_by_band: dict[str, float] = {}
    for band, fallback in default_retention.items():
        samples = retention_samples.get(band, [])
        retention_by_band[band] = round(mean(samples), 4) if samples else fallback
    zero_growth = round(mean(zero_growth_samples), 4) if zero_growth_samples else 1.0
    return retention_by_band, zero_growth


def _forecast_applicant_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_by_band: Mapping[str, float],
    zero_growth: float,
) -> dict[int, int]:
    prior_points = sorted(int(points) for points in latest_ladder.keys())
    max_points = max(prior_points) if prior_points else 0
    tail_buffer = 4
    forecast: dict[int, int] = {}
    forecast[0] = _round_count(latest_ladder.get(0, {}).get("eligible", 0) * zero_growth)

    for points in range(1, max_points + tail_buffer + 1):
        prior_level = latest_ladder.get(points - 1, {})
        unsuccessful_prior = max(int(prior_level.get("eligible", 0)) - int(prior_level.get("bonus", 0)) - int(prior_level.get("regular", 0)), 0)
        retained = unsuccessful_prior * retention_by_band.get(_band_for_points(points - 1), 0.85)
        switch_proxy = int(latest_ladder.get(points, {}).get("eligible", 0)) * 0.08
        forecast[points] = _round_count(retained + switch_proxy)

    # Keep zero-tail ladder rows so the public PDF row structure stays aligned.
    # The official tables often include upper point levels with zero permits or
    # zero applicants, and dropping them creates row-key drift during blind
    # comparison even though those rows are still part of the source truth.
    return forecast


def _weighted_random_probability(points: int, applicants_by_points: Mapping[int, int], random_permits: int) -> float:
    total_weight = 0.0
    target_weight = 0.0
    for point_level, count in applicants_by_points.items():
        weight = max(0, int(count)) * max(1, int(point_level) + 1)
        total_weight += weight
        if int(point_level) == int(points):
            target_weight += weight
    if random_permits <= 0 or total_weight <= 0 or target_weight <= 0:
        return 0.0
    share = min(1.0, max(0.0, target_weight / total_weight))
    return max(0.0, min(1.0, 1.0 - ((1.0 - share) ** max(1, random_permits))))


def _guaranteed_level(ladder: Mapping[int, int], quota: int) -> int | None:
    running = 0
    guaranteed: int | None = None
    for points in sorted(ladder.keys(), reverse=True):
        applicants = max(int(ladder.get(points, 0)), 0)
        if applicants <= 0:
            continue
        if running + applicants <= quota:
            guaranteed = points
            running += applicants
            continue
        break
    return guaranteed


def _status(max_point_permits: int, random_permits: int, p_bonus_pool: float) -> str:
    if max_point_permits == 0 and random_permits > 0:
        return "RANDOM ONLY"
    if p_bonus_pool >= 0.999:
        return "MAX POOL"
    if p_bonus_pool > 0:
        return "ON EDGE"
    return "BEHIND"


def _draw_outlook(probability: float, pending: bool = False, excluded: bool = False, availability: bool = False) -> str:
    if availability:
        return "REMAINING PERMIT / AVAILABILITY"
    if excluded:
        return "NOT A DRAW"
    if pending:
        return "MODEL PENDING"
    if probability >= 0.75:
        return "GREEN LIGHT"
    if probability > 0.10:
        return "MAY DRAW IN 5-10 YEARS"
    return "RANDOM POOL RELIANCE" if probability > 0 else "POINT CREEP DEFEAT"


def _trend(prior_level: int | None, forecast_level: int | None) -> str:
    if prior_level is None and forecast_level is None:
        return "YELLOW"
    if prior_level is None:
        return "GREEN"
    if forecast_level is None:
        return "RED"
    if forecast_level > prior_level:
        return "GREEN"
    if forecast_level == prior_level:
        return "YELLOW"
    return "RED"


def _forecast_quota_for_residency(
    db_row: Mapping[str, object],
    residency: str,
    forecast_year: int,
    source_year: int | None = None,
) -> int:
    allocation = target_residency_permit_allocation(db_row, forecast_year, source_year=source_year)
    if not allocation.supported:
        return 0
    return allocation.for_residency(residency)


def _has_published_permit_split(db_row: Mapping[str, object]) -> bool:
    return any(
        _clean(db_row.get(field))
        for field in ("permits_2026_res", "permits_2026_nr", "permits_2026_total")
    )


def _has_known_zero_residency_quota(db_row: Mapping[str, object], residency: str) -> bool:
    if not _has_published_permit_split(db_row):
        return False
    total = _to_int(db_row.get("permits_2026_total"))
    if total <= 0:
        return False
    quota = _to_int(db_row.get("permits_2026_res" if residency == "Resident" else "permits_2026_nr"))
    return quota <= 0


def _data_quality_flags(
    available_years: list[int],
    total_applicants: int,
    public_quota: int,
    max_point_permits: int,
    subtype: str,
) -> list[str]:
    flags: list[str] = ["FIRST_CHOICE_ONLY_MODEL"]
    if len(available_years) == 1:
        flags.append("MISSING_MULTIPLE_YEARS")
    if total_applicants < 5:
        flags.append("LOW_APPLICANT_COUNT")
    if public_quota == 1 and max_point_permits == 0:
        flags.append("ONE_PERMIT_RANDOM_ONLY")
    if max_point_permits == 0 and public_quota > 0:
        flags.append("NO_MAX_POINT_POOL")
    return flags


def _permit_availability_type(subtype: str) -> str:
    if subtype == STATEWIDE_BEAR_PERMIT:
        return "STATEWIDE_PERMIT"
    if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
        return "HARVEST_OBJECTIVE"
    if subtype == UNLIMITED_PURSUIT_PERMIT:
        return "UNLIMITED_PURSUIT"
    if subtype == RESTRICTED_BEAR_PURSUIT:
        return "RESTRICTED_PURSUIT_BONUS_DRAW"
    if subtype == REMAINING_PERMIT_AVAILABILITY:
        return "REMAINING_PERMIT"
    if subtype == CONSERVATION_OR_NON_PUBLIC:
        return "NON_PUBLIC_EXCLUDED"
    if subtype in MODELED_BEAR_SUBTYPES:
        return "DRAW_ODDS"
    return "UNKNOWN"


def _base_row(
    *,
    forecast_year: int,
    source_years_used_text: str,
    source_year_count: int,
    earliest_source_year: int,
    latest_source_year: int,
    hunt_code: str,
    hunt_name: str,
    species: str,
    sex_type: str,
    hunt_type: str,
    hunt_class: str,
    residency: str,
    public_permits_2025: int,
    public_permits_2026: int,
    weapon: str,
    subtype: str,
    season_dates: str = "",
) -> dict[str, object]:
    return {
        "model_version": MODEL_VERSION,
        "rule_version": BONUS_RULE_VERSION,
        "year": str(forecast_year),
        "forecast_year": str(forecast_year),
        "hunt_code": hunt_code,
        "hunt_name": hunt_name,
        "species": species,
        "sex_type": sex_type,
        "hunt_type": hunt_type,
        "hunt_class": hunt_class,
        "residency": residency,
        "draw_pool": "standard",
        "public_permits_2025": public_permits_2025,
        "public_permits_2026": public_permits_2026,
        "source_years_used": source_years_used_text,
        "source_year_count": source_year_count,
        "latest_source_year": latest_source_year,
        "earliest_source_year": earliest_source_year,
        "source_dataset": "predictive",
        "model_strategy": MODEL_STRATEGY_NAME,
        "weapon": weapon,
        "draw_system_type": BEAR_DRAW_SYSTEM_TYPE,
        "bear_draw_subtype": subtype,
        "permit_availability_type": _permit_availability_type(subtype),
        "season_dates": season_dates,
        "harvest_objective_unit_count": "",
        "harvest_objective_take_quota": "",
        "harvest_objective_remaining_quota": "",
        "harvest_objective_status": "",
        "unit_status": "",
        "availability_reason": "",
        "probability_model": "",
        "reason_codes": "",
        "rule_status": "",
        "p_availability": "",
        "availability_pct": "",
        "closure_risk": "",
        "sellout_or_closure_risk": "",
    }


def build_bear_draw_odds_source_audit(
    db_rows: Iterable[Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    official_rows = _parse_official_bear_draw_odds_pdf()
    bear_db_rows: dict[str, Mapping[str, object]] = {}
    for row in db_rows:
        hunt_code = _clean(row.get("hunt_code")).upper()
        if not hunt_code or not is_bear_row(row):
            continue
        bear_db_rows.setdefault(hunt_code, row)

    audit_rows: list[dict[str, object]] = []
    corrected_pursuit_codes: list[str] = []
    pursuit_codes_in_pdf = sorted(official_bear_pursuit_hunt_codes())

    for hunt_code in sorted(bear_db_rows):
        row = bear_db_rows[hunt_code]
        official = official_rows.get(hunt_code, {})
        before = classify_bear_subtype_before_source_correction(row)
        after = classify_bear_subtype(row)
        text = _joined_text(row)
        if hunt_code == "BR1000" or is_sportsman_permit_row(row):
            source_classification = "SPORTSMAN_PERMIT"
            flags = ["SPORTSMAN_SEPARATE"]
        elif hunt_code == "BR1001" or "harvest objective" in text:
            source_classification = "BEAR_HARVEST_OBJECTIVE_AVAILABILITY"
            flags = ["HARVEST_OBJECTIVE_SOURCE"]
        elif hunt_code in {"BR1007", "BR1018"}:
            source_classification = "BEAR_UNLIMITED_PURSUIT_AVAILABILITY"
            flags = ["UNLIMITED_PURSUIT_SOURCE"]
        elif official:
            source_classification = str(official.get("source_classification"))
            flags = ["OFFICIAL_BEAR_DRAW_ODDS_SOURCE"]
            if source_classification == "BEAR_PURSUIT_BONUS_DRAW":
                flags.append("PURSUIT_BONUS_SOURCE_PROVEN")
        elif any(token in text for token in ("conservation", "expo", "private", "sportsman", "landowner", "voucher")):
            source_classification = "CONSERVATION_OR_NON_PUBLIC"
            flags = ["NON_PUBLIC_OR_EXCLUDED_SOURCE"]
        elif any(token in text for token in ("remaining permit", " otc", "over the counter")):
            source_classification = "BEAR_REMAINING_OR_OTC_AVAILABILITY"
            flags = ["REMAINING_OR_OTC_SOURCE_ONLY"]
        else:
            source_classification = "UNKNOWN_FROM_SOURCE"
            flags = ["SOURCE_CLASSIFICATION_AMBIGUOUS"]

        correction_needed = before != after
        if correction_needed and source_classification == "BEAR_PURSUIT_BONUS_DRAW":
            corrected_pursuit_codes.append(hunt_code)

        audit_rows.append(
            {
                "hunt_code": hunt_code,
                "hunt_name": _clean(row.get("hunt_name")),
                "source_year": official.get("source_year", BEAR_DRAW_ODDS_SOURCE_YEAR if official else ""),
                "source_file": official.get("source_file", "pipeline/RAW/hunt_unit_database/2026/csv/2026 Permits/black bear.csv"),
                "appears_in_draw_odds_pdf": "yes" if official else "no",
                "has_point_level_bonus_rows": "yes" if official else "no",
                "resident_bonus_permits_total": official.get("resident_bonus_permits_total", ""),
                "resident_regular_permits_total": official.get("resident_regular_permits_total", ""),
                "resident_total_permits": official.get("resident_total_permits", ""),
                "nonresident_bonus_permits_total": official.get("nonresident_bonus_permits_total", ""),
                "nonresident_regular_permits_total": official.get("nonresident_regular_permits_total", ""),
                "nonresident_total_permits": official.get("nonresident_total_permits", ""),
                "source_classification": source_classification,
                "engine_classification_before": before,
                "engine_classification_after": after,
                "correction_needed": "yes" if correction_needed else "no",
                "data_quality_flags": "|".join(flags),
            }
        )

    summary = {
        "source_year": BEAR_DRAW_ODDS_SOURCE_YEAR,
        "source_file": BEAR_DRAW_ODDS_SOURCE_RELATIVE,
        "source_status": "AVAILABLE" if BEAR_DRAW_ODDS_SOURCE_PDF.exists() else "MISSING_REPO_EXTERNAL_SOURCE",
        "blocker": not BEAR_DRAW_ODDS_SOURCE_PDF.exists(),
        "production_ready": BEAR_DRAW_ODDS_SOURCE_PDF.exists(),
        "bear_hunt_codes_found_in_official_draw_odds_pdf": len(official_rows),
        "bear_pursuit_hunt_codes_found_in_official_draw_odds_pdf": len(pursuit_codes_in_pdf),
        "pursuit_hunt_codes_found_in_official_draw_odds_pdf": pursuit_codes_in_pdf,
        "pursuit_rows_corrected_from_availability_to_modeled_bonus": len(corrected_pursuit_codes),
        "pursuit_hunt_codes_corrected": sorted(corrected_pursuit_codes),
        "rows": audit_rows,
    }
    return audit_rows, summary


def _read_br7307_2025_supplemental_ladder() -> list[dict[str, object]]:
    if not BR7307_2025_SUPPLEMENTAL_LADDER.exists():
        return []
    if BR7307_2025_SUPPLEMENTAL_LADDER.suffix.lower() == ".json":
        return list(json.loads(BR7307_2025_SUPPLEMENTAL_LADDER.read_text(encoding="utf-8")))
    with BR7307_2025_SUPPLEMENTAL_LADDER.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _with_supplemental_bear_truth_rows(
    truth_rows: list[Mapping[str, object]],
    history_year_set: set[int],
) -> list[Mapping[str, object]]:
    if 2025 not in history_year_set:
        return truth_rows
    has_scorable_br7307_2025 = any(
        _to_int(row.get("actual_draw_year") or row.get("year")) == 2025
        and _clean(row.get("hunt_code")).upper() == "BR7307"
        and _is_proven_bonus_bear_truth_row(row)
        for row in truth_rows
    )
    if has_scorable_br7307_2025:
        return truth_rows
    supplemental = _read_br7307_2025_supplemental_ladder()
    if not supplemental:
        return truth_rows
    return [*truth_rows, *supplemental]


def build_bear_bonus_predictions(
    truth_rows: Iterable[Mapping[str, object]],
    db_rows: Iterable[Mapping[str, object]],
    forecast_year: int,
    history_years: list[int],
) -> tuple[list[dict[str, object]], dict[str, object]]:
    truth_rows_list = list(truth_rows)
    history_years = _history_years_or_bootstrap(history_years, truth_rows_list)
    if not history_years:
        return [], _skipped_no_history_report(forecast_year)
    history_year_set = {int(year) for year in history_years}
    truth_rows_list = _with_supplemental_bear_truth_rows(truth_rows_list, history_year_set)
    source_years_used_text = ",".join(str(year) for year in history_years)
    source_year_count = len(history_years)
    default_earliest_source_year = min(history_years)
    default_latest_source_year = max(history_years)
    ladders, meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows_list, history_year_set)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    years_by_subtype_code_res: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for subtype, year, hunt_code, residency in ladders:
        years_by_subtype_code_res[(subtype, hunt_code, residency)].append(year)

    def history_context(
        subtype: str,
        hunt_code: str,
        residency: str,
    ) -> tuple[str, list[int], str]:
        exact_years = sorted(set(years_by_subtype_code_res.get((subtype, hunt_code, residency), [])))
        if exact_years:
            return residency, exact_years, ""
        total_years = sorted(set(years_by_subtype_code_res.get((subtype, hunt_code, "All"), [])))
        if total_years:
            return "All", total_years, "TOTAL_SCOPE_HISTORY_USED_FOR_RESIDENCY"
        return residency, [], ""

    rows: list[dict[str, object]] = []
    report_counts = Counter()
    data_quality_counter: Counter[str] = Counter()
    review_rows: list[dict[str, object]] = []

    for db_row in db_rows:
        if not is_bear_row(db_row):
            continue
        if _clean(db_row.get("hunt_code")).upper() == "BR1000" or "sportsman" in _joined_text(db_row):
            continue
        review_rows.append(dict(db_row))

        hunt_code = _clean(db_row.get("hunt_code")).upper()
        if not hunt_code:
            continue
        if hunt_code in BEAR_HISTORICAL_CODE_SUCCESSORS_2026:
            report_counts["historical_successor_skipped"] += 1
            continue
        history_hunt_code = BEAR_HISTORY_CODE_ALIASES_2026.get(hunt_code, hunt_code)
        subtype = classify_bear_subtype(db_row)
        hunt_name = _clean(db_row.get("hunt_name")) or meta.get(hunt_code, {}).get("hunt_name", "")
        species = _clean(db_row.get("species")) or meta.get(hunt_code, {}).get("species", "Black Bear")
        sex_type = _clean(db_row.get("sex_type")) or meta.get(hunt_code, {}).get("sex_type", "")
        hunt_type = _clean(db_row.get("hunt_type")) or meta.get(hunt_code, {}).get("hunt_type", "")
        weapon = _clean(db_row.get("weapon")) or meta.get(hunt_code, {}).get("weapon", "")
        season_dates = _clean(db_row.get("season"))
        hunt_class = "Public"
        if subtype == CONSERVATION_OR_NON_PUBLIC:
            hunt_class = _clean(db_row.get("hunt_class")) or "Non-Public / Excluded"

        residencies = ("Resident", "Nonresident")
        if subtype == UNLIMITED_PURSUIT_PERMIT:
            if hunt_code == "BR1007":
                residencies = ("Resident",)
            elif hunt_code == "BR1018":
                residencies = ("Nonresident",)
            else:
                has_resident_line = (
                    _to_int(db_row.get("permit_allotment_2026_res")) > 0
                    or _to_int(db_row.get("permits_2026_res")) > 0
                    or "res:" in _clean_lower(db_row.get("permit_allotment_2026_total"))
                    or "res:" in _clean_lower(db_row.get("permits_2026_total"))
                )
                has_nonresident_line = (
                    _to_int(db_row.get("permit_allotment_2026_nr")) > 0
                    or _to_int(db_row.get("permits_2026_nr")) > 0
                    or "nonres:" in _clean_lower(db_row.get("permit_allotment_2026_total"))
                    or "nonres:" in _clean_lower(db_row.get("permits_2026_total"))
                )
                if has_resident_line and has_nonresident_line:
                    residencies = ("Resident", "Nonresident")
                elif has_resident_line:
                    residencies = ("Resident",)
                elif has_nonresident_line:
                    residencies = ("Nonresident",)
                else:
                    residencies = ("Resident", "Nonresident")

        for residency in residencies:
            history_residency, available_years, history_scope_flag = history_context(subtype, history_hunt_code, residency)
            latest_year = available_years[-1] if available_years else default_latest_source_year
            earliest_source_year = available_years[0] if available_years else default_earliest_source_year
            latest_ladder = ladders.get((subtype, latest_year, history_hunt_code, history_residency), {}) if available_years else {}
            prior_total = sum(int(values.get("total", 0)) for values in latest_ladder.values())
            public_quota = _forecast_quota_for_residency(
                db_row,
                residency,
                forecast_year,
                source_year=latest_year,
            )
            base = _base_row(
                forecast_year=forecast_year,
                source_years_used_text=source_years_used_text,
                source_year_count=source_year_count,
                earliest_source_year=earliest_source_year,
                latest_source_year=latest_year,
                hunt_code=hunt_code,
                hunt_name=hunt_name,
                species=species,
                sex_type=sex_type,
                hunt_type=hunt_type,
                hunt_class=hunt_class,
                residency=residency,
                public_permits_2025=prior_total,
                public_permits_2026=public_quota,
                weapon=weapon,
                subtype=subtype,
                season_dates=season_dates,
            )
            base["history_hunt_code"] = history_hunt_code
            base["crosswalk_status"] = "DIRECT_HISTORICAL_TO_CURRENT_CODE" if history_hunt_code != hunt_code else ""

            if subtype == UNLIMITED_PURSUIT_PERMIT:
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": _draw_outlook(0.0, excluded=True, availability=True),
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Unlimited pursuit availability is not a draw-odds row.",
                        "availability_status": "PURSUIT-ONLY AVAILABLE",
                        "availability_reason": "Unlimited pursuit permit is a pursuit-only availability row, not a harvested-bear draw-odds row.",
                        "probability_model": "NONE",
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "AVAILABILITY_ONLY_NO_DRAW_PROBABILITY",
                            "BEAR_PURSUIT_ONLY_STATUS",
                        ),
                        "data_quality_flags": "",
                        "unit_status": "OPEN",
                        "rule_status": "PURSUIT_ONLY_NON_HARVEST",
                        "p_availability": "1.000000",
                        "availability_pct": "100.000",
                        "closure_risk": "NONE",
                        "sellout_or_closure_risk": "NONE",
                    }
                )
                rows.append(row)
                report_counts["availability"] += 1
                continue

            if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": "REMAINING PERMIT / AVAILABILITY",
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Harvest objective is surfaced as availability/rule-status, not draw odds.",
                        "availability_status": "HARVEST OBJECTIVE STATUS UNKNOWN",
                        "availability_reason": "Harvest objective source confirms status/closure semantics rather than modeled draw odds.",
                        "probability_model": "NONE",
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "AVAILABILITY_ONLY_NO_DRAW_PROBABILITY",
                            "BEAR_HARVEST_OBJECTIVE_STATUS",
                        ),
                        "data_quality_flags": "BEAR_HO_SOURCE_MISSING",
                        "harvest_objective_status": "SOURCE MISSING",
                        "unit_status": "UNKNOWN",
                        "rule_status": "HARVEST_OBJECTIVE_RULE_STATUS",
                    }
                )
                data_quality_counter["BEAR_HO_SOURCE_MISSING"] += 1
                rows.append(row)
                report_counts["availability"] += 1
                continue

            if subtype in EXCLUDED_BEAR_SUBTYPES or (subtype == STATEWIDE_BEAR_PERMIT and is_excluded_bear_row(base)):
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": _draw_outlook(0.0, excluded=True, availability=subtype in {HARVEST_OBJECTIVE_AVAILABILITY, REMAINING_PERMIT_AVAILABILITY}),
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Bear row is in scope, but this subtype is not a predictive public draw-probability target.",
                        "data_quality_flags": "",
                    }
                )
                rows.append(row)
                report_counts["excluded"] += 1
                continue

            if subtype not in MODELED_BEAR_SUBTYPES:
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": _draw_outlook(0.0, pending=True),
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Bear subtype could not be cleanly proven from public draw source data.",
                        "data_quality_flags": "BEAR_SUBTYPE_AMBIGUOUS",
                    }
                )
                data_quality_counter["BEAR_SUBTYPE_AMBIGUOUS"] += 1
                rows.append(row)
                report_counts["pending"] += 1
                continue

            if public_quota <= 0 and _has_known_zero_residency_quota(db_row, residency):
                flags = ["KNOWN_ZERO_RESIDENCY_QUOTA", "FIRST_CHOICE_ONLY_MODEL"]
                for flag in flags:
                    data_quality_counter[flag] += 1
                row = dict(base)
                row.update(
                    {
                        "points": "0",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": "NO PERMITS FOR RESIDENCY",
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Published 2026 permit split assigns zero permits to this residency.",
                        "data_quality_flags": "|".join(flags),
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "KNOWN_ZERO_RESIDENCY_QUOTA",
                            "NO_PUBLIC_DRAW_PROBABILITY_FOR_RESIDENCY",
                        ),
                    }
                )
                rows.append(row)
                report_counts["excluded"] += 1
                continue

            if not available_years or public_quota <= 0:
                flags = []
                if not available_years:
                    flags.append("MISSING_PROVEN_BEAR_DRAW_HISTORY")
                elif history_hunt_code != hunt_code:
                    flags.append("CURRENT_TO_HISTORICAL_CODE_ALIAS")
                if public_quota <= 0:
                    flags.append("MISSING_FORECAST_QUOTA")
                if history_scope_flag:
                    flags.append(history_scope_flag)
                flags.append("FIRST_CHOICE_ONLY_MODEL")
                for flag in flags:
                    data_quality_counter[flag] += 1
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": _draw_outlook(0.0, pending=True),
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Missing proven bear history or usable 2026 public quota for this residency.",
                        "data_quality_flags": "|".join(flags),
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            BEAR_NO_PRIOR_LADDER_REASON_CODE if "MISSING_PROVEN_BEAR_DRAW_HISTORY" in flags else "",
                            "NO_PUBLIC_DRAW_PROBABILITY_FOR_RESIDENCY" if public_quota <= 0 else "",
                        ),
                    }
                )
                rows.append(row)
                report_counts["pending"] += 1
                continue

            split = split_utah_bonus_permits(public_quota, residency)
            max_point_permits = split.maxPointPermits
            random_permits = split.randomPermits
            forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
            if not forecast_ladder:
                flags = ["LOW_APPLICANT_COUNT", "FIRST_CHOICE_ONLY_MODEL"]
                for flag in flags:
                    data_quality_counter[flag] += 1
                row = dict(base)
                row.update(
                    {
                        "points": "",
                        "p_preference_draw": "",
                        "p_bonus_pool": "",
                        "p_random_pool": "",
                        "p_draw": "",
                        "p_bonus_pool_pct": "",
                        "p_random_pool_pct": "",
                        "p_draw_pct": "",
                        "draw_outlook": _draw_outlook(0.0, pending=True),
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "Proven bear history existed, but the forecast ladder was empty.",
                        "data_quality_flags": "|".join(flags),
                    }
                )
                rows.append(row)
                report_counts["pending"] += 1
                continue

            prior_guaranteed = _guaranteed_level({points: int(values.get("eligible", 0)) for points, values in latest_ladder.items()}, prior_total)
            forecast_guaranteed = _guaranteed_level(forecast_ladder, public_quota)
            total_applicants = sum(forecast_ladder.values())
            flags = _data_quality_flags(available_years, total_applicants, public_quota, max_point_permits, subtype)
            if history_hunt_code != hunt_code:
                flags.append("CURRENT_TO_HISTORICAL_CODE_ALIAS")
            if history_scope_flag:
                flags.append(history_scope_flag)
            for flag in flags:
                data_quality_counter[flag] += 1

            for points in sorted(forecast_ladder.keys(), reverse=True):
                applicants_by_points = {int(level): int(count) for level, count in forecast_ladder.items()}
                p_bonus_pool, applicants_above, applicants_at_level = compute_bonus_pool_probability(points, applicants_by_points, max_point_permits)
                p_random_pool = _weighted_random_probability(points, applicants_by_points, random_permits)
                p_draw = combine_probabilities(p_bonus_pool, p_random_pool)
                row = dict(base)
                row.update(
                    {
                        "points": str(points),
                        "max_point_permits_2025": "",
                        "max_point_permits_2026": max_point_permits,
                        "random_permits_2025": "",
                        "random_permits_2026": random_permits,
                        "guaranteed_at_2025": "" if prior_guaranteed is None else str(prior_guaranteed),
                        "guaranteed_at_2026": "" if forecast_guaranteed is None else str(forecast_guaranteed),
                        "applicants_above": applicants_above,
                        "applicants_at_level": applicants_at_level,
                        "p_preference_draw": "",
                        "p_bonus_pool": f"{p_bonus_pool:.6f}",
                        "p_random_pool": f"{p_random_pool:.6f}",
                        "p_draw": f"{p_draw:.6f}",
                        "p_bonus_pool_pct": f"{p_bonus_pool * 100.0:.3f}",
                        "p_random_pool_pct": f"{p_random_pool * 100.0:.3f}",
                        "p_draw_pct": f"{p_draw * 100.0:.3f}",
                        "random_draw_odds_2026": f"{p_random_pool * 100.0:.3f}",
                        "gap": "" if forecast_guaranteed is None else str(forecast_guaranteed - points),
                        "delta_gap": "" if forecast_guaranteed is None or prior_guaranteed is None else str((forecast_guaranteed - points) - (prior_guaranteed - points)),
                        "status": _status(max_point_permits, random_permits, p_bonus_pool),
                        "trend": _trend(prior_guaranteed, forecast_guaranteed),
                        "draw_outlook": _draw_outlook(p_draw),
                        "bear_bonus_valid": "TRUE",
                        "bear_bonus_note": f"Forecasted from {latest_year} public bear draw history with Utah bonus split rules.",
                        "data_quality_flags": "|".join(flags),
                    }
                )
                rows.append(row)
                report_counts["modeled"] += 1

    observed_history_rows = [row for row in truth_rows if is_bear_row(row)]
    review_counter = Counter(classify_bear_subtype(row) for row in review_rows)
    modeled_rows = [row for row in rows if _clean(row.get("bear_bonus_valid")) == "TRUE"]

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_bear_rows_reviewed": len(review_rows),
        "bear_rows_seen_observed_history": len(observed_history_rows),
        "bear_rows_seen_active_predictive": len(rows),
        "bear_rows_by_bear_draw_subtype": dict(sorted(review_counter.items())),
        "bear_rows_by_algorithm_status": {
            "MODELED_BONUS": report_counts["modeled"],
            "MODELED_AVAILABILITY": report_counts["availability"],
            "IN_SCOPE_MODEL_PENDING": report_counts["pending"],
            "EXCLUDED_NOT_PREDICTIVE_DRAW": report_counts["excluded"],
        },
        "historical_successor_current_rows_skipped": report_counts["historical_successor_skipped"],
        "bear_draw_active_predictive_row_count": len(rows),
        "bear_draw_modeled_row_count": report_counts["modeled"],
        "bear_draw_pending_row_count": report_counts["pending"],
        "bear_draw_excluded_non_draw_row_count": report_counts["excluded"],
        "modeled_bear_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in modeled_rows if str(row.get("hunt_code", "")).strip()}),
        "limited_entry_bear_modeled_row_count": sum(1 for row in modeled_rows if row.get("bear_draw_subtype") == LIMITED_ENTRY_BEAR_HUNT),
        "restricted_pursuit_modeled_row_count": sum(1 for row in modeled_rows if row.get("bear_draw_subtype") == RESTRICTED_BEAR_PURSUIT),
        "limited_entry_hunt_modeled_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in modeled_rows if row.get("bear_draw_subtype") == LIMITED_ENTRY_BEAR_HUNT and str(row.get("hunt_code", "")).strip()}),
        "restricted_pursuit_modeled_hunt_code_count": len({str(row.get("hunt_code", "")).strip() for row in modeled_rows if row.get("bear_draw_subtype") == RESTRICTED_BEAR_PURSUIT and str(row.get("hunt_code", "")).strip()}),
        "harvest_objective_excluded_or_availability_pending_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == HARVEST_OBJECTIVE_AVAILABILITY),
        "remaining_permit_excluded_or_availability_pending_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == REMAINING_PERMIT_AVAILABILITY),
        "statewide_bear_permit_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == STATEWIDE_BEAR_PERMIT),
        "statewide_bear_permit_modeled_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == STATEWIDE_BEAR_PERMIT and row.get("algorithm_status") == "MODELED_BONUS"),
        "statewide_bear_permit_pending_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == STATEWIDE_BEAR_PERMIT and row.get("algorithm_status") == "IN_SCOPE_MODEL_PENDING"),
        "statewide_bear_permit_excluded_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == STATEWIDE_BEAR_PERMIT and row.get("algorithm_status") == "EXCLUDED_NOT_PREDICTIVE_DRAW"),
        "statewide_bear_permit_p_draw_non_null_count": sum(1 for row in rows if row.get("bear_draw_subtype") == STATEWIDE_BEAR_PERMIT and _clean(row.get("p_draw"))),
        "harvest_objective_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == HARVEST_OBJECTIVE_AVAILABILITY),
        "harvest_objective_p_draw_non_null_count": sum(1 for row in rows if row.get("bear_draw_subtype") == HARVEST_OBJECTIVE_AVAILABILITY and _clean(row.get("p_draw"))),
        "harvest_objective_availability_fields_populated_count": sum(
            1
            for row in rows
            if row.get("bear_draw_subtype") == HARVEST_OBJECTIVE_AVAILABILITY
            and any(_clean(row.get(field)) for field in ("p_availability", "availability_pct", "harvest_objective_take_quota", "harvest_objective_status"))
        ),
        "unlimited_pursuit_permit_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == UNLIMITED_PURSUIT_PERMIT),
        "unlimited_pursuit_permit_p_draw_non_null_count": sum(1 for row in rows if row.get("bear_draw_subtype") == UNLIMITED_PURSUIT_PERMIT and _clean(row.get("p_draw"))),
        "sportsman_bear_row_count": sum(1 for row in db_rows if _clean(row.get("hunt_code")).upper() == "BR1000"),
        "sportsman_bear_p_sportsman_draw_non_null_count": 1 if any(_clean(row.get("hunt_code")).upper() == "BR1000" for row in db_rows) else 0,
        "conservation_or_non_public_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == CONSERVATION_OR_NON_PUBLIC),
        "conservation_or_non_public_p_draw_non_null_count": sum(1 for row in rows if row.get("bear_draw_subtype") == CONSERVATION_OR_NON_PUBLIC and _clean(row.get("p_draw"))),
        "non_public_excluded_bear_row_count": sum(1 for row in rows if row.get("bear_draw_subtype") == CONSERVATION_OR_NON_PUBLIC),
        "p_bonus_pool_non_null_count": sum(1 for row in rows if _clean(row.get("p_bonus_pool"))),
        "p_random_pool_non_null_count": sum(1 for row in rows if _clean(row.get("p_random_pool"))),
        "p_draw_non_null_count": sum(1 for row in rows if _clean(row.get("p_draw"))),
        "p_draw_pct_non_null_count": sum(1 for row in rows if _clean(row.get("p_draw_pct"))),
        "p_preference_draw_non_null_count": sum(1 for row in rows if _clean(row.get("p_preference_draw"))),
        "p_draw_outside_0_1_count": sum(1 for row in rows if _clean(row.get("p_draw")) and not (0.0 <= float(str(row.get("p_draw"))) <= 1.0)),
        "p_draw_pct_outside_0_100_count": sum(1 for row in rows if _clean(row.get("p_draw_pct")) and not (0.0 <= float(str(row.get("p_draw_pct"))) <= 100.0)),
        "duplicate_key_count": len(rows) - len({(str(row.get("hunt_code", "")).strip(), str(row.get("residency", "")).strip(), str(row.get("points", "")).strip()) for row in rows}),
        "pending_rows_with_p_draw_count": sum(1 for row in rows if _clean(row.get("algorithm_status")) == "IN_SCOPE_MODEL_PENDING" and _clean(row.get("p_draw"))),
        "source_years_used_non_null_count": sum(1 for row in rows if _clean(row.get("source_years_used"))),
        "first_choice_only_model_count": sum(1 for row in rows if "FIRST_CHOICE_ONLY_MODEL" in _clean(row.get("data_quality_flags")).split("|")),
        "bear_subtype_ambiguous_count": sum(1 for row in rows if "BEAR_SUBTYPE_AMBIGUOUS" in _clean(row.get("data_quality_flags")).split("|")),
        "multiseason_limited_entry_bear_modeled_row_count": sum(
            1 for row in modeled_rows if "multiseason" in _clean_lower(row.get("hunt_type"))
        ),
        "spot_and_stalk_bear_modeled_row_count": sum(
            1 for row in modeled_rows if "spot and stalk" in _clean_lower(row.get("hunt_type"))
        ),
        "data_quality_flags_summary": dict(sorted(data_quality_counter.items())),
    }
    return rows, report
