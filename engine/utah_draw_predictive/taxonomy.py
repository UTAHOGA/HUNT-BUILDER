from __future__ import annotations

from typing import Mapping


def clean(value: object) -> str:
    return str(value or "").strip()


def effective_draw_design(row: Mapping[str, object]) -> str:
    """Preferred draw-design label for routing and scoring.

    draw_design is the source-facing authority. draw_system_type remains an
    engine-compatibility alias while the repo transitions. Legacy
    hunt_draw_class/draw_class_type are intentionally ignored here.
    """

    return clean(row.get("draw_design") or row.get("draw_system_type"))


def draw_design_contract_flags(row: Mapping[str, object]) -> list[str]:
    """Non-fatal taxonomy conflicts for audits."""

    flags: list[str] = []
    draw_design = clean(row.get("draw_design"))
    draw_system_type = clean(row.get("draw_system_type"))
    hunt_class = clean(row.get("hunt_class"))
    hunt_draw_class = clean(row.get("hunt_draw_class"))
    if draw_design and draw_system_type and draw_design != draw_system_type:
        flags.append("DRAW_DESIGN_DRAW_SYSTEM_TYPE_MISMATCH")
    if hunt_draw_class and hunt_class and hunt_draw_class != hunt_class:
        flags.append("HUNT_DRAW_CLASS_HUNT_CLASS_CONFLICT_IGNORED")
    if hunt_draw_class and draw_system_type and hunt_draw_class != draw_system_type:
        flags.append("HUNT_DRAW_CLASS_DRAW_SYSTEM_TYPE_CONFLICT_IGNORED")
    return flags
