#!/usr/bin/env python3
"""Standardize draw-odds PDF filenames across year folders.

This script focuses on the legacy/raw draw-odds PDFs under:

    pipeline/RAW/hunt_unit_database/<YEAR>/pdf/draw_odds/

It does two things:

1. Builds an inventory report with file counts and a species / sex / hunt-type
   breakdown inferred from the filename text.
2. Optionally renames PDFs in place to the canonical pattern:

       <YEAR>_PERMITS=<YEAR+1>_MODEL__NORMALIZED_TITLE.pdf

The script is conservative:

- It never renames non-PDF files.
- It recurses through source subfolders such as CWMU and Parent Files.
- It never overwrites an existing target file.
- It keeps the source title words and normalizes separators to underscores.
- It reports collisions and year mismatches instead of guessing around them.
- It treats official preference-point draw-result PDFs as draw-hunt sources.
  "Preference point" is not a reference-only classifier by itself.
- Cougar is treated as a draw-result family through permit year 2023 and as
  license/status source context after 2023 unless the source title explicitly
  says draw results.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
PIPELINE_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
AUDIT_ROOT = REPO / "audits"

CANONICAL_PREFIX_RE = re.compile(r"^(?P<year>\d{4})_PERMITS=(?P<model>\d{4})_MODEL__")
LEGACY_YEAR_PREFIX_RE = re.compile(r"^(?P<year>\d{4}|\d{2})(?:=|\s+|_+|-+)?(?P<model>\d{4})?(?:=|\s+|_+|-+)?")

KNOWN_SPECIES = [
    ("BLACK_BEAR", "BEAR"),
    ("BEAR", "BEAR"),
    ("COUGAR", "COUGAR"),
    ("DEER", "DEER"),
    ("ELK", "ELK"),
    ("MOOSE", "MOOSE"),
    ("PRONGHORN", "PRONGHORN"),
    ("BISON", "BISON"),
    ("ROCKY_MTN_SHEEP", "SHEEP"),
    ("ROCKY_MOUNTAIN_SHEEP", "SHEEP"),
    ("DESERT_BIGHORN_SHEEP", "SHEEP"),
    ("ROCKY_MTN_BIGHORN_SHEEP", "SHEEP"),
    ("ROCKY_MOUNTAIN_BIGHORN_SHEEP", "SHEEP"),
    ("MTN_GOAT", "GOAT"),
    ("MOUNTAIN_GOAT", "GOAT"),
    ("TURKEY", "TURKEY"),
]

KNOWN_SEX = [
    ("ANTLERLESS", "ANTLERLESS"),
    ("ANY_BULL", "BULL"),
    ("BULL", "BULL"),
    ("BUCK", "BUCK"),
    ("DOE", "DOE"),
    ("EWE", "EWE"),
    ("BEAR", "EITHER_SEX"),
    ("BEARDRAW", "EITHER_SEX"),
]

KNOWN_HUNT_TYPE = [
    ("SPORTSMAN", "SPORTSMAN"),
    ("DEDICATED_HUNTER", "DEDICATED_HUNTER"),
    ("D_H", "DEDICATED_HUNTER"),
    ("GENERAL", "GENERAL_SEASON"),
    ("G_S", "GENERAL_SEASON"),
    ("LIMITED_ENTRY", "LIMITED_ENTRY"),
    ("L_E", "LIMITED_ENTRY"),
    ("O_I_L", "O_I_L"),
    ("OIL", "O_I_L"),
    ("YOUTH", "YOUTH"),
    ("BONUS", "BONUS"),
    ("PREFERENCE", "PREFERENCE"),
    ("POINT", "POINTS"),
    ("QUOTA", "PERMIT_QUOTA"),
    ("ODDS", "ODDS"),
    ("RESULTS", "DRAW_RESULTS"),
    ("DRAW", "DRAW_RESULTS"),
    ("COMBINED", "COMBINED"),
    ("PURSUIT", "PURSUIT"),
]

CANONICAL_TITLE_OVERRIDES = {
    # 2017 / legacy pipeline names that should land on the same canonical
    # naming shape as the already-correct 2023-style folder.
    "ANTLERLESS_DEER": "ANTLERLESS_DEER_DRAW_RESULTS",
    "ANTLERLESS_ELK": "ANTLERLESS_ELK_DRAW_RESULTS",
    "ANTLERLESS_MOOSE": "ANTLERLESS_MOOSE_DRAW_RESULTS",
    "ANTLERLESS_PRONGHORN": "ANTLERLESS_PRONGHORN_DRAW_RESULTS",
    "COUGAR_BONUS_POINT_DRAW": "COUGAR_DRAW_RESULTS",
    "DEDICATED_HUNTER_DEER": "D.H._DEER_DRAW_RESULTS",
    "GENERAL_DEER": "G.S._BUCK_DEER_DRAW_RESULTS",
    "GENERAL_DEER_LIFETIME_PERMIT_HOLDER": "LIFETIME_G.S._DEER_DRAW_RESULTS",
    "GENERAL_DEER_YOUTH": "YOUTH_G.S._DEER_DRAW_RESULTS",
    "LIMITED_ENTRY_BLACK_BEAR": "BEAR_DRAW_RESULTS",
    "LIMITED_ENTRY_BISON": "O.I.L._BISON_DRAW_RESULTS",
    "LIMITED_ENTRY_DEER": "L.E._DEER_DRAW_RESULTS",
    "LIMITED_ENTRY_DESERT_BIGHORN_SHEEP": "O.I.L._DESERT_BIGHORN_SHEEP_DRAW_RESULTS",
    "LIMITED_ENTRY_ELK": "L.E._ELK_DRAW_RESULTS",
    "LIMITED_ENTRY_MOOSE": "O.I.L._BULL_MOOSE_DRAW_RESULTS",
    "LIMITED_ENTRY_MOUNTAIN_GOAT": "O.I.L._MTN_GOAT_DRAW_RESULTS",
    "LIMITED_ENTRY_MTN_GOAT": "O.I.L._MTN_GOAT_DRAW_RESULTS",
    "LIMITED_ENTRY_PRONGHORN": "L.E._PRONGHORN_DRAW_RESULTS",
    "LIMITED_ENTRY_ROCKY_MOUNTAIN_BIGHORN_SHEEP": "O.I.L._ROCKY_MTN_SHEEP_DRAW_RESULTS",
    "LIMITED_ENTRY_ROCKY_MTN_SHEEP": "O.I.L._ROCKY_MTN_SHEEP_DRAW_RESULTS",
    "LIMITED_ENTRY_TURKEY": "TURKEY_DRAW_RESULTS",
    "SPORTSMAN_ODDS": "SPORTSMAN_DRAW_RESULTS",
    "TURKEY_DRAW_RESULTS": "TURKEY_DRAW_RESULTS",
    "YOUTH_ANY_BULL_ELK": "YOUTH_ELK_DRAW_RESULTS",
    "YOUTH_ANTLERLESS_DEER": "YOUTH_ANTLERLESS_DEER_DRAW_RESULTS",
    "YOUTH_ANTLERLESS_ELK": "YOUTH_ANTLERLESS_ELK_DRAW_RESULTS",
    "YOUTH_ANTLERLESS_PRONGHORN": "YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS",
}

TITLE_HINTS = {
    "BEAR_DRAW_RESULTS": ("BEAR", "EITHER_SEX", "LIMITED_ENTRY"),
    "COUGAR_DRAW_RESULTS": ("COUGAR", "EITHER_SEX", "LIMITED_ENTRY"),
    "D.H._DEER_DRAW_RESULTS": ("DEER", "BUCK", "DEDICATED_HUNTER"),
    "G.S._BUCK_DEER_DRAW_RESULTS": ("DEER", "BUCK", "GENERAL_SEASON"),
    "L.E._DEER_DRAW_RESULTS": ("DEER", "BUCK", "LIMITED_ENTRY"),
    "L.E._ELK_DRAW_RESULTS": ("ELK", "BULL", "LIMITED_ENTRY"),
    "L.E._PRONGHORN_DRAW_RESULTS": ("PRONGHORN", "BUCK", "LIMITED_ENTRY"),
    "LIFETIME_G.S._DEER_DRAW_RESULTS": ("DEER", "BUCK", "GENERAL_SEASON"),
    "O.I.L._BISON_DRAW_RESULTS": ("BISON", "EITHER_SEX", "O_I_L"),
    "O.I.L._BULL_MOOSE_DRAW_RESULTS": ("MOOSE", "BULL", "O_I_L"),
    "O.I.L._DESERT_BIGHORN_SHEEP_DRAW_RESULTS": ("SHEEP", "RAM", "O_I_L"),
    "O.I.L._MTN_GOAT_DRAW_RESULTS": ("GOAT", "EITHER_SEX", "O_I_L"),
    "O.I.L._ROCKY_MTN_SHEEP_DRAW_RESULTS": ("SHEEP", "RAM", "O_I_L"),
    "SPORTSMAN_DRAW_RESULTS": ("UNKNOWN", "UNKNOWN", "SPORTSMAN"),
    "TURKEY_DRAW_RESULTS": ("TURKEY", "BEARDED", "LIMITED_ENTRY"),
    "YOUTH_ANTLERLESS_DEER_DRAW_RESULTS": ("DEER", "ANTLERLESS", "YOUTH"),
    "YOUTH_ANTLERLESS_ELK_DRAW_RESULTS": ("ELK", "ANTLERLESS", "YOUTH"),
    "YOUTH_ANTLERLESS_MOOSE_DRAW_RESULTS": ("MOOSE", "ANTLERLESS", "YOUTH"),
    "YOUTH_ANTLERLESS_PRONGHORN_DRAW_RESULTS": ("PRONGHORN", "ANTLERLESS", "YOUTH"),
    "YOUTH_ELK_DRAW_RESULTS": ("ELK", "BULL", "YOUTH"),
    "YOUTH_G.S._DEER_DRAW_RESULTS": ("DEER", "BUCK", "YOUTH"),
    "YOUTH_TURKEY_DRAW_RESULTS": ("TURKEY", "BEARDED", "YOUTH"),
    "ANTLERLESS_DEER_DRAW_RESULTS": ("DEER", "ANTLERLESS", "LIMITED_ENTRY"),
    "ANTLERLESS_ELK_DRAW_RESULTS": ("ELK", "ANTLERLESS", "LIMITED_ENTRY"),
    "ANTLERLESS_MOOSE_DRAW_RESULTS": ("MOOSE", "ANTLERLESS", "LIMITED_ENTRY"),
    "ANTLERLESS_PRONGHORN_DRAW_RESULTS": ("PRONGHORN", "ANTLERLESS", "LIMITED_ENTRY"),
}


@dataclass
class FilePlan:
    year_folder: str
    relative_dir: str
    source_path: Path
    target_path: Path
    status: str
    reason: str
    species: str
    sex_type: str
    hunt_type: str
    source_family: str
    source_role: str
    active_for_scoring: str
    cwmu_stack_status: str
    title_before: str
    title_after: str


def clean_text(value: str) -> str:
    return " ".join((value or "").replace("\u2019", "'").replace("\u2018", "'").split())


def normalize_title(raw_title: str) -> str:
    text = clean_text(raw_title).upper()
    text = text.replace("&", " AND ")
    text = re.sub(r"[\s/\\-]+", "_", text)
    text = re.sub(r"[^A-Z0-9._=]+", "_", text)
    text = re.sub(r"_+", "_", text)
    return text.strip("_")


def parse_year_token(text: str) -> int | None:
    match = re.match(r"^(?P<year>\d{4})", text)
    if match:
        return int(match.group("year"))
    match = re.match(r"^(?P<year>\d{2})(?=[_\s=-])", text)
    if match:
        return 2000 + int(match.group("year"))
    return None


def strip_existing_prefix(stem: str) -> tuple[int | None, str, str]:
    """Return (source_year, residual_title, reason)."""

    canonical = CANONICAL_PREFIX_RE.match(stem)
    if canonical:
        return int(canonical.group("year")), stem[canonical.end():], "already_canonical_prefix"

    legacy = re.match(r"^(?P<year>\d{4}|\d{2})(?:=|\s+|_+|-+)?(?P<model>\d{4})?(?:=|\s+|_+|-+)?", stem)
    if legacy:
        year = legacy.group("year")
        source_year = 2000 + int(year) if len(year) == 2 else int(year)
        residual = stem[legacy.end():]
        return source_year, residual, "legacy_year_prefix"

    return None, stem, "no_year_prefix"


def canonical_prefix_for(year: int) -> str:
    return f"{year}_PERMITS={year + 1}_MODEL__"


def build_target(path: Path, folder_year: int) -> tuple[Path, str, str, int, int | None]:
    source_year, residual, prefix_reason = strip_existing_prefix(path.stem)
    target_year = source_year or folder_year
    residual_norm = normalize_title(residual)
    title = CANONICAL_TITLE_OVERRIDES.get(residual_norm, residual_norm)
    if not title:
        title = normalize_title(path.stem)
    target_name = f"{canonical_prefix_for(target_year)}{title}{path.suffix.lower()}"
    return path.with_name(target_name), title, prefix_reason, target_year, source_year


def classify_species(title: str) -> str:
    hay = title.upper()
    if title in TITLE_HINTS:
        return TITLE_HINTS[title][0]
    for token, species in KNOWN_SPECIES:
        if token in hay:
            return species
    return "UNKNOWN"


def classify_sex(title: str) -> str:
    hay = title.upper()
    if title in TITLE_HINTS:
        return TITLE_HINTS[title][1]
    for token, sex in KNOWN_SEX:
        if token in hay:
            return sex
    return "UNKNOWN"


def classify_hunt_type(title: str) -> str:
    hay = title.upper()
    if title in TITLE_HINTS:
        return TITLE_HINTS[title][2]
    if "O.I.L" in hay:
        return "O_I_L"
    if "L.E" in hay:
        return "LIMITED_ENTRY"
    if "D.H" in hay:
        return "DEDICATED_HUNTER"
    if "G.S" in hay:
        return "GENERAL_SEASON"
    for token, hunt_type in KNOWN_HUNT_TYPE:
        if token in hay:
            return hunt_type
    return "UNKNOWN"


def classify_source_family(title: str, species: str, hunt_type: str) -> str:
    hay = title.upper()
    if "SPORTSMAN" in hay:
        return "SPORTSMAN"
    if "YOUTH_ELK" in hay or "YOUTH_ANY_BULL_ELK" in hay:
        return "YOUTH_ANY_BULL_ELK"
    if species == "BEAR":
        return "BEAR_DRAW_RESULTS"
    if species == "COUGAR":
        return "COUGAR"
    if "YOUTH_D.H" in hay or "YOUTH_D_H" in hay or "YOUTH_DEDICATED" in hay:
        return "YOUTH_DEDICATED_HUNTER_DEER"
    if "D.H" in hay or "D_H" in hay or "DEDICATED_HUNTER" in hay:
        return "DEDICATED_HUNTER_DEER"
    if "YOUTH_G.S" in hay or "YOUTH_G_S" in hay or "YOUTH_GENERAL" in hay:
        return "YOUTH_GENERAL_SEASON_DEER"
    if "LIFETIME_G.S" in hay or "LIFETIME_G_S" in hay or "LIFETIME" in hay:
        return "LIFETIME_GENERAL_SEASON_DEER"
    if "G.S" in hay or "G_S" in hay or "GENERAL" in hay:
        if species == "DEER":
            return "GENERAL_SEASON_DEER"
    if "YOUTH_ANTLERLESS" in hay:
        return "YOUTH_ANTLERLESS"
    if "ANTLERLESS" in hay and species == "MOOSE":
        return "ANTLERLESS_MOOSE"
    if "ANTLERLESS" in hay or "DOE_PRONGHORN" in hay or "DOE" in hay:
        return "ADULT_ANTLERLESS"
    if "TURKEY" in hay:
        return "TURKEY"
    if hunt_type == "O_I_L" or title.startswith("O.I.L") or species in {"BISON", "GOAT", "SHEEP"}:
        return "OIL_BIG_GAME"
    if "P.L.E" in hay or "P_L_E" in hay or "PREMIUM" in hay:
        return "PLE_BIG_GAME"
    if hunt_type == "LIMITED_ENTRY" or "L.E" in hay or "L_E" in hay:
        return "LE_BIG_GAME"
    if "CWMU" in hay:
        return "CWMU_BIG_GAME"
    return "UNKNOWN"


def classify_source_role(
    title: str,
    source_family: str,
    hunt_type: str,
    source_year: int,
    relative_dir: str,
) -> tuple[str, str]:
    hay = title.upper()
    dir_hay = relative_dir.upper()
    if any(token in dir_hay for token in ("PARENT", "ORIGINALS", "ORIGINAL")):
        return "PARENT_OR_REFERENCE_SOURCE", "false"
    if any(
        token in hay
        for token in (
            "BONUS_POINT_SUMMARY",
            "BIG_GAME_ODDS_REPORT",
            "SUMMARY_AND_PURCHASE_PAGES",
            "POINT_PURCHASE",
            "PURCHASE_PAGES",
            "POINTS_ONLY",
        )
    ):
        return "PARENT_OR_REFERENCE_SOURCE", "false"
    if "BONUS_POINTS" in hay and "DRAW_RESULTS" not in hay and "ODDS" not in hay:
        return "PARENT_OR_REFERENCE_SOURCE", "false"
    if "PERMIT_QUOTA" in hay:
        return "PERMIT_QUOTA_INVENTORY", "false"
    if "CONSERVATION" in hay or "AUCTION" in hay:
        return "CONSERVATION_BENEFIT_AUCTION_NOT_DRAW", "false"
    if source_family == "COUGAR" and source_year > 2023 and "DRAW_RESULTS" not in hay and "ODDS" not in hay:
        return "COUGAR_LICENSE_STATUS_AFTER_2023", "false"
    if "DRAW_RESULTS" in hay or "ODDS" in hay or "DRAW_ODDS" in hay:
        return "OFFICIAL_DRAW_RESULTS", "true"
    if "PREFERENCE" in hay or "PREFERENCE_POINT" in hay:
        return "OFFICIAL_DRAW_RESULTS_PREFERENCE_POINT", "true"
    if hunt_type in {"SPORTSMAN", "LIMITED_ENTRY", "O_I_L", "GENERAL_SEASON", "DEDICATED_HUNTER", "YOUTH"}:
        return "OFFICIAL_DRAW_RESULTS", "true"
    return "REVIEW_REQUIRED", "false"


def classify_cwmu_stack_status(title: str, relative_dir: str) -> str:
    hay = title.upper()
    dir_hay = relative_dir.replace("\\", "/").upper()
    if "CWMU" not in hay and "CWMU" not in dir_hay:
        return ""
    if any(token in hay for token in ("ANTLERLESS", "DOE_PRONGHORN", "DOE")):
        expected = "CWMU/ANTLERLESS CWMU"
    else:
        expected = "CWMU/BIG GAME CWMU"
    if dir_hay == expected:
        return "OK"
    return f"VIOLATION_EXPECT_{expected}"


def collect_plans(root: Path) -> list[FilePlan]:
    plans: list[FilePlan] = []
    for year_dir in sorted(p for p in root.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}", p.name)):
        year_folder = int(year_dir.name)
        draw_dir = year_dir / "pdf" / "draw_odds"
        if not draw_dir.exists():
            continue
        for file_path in sorted(p for p in draw_dir.rglob("*.pdf") if p.is_file()):
            target_path, title_after, prefix_reason, target_year, source_year = build_target(file_path, year_folder)
            species = classify_species(title_after)
            sex_type = classify_sex(title_after)
            hunt_type = classify_hunt_type(title_after)
            source_family = classify_source_family(title_after, species, hunt_type)
            relative_dir = str(file_path.parent.relative_to(draw_dir)).replace("\\", "/")
            if relative_dir == ".":
                relative_dir = ""
            source_role, active_for_scoring = classify_source_role(
                title_after,
                source_family,
                hunt_type,
                target_year,
                relative_dir,
            )
            cwmu_stack_status = classify_cwmu_stack_status(title_after, relative_dir)
            if target_path.name == file_path.name:
                status = "ALREADY_STANDARDIZED"
                reason = prefix_reason
            elif target_path.exists():
                status = "COLLISION_TARGET_EXISTS"
                reason = f"{prefix_reason}; target already exists"
            else:
                status = "READY_TO_RENAME"
                reason = prefix_reason

            if source_year is not None and source_year != year_folder:
                reason = f"{reason}; year_mismatch_folder={year_folder}"
                if status == "READY_TO_RENAME":
                    status = "READY_WITH_YEAR_MISMATCH"

            plans.append(
                FilePlan(
                    year_folder=year_dir.name,
                    relative_dir=relative_dir,
                    source_path=file_path,
                    target_path=target_path,
                    status=status,
                    reason=reason,
                    species=species,
                    sex_type=sex_type,
                    hunt_type=hunt_type,
                    source_family=source_family,
                    source_role=source_role,
                    active_for_scoring=active_for_scoring,
                    cwmu_stack_status=cwmu_stack_status,
                    title_before=file_path.stem,
                    title_after=title_after,
                )
            )
    return plans


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def summarize(plans: list[FilePlan]) -> dict[str, object]:
    year_counts = Counter(plan.year_folder for plan in plans)
    status_counts = Counter(plan.status for plan in plans)
    species_counts = Counter(plan.species for plan in plans)
    sex_counts = Counter(plan.sex_type for plan in plans)
    hunt_counts = Counter(plan.hunt_type for plan in plans)
    family_counts = Counter(plan.source_family for plan in plans)
    role_counts = Counter(plan.source_role for plan in plans)
    cwmu_stack_counts = Counter(plan.cwmu_stack_status for plan in plans if plan.cwmu_stack_status)
    combo_counts = Counter((plan.species, plan.sex_type, plan.hunt_type) for plan in plans)
    return {
        "total_files": len(plans),
        "year_counts": dict(sorted(year_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "species_counts": dict(sorted(species_counts.items())),
        "sex_counts": dict(sorted(sex_counts.items())),
        "hunt_counts": dict(sorted(hunt_counts.items())),
        "source_family_counts": dict(sorted(family_counts.items())),
        "source_role_counts": dict(sorted(role_counts.items())),
        "cwmu_stack_counts": dict(sorted(cwmu_stack_counts.items())),
        "combo_counts": [
            {"species": species, "sex_type": sex_type, "hunt_type": hunt_type, "count": count}
            for (species, sex_type, hunt_type), count in combo_counts.most_common()
        ],
    }


def render_markdown(summary: dict[str, object], plans: list[FilePlan]) -> str:
    lines = [
        "# Draw Odds PDF Filename Standardization",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Summary",
        "",
        f"- Total PDF files scanned: {summary['total_files']}",
        f"- Ready to rename: {summary['status_counts'].get('READY_TO_RENAME', 0)}",
        f"- Ready with year mismatch: {summary['status_counts'].get('READY_WITH_YEAR_MISMATCH', 0)}",
        f"- Already standardized: {summary['status_counts'].get('ALREADY_STANDARDIZED', 0)}",
        f"- Collisions blocked: {summary['status_counts'].get('COLLISION_TARGET_EXISTS', 0)}",
        f"- CWMU stack violations: {sum(count for status, count in summary['cwmu_stack_counts'].items() if status != 'OK')}",
        "",
        "## Files By Year",
        "",
        "| Year | Count |",
        "| --- | ---: |",
        *[f"| {year} | {count} |" for year, count in summary["year_counts"].items()],
        "",
        "## Files By Species",
        "",
        "| Species | Count |",
        "| --- | ---: |",
        *[f"| {species} | {count} |" for species, count in summary["species_counts"].items()],
        "",
        "## Files By Sex Type",
        "",
        "| Sex Type | Count |",
        "| --- | ---: |",
        *[f"| {sex_type} | {count} |" for sex_type, count in summary["sex_counts"].items()],
        "",
        "## Files By Hunt Type",
        "",
        "| Hunt Type | Count |",
        "| --- | ---: |",
        *[f"| {hunt_type} | {count} |" for hunt_type, count in summary["hunt_counts"].items()],
        "",
        "## Files By Source Role",
        "",
        "| Source Role | Count |",
        "| --- | ---: |",
        *[f"| {source_role} | {count} |" for source_role, count in summary["source_role_counts"].items()],
        "",
        "## Rename Candidates",
        "",
        "| Year | Folder | Current Name | Proposed Name | Status | Family | Role | Active | Species | Sex Type | Hunt Type |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for plan in plans:
        if plan.status not in {"READY_TO_RENAME", "READY_WITH_YEAR_MISMATCH", "COLLISION_TARGET_EXISTS"}:
            continue
        lines.append(
            f"| {plan.year_folder} | {plan.relative_dir} | {plan.source_path.name} | {plan.target_path.name} | {plan.status} | "
            f"{plan.source_family} | {plan.source_role} | {plan.active_for_scoring} | {plan.species} | {plan.sex_type} | {plan.hunt_type} |"
        )
    lines.append("")
    return "\n".join(lines)


def apply_renames(plans: list[FilePlan], include_year_mismatch: bool = False) -> list[dict[str, str]]:
    results: list[dict[str, str]] = []
    for plan in plans:
        allowed_statuses = {"READY_TO_RENAME"}
        if include_year_mismatch:
            allowed_statuses.add("READY_WITH_YEAR_MISMATCH")
        if plan.status not in allowed_statuses:
            continue
        if plan.source_path.name == plan.target_path.name:
            results.append(
                {
                    "source_path": str(plan.source_path),
                    "target_path": str(plan.target_path),
                    "status": "SKIPPED_ALREADY_STANDARD",
                }
            )
            continue
        if plan.target_path.exists():
            results.append(
                {
                    "source_path": str(plan.source_path),
                    "target_path": str(plan.target_path),
                    "status": "BLOCKED_TARGET_EXISTS",
                }
            )
            continue
        plan.source_path.rename(plan.target_path)
        results.append(
            {
                "source_path": str(plan.source_path),
                "target_path": str(plan.target_path),
                "status": "RENAMED",
            }
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Rename files in place.")
    parser.add_argument(
        "--include-year-mismatch",
        action="store_true",
        help="When applying renames, also rename files whose filename year does not match the folder year.",
    )
    parser.add_argument(
        "--report-dir",
        type=Path,
        default=AUDIT_ROOT / "draw_odds_filename_standardization",
        help="Directory for audit outputs.",
    )
    args = parser.parse_args()

    plans = collect_plans(PIPELINE_ROOT)
    summary = summarize(plans)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%SZ")
    report_dir = args.report_dir / stamp
    report_dir.mkdir(parents=True, exist_ok=True)

    plan_rows = [
        {
            "year_folder": plan.year_folder,
            "relative_dir": plan.relative_dir,
            "source_path": str(plan.source_path),
            "current_name": plan.source_path.name,
            "target_path": str(plan.target_path),
            "proposed_name": plan.target_path.name,
            "status": plan.status,
            "reason": plan.reason,
            "species": plan.species,
            "sex_type": plan.sex_type,
            "hunt_type": plan.hunt_type,
            "source_family": plan.source_family,
            "source_role": plan.source_role,
            "active_for_scoring": plan.active_for_scoring,
            "cwmu_stack_status": plan.cwmu_stack_status,
        }
        for plan in plans
    ]
    write_csv(
        report_dir / "draw_odds_filename_standardization_plan.csv",
        [
            "year_folder",
            "relative_dir",
            "source_path",
            "current_name",
            "target_path",
            "proposed_name",
            "status",
            "reason",
            "species",
            "sex_type",
            "hunt_type",
            "source_family",
            "source_role",
            "active_for_scoring",
            "cwmu_stack_status",
        ],
        plan_rows,
    )

    breakdown_rows = [
        {"species": row["species"], "sex_type": row["sex_type"], "hunt_type": row["hunt_type"], "count": str(row["count"])}
        for row in summary["combo_counts"]
    ]
    write_csv(
        report_dir / "draw_odds_species_sex_hunt_type_breakdown.csv",
        ["species", "sex_type", "hunt_type", "count"],
        breakdown_rows,
    )

    report_md = render_markdown(summary, plans)
    (report_dir / "draw_odds_filename_standardization_report.md").write_text(report_md, encoding="utf-8")
    (report_dir / "draw_odds_filename_standardization_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n",
        encoding="utf-8",
    )

    rename_results = []
    if args.apply:
        rename_results = apply_renames(plans, include_year_mismatch=args.include_year_mismatch)
        write_csv(
            report_dir / "draw_odds_filename_standardization_renames.csv",
            ["source_path", "target_path", "status"],
            rename_results,
        )

    print(
        json.dumps(
            {
                "ok": True,
                "report_dir": str(report_dir),
                "total_files": summary["total_files"],
                "ready_to_rename": summary["status_counts"].get("READY_TO_RENAME", 0),
                "ready_with_year_mismatch": summary["status_counts"].get("READY_WITH_YEAR_MISMATCH", 0),
                "already_standardized": summary["status_counts"].get("ALREADY_STANDARDIZED", 0),
                "collisions_blocked": summary["status_counts"].get("COLLISION_TARGET_EXISTS", 0),
                "renamed": sum(1 for row in rename_results if row["status"] == "RENAMED"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
