"""Explicit exclusions and out-of-scope declarations."""

from __future__ import annotations

import re
from typing import Mapping

from . import (
    ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
    ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET,
    ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW,
    StrategySpec,
    TARGET_SCOPE_OUT_OF_SCOPE,
    TARGET_SCOPE_TARGET,
)


NO_ORIGINAL_DRAW_PROBABILITY = "NO_ORIGINAL_DRAW_PROBABILITY"
CWMU_CONTACT_OPERATOR_REFERENCE_ONLY = "CWMU_CONTACT_OPERATOR_REFERENCE_ONLY"


def is_cwmu_operator_reference(row: Mapping[str, object]) -> bool:
    """Recognize explicit operator inventory, not public hunters' season notes.

    Public CWMU winners also contact operators for dates (DWR /cwmu). Neither
    that note, an operator name, nor a missing quota alone proves no drawing.
    Explicit reference labels outrank stale model flags and numeric overlays.
    """
    fields = (
        "hunt_type", "hunt_class", "draw_design", "draw_system_type", "draw_pool",
        "record_type", "row_type", "source_type", "source_family", "source_file",
        "classification_status", "prediction_status", "reason_codes", "NOTES", "notes",
    )
    values = [str(row.get(field) or "").strip().upper() for field in fields]
    values.extend(str(value or "").strip().upper() for key, value in row.items()
                  if key.startswith("permit_allotment_") and key.endswith("_status"))
    if not any("CWMU" in value for value in values):
        return False
    if any(CWMU_CONTACT_OPERATOR_REFERENCE_ONLY in value or
           NO_ORIGINAL_DRAW_PROBABILITY in value for value in values):
        return True

    def contact_label(value: object) -> bool:
        text = re.sub(r"[^a-z]+", " ", str(value or "").lower()).strip()
        return text in {"contact operator", "contact cwmu operator", "cwmu contact operator",
                        "cwmu operator contact", "cwmu operator reference only"}

    reference_fields = ("hunt_class", "record_type", "row_type", "source_type",
                        "draw_design", "draw_system_type", "classification_status")
    permit_fields = [key for key in row if
                     re.fullmatch(r"(?:permits|quota)_\d{4}_(?:res|nr|total)", key)
                     or re.fullmatch(r"target_permits_(?:res|nr|total)", key)]
    if any(contact_label(row.get(key)) for key in (*reference_fields, *permit_fields)):
        return True
    # A bare season cell may label reference-only inventory, but an actual
    # point-result record with the same season label retains its draw identity.
    reference_record = any(str(row.get(key) or "").strip().upper() == "REFERENCE_ONLY"
                           for key in ("record_type", "row_type", "draw_system_type", "draw_design"))
    return reference_record and any(contact_label(row.get(key)) for key in ("season", "season_dates"))


STRATEGY_SPECS = [
    StrategySpec(
        draw_system_type=NO_ORIGINAL_DRAW_PROBABILITY,
        module_name="engine.utah_draw_predictive.exclusions",
        algorithm_status=ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="CWMU_CONTACT_OPERATOR_REFERENCE_ONLY: operator/contact inventory has no original public draw probability; overlay allotments are not public quota.",
    ),
    StrategySpec(
        draw_system_type="LANDOWNER_BIG_GAME",
        module_name="engine.utah_draw_predictive.exclusions",
        algorithm_status=ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Landowner and other private big-game permit categories are target-scope inventory items but excluded from predictive public draw modeling.",
    ),
    StrategySpec(
        draw_system_type="MITIGATION_OR_DEPREDATION_BIG_GAME",
        module_name="engine.utah_draw_predictive.exclusions",
        algorithm_status=ALGORITHM_STATUS_EXCLUDED_NOT_PREDICTIVE_DRAW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Mitigation and depredation big-game categories are excluded from predictive public draw modeling.",
    ),
    StrategySpec(
        draw_system_type="OUT_OF_SCOPE_NON_TARGET",
        module_name="engine.utah_draw_predictive.exclusions",
        algorithm_status=ALGORITHM_STATUS_OUT_OF_SCOPE_NON_TARGET,
        target_scope=TARGET_SCOPE_OUT_OF_SCOPE,
        reason="This category is outside the approved predictive-engine universe.",
    ),
    StrategySpec(
        draw_system_type="UNKNOWN_TARGET",
        module_name="engine.utah_draw_predictive.exclusions",
        algorithm_status=ALGORITHM_STATUS_UNKNOWN_TARGET_NEEDS_REVIEW,
        target_scope=TARGET_SCOPE_TARGET,
        reason="Target-scope category could not be resolved to a supported draw-system family.",
    ),
]
