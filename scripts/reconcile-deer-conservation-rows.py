"""Reconcile deer conservation rows into a target CSV.

For rows that can be confirmed as conservation permits, this script:
- sets hunt_type to "Conservation"
- sets hunt_class to organization code(s) when available
- fills hunt_code when missing and a confident match exists
- backfills boundary_id from DATABASE.csv when a hunt_code is known

Confirmation sources:
1) 2026 deer buck conservation CSV (direct hunt_code list)
2) conservation permits database-match CSV (deer rows with hunt_code + conservation database type)
3) DATABASE.csv cross-check for hunt_code validity and conservation context
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path


def clean(value: object) -> str:
    return str(value or "").strip()


def upper(value: object) -> str:
    return clean(value).upper()


def normalize_name(value: object) -> str:
    text = upper(value)
    text = re.sub(r"\(.*?\)", " ", text)
    text = re.sub(r"[^A-Z0-9]+", " ", text)
    text = re.sub(r"\b(BUCK|DEER|CONSERVATION|EXPO|PERMIT)\b", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_weapon(value: object) -> str:
    text = upper(value)
    if "ARCH" in text:
        return "ARCHERY"
    if "MUZZ" in text:
        return "MUZZLELOADER"
    if "ANY LEGAL" in text or text == "ALW":
        return "ANY LEGAL WEAPON"
    if "MULTI" in text:
        return "MULTISEASON"
    return text


def set_if_present(row: dict[str, str], fieldnames: list[str], key: str, value: object) -> bool:
    if key not in fieldnames:
        return False
    text = clean(value)
    if row.get(key) == text:
        return False
    row[key] = text
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-csv", required=True, help="Target CSV path to update.")
    parser.add_argument(
        "--database-csv",
        default="pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv",
        help="Canonical DATABASE.csv path.",
    )
    parser.add_argument(
        "--deer-conservation-csv",
        default="pipeline/RAW/hunt_unit_database/2026/csv/2026_deer_buck_conservation.csv",
        help="Direct deer conservation hunt rows.",
    )
    parser.add_argument(
        "--conservation-match-csv",
        default="pipeline/RAW/hunt_unit_database/2026/reports/conservation_permits_2025_2027_database_match.csv",
        help="Conservation table to database match output.",
    )
    parser.add_argument("--write", action="store_true", help="Write changes to target CSV.")
    return parser.parse_args()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    args = parse_args()
    target_path = Path(args.target_csv)
    database_path = Path(args.database_csv)
    deer_cons_path = Path(args.deer_conservation_csv)
    match_path = Path(args.conservation_match_csv)

    if not target_path.exists():
        raise FileNotFoundError(f"Missing target CSV: {target_path}")
    if not database_path.exists():
        raise FileNotFoundError(f"Missing DATABASE CSV: {database_path}")
    if not deer_cons_path.exists():
        raise FileNotFoundError(f"Missing deer conservation CSV: {deer_cons_path}")
    if not match_path.exists():
        raise FileNotFoundError(f"Missing conservation match CSV: {match_path}")

    with target_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        target_fields = list(reader.fieldnames or [])
        target_rows = list(reader)

    db_rows = load_csv(database_path)
    db_by_code = {upper(row.get("hunt_code")): row for row in db_rows if clean(row.get("hunt_code"))}

    deer_cons_rows = load_csv(deer_cons_path)
    deer_cons_codes = {upper(row.get("hunt_code")) for row in deer_cons_rows if clean(row.get("hunt_code"))}
    deer_cons_by_name_weapon: dict[tuple[str, str], str] = {}
    for row in deer_cons_rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        key = (normalize_name(row.get("hunt_name")), normalize_weapon(row.get("weapon")))
        deer_cons_by_name_weapon[key] = code

    match_rows = load_csv(match_path)
    org_by_code: dict[str, set[str]] = defaultdict(set)
    for row in match_rows:
        if upper(row.get("species")) != "DEER":
            continue
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        db_hunt_type = upper(row.get("database_hunt_type"))
        if "CONSERVATION" not in db_hunt_type:
            continue
        organizations = [item.strip() for item in clean(row.get("organizations")).split(";") if item.strip()]
        for org in organizations:
            org_by_code[code].add(org)

    changes = []
    skipped = []

    for index, row in enumerate(target_rows, start=2):
        current_code = upper(row.get("hunt_code"))
        current_name = clean(row.get("hunt_name"))
        current_weapon = clean(row.get("weapon"))

        candidate_code = current_code
        source = ""

        if current_code in deer_cons_codes:
            candidate_code = current_code
            source = "direct_deer_conservation_code"
        else:
            # Only infer a code from name/weapon when hunt_code is missing.
            # This avoids overriding non-conservation rows that share area names.
            if not current_code:
                lookup_key = (normalize_name(current_name), normalize_weapon(current_weapon))
                mapped = deer_cons_by_name_weapon.get(lookup_key, "")
                if mapped:
                    candidate_code = mapped
                    source = "name_weapon_match_to_deer_conservation"

        if not candidate_code:
            continue

        db_row = db_by_code.get(candidate_code)
        if not db_row:
            skipped.append(
                {
                    "line": index,
                    "hunt_name": current_name,
                    "hunt_code": current_code,
                    "candidate_code": candidate_code,
                    "reason": "candidate_code_missing_from_database",
                }
            )
            continue

        db_hunt_type = upper(db_row.get("hunt_type"))
        if "CONSERVATION" not in db_hunt_type and candidate_code not in deer_cons_codes:
            skipped.append(
                {
                    "line": index,
                    "hunt_name": current_name,
                    "hunt_code": current_code,
                    "candidate_code": candidate_code,
                    "reason": "database_hunt_type_not_conservation",
                    "database_hunt_type": clean(db_row.get("hunt_type")),
                }
            )
            continue

        before = {
            "hunt_code": clean(row.get("hunt_code")),
            "boundary_id": clean(row.get("boundary_id")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class")),
        }

        db_boundary_id = clean(db_row.get("boundary_id"))
        if db_boundary_id:
            set_if_present(row, target_fields, "boundary_id", db_boundary_id)

        if not clean(row.get("hunt_code")):
            row["hunt_code"] = candidate_code
        row["hunt_type"] = "Conservation"

        organizations = sorted(org_by_code.get(candidate_code, set()))
        if organizations:
            row["hunt_class"] = ";".join(organizations)

        after = {
            "hunt_code": clean(row.get("hunt_code")),
            "boundary_id": clean(row.get("boundary_id")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class")),
        }

        if before != after:
            changes.append(
                {
                    "line": index,
                    "source": source,
                    "hunt_name": current_name,
                    "candidate_code": candidate_code,
                    "before": before,
                    "after": after,
                }
            )

    backup_file = ""
    if args.write and changes:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup = target_path.with_name(f"{target_path.stem}.backup_conservation_reconcile_{stamp}{target_path.suffix}")
        shutil.copy2(target_path, backup)
        backup_file = str(backup)
        with target_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=target_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(target_rows)

    report = {
        "mode": "write" if args.write else "dry_run",
        "target_csv": str(target_path),
        "database_csv": str(database_path),
        "deer_conservation_csv": str(deer_cons_path),
        "conservation_match_csv": str(match_path),
        "rows_checked": len(target_rows),
        "changes": len(changes),
        "skipped": len(skipped),
        "backup_file": backup_file,
        "sample_changes": changes[:40],
        "sample_skipped": skipped[:20],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
