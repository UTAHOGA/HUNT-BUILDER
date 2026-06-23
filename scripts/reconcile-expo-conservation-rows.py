"""Reconcile Expo + Conservation draw-class fields in a target CSV.

Behavior:
- Confirms rows as conservation/expo using DATABASE + conservation match table + text cues.
- Fills missing hunt_code when a confident name/weapon match exists.
- Backfills boundary_id from DATABASE.csv when the hunt_code is known.
- Applies draw-class outputs:
  - Conservation rows: hunt_type="Conservation", hunt_class="<organization(s)>" when available
  - Expo rows: hunt_type="L.E.", hunt_class="expo"

Conservation takes precedence over Expo when both are indicated.
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
    text = re.sub(
        r"\b(BUCK|BULL|COW|DOE|DEER|ELK|MOOSE|BISON|PRONGHORN|SHEEP|GOAT|CONSERVATION|EXPO|PERMIT|HUNT)\b",
        " ",
        text,
    )
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
    if "SHOTGUN" in text and "ARCHERY" in text and "MUZZLELOADER" in text:
        return "ARCHERY MUZZLELOADER SHOTGUN"
    return text


def contains_token(*values: str, token: str) -> bool:
    token_u = token.upper()
    return any(token_u in upper(value) for value in values)


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
    match_path = Path(args.conservation_match_csv)

    if not target_path.exists():
        raise FileNotFoundError(f"Missing target CSV: {target_path}")
    if not database_path.exists():
        raise FileNotFoundError(f"Missing DATABASE CSV: {database_path}")
    if not match_path.exists():
        raise FileNotFoundError(f"Missing conservation match CSV: {match_path}")

    with target_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        target_fields = list(reader.fieldnames or [])
        target_rows = list(reader)

    required_cols = {"hunt_name", "hunt_code", "weapon", "hunt_type", "hunt_class"}
    missing_cols = sorted(col for col in required_cols if col not in target_fields)
    if missing_cols:
        raise ValueError(f"Target CSV missing required columns: {', '.join(missing_cols)}")

    db_rows = load_csv(database_path)
    db_by_code = {upper(row.get("hunt_code")): row for row in db_rows if clean(row.get("hunt_code"))}
    db_by_name_weapon: dict[tuple[str, str], str] = {}
    for row in db_rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        key = (normalize_name(row.get("hunt_name")), normalize_weapon(row.get("weapon")))
        if key[0]:
            db_by_name_weapon.setdefault(key, code)

    match_rows = load_csv(match_path)
    cons_codes: set[str] = set()
    expo_codes: set[str] = set()
    organizations_by_code: dict[str, set[str]] = defaultdict(set)
    for row in match_rows:
        code = upper(row.get("hunt_code"))
        if not code:
            continue
        hay = " ".join(
            [
                clean(row.get("species")),
                clean(row.get("area")),
                clean(row.get("condition")),
                clean(row.get("hunt_name")),
                clean(row.get("database_hunt_type")),
            ]
        ).upper()
        if "CONSERVATION" in hay:
            cons_codes.add(code)
        if "EXPO" in hay:
            expo_codes.add(code)
        orgs = [item.strip() for item in clean(row.get("organizations")).split(";") if item.strip()]
        for org in orgs:
            organizations_by_code[code].add(org)

    changes: list[dict[str, object]] = []
    skip_counts: dict[str, int] = defaultdict(int)
    cons_updates = 0
    expo_updates = 0
    code_fills = 0

    for line_no, row in enumerate(target_rows, start=2):
        before = {
            "hunt_code": clean(row.get("hunt_code")),
            "boundary_id": clean(row.get("boundary_id")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class")),
            "draw_design": clean(row.get("draw_design")),
        }

        hunt_name = clean(row.get("hunt_name"))
        weapon = clean(row.get("weapon"))
        existing_code = upper(row.get("hunt_code"))
        code = existing_code
        code_source = ""

        if not code:
            key = (normalize_name(hunt_name), normalize_weapon(weapon))
            mapped = db_by_name_weapon.get(key, "")
            if mapped:
                code = mapped
                code_source = "name_weapon_match_to_database"

        db_row = db_by_code.get(code) if code else None
        db_name = clean(db_row.get("hunt_name")) if db_row else ""
        db_hunt_type = clean(db_row.get("hunt_type")) if db_row else ""
        db_hunt_class = clean(db_row.get("hunt_class")) if db_row else ""
        db_boundary_id = clean(db_row.get("boundary_id")) if db_row else ""

        is_conservation = (
            (code in cons_codes)
            or contains_token(hunt_name, row.get("hunt_type"), row.get("hunt_class"), token="conservation")
            or contains_token(db_name, db_hunt_type, db_hunt_class, token="conservation")
        )
        is_expo = (
            (code in expo_codes)
            or contains_token(hunt_name, row.get("hunt_type"), row.get("hunt_class"), token="expo")
            or contains_token(db_name, db_hunt_type, db_hunt_class, token="expo")
        )

        if not is_conservation and not is_expo:
            skip_counts["not_expo_or_conservation"] += 1
            continue

        if code and not clean(row.get("hunt_code")):
            row["hunt_code"] = code
            code_fills += 1
        if db_boundary_id:
            set_if_present(row, target_fields, "boundary_id", db_boundary_id)

        if is_conservation:
            row["hunt_type"] = "Conservation"
            orgs = sorted(organizations_by_code.get(code, set())) if code else []
            if orgs:
                row["hunt_class"] = ";".join(orgs)
            set_if_present(row, target_fields, "draw_design", "Organization")
            cons_updates += 1
        elif is_expo:
            row["hunt_type"] = "L.E."
            row["hunt_class"] = "expo"
            set_if_present(row, target_fields, "draw_design", "Expo")
            expo_updates += 1

        after = {
            "hunt_code": clean(row.get("hunt_code")),
            "boundary_id": clean(row.get("boundary_id")),
            "hunt_type": clean(row.get("hunt_type")),
            "hunt_class": clean(row.get("hunt_class")),
            "draw_design": clean(row.get("draw_design")),
        }
        if before != after:
            changes.append(
                {
                    "line": line_no,
                    "hunt_name": hunt_name,
                    "source_code": code,
                    "code_source": code_source,
                    "resolved_as": "conservation" if is_conservation else "expo",
                    "before": before,
                    "after": after,
                }
            )

    backup_file = ""
    if args.write and changes:
        stamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        backup = target_path.with_name(f"{target_path.stem}.backup_expo_conservation_{stamp}{target_path.suffix}")
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
        "conservation_match_csv": str(match_path),
        "rows_checked": len(target_rows),
        "changes": len(changes),
        "conservation_rows_touched": cons_updates,
        "expo_rows_touched": expo_updates,
        "hunt_codes_filled": code_fills,
        "skip_counts": dict(skip_counts),
        "backup_file": backup_file,
        "sample_changes": changes[:40],
    }
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
