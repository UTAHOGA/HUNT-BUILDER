"""Permit split logic for Utah bonus-style draws."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class UtahBonusPermitSplit:
    publicPermits: int
    maxPointPermits: int
    randomPermits: int
    randomOnly: bool


def _is_nonresident(residency: object) -> bool:
    return str(residency or "").strip().lower() in {"nonresident", "non-resident", "nr"}


def split_utah_bonus_permits(public_permits_raw: int, residency: object = None) -> UtahBonusPermitSplit:
    """Split a Utah bonus pool into max-point and regular-draw permits.

    Utah rounds an odd permit count toward the max-point pool. The documented
    exception is a one-permit nonresident pool, which is issued after the bonus
    point round. Callers with a residency lane must provide it; an unspecified
    lane follows the ordinary odd-count rule and is not presumed nonresident.
    """

    public_permits = max(0, int(public_permits_raw or 0))
    if public_permits == 0:
        return UtahBonusPermitSplit(public_permits, 0, 0, False)
    if public_permits == 1 and _is_nonresident(residency):
        return UtahBonusPermitSplit(public_permits, 0, 1, True)
    max_point = (public_permits + 1) // 2
    random = public_permits - max_point
    return UtahBonusPermitSplit(public_permits, max_point, random, False)

