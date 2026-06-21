import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2019_for_2020_canonical_yearly_draw_results.csv"
)
AUDIT = REPO / "audits" / "truth_cross_year" / "final_yearly_canonical_audit" / "2019_for_2020" / "hunt_name_cleanup"
BACKUPS = AUDIT / "backups"

PROGRAM_PREFIXES = [
    "Antlerless Rocky Mountain Bighorn Sheep",
    "Rocky Mountain Bighorn Sheep",
    "Limited Entry Archery Buck Pronghorn",
    "Limited Entry Alw (rifle) Buck Pronghorn",
    "Limited Entry Muzzleloader Buck Pronghorn",
    "Limited Entry Buck Pronghorn",
    "Limited Entry Archery Buck Deer",
    "Limited Entry Alw (rifle) Buck Deer",
    "Limited Entry Muzzleloader Buck Deer",
    "Limited Entry Multi-season Buck Deer",
    "Limited Entry Buck Deer",
    "Limited Entry Archery Bull Elk",
    "Limited Entry Alw (rifle) Bull Elk",
    "Limited Entry Muzzleloader Bull Elk",
    "Limited Entry Multi-season Bull Elk",
    "Limited Entry Bull Elk",
    "Cwmu Buck Deer",
    "CWMU Buck Deer",
    "Cwmu Bull Elk",
    "CWMU Bull Elk",
    "Cwmu Buck Pronghorn",
    "CWMU Buck Pronghorn",
    "Dedicated Hunter",
    "General Season Buck Deer",
    "Youth General Season Buck Deer",
    "Youth Dedicated Hunter",
    "Antlerless Pronghorn",
    "Doe Pronghorn",
    "Youth Doe Pronghorn",
    "Youth Antlerless Pronghorn",
    "Antlerless Moose",
    "Cow Moose",
    "Antlerless Deer",
    "Youth Antlerless Deer",
    "Antlerless Elk",
    "Youth Antlerless Elk",
    "Cow Elk",
    "Bison",
    "Buck Pronghorn",
    "Buck Deer",
    "Bull Elk",
    "Bull Moose",
    "Mountain Goat",
    "Cougar",
    "Black Bear",
]

LEADING_PREFIXES = [
    *PROGRAM_PREFIXES,
    "Limited Entry",
    "Cwmu",
    "CWMU",
    "Youth",
    "General Season",
    "Draw-only",
    "Management",
    "Archery",
    "Muzzleloader",
    "Rifle",
    "Shotgun",
    "Any Legal Weapon",
    "Any Weapon",
    "Multi-season",
    "ALW",
]

WEAPON_SUFFIXES = {
    "Any Legal Weapon",
    "ALW",
    "Archery",
    "Muzzleloader",
    "Multi-season",
    "Mzl",
    "Muzzleloader Only",
    "Archery Only",
    "Hounds",
    "Rifle",
    "Shotgun",
    "Any Weapon",
}

OCR_FIXES = [
    (re.compile(r"\bAn y\b", re.I), "Any"),
    (re.compile(r"\bHenr y\b", re.I), "Henry"),
    (re.compile(r"\bO quirrh\b", re.I), "Oquirrh"),
    (re.compile(r"\bA rchery\b", re.I), "Archery"),
    (re.compile(r"\bLimited[- ]Entry\b", re.I), "Limited Entry"),
]

TRAILING_DESCRIPTOR_RE = re.compile(
    r"\s*\((?:[^)]*?(?:cow|bull|buck|doe|ram|female|male|hunter|hunters|choice|weapon|archery|muzzleloader|rifle|shotgun|any legal weapon|alw|multi-season|hounds|youth)[^)]*)\)\s*$",
    re.I,
)


def clean(value):
    return "" if value is None else str(value).strip()


def normalize_whitespace(text):
    return re.sub(r"\s+", " ", clean(text))


def normalize_punctuation(text):
    return re.sub(r"\s*,\s*", ", ", text).replace(" / ", "/")


def compact_text(text):
    return re.sub(r"[^a-z]", "", clean(text).lower())


def split_unit_segments(text):
    return [segment.strip() for segment in re.split(r"\s+-\s*|\s*-\s+", text) if segment.strip()]


def is_weaponish(text):
    compact = compact_text(text)
    return any(compact == compact_text(suffix) or compact.endswith(compact_text(suffix)) for suffix in WEAPON_SUFFIXES)


def is_species_lead(text):
    return bool(re.match(r"^Any\s+(?:Bull|Buck|Antlerless|Cow|Doe|Ram)\b", clean(text), flags=re.I))


def clean_hunt_name(value, row):
    text = normalize_punctuation(normalize_whitespace(value))
    text = re.sub(r"^Hunt:\s*[A-Z]{1,3}\d{3,4}\s+", "", text, flags=re.I)

    for pattern, replacement in OCR_FIXES:
        text = pattern.sub(replacement, text)

    changed = True
    while changed:
        changed = False

        segments = split_unit_segments(text)
        if len(segments) >= 3 and is_weaponish(segments[-1]):
            text = " - ".join(segments[1:-1])
            changed = True
        elif len(segments) == 2 and (is_weaponish(segments[0]) or is_species_lead(segments[0])):
            text = segments[1]
            changed = True

        for prefix in LEADING_PREFIXES:
            pattern = rf"^{re.escape(prefix)}(?:\s*-\s*|\s+)?"
            new_text = re.sub(pattern, "", text, flags=re.I).strip()
            if new_text != text:
                text = new_text
                changed = True

        new_text = TRAILING_DESCRIPTOR_RE.sub("", text).strip()
        if new_text != text:
            text = new_text
            changed = True

        if clean(row.get("hunt_type")).upper() == "CWMU" and re.search(r"\bCWMU\b$", text, flags=re.I):
            text = re.sub(r"\s*CWMU\s*$", "", text, flags=re.I).strip()
            changed = True

        suffix_match = re.match(r"^(.*?)(?:\s*-\s*)([^-]+?)\s*$", text)
        if suffix_match:
            head = suffix_match.group(1).strip()
            tail = suffix_match.group(2).strip()
            compact_tail = compact_text(tail)
            if any(
                compact_tail == compact_text(suffix) or compact_tail.endswith(compact_text(suffix))
                for suffix in WEAPON_SUFFIXES
            ):
                text = head
                changed = True

    text = re.sub(r"\s+", " ", text).replace(", ", ", ").strip(" -")
    return text


def main():
    AUDIT.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    with TARGET.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    backup = BACKUPS / f"{TARGET.stem}.backup_before_hunt_name_cleanup_{timestamp}.csv"
    shutil.copy2(TARGET, backup)

    mutation_counts = Counter()
    samples = []
    changed_rows = 0

    for row in rows:
        old_name = clean(row.get("hunt_name"))
        new_name = clean_hunt_name(old_name, row)
        if new_name != old_name:
            row["hunt_name"] = new_name
            changed_rows += 1
            mutation_counts["hunt_name"] += 1
            if len(samples) < 200:
                samples.append(
                    {
                        "hunt_code": clean(row.get("hunt_code")),
                        "row_type": clean(row.get("row_type")),
                        "hunt_type": clean(row.get("hunt_type")),
                        "old_hunt_name": old_name,
                        "new_hunt_name": new_name,
                    }
                )

    tmp_path = TARGET.with_suffix(f".hunt_name_cleanup_{timestamp}.tmp")
    with tmp_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    shutil.move(str(tmp_path), str(TARGET))

    with (AUDIT / "2019_hunt_name_cleanup_samples.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["hunt_code", "row_type", "hunt_type", "old_hunt_name", "new_hunt_name"])
        writer.writeheader()
        writer.writerows(samples)

    status = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "target": str(TARGET),
        "backup": str(backup),
        "changed_rows": changed_rows,
        "mutation_counts": dict(sorted(mutation_counts.items())),
        "sample_transformations": samples[:25],
        "status": "PASS" if changed_rows else "NO_CHANGES",
        "rules": [
            "Strip leading Hunt: CODE labels when they leak into hunt_name.",
            "Remove obvious species/program prefixes from hunt_name.",
            "Strip trailing CWMU from CWMU hunt rows.",
            "Strip trailing weapon suffixes like Any Legal Weapon, Archery, Muzzleloader, Rifle, and Shotgun.",
            "Preserve raw_hunt_name and other fields unchanged.",
        ],
    }
    (AUDIT / "2019_hunt_name_cleanup_status.json").write_text(json.dumps(status, indent=2), encoding="utf-8")
    print(json.dumps(status, indent=2))


if __name__ == "__main__":
    main()
