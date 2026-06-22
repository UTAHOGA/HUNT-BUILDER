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
    name = re.sub(r"^(?:Limited[- ]Entry|Premium Limited Entry|Once[- ]in[- ]a[- ]lifetime)\s*[-:]\s*", "", name, flags=re.I)

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
    hunt_type = compact(row.get("hunt_type"))
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

    for row_number, row in enumerate(rows, start=2):
        old = compact(row.get("hunt_name"))
        old_hunt_type = compact(row.get("hunt_type"))
        old_hunt_class = compact(row.get("hunt_class"))
        new = normalize_hunt_name(old, row.get("hunt_code"))
        if old != new and unsafe_clean_result(new):
            new = old

        new_hunt_type, new_hunt_class = normalize_cwmu_fields(row, old)
        row_for_private_land = dict(row)
        row_for_private_land["hunt_type"] = new_hunt_type
        row_for_private_land["hunt_class"] = new_hunt_class
        new_hunt_type, new_hunt_class = normalize_private_land_fields(row_for_private_land, old)
        field_changed = (
            old_hunt_type != new_hunt_type
            or old_hunt_class != new_hunt_class
        )

        if old != new or field_changed:
            changed += 1
            category = classify_change(old, new)
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
