"""Apply confirmed remaining 2026 permit values to DATABASE.csv.

Scope approved by user:
- DA disagreement rows use current recommended values.
- Pronghorn Doe rows use PRONGHORN DOE.csv where it agrees with recommended.
- EA1176 explicit value: 45 / 5 / 50.
- EB1000 explicit total: 1.

This leaves all other disagreements untouched.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
PRONGHORN_DOE = Path(r"C:\Users\tyler\Desktop\BIBLE HUNT CODES\PRONGHORN DOE.csv")

OUT_PATCH = ROOT / "processed_data/audits/confirmed_remaining_permit_values_database_patch_2026.csv"
OUT_PRONGHORN_AUDIT = ROOT / "processed_data/audits/pronghorn_doe_csv_vs_recommended_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/confirmed_remaining_permit_values_database_patch_2026_summary.json"
OUT_DOC = ROOT / "docs/confirmed_remaining_permit_values_database_patch_2026.md"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


def triple(res: object, nr: object, total: object) -> tuple[str, str, str]:
    r = int_text(res)
    n = int_text(nr)
    t = int_text(total)
    if not t and (r or n):
        t = str(int(r or 0) + int(n or 0))
    return r, n, t


def compare(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    if not any(left) and not any(right):
        return "BOTH_BLANK"
    if not any(left):
        return "LEFT_BLANK"
    if not any(right):
        return "RIGHT_BLANK"
    if left == right:
        return "EXACT_MATCH"
    if left[2] and right[2] and left[2] == right[2]:
        return "TOTAL_MATCH_ONLY"
    return "DIFFERS"


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def backup_database() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = ROOT / "processed_data/backups" / f"DATABASE_before_confirmed_remaining_permit_patch_{stamp}.csv"
    backup.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(DATABASE, backup)
    return backup


def parse_pronghorn_doe() -> dict[str, dict[str, str]]:
    source_rows, _ = read_csv(PRONGHORN_DOE)
    parsed: dict[str, dict[str, str]] = {}
    current: dict[str, str] | None = None
    for row in source_rows:
        possible_code = clean(row.get("hunt_name")).upper()
        possible_name = clean(row.get("hunt_code"))
        if re.fullmatch(r"PD\d{4}", possible_code):
            if current:
                current["res"], current["nr"], current["total"] = triple(
                    current.get("res"), current.get("nr"), current.get("total")
                )
                parsed[current["hunt_code"]] = current
            current = {
                "hunt_code": possible_code,
                "hunt_name": possible_name,
                "sex_type": clean(row.get("SEX")),
                "species": clean(row.get("SPECIES")),
                "weapon": clean(row.get("WEAPON")),
                "hunt_type": clean(row.get("HUNT TYPE")),
                "season": clean(row.get("SEASON")),
                "res": int_text(row.get("PERMITS RES")),
                "nr": int_text(row.get("PERMITS NR")),
                "total": int_text(row.get("PERMITS TOTAL")),
            }
        elif current:
            nr = int_text(row.get("PERMITS RES")) or int_text(row.get("PERMITS NR"))
            if nr and not current.get("nr"):
                current["nr"] = nr
            total = int_text(row.get("PERMITS TOTAL"))
            if total and not current.get("total"):
                current["total"] = total
    if current:
        current["res"], current["nr"], current["total"] = triple(
            current.get("res"), current.get("nr"), current.get("total")
        )
        parsed[current["hunt_code"]] = current
    return parsed


def main() -> int:
    db_rows, db_fields = read_csv(DATABASE)
    recon_rows, _ = read_csv(RECON)
    recon_by_code = {clean(row.get("hunt_code")).upper(): row for row in recon_rows if clean(row.get("hunt_code"))}
    db_by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows if clean(row.get("hunt_code"))}
    pronghorn_by_code = parse_pronghorn_doe()
    backup = backup_database()

    patch_specs: dict[str, dict[str, object]] = {}

    for code in ["DA1009", "DA1018", "DA1033"]:
        recon = recon_by_code[code]
        values = triple(recon.get("recommended_res"), recon.get("recommended_nr"), recon.get("recommended_total"))
        patch_specs[code] = {
            "values": values,
            "source": "USER_CONFIRMED_DA_RECOMMENDED_VALUES",
            "source_file": RECON.relative_to(ROOT).as_posix(),
            "status": "RECONCILED_2026_DA_RECOMMENDED_USER_CONFIRMED",
            "notes": "User confirmed DA codes matched recommended values.",
        }

    pronghorn_audit: list[dict[str, object]] = []
    for code, source in sorted(pronghorn_by_code.items()):
        recon = recon_by_code.get(code, {})
        db = db_by_code.get(code, {})
        source_values = triple(source.get("res"), source.get("nr"), source.get("total"))
        rec_values = triple(recon.get("recommended_res"), recon.get("recommended_nr"), recon.get("recommended_total"))
        db_values = triple(
            db.get("permit_allotment_2026_res"),
            db.get("permit_allotment_2026_nr"),
            db.get("permit_allotment_2026_total"),
        )
        source_vs_recommended = compare(source_values, rec_values)
        source_vs_database = compare(source_values, db_values)
        pronghorn_audit.append(
            {
                "hunt_code": code,
                "source_hunt_name": source.get("hunt_name", ""),
                "database_hunt_name": clean(db.get("hunt_name")),
                "source_res": source_values[0],
                "source_nr": source_values[1],
                "source_total": source_values[2],
                "recommended_res": rec_values[0],
                "recommended_nr": rec_values[1],
                "recommended_total": rec_values[2],
                "database_res": db_values[0],
                "database_nr": db_values[1],
                "database_total": db_values[2],
                "source_vs_recommended": source_vs_recommended,
                "source_vs_database": source_vs_database,
                "database_alignment": clean(recon.get("database_alignment")),
                "winner_source": clean(recon.get("winner_source")),
            }
        )
        if (
            source_vs_recommended == "EXACT_MATCH"
            and source_vs_database == "DIFFERS"
            and clean(recon.get("database_alignment")) == "DATABASE_DIFFERS_FROM_RECOMMENDED"
        ):
            patch_specs[code] = {
                "values": source_values,
                "source": "PRONGHORN_DOE_CSV_CONFIRMED_RECOMMENDED",
                "source_file": str(PRONGHORN_DOE),
                "status": "RECONCILED_2026_PRONGHORN_DOE_SOURCE_CONFIRMED",
                "notes": "PRONGHORN DOE.csv exactly matched recommended and differed from DATABASE.",
            }

    patch_specs["EA1176"] = {
        "values": ("45", "5", "50"),
        "source": "USER_CONFIRMED_EA1176_VALUE",
        "source_file": "user message 2026-06-04",
        "status": "RECONCILED_2026_USER_CONFIRMED_EA1176",
        "notes": "User supplied EA1176 as 45 / 5 / 50.",
    }
    patch_specs["EB1000"] = {
        "values": ("", "", "1"),
        "source": "USER_CONFIRMED_EB1000_TEXT_EXTRACTION_FIX",
        "source_file": "user message 2026-06-04",
        "status": "RECONCILED_2026_USER_CONFIRMED_EB1000_TOTAL_ONLY",
        "notes": "User confirmed EB1000 is one permit and prior 15 indicated poor text extraction or column alignment.",
    }

    patch_rows: list[dict[str, object]] = []
    missing = sorted(set(patch_specs) - set(db_by_code))
    if missing:
        raise RuntimeError(f"Patch codes missing from DATABASE.csv: {missing}")

    for code, spec in sorted(patch_specs.items()):
        row = db_by_code[code]
        before = triple(
            row.get("permit_allotment_2026_res"),
            row.get("permit_allotment_2026_nr"),
            row.get("permit_allotment_2026_total"),
        )
        values = spec["values"]
        assert isinstance(values, tuple)
        row["permit_allotment_2026_res"] = values[0]
        row["permit_allotment_2026_nr"] = values[1]
        row["permit_allotment_2026_total"] = values[2]
        row["permit_allotment_2026_source"] = str(spec["source"])
        row["permit_allotment_2026_source_file"] = str(spec["source_file"])
        row["permit_allotment_2026_status"] = str(spec["status"])
        patch_rows.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "before_res": before[0],
                "before_nr": before[1],
                "before_total": before[2],
                "after_res": values[0],
                "after_nr": values[1],
                "after_total": values[2],
                "source": spec["source"],
                "source_file": spec["source_file"],
                "status": spec["status"],
                "notes": spec["notes"],
            }
        )

    with DATABASE.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=db_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(db_rows)

    patch_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "before_res",
        "before_nr",
        "before_total",
        "after_res",
        "after_nr",
        "after_total",
        "source",
        "source_file",
        "status",
        "notes",
    ]
    pronghorn_fields = [
        "hunt_code",
        "source_hunt_name",
        "database_hunt_name",
        "source_res",
        "source_nr",
        "source_total",
        "recommended_res",
        "recommended_nr",
        "recommended_total",
        "database_res",
        "database_nr",
        "database_total",
        "source_vs_recommended",
        "source_vs_database",
        "database_alignment",
        "winner_source",
    ]
    write_csv(OUT_PATCH, patch_rows, patch_fields)
    write_csv(OUT_PRONGHORN_AUDIT, pronghorn_audit, pronghorn_fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "backup_path": backup.relative_to(ROOT).as_posix(),
        "updated_database_rows": len(patch_rows),
        "updated_codes": [row["hunt_code"] for row in patch_rows],
        "updated_species_counts": dict(sorted(Counter(row["species"] for row in patch_rows).items())),
        "pronghorn_source_rows": len(pronghorn_audit),
        "pronghorn_source_vs_recommended_counts": dict(
            sorted(Counter(row["source_vs_recommended"] for row in pronghorn_audit).items())
        ),
        "pronghorn_source_vs_database_counts": dict(
            sorted(Counter(row["source_vs_database"] for row in pronghorn_audit).items())
        ),
        "outputs": {
            "patch_csv": OUT_PATCH.relative_to(ROOT).as_posix(),
            "pronghorn_audit_csv": OUT_PRONGHORN_AUDIT.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Applied only user-confirmed DA, EA1176, EB1000 and PRONGHORN DOE.csv-confirmed values.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Confirmed Remaining Permit Values DATABASE Patch 2026",
        "",
        "## Scope",
        "",
        "Applied user-confirmed DA values, PRONGHORN DOE.csv-confirmed Pronghorn Doe values, and explicit EA1176 / EB1000 corrections.",
        "",
        "## Counts",
        "",
        f"- DATABASE rows updated: `{len(patch_rows)}`",
        f"- Backup: `{backup.relative_to(ROOT).as_posix()}`",
        "",
        "## Outputs",
        "",
        f"- Patch CSV: `{OUT_PATCH.relative_to(ROOT).as_posix()}`",
        f"- Pronghorn source audit: `{OUT_PRONGHORN_AUDIT.relative_to(ROOT).as_posix()}`",
        f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
    ]
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
