#!/usr/bin/env python3
"""Apply the narrowly proven 2021 and 2023 canonical draw-truth repairs.

The script is fail-closed. It will not write either canonical unless the known
2021 classification population and the known 2023 duplicate lane both exactly
reconcile to their independently retained official-source counterparts.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_ROOT = (
    REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
)
CANONICAL_2021 = (
    CANONICAL_ROOT / "draw_results_2021_for_2022_canonical_yearly_draw_results.csv"
)
CANONICAL_2023 = (
    CANONICAL_ROOT / "draw_results_2023_for_2024_canonical_yearly_draw_results.csv"
)
DEFAULT_AUDIT_DIR = (
    REPO_ROOT
    / "audits"
    / "source_pdf_revalidation"
    / "dwr_draw_results_2017_2026_20260907"
    / "canonical_repairs"
)

ADULT_2021_SOURCE = "21_deer_odds.pdf"
BAD_2021_SYSTEM = "REFERENCE_ONLY"
BAD_2021_POOL = "youth_general_deer"
GOOD_2021_SYSTEM = "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
GOOD_2021_POOL = "adult_general_deer"
GOOD_2021_DESIGN = "PREFERENCE_GENERAL_SEASON_BUCK_DEER"
GOOD_2021_HUNT_CLASS = "GENERAL_SEASON_DEER"
EXPECTED_2021_ROWS = 483
EXPECTED_2021_CODES = {
    "DB1505",
    "DB1515",
    "DB1520",
    "DB1527",
    "DB1530",
    "DB1532",
    "DB1535",
    "DB1545",
    "DB1548",
    "DB1550",
    "DB1557",
    "DB1558",
    "DB1560",
    "DB1562",
    "DB1565",
    "DB1575",
    "DB1578",
    "DB1580",
    "DB1587",
    "DB1588",
    "DB1590",
}

BAD_2023_SOURCE = "2023_PERMITS=2024_MODEL__YOUTH G.S. DEER DRAW RESULTS.pdf"
GOOD_2023_SOURCES = {
    "2023_PERMITS=2024_MODEL__YOUTH ANTLERLESS DEER DRAW RESULTS.pdf",
    "2023_PERMITS=2024_MODEL__YOUTH ANTLERLESS ELK DRAW RESULTS.pdf",
    "2023_PERMITS=2024_MODEL__YOUTH ANTLERLESS PRONGHORN DRAW RESULTS.pdf",
}
EXPECTED_2023_ROWS = 3_040
EXPECTED_2023_CODES = 190
EXPECTED_2023_PREFIX_COUNTS = Counter({"DA": 320, "EA": 2_432, "PD": 288})
CORE_2023_FIELDS = (
    "hunt_code",
    "points",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "successful_applicants",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise RuntimeError(f"Canonical has no header: {path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def assert_required_fields(fieldnames: list[str], required: Iterable[str], label: str) -> None:
    missing = sorted(set(required) - set(fieldnames))
    if missing:
        raise RuntimeError(f"{label} is missing required fields: {missing}")


def prepare_repairs(audit_dir: Path) -> dict[str, object]:
    fields_2021, rows_2021 = read_csv(CANONICAL_2021)
    fields_2023, rows_2023 = read_csv(CANONICAL_2023)
    assert_required_fields(
        fields_2021,
        (
            "source_file",
            "hunt_code",
            "draw_design",
            "draw_system_type",
            "draw_pool",
            "hunt_class",
        ),
        "2021 canonical",
    )
    assert_required_fields(
        fields_2023,
        ("source_file", *CORE_2023_FIELDS),
        "2023 canonical",
    )

    source_rows_2021 = [row for row in rows_2021 if row["source_file"] == ADULT_2021_SOURCE]
    repair_population_2021 = [
        row
        for row in source_rows_2021
        if row["hunt_code"] in EXPECTED_2021_CODES
    ]
    if len(repair_population_2021) != EXPECTED_2021_ROWS:
        raise RuntimeError(
            f"2021 repair population changed: expected {EXPECTED_2021_ROWS} rows, "
            f"found {len(repair_population_2021)}"
        )
    repair_rows_2021 = [
        row
        for row in repair_population_2021
        if row["draw_design"] != GOOD_2021_DESIGN
        or row["draw_system_type"] != GOOD_2021_SYSTEM
        or row["draw_pool"] != GOOD_2021_POOL
        or row["hunt_class"] != GOOD_2021_HUNT_CLASS
    ]
    if not repair_rows_2021:
        repair_state_2021 = "ALREADY_REPAIRED"
    elif len(repair_rows_2021) == EXPECTED_2021_ROWS:
        repair_state_2021 = "REPAIR_REQUIRED"
    else:
        raise RuntimeError(
            f"2021 repair population is only partially normalized: expected zero or "
            f"{EXPECTED_2021_ROWS} rows requiring repair, found {len(repair_rows_2021)}"
        )
    repair_codes_2021 = {row["hunt_code"] for row in repair_population_2021}
    if repair_codes_2021 != EXPECTED_2021_CODES:
        raise RuntimeError(
            "2021 repair hunt-code set changed: "
            f"missing={sorted(EXPECTED_2021_CODES - repair_codes_2021)} "
            f"unexpected={sorted(repair_codes_2021 - EXPECTED_2021_CODES)}"
        )
    allowed_2021_values = {
        "draw_design": {"REFERENCE_ONLY", GOOD_2021_DESIGN},
        "draw_system_type": {BAD_2021_SYSTEM, GOOD_2021_SYSTEM},
        "draw_pool": {BAD_2021_POOL, GOOD_2021_POOL},
        "hunt_class": {"Youth", GOOD_2021_HUNT_CLASS},
    }
    unexpected_2021 = [
        (row["hunt_code"], field, row[field])
        for row in repair_population_2021
        for field, allowed in allowed_2021_values.items()
        if row[field] not in allowed
    ]
    if unexpected_2021:
        raise RuntimeError(f"2021 repair population has unexpected classifications: {unexpected_2021[:10]}")
    good_siblings_2021 = [
        row
        for row in source_rows_2021
        if row["draw_system_type"] == GOOD_2021_SYSTEM and row["draw_pool"] == GOOD_2021_POOL
    ]
    if not good_siblings_2021:
        raise RuntimeError("2021 adult source has no correctly classified sibling rows")

    repaired_2021: list[dict[str, str]] = []
    change_detail_2021: list[dict[str, str]] = []
    for row_number, row in enumerate(rows_2021, start=2):
        output = dict(row)
        if row in repair_rows_2021:
            output["draw_design"] = GOOD_2021_DESIGN
            output["draw_system_type"] = GOOD_2021_SYSTEM
            output["draw_pool"] = GOOD_2021_POOL
            output["hunt_class"] = GOOD_2021_HUNT_CLASS
            change_detail_2021.append(
                {
                    "canonical_row": str(row_number),
                    "hunt_code": row["hunt_code"],
                    "points": row.get("points", ""),
                    "pdf_page": row.get("pdf_page", ""),
                    "source_file": row["source_file"],
                    "old_draw_design": row["draw_design"],
                    "new_draw_design": output["draw_design"],
                    "old_draw_system_type": row["draw_system_type"],
                    "new_draw_system_type": output["draw_system_type"],
                    "old_draw_pool": row["draw_pool"],
                    "new_draw_pool": output["draw_pool"],
                    "old_hunt_class": row["hunt_class"],
                    "new_hunt_class": output["hunt_class"],
                }
            )
        repaired_2021.append(output)

    bad_rows_2023 = [row for row in rows_2023 if row["source_file"] == BAD_2023_SOURCE]
    good_rows_2023 = [row for row in rows_2023 if row["source_file"] in GOOD_2023_SOURCES]
    if len(bad_rows_2023) == EXPECTED_2023_ROWS:
        repair_state_2023 = "REPAIR_REQUIRED"
        duplicate_evidence_2023 = bad_rows_2023
    elif not bad_rows_2023:
        repair_state_2023 = "ALREADY_REPAIRED"
        removed_evidence = audit_dir / "draw_results_2023_removed_duplicate_rows.csv"
        if not removed_evidence.exists():
            raise RuntimeError(
                "2023 duplicate lane is absent but its retained row-level removal evidence is missing"
            )
        _removed_fields, duplicate_evidence_2023 = read_csv(removed_evidence)
    else:
        raise RuntimeError(
            f"2023 duplicate population changed: expected zero or {EXPECTED_2023_ROWS}, "
            f"found {len(bad_rows_2023)}"
        )
    if len(duplicate_evidence_2023) != EXPECTED_2023_ROWS:
        raise RuntimeError(
            f"2023 duplicate evidence changed: expected {EXPECTED_2023_ROWS}, "
            f"found {len(duplicate_evidence_2023)}"
        )
    if len(good_rows_2023) != EXPECTED_2023_ROWS:
        raise RuntimeError(
            f"2023 correct antlerless population changed: expected {EXPECTED_2023_ROWS}, "
            f"found {len(good_rows_2023)}"
        )
    bad_codes_2023 = {row["hunt_code"] for row in duplicate_evidence_2023}
    good_codes_2023 = {row["hunt_code"] for row in good_rows_2023}
    if len(bad_codes_2023) != EXPECTED_2023_CODES or bad_codes_2023 != good_codes_2023:
        raise RuntimeError(
            "2023 duplicate and correct hunt-code populations do not reconcile: "
            f"bad={len(bad_codes_2023)} good={len(good_codes_2023)}"
        )
    prefix_counts = Counter(row["hunt_code"][:2] for row in duplicate_evidence_2023)
    if prefix_counts != EXPECTED_2023_PREFIX_COUNTS:
        raise RuntimeError(
            f"2023 duplicate prefix population changed: {dict(sorted(prefix_counts.items()))}"
        )
    bad_core = Counter(tuple(row[field] for field in CORE_2023_FIELDS) for row in duplicate_evidence_2023)
    good_core = Counter(tuple(row[field] for field in CORE_2023_FIELDS) for row in good_rows_2023)
    if bad_core != good_core:
        raise RuntimeError(
            "2023 duplicate lane does not exactly reconcile to the retained youth-antlerless lanes: "
            f"bad_only={sum((bad_core - good_core).values())} "
            f"good_only={sum((good_core - bad_core).values())}"
        )
    repaired_2023 = [row for row in rows_2023 if row["source_file"] != BAD_2023_SOURCE]

    return {
        "fields_2021": fields_2021,
        "rows_2021": rows_2021,
        "repaired_2021": repaired_2021,
        "change_detail_2021": change_detail_2021,
        "repair_state_2021": repair_state_2021,
        "fields_2023": fields_2023,
        "rows_2023": rows_2023,
        "repaired_2023": repaired_2023,
        "bad_rows_2023": bad_rows_2023,
        "duplicate_evidence_2023": duplicate_evidence_2023,
        "bad_codes_2023": bad_codes_2023,
        "repair_state_2023": repair_state_2023,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write the guarded canonical repairs.")
    parser.add_argument("--audit-dir", type=Path, default=DEFAULT_AUDIT_DIR)
    args = parser.parse_args()

    audit_dir = args.audit_dir.resolve()
    prepared = prepare_repairs(audit_dir)
    before_2021 = sha256(CANONICAL_2021)
    before_2023 = sha256(CANONICAL_2023)
    manifest: dict[str, object] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "guard_status": "PASS",
        "2021": {
            "canonical": str(CANONICAL_2021.relative_to(REPO_ROOT)),
            "before_sha256": before_2021,
            "before_rows": len(prepared["rows_2021"]),
            "repair_state": prepared["repair_state_2021"],
            "reclassified_rows": EXPECTED_2021_ROWS,
            "affected_hunt_codes": len(EXPECTED_2021_CODES),
            "changed_fields": ["draw_design", "draw_system_type", "draw_pool", "hunt_class"],
        },
        "2023": {
            "canonical": str(CANONICAL_2023.relative_to(REPO_ROOT)),
            "before_sha256": before_2023,
            "before_rows": len(prepared["rows_2023"]),
            "repair_state": prepared["repair_state_2023"],
            "removed_rows": EXPECTED_2023_ROWS,
            "removed_source_file": BAD_2023_SOURCE,
            "affected_hunt_codes": len(prepared["bad_codes_2023"]),
            "reconciliation_fields": list(CORE_2023_FIELDS),
            "reconciliation_status": "EXACT_MULTISET_MATCH",
        },
    }

    if args.apply:
        if (
            prepared["repair_state_2021"] == "ALREADY_REPAIRED"
            and prepared["repair_state_2023"] == "ALREADY_REPAIRED"
        ):
            manifest["mode"] = "apply_noop_already_repaired"
            manifest["2021"]["after_sha256"] = before_2021
            manifest["2021"]["after_rows"] = len(prepared["rows_2021"])
            manifest["2023"]["after_sha256"] = before_2023
            manifest["2023"]["after_rows"] = len(prepared["rows_2023"])
            print(json.dumps(manifest, indent=2))
            return 0
        audit_dir.mkdir(parents=True, exist_ok=True)
        for canonical, before_hash in ((CANONICAL_2021, before_2021), (CANONICAL_2023, before_2023)):
            backup = audit_dir / f"{canonical.stem}.before_repair.csv"
            if backup.exists() and sha256(backup) != before_hash:
                raise RuntimeError(f"Refusing to overwrite nonmatching rollback copy: {backup}")
            if not backup.exists():
                shutil.copy2(canonical, backup)
            if sha256(backup) != before_hash:
                raise RuntimeError(f"Rollback copy did not hash-match its canonical: {backup}")

        temp_2021 = CANONICAL_2021.with_suffix(".csv.repair-tmp")
        temp_2023 = CANONICAL_2023.with_suffix(".csv.repair-tmp")
        write_csv(temp_2021, prepared["fields_2021"], prepared["repaired_2021"])
        write_csv(temp_2023, prepared["fields_2023"], prepared["repaired_2023"])
        os.replace(temp_2021, CANONICAL_2021)
        os.replace(temp_2023, CANONICAL_2023)

        detail_2021 = audit_dir / "draw_results_2021_reclassified_rows.csv"
        write_csv(
            detail_2021,
            list(prepared["change_detail_2021"][0]),
            prepared["change_detail_2021"],
        )
        removed_2023 = audit_dir / "draw_results_2023_removed_duplicate_rows.csv"
        write_csv(removed_2023, prepared["fields_2023"], prepared["duplicate_evidence_2023"])

        manifest["2021"]["after_sha256"] = sha256(CANONICAL_2021)
        manifest["2021"]["after_rows"] = len(prepared["repaired_2021"])
        manifest["2023"]["after_sha256"] = sha256(CANONICAL_2023)
        manifest["2023"]["after_rows"] = len(prepared["repaired_2023"])
        manifest["rollback_copies"] = [
            str(path.relative_to(REPO_ROOT))
            for path in sorted(audit_dir.glob("*.before_repair.csv"))
        ]
        manifest_path = audit_dir / "canonical_repair_manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
