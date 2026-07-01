import argparse
import csv
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE_PATH = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
AUDIT_PATH = ROOT / "audits/2025_canonical_finalization/database_hunt_name_normalization_audit.csv"

HUNT_CODE_NAME_OVERRIDES = {
    # Broad elk reference rows: keep the boundary-style name, not sex/species/weapon title text.
    "EB1005": "Any Bull Units",
    "EB1007": "Youth Any Bull Units",
    "EB1011": "Youth General Season Units",
    "EB1012": "Uinta Basin",
}

SPORTSMAN_CODES = {
    "BI1000",
    "BR1000",
    "CG1000",
    "DB0007",
    "DS1000",
    "EB1000",
    "GO1000",
    "MB1000",
    "PB1000",
    "RS0001",
    "TK0001",
}

HUNT_TYPE_MAP = {
    "Antlerless Elk Control": "O.T.C.",
    "General-Season": "General Season",
    "General-season": "General Season",
    "General Season - Archery": "General Season",
    "General Season - Any Bull": "General Season",
    "General Season - Spike Bull": "General Season",
    "General Season - Youth": "General Season",
    "Harvest Objective": "O.T.C.",
    "Fall Management": "O.T.C.",
    "Limited Entry - Fall": "Limited Entry",
    "Limited Entry - Multiseason": "Limited Entry",
    "Limited Entry - Spring": "Limited Entry",
    "Limited Entry - Summer": "Limited Entry",
    "Multiseason - Conservation": "Conservation",
    "P.L.E.": "P.L.E.",
    "PLE": "P.L.E.",
    "Premium LE": "P.L.E.",
    "Premium Le": "P.L.E.",
    "Premium Limited Entry": "P.L.E.",
    "Restricted Pursuit - Late Summer": "O.T.C.",
    "Restricted Pursuit - Spring": "O.T.C.",
    "Restricted Pursuit - Summer": "O.T.C.",
    "Spot and Stalk": "O.T.C.",
    "Spring General Season": "General Season",
    "Pursuit": "O.T.C.",
    "Extended Archery": "O.T.C.",
}


SPECIES_PREFIXES = (
    "Antlerless Deer",
    "Buck Deer",
    "Deer",
    "Bull Elk",
    "Antlerless Elk",
    "Cow Elk",
    "Elk",
    "Black Bear",
    "Bison",
    "Moose",
    "Mountain Goat",
    "Rocky Mountain Bighorn Sheep",
    "Rocky Mountain Sheep",
    "Desert Bighorn Sheep",
    "Pronghorn Antelope",
    "Pronghorn",
    "Turkey",
    "Cougar",
)

SEX_WORDS = (
    "Hunter's Choice",
    "Hunters Choice",
    "Any Bull/Hunters Choice",
    "Any Bull/Hunter's Choice",
    "Any Bull",
    "Male Only",
    "Female Only",
    "Either Sex",
    "Cow Only",
    "Bull Only",
    "Buck Only",
    "Doe Only",
    "Ram",
    "Ewe",
    "Bearded",
    "Antlerless",
    "Bull",
    "Buck",
    "Cow",
    "Doe",
)

WEAPON_WORDS = (
    "Any Legal Weapon",
    "Archery",
    "Muzzleloader",
    "Mzldr",
    "Shotgun",
    "Shotgn",
    "Rifle",
    "Multiseason",
    "Multi-season",
    "Multi Season",
    "HAMMS",
    "HAMS",
    "H.A.M.S.",
)

CLASS_SUFFIXES = (
    "P.L.E.",
    "Premium Limited Entry",
    "Premium LE",
    "Premium Le",
    "Premium",
    "Limited Entry",
    "Limited-Entry",
    "LE",
    "L.E.",
    "OIL",
    "O.I.L.",
    "Once-in-a-lifetime",
    "Once In A Lifetime",
    "Conservation",
    "Sportsman",
    "CWMU",
)

PRIVATE_LAND_RE = re.compile(
    r"\s*[-,]\s*Private\s+Lands?\s+Only\s*$",
    flags=re.I,
)

DATE_TOKEN_RE = re.compile(
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|"
    r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)(?:\.?)\s*\d{1,2}(?:,\s*\d{4})?",
    flags=re.I,
)


def compact(value: object) -> str:
    text = "" if value is None else str(value)
    return (
        text.replace("\u2019", "'")
        .replace("\u2018", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
        .replace("\xa0", " ")
        .strip()
    )


def normalize_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" ,;-")


def alternation(words: tuple[str, ...]) -> str:
    return "|".join(re.escape(word) for word in sorted(words, key=len, reverse=True))


SPECIES_ALT = alternation(SPECIES_PREFIXES)
SEX_ALT = alternation(SEX_WORDS)
WEAPON_ALT = alternation(WEAPON_WORDS)
CLASS_ALT = alternation(CLASS_SUFFIXES)


def normalize_hunt_name(raw_value: object, hunt_code: object = "") -> str:
    code = compact(hunt_code).upper()
    if code in HUNT_CODE_NAME_OVERRIDES:
        return HUNT_CODE_NAME_OVERRIDES[code]

    name = normalize_spaces(compact(raw_value))
    if not name:
        return name

    # Standardize statewide permit rows to the actual hunt name, not species + permit jargon.
    name = re.sub(r"\s+-\s+Statewide Permit$", " - Statewide", name, flags=re.I)
    name = re.sub(rf"^(?:{SPECIES_ALT})\s+-\s+Statewide$", "Statewide", name, flags=re.I)
    name = re.sub(r"\bStatewide Permit\b", "Statewide", name, flags=re.I)
    name = re.sub(r"\s+\bPermit\b$", "", name, flags=re.I)

    # Remove leading species/draw labels when a real unit name follows after a separator.
    name = re.sub(rf"^(?:{SPECIES_ALT})\s*[-:]\s*", "", name, flags=re.I)
    name = re.sub(r"^(?:Limited[- ]Entry|P\.L\.E\.|Premium Limited Entry|Once[- ]in[- ]a[- ]lifetime)\s*[-:]\s*", "", name, flags=re.I)

    # Remove classification-only parentheticals, but keep meaningful unit parentheticals.
    name = re.sub(r"\s*\((?:Conservation|Premium|Limited Entry|LE|OIL|Early|Mid|Late|Hunter'?s Choice)\)\s*$", "", name, flags=re.I)

    # If trailing dash text is weapon/sex/classification, remove only that trailing segment.
    name = PRIVATE_LAND_RE.sub("", name)
    name = re.sub(rf"\s+-\s*(?:{WEAPON_ALT})(?:\b.*)?$", "", name, flags=re.I)
    name = re.sub(rf"\s+-\s*(?:{SEX_ALT})\s*$", "", name, flags=re.I)
    name = re.sub(rf"\s+-\s*(?:{CLASS_ALT})\s*$", "", name, flags=re.I)

    # Remove terminal species/sex/class artifacts that were appended without a separator.
    name = re.sub(rf"\s+\b(?:{SEX_ALT})\s+(?:{SPECIES_ALT})\b$", "", name, flags=re.I)
    name = re.sub(rf"\s+\b(?:{SPECIES_ALT})\b$", "", name, flags=re.I)
    name = re.sub(rf"\s+\b(?:{CLASS_ALT})\b$", "", name, flags=re.I)

    return normalize_spaces(name)


def unsafe_clean_result(value: str) -> bool:
    normalized = normalize_spaces(value).lower()
    if not normalized:
        return True
    if normalized in {
        "archery",
        "muzzleloader",
        "rifle",
        "multiseason",
        "multi-season",
        "any",
        "any bull",
        "hunters choice",
        "hunter's choice",
        "draw-only youth",
        "youth general season",
    }:
        return True
    if normalized.endswith(" any"):
        return True
    if "hunter's choice" in normalized or "hunters choice" in normalized:
        return True
    return False


def classify_change(old: str, new: str) -> str:
    old_lower = old.lower()
    if re.search(r"\bCWMU\b$", old, re.I):
        return "cwmu_hunt_type_label_removed"
    if PRIVATE_LAND_RE.search(old):
        return "private_land_label_removed"
    if "statewide permit" in old_lower or old_lower.endswith(" permit"):
        return "statewide_or_permit_artifact"
    if re.search(r"\((?:conservation|premium|limited entry|le|oil)\)$", old, re.I):
        return "classification_parenthetical_removed"
    if re.search(rf"\b(?:{CLASS_ALT})\b$", old, re.I):
        return "classification_suffix_removed"
    if re.search(rf"\b(?:{WEAPON_ALT})\b", old, re.I):
        return "weapon_artifact_removed"
    if re.search(rf"\b(?:{SEX_ALT})\b", old, re.I):
        return "sex_artifact_removed"
    if re.search(rf"^(?:{SPECIES_ALT})\s*[-:]", old, re.I) or re.search(rf"\b(?:{SPECIES_ALT})\b$", old, re.I):
        return "species_artifact_removed"
    return "normalized_spacing_or_label"


def normalize_cwmu_fields(row: dict[str, str], old_hunt_name: str) -> tuple[str, str]:
    """Move displaced draw wording out of hunt_type before making hunt_type CWMU."""
    hunt_type = normalize_hunt_type(row.get("hunt_type"))
    hunt_class = compact(row.get("hunt_class"))
    if not re.search(r"\bCWMU\b$", old_hunt_name, re.I):
        return hunt_type, hunt_class
    if hunt_type.upper() == "CWMU":
        return hunt_type, hunt_class

    next_hunt_type = "CWMU"
    next_hunt_class = hunt_class
    if hunt_type and (not hunt_class or hunt_class.upper() == "CWMU"):
        next_hunt_class = hunt_type
    return next_hunt_type, next_hunt_class


def normalize_private_land_fields(row: dict[str, str], old_hunt_name: str) -> tuple[str, str]:
    hunt_type = compact(row.get("hunt_type"))
    hunt_class = compact(row.get("hunt_class"))
    has_private_land_name = bool(PRIVATE_LAND_RE.search(old_hunt_name))
    has_private_land_type = bool(re.search(r"\bPrivate\s+Lands?\s+Only\b", hunt_type, re.I))
    if not has_private_land_name and not has_private_land_type:
        return hunt_type, hunt_class

    exact_private_land_type = bool(re.fullmatch(r"Private\s+Lands?\s+Only", hunt_type, flags=re.I))
    next_hunt_type = (
        ""
        if exact_private_land_type
        else normalize_spaces(
            re.sub(r"\s*[-,]\s*Private\s+Lands?\s+Only\s*$", "", hunt_type, flags=re.I)
        )
    )
    next_hunt_class = hunt_class
    if not next_hunt_type and has_private_land_type:
        next_hunt_type = "O.T.C."
        next_hunt_class = "Private Land Only"
    elif not next_hunt_class or re.fullmatch(r"General Season", next_hunt_class, flags=re.I):
        next_hunt_class = "Private Land Only"
    return next_hunt_type, next_hunt_class


def normalize_hunt_type(value: object) -> str:
    hunt_type = normalize_spaces(compact(value))
    if not hunt_type:
        return hunt_type
    return HUNT_TYPE_MAP.get(hunt_type, hunt_type)


def infer_draw_design(row: dict[str, str], hunt_type: str) -> str:
    code = compact(row.get("hunt_code")).upper()
    text = " ".join(
        [
            code,
            compact(row.get("hunt_name")),
            hunt_type,
            compact(row.get("hunt_class")),
            compact(row.get("weapon")),
            compact(row.get("season")),
            compact(row.get("draw_2026_system_type")),
        ]
    ).lower()
    system_type = compact(row.get("draw_2026_system_type")).upper()
    if not system_type:
        system_type = compact(row.get("draw_system_type")).upper()
    if system_type:
        return system_type
    hunt_class = compact(row.get("hunt_class")).lower()

    if code in SPORTSMAN_CODES or system_type.startswith("SPORTSMAN") or "sportsman" in text:
        return "Random"
    if system_type.startswith("PREFERENCE_") or "dedicated hunter" in text or hunt_type == "General Season":
        return "Preference"
    if hunt_type == "O.T.C." or system_type == "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK":
        return "Capped Permits"
    if hunt_type == "Conservation" or "conservation" in hunt_class:
        return "Organizations"
    if hunt_type in {"Limited Entry", "P.L.E.", "Once-in-a-lifetime"} or system_type.startswith("BONUS_") or system_type == "BEAR_DRAW":
        return "Max/Weighted Split"
    if hunt_type == "CWMU" or system_type.startswith("BONUS_CWMU"):
        return "Max/Weighted Split"
    if hunt_type == "Tribal":
        return "Tribal"
    if hunt_type == "Statewide":
        return "Capped Permits"
    if "youth" in text and "elk" in text:
        return "Random"
    return ""


def normalize_season(value: object) -> str:
    season = normalize_spaces(compact(value))
    if not season:
        return season
    if season.lower() == "multiseason":
        return "Multiseason"
    # Compound season strings usually contain multiple explicit date ranges.
    # Keep single season windows intact, but collapse true multi-date entries.
    if len(DATE_TOKEN_RE.findall(season)) >= 4:
        return "Multiseason"
    return season


DRAW_DESIGN_CLASSES = {
    "Random",
    "Preference",
    "Max/Weighted Split",
    "Capped Permits",
    "Organizations",
    "Tribal",
}


def normalize_hunt_class(row: dict[str, str], hunt_type: str) -> str:
    hunt_class = normalize_spaces(compact(row.get("hunt_class")))
    if hunt_class in DRAW_DESIGN_CLASSES:
        return hunt_class
    new_value = infer_draw_design(row, hunt_type)
    return new_value if new_value in DRAW_DESIGN_CLASSES else ""


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write DATABASE.csv updates.")
    args = parser.parse_args()

    with DATABASE_PATH.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = reader.fieldnames or []

    if "hunt_name" not in fieldnames:
        raise SystemExit("DATABASE.csv does not contain a hunt_name column")

    audit_rows: list[dict[str, str]] = []
    changed = 0
    unchanged = 0
    categories: Counter[str] = Counter()
    has_draw_design = "draw_design" in fieldnames

    for row_number, row in enumerate(rows, start=2):
        old = compact(row.get("hunt_name"))
        old_hunt_type = compact(row.get("hunt_type"))
        old_hunt_class = compact(row.get("hunt_class"))
        old_season = compact(row.get("season"))
        old_draw_design = compact(row.get("draw_design")) if has_draw_design else ""
        new = normalize_hunt_name(old, row.get("hunt_code"))
        if old != new and unsafe_clean_result(new):
            new = old

        new_hunt_type = normalize_hunt_type(old_hunt_type)
        new_hunt_type, new_hunt_class = normalize_cwmu_fields(row, old)
        row_for_private_land = dict(row)
        row_for_private_land["hunt_type"] = new_hunt_type
        row_for_private_land["hunt_class"] = new_hunt_class
        new_hunt_type, new_hunt_class = normalize_private_land_fields(row_for_private_land, old)
        new_hunt_class = normalize_hunt_class({**row, "hunt_type": new_hunt_type, "hunt_class": new_hunt_class}, new_hunt_type)
        new_season = normalize_season(old_season)
        new_draw_design = old_draw_design
        if has_draw_design and not old_draw_design:
            new_draw_design = infer_draw_design(row, new_hunt_type)
        field_changed = (
            old_hunt_type != new_hunt_type
            or old_hunt_class != new_hunt_class
            or old_season != new_season
            or (has_draw_design and old_draw_design != new_draw_design)
        )

        if old != new or field_changed:
            changed += 1
            category = classify_change(old, new)
            if old == new and old_season != new_season:
                category = "season_multiseason_normalized"
            elif old_hunt_type != new_hunt_type:
                category = "hunt_type_label_normalized"
            elif old_hunt_class != new_hunt_class:
                category = "hunt_class_normalized"
            elif has_draw_design and old_draw_design != new_draw_design:
                category = "draw_design_filled"
            categories[category] += 1
            audit_rows.append(
                {
                    "csv_row": str(row_number),
                    "hunt_code": compact(row.get("hunt_code")),
                    "boundary_id": compact(row.get("boundary_id")),
                    "species": compact(row.get("species")),
                    "sex_type": compact(row.get("sex_type")),
                    "weapon": compact(row.get("weapon")),
                    "old_hunt_name": old,
                    "new_hunt_name": new,
                    "old_hunt_type": old_hunt_type,
                    "new_hunt_type": new_hunt_type,
                    "old_hunt_class": old_hunt_class,
                    "new_hunt_class": new_hunt_class,
                    "old_season": old_season,
                    "new_season": new_season,
                    "old_draw_design": old_draw_design if has_draw_design else "",
                    "new_draw_design": new_draw_design if has_draw_design else "",
                    "change_category": category,
                    "applied": "yes" if args.apply else "no",
                }
            )
            if args.apply:
                row["hunt_name"] = new
                if "hunt_type" in row:
                    row["hunt_type"] = new_hunt_type
                if "hunt_class" in row:
                    row["hunt_class"] = new_hunt_class
                if "season" in row:
                    row["season"] = new_season
                if has_draw_design and "draw_design" in row:
                    row["draw_design"] = new_draw_design
        else:
            unchanged += 1

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "csv_row",
                "hunt_code",
                "boundary_id",
                "species",
                "sex_type",
                "weapon",
                "old_hunt_name",
                "new_hunt_name",
                "old_hunt_type",
                "new_hunt_type",
                "old_hunt_class",
                "new_hunt_class",
                "old_season",
                "new_season",
                "old_draw_design",
                "new_draw_design",
                "change_category",
                "applied",
            ],
        )
        writer.writeheader()
        writer.writerows(audit_rows)

    if args.apply:
        tmp_path = DATABASE_PATH.with_suffix(".csv.tmp")
        with tmp_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        tmp_path.replace(DATABASE_PATH)

    print(
        {
            "mode": "apply" if args.apply else "dry-run",
            "database_rows": len(rows),
            "changed": changed,
            "unchanged": unchanged,
            "categories": dict(categories),
            "audit_path": str(AUDIT_PATH),
            "database_path": str(DATABASE_PATH) if args.apply else None,
        }
    )


if __name__ == "__main__":
    main()
