"""Rule helpers for the Utah draw engine."""

from __future__ import annotations

from dataclasses import replace
from typing import Iterable, List, Sequence, Tuple

from .models import Application, ApplicationUnit, DrawSystem, Group, Hunt, Quota, UtahRuleConfig, floor_average, normalize_choices


DEFAULT_DRAW_ORDER: Tuple[str, ...] = (
    "limited_entry",
    "once_in_lifetime",
    "general_season",
    "dedicated_hunter",
    "antlerless",
    "youth_general",
    "cmwu",
    "other",
)

def _text(value: object) -> str:
    return str(value or "").strip().lower()


def classify_utah_draw_rule(row: dict[str, object] | Application | Hunt) -> str:
    """Conservative classifier for Utah draw rule system."""
    if isinstance(row, Application):
        combined = f"{_text(row.point_type)} {_text(row.draw_type)} {_text(row.species)}"
    elif isinstance(row, Hunt):
        combined = f"{_text(row.rule_system)} {_text(row.hunt_type)} {_text(row.hunt_code)}"
    else:
        combined = " ".join(
            _text(row.get(key))
            for key in (
                "draw_system",
                "rule_system",
                "point_type",
                "draw_type",
                "hunt_type",
                "hunt_class",
                "hunt_name",
            )
        )

    if any(token in combined for token in ("bonus", "limited entry", "once in a lifetime", "once-in-a-lifetime", "oial", "premium limited")):
        return DrawSystem.BONUS
    if any(token in combined for token in ("preference", "dedicated hunter", "antlerless", "general-season buck deer", "general season buck deer")):
        return DrawSystem.PREFERENCE
    if "harvest objective" in combined:
        return DrawSystem.HARVEST_OBJECTIVE
    if "general" in combined:
        return DrawSystem.GENERAL
    return DrawSystem.UNKNOWN


def calculate_effective_group_points(member_points: Sequence[int]) -> int:
    return floor_average(member_points)


def validate_group_choices(applications: Sequence[Application]) -> bool:
    if not applications:
        return False
    normalized = [tuple(normalize_choices(app.hunt_choices)) for app in applications]
    first = normalized[0]
    return all(choices == first for choices in normalized)


def validate_group_size(group: Group, hunt_type: str, config: UtahRuleConfig) -> bool:
    max_size = config.max_group_size_default
    if hunt_type == "once_in_lifetime":
        max_size = 0 if not config.once_in_lifetime_groups_allowed else config.max_group_size_default
    elif hunt_type == "limited_entry":
        max_size = config.max_group_size_limited_entry
    elif hunt_type == "general_season":
        max_size = config.max_group_size_general_deer
    elif hunt_type == "youth_general":
        max_size = config.max_group_size_youth_general_deer
    elif hunt_type == "antlerless":
        max_size = config.max_group_size_antlerless_deer_elk_doe_pronghorn
    return group.group_size <= max_size


def validate_youth_group(group: Group, applications: Sequence[Application]) -> bool:
    if not group.youth_only_flag:
        return True
    return all(app.youth_flag for app in applications)


def can_group_fit_quota(group_size: int, remaining_quota: int) -> bool:
    return remaining_quota >= group_size


def _normalized_species(value: object) -> str:
    text = _text(value).replace("-", " ")
    if "pronghorn" in text:
        return "pronghorn"
    if "deer" in text:
        return "deer"
    if "elk" in text:
        return "elk"
    return text


def derive_quota(quota: Quota, hunt: Hunt, config: UtahRuleConfig) -> Quota:
    total = max(int(quota.total_public_permits), 0)
    reserved = quota.reserved_quota
    random_quota = quota.random_quota
    preference_quota = quota.preference_quota
    youth_reserved = quota.youth_reserved_quota
    species = _normalized_species(hunt.species)

    if hunt.rule_system == DrawSystem.BONUS:
        if reserved is None:
            reserved = int(total * config.bonus_reserved_fraction)
        if random_quota is None:
            random_quota = max(total - reserved, 0)
    elif hunt.rule_system == DrawSystem.PREFERENCE:
        if preference_quota is None:
            preference_quota = total

    if youth_reserved is None and hunt.hunt_type == "general_season" and species == "deer":
        youth_reserved = int(total * config.general_deer_youth_reserved_fraction)

    if youth_reserved is None and hunt.hunt_type == "antlerless" and species in {"deer", "elk", "pronghorn"}:
        youth_reserved = int(total * config.antlerless_youth_reserved_fraction)

    return replace(
        quota,
        reserved_quota=reserved,
        random_quota=random_quota,
        preference_quota=preference_quota,
        youth_reserved_quota=youth_reserved,
    )


def get_draw_order(hunt_type: str) -> Tuple[str, ...]:
    if hunt_type == "limited_entry":
        return ("limited_entry", "once_in_lifetime", "general_season", "youth_general")
    if hunt_type == "general_season":
        return ("youth_general", "general_season")
    if hunt_type == "antlerless":
        return ("antlerless", "youth_general")
    return DEFAULT_DRAW_ORDER


def build_application_unit(
    application: Application,
    group: Group | None,
    reason_codes: Iterable[str] | None = None,
) -> ApplicationUnit:
    reason_codes = tuple(reason_codes or ())
    group_size = group.group_size if group else 1
    effective_points = group.effective_points if group else application.points_before_draw
    ticket_count = 1 + max(effective_points, 0) if application.point_type == DrawSystem.BONUS else 1
    return ApplicationUnit(
        application_unit_id=application.application_id if not group else group.group_id,
        member_application_ids=(application.application_id,),
        member_customer_ids_hashed=(application.hashed_customer_id,),
        group_id=group.group_id if group else None,
        group_size=group_size,
        residency=application.residency,
        species=application.species,
        hunt_choices=tuple(normalize_choices(application.hunt_choices)),
        effective_points=effective_points,
        point_type=application.point_type,
        youth_only_flag=application.youth_flag if not group else group.youth_only_flag,
        valid_flag=application.valid_flag,
        eligible_flag=application.eligible_flag,
        random_ticket_count=ticket_count,
        reason_codes=reason_codes,
    )

