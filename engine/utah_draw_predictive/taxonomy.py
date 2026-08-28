from __future__ import annotations

from typing import Mapping


DRAW_DESIGN_MODIFIERS = {"MAX_WEIGHTED_SPLIT", "REFERENCE_ONLY"}
PREFERENCE_DRAW_DESIGNS = {
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
    "PREFERENCE_DEDICATED_HUNTER_DEER",
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def canonical_draw_design(value: object) -> str:
    """Return one primary routing design from source labels and modifiers.

    DATABASE rows currently carry some semicolon-delimited design plus overlay
    labels. Routing needs one parent design. Reference/max-weighted labels are
    modifiers; CWMU is retained for bonus big game but preference remains the
    parent design for CWMU antlerless deer, elk, and doe-pronghorn rows.
    """

    raw = clean(value)
    if not raw or ";" not in raw:
        return raw
    tokens = [token.strip() for token in raw.split(";") if token.strip()]
    primary = [token for token in tokens if token not in DRAW_DESIGN_MODIFIERS]
    if not primary:
        return tokens[0] if tokens else ""

    preference = [token for token in primary if token in PREFERENCE_DRAW_DESIGNS]
    if preference:
        return preference[0]
    if "BONUS_CWMU_BIG_GAME" in primary:
        return "BONUS_CWMU_BIG_GAME"
    return primary[0]


def effective_draw_design(row: Mapping[str, object]) -> str:
    """Preferred draw-design label for routing and scoring.

    draw_design is the source-facing authority. draw_system_type remains an
    engine-compatibility alias while the repo transitions. Legacy
    hunt_draw_class/draw_class_type are intentionally ignored here.
    """

    return canonical_draw_design(row.get("draw_design") or row.get("draw_system_type"))


def draw_design_contract_flags(row: Mapping[str, object]) -> list[str]:
    """Non-fatal taxonomy conflicts for audits."""

    flags: list[str] = []
    draw_design = clean(row.get("draw_design"))
    draw_system_type = clean(row.get("draw_system_type"))
    hunt_class = clean(row.get("hunt_class"))
    hunt_draw_class = clean(row.get("hunt_draw_class"))
    if draw_design and draw_system_type and draw_design != draw_system_type:
        flags.append("DRAW_DESIGN_DRAW_SYSTEM_TYPE_MISMATCH")
    if ";" in draw_design or ";" in draw_system_type:
        flags.append("COMPOSITE_DRAW_DESIGN_NORMALIZED_FOR_ROUTING")
    if hunt_draw_class and hunt_class and hunt_draw_class != hunt_class:
        flags.append("HUNT_DRAW_CLASS_HUNT_CLASS_CONFLICT_IGNORED")
    if hunt_draw_class and draw_system_type and hunt_draw_class != draw_system_type:
        flags.append("HUNT_DRAW_CLASS_DRAW_SYSTEM_TYPE_CONFLICT_IGNORED")
    return flags
