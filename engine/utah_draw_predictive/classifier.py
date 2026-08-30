"""Target-scope draw-system classifier and coverage audit for Utah predictive draws."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path
from typing import Mapping

from . import (
    ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
    ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    ALGORITHM_STATUS_MODELED_ALLOCATION,
    ALGORITHM_STATUS_MODELED_AVAILABILITY,
    ALGORITHM_STATUS_MODELED_BONUS,
    ALGORITHM_STATUS_MODELED_PREFERENCE,
    ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
    ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW,
    ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET,
    ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW,
    ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW,
    TARGET_SCOPE_OUT_OF_SCOPE,
    TARGET_SCOPE_TARGET,
)
from .bear import (
    STRATEGY_SPECS as BEAR_SPECS,
    BEAR_DRAW_SYSTEM_TYPE,
    CONSERVATION_OR_NON_PUBLIC,
    HARVEST_OBJECTIVE_AVAILABILITY,
    LIMITED_ENTRY_BEAR_HUNT,
    REMAINING_PERMIT_AVAILABILITY,
    RESTRICTED_BEAR_PURSUIT,
    STATEWIDE_BEAR_PERMIT,
    UNKNOWN_BEAR_SUBTYPE,
    UNLIMITED_PURSUIT_PERMIT,
    classify_bear_subtype,
    is_bear_row,
    is_excluded_bear_row,
    is_harvest_objective_bear_row,
    is_modeled_bear_row,
    is_modeled_bear_availability_row,
    is_nonpublic_bear_row,
    is_remaining_bear_row,
    is_supported_bear_bonus_row,
)
from .bonus import STRATEGY_SPECS as BONUS_SPECS
from .dedicated_hunter import STRATEGY_SPECS as DEDICATED_SPECS, is_modeled_dedicated_hunter_row
from .exclusions import STRATEGY_SPECS as EXCLUSION_SPECS
from .mountain_lion import (
    STRATEGY_SPECS as MOUNTAIN_LION_SPECS,
    DRAW_SYSTEM_TYPE as MOUNTAIN_LION_DRAW_SYSTEM_TYPE,
    is_mountain_lion_row,
    is_modeled_mountain_lion_row,
)
from .preference_antlerless import STRATEGY_SPECS as PREFERENCE_ANTLERLESS_SPECS, is_modeled_antlerless_row
from .preference_general_deer import STRATEGY_SPECS as PREFERENCE_GENERAL_DEER_SPECS, is_modeled_general_deer_row
from .private_lands_antlerless_elk import (
    STRATEGY_SPECS as PRIVATE_LANDS_ANTLERLESS_ELK_SPECS,
    DRAW_SYSTEM_TYPE as PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE,
    is_private_lands_antlerless_elk_row,
    is_modeled_private_lands_antlerless_elk_row,
)
from .random_only import STRATEGY_SPECS as RANDOM_ONLY_SPECS
from .special_bonus import PHASE6_DRAW_SYSTEM_TYPES, is_modeled_phase6_bonus_row
from .sportsman import STRATEGY_SPECS as SPORTSMAN_SPECS, SPORTSMAN_DRAW_SYSTEM_TYPE, is_modeled_sportsman_row, is_sportsman_permit_row
from .taxonomy import draw_design_contract_flags, effective_draw_design
from .turkey import (
    STRATEGY_SPECS as TURKEY_SPECS,
    TURKEY_DRAW_SYSTEM_TYPE,
    YOUTH_TURKEY_DRAW_SYSTEM_TYPE,
    is_general_season_turkey_row,
    is_modeled_turkey_row,
    is_modeled_youth_turkey_row,
    is_nonpublic_turkey_row,
    is_remaining_turkey_row,
    is_supported_turkey_bonus_row,
    is_turkey_row,
    is_youth_turkey_row,
)
from .youth import (
    STRATEGY_SPECS as YOUTH_SPECS,
    YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE,
    YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE,
    YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE,
    YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
    YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE,
    is_youth_antlerless_or_doe_row,
    is_youth_draw_only_elk_row,
    is_youth_general_deer_row,
    is_youth_otc_or_availability_row,
    resolve_youth_algorithm_status,
)


REPO = Path(__file__).resolve().parents[2]
OBSERVED_RUNTIME_PATH = REPO / "processed_data" / "draw_reality_engine_v2.csv"
PREDICTIVE_PATH = REPO / "processed_data" / "draw_reality_engine_predictive_v2.csv"

ALL_SPECS = (
    BONUS_SPECS
    + BEAR_SPECS
    + PREFERENCE_GENERAL_DEER_SPECS
    + PREFERENCE_ANTLERLESS_SPECS
    + DEDICATED_SPECS
    + YOUTH_SPECS
    + PRIVATE_LANDS_ANTLERLESS_ELK_SPECS
    + MOUNTAIN_LION_SPECS
    + SPORTSMAN_SPECS
    + TURKEY_SPECS
    + RANDOM_ONLY_SPECS
    + EXCLUSION_SPECS
)
REGISTRY = {spec.draw_system_type: spec for spec in ALL_SPECS}
DRAW_SYSTEM_ORDER = [spec.draw_system_type for spec in ALL_SPECS]
DRAW_SYSTEM_ORDER = list(dict.fromkeys(DRAW_SYSTEM_ORDER))
LEGACY_BONUS_DRAW_DESIGNS = {"MAX_WEIGHTED_SPLIT"}

OUT_OF_SCOPE_TOKENS = (
    "swan",
    "sandhill crane",
    "crane",
    "sharp-tailed grouse",
    "sharp tailed grouse",
    "sage-grouse",
    "sage grouse",
    "greater sage grouse",
    "waterfowl",
    "duck",
    "goose",
    "geese",
    "small game",
    "fishing",
    "fish",
    "upland game",
)
BIG_GAME_TOKENS = (
    "deer",
    "elk",
    "pronghorn",
    "moose",
    "bison",
    "mountain goat",
    "goat",
    "bighorn sheep",
    "desert bighorn",
    "rocky mountain bighorn",
    "sheep",
)
TARGET_OTHER_TOKENS = ("turkey", "black bear", "bear", "mountain lion", "lion", "cougar")
TARGET_DRAW_SYSTEM_TYPES = {
    "BONUS_OIL_BIG_GAME",
    "BONUS_LE_BIG_GAME",
    "BONUS_PLE_BIG_GAME",
    "BONUS_CWMU_BIG_GAME",
    "BONUS_ANTLERLESS_MOOSE",
    "BONUS_EWE_BIGHORN",
    "BONUS_TURKEY",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
    "SPORTSMAN_PERMIT",
    "GENERAL_BIG_GAME_OTHER",
    "BEAR_DRAW",
    "COUGAR_LICENSE_BASED",
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK",
    "YOUTH_GENERAL_DEER_RESERVE",
    "YOUTH_ANTLERLESS_OR_DOE_RESERVE",
    "YOUTH_GENERAL_ANY_BULL_ELK",
    "YOUTH_OTC_OR_AVAILABILITY",
    "YOUTH_TURKEY_SET_ASIDE",
    "RANDOM_ONLY_TARGET",
    "OTC_OR_REMAINING_TARGET",
    "LANDOWNER_BIG_GAME",
    "MITIGATION_OR_DEPREDATION_BIG_GAME",
    "UNKNOWN_TARGET",
}

TRUE_PLE_HUNT_CODES = {
    "DB0009",
    "DB1000",
    "DB1001",
    "DB1002",
    "DB1003",
    "DB1004",
    "DB1005",
    "DB1006",
    "DB1007",
    "DB1008",
}


def _canonical_big_game_bonus_draw_system(row: Mapping[str, object]) -> str:
    text = _joined_text(row)
    hunt_code = _clean(row.get("hunt_code")).upper()
    species = _clean_lower(row.get("species"))
    if hunt_code in TRUE_PLE_HUNT_CODES:
        return "BONUS_PLE_BIG_GAME"
    if "premium limited entry" in text or "premium limited-entry" in text or "p.l.e" in text:
        return "BONUS_PLE_BIG_GAME"
    if "once-in-a-lifetime" in text or "once in a lifetime" in text or "o.i.l." in text or "oial" in text:
        return "BONUS_OIL_BIG_GAME"
    if species in {"bison", "mountain goat"}:
        return "BONUS_OIL_BIG_GAME"
    if "bighorn sheep" in text and "ewe" not in text:
        return "BONUS_OIL_BIG_GAME"
    if species == "moose" and "antlerless" not in text:
        return "BONUS_OIL_BIG_GAME"
    return "BONUS_LE_BIG_GAME"


def _clean(value: object) -> str:
    return str(value or "").strip()


def _clean_lower(value: object) -> str:
    return _clean(value).lower()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _safe_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(REPO))
    except ValueError:
        return str(path)


def _joined_text(row: Mapping[str, object]) -> str:
    parts = [
        row.get("hunt_code"),
        row.get("hunt_name"),
        row.get("species"),
        row.get("sex_type"),
        row.get("hunt_type"),
        row.get("hunt_class"),
        row.get("weapon"),
        row.get("draw_pool"),
        row.get("source_file"),
        row.get("NOTES"),
    ]
    return " ".join(_clean_lower(part) for part in parts if _clean(part))


def _normalized_token_text(row: Mapping[str, object]) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _joined_text(row)).strip()


def is_out_of_scope_non_target(row: Mapping[str, object]) -> bool:
    text = _normalized_token_text(row)
    # Keep explicit bird-species exclusions, but do not let geographic names like
    # "Grouse Creek" force target-scope elk rows into the out-of-scope bucket.
    return any(f" {token} " in f" {text} " for token in OUT_OF_SCOPE_TOKENS) and " turkey " not in f" {text} "


def is_target_scope(row: Mapping[str, object]) -> bool:
    text = _joined_text(row)
    if is_out_of_scope_non_target(row):
        return False
    if any(token in text for token in TARGET_OTHER_TOKENS):
        return True
    if any(token in text for token in BIG_GAME_TOKENS):
        return True
    return False


def classify_draw_system_type(row: Mapping[str, object]) -> str:
    text = _joined_text(row)
    hunt_code = _clean(row.get("hunt_code")).upper()
    hunt_type = _clean_lower(row.get("hunt_type"))
    hunt_class = _clean_lower(row.get("hunt_class"))
    species = _clean_lower(row.get("species"))
    sex_type = _clean_lower(row.get("sex_type"))
    draw_pool = _clean_lower(row.get("draw_pool"))
    if is_out_of_scope_non_target(row):
        return "OUT_OF_SCOPE_NON_TARGET"

    existing_draw_system_type = effective_draw_design(row)
    # Raw UtahDraws rows use MAX_WEIGHTED_SPLIT for both big-game bonus draws
    # and source-classified turkey rows.  Resolve target-specific systems before
    # the legacy big-game alias so adult and youth turkey ladders cannot collapse
    # into one BONUS_LE_BIG_GAME key.  Sportsman remains first because it is a
    # distinct random-only draw regardless of its source draw-design label.
    if is_sportsman_permit_row(row):
        return SPORTSMAN_DRAW_SYSTEM_TYPE
    if is_bear_row(row):
        return BEAR_DRAW_SYSTEM_TYPE
    if is_turkey_row(row):
        if is_youth_turkey_row(row):
            return YOUTH_TURKEY_DRAW_SYSTEM_TYPE
        if is_supported_turkey_bonus_row(row):
            return TURKEY_DRAW_SYSTEM_TYPE
        if is_general_season_turkey_row(row) or is_remaining_turkey_row(row) or is_nonpublic_turkey_row(row) or "fall management" in text or "statewide" in text:
            return "OTC_OR_REMAINING_TARGET"
        return TURKEY_DRAW_SYSTEM_TYPE
    if "cwmu" in text and hunt_class == "private":
        return "LANDOWNER_BIG_GAME"
    if "cwmu" in text:
        return "BONUS_CWMU_BIG_GAME"
    if existing_draw_system_type in LEGACY_BONUS_DRAW_DESIGNS:
        return _canonical_big_game_bonus_draw_system(row)
    if existing_draw_system_type and (
        is_modeled_general_deer_row(row)
        or is_modeled_antlerless_row(row)
        or is_modeled_dedicated_hunter_row(row)
        or is_modeled_phase6_bonus_row(row)
        or is_modeled_turkey_row(row)
        or is_modeled_youth_turkey_row(row)
        or is_modeled_bear_row(row)
        or is_modeled_sportsman_row(row)
    ):
        return existing_draw_system_type

    if is_modeled_private_lands_antlerless_elk_row(row):
        return PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE

    if is_modeled_mountain_lion_row(row):
        return MOUNTAIN_LION_DRAW_SYSTEM_TYPE

    if "mountain lion" in text or "cougar" in text:
        return "COUGAR_LICENSE_BASED"
    if is_youth_draw_only_elk_row(row):
        return YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE
    if is_youth_otc_or_availability_row(row):
        return YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE
    if is_youth_general_deer_row(row):
        return YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE
    if is_youth_antlerless_or_doe_row(row):
        return YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE

    if "mitigation" in text or "depredation" in text:
        return "MITIGATION_OR_DEPREDATION_BIG_GAME"
    if is_private_lands_antlerless_elk_row(row):
        return "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"
    if any(token in text for token in ("conservation", "expo", "sportsman")):
        return "OTC_OR_REMAINING_TARGET"
    if "landowner" in text or "private land only" in text or hunt_class == "private":
        return "LANDOWNER_BIG_GAME"
    if (
        "remaining permit" in text
        or " otc" in f" {text}"
        or "o.t.c" in text
        or "over the counter" in text
        or "capped permit" in text
    ):
        return "OTC_OR_REMAINING_TARGET"
    if "restricted pursuit" in text or "extended archery" in text:
        return "RANDOM_ONLY_TARGET"

    if "moose" in text and ("antlerless" in text or sex_type in {"antlerless", "cow", "cow only"}):
        return "BONUS_ANTLERLESS_MOOSE"
    if "bighorn" in text and ("ewe" in text or sex_type == "ewe"):
        return "BONUS_EWE_BIGHORN"

    if hunt_code in TRUE_PLE_HUNT_CODES:
        return "BONUS_PLE_BIG_GAME"

    if draw_pool == "dedicated_hunter" or draw_pool == "youth_dedicated_hunter" or "dedicated hunter" in text:
        return "PREFERENCE_DEDICATED_HUNTER_DEER"

    if ("doe" in text or sex_type == "doe") and "pronghorn" in text:
        return "PREFERENCE_DOE_PRONGHORN"
    if "antlerless" in text and "deer" in text:
        return "PREFERENCE_ANTLERLESS_DEER"
    if "antlerless" in text and "elk" in text:
        return "PREFERENCE_ANTLERLESS_ELK"

    if "general season" in text or "general-season" in text or "management buck deer" in text or "cactus buck" in text:
        if "deer" in text and "buck" in text:
            return "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
        return "GENERAL_BIG_GAME_OTHER"

    if "premium limited entry" in text or "premium limited-entry" in text or "p.l.e" in text:
        return "BONUS_PLE_BIG_GAME"
    if "once-in-a-lifetime" in text or "once in a lifetime" in text or "o.i.l." in text or "oial" in text:
        return "BONUS_OIL_BIG_GAME"
    if any(token in text for token in BIG_GAME_TOKENS):
        if "limited entry" in text or "limited-entry" in text:
            return "BONUS_LE_BIG_GAME"
        if species in {"bison", "mountain goat"}:
            return "BONUS_OIL_BIG_GAME"
        if "bighorn sheep" in text and "ewe" not in text:
            return "BONUS_OIL_BIG_GAME"
        if species == "moose" and "antlerless" not in text:
            return "BONUS_OIL_BIG_GAME"
        return "GENERAL_BIG_GAME_OTHER"

    if is_target_scope(row):
        return "UNKNOWN_TARGET"
    return "OUT_OF_SCOPE_NON_TARGET"


def resolve_algorithm_status(row: Mapping[str, object], draw_system_type: str | None = None) -> str:
    draw_system_type = draw_system_type or classify_draw_system_type(row)
    if draw_system_type in LEGACY_BONUS_DRAW_DESIGNS:
        draw_system_type = _canonical_big_game_bonus_draw_system(row)
    if draw_system_type in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        draw_system_type = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
    if draw_system_type == "PREFERENCE_GENERAL_SEASON_BUCK_DEER":
        return ALGORITHM_STATUS_MODELED_PREFERENCE if is_modeled_general_deer_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type in {"PREFERENCE_ANTLERLESS_DEER", "PREFERENCE_ANTLERLESS_ELK", "PREFERENCE_DOE_PRONGHORN"}:
        return ALGORITHM_STATUS_MODELED_PREFERENCE if is_modeled_antlerless_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == "PREFERENCE_DEDICATED_HUNTER_DEER":
        return ALGORITHM_STATUS_MODELED_PREFERENCE if is_modeled_dedicated_hunter_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_MODELED_ALLOCATION if is_modeled_private_lands_antlerless_elk_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == MOUNTAIN_LION_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW if is_mountain_lion_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == SPORTSMAN_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW if is_modeled_sportsman_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type in {
        YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
        YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE,
        YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE,
        YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE,
    }:
        return resolve_youth_algorithm_status(row, draw_system_type)
    if draw_system_type == TURKEY_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_MODELED_BONUS if is_modeled_turkey_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == YOUTH_TURKEY_DRAW_SYSTEM_TYPE:
        return ALGORITHM_STATUS_MODELED_BONUS if is_modeled_youth_turkey_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type == BEAR_DRAW_SYSTEM_TYPE:
        subtype = classify_bear_subtype(row)
        if is_modeled_bear_row(row):
            return ALGORITHM_STATUS_MODELED_BONUS
        if subtype in {HARVEST_OBJECTIVE_AVAILABILITY, UNLIMITED_PURSUIT_PERMIT} and is_modeled_bear_availability_row(row):
            return ALGORITHM_STATUS_MODELED_AVAILABILITY
        if is_excluded_bear_row(row):
            return ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW
        return ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    if draw_system_type in PHASE6_DRAW_SYSTEM_TYPES:
        return ALGORITHM_STATUS_MODELED_BONUS if is_modeled_phase6_bonus_row(row) else ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING
    return REGISTRY[draw_system_type].algorithm_status


def target_scope_label(row: Mapping[str, object], draw_system_type: str | None = None) -> str:
    draw_system_type = draw_system_type or classify_draw_system_type(row)
    if draw_system_type in LEGACY_BONUS_DRAW_DESIGNS:
        draw_system_type = _canonical_big_game_bonus_draw_system(row)
    if draw_system_type in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        draw_system_type = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
    return REGISTRY[draw_system_type].target_scope


def modeled_by_engine(row: Mapping[str, object], draw_system_type: str | None = None, algorithm_status: str | None = None) -> bool:
    draw_system_type = draw_system_type or classify_draw_system_type(row)
    if draw_system_type in LEGACY_BONUS_DRAW_DESIGNS:
        draw_system_type = _canonical_big_game_bonus_draw_system(row)
    if draw_system_type in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        draw_system_type = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
    algorithm_status = algorithm_status or resolve_algorithm_status(row, draw_system_type)
    if algorithm_status not in {
        ALGORITHM_STATUS_MODELED_ALLOCATION,
        ALGORITHM_STATUS_MODELED_AVAILABILITY,
        ALGORITHM_STATUS_MODELED_BONUS,
        ALGORITHM_STATUS_MODELED_PREFERENCE,
        ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
        ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW,
    }:
        return False
    source_dataset = _clean_lower(row.get("source_dataset"))
    return source_dataset == "predictive"


def classification_reason(row: Mapping[str, object], draw_system_type: str | None = None, algorithm_status: str | None = None) -> str:
    draw_system_type = draw_system_type or classify_draw_system_type(row)
    if draw_system_type in {"YOUTH_DRAW_ONLY_ELK", "YOUTH_RANDOM_ELK_GENERAL_BULL"}:
        draw_system_type = YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE
    algorithm_status = algorithm_status or resolve_algorithm_status(row, draw_system_type)
    if draw_system_type == BEAR_DRAW_SYSTEM_TYPE and algorithm_status != ALGORITHM_STATUS_MODELED_BONUS:
        subtype = classify_bear_subtype(row)
        if algorithm_status == ALGORITHM_STATUS_MODELED_AVAILABILITY:
            if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
                return "Bear harvest-objective rows are surfaced as availability/rule-status, not draw odds."
            if subtype == UNLIMITED_PURSUIT_PERMIT:
                return "Bear pursuit rows are surfaced as unlimited-availability rows, not draw odds."
        if subtype == HARVEST_OBJECTIVE_AVAILABILITY:
            return "Bear harvest-objective rows stay in scope but do not receive predictive draw odds."
        if subtype == REMAINING_PERMIT_AVAILABILITY:
            return "Bear remaining or availability-only rows do not receive predictive draw odds."
        if subtype == UNLIMITED_PURSUIT_PERMIT:
            return "Unlimited bear pursuit rows are availability rows and do not receive predictive draw odds."
        if subtype == CONSERVATION_OR_NON_PUBLIC:
            return "Non-public or otherwise excluded bear rows do not receive predictive draw odds."
        if subtype == STATEWIDE_BEAR_PERMIT:
            return "The statewide sportsman bear permit stays separate and only receives draw odds if usable public draw history is proven."
        if subtype == UNKNOWN_BEAR_SUBTYPE:
            return "Bear remains in scope, but the subtype is ambiguous and stays pending until public draw support is proven."
    if draw_system_type == SPORTSMAN_DRAW_SYSTEM_TYPE and algorithm_status != ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW:
        return "Sportsman permits are tracked separately and stay pending until a usable official sportsman odds source exists."
    if draw_system_type == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE:
        return "Youth general deer reserve rows stay separate from the adult general-season deer model and remain pending until the active-year youth pool is source-proven."
    if draw_system_type == YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE:
        return "Youth antlerless/doe reserve rows stay separate from adult antlerless/doe preference models until youth reserve mechanics are source-proven."
    if draw_system_type == YOUTH_GENERAL_ANY_BULL_ELK_DRAW_SYSTEM_TYPE:
        if algorithm_status == ALGORITHM_STATUS_MODELED_RANDOM_ONLY:
            return "Youth general any-bull elk uses the dedicated EB1007 youth set-aside random-only lane."
        return "Youth general any-bull elk stays in scope, but remains pending when usable quota and applicant history are not both available."
    if draw_system_type == YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE:
        return "Youth OTC or availability rows are purchase/availability rows, not predictive draw-odds rows."
    if draw_system_type == YOUTH_TURKEY_DRAW_SYSTEM_TYPE:
        if algorithm_status == ALGORITHM_STATUS_MODELED_BONUS:
            return "Modeled by engine.utah_draw_predictive.turkey."
        return "Youth limited-entry turkey is source-classified separately; raw source rows wait for the 15 percent set-aside materializer before receiving probabilities."
    spec = REGISTRY[draw_system_type]
    if modeled_by_engine(row, draw_system_type, algorithm_status):
        return f"Modeled by {spec.module_name}."
    return spec.reason


def classify_runtime_row(row: Mapping[str, object]) -> dict[str, object]:
    draw_system_type = classify_draw_system_type(row)
    algorithm_status = resolve_algorithm_status(row, draw_system_type)
    target_scope = target_scope_label(row, draw_system_type)
    is_modeled = modeled_by_engine(row, draw_system_type, algorithm_status)
    reason = classification_reason(row, draw_system_type, algorithm_status)
    contract_flags = draw_design_contract_flags(row)
    return {
        "draw_system_type": draw_system_type,
        "algorithm_status": algorithm_status,
        "target_scope": target_scope,
        "modeled_by_engine": is_modeled,
        "reason": reason,
        "draw_design_contract_flags": "|".join(contract_flags),
    }


def sanitize_modeled_probability_fields(row: dict[str, object]) -> dict[str, object]:
    classification = classify_runtime_row(row)
    row.update(classification)
    if classification["algorithm_status"] == ALGORITHM_STATUS_MODELED_AVAILABILITY:
        for key in (
            "p_draw",
            "p_draw_pct",
            "p_prior_year_baseline",
            "p_quota_adjusted",
            "p_rollover_adjusted",
            "p_harvest_adjusted",
            "p_preference_draw",
            "p_bonus_pool",
            "p_random_pool",
            "p_bonus_pool_pct",
            "p_random_pool_pct",
            "p_sportsman_draw",
        ):
            row[key] = ""
    if classification["algorithm_status"] in {
        ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
        ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET,
        ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW,
        ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW,
    }:
        for key in (
            "p_draw",
            "p_draw_pct",
            "p_prior_year_baseline",
            "p_quota_adjusted",
            "p_rollover_adjusted",
            "p_harvest_adjusted",
            "p_preference_draw",
            "p_bonus_pool",
            "p_random_pool",
            "p_bonus_pool_pct",
            "p_random_pool_pct",
            "p_sportsman_draw",
        ):
            row[key] = ""
        existing_outlook = _clean(row.get("draw_outlook"))
        if classification["algorithm_status"] == ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET:
            row["draw_outlook"] = existing_outlook or "OUT OF SCOPE"
        elif classification["algorithm_status"] == ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW:
            row["draw_outlook"] = existing_outlook or "REFERENCE LICENSE-BASED; NO DRAW"
        else:
            row["draw_outlook"] = existing_outlook or ("MODEL PENDING" if classification["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING else "NOT MODELED")
    return row


def _coverage_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for source_dataset, path in (("observed_runtime", OBSERVED_RUNTIME_PATH), ("predictive", PREDICTIVE_PATH)):
        for raw in _read_csv(path):
            row = dict(raw)
            row["source_dataset"] = source_dataset
            classification = classify_runtime_row(row)
            sanitized = sanitize_modeled_probability_fields(row)
            rows.append(
                {
                    "hunt_code": _clean(raw.get("hunt_code")).upper(),
                    "hunt_name": _clean(raw.get("hunt_name")),
                    "species": _clean(raw.get("species")),
                    "hunt_type": _clean(raw.get("hunt_type")),
                    "residency": _clean(raw.get("residency")),
                    "year": _clean(raw.get("year")),
                    "draw_system_type": classification["draw_system_type"],
                    "draw_design": _clean(raw.get("draw_design")),
                    "draw_design_contract_flags": classification["draw_design_contract_flags"],
                    "algorithm_status": classification["algorithm_status"],
                    "target_scope": classification["target_scope"],
                    "modeled_by_engine": "True" if classification["modeled_by_engine"] else "False",
                    "reason": classification["reason"],
                    "source_file": _clean(raw.get("source_file")),
                    "source_years_used": _clean(raw.get("source_years_used")),
                    "source_dataset": source_dataset,
                    "draw_pool": _clean(raw.get("draw_pool")),
                    "hunt_class": _clean(raw.get("hunt_class")),
                    "sex_type": _clean(raw.get("sex_type")),
                    "weapon": _clean(raw.get("weapon")),
                    "bear_draw_subtype": _clean(raw.get("bear_draw_subtype")) or classify_bear_subtype(raw),
                    "p_draw": _clean(sanitized.get("p_draw")),
                    "p_draw_pct": _clean(sanitized.get("p_draw_pct")),
                    "p_bonus_pool": _clean(sanitized.get("p_bonus_pool")),
                    "p_random_pool": _clean(sanitized.get("p_random_pool")),
                    "p_availability": _clean(sanitized.get("p_availability")),
                    "availability_pct": _clean(sanitized.get("availability_pct")),
                    "availability_status": _clean(sanitized.get("availability_status")),
                    "availability_reason": _clean(sanitized.get("availability_reason")),
                    "permit_availability_type": _clean(sanitized.get("permit_availability_type")),
                    "probability_model": _clean(sanitized.get("probability_model")),
                    "reason_codes": _clean(sanitized.get("reason_codes")),
                    "rule_status": _clean(sanitized.get("rule_status")),
                    "harvest_objective_status": _clean(sanitized.get("harvest_objective_status")),
                    "data_quality_flags": _clean(sanitized.get("data_quality_flags")),
                    "unit_name": _clean(sanitized.get("unit_name")),
                    "unit_status": _clean(sanitized.get("unit_status")),
                    "draw_outlook": _clean(sanitized.get("draw_outlook")),
                }
            )
    return rows


def _distinct_count(rows: list[dict[str, object]], predicate, field: str = "hunt_code") -> int:
    return len({str(row.get(field, "")).strip().upper() for row in rows if predicate(row) and str(row.get(field, "")).strip()})


def _counter(rows: list[dict[str, object]], field: str, predicate=lambda row: True) -> dict[str, int]:
    counts = Counter()
    for row in rows:
        if not predicate(row):
            continue
        key = _clean(row.get(field)) or "(blank)"
        counts[key] += 1
    return dict(sorted(counts.items()))


def _duplicate_count(rows: list[dict[str, object]], fields: list[str]) -> int:
    keys = [tuple(_clean(row.get(field)) for field in fields) for row in rows]
    return len(keys) - len(set(keys))


def _family_history_semantics(
    observed_rows: list[dict[str, object]],
    predictive_rows: list[dict[str, object]],
    draw_system_type: str,
) -> dict[str, object]:
    predictive_family_rows = [row for row in predictive_rows if row["draw_system_type"] == draw_system_type]
    observed_family_rows = [row for row in observed_rows if row["draw_system_type"] == draw_system_type]
    predictive_hunt_codes = {
        str(row.get("hunt_code", "")).strip().upper()
        for row in predictive_family_rows
        if str(row.get("hunt_code", "")).strip()
    }
    observed_hunt_codes = {
        str(row.get("hunt_code", "")).strip().upper()
        for row in observed_family_rows
        if str(row.get("hunt_code", "")).strip()
    }
    modeled_predictive_rows = [
        row for row in predictive_family_rows if str(row.get("modeled_by_engine")) == "True"
    ]
    modeled_predictive_hunt_codes = {
        str(row.get("hunt_code", "")).strip().upper()
        for row in modeled_predictive_rows
        if str(row.get("hunt_code", "")).strip()
    }
    unmodeled_history_codes = sorted(observed_hunt_codes - modeled_predictive_hunt_codes)
    return {
        "engine_family_modeled": REGISTRY[draw_system_type].algorithm_status == ALGORITHM_STATUS_MODELED_BONUS,
        "active_predictive_coverage_complete": (
            len(predictive_hunt_codes) == len(modeled_predictive_hunt_codes)
            and len(predictive_family_rows) > 0
        ),
        "all_seen_history_codes_modeled": (
            len(observed_hunt_codes) == len(observed_hunt_codes & modeled_predictive_hunt_codes)
            and len(observed_hunt_codes) > 0
        ),
        "unmodeled_seen_hunt_code_count": len(unmodeled_history_codes),
        "unmodeled_seen_hunt_codes_sample": unmodeled_history_codes[:10],
        "active_predictive_row_count": len(predictive_family_rows),
        "active_predictive_hunt_code_count": len(predictive_hunt_codes),
        "observed_history_row_count": len(observed_family_rows),
        "observed_history_hunt_code_count": len(observed_hunt_codes),
    }


def build_draw_system_coverage_report(
    output_dir: Path,
    forecast_year: int = 2026,
    history_years: list[int] | None = None,
) -> dict[str, Path]:
    history_years = history_years or [2021, 2022, 2023, 2024, 2025]
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = _coverage_rows()
    observed_rows = [row for row in rows if row["source_dataset"] == "observed_runtime"]
    predictive_rows = [row for row in rows if row["source_dataset"] == "predictive"]

    detail_csv = output_dir / "draw_system_coverage_report.csv"
    _write_csv(
        detail_csv,
        rows,
        [
            "hunt_code",
            "hunt_name",
            "species",
            "hunt_type",
            "residency",
            "year",
            "draw_system_type",
            "draw_design",
            "draw_design_contract_flags",
            "algorithm_status",
            "target_scope",
            "modeled_by_engine",
            "reason",
            "source_file",
            "source_years_used",
            "source_dataset",
            "draw_pool",
            "hunt_class",
            "sex_type",
            "weapon",
            "bear_draw_subtype",
            "p_draw",
            "p_draw_pct",
            "p_bonus_pool",
            "p_random_pool",
            "p_availability",
            "availability_pct",
            "availability_status",
            "availability_reason",
            "permit_availability_type",
            "probability_model",
            "reason_codes",
            "rule_status",
            "harvest_objective_status",
            "data_quality_flags",
            "unit_name",
            "unit_status",
            "draw_outlook",
        ],
    )

    target_predicate = lambda row: row["target_scope"] == TARGET_SCOPE_TARGET
    modeled_predicate = lambda row: target_predicate(row) and str(row["modeled_by_engine"]) == "True"
    unmodeled_predicate = lambda row: target_predicate(row) and str(row["modeled_by_engine"]) != "True"
    out_of_scope_predicate = lambda row: row["algorithm_status"] == ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET
    unknown_target_predicate = lambda row: row["algorithm_status"] == ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW

    counts_by_draw_system_type = _counter(rows, "draw_system_type")
    counts_by_draw_system_type_hunt_codes = {
        draw_system_type: _distinct_count(rows, lambda row, dst=draw_system_type: row["draw_system_type"] == dst)
        for draw_system_type in DRAW_SYSTEM_ORDER
    }
    counts_by_draw_system_type_by_source_dataset = {
        source_dataset: {
            draw_system_type: _counter(dataset_rows, "draw_system_type").get(draw_system_type, 0)
            for draw_system_type in DRAW_SYSTEM_ORDER
        }
        for source_dataset, dataset_rows in {
            "observed_history": observed_rows,
            "active_predictive": predictive_rows,
        }.items()
    }
    counts_by_algorithm_status_by_source_dataset = {
        source_dataset: _counter(dataset_rows, "algorithm_status")
        for source_dataset, dataset_rows in {
            "observed_history": observed_rows,
            "active_predictive": predictive_rows,
        }.items()
    }

    summary_rows = []
    for draw_system_type in DRAW_SYSTEM_ORDER:
        algorithm_status = REGISTRY[draw_system_type].algorithm_status
        modeled_engine_rows = sum(
            1 for row in rows if row["draw_system_type"] == draw_system_type and str(row["modeled_by_engine"]) == "True"
        )
        summary_rows.append(
            {
                "draw_system_type": draw_system_type,
                "row_count": counts_by_draw_system_type.get(draw_system_type, 0),
                "hunt_code_count": counts_by_draw_system_type_hunt_codes.get(draw_system_type, 0),
                "active_predictive_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == draw_system_type),
                "observed_history_row_count": sum(1 for row in observed_rows if row["draw_system_type"] == draw_system_type),
                "algorithm_status": algorithm_status,
            }
        )

    oil_family = _family_history_semantics(observed_rows, predictive_rows, "BONUS_OIL_BIG_GAME")
    le_family = _family_history_semantics(observed_rows, predictive_rows, "BONUS_LE_BIG_GAME")
    ple_family = _family_history_semantics(observed_rows, predictive_rows, "BONUS_PLE_BIG_GAME")

    bear_modeled_rows = sum(1 for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True")
    bear_modeled_bonus_rows = sum(1 for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_MODELED_BONUS)
    bear_modeled_availability_rows = sum(1 for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_MODELED_AVAILABILITY)
    bear_pending_rows = sum(1 for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING)
    bear_excluded_rows = sum(1 for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW)
    bear_rows = [row for row in rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE]
    predictive_bear_rows = [row for row in predictive_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE]

    answers = {
        "is_general_season_buck_deer_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_GENERAL_SEASON_BUCK_DEER" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_dedicated_hunter_deer_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_DEDICATED_HUNTER_DEER" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_antlerless_deer_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_ANTLERLESS_DEER" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_antlerless_elk_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_ANTLERLESS_ELK" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_doe_pronghorn_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_DOE_PRONGHORN" and str(row["modeled_by_engine"]) == "True") > 0,
        "private_lands_only_antlerless_elk_in_scope": True,
        "private_lands_only_antlerless_elk_modeled_allocation": _distinct_count(rows, lambda row: row["draw_system_type"] == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True") > 0,
        "are_antlerless_moose_and_ewe_sheep_modeled_under_bonus_rules": (
            _distinct_count(rows, lambda row: row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE" and str(row["modeled_by_engine"]) == "True") > 0
            and _distinct_count(rows, lambda row: row["draw_system_type"] == "BONUS_EWE_BIGHORN" and str(row["modeled_by_engine"]) == "True") > 0
        ),
        "oil_big_game_engine_family_modeled": oil_family["engine_family_modeled"],
        "le_big_game_engine_family_modeled": le_family["engine_family_modeled"],
        "ple_big_game_engine_family_modeled": ple_family["engine_family_modeled"],
        "oil_big_game_active_predictive_coverage_complete": oil_family["active_predictive_coverage_complete"],
        "le_big_game_active_predictive_coverage_complete": le_family["active_predictive_coverage_complete"],
        "ple_big_game_active_predictive_coverage_complete": ple_family["active_predictive_coverage_complete"],
        "oil_big_game_all_seen_history_codes_modeled": oil_family["all_seen_history_codes_modeled"],
        "le_big_game_all_seen_history_codes_modeled": le_family["all_seen_history_codes_modeled"],
        "ple_big_game_all_seen_history_codes_modeled": ple_family["all_seen_history_codes_modeled"],
        "oil_big_game_unmodeled_seen_hunt_code_count": oil_family["unmodeled_seen_hunt_code_count"],
        "le_big_game_unmodeled_seen_hunt_code_count": le_family["unmodeled_seen_hunt_code_count"],
        "ple_big_game_unmodeled_seen_hunt_code_count": ple_family["unmodeled_seen_hunt_code_count"],
        "is_turkey_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True") > 0,
        "is_bear_modeled": bear_modeled_rows > 0,
        "sportsman_in_scope": True,
        "is_sportsman_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == SPORTSMAN_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True") > 0,
        "is_mountain_lion_cougar_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == MOUNTAIN_LION_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True") > 0,
        "is_cwmu_public_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "BONUS_CWMU_BIG_GAME" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_antlerless_moose_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE" and str(row["modeled_by_engine"]) == "True") > 0,
        "is_ewe_bighorn_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "BONUS_EWE_BIGHORN" and str(row["modeled_by_engine"]) == "True") > 0,
        "youth_general_deer_reserve_in_scope": True,
        "youth_antlerless_or_doe_reserve_in_scope": True,
        "youth_draw_only_elk_in_scope": True,
        "youth_otc_or_availability_in_scope": True,
        "youth_general_deer_in_scope": True,
        "youth_general_any_bull_elk_in_scope": True,
    }

    cwmu_private_excluded_rows = [
        row for row in rows
        if row["draw_system_type"] == "LANDOWNER_BIG_GAME" and "cwmu" in _joined_text(row)
    ]
    phase6_summary = {
        "cwmu_public_modeled_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_CWMU_BIG_GAME" and str(row["modeled_by_engine"]) == "True"),
        "cwmu_public_pending_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_CWMU_BIG_GAME" and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "cwmu_private_excluded_row_count": len(cwmu_private_excluded_rows),
        "antlerless_moose_modeled_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE" and str(row["modeled_by_engine"]) == "True"),
        "antlerless_moose_pending_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_ANTLERLESS_MOOSE" and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "ewe_bighorn_modeled_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_EWE_BIGHORN" and str(row["modeled_by_engine"]) == "True"),
        "ewe_bighorn_pending_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "BONUS_EWE_BIGHORN" and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "turkey_still_pending": "BONUS_TURKEY" in {row["draw_system_type"] for row in predictive_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING},
        "bear_still_pending": bear_pending_rows > 0,
        "mountain_lion_cougar_in_scope": REGISTRY["COUGAR_LICENSE_BASED"].target_scope == TARGET_SCOPE_TARGET,
        "mountain_lion_cougar_modeled": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status in {
            ALGORITHM_STATUS_MODELED_ALLOCATION,
            ALGORITHM_STATUS_MODELED_AVAILABILITY,
            ALGORITHM_STATUS_MODELED_BONUS,
            ALGORITHM_STATUS_MODELED_PREFERENCE,
            ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
        },
        "mountain_lion_cougar_still_pending": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "mountain_lion_cougar_active_predictive_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED"),
        "mountain_lion_cougar_active_predictive_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == "COUGAR_LICENSE_BASED"),
        "mountain_lion_cougar_modeled_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED" and str(row["modeled_by_engine"]) == "True"),
        "mountain_lion_cougar_pending_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED" and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "mountain_lion_cougar_strategy_status": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status,
        "private_lands_only_antlerless_elk_allocation_pending": REGISTRY["PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    }
    turkey_rows = [row for row in rows if "turkey" in _joined_text(row)]
    predictive_turkey_rows = [row for row in predictive_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE]
    observed_turkey_rows = [row for row in observed_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE]
    turkey_summary = {
        "turkey_rows_seen_total": len(turkey_rows),
        "turkey_rows_seen_active_predictive": len(predictive_turkey_rows),
        "turkey_rows_seen_observed_history": len(observed_turkey_rows),
        "turkey_forecast_eligible_rows_active_predictive": sum(1 for row in predictive_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE),
        "turkey_modeled_bonus_rows_active_predictive": sum(1 for row in predictive_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and str(row["modeled_by_engine"]) == "True"),
        "turkey_in_scope_model_pending_rows_active_predictive": sum(1 for row in predictive_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "turkey_in_scope_model_pending_rows_observed_history": sum(1 for row in observed_rows if row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "turkey_in_scope_model_pending_hunt_codes_active_predictive": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "turkey_in_scope_model_pending_hunt_codes_observed_history": _distinct_count(observed_rows, lambda row: row["draw_system_type"] == TURKEY_DRAW_SYSTEM_TYPE and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "turkey_excluded_not_predictive_draw_rows_active_predictive": sum(1 for row in predictive_turkey_rows if row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW),
        "turkey_excluded_not_predictive_draw_rows_observed_history": sum(1 for row in observed_turkey_rows if row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW),
        "general_season_turkey_excluded": any(is_general_season_turkey_row(row) and row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW for row in turkey_rows),
        "remaining_turkey_excluded_or_availability_pending": any(is_remaining_turkey_row(row) and row["algorithm_status"] in {ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW, ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING} for row in turkey_rows),
        "non_public_turkey_excluded_rows_total": sum(1 for row in turkey_rows if is_nonpublic_turkey_row(row) and row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW),
        "bear_still_pending": bear_pending_rows > 0,
        "mountain_lion_cougar_in_scope": REGISTRY["COUGAR_LICENSE_BASED"].target_scope == TARGET_SCOPE_TARGET,
        "mountain_lion_cougar_modeled": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status in {
            ALGORITHM_STATUS_MODELED_ALLOCATION,
            ALGORITHM_STATUS_MODELED_AVAILABILITY,
            ALGORITHM_STATUS_MODELED_BONUS,
            ALGORITHM_STATUS_MODELED_PREFERENCE,
            ALGORITHM_STATUS_MODELED_RANDOM_ONLY,
        },
        "mountain_lion_cougar_still_pending": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "mountain_lion_cougar_active_predictive_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED"),
        "mountain_lion_cougar_active_predictive_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == "COUGAR_LICENSE_BASED"),
        "mountain_lion_cougar_modeled_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED" and str(row["modeled_by_engine"]) == "True"),
        "mountain_lion_cougar_pending_row_count": sum(1 for row in predictive_rows if row["draw_system_type"] == "COUGAR_LICENSE_BASED" and row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "mountain_lion_cougar_strategy_status": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status,
        "private_lands_only_antlerless_elk_allocation_pending": REGISTRY["PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    }
    bear_summary = {
        "bear_modeled": bear_modeled_rows > 0,
        "bear_still_pending": bear_pending_rows > 0,
        "bear_draw_modeled_bonus_row_count": bear_modeled_bonus_rows,
        "bear_draw_in_scope_model_pending_row_count": bear_pending_rows,
        "bear_draw_excluded_not_predictive_draw_row_count": bear_excluded_rows,
        "bear_draw_modeled_bonus_rows": bear_modeled_bonus_rows,
        "bear_draw_pending_rows": bear_pending_rows,
        "bear_draw_modeled_availability_rows": bear_modeled_availability_rows,
        "bear_draw_active_predictive_row_count": len(predictive_bear_rows),
        "bear_draw_active_predictive_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE),
        "limited_entry_bear_hunt_modeled": any(row["bear_draw_subtype"] == LIMITED_ENTRY_BEAR_HUNT and str(row["modeled_by_engine"]) == "True" for row in predictive_bear_rows),
        "restricted_bear_pursuit_modeled": any(row["bear_draw_subtype"] == RESTRICTED_BEAR_PURSUIT and str(row["modeled_by_engine"]) == "True" for row in predictive_bear_rows),
        "limited_entry_bear_modeled_row_count": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == LIMITED_ENTRY_BEAR_HUNT and str(row["modeled_by_engine"]) == "True"),
        "restricted_pursuit_bear_modeled_row_count": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == RESTRICTED_BEAR_PURSUIT and str(row["modeled_by_engine"]) == "True"),
        "bear_harvest_objective_rows": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == HARVEST_OBJECTIVE_AVAILABILITY),
        "bear_unlimited_pursuit_rows": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == UNLIMITED_PURSUIT_PERMIT),
        "bear_sportsman_rows": sum(1 for row in predictive_rows if row["draw_system_type"] == SPORTSMAN_DRAW_SYSTEM_TYPE and str(row.get("species", "")).strip().lower() == "black bear"),
        "bear_rows_with_p_draw": sum(1 for row in predictive_bear_rows if str(row.get("p_draw", "")).strip()),
        "harvest_objective_bear_excluded_or_availability_pending": any(row["bear_draw_subtype"] == HARVEST_OBJECTIVE_AVAILABILITY for row in bear_rows),
        "harvest_objective_bear_excluded_or_availability_pending_row_count": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == HARVEST_OBJECTIVE_AVAILABILITY),
        "remaining_bear_excluded_or_availability_pending": any(row["bear_draw_subtype"] == REMAINING_PERMIT_AVAILABILITY for row in bear_rows),
        "remaining_bear_excluded_or_availability_pending_row_count": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == REMAINING_PERMIT_AVAILABILITY),
        "non_public_bear_excluded_row_count": sum(1 for row in predictive_bear_rows if row["bear_draw_subtype"] == CONSERVATION_OR_NON_PUBLIC),
        "br1001_classified_as_harvest_objective_availability": any(row.get("hunt_code") == "BR1001" and row["bear_draw_subtype"] == HARVEST_OBJECTIVE_AVAILABILITY for row in predictive_bear_rows),
        "br1001_modeled_as_draw_odds": any(row.get("hunt_code") == "BR1001" and row["algorithm_status"] == ALGORITHM_STATUS_MODELED_BONUS for row in predictive_bear_rows),
        "br1001_p_draw_count": sum(1 for row in predictive_bear_rows if row.get("hunt_code") == "BR1001" and str(row.get("p_draw", "")).strip()),
        "br1007_and_br1018_classified_as_unlimited_pursuit_permit": all(
            any(row.get("hunt_code") == code and row["bear_draw_subtype"] == UNLIMITED_PURSUIT_PERMIT for row in predictive_bear_rows)
            for code in ("BR1007", "BR1018")
        ),
        "br1007_and_br1018_modeled_as_draw_odds": any(row.get("hunt_code") in {"BR1007", "BR1018"} and row["algorithm_status"] == ALGORITHM_STATUS_MODELED_BONUS for row in predictive_bear_rows),
        "conservation_bear_rows_modeled_as_draw_odds": any(row["bear_draw_subtype"] == CONSERVATION_OR_NON_PUBLIC and str(row["modeled_by_engine"]) == "True" for row in predictive_bear_rows),
        "mountain_lion_cougar_still_pending": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "private_lands_only_antlerless_elk_allocation_pending": REGISTRY["PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
        "youth_families_still_pending": True,
    }
    sportsman_rows = [row for row in rows if row["draw_system_type"] == SPORTSMAN_DRAW_SYSTEM_TYPE]
    predictive_sportsman_rows = [row for row in predictive_rows if row["draw_system_type"] == SPORTSMAN_DRAW_SYSTEM_TYPE]
    sportsman_summary = {
        "sportsman_in_scope": True,
        "sportsman_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_sportsman_rows),
        "sportsman_row_count": len(predictive_sportsman_rows),
        "sportsman_pending_row_count": sum(1 for row in predictive_sportsman_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "sportsman_modeled_row_count": sum(1 for row in predictive_sportsman_rows if row["algorithm_status"] == ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW),
        "sportsman_rows_with_p_bonus_pool_non_null": sum(1 for row in predictive_sportsman_rows if str(row.get("p_bonus_pool", "")).strip()),
        "sportsman_rows_with_p_random_pool_non_null": sum(1 for row in predictive_sportsman_rows if str(row.get("p_random_pool", "")).strip()),
        "sportsman_rows_with_p_preference_draw_non_null": sum(1 for row in predictive_sportsman_rows if str(row.get("p_preference_draw", "")).strip()),
        "br1000_classified_as_sportsman_permit": any(row.get("hunt_code") == "BR1000" for row in predictive_sportsman_rows),
        "br1000_modeled_as_sportsman_draw": any(row.get("hunt_code") == "BR1000" and str(row["modeled_by_engine"]) == "True" for row in predictive_sportsman_rows),
        "br1000_p_draw_count": sum(1 for row in predictive_sportsman_rows if row.get("hunt_code") == "BR1000" and str(row.get("p_draw", "")).strip()),
        "db0007_classified_as_sportsman_permit": any(row.get("hunt_code") == "DB0007" for row in predictive_sportsman_rows),
        "rs0001_classified_as_sportsman_permit": any(row.get("hunt_code") == "RS0001" for row in predictive_sportsman_rows),
        "tk0001_classified_as_sportsman_permit": any(row.get("hunt_code") == "TK0001" for row in predictive_sportsman_rows),
        "sportsman_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == SPORTSMAN_DRAW_SYSTEM_TYPE),
    }
    predictive_mountain_lion_rows = [row for row in predictive_rows if row["draw_system_type"] == MOUNTAIN_LION_DRAW_SYSTEM_TYPE]
    predictive_availability_rows = [row for row in predictive_rows if row["algorithm_status"] == ALGORITHM_STATUS_MODELED_AVAILABILITY]
    mountain_lion_availability_rows = [row for row in predictive_availability_rows if row["draw_system_type"] == MOUNTAIN_LION_DRAW_SYSTEM_TYPE]
    bear_availability_rows = [row for row in predictive_availability_rows if row["draw_system_type"] == BEAR_DRAW_SYSTEM_TYPE]
    other_availability_rows = [
        row
        for row in predictive_availability_rows
        if row["draw_system_type"] not in {MOUNTAIN_LION_DRAW_SYSTEM_TYPE, BEAR_DRAW_SYSTEM_TYPE}
    ]
    availability_duplicate_key_count = _duplicate_count(
        predictive_availability_rows,
        ["hunt_code", "residency", "year", "source_dataset"],
    )
    availability_signal_fields = (
        "p_availability",
        "availability_pct",
        "availability_status",
        "permit_availability_type",
        "unit_status",
        "rule_status",
        "harvest_objective_status",
        "reason_codes",
    )
    availability_rows_missing_signal = [
        row
        for row in predictive_availability_rows
        if not any(_clean(row.get(field)) for field in availability_signal_fields)
    ]
    availability_rows_with_draw_fields = [
        row
        for row in predictive_availability_rows
        if any(_clean(row.get(field)) for field in ("p_draw", "p_draw_pct", "p_preference_draw", "p_bonus_pool", "p_random_pool"))
    ]
    availability_rows_with_invalid_range = [
        row
        for row in predictive_availability_rows
        if (
            _clean(row.get("p_availability"))
            and not (0.0 <= float(_clean(row.get("p_availability"))) <= 1.0)
        )
        or (
            _clean(row.get("availability_pct"))
            and not (0.0 <= float(_clean(row.get("availability_pct"))) <= 100.0)
        )
    ]
    availability_rows_requiring_reclassification = availability_rows_missing_signal + availability_rows_with_draw_fields + availability_rows_with_invalid_range
    modeled_availability_summary = {
        "modeled_availability_total_row_count": len(predictive_availability_rows),
        "modeled_availability_hunt_code_count": _distinct_count(
            predictive_rows,
            lambda row: row["algorithm_status"] == ALGORITHM_STATUS_MODELED_AVAILABILITY,
        ),
        "modeled_availability_by_draw_system_type": _counter(
            predictive_availability_rows,
            "draw_system_type",
        ),
        "mountain_lion_cougar_modeled_availability_row_count": len(mountain_lion_availability_rows),
        "bear_modeled_availability_row_count": len(bear_availability_rows),
        "other_modeled_availability_row_count": len(other_availability_rows),
        "modeled_availability_p_draw_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_draw"))),
        "modeled_availability_p_draw_pct_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_draw_pct"))),
        "modeled_availability_p_preference_draw_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_preference_draw"))),
        "modeled_availability_p_bonus_pool_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_bonus_pool"))),
        "modeled_availability_p_random_pool_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_random_pool"))),
        "modeled_availability_p_availability_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("p_availability"))),
        "modeled_availability_availability_pct_non_null_count": sum(1 for row in predictive_availability_rows if _clean(row.get("availability_pct"))),
        "modeled_availability_duplicate_key_count": availability_duplicate_key_count,
        "modeled_availability_rows_requiring_reclassification_count": len({
            (
                _clean(row.get("hunt_code")),
                _clean(row.get("residency")),
                _clean(row.get("year")),
                _clean(row.get("source_dataset")),
            )
            for row in availability_rows_requiring_reclassification
        }),
    }
    modeled_availability_summary["modeled_availability_pass"] = (
        modeled_availability_summary["modeled_availability_p_draw_non_null_count"] == 0
        and modeled_availability_summary["modeled_availability_p_draw_pct_non_null_count"] == 0
        and modeled_availability_summary["modeled_availability_p_preference_draw_non_null_count"] == 0
        and modeled_availability_summary["modeled_availability_p_bonus_pool_non_null_count"] == 0
        and modeled_availability_summary["modeled_availability_p_random_pool_non_null_count"] == 0
        and len(availability_rows_missing_signal) == 0
        and modeled_availability_summary["modeled_availability_duplicate_key_count"] == 0
        and modeled_availability_summary["modeled_availability_rows_requiring_reclassification_count"] == 0
    )
    mountain_lion_summary = {
        "mountain_lion_cougar_in_scope": True,
        "mountain_lion_cougar_modeled_availability": False,
        "mountain_lion_cougar_reference_license_based_no_draw": any(
            row["algorithm_status"] == ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW
            for row in predictive_mountain_lion_rows
        ),
        "mountain_lion_cougar_still_pending_availability": any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_mountain_lion_rows),
        "mountain_lion_cougar_active_predictive_row_count": len(predictive_mountain_lion_rows),
        "mountain_lion_cougar_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == MOUNTAIN_LION_DRAW_SYSTEM_TYPE),
        "mountain_lion_cougar_active_predictive_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == MOUNTAIN_LION_DRAW_SYSTEM_TYPE),
        "mountain_lion_cougar_unit_count": len({str(row.get("unit_name", "")).strip() for row in predictive_mountain_lion_rows if str(row.get("unit_name", "")).strip()}),
        "mountain_lion_cougar_p_draw_non_null_count": sum(1 for row in predictive_mountain_lion_rows if str(row.get("p_draw", "")).strip()),
        "mountain_lion_cougar_p_availability_non_null_count": sum(1 for row in predictive_mountain_lion_rows if str(row.get("p_availability", "")).strip()),
        "mountain_lion_cougar_modeled": False,
        "mountain_lion_cougar_still_pending": any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_mountain_lion_rows),
        "mountain_lion_cougar_strategy_status": ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW,
        "mountain_lion_cougar_modeled_row_count": 0,
        "mountain_lion_cougar_reference_row_count": sum(
            1
            for row in predictive_mountain_lion_rows
            if row["algorithm_status"] == ALGORITHM_STATUS_REFERENCE_LICENSE_BASED_NO_DRAW
        ),
        "mountain_lion_cougar_pending_row_count": sum(1 for row in predictive_mountain_lion_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "mountain_lion_cougar_excluded_row_count": sum(1 for row in predictive_mountain_lion_rows if row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW),
    }
    private_lands_rows = [row for row in rows if row["draw_system_type"] == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE]
    predictive_private_lands_rows = [row for row in predictive_rows if row["draw_system_type"] == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE]
    private_lands_summary = {
        "private_lands_only_antlerless_elk_in_scope": True,
        "private_lands_only_antlerless_elk_modeled_allocation": any(row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION for row in predictive_private_lands_rows),
        # Compatibility aliases retained for the original capped-permit coverage
        # contract.  These describe the same allocation rows; they do not
        # reclassify private-lands permits as draw odds or availability odds.
        "private_lands_only_antlerless_elk_modeled_capped_permits": any(row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION for row in predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_modeled": any(row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION for row in predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_pending": any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_still_pending": any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_row_count": len(predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_active_predictive_row_count": len(predictive_private_lands_rows),
        "private_lands_only_antlerless_elk_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE),
        "private_lands_only_antlerless_elk_active_predictive_hunt_code_count": _distinct_count(predictive_rows, lambda row: row["draw_system_type"] == PRIVATE_LANDS_ANTLERLESS_ELK_DRAW_SYSTEM_TYPE),
        "private_lands_only_antlerless_elk_modeled_allocation_row_count": sum(1 for row in predictive_private_lands_rows if row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION),
        "private_lands_only_antlerless_elk_modeled_capped_permit_row_count": sum(1 for row in predictive_private_lands_rows if row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION),
        "private_lands_only_antlerless_elk_pending_row_count": sum(1 for row in predictive_private_lands_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "private_lands_only_antlerless_elk_excluded_row_count": sum(1 for row in predictive_private_lands_rows if row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW),
        "private_lands_only_antlerless_elk_p_draw_count": sum(1 for row in predictive_private_lands_rows if str(row.get("p_draw", "")).strip()),
        "private_lands_only_antlerless_elk_p_availability_count": sum(1 for row in predictive_private_lands_rows if str(row.get("p_availability", "")).strip()),
        "private_lands_only_antlerless_elk_strategy_status": (
            ALGORITHM_STATUS_MODELED_ALLOCATION
            if any(row["algorithm_status"] == ALGORITHM_STATUS_MODELED_ALLOCATION for row in predictive_private_lands_rows)
            else REGISTRY["PRIVATE_LANDS_ONLY_ANTLERLESS_ELK"].algorithm_status
        ),
        "normal_antlerless_elk_preference_still_modeled": _distinct_count(rows, lambda row: row["draw_system_type"] == "PREFERENCE_ANTLERLESS_ELK" and str(row["modeled_by_engine"]) == "True") > 0,
        "private_lands_only_antlerless_elk_incorrectly_classified_as_preference_antlerless_elk_count": sum(
            1 for row in rows if "private land only" in _joined_text(row) and row["draw_system_type"] == "PREFERENCE_ANTLERLESS_ELK"
        ),
        "mountain_lion_cougar_still_pending": REGISTRY["COUGAR_LICENSE_BASED"].algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING,
    }
    predictive_youth_deer_rows = [row for row in predictive_rows if row["draw_system_type"] == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE]
    predictive_youth_antlerless_or_doe_rows = [row for row in predictive_rows if row["draw_system_type"] == YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE]
    predictive_youth_elk_rows = [row for row in predictive_rows if row["draw_system_type"] == YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE]
    predictive_youth_otc_rows = [row for row in predictive_rows if row["draw_system_type"] == YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE]
    observed_youth_deer_rows = [row for row in observed_rows if row["draw_system_type"] == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE]
    observed_youth_antlerless_or_doe_rows = [row for row in observed_rows if row["draw_system_type"] == YOUTH_ANTLERLESS_OR_DOE_RESERVE_DRAW_SYSTEM_TYPE]
    observed_youth_elk_rows = [row for row in observed_rows if row["draw_system_type"] == YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE]
    observed_youth_otc_rows = [row for row in observed_rows if row["draw_system_type"] == YOUTH_OTC_OR_AVAILABILITY_DRAW_SYSTEM_TYPE]
    youth_summary = {
        "youth_general_deer_reserve_in_scope": True,
        "youth_general_deer_reserve_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_youth_deer_rows),
        "youth_general_deer_reserve_still_pending": (
            any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_youth_deer_rows)
            or len(predictive_youth_deer_rows) == 0
        ),
        "youth_general_deer_reserve_active_predictive_row_count": len(predictive_youth_deer_rows),
        "youth_general_deer_reserve_active_predictive_hunt_code_count": _distinct_count(
            predictive_rows,
            lambda row: row["draw_system_type"] == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
        ),
        "youth_general_deer_reserve_modeled_row_count": sum(1 for row in predictive_youth_deer_rows if str(row["modeled_by_engine"]) == "True"),
        "youth_general_deer_reserve_pending_row_count": sum(1 for row in predictive_youth_deer_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "youth_general_deer_reserve_observed_history_row_count": len(observed_youth_deer_rows),
        "youth_general_deer_in_scope": True,
        "youth_general_deer_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_youth_deer_rows),
        "youth_general_deer_still_pending": (
            any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_youth_deer_rows)
            or len(predictive_youth_deer_rows) == 0
        ),
        "youth_general_deer_active_predictive_row_count": len(predictive_youth_deer_rows),
        "youth_general_deer_active_predictive_hunt_code_count": _distinct_count(
            predictive_rows,
            lambda row: row["draw_system_type"] == YOUTH_GENERAL_DEER_RESERVE_DRAW_SYSTEM_TYPE,
        ),
        "youth_general_deer_modeled_row_count": sum(1 for row in predictive_youth_deer_rows if str(row["modeled_by_engine"]) == "True"),
        "youth_general_deer_pending_row_count": sum(1 for row in predictive_youth_deer_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "youth_general_deer_observed_history_row_count": len(observed_youth_deer_rows),
        "youth_antlerless_or_doe_reserve_in_scope": True,
        "youth_antlerless_or_doe_reserve_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_youth_antlerless_or_doe_rows),
        "youth_antlerless_or_doe_reserve_still_pending": (
            any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_youth_antlerless_or_doe_rows)
            or len(predictive_youth_antlerless_or_doe_rows) == 0
        ),
        "youth_antlerless_or_doe_reserve_active_predictive_row_count": len(predictive_youth_antlerless_or_doe_rows),
        "youth_antlerless_or_doe_reserve_observed_history_row_count": len(observed_youth_antlerless_or_doe_rows),
        "youth_draw_only_elk_in_scope": True,
        "youth_draw_only_elk_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_youth_elk_rows),
        "youth_draw_only_elk_still_pending": (
            any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_youth_elk_rows)
            or len(predictive_youth_elk_rows) == 0
        ),
        "youth_draw_only_elk_active_predictive_row_count": len(predictive_youth_elk_rows),
        "youth_draw_only_elk_active_predictive_hunt_code_count": _distinct_count(
            predictive_rows,
            lambda row: row["draw_system_type"] == YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE,
        ),
        "youth_draw_only_elk_modeled_row_count": sum(1 for row in predictive_youth_elk_rows if str(row["modeled_by_engine"]) == "True"),
        "youth_draw_only_elk_pending_row_count": sum(1 for row in predictive_youth_elk_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "youth_draw_only_elk_observed_history_row_count": len(observed_youth_elk_rows),
        "youth_general_any_bull_elk_in_scope": True,
        "youth_general_any_bull_elk_modeled": any(str(row["modeled_by_engine"]) == "True" for row in predictive_youth_elk_rows),
        "youth_general_any_bull_elk_still_pending": (
            any(row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING for row in predictive_youth_elk_rows)
            or len(predictive_youth_elk_rows) == 0
        ),
        "youth_general_any_bull_elk_active_predictive_row_count": len(predictive_youth_elk_rows),
        "youth_general_any_bull_elk_active_predictive_hunt_code_count": _distinct_count(
            predictive_rows,
            lambda row: row["draw_system_type"] == YOUTH_DRAW_ONLY_ELK_DRAW_SYSTEM_TYPE,
        ),
        "youth_general_any_bull_elk_modeled_row_count": sum(1 for row in predictive_youth_elk_rows if str(row["modeled_by_engine"]) == "True"),
        "youth_general_any_bull_elk_pending_row_count": sum(1 for row in predictive_youth_elk_rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING),
        "youth_general_any_bull_elk_observed_history_row_count": len(observed_youth_elk_rows),
        "youth_otc_or_availability_in_scope": True,
        "youth_otc_or_availability_active_predictive_row_count": len(predictive_youth_otc_rows),
        "youth_otc_or_availability_observed_history_row_count": len(observed_youth_otc_rows),
        "youth_rows_with_p_draw_non_null_count": sum(
            1
            for row in predictive_youth_deer_rows + predictive_youth_antlerless_or_doe_rows + predictive_youth_elk_rows + predictive_youth_otc_rows
            if str(row.get("p_draw", "")).strip()
        ),
        "youth_rows_with_p_bonus_pool_non_null_count": sum(
            1
            for row in predictive_youth_deer_rows + predictive_youth_antlerless_or_doe_rows + predictive_youth_elk_rows + predictive_youth_otc_rows
            if str(row.get("p_bonus_pool", "")).strip()
        ),
        "youth_rows_with_p_random_pool_non_null_count": sum(
            1
            for row in predictive_youth_deer_rows + predictive_youth_antlerless_or_doe_rows + predictive_youth_elk_rows + predictive_youth_otc_rows
            if str(row.get("p_random_pool", "")).strip()
        ),
        "youth_rows_with_p_preference_draw_non_null_count": sum(
            1
            for row in predictive_youth_deer_rows + predictive_youth_antlerless_or_doe_rows + predictive_youth_elk_rows + predictive_youth_otc_rows
            if str(row.get("p_preference_draw", "")).strip()
        ),
    }

    report = {
        "forecast_year": forecast_year,
        "history_years": history_years,
        "total_rows_seen": len(rows),
        "rows_seen_observed_history": len(observed_rows),
        "rows_seen_active_predictive": len(predictive_rows),
        "total_hunt_codes_seen": _distinct_count(rows, lambda row: True),
        "target_scope_rows": sum(1 for row in rows if target_predicate(row)),
        "target_scope_hunt_codes": _distinct_count(rows, target_predicate),
        "out_of_scope_rows": sum(1 for row in rows if out_of_scope_predicate(row)),
        "out_of_scope_hunt_codes": _distinct_count(rows, out_of_scope_predicate),
        "unknown_target_rows": sum(1 for row in rows if unknown_target_predicate(row)),
        "unknown_target_hunt_codes": _distinct_count(rows, unknown_target_predicate),
        "counts_by_draw_system_type": counts_by_draw_system_type,
        "counts_by_draw_system_type_hunt_codes": counts_by_draw_system_type_hunt_codes,
        "counts_by_algorithm_status": _counter(rows, "algorithm_status"),
        "counts_by_draw_system_type_by_source_dataset": counts_by_draw_system_type_by_source_dataset,
        "counts_by_algorithm_status_by_source_dataset": counts_by_algorithm_status_by_source_dataset,
        "counts_by_species": _counter(rows, "species"),
        "counts_by_residency": _counter(rows, "residency"),
        "counts_by_year": _counter(rows, "year"),
        "modeled_target_rows": sum(1 for row in rows if modeled_predicate(row)),
        "unmodeled_target_rows": sum(1 for row in rows if unmodeled_predicate(row)),
        "modeled_target_hunt_codes": _distinct_count(rows, modeled_predicate),
        "unmodeled_target_hunt_codes": _distinct_count(rows, unmodeled_predicate),
        "out_of_scope_non_target_rows": sum(1 for row in rows if out_of_scope_predicate(row)),
        "out_of_scope_non_target_hunt_codes": _distinct_count(rows, out_of_scope_predicate),
        "answers": answers,
        "phase6_bonus_special": phase6_summary,
        "phase7_turkey": turkey_summary,
        "phase8_bear": bear_summary,
        "phase12_bear": bear_summary,
        "phase8_sportsman": sportsman_summary,
        "phase11_sportsman": sportsman_summary,
        "phase9_private_lands_antlerless_elk": private_lands_summary,
        "phase14_private_lands_antlerless_elk": private_lands_summary,
        "phase10_mountain_lion": mountain_lion_summary,
        "phase13_mountain_lion": mountain_lion_summary,
        "phase15_youth": youth_summary,
        "modeled_availability": modeled_availability_summary,
        "family_modeling_semantics": {
            "bonus_oil_big_game": oil_family,
            "bonus_le_big_game": le_family,
            "bonus_ple_big_game": ple_family,
        },
        "currently_production_modeled_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_BONUS],
        "modeled_bonus_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_BONUS],
        "modeled_preference_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_PREFERENCE],
        "modeled_allocation_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_ALLOCATION],
        "modeled_availability_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_AVAILABILITY],
        "modeled_random_only_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_RANDOM_ONLY],
        "modeled_sportsman_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_MODELED_SPORTSMAN_DRAW],
        "in_scope_model_pending_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING],
        "excluded_not_predictive_draw_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW],
        "out_of_scope_non_target_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET],
        "unknown_target_categories": [draw_system_type for draw_system_type, spec in REGISTRY.items() if spec.algorithm_status == ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW],
        "target_categories_only_in_scope_model_pending": sorted(
            {row["draw_system_type"] for row in rows if row["algorithm_status"] == ALGORITHM_STATUS_IN_SCOPE_MODEL_PENDING}
        ),
        "target_categories_excluded_not_predictive_draw": sorted(
            {row["draw_system_type"] for row in rows if row["algorithm_status"] == ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW}
        ),
        "target_categories_unknown_needs_review": sorted(
            {row["draw_system_type"] for row in rows if row["algorithm_status"] == ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW}
        ),
        "summary_by_draw_system_type": summary_rows,
        "source_files": {
            "observed_runtime": _safe_relative(OBSERVED_RUNTIME_PATH),
            "predictive_runtime": _safe_relative(PREDICTIVE_PATH),
            "detail_csv": _safe_relative(detail_csv),
        },
    }
    json_path = output_dir / "draw_system_coverage_report.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"csv": detail_csv, "json": json_path}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(REPO / "processed_data"))
    parser.add_argument("--forecast-year", type=int, default=2026)
    parser.add_argument("--history-years", default="2021,2022,2023,2024,2025")
    args = parser.parse_args()
    history_years = [int(token.strip()) for token in str(args.history_years).split(",") if token.strip()]
    artifacts = build_draw_system_coverage_report(Path(args.output_dir), forecast_year=args.forecast_year, history_years=history_years)
    print(json.dumps({key: str(value) for key, value in artifacts.items()}, indent=2))


if __name__ == "__main__":
    main()
