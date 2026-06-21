from __future__ import annotations

import csv
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import re


REPO = Path(__file__).resolve().parents[1]
TARGET = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "draw_results_2021_for_2022_candidate_promotion_file_records.csv"
)
CANONICAL_YEARLY = (
    REPO
    / "data_truth"
    / "draw_results_truth"
    / "normalized"
    / "canonical_yearly"
    / "draw_results_2021_for_2022_canonical_yearly_draw_results.csv"
)
AUDIT_DIR = (
    REPO
    / "audits"
    / "truth_cross_year"
    / "final_yearly_canonical_audit"
    / "2021_for_2022"
    / "hunt_name_cleanup"
)
BACKUPS = AUDIT_DIR / "backups"


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

WEAPON_SUFFIXES = [
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
]

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


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize_whitespace(text: object) -> str:
    return re.sub(r"\s+", " ", clean(text))


def normalize_punctuation(text: str) -> str:
    return re.sub(r"\s*,\s*", ", ", text).replace(" / ", "/")


def compact_text(text: str) -> str:
    return re.sub(r"[^a-z]", "", clean(text).lower())


def split_unit_segments(text: str) -> list[str]:
    return [segment.strip() for segment in re.split(r"\s+-\s*|\s*-\s+", text) if segment.strip()]


def is_weaponish(text: str) -> bool:
    compact = compact_text(text)
    return any(
        compact == compact_text(suffix) or compact.endswith(compact_text(suffix))
        for suffix in WEAPON_SUFFIXES
    )


def is_species_lead(text: str) -> bool:
    return bool(re.match(r"^Any\s+(?:Bull|Buck|Antlerless|Cow|Doe|Ram)\b", clean(text), re.I))


def clean_hunt_name(value: object, row: dict[str, str] | None = None) -> str:
    row = row or {}
    text = normalize_punctuation(normalize_whitespace(value))

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
            prefix_regex = re.compile(rf"^{re.escape(prefix)}(?:\s*-\s*|\s+)?", re.I)
            next_text = prefix_regex.sub("", text).strip()
            if next_text != text:
                text = next_text
                changed = True

        next_text = TRAILING_DESCRIPTOR_RE.sub("", text).strip()
        if next_text != text:
            text = next_text
            changed = True

        if clean(row.get("hunt_type")).upper() == "CWMU" and re.search(r"\bCWMU\b$", text, re.I):
            text = re.sub(r"\s*CWMU\s*$", "", text, flags=re.I).strip()
            changed = True

        suffix_match = re.match(r"^(.*?)(?:\s*-\s*)([^-]+?)\s*$", text)
        if suffix_match:
            head = suffix_match.group(1).strip()
            tail = suffix_match.group(2).strip()
            compact_tail = compact_text(tail)
            weaponish = any(
                compact_tail == compact_text(suffix) or compact_tail.find(compact_text(suffix)) >= 0
                for suffix in WEAPON_SUFFIXES
            )
            if weaponish:
                text = head
                changed = True

        if re.search(r"\s{2,}", text):
            text = re.sub(r"\s{2,}", " ", text).strip()
            changed = True

    return re.sub(r"\s+", " ", text).replace(" ,", ", ").strip()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = [{key: clean(value) for key, value in row.items()} for row in reader]
    return fields, rows


def write_rows(path: Path, fieldnames: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup(path: Path, label: str, tag: str) -> Path:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    target = BACKUPS / f"{path.stem}.{label}.{tag}{path.suffix}"
    shutil.copy2(path, target)
    return target


def main() -> None:
    tag = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUPS.mkdir(parents=True, exist_ok=True)

    candidate_fields, candidate_rows = read_rows(TARGET)
    canonical_fields, canonical_rows = read_rows(CANONICAL_YEARLY)

    backups = {
        "candidate": str(backup(TARGET, "before_2021_hunt_name_cleanup", tag)),
        "canonical_yearly": str(backup(CANONICAL_YEARLY, "before_2021_hunt_name_cleanup", tag)),
    }

    changed_rows = 0
    changed_by_row_type: Counter[str] = Counter()
    changed_by_record_type: Counter[str] = Counter()
    samples: list[dict[str, str]] = []

    for row in candidate_rows:
        if clean(row.get("actual_draw_year") or row.get("year")) != "2021":
            continue
        old_name = clean(row.get("hunt_name"))
        new_name = clean_hunt_name(old_name, row)
        if new_name == old_name:
            continue
        row["hunt_name"] = new_name
        changed_rows += 1
        changed_by_row_type[clean(row.get("row_type")) or "(blank)"] += 1
        changed_by_record_type[clean(row.get("record_type")) or "(blank)"] += 1
        if len(samples) < 50:
            samples.append(
                {
                    "source_file": clean(row.get("source_file")),
                    "hunt_code": clean(row.get("hunt_code")).upper(),
                    "row_type": clean(row.get("row_type")),
                    "record_type": clean(row.get("record_type")),
                    "before": old_name,
                    "after": new_name,
                }
            )

    canonical_changed = 0
    for row in canonical_rows:
        if clean(row.get("actual_draw_year") or row.get("year")) != "2021":
            continue
        old_name = clean(row.get("hunt_name"))
        new_name = clean_hunt_name(old_name, row)
        if new_name == old_name:
            continue
        row["hunt_name"] = new_name
        canonical_changed += 1

    write_rows(TARGET, candidate_fields, candidate_rows)
    write_rows(CANONICAL_YEARLY, canonical_fields, canonical_rows)

    report = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "target_candidate": str(TARGET.relative_to(REPO)).replace("\\", "/"),
        "target_canonical_yearly": str(CANONICAL_YEARLY.relative_to(REPO)).replace("\\", "/"),
        "backups": backups,
        "candidate_rows_changed": changed_rows,
        "canonical_yearly_rows_changed": canonical_changed,
        "changed_by_row_type": dict(sorted(changed_by_row_type.items())),
        "changed_by_record_type": dict(sorted(changed_by_record_type.items())),
        "sample_changes": samples,
        "notes": [
            "Applied the hunt_name cleanup logic to every 2021 row so the feeder and canonical yearly CSVs agree.",
            "Preserved all non-hunt_name columns and row order.",
        ],
    }
    (AUDIT_DIR / "2021_hunt_name_cleanup_report.json").write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
