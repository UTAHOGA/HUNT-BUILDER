"""Strict harvest-row identity matching.

Harvest data may enrich a current hunt only when the normalized hunt code and
hunt name/unit identity agree. ``boundary_id`` is deliberately absent from this
module because geography is not source-row identity.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass


_TOKEN_REPLACEMENTS = {
    "alw": "any legal weapon",
    "mtn": "mountain",
    "mtns": "mountains",
    "mt": "mount",
}

_GENERIC_NAME_TOKENS = {
    "antlerless",
    "association",
    "bull",
    "buck",
    "deer",
    "elk",
    "hunt",
    "landowner",
    "limited",
    "entry",
    "male",
    "female",
    "only",
    "permit",
    "premium",
    "unit",
}


def normalize_code(value: object) -> str:
    return str(value or "").strip().upper()


def normalize_text(value: object) -> str:
    text = str(value or "").lower().replace("’", "'")
    text = re.sub(r"(?<=[a-z])'(?=[a-z])", "", text)
    for source, replacement in _TOKEN_REPLACEMENTS.items():
        text = re.sub(rf"\b{re.escape(source)}\b", replacement, text)
    return " ".join(re.findall(r"[a-z0-9]+", text))


def normalize_species(value: object) -> str:
    text = normalize_text(value)
    aliases = {
        "antlerless deer": "deer",
        "mule deer": "deer",
        "antlerless elk": "elk",
        "rocky bighorn": "rocky mountain bighorn sheep",
        "desert bighorn": "desert bighorn sheep",
    }
    return aliases.get(text, text)


def species_family(value: object) -> str:
    """Return the base species while preserving bighorn subspecies identity."""

    species = normalize_species(value)
    if "desert" in species and "bighorn" in species:
        return "desert bighorn sheep"
    if "rocky" in species and "bighorn" in species:
        return "rocky mountain bighorn sheep"
    for token, family in (
        ("bighorn sheep", "bighorn sheep"),
        ("mountain goat", "mountain goat"),
        ("pronghorn", "pronghorn"),
        ("moose", "moose"),
        ("elk", "elk"),
        ("deer", "deer"),
        ("bison", "bison"),
        ("bear", "black bear"),
        ("cougar", "cougar"),
        ("turkey", "turkey"),
    ):
        if token in species:
            return family
    return species


def _meaningful_name_tokens(value: object) -> tuple[str, ...]:
    tokens = []
    for token in normalize_text(value).split():
        if token in _GENERIC_NAME_TOKENS:
            continue
        if len(token) > 4 and token.endswith("s"):
            token = token[:-1]
        tokens.append(token)
    return tuple(tokens)


def _one_edit_or_equal(left: str, right: str) -> bool:
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right)) <= 1
    shorter, longer = (left, right) if len(left) < len(right) else (right, left)
    index = offset = 0
    while index < len(shorter) and offset < len(longer):
        if shorter[index] == longer[offset]:
            index += 1
        elif offset != index:
            return False
        offset += 1
    return True


def hunt_name_compatible(source_name: object, target_name: object) -> bool:
    source = normalize_text(source_name)
    target = normalize_text(target_name)
    if not source or not target:
        return False
    if source == target:
        return True

    source_tokens = _meaningful_name_tokens(source)
    target_tokens = _meaningful_name_tokens(target)
    if not source_tokens or not target_tokens:
        return False
    source_compact = "".join(source_tokens)
    target_compact = "".join(target_tokens)
    if _one_edit_or_equal(source_compact, target_compact):
        return True

    source_set = set(source_tokens)
    target_set = set(target_tokens)
    smaller, larger = (source_set, target_set) if len(source_set) <= len(target_set) else (target_set, source_set)
    if smaller <= larger:
        return True
    fuzzy_matches = sum(
        1
        for source_token in source_set
        if any(_one_edit_or_equal(source_token, target_token) for target_token in target_set)
    )
    overlap = fuzzy_matches / max(len(source_set), len(target_set))
    return overlap >= 0.75


def species_compatible(source_species: object, target_species: object) -> bool:
    source = normalize_species(source_species)
    target = normalize_species(target_species)
    return bool(source and target and source == target)


def harvest_identity_compatible(source: Mapping[str, object], target: Mapping[str, object]) -> bool:
    """Return true only for exact code plus compatible species and name identity."""

    if normalize_code(source.get("hunt_code")) != normalize_code(target.get("hunt_code")):
        return False
    if not species_compatible(source.get("species"), target.get("species")):
        return False
    source_name = source.get("hunt_name") or source.get("unit_name") or source.get("name")
    target_name = target.get("hunt_name") or target.get("unit_name") or target.get("name")
    return hunt_name_compatible(source_name, target_name)


def build_identity_index(rows: Iterable[Mapping[str, object]]) -> dict[str, list[Mapping[str, object]]]:
    index: dict[str, list[Mapping[str, object]]] = defaultdict(list)
    for row in rows:
        code = normalize_code(row.get("hunt_code"))
        if code:
            index[code].append(row)
    return dict(index)


@dataclass(frozen=True)
class IdentityResolution:
    row: Mapping[str, object] | None
    status: str
    candidate_count: int
    compatible_count: int


def resolve_identity_match(
    source: Mapping[str, object],
    target_candidates: Iterable[Mapping[str, object]],
) -> IdentityResolution:
    candidates = [row for row in target_candidates if normalize_code(row.get("hunt_code")) == normalize_code(source.get("hunt_code"))]
    compatible = [row for row in candidates if harvest_identity_compatible(source, row)]
    if not candidates:
        return IdentityResolution(None, "MISSING_HUNT_CODE", 0, 0)
    if not compatible:
        return IdentityResolution(None, "HUNT_CODE_NAME_OR_SPECIES_MISMATCH", len(candidates), 0)

    identities = {
        (
            normalize_species(row.get("species")),
            normalize_text(row.get("hunt_name") or row.get("unit_name") or row.get("name")),
        )
        for row in compatible
    }
    if len(identities) != 1:
        return IdentityResolution(None, "AMBIGUOUS_COMPATIBLE_IDENTITIES", len(candidates), len(compatible))
    return IdentityResolution(compatible[0], "MATCHED_CODE_NAME_SPECIES", len(candidates), len(compatible))
