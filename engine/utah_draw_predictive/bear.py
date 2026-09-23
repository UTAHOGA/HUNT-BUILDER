"""Bear subtype helpers and source-backed predictive logic for Utah bear rows."""

from __future__ import annotations

import re
import csv
import json
import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
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
from .permit_accessors import target_residency_permit_allocation


MODEL_STRATEGY_NAME = "bear_bonus_phase9_candidate"
# New default priors and arrival constants are unvalidated candidate behavior.
# Saved phase8 forecasts retain their own implementation hashes and labels.
BONUS_RULE_VERSION = "utah_bear_bonus_v1.0.0"
FUTURE_BEAR_DRAW_PROBABILITY_CEILING = 0.99
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

# Current non-draw catalog products, not the limited-entry hunt inventory.
# Do not expand from a Pursuit Only/OTC label or from an old saved row count.
BEAR_AVAILABILITY_PRODUCTS = {
    "BR1001": (HARVEST_OBJECTIVE_AVAILABILITY, ("Resident", "Nonresident")),
    "BR1007": (UNLIMITED_PURSUIT_PERMIT, ("Resident",)),
    "BR1018": (UNLIMITED_PURSUIT_PERMIT, ("Nonresident",)),
}

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
# Lineage only: a boundary split is not permission to inherit applicants.
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
    # The historical public-draw multiseason row moved to BR7326.  BR7307
    # was reused in 2026 for a conservation allocation and must never be
    # materialized as a duplicate public-draw forecast.
    "BR7307": "BR7326",
}
BEAR_SPLIT_HISTORY_START = dict.fromkeys(
    ("BR7021", "BR7022", "BR7126", "BR7127", "BR7238", "BR7239", "BR7326"), 2026
)
# Reviewed current permit references, NOT source-year awards or modeled quota.
# Whole-hunt totals from the retained 2024/2025/2026 crosswalk; no R/NR split
# is inferred here. This dated display context is never used in earlier folds.
BEAR_SPLIT_REFERENCE_TOTALS_2026 = {
    "BR7021": 2, "BR7022": 43, "BR7126": 6, "BR7127": 27,
    "BR7238": 2, "BR7239": 6, "BR7326": 14,
}
BEAR_SPLIT_REFERENCE_SOURCE = (
    "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv|"
    "data_truth/crosswalk_truth/normalized/black_bear_BR_2024_2025_2026_crosswalk.csv"
)

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


@dataclass(frozen=True)
class _BearCohortEvidence:
    """Aggregate public-ladder evidence for one source-to-target cohort.

    DWR's public reports do not identify people.  ``retained`` is therefore
    the portion of the next-year same-lane rung that can be supplied by the
    preceding year's unsuccessful cohort; any excess is retained separately as
    a measured arrival, rather than being silently treated as reapplication.
    """

    transitions: int = 0
    unsuccessful: int = 0
    retained: int = 0
    arrivals: int = 0


@dataclass(frozen=True)
class _BearCohortCalibration:
    reapply_rate: float
    arrival_count: float
    evidence_scope: str
    exact_unsuccessful: int
    exact_transitions: int


@dataclass(frozen=True)
class _BearLaneCohortModel:
    exact_rung: Mapping[tuple[str, str, str, int], _BearCohortEvidence]
    lane_band: Mapping[tuple[str, str, str, str], _BearCohortEvidence]
    subtype_residency_band: Mapping[tuple[str, str, str], _BearCohortEvidence]
    residency_band: Mapping[tuple[str, str], _BearCohortEvidence]


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
    """Use retained-PDF identity only for verified lane evidence.

    Some 2018-2020 canonical rows preserve a generic legacy draw label even
    though the retained official Black Bear PDF page identifies the program.
    The residency-lane audit projection and a canonical row promoted from that
    hash-linked evidence carry the exact page classification forward in
    dedicated fields. Do not infer it from a code prefix, permit count, or a
    generic legacy draw label.
    """

    classification = _clean(row.get("bear_source_classification")).upper()
    source = _clean(row.get("bear_source_identity_source")).upper()
    source_file = _clean_lower(row.get("bear_source_identity_file") or row.get("source_file")).replace("\\", "/")
    qa_status = _clean(row.get("qa_status")).upper()
    hunt_code = _clean(row.get("hunt_code")).upper()
    if (
        classification not in HISTORICAL_BEAR_PDF_CLASSIFICATIONS
        or source not in {
            "RETAINED_OFFICIAL_BLACK_BEAR_PDF",
            "CANONICAL_OFFICIAL_BLACK_BEAR_PDF",
        }
        or not hunt_code.startswith("BR")
        or "/official_dwr_archive/black_bear/" not in f"/{source_file.lstrip('/')}"
        or qa_status not in {
            "OFFICIAL_PDF_RESIDENCY_LANE_PROJECTED",
            "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL",
        }
    ):
        return ""
    return classification


def _canonical_official_bear_residency_lanes(row: Mapping[str, object]) -> list[dict[str, object]]:
    """Expand a verified canonical Bear point record into DWR residency lanes.

    Canonical records retain a combined row so they remain reversible to the
    original report shape.  The model reads the published lane columns only
    when either explicit PDF-lane provenance is present *or* an accepted
    canonical record retains all eight published lane counts and they
    reconcile exactly to the combined count at that point rung.  The latter
    covers older retained DWR reports whose canonical promotion predated the
    dedicated Bear-PDF identity fields.  It is not a residency split inferred
    from totals: both published lanes already exist in the canonical row.
    """
    if _clean(row.get("residency")) or _clean_lower(row.get("metric_scope")) not in {"", "total"}:
        return []

    explicit_pdf_lanes = (
        _clean(row.get("qa_status")).upper() == "OFFICIAL_PDF_RESIDENCY_LANES_CANONICAL"
        and _clean(row.get("bear_source_identity_source")).upper() == "CANONICAL_OFFICIAL_BLACK_BEAR_PDF"
        and bool(_historical_bear_pdf_classification(row))
    )
    accepted_canonical = any(
        token in _clean(row.get("candidate_promotion_status")).upper()
        for token in ("CANONICAL", "ACCEPTED", "PROMOTED", "CONFIRMED")
    )
    lane_count_fields = (
        "eligible_applicants",
        "bonus_permits",
        "regular_permits",
        "total_permits",
    )
    accepted_canonical = accepted_canonical or bool(_canonical_bear_program(row))
    reconciled_published_lanes = bool(_clean(row.get("source_file"))) and (accepted_canonical or explicit_pdf_lanes)
    for field in lane_count_fields:
        resident_value = _clean(row.get(f"resident_{field}"))
        nonresident_value = _clean(row.get(f"nonresident_{field}"))
        if not resident_value or not nonresident_value:
            reconciled_published_lanes = False
            break
        if _to_int(resident_value) + _to_int(nonresident_value) != _to_int(
            row.get(f"total_{field}") or row.get(field)
        ):
            reconciled_published_lanes = False
            break
    if not reconciled_published_lanes:
        return []

    lanes: list[dict[str, object]] = []
    for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
        item = dict(row)
        item.update(
            {
                "residency": residency,
                "metric_scope": residency.lower(),
                "eligible_applicants": _clean(row.get(f"{prefix}_eligible_applicants")),
                "bonus_permits": _clean(row.get(f"{prefix}_bonus_permits")),
                "regular_permits": _clean(row.get(f"{prefix}_regular_permits")),
                "total_permits": _clean(row.get(f"{prefix}_total_permits")),
                "success_ratio": _clean(row.get(f"{prefix}_success_ratio")),
                "p_draw": _clean(row.get(f"{prefix}_p_draw")),
                "p_draw_percent": _clean(row.get(f"{prefix}_p_draw_percent")),
            }
        )
        lanes.append(item)
    return lanes


def _canonical_bear_program(row: Mapping[str, object]) -> str:
    """Read dated canonical program identity, never a later code allowlist."""
    program = _clean(row.get("draw_pool")).upper()
    source = _clean_lower(row.get("source_file")).replace("\\", "/")
    year = _to_int(row.get("actual_draw_year"))
    if (program in MODELED_BEAR_SUBTYPES
            and _clean(row.get("source_scope")).upper() == "BLACK_BEAR"
            and _clean(row.get("qa_status")) == "SOURCE_TABLE_PARSED"
            and _clean(row.get("extraction_status")) == "OK"
            and _clean(row.get("candidate_promotion_status")) in {
                "OFFICIAL_SOURCE_PARSED", "SOURCE_ONLY_CANONICAL_CANDIDATE_NOT_PROMOTED"}
            and _to_int(row.get("pdf_page")) > 0 and year > 0
            and "/official_dwr_archive/black_bear/" in "/" + source.lstrip("/")
            and (source.endswith(f"/{year % 100:02d}_drawing_odds.pdf")
                 or year == 2017 and source.endswith("/17_bonus_points.pdf"))):
        return program
    return ""


def classify_bear_subtype_before_source_correction(row: Mapping[str, object]) -> str:
    if not is_bear_row(row):
        return UNKNOWN_BEAR_SUBTYPE
    if _clean(row.get("hunt_code")).upper() == "BR1000" or "sportsman" in _joined_text(row):
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
    if "restricted pursuit" in text:
        return RESTRICTED_BEAR_PURSUIT
    if hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only":
        return UNLIMITED_PURSUIT_PERMIT
    if "spot and stalk" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    if "limited entry" in text or "limited-entry" in text:
        return LIMITED_ENTRY_BEAR_HUNT
    return UNKNOWN_BEAR_SUBTYPE


def classify_bear_subtype(row: Mapping[str, object]) -> str:
    if not is_bear_row(row):
        return UNKNOWN_BEAR_SUBTYPE
    text = _joined_text(row)
    hunt_type = _clean_lower(row.get("hunt_type"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    weapon = _clean_lower(row.get("weapon"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    hunt_code = _clean(row.get("hunt_code")).upper()
    # Bear's explicit Sportsman identity does not need another family's saved
    # count file. More importantly, a source-dated PDF lane must be classified
    # before opening a later year's report merely to obtain a code allowlist.
    if hunt_code == "BR1000" or "sportsman" in text:
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
    canonical_program = _canonical_bear_program(row)
    if canonical_program:
        return canonical_program
    historical_pdf_classification = _historical_bear_pdf_classification(row)
    if historical_pdf_classification == "BEAR_PURSUIT_BONUS_DRAW":
        return RESTRICTED_BEAR_PURSUIT
    if historical_pdf_classification == "TRUE_BEAR_BONUS_DRAW":
        return LIMITED_ENTRY_BEAR_HUNT
    official_draw_codes = official_bear_draw_odds_hunt_codes()
    official_pursuit_codes = official_bear_pursuit_hunt_codes()
    if hunt_code in official_pursuit_codes:
        return RESTRICTED_BEAR_PURSUIT
    if hunt_code in official_draw_codes:
        return LIMITED_ENTRY_BEAR_HUNT
    if "remaining permit" in text or " otc" in f" {text}" or "over the counter" in text:
        return REMAINING_PERMIT_AVAILABILITY
    if "restricted pursuit" in text:
        return UNKNOWN_BEAR_SUBTYPE
    if hunt_code not in official_draw_codes and hunt_code not in official_pursuit_codes and (hunt_type == "pursuit" or hunt_type.startswith("pursuit") or weapon == "pursuit only"):
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
    product = BEAR_AVAILABILITY_PRODUCTS.get(_clean(row.get("hunt_code")).upper())
    if product is None or not _species_is_black_bear(row) or _clean(row.get("residency")) not in product[1]:
        return False
    subtype = classify_bear_subtype(row)
    if subtype != product[0]:
        return False
    if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
        return _clean_lower(row.get("harvest_objective_status")) in {"unknown", "open", "closed", "source missing"}
    if subtype == UNLIMITED_PURSUIT_PERMIT:
        return _clean_lower(row.get("permit_availability_type")) == "unlimited_pursuit"
    return False


def validate_bear_availability_identity(
    rows: Iterable[Mapping[str, object]],
    target_rows: Iterable[Mapping[str, object]],
) -> None:
    """Reject cross-species templates, wrong lanes and duplicate availability.

    Target metadata is identity context only, never applicant/quota truth.
    This gate does not repair saved rows or invent missing source identities.
    """
    targets = {}
    for target in target_rows:
        code = _clean(target.get("hunt_code")).upper()
        if code not in BEAR_AVAILABILITY_PRODUCTS:
            if _clean(target.get("algorithm_status")) == "MODELED_AVAILABILITY" and code.startswith("BR"):
                raise ValueError(f"Invalid Bear availability target identity: {code}")
            continue
        name = _clean(target.get("hunt_name"))
        if not _species_is_black_bear(target) or not name or "sportsman" in name.lower():
            raise ValueError(f"Invalid Bear availability target identity: {code}")
        if code in targets:
            if any(_clean(target.get(field)) != _clean(targets[code].get(field))
                   for field in ("hunt_name", "species")):
                raise ValueError(f"Conflicting Bear availability target identity: {code}")
            raise ValueError(f"Duplicate Bear availability target identity: {code}")
        if classify_bear_subtype(target) != BEAR_AVAILABILITY_PRODUCTS[code][0]:
            raise ValueError(f"Invalid Bear availability target program: {code}")
        targets[code] = target
    seen = set()
    for row in rows:
        code = _clean(row.get("hunt_code")).upper()
        if not code.startswith("BR") or not (
            _clean(row.get("algorithm_status")) == "MODELED_AVAILABILITY"
            or is_modeled_bear_availability_row(row)
        ):
            continue
        product = BEAR_AVAILABILITY_PRODUCTS.get(code)
        target = targets.get(code)
        key = (code, _clean(row.get("residency")))
        if product is None or target is None or key[1] not in product[1]:
            raise ValueError(f"Unsupported Bear availability identity/lane: {key}")
        if any(_clean(target.get(field)) and _clean(row.get(field)) != _clean(target.get(field))
               for field in ("hunt_name", "species", "weapon", "hunt_type", "sex_type")):
            raise ValueError(f"Bear availability identity mismatch: {key}")
        if _clean(row.get("bear_draw_subtype")) != product[0]:
            raise ValueError(f"Bear availability program mismatch: {key}")
        if (_clean(row.get("draw_system_type")) != BEAR_DRAW_SYSTEM_TYPE
                or not _species_is_black_bear(row)
                or (row.get("points") is not None and str(row["points"]).strip())):
            raise ValueError(f"Invalid Bear availability draw/point identity: {key}")
        if key in seen:
            raise ValueError(f"Duplicate Bear availability identity/lane: {key}")
        seen.add(key)
        for field in ("p_draw", "p_draw_pct", "p_bonus_pool", "p_random_pool", "p_preference_draw",
                      "p_draw_mean", "p_bonus_pool_pct", "p_random_pool_pct", "certified_p_draw",
                      "certified_p_draw_mean", "certified_p_draw_pct"):
            if row.get(field) is not None and str(row.get(field)).strip():
                raise ValueError(f"Draw probability on Bear availability row: {key}/{field}")


def _is_proven_bonus_bear_truth_row(row: Mapping[str, object]) -> bool:
    if not is_bear_row(row):
        return False
    if classify_bear_subtype(row) not in MODELED_BEAR_SUBTYPES:
        return False
    # Older accepted canonicals can retain the complete published residency
    # columns before the later dedicated Bear-PDF identity fields existed.
    # Exact lane/combined reconciliation is sufficient provenance to admit
    # those rows; it never derives a lane from a total.
    if _canonical_official_bear_residency_lanes(row):
        return True
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
    seen: dict[tuple[str, int, str, str, int], tuple[int, int, int, int]] = {}

    for source_row in truth_rows:
        dated_year = _to_int(source_row.get("actual_draw_year") or source_row.get("source_year")
                             or source_row.get("draw_year") or source_row.get("year"))
        if dated_year not in history_years:
            continue
        # Establish source admissibility before expanding a combined canonical
        # into lane copies.  A copy is intentionally marked Resident or
        # Nonresident, so it no longer satisfies the combined-row expansion
        # predicate by itself; testing the copy would accidentally drop an
        # otherwise proven older source year.
        if not _is_proven_bonus_bear_truth_row(source_row):
            continue
        # Promoted combined rows carry both DWR lanes in dedicated fields. Do
        # not let their aggregate values double as a residency demand ladder.
        candidate_rows = _canonical_official_bear_residency_lanes(source_row) or [dict(source_row)]
        for row in candidate_rows:
            # A Hunt Total is a report summary, not a point rung.  Feeding it
            # through ``_to_int('Totals')`` creates a false point-zero demand
            # record, often as a third aggregate residency lane beside the
            # actual resident/nonresident tables.  Only official point-rung
            # records may form an applicant ladder.
            record_type = _clean_lower(row.get("record_type") or row.get("row_type"))
            # Retained legacy/synthetic truth rows may predate the explicit
            # point-row label.  Exclude only rows positively identified as
            # hunt totals; a blank record type is not evidence that a point
            # rung should be discarded.
            if record_type in {"hunt_total_draw_result", "total", "hunt_total", "total_row"}:
                continue
            # Canonical draw rows are dated by the draw that actually happened.
            # Some retained legacy rows also contain the literal text "None" in
            # the old ``year`` column.  Treating that placeholder as a date
            # silently drops otherwise valid historical ladders, so keep the
            # explicit official draw-year field authoritative and only then
            # fall back through alternate source-date names.
            year = _to_int(
                row.get("actual_draw_year")
                or row.get("source_year")
                or row.get("draw_year")
                or row.get("year")
            )
            if year not in history_years:
                continue
            subtype = classify_bear_subtype(row)
            hunt_code = _clean(row.get("hunt_code")).upper()
            if year < BEAR_SPLIT_HISTORY_START.get(hunt_code, 0):
                continue
            metric_scope = _clean_lower(row.get("metric_scope"))
            residency = _clean(row.get("residency"))
            if metric_scope == "total" or residency not in {"Resident", "Nonresident"}:
                # A combined ladder is never a proxy for either residency.
                continue
            point_value = _clean(row.get("points"))
            if point_value.lower() in {"total", "totals"}:
                raise ValueError(f"Invalid Bear point-rung value: {hunt_code}/{point_value}")
            points = _to_int(row.get("points"))
            if not hunt_code:
                continue

            eligible = _to_int(row.get("eligible_applicants"))
            bonus = _to_int(row.get("bonus_permits"))
            regular = _to_int(row.get("regular_permits"))
            total = _to_int(row.get("total_permits"))
            if bonus + regular != total or min(eligible, bonus, regular, total) < 0 or total > eligible:
                raise ValueError(f"Bear award components do not reconcile: {year}/{hunt_code}/{residency}/{points}")
            key = (subtype, year, hunt_code, residency, points)
            values = (eligible, bonus, regular, total)
            if key in seen:
                if seen[key] != values:
                    raise ValueError(f"Conflicting Bear point records: {key}")
                continue
            seen[key] = values
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


def _bear_default_retention_and_growth(subtype: str | None, residency: str | None) -> tuple[dict[str, float], float]:
    """
    Candidate program/residency priors, not verified calibration evidence.
    Provenance and held-out accuracy of these constants remain UNVERIFIED.
    Existing observed same-lane transitions still take precedence when present.
    """
    # Generic fallback if subtype unknown (global call)
    generic = ({"0": 0.78, "1": 0.83, "2_3": 0.87, "4_5": 0.91, "6_9": 0.95, "10_plus": 0.98}, 1.0)
    if not subtype:
        return generic
    if subtype == LIMITED_ENTRY_BEAR_HUNT:
        if residency == "Resident":
            return ({"0": 0.72, "1": 0.78, "2_3": 0.82, "4_5": 0.86, "6_9": 0.90, "10_plus": 0.94}, 1.15)
        elif residency == "Nonresident":
            return ({"0": 0.60, "1": 0.66, "2_3": 0.71, "4_5": 0.76, "6_9": 0.81, "10_plus": 0.86}, 1.08)
        else:
            return ({"0": 0.66, "1": 0.72, "2_3": 0.76, "4_5": 0.81, "6_9": 0.86, "10_plus": 0.90}, 1.12)
    elif subtype == RESTRICTED_BEAR_PURSUIT:
        if residency == "Resident":
            return ({"0": 0.50, "1": 0.55, "2_3": 0.60, "4_5": 0.66, "6_9": 0.72, "10_plus": 0.78}, 0.95)
        elif residency == "Nonresident":
            return ({"0": 0.40, "1": 0.46, "2_3": 0.51, "4_5": 0.56, "6_9": 0.62, "10_plus": 0.68}, 0.90)
        else:
            return ({"0": 0.45, "1": 0.50, "2_3": 0.55, "4_5": 0.61, "6_9": 0.67, "10_plus": 0.73}, 0.92)
    return generic


def _build_retention_and_zero_growth(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
    subtype_hint: str | None = None,
    residency_hint: str | None = None,
) -> tuple[dict[str, float], float, dict[str, tuple[float, ...]], tuple[float, ...]]:
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

    # Detect subtype/residency from ladders if hints not provided
    detected_subtypes = {k[0] for k in ladders.keys()} if ladders else set()
    detected_residencies = {k[3] for k in ladders.keys()} if ladders else set()
    # If single subtype/residency in scoped ladders, use it for Bear-specific defaults
    inferred_subtype = subtype_hint or (next(iter(detected_subtypes)) if len(detected_subtypes)==1 else None)
    inferred_residency = residency_hint or (next(iter(detected_residencies)) if len(detected_residencies)==1 else None)

    bear_defaults, bear_zero_default = _bear_default_retention_and_growth(inferred_subtype, inferred_residency)
    default_retention = bear_defaults
    retention_by_band: dict[str, float] = {}
    retention_history_by_band: dict[str, tuple[float, ...]] = {}
    for band, fallback in default_retention.items():
        samples = retention_samples.get(band, [])
        retention_by_band[band] = round(mean(samples), 4) if samples else fallback
        retention_history_by_band[band] = tuple(samples) if samples else (fallback,)
    zero_growth = round(mean(zero_growth_samples), 4) if zero_growth_samples else bear_zero_default
    zero_growth_history = tuple(zero_growth_samples) if zero_growth_samples else (zero_growth,)
    return retention_by_band, zero_growth, retention_history_by_band, zero_growth_history


def _add_bear_cohort_evidence(
    evidence: dict[tuple[object, ...], _BearCohortEvidence],
    key: tuple[object, ...],
    *,
    unsuccessful: int,
    observed_next: int,
) -> None:
    """Accumulate one official adjacent-year public-ladder transition."""

    current = evidence.get(key, _BearCohortEvidence())
    supplied_by_prior_unsuccessful = min(max(0, unsuccessful), max(0, observed_next))
    evidence[key] = _BearCohortEvidence(
        transitions=current.transitions + 1,
        unsuccessful=current.unsuccessful + max(0, unsuccessful),
        retained=current.retained + supplied_by_prior_unsuccessful,
        arrivals=current.arrivals + max(0, observed_next - supplied_by_prior_unsuccessful),
    )


def _build_lane_cohort_model(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
) -> _BearLaneCohortModel:
    """Build source-only same-lane reapplication and arrival evidence.

    The exact key is ``subtype / hunt code / residency / source point``.  Its
    observed following-year applicant count is decomposed into the part that
    the prior unsuccessful cohort could supply and a residual measured arrival.
    The progressively broader maps are empirical fallback evidence only; they
    never receive a statewide point-purchase count or a quota-derived value.
    """

    exact_rung: dict[tuple[object, ...], _BearCohortEvidence] = {}
    lane_band: dict[tuple[object, ...], _BearCohortEvidence] = {}
    subtype_residency_band: dict[tuple[object, ...], _BearCohortEvidence] = {}
    residency_band: dict[tuple[object, ...], _BearCohortEvidence] = {}
    years_by_lane: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for subtype, year, hunt_code, residency in ladders:
        if residency in {"Resident", "Nonresident"}:
            years_by_lane[(subtype, hunt_code, residency)].append(year)

    for (subtype, hunt_code, residency), years in years_by_lane.items():
        for source_year in sorted(set(years)):
            target_year = source_year + 1
            if target_year not in years:
                continue
            source = ladders[(subtype, source_year, hunt_code, residency)]
            target = ladders[(subtype, target_year, hunt_code, residency)]
            for source_points, source_values in source.items():
                source_points = int(source_points)
                target_points = source_points + 1
                unsuccessful = max(
                    int(source_values.get("eligible", 0))
                    - int(source_values.get("bonus", 0))
                    - int(source_values.get("regular", 0)),
                    0,
                )
                observed_next = max(0, int(target.get(target_points, {}).get("eligible", 0)))
                band = _band_for_points(source_points)
                payload = {"unsuccessful": unsuccessful, "observed_next": observed_next}
                _add_bear_cohort_evidence(
                    exact_rung,
                    (subtype, hunt_code, residency, source_points),
                    **payload,
                )
                _add_bear_cohort_evidence(
                    lane_band,
                    (subtype, hunt_code, residency, band),
                    **payload,
                )
                _add_bear_cohort_evidence(
                    subtype_residency_band,
                    (subtype, residency, band),
                    **payload,
                )
                _add_bear_cohort_evidence(
                    residency_band,
                    (residency, band),
                    **payload,
                )
    return _BearLaneCohortModel(
        exact_rung=exact_rung,
        lane_band=lane_band,
        subtype_residency_band=subtype_residency_band,
        residency_band=residency_band,
    )


def _rate_from_evidence(evidence: _BearCohortEvidence | None, default: float) -> float:
    if evidence is None or evidence.unsuccessful <= 0:
        return default
    return max(0.0, min(1.0, evidence.retained / evidence.unsuccessful))


def _arrival_from_evidence(evidence: _BearCohortEvidence | None, default: float) -> float:
    if evidence is None or evidence.transitions <= 0:
        return default
    return max(0.0, evidence.arrivals / evidence.transitions)


def _without_bear_cohort_evidence(
    total: _BearCohortEvidence | None,
    excluded: _BearCohortEvidence | None,
) -> _BearCohortEvidence | None:
    """Leave the exact rung out of the broader prior when it is available.

    Otherwise a one-observation, 100% exact lane would also make every parent
    100%, defeating the hierarchy and recreating the false-guarantee problem.
    """

    if total is None:
        return None
    if excluded is None:
        return total
    return _BearCohortEvidence(
        transitions=max(0, total.transitions - excluded.transitions),
        unsuccessful=max(0, total.unsuccessful - excluded.unsuccessful),
        retained=max(0, total.retained - excluded.retained),
        arrivals=max(0, total.arrivals - excluded.arrivals),
    )


def _smooth_bear_cohort_value(observed: float, evidence_total: int, prior: float, prior_strength: float) -> float:
    if evidence_total <= 0:
        return prior
    weight = evidence_total / (evidence_total + max(1.0, prior_strength))
    return (weight * observed) + ((1.0 - weight) * prior)


def _lane_cohort_calibration(
    model: _BearLaneCohortModel,
    *,
    subtype: str,
    hunt_code: str,
    residency: str,
    source_points: int,
) -> _BearCohortCalibration:
    """Resolve exact public-lane evidence before a progressively broader prior.

    The posterior is deliberately bounded to a real reapplication percentage.
    Excess next-year applicants remain an arrival component, so an observed
    hunt switch cannot inflate the same-hunt retention percentage beyond 100%.
    """

    band = _band_for_points(source_points)
    exact = model.exact_rung.get((subtype, hunt_code, residency, source_points))
    # Every broader level is leave-exact-rung-out. This is a source-only
    # hierarchy, not a self-referential way to turn one perfect transition into
    # a perfect fallback prior.
    broad = _without_bear_cohort_evidence(
        model.residency_band.get((residency, band)), exact
    )
    # Bear-specific priors - per program/residency, not generic 0.85
    bear_ret_defaults, _ = _bear_default_retention_and_growth(subtype, residency)
    bear_prior_rate = bear_ret_defaults.get(band, 0.85)
    # Candidate arrival priors; measured provenance remains UNVERIFIED.
    if subtype == LIMITED_ENTRY_BEAR_HUNT:
        bear_prior_arrival = 8.0 if residency == "Resident" else 2.0
    else:  # RESTRICTED_BEAR_PURSUIT
        bear_prior_arrival = 1.5 if residency == "Resident" else 0.5
    broad_rate = _rate_from_evidence(broad, bear_prior_rate)
    broad_arrivals = _arrival_from_evidence(broad, bear_prior_arrival)
    subtype_evidence = _without_bear_cohort_evidence(
        model.subtype_residency_band.get((subtype, residency, band)), exact
    )
    subtype_rate = _smooth_bear_cohort_value(
        _rate_from_evidence(subtype_evidence, broad_rate),
        0 if subtype_evidence is None else subtype_evidence.unsuccessful,
        broad_rate,
        30.0,
    )
    subtype_arrivals = _smooth_bear_cohort_value(
        _arrival_from_evidence(subtype_evidence, broad_arrivals),
        0 if subtype_evidence is None else subtype_evidence.transitions,
        broad_arrivals,
        6.0,
    )
    lane_evidence = _without_bear_cohort_evidence(
        model.lane_band.get((subtype, hunt_code, residency, band)), exact
    )
    lane_rate = _smooth_bear_cohort_value(
        _rate_from_evidence(lane_evidence, subtype_rate),
        0 if lane_evidence is None else lane_evidence.unsuccessful,
        subtype_rate,
        16.0,
    )
    lane_arrivals = _smooth_bear_cohort_value(
        _arrival_from_evidence(lane_evidence, subtype_arrivals),
        0 if lane_evidence is None else lane_evidence.transitions,
        subtype_arrivals,
        4.0,
    )
    exact_unsuccessful = 0 if exact is None else exact.unsuccessful
    exact_transitions = 0 if exact is None else exact.transitions
    reapply_rate = _smooth_bear_cohort_value(
        _rate_from_evidence(exact, lane_rate),
        exact_unsuccessful,
        lane_rate,
        8.0,
    )
    arrival_count = _smooth_bear_cohort_value(
        _arrival_from_evidence(exact, lane_arrivals),
        exact_transitions,
        lane_arrivals,
        2.0,
    )
    if exact_unsuccessful >= 8 and exact_transitions >= 2:
        evidence_scope = "EXACT_LANE_RUNG"
    elif lane_evidence and lane_evidence.unsuccessful > 0:
        evidence_scope = "LANE_POINT_BAND_SMOOTHED"
    elif subtype_evidence and subtype_evidence.unsuccessful > 0:
        evidence_scope = "SUBTYPE_RESIDENCY_POINT_BAND_FALLBACK"
    else:
        evidence_scope = "RESIDENCY_POINT_BAND_FALLBACK"
    return _BearCohortCalibration(
        reapply_rate=max(0.0, min(1.0, reapply_rate)),
        arrival_count=max(0.0, arrival_count),
        evidence_scope=evidence_scope,
        exact_unsuccessful=exact_unsuccessful,
        exact_transitions=exact_transitions,
    )


def _forecast_lane_cohort_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    model: _BearLaneCohortModel,
    *,
    subtype: str,
    hunt_code: str,
    residency: str,
) -> tuple[dict[int, int], dict[int, _BearCohortCalibration]]:
    """Forecast one Bear lane using measured reapplication plus measured arrivals."""

    prior_points = sorted(int(points) for points in latest_ladder)
    max_points = max(prior_points) if prior_points else 0
    forecast: dict[int, int] = {0: _round_count(latest_ladder.get(0, {}).get("eligible", 0))}
    calibrations: dict[int, _BearCohortCalibration] = {}
    for target_points in range(1, max_points + 5):
        source_points = target_points - 1
        source = latest_ladder.get(source_points, {})
        unsuccessful = max(
            int(source.get("eligible", 0)) - int(source.get("bonus", 0)) - int(source.get("regular", 0)),
            0,
        )
        calibration = _lane_cohort_calibration(
            model,
            subtype=subtype,
            hunt_code=hunt_code,
            residency=residency,
            source_points=source_points,
        )
        calibrations[target_points] = calibration
        # An aggregate public ladder cannot identify a person who appears at an
        # otherwise empty upper rung. A broad fallback must therefore never
        # create that population. An exact same-lane transition is different:
        # it is direct historical evidence that this specific rung has received
        # an arrival despite having no prior unsuccessful cohort. Keep that
        # measured component separate from returning applicants.
        allow_exact_arrival = calibration.exact_transitions > 0
        forecast[target_points] = (
            _round_count((unsuccessful * calibration.reapply_rate) + calibration.arrival_count)
            if unsuccessful > 0
            else _round_count(calibration.arrival_count) if allow_exact_arrival else 0
        )
    return forecast, calibrations


def _point_purchase_counts_by_year_residency(
    point_purchase_rows: Iterable[Mapping[str, object]],
    history_years: set[int],
) -> dict[tuple[int, str], dict[int, int]]:
    """Read only the separate statewide point-purchase evidence class.

    These counts deliberately remain statewide.  They are used below solely
    to corroborate that an observed historical high-point return/switch could
    have come from an outside applicant pool; they are never allocated to a
    hunt or converted directly into forecast applicants.
    """

    counts: dict[tuple[int, str], dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for row in point_purchase_rows:
        year = _to_int(row.get("draw_year") or row.get("actual_draw_year") or row.get("year"))
        residency = _clean(row.get("residency"))
        points = _to_int(row.get("points"))
        applicants = _to_int(row.get("point_purchase_applicants"))
        if year not in history_years or residency not in {"Resident", "Nonresident"}:
            continue
        if points < 0 or applicants <= 0:
            continue
        counts[(year, residency)][points] += applicants
    return {key: dict(value) for key, value in counts.items()}


def _build_source_calibrated_returning_tail_profiles(
    ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]],
    point_purchase_counts: Mapping[tuple[int, str], Mapping[int, int]],
) -> dict[tuple[str, str, str], tuple[dict[int, int], ...]]:
    """Find prior, hunt-specific high-tail arrivals supported by source pools.

    A profile is accepted only when a prior official transition shows an
    applicant at a high rung that the immediately preceding same-hunt
    unsuccessful cohort could not have supplied *and* the separately retained
    statewide point-purchase table confirms people existed at that rung.  The
    profile is a sampled historical scenario, not a direct assignment of
    statewide purchasers to that hunt.
    """

    years_by_lane: dict[tuple[str, str, str], list[int]] = defaultdict(list)
    for subtype, year, hunt_code, residency in ladders:
        if residency in {"Resident", "Nonresident"}:
            years_by_lane[(subtype, hunt_code, residency)].append(year)

    profiles: dict[tuple[str, str, str], tuple[dict[int, int], ...]] = {}
    for lane_key, years in years_by_lane.items():
        subtype, hunt_code, residency = lane_key
        profiles_for_lane: list[dict[int, int]] = []
        for prior_year in sorted(set(years)):
            next_year = prior_year + 1
            if next_year not in years:
                continue
            prior = ladders[(subtype, prior_year, hunt_code, residency)]
            nxt = ladders[(subtype, next_year, hunt_code, residency)]
            statewide = point_purchase_counts.get((prior_year, residency), {})
            tail: dict[int, int] = {}
            for points, next_values in nxt.items():
                # The 6+ band is the high-stack range for Bear.  Lower bands
                # already have substantial direct just-missed cohorts and are
                # not appropriate for an external-returning uncertainty path.
                if int(points) < 6 or int(statewide.get(int(points), 0)) <= 0:
                    continue
                previous = prior.get(int(points) - 1, {})
                prior_unsuccessful = max(
                    int(previous.get("eligible", 0))
                    - int(previous.get("bonus", 0))
                    - int(previous.get("regular", 0)),
                    0,
                )
                observed_next = max(0, int(next_values.get("eligible", 0)))
                unobserved_arrivals = max(0, observed_next - prior_unsuccessful)
                if unobserved_arrivals:
                    tail[int(points)] = unobserved_arrivals
            if tail:
                profiles_for_lane.append(tail)
        if profiles_for_lane:
            profiles[lane_key] = tuple(profiles_for_lane)
    return profiles



# NOTE: This counts source-ladder rows reviewed, NOT independently scored forecasts.
# Does NOT prove '400+ scored rows below 10pp MAE'. Claim recorded as UNVERIFIED.
# Frozen forecasts remain untouched per 2026_OFFICIAL_SOURCE_RESCORE.
def _measured_pursuit_row_count(ladders: Mapping[tuple[str, int, str, str], dict[int, dict[str, int]]]) -> int:
    """
    Returns source inventory count, not the certification joined-row gate.
    Counts only point levels with eligible>0 in source ladders.
    Does NOT add empty rows to satisfy 400-row gate.
    """
    count = 0
    for (subtype, year, hunt_code, residency), ladder in ladders.items():
        if subtype != RESTRICTED_BEAR_PURSUIT:
            continue
        for points, vals in ladder.items():
            if int(vals.get("eligible", 0)) > 0:
                count += 1
    return count


def _forecast_applicant_ladder(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_by_band: Mapping[str, float],
    zero_growth: float,
) -> dict[int, int]:
    prior_points = sorted(int(points) for points in latest_ladder.keys())
    max_points = max(prior_points) if prior_points else 0
    # A source-year point ladder can advance only one year in an adjacent fold.
    tail_buffer = 1
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


@lru_cache(maxsize=4)
def _unit_interval_gauss_legendre(order: int = 16) -> tuple[tuple[float, float], ...]:
    """Return deterministic Gauss-Legendre nodes and weights on ``[0, 1]``.

    Utah compares the lowest random number retained by each application.  The
    exact inclusion probability below is a one-dimensional integral.  Keeping
    this small quadrature implementation in the Bear owner avoids a new runtime
    dependency and makes the probability deterministic across audit replays.
    Sixteen nodes keep the verified numerical difference below one hundredth of
    one percentage point while allowing the existing 200-scenario uncertainty
    review to remain operational.
    """

    node_weights: list[tuple[float, float]] = []
    half = (int(order) + 1) // 2
    for index in range(1, half + 1):
        root = math.cos(math.pi * (index - 0.25) / (order + 0.5))
        derivative = 0.0
        for _ in range(100):
            p_prev = 1.0
            p_curr = root
            for degree in range(2, order + 1):
                p_next = ((2 * degree - 1) * root * p_curr - (degree - 1) * p_prev) / degree
                p_prev, p_curr = p_curr, p_next
            derivative = order * (root * p_curr - p_prev) / (root * root - 1.0)
            updated = root - p_curr / derivative
            if abs(updated - root) <= 1e-15:
                root = updated
                break
            root = updated
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        left = (1.0 - root) / 2.0
        right = (1.0 + root) / 2.0
        mapped_weight = weight / 2.0
        node_weights.append((left, mapped_weight))
        if abs(left - right) > 1e-15:
            node_weights.append((right, mapped_weight))
    return tuple(sorted(node_weights))


def _truncated_binomial_probabilities(count: int, probability: float, cap: int) -> list[float]:
    """Return binomial probabilities from zero through ``cap`` successes."""

    count = max(0, int(count))
    cap = min(max(0, int(cap)), count)
    if probability <= 0.0:
        return [1.0] + [0.0] * cap
    if probability >= 1.0:
        result = [0.0] * (cap + 1)
        if count <= cap:
            result[count] = 1.0
        return result
    log_probability = math.log(probability)
    log_complement = math.log1p(-probability)
    return [
        math.exp(
            math.lgamma(count + 1)
            - math.lgamma(successes + 1)
            - math.lgamma(count - successes + 1)
            + successes * log_probability
            + (count - successes) * log_complement
        )
        for successes in range(cap + 1)
    ]


@lru_cache(maxsize=65_536)
def _exact_weighted_random_inclusion_probability(
    target_weight: int,
    other_applicants_by_weight: tuple[tuple[int, int], ...],
    random_permits: int,
) -> float:
    """Probability that one application ranks within the random permits.

    Every application keeps its lowest of ``points + 1`` independent random
    numbers.  After a monotone ``-log(1-u)`` transform, those retained numbers
    are independent exponential clocks with rates equal to their ticket
    counts.  The requested probability is therefore the chance that at most
    ``random_permits - 1`` other application clocks finish before the focal
    application.  Integrating that Poisson-binomial CDF gives the exact Utah
    applicant-ranking mechanic; it is not repeated ticket-share sampling with
    replacement.
    """

    target_weight = max(1, int(target_weight))
    random_permits = max(0, int(random_permits))
    other_groups = tuple(
        (max(1, int(weight)), max(0, int(count)))
        for weight, count in other_applicants_by_weight
        if int(count) > 0
    )
    other_count = sum(count for _, count in other_groups)
    if random_permits <= 0:
        return 0.0
    if random_permits >= other_count + 1:
        return 1.0

    cap = random_permits - 1
    integral = 0.0
    for focal_survival, quadrature_weight in _unit_interval_gauss_legendre():
        # Substituting focal_survival = exp(-target_weight * t) makes
        # the focal application's density uniform on [0, 1].
        distribution = [1.0] + [0.0] * cap
        for weight, count in other_groups:
            earlier_probability = 1.0 - focal_survival ** (weight / target_weight)
            group_pmf = _truncated_binomial_probabilities(count, earlier_probability, cap)
            updated = [0.0] * (cap + 1)
            for prior_successes, prior_probability in enumerate(distribution):
                if prior_probability == 0.0:
                    continue
                for group_successes, group_probability in enumerate(group_pmf):
                    total_successes = prior_successes + group_successes
                    if total_successes > cap:
                        break
                    updated[total_successes] += prior_probability * group_probability
            distribution = updated
        integral += quadrature_weight * sum(distribution)
    return min(1.0, max(0.0, integral))


def _weighted_random_probability(
    points: int,
    applicants_by_points: Mapping[int, int],
    random_permits: int,
    max_point_permits: int = 0,
) -> float:
    remaining_max_permits = max(0, int(max_point_permits))
    nonwinners_by_points: dict[int, int] = {}
    for point_level in sorted((int(level) for level in applicants_by_points), reverse=True):
        count = max(0, int(applicants_by_points.get(point_level, 0)))
        max_pool_winners = min(count, remaining_max_permits)
        nonwinners_by_points[point_level] = count - max_pool_winners
        remaining_max_permits -= max_pool_winners

    target_count = max(0, int(nonwinners_by_points.get(int(points), 0)))
    if random_permits <= 0 or target_count <= 0:
        return 0.0
    other_applicants_by_weight = tuple(
        sorted(
            (
                max(1, int(point_level) + 1),
                int(count) - (1 if int(point_level) == int(points) else 0),
            )
            for point_level, count in nonwinners_by_points.items()
            if int(count) - (1 if int(point_level) == int(points) else 0) > 0
        )
    )
    target_weight = max(1, int(points) + 1)
    total_weight = target_weight + sum(weight * count for weight, count in other_applicants_by_weight)
    if int(random_permits) == 1:
        # The lowest of every random number in the pool is uniformly likely to
        # be any ticket, so the one-permit case has this exact closed form.
        return target_weight / total_weight
    other_count = sum(count for _, count in other_applicants_by_weight)
    if all(weight == target_weight for weight, _ in other_applicants_by_weight):
        # Equal-rate application clocks are exchangeable.
        return min(1.0, int(random_permits) / (other_count + 1))
    return _exact_weighted_random_inclusion_probability(
        target_weight,
        other_applicants_by_weight,
        int(random_permits),
    )


def _forecast_cumulative_stack(ladders, subtype, hunt_code, residency):
    """Candidate: same-hunt/residency cumulative demand, source years only.

    Forecast the number at or above each point, not independent noisy cells.
    Recent observed transition residuals add switching/returning demand to
    unsuccessful applicants advanced one point. With no transition, retain
    the latest observed same-point cumulative demand as an explicit baseline.
    """
    years = sorted(k[1] for k in ladders if k[0] == subtype and k[2:] == (hunt_code, residency))
    if not years:
        return {}
    latest = ladders[(subtype, years[-1], hunt_code, residency)]
    top = max(latest, default=0) + 1

    def cumulative(ladder, threshold, survivors=False):
        return sum(max(0, v["eligible"] - (v["total"] if survivors else 0))
                   for p, v in ladder.items() if p >= threshold)

    estimates = {}
    for p in range(top + 1):
        baseline = cumulative(latest, p)
        residuals = []
        for year in years[-3:]:
            if year-1 not in years:
                continue
            earlier = ladders[(subtype, year-1, hunt_code, residency)]
            later = ladders[(subtype, year, hunt_code, residency)]
            residuals.append(cumulative(later, p) - cumulative(earlier, max(0, p-1), p > 0))
        if residuals:
            cohort = cumulative(latest, max(0, p-1), p > 0)
            # Two-observation shrinkage toward observed same-lane demand;
            # fixed before evaluating the final two historical holdouts.
            estimates[p] = max(0.0, (len(residuals) * (cohort + mean(residuals)) + 2 * baseline) / (len(residuals)+2))
        else:
            estimates[p] = float(baseline)
    # A cumulative stack cannot rise as the point threshold increases.
    for p in range(1, top + 1):
        estimates[p] = min(estimates[p-1], estimates[p])
    rounded = {p: _round_count(value) for p, value in estimates.items()}
    return {p: rounded[p] - rounded.get(p+1, 0) for p in rounded}


def _forecast_cumulative_transition_ensemble(ladders, subtype, hunt_code, residency):
    """Joint, source-only demand scenarios for one comparable hunt/lane.

    Each observed adjacent transition contributes its entire cumulative
    innovation vector, preserving dependence between point thresholds. Both
    bonus and random winners leave before the unsuccessful stack advances.
    Two same-lane persistence scenarios regularize short histories; they are
    explicit demand assumptions, not observed applicants or additional years.
    No statewide purchases, other residency, program or hunt supplies entrants.
    """
    years = sorted(k[1] for k in ladders if k[0] == subtype and k[2:] == (hunt_code, residency))
    if not years:
        return {}, [], []
    latest_year = years[-1]
    # A missing intervening year is not a measured transition across a gap.
    contiguous = [latest_year]
    while contiguous[-1] - 1 in years:
        contiguous.append(contiguous[-1] - 1)
    latest = ladders[(subtype, latest_year, hunt_code, residency)]
    top = max(latest, default=0) + 1

    def stack(ladder, threshold, survivors=False):
        return sum(max(0, v['eligible'] - (v['total'] if survivors else 0))
                   for level, v in ladder.items() if level >= threshold)

    def invert(estimates):
        monotone = {}
        for p in range(top + 1):
            value = max(0.0, estimates[p])
            monotone[p] = min(monotone[p - 1], value) if p else value
        rounded = {p: _round_count(value) for p, value in monotone.items()}
        return {p: rounded[p] - rounded.get(p + 1, 0) for p in rounded}

    baseline = {p: stack(latest, p) for p in range(top + 1)}
    years_used = sorted(contiguous[:-1])[-3:]
    if not years_used:
        # A single year gives a survivor rollforward, not invented innovations.
        single = {0: latest.get(0, {}).get('eligible', 0)}
        single.update({p: max(0, latest.get(p - 1, {}).get('eligible', 0)
                             - latest.get(p - 1, {}).get('total', 0))
                       for p in range(1, top + 1)})
        return single, [single], []
    scenarios = [invert(baseline), invert(baseline)]
    for year in years_used:
        earlier = ladders[(subtype, year - 1, hunt_code, residency)]
        later = ladders[(subtype, year, hunt_code, residency)]
        estimates = {}
        for p in range(top + 1):
            threshold = max(0, p - 1)
            innovation = stack(later, p) - stack(earlier, threshold, True)
            estimates[p] = stack(latest, threshold, True) + innovation
        scenarios.append(invert(estimates))
    central_stack = {p: mean(sum(lane[q] for q in lane if q >= p) for lane in scenarios)
                     for p in range(top + 1)}
    return invert(central_stack), scenarios, years_used


def _forecast_adaptive_cumulative_stack(ladders, subtype, hunt_code, residency):
    """Learn persistence versus advancing survivors from this exact lane only.

    Fit one bounded blend coefficient on recent, already observed transitions,
    using inverse-count weights so the zero/low-point mass cannot dominate the
    cutoff. Shrink the measured cumulative innovations with two zero-innovation
    prior observations. This forecasts demand, not next-year realized winners.
    """
    years = sorted(k[1] for k in ladders if k[0] == subtype and k[2:] == (hunt_code, residency))
    if not years:
        return {}, .5, []
    contiguous = [years[-1]]
    while contiguous[-1] - 1 in years:
        contiguous.append(contiguous[-1] - 1)
    transitions = sorted(contiguous[:-1])[-3:]
    if not transitions:
        single, _, _ = _forecast_cumulative_transition_ensemble(ladders, subtype, hunt_code, residency)
        return single, 1.0, []

    def cumulative(ladder, point, survivors=False):
        return sum(max(0, v['eligible'] - (v['total'] if survivors else 0))
                   for p, v in ladder.items() if p >= point)

    numerator, denominator = .5, 1.0  # Explicit fixed ridge prior, not applicant counts.
    for year in transitions:
        earlier = ladders[(subtype, year - 1, hunt_code, residency)]
        later = ladders[(subtype, year, hunt_code, residency)]
        for point in range(1, max(earlier, default=0) + 2):
            baseline = cumulative(earlier, point)
            difference = cumulative(earlier, point - 1, True) - baseline
            change = cumulative(later, point) - baseline
            weight = 1.0 / max(1, baseline)
            numerator += weight * difference * change
            denominator += weight * difference * difference
    blend = max(0.0, min(1.0, numerator / denominator))
    latest = ladders[(subtype, years[-1], hunt_code, residency)]
    top = max(latest, default=0) + 1
    estimates = {}
    for point in range(top + 1):
        def estimate(ladder):
            baseline = cumulative(ladder, point)
            advanced = cumulative(ladder, point - 1, True) if point else baseline
            return baseline + blend * (advanced - baseline)
        innovations = [cumulative(ladders[(subtype, year, hunt_code, residency)], point)
                       - estimate(ladders[(subtype, year - 1, hunt_code, residency)])
                       for year in transitions]
        value = max(0.0, estimate(latest) + sum(innovations) / (len(innovations) + 2))
        estimates[point] = min(estimates[point - 1], value) if point else value
    rounded = {p: _round_count(v) for p, v in estimates.items()}
    return {p: rounded[p] - rounded.get(p + 1, 0) for p in rounded}, blend, transitions


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = max(0.0, min(1.0, quantile)) * (len(ordered) - 1)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + ((ordered[upper] - ordered[lower]) * fraction)


def _sample_bear_forecast_ladders(
    latest_ladder: Mapping[int, dict[str, int]],
    retention_history_by_band: Mapping[str, tuple[float, ...]],
    zero_growth_history: tuple[float, ...],
    iterations: int,
    seed: str,
    returning_tail_profiles: Iterable[Mapping[int, int]] = (),
) -> list[dict[int, int]]:
    """Sample applicant ladders only from source-year transition history."""

    rng = random.Random(seed)
    sampled_ladders: list[dict[int, int]] = []
    profiles = [dict(profile) for profile in returning_tail_profiles]
    # Keep an explicit no-tail scenario.  This makes the historical-returning
    # path a calibrated mixture rather than a deterministic population add.
    scenarios = [{}] + profiles
    for _ in range(max(1, iterations)):
        sampled_retention = {
            band: rng.choice(samples)
            for band, samples in retention_history_by_band.items()
        }
        sampled_zero_growth = rng.choice(zero_growth_history)
        sampled = _forecast_applicant_ladder(latest_ladder, sampled_retention, sampled_zero_growth)
        for points, arrivals in rng.choice(scenarios).items():
            sampled[int(points)] = max(0, int(sampled.get(int(points), 0)) + int(arrivals))
        sampled_ladders.append(sampled)
    return sampled_ladders


def _sample_observed_arrival_count(rng: random.Random, expected_arrivals: float) -> int:
    """Sample an integer arrival count with the measured posterior mean.

    The public ladders give an aggregate residual count, not a person-level
    identity.  A Poisson count is the least-committal discrete distribution for
    that measured mean: it preserves the expected observed residual while
    allowing zero, one, or multiple arrivals in a particular simulation.  It
    replaces the former deterministic rounding of a fractional arrival into
    every iteration.
    """

    rate = max(0.0, float(expected_arrivals))
    if rate <= 0.0:
        return 0
    # Knuth's exact sampler is stable and fast for the small high-stack
    # residuals. A normal approximation prevents pathological loops in a large
    # lower-point lane without changing the retained-applicant calculation.
    if rate > 30.0:
        return max(0, int(round(rng.gauss(rate, math.sqrt(rate)))))
    threshold = math.exp(-rate)
    product = 1.0
    count = 0
    while product > threshold:
        count += 1
        product *= rng.random()
    return max(0, count - 1)


def _split_bear_bonus_permits(public_permits_raw: int, residency: object) -> tuple[int, int]:
    """Return the official Bear max-point/random allocation for one lane.

    The ordinary Utah bonus split rounds odd pools toward max point. Retained
    official Black Bear draw-result ladders consistently show the distinct
    one-permit Bear case in the regular/random column for both residency lanes.
    Keep this exception in the Bear owner rather than changing the shared
    limited-entry/OIL bonus rule.
    """

    public_permits = max(0, int(public_permits_raw or 0))
    if public_permits == 1:
        return 0, 1
    split = split_utah_bonus_permits(public_permits, residency)
    return split.maxPointPermits, split.randomPermits


def _sample_lane_cohort_forecast_ladders(
    latest_ladder: Mapping[int, dict[str, int]],
    calibrations: Mapping[int, _BearCohortCalibration],
    *,
    iterations: int,
    seed: str,
) -> list[dict[int, int]]:
    """Sample only the uncertainty inherent in public-ladder retention evidence.

    A rate backed by a thin exact lane keeps a broader posterior and therefore
    cannot become a deterministic visitor-facing guarantee merely because one
    prior transition happened to retain every applicant.
    """

    rng = random.Random(seed)
    max_points = max((int(points) for points in latest_ladder), default=0)
    sampled_ladders: list[dict[int, int]] = []
    for _ in range(max(1, iterations)):
        sampled: dict[int, int] = {
            0: _round_count(latest_ladder.get(0, {}).get("eligible", 0))
        }
        for target_points in range(1, max_points + 5):
            source_points = target_points - 1
            source = latest_ladder.get(source_points, {})
            unsuccessful = max(
                int(source.get("eligible", 0)) - int(source.get("bonus", 0)) - int(source.get("regular", 0)),
                0,
            )
            calibration = calibrations[target_points]
            if unsuccessful <= 0 and calibration.exact_transitions <= 0:
                sampled[target_points] = 0
                continue
            # Eight pseudo-applicants is the exact-rung prior strength used by
            # the hierarchical estimator.  It leaves a thin lane genuinely
            # uncertain while allowing a repeatedly observed lane to dominate.
            if unsuccessful > 0:
                evidence_strength = max(8.0, float(calibration.exact_unsuccessful + 8))
                alpha = max(0.001, calibration.reapply_rate * evidence_strength)
                beta = max(0.001, (1.0 - calibration.reapply_rate) * evidence_strength)
                sampled_reapply_rate = rng.betavariate(alpha, beta)
            else:
                sampled_reapply_rate = 0.0
            sampled_arrivals = _sample_observed_arrival_count(
                rng,
                calibration.arrival_count,
            )
            # Preserve an empty-rung arrival only when the exact hunt/lane/rung
            # has actually exhibited that behavior in an earlier source-only
            # transition. Broader priors guide a measured existing cohort but
            # cannot invent a high-stack population.
            sampled[target_points] = (
                _round_count(unsuccessful * sampled_reapply_rate) + sampled_arrivals
                if (unsuccessful > 0 or calibration.exact_transitions > 0)
                else 0
            )
        sampled_ladders.append(sampled)
    return sampled_ladders


def _condition_for_focal_bear_applicant(
    applicants_by_points: Mapping[int, int],
    points: int,
) -> dict[int, int]:
    """Evaluate probability for the applicant represented by this forecast row.

    An aggregate arrival sample may be zero at a rung even though the page is
    answering the chance for one applicant who is considering that rung.  The
    applicant must be present in both the deterministic ceiling and every
    simulation; otherwise a sampled zero incorrectly becomes a 0% chance.
    """

    conditioned = {int(level): max(0, int(count)) for level, count in applicants_by_points.items()}
    conditioned[int(points)] = max(1, conditioned.get(int(points), 0))
    return conditioned


def _bear_simulation_probability(
    points: int,
    sampled_ladders: Iterable[Mapping[int, int]],
    max_point_permits: int,
    random_permits: int,
) -> tuple[float, float, float, float, float, float]:
    """Return mean draw components and P10/P50/P90 for one applicant."""

    bonus_samples: list[float] = []
    random_samples: list[float] = []
    draw_samples: list[float] = []
    for sampled in sampled_ladders:
        conditioned = _condition_for_focal_bear_applicant(sampled, points)
        p_bonus, _, _ = compute_bonus_pool_probability(points, conditioned, max_point_permits)
        p_random = _weighted_random_probability(points, conditioned, random_permits, max_point_permits)
        bonus_samples.append(p_bonus)
        random_samples.append(p_random)
        draw_samples.append(combine_probabilities(p_bonus, p_random))
    return (
        mean(bonus_samples) if bonus_samples else 0.0,
        mean(random_samples) if random_samples else 0.0,
        mean(draw_samples) if draw_samples else 0.0,
        _percentile(draw_samples, 0.10),
        _percentile(draw_samples, 0.50),
        _percentile(draw_samples, 0.90),
    )


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
        if hunt_code == "BR1000" or "sportsman" in _joined_text(row):
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
    central_estimate_mode: str = "deterministic",
    iterations: int = 1,
    seed: int = 20260701,
    returning_cohort_mode: str = "off",
    point_purchase_rows: Iterable[Mapping[str, object]] = (),
    demand_mode: str = "cohort_rollforward",
) -> tuple[list[dict[str, object]], dict[str, object]]:
    if demand_mode not in {"cohort_rollforward", "cumulative_stack", "cumulative_transition_ensemble", "adaptive_cumulative_stack"}:
        raise ValueError("Unknown Bear demand mode")
    if demand_mode != "cohort_rollforward" and central_estimate_mode != "deterministic":
        raise ValueError("Cumulative candidate does not use independent cell arrival noise")
    if demand_mode != "cohort_rollforward" and returning_cohort_mode != "off":
        raise ValueError("Cumulative demand candidates cannot mix a second arrival model")
    if central_estimate_mode not in {"deterministic", "simulation_mean"}:
        raise ValueError("central_estimate_mode must be deterministic or simulation_mean")
    if returning_cohort_mode not in {
        "off",
        "source_calibrated_tail_mixture",
        "lane_cohort_hierarchical",
    }:
        raise ValueError(
            "returning_cohort_mode must be off, source_calibrated_tail_mixture, or lane_cohort_hierarchical"
        )
    if returning_cohort_mode != "off" and central_estimate_mode != "simulation_mean":
        raise ValueError("The returning cohort mixture requires central_estimate_mode=simulation_mean")
    if iterations < 1:
        raise ValueError("iterations must be at least 1")
    truth_rows_list = list(truth_rows)
    db_rows = list(db_rows)
    validate_bear_availability_identity([], db_rows)
    history_years = _history_years_or_bootstrap(history_years, truth_rows_list)
    if not history_years:
        return [], _skipped_no_history_report(forecast_year)
    history_year_set = {int(year) for year in history_years}
    if any(year >= forecast_year for year in history_year_set):
        raise ValueError("Bear history years must be before forecast year")
    # Intake is explicit: hidden supplemental reads cannot fill a missing lane.
    source_years_used_text = ",".join(str(year) for year in history_years)
    source_year_count = len(history_years)
    default_earliest_source_year = min(history_years)
    default_latest_source_year = max(history_years)
    ladders, meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows_list, history_year_set)
    source_files: dict[tuple[str, int], set[str]] = defaultdict(set)
    for source in truth_rows_list:
        source_files[(_clean(source.get("hunt_code")).upper(), _to_int(
            source.get("actual_draw_year") or source.get("source_year") or source.get("draw_year") or source.get("year")))].add(
                _clean(source.get("source_file")))
    retention_by_band, zero_growth, retention_history_by_band, zero_growth_history = _build_retention_and_zero_growth(ladders)
    lane_cohort_model = _build_lane_cohort_model(ladders)
    point_purchase_counts = _point_purchase_counts_by_year_residency(point_purchase_rows, history_year_set)
    returning_tail_profiles = (
        _build_source_calibrated_returning_tail_profiles(ladders, point_purchase_counts)
        if returning_cohort_mode == "source_calibrated_tail_mixture"
        else {}
    )
    calibration_cache = {}

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
        # These are dated 2026 identity decisions, not timeless aliases.
        # Earlier source-only folds must retain the original La Sal codes.
        if forecast_year == 2026 and hunt_code in BEAR_HISTORICAL_CODE_SUCCESSORS_2026:
            report_counts["historical_successor_skipped"] += 1
            continue
        history_hunt_code = hunt_code
        history_start = max(BEAR_SPLIT_HISTORY_START.get(hunt_code, 0),
                            _to_int(db_row.get("bear_history_effective_start_year")))
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
            # Calibrate within program/residency. Split hunts cannot inherit
            # pre-split demand indirectly through pooled retention/arrivals.
            calibration_key = (subtype, residency, history_start)
            if calibration_key not in calibration_cache:
                scoped = {k: v for k, v in ladders.items()
                          if k[0] == subtype and k[3] == residency and k[1] >= history_start}
                purchase_scope = {k: v for k, v in point_purchase_counts.items()
                                  if k[0] >= history_start and subtype == LIMITED_ENTRY_BEAR_HUNT}
                calibration_cache[calibration_key] = (
                    _build_retention_and_zero_growth(scoped, subtype_hint=subtype, residency_hint=residency),
                    _build_lane_cohort_model(scoped),
                    _build_source_calibrated_returning_tail_profiles(scoped, purchase_scope)
                    if returning_cohort_mode == "source_calibrated_tail_mixture" else {},
                )
            (retention_by_band, zero_growth, retention_history_by_band, zero_growth_history), lane_cohort_model, returning_tail_profiles = calibration_cache[calibration_key]
            history_residency, available_years, history_scope_flag = history_context(subtype, history_hunt_code, residency)
            available_years = [year for year in available_years if year >= history_start]
            latest_year = forecast_year - 1
            earliest_source_year = available_years[0] if available_years else ""
            latest_ladder = ladders.get((subtype, latest_year, history_hunt_code, history_residency), {}) if latest_year in available_years else {}
            prior_total = sum(int(values.get("total", 0)) for values in latest_ladder.values())
            # Forecast assumption only: exact immediately prior program/lane
            # awards, never a current catalog or another residency's permits.
            public_quota = prior_total
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
            base.update(source_years_used=",".join(map(str, available_years)),
                        source_year_count=len(available_years),
                        earliest_source_year=earliest_source_year,
                        latest_source_year=available_years[-1] if available_years else "",
                        public_permits_target=public_quota,
                        forecast_quota_proxy=public_quota if latest_ladder else "",
                        quota_source="SOURCE_YEAR_CANONICAL_AWARDS_PROXY",
                        quota_source_type="SOURCE_YEAR_CANONICAL_AWARDS_PROXY",
                        quota_source_year=str(latest_year),
                        quota_source_file="|".join(sorted(source_files.get((hunt_code, latest_year), set()))),
                        quota_is_current_allocation="FALSE")
            base["crosswalk_status"] = "DIRECT_HISTORICAL_TO_CURRENT_CODE" if history_hunt_code != hunt_code else ""
            if history_start:
                base.update(history_effective_start_year=history_start,
                            crosswalk_status="BOUNDARY_SPLIT_POST_EFFECTIVE_HISTORY_ONLY",
                            source_years_used=",".join(map(str, available_years)),
                            source_year_count=len(available_years),
                            earliest_source_year=available_years[0] if available_years else "",
                            latest_source_year=available_years[-1] if available_years else "")
            if hunt_code in BEAR_SPLIT_HISTORY_START:
                base.update(effective_split_year=2026, use_pre_split_history=False, use_forward_from=2026)
                if forecast_year == 2026:
                    base.update(public_permits_target=BEAR_SPLIT_REFERENCE_TOTALS_2026[hunt_code],
                                public_permits_target_scope="WHOLE_HUNT_REFERENCE_NOT_MODEL_QUOTA",
                                public_permits_target_source=BEAR_SPLIT_REFERENCE_SOURCE,
                                source_file=BEAR_SPLIT_REFERENCE_SOURCE,
                                source_file_role="CURRENT_IDENTITY_AND_PERMIT_REFERENCE_NOT_DRAW_TRUTH")
            # Retain the narrow current-target identity bridge in diagnostic
            # output. Its current permit split is target configuration only;
            # it never contributes applicant or probability evidence.
            if _clean(db_row.get("target_identity_diagnostic")):
                base["target_identity_diagnostic"] = _clean(db_row.get("target_identity_diagnostic"))
                base["bear_target_identity_status"] = _clean(db_row.get("bear_target_identity_status"))
                base["bear_crosswalk_parent_hunt_code"] = _clean(db_row.get("bear_crosswalk_parent_hunt_code"))
                base["public_permits_source"] = _clean(db_row.get("forecast_permits_source"))

            if subtype == UNLIMITED_PURSUIT_PERMIT and hunt_code in BEAR_AVAILABILITY_PRODUCTS:
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

            if subtype == HARVEST_OBJECTIVE_AVAILABILITY and hunt_code in BEAR_AVAILABILITY_PRODUCTS:
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

            if public_quota <= 0 and latest_ladder:
                flags = ["ZERO_SOURCE_YEAR_AWARDS_PROXY", "FIRST_CHOICE_ONLY_MODEL"]
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
                        "draw_outlook": "INSUFFICIENT QUOTA EVIDENCE",
                        "bear_bonus_valid": "FALSE",
                        "bear_bonus_note": "The source-year official lane awarded zero permits; this proxy does not prove a current zero allocation.",
                        "data_quality_flags": "|".join(flags),
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "ZERO_SOURCE_YEAR_AWARDS_PROXY",
                            "NO_PUBLIC_DRAW_PROBABILITY_FOR_RESIDENCY",
                        ),
                    }
                )
                rows.append(row)
                report_counts["excluded"] += 1
                continue

            if not latest_ladder or public_quota <= 0:
                flags = []
                if not latest_ladder:
                    flags.append("MISSING_SOURCE_YEAR_PROGRAM_RESIDENCY_LADDER")
                is_new_unit_without_history = (
                    _clean(db_row.get("bear_target_identity_status"))
                    == "CURRENT_NEW_UNIT_NO_COMPARABLE_HISTORY"
                )
                if not available_years:
                    flags.append("MISSING_PROVEN_BEAR_DRAW_HISTORY")
                    if history_start:
                        flags.append("SPLIT_UNIT_POST_EFFECTIVE_HISTORY_REQUIRED")
                    if is_new_unit_without_history:
                        flags.append("NEW_UNIT_NO_COMPARABLE_HISTORY")
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
                        "bear_bonus_note": (
                            "Current official public-draw Bear unit is new and has no comparable prior official applicant ladder; no probability is modeled."
                            if is_new_unit_without_history
                            else "Missing proven bear history or usable 2026 public quota for this residency."
                        ),
                        "algorithm_status": (
                            "NOT_SCORED_NEW_UNIT_NO_COMPARABLE_HISTORY"
                            if is_new_unit_without_history
                            else "IN_SCOPE_MODEL_PENDING"
                        ),
                        "data_quality_flags": "|".join(flags),
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "MISSING_SOURCE_YEAR_PROGRAM_RESIDENCY_LADDER" if not latest_ladder else "",
                            BEAR_NO_PRIOR_LADDER_REASON_CODE if "MISSING_PROVEN_BEAR_DRAW_HISTORY" in flags else "",
                            "NOT_SCORED_NEW_UNIT_NO_COMPARABLE_HISTORY" if is_new_unit_without_history else "",
                            "NO_PUBLIC_DRAW_PROBABILITY_FOR_RESIDENCY" if public_quota <= 0 else "",
                        ),
                    }
                )
                if history_start and not available_years:
                    row.update(algorithm_status="NO_TRANSITION_EVIDENCE", probability_model="NONE",
                               no_transition_reason=(
                                   "Split-unit effective 2026 per DWR p.4 + WORK_LOG 2026-09-20 + crosswalk "
                                   "CURRENT_SPLIT_CHILD_NO_PRIOR_DRAW_ROW / HISTORICAL_CODE_RECODED - pre-split "
                                   "BR7008/7108/7208/7307 2020-2025 not comparable due to boundary change + "
                                   "applicant redistribution unknown - copying same stack into both child units "
                                   "invalid - no forward history from 2026 exists yet for 2026 prediction - "
                                   "will use forward from 2026"
                                   if hunt_code in BEAR_SPLIT_HISTORY_START else
                                   f"No comparable program history from effective year {history_start}"),
                               reason_codes=append_reason_codes(row.get("reason_codes"), "NO_TRANSITION_EVIDENCE"))
                rows.append(row)
                report_counts["pending"] += 1
                continue

            max_point_permits, random_permits = _split_bear_bonus_permits(public_quota, residency)
            lane_cohort_calibrations: dict[int, _BearCohortCalibration] = {}
            joint_transition_years = []
            adaptive_blend = ""
            if returning_cohort_mode == "lane_cohort_hierarchical":
                forecast_ladder, lane_cohort_calibrations = _forecast_lane_cohort_ladder(
                    latest_ladder,
                    lane_cohort_model,
                    subtype=subtype,
                    hunt_code=history_hunt_code,
                    residency=history_residency,
                )
                sampled_ladders = (
                    _sample_lane_cohort_forecast_ladders(
                        latest_ladder,
                        lane_cohort_calibrations,
                        iterations=iterations,
                        seed=f"{seed}|lane-cohort|{subtype}|{hunt_code}|{residency}|{latest_year}",
                    )
                    if central_estimate_mode == "simulation_mean"
                    else []
                )
            else:
                forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
                if demand_mode == "cumulative_stack":
                    forecast_ladder = _forecast_cumulative_stack(
                        {k: v for k, v in ladders.items() if k[1] >= history_start},
                        subtype, history_hunt_code, history_residency)
                sampled_ladders = (
                    _sample_bear_forecast_ladders(
                        latest_ladder,
                        retention_history_by_band,
                        zero_growth_history,
                        iterations,
                        f"{seed}|{subtype}|{hunt_code}|{residency}|{latest_year}",
                        returning_tail_profiles.get((subtype, history_hunt_code, history_residency), ()),
                    )
                    if central_estimate_mode == "simulation_mean"
                    else []
                )
                if demand_mode == "cumulative_transition_ensemble":
                    forecast_ladder, sampled_ladders, joint_transition_years = _forecast_cumulative_transition_ensemble(
                        {k: v for k, v in ladders.items() if k[1] >= history_start},
                        subtype, history_hunt_code, history_residency)
                if demand_mode == "adaptive_cumulative_stack":
                    forecast_ladder, adaptive_blend, joint_transition_years = _forecast_adaptive_cumulative_stack(
                        {k: v for k, v in ladders.items() if k[1] >= history_start},
                        subtype, history_hunt_code, history_residency)
            returning_profile_count = len(
                returning_tail_profiles.get((subtype, history_hunt_code, history_residency), ())
            )
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
                lane_calibration = lane_cohort_calibrations.get(int(points))
                has_point_history = any(
                    values.get("eligible", 0) > 0
                    for year in available_years
                    for level, values in ladders[(subtype, year, history_hunt_code, history_residency)].items()
                    if level in {int(points), int(points)-1}
                )
                applicants_by_points = {int(level): int(count) for level, count in forecast_ladder.items()}
                # Conditional odds for ONE applicant, not the probability that
                # somebody exists in a rounded demand cell. This does not add
                # arrivals to the demand forecast used by other point levels.
                applicants_by_points = _condition_for_focal_bear_applicant(applicants_by_points, points)
                p_bonus_pool, applicants_above, applicants_at_level = compute_bonus_pool_probability(points, applicants_by_points, max_point_permits)
                p_random_pool = _weighted_random_probability(points, applicants_by_points, random_permits, max_point_permits)
                p_draw = combine_probabilities(p_bonus_pool, p_random_pool)
                deterministic_p_bonus_pool = p_bonus_pool
                deterministic_p_random_pool = p_random_pool
                p_draw_p10 = max(0.0, p_draw - 0.05)
                p_draw_p50 = p_draw
                p_draw_p90 = min(1.0, p_draw + 0.05)
                if central_estimate_mode == "simulation_mean":
                    (
                        simulated_p_bonus_pool,
                        simulated_p_random_pool,
                        _simulated_p_draw,
                        p_draw_p10,
                        p_draw_p50,
                        p_draw_p90,
                    ) = _bear_simulation_probability(
                        points,
                        sampled_ladders,
                        max_point_permits,
                        random_permits,
                    )
                    # This uncertainty layer represents unobserved returning or
                    # switching applicants.  It may discount a deterministic
                    # chance, but it must never create a higher chance or move
                    # a false guarantee to a different point rung.
                    p_bonus_pool = min(deterministic_p_bonus_pool, simulated_p_bonus_pool)
                    p_random_pool = min(deterministic_p_random_pool, simulated_p_random_pool)
                    p_draw = combine_probabilities(p_bonus_pool, p_random_pool)
                if demand_mode == "cumulative_transition_ensemble":
                    # Average complete scenario probabilities, NOT a product
                    # of separately averaged max/random components. Their
                    # dependence is material when a lane moves across cutoff.
                    p_bonus_pool, p_random_pool, p_draw, p_draw_p10, p_draw_p50, p_draw_p90 = _bear_simulation_probability(
                        points, sampled_ladders, max_point_permits, random_permits)
                p_draw_before_existing_ceiling = p_draw
                structural_future_certainty = p_draw >= 1.0 - 1e-12
                total_scope_guarantee_blocked = (
                    history_scope_flag == "TOTAL_SCOPE_HISTORY_USED_FOR_RESIDENCY"
                    and structural_future_certainty
                )
                if not total_scope_guarantee_blocked:
                    # A projected applicant stack may clear structurally, but
                    # a future Utah draw is never an observed guarantee. Keep
                    # the internal draw-line evidence while withholding 100%
                    # visitor-facing certainty.
                    p_draw = min(FUTURE_BEAR_DRAW_PROBABILITY_CEILING, p_draw)
                    p_draw_p10 = min(FUTURE_BEAR_DRAW_PROBABILITY_CEILING, p_draw_p10)
                    p_draw_p50 = min(FUTURE_BEAR_DRAW_PROBABILITY_CEILING, p_draw_p50)
                    p_draw_p90 = min(FUTURE_BEAR_DRAW_PROBABILITY_CEILING, p_draw_p90)
                row = dict(base)
                row.update(
                    {
                        "points": str(points),
                        "max_point_permits_2025": "",
                        "max_point_permits_2026": max_point_permits,
                        "random_permits_2025": "",
                        "random_permits_2026": random_permits,
                        # A combined applicant ladder can support neither a
                        # resident nor a nonresident exact guarantee.  Keep
                        # its lower-probability signal, but never surface a
                        # lane-specific draw line or 100% outcome from it.
                        "guaranteed_at_2025": "" if total_scope_guarantee_blocked or prior_guaranteed is None else str(prior_guaranteed),
                        "guaranteed_at_2026": "" if total_scope_guarantee_blocked or forecast_guaranteed is None else str(forecast_guaranteed),
                        "applicants_above": applicants_above,
                        "applicants_at_level": applicants_at_level,
                        "p_preference_draw": "",
                        "p_bonus_pool": "" if total_scope_guarantee_blocked else f"{p_bonus_pool:.6f}",
                        "p_random_pool": "" if total_scope_guarantee_blocked else f"{p_random_pool:.6f}",
                        "p_draw": "" if total_scope_guarantee_blocked else f"{p_draw:.6f}",
                        "p_draw_mean": "" if total_scope_guarantee_blocked else f"{p_draw:.6f}",
                        "bear_demand_mode": demand_mode,
                        "p_draw_before_existing_ceiling": f"{p_draw_before_existing_ceiling:.6f}",
                        "bear_demand_transition_years": ",".join(map(str, joint_transition_years)),
                        "bear_demand_adaptive_blend": adaptive_blend,
                        "bear_demand_scenario_count": len(sampled_ladders) if demand_mode == "cumulative_transition_ensemble" else "",
                        "p_draw_p10": "" if total_scope_guarantee_blocked else f"{p_draw_p10:.6f}",
                        "p_draw_p50": "" if total_scope_guarantee_blocked else f"{p_draw_p50:.6f}",
                        "p_draw_p90": "" if total_scope_guarantee_blocked else f"{p_draw_p90:.6f}",
                        "p_bonus_pool_pct": "" if total_scope_guarantee_blocked else f"{p_bonus_pool * 100.0:.3f}",
                        "p_random_pool_pct": "" if total_scope_guarantee_blocked else f"{p_random_pool * 100.0:.3f}",
                        "p_draw_pct": "" if total_scope_guarantee_blocked else f"{p_draw * 100.0:.3f}",
                        "random_draw_odds_2026": "" if total_scope_guarantee_blocked else f"{p_random_pool * 100.0:.3f}",
                        "gap": "" if total_scope_guarantee_blocked or forecast_guaranteed is None else str(forecast_guaranteed - points),
                        "delta_gap": "" if total_scope_guarantee_blocked or forecast_guaranteed is None or prior_guaranteed is None else str((forecast_guaranteed - points) - (prior_guaranteed - points)),
                        "status": "INSUFFICIENT LANE EVIDENCE" if total_scope_guarantee_blocked else _status(max_point_permits, random_permits, p_bonus_pool),
                        "trend": _trend(prior_guaranteed, forecast_guaranteed),
                        "draw_outlook": _draw_outlook(0.0, pending=True) if total_scope_guarantee_blocked else _draw_outlook(p_draw),
                        "bear_bonus_valid": "FALSE" if total_scope_guarantee_blocked else "TRUE",
                        "bear_bonus_note": (
                            "Combined-residency bear applicant history cannot establish a resident or nonresident guarantee."
                            if total_scope_guarantee_blocked
                            else (
                            f"Forecasted from {latest_year} public Bear draw history with source-calibrated returning-applicant tail scenarios; "
                            "statewide point-purchase counts corroborate the historical source pool but are not allocated to this hunt."
                            if returning_cohort_mode == "source_calibrated_tail_mixture" and returning_profile_count
                            else (
                            f"Forecasted from {latest_year} public bear draw history with source-transition Monte Carlo uncertainty."
                            if central_estimate_mode == "simulation_mean"
                            else f"Forecasted from {latest_year} public bear draw history with Utah bonus split rules."
                            )
                            )
                        ),
                        "returning_cohort_mode": returning_cohort_mode,
                        "returning_tail_profile_count": str(returning_profile_count),
                        "bear_cohort_evidence_scope": "" if lane_calibration is None else lane_calibration.evidence_scope,
                        "bear_cohort_reapply_rate": "" if lane_calibration is None else f"{lane_calibration.reapply_rate:.6f}",
                        "bear_cohort_arrival_count": "" if lane_calibration is None else f"{lane_calibration.arrival_count:.6f}",
                        "bear_cohort_exact_unsuccessful": "" if lane_calibration is None else str(lane_calibration.exact_unsuccessful),
                        "bear_cohort_exact_transitions": "" if lane_calibration is None else str(lane_calibration.exact_transitions),
                        "algorithm_status": (
                            "NOT_SCORED_TOTAL_SCOPE_RESIDENCY_GUARANTEE_BLOCKED"
                            if total_scope_guarantee_blocked
                            else ALGORITHM_STATUS_MODELED_BONUS
                        ),
                        "reason_codes": append_reason_codes(
                            row.get("reason_codes"),
                            "BEAR_SOURCE_TRANSITION_UNCERTAINTY_DISCOUNT" if central_estimate_mode == "simulation_mean" else "",
                            "BEAR_SOURCE_CALIBRATED_RETURNING_TAIL_MIXTURE"
                            if returning_cohort_mode == "source_calibrated_tail_mixture" and returning_profile_count
                            else "",
                            "TOTAL_SCOPE_RESIDENCY_GUARANTEE_BLOCKED" if total_scope_guarantee_blocked else "",
                            "FUTURE_BEAR_DRAW_PROBABILITY_CEILING_APPLIED"
                            if structural_future_certainty and not total_scope_guarantee_blocked
                            else "",
                        ),
                        "data_quality_flags": "|".join(flags),
                    }
                )
                rows.append(row)
                if not has_point_history:
                    # An empty historical upper rung is neither a zero chance
                    # nor a guaranteed opportunity. Preserve its reasoned blank.
                    for field in tuple(row):
                        if field.startswith("p_") or field in {"display_odds_pct", "guaranteed_at_2026"}:
                            row[field] = ""
                    row.update(algorithm_status="NO_TRANSITION_EVIDENCE", bear_bonus_valid="FALSE",
                               probability_model="NONE", draw_outlook="Insufficient evidence",
                               bear_bonus_note="No same-lane applicant evidence at this point or its predecessor; probability withheld.",
                               reason_codes=append_reason_codes(row.get("reason_codes"), "NO_TRANSITION_EVIDENCE"))
                if total_scope_guarantee_blocked or not has_point_history:
                    report_counts["pending"] += 1
                else:
                    report_counts["modeled"] += 1

    validate_bear_availability_identity(rows, db_rows)
    observed_history_rows = [row for row in truth_rows_list if is_bear_row(row)]
    review_counter = Counter(classify_bear_subtype(row) for row in review_rows)
    modeled_rows = [row for row in rows if _clean(row.get("bear_bonus_valid")) == "TRUE"]

    report = {
        "forecast_year": forecast_year,
        "quota_authority": "SOURCE_YEAR_CANONICAL_AWARDS_PROXY",
        "database_quota_used": False,
        "retention_calibration_boundary": "BEAR_PROGRAM_AND_RESIDENCY",
        "central_estimate_mode": central_estimate_mode,
        "iterations": iterations,
        "returning_cohort_mode": returning_cohort_mode,
        "statewide_point_purchase_source_row_count": sum(
            len(levels) for levels in point_purchase_counts.values()
        ),
        "returning_tail_profile_lane_count": len(returning_tail_profiles),
        "returning_tail_profile_count": sum(len(profiles) for profiles in returning_tail_profiles.values()),
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
        # Inventory only: never a replacement for independently joined scores or MAE.
        "restricted_pursuit_measured_row_count": _measured_pursuit_row_count(ladders),
        "restricted_pursuit_measured_row_count_basis": "SOURCE_LADDER_ELIGIBLE_POSITIVE_POINT_CELLS_NOT_SCORED_FORECASTS",
        "bear_400_plus_below_10pp_claim": "UNVERIFIED",
        "candidate_behavior_acceptance_status": "NOT_VALIDATED_NOT_FOR_PROMOTION",
        "retention_calibration_per_program_residency": "BEAR_PROGRAM_AND_RESIDENCY_SPECIFIC_DEFAULTS_APPLIED",
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
