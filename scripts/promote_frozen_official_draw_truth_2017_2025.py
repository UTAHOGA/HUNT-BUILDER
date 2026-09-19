#!/usr/bin/env python3
"""Promote the reviewed official-PDF yearly draw truth freezes.

The source files are immutable audit artifacts.  This command verifies each
freeze manifest, records the current canonical hashes, creates byte-for-byte
rollback copies, and atomically replaces only the selected yearly canonicals.
It intentionally leaves the already promoted 2020 canonical and the 2026
endpoint canonical untouched.  Rebuilding ``draw_results_long.csv`` is a
separate explicit step.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REBUILD_ROOT = (
    ROOT
    / "audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909"
)
CANONICAL_ROOT = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly"
PROMOTION_ROOT = REBUILD_ROOT / "canonical_promotion_20260919"

FREEZES = {
    2017: "2017/frozen_v3_complete_draw_year_rule",
    2018: "2018/frozen_bear_pursuit_repaired",
    2019: "2019/frozen_bear_pursuit_repaired",
    2021: "2021/frozen",
    2022: "2022/frozen",
    2023: "2023/frozen",
    2024: "2024/frozen",
    2025: "2025/frozen",
}

EXPECTED_STATUS = "FROZEN_ISOLATED_SOURCE_TRUTH_READY_FOR_NEXT_YEAR_NOT_PROMOTED"
REQUIRED_COLUMNS = {
    "actual_draw_year",
    "model_target_year",
    "hunt_code",
    "residency",
    "points",
    "eligible_applicants",
    "total_permits",
    "p_draw",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def inspect_freeze(year: int, freeze_dir: str) -> dict[str, object]:
    manifest_path = REBUILD_ROOT / freeze_dir / "SOURCE_TRUTH_FREEZE_MANIFEST.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    candidate = ROOT / manifest["frozen_candidate"]["path"]
    destination = (
        CANONICAL_ROOT
        / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    )

    if manifest.get("status") != EXPECTED_STATUS:
        raise ValueError(f"Unexpected freeze status for {year}: {manifest.get('status')}")
    if int(manifest.get("draw_year", -1)) != year:
        raise ValueError(f"Freeze draw year mismatch for {year}")
    if int(manifest.get("model_target_year", -1)) != year + 1:
        raise ValueError(f"Freeze model target year mismatch for {year}")
    if not candidate.is_file() or not destination.is_file():
        raise FileNotFoundError(f"Missing candidate or destination for {year}")

    candidate_hash = sha256(candidate)
    if candidate_hash != manifest["frozen_candidate"]["sha256"]:
        raise ValueError(f"Frozen candidate hash mismatch for {year}")
    if candidate.stat().st_size != int(manifest["frozen_candidate"]["bytes"]):
        raise ValueError(f"Frozen candidate size mismatch for {year}")

    row_count = 0
    draw_years: set[str] = set()
    target_years: set[str] = set()
    with candidate.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or ())
        missing = sorted(REQUIRED_COLUMNS - fields)
        if missing:
            raise ValueError(f"Frozen candidate {year} is missing columns: {missing}")
        for row in reader:
            row_count += 1
            draw_years.add(str(row.get("actual_draw_year") or "").strip())
            target_years.add(str(row.get("model_target_year") or "").strip())

    if row_count != int(manifest.get("candidate_rows", -1)):
        raise ValueError(f"Frozen candidate row count mismatch for {year}")
    if draw_years != {str(year)} or target_years != {str(year + 1)}:
        raise ValueError(
            f"Frozen candidate year fields mismatch for {year}: "
            f"actual={sorted(draw_years)} target={sorted(target_years)}"
        )

    return {
        "draw_year": year,
        "model_target_year": year + 1,
        "freeze_manifest": rel(manifest_path),
        "freeze_manifest_sha256": sha256(manifest_path),
        "candidate": rel(candidate),
        "candidate_sha256": candidate_hash,
        "candidate_bytes": candidate.stat().st_size,
        "candidate_rows": row_count,
        "destination": rel(destination),
        "prior_destination_sha256": sha256(destination),
        "prior_destination_bytes": destination.stat().st_size,
        "already_promoted": sha256(destination) == candidate_hash,
        "candidate_path": candidate,
        "destination_path": destination,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    records = [inspect_freeze(year, directory) for year, directory in FREEZES.items()]

    backup_dir = PROMOTION_ROOT / "backups" / stamp
    if args.apply:
        backup_dir.mkdir(parents=True, exist_ok=False)
        for record in records:
            candidate = record.pop("candidate_path")
            destination = record.pop("destination_path")
            backup = backup_dir / destination.name
            shutil.copy2(destination, backup)
            if sha256(backup) != record["prior_destination_sha256"]:
                raise ValueError(f"Rollback backup hash mismatch for {destination.name}")

            temporary = destination.with_suffix(destination.suffix + ".promotion-tmp")
            shutil.copy2(candidate, temporary)
            if sha256(temporary) != record["candidate_sha256"]:
                temporary.unlink(missing_ok=True)
                raise ValueError(f"Promotion temporary hash mismatch for {destination.name}")
            temporary.replace(destination)
            if sha256(destination) != record["candidate_sha256"]:
                raise ValueError(f"Promoted canonical hash mismatch for {destination.name}")
            record["rollback_backup"] = rel(backup)
            record["promoted_destination_sha256"] = sha256(destination)
            record["promotion_status"] = "PROMOTED_VERIFIED_OFFICIAL_PDF_FREEZE"
    else:
        for record in records:
            record.pop("candidate_path")
            record.pop("destination_path")
            record["promotion_status"] = "DRY_RUN_VERIFIED_READY"

    summary = {
        "generated_at_utc": generated_at,
        "status": "PASS_PROMOTED" if args.apply else "PASS_READY_TO_PROMOTE",
        "scope": "reviewed official Utah DWR draw-result PDF truth for 2017-2019 and 2021-2025",
        "excluded_years": {
            "2020": "already promoted through the dedicated 2020 source workflow",
            "2026": "current endpoint truth; not part of the historical replacement",
        },
        "canonical_years_promoted": sorted(FREEZES),
        "canonical_count": len(records),
        "draw_results_long_changed": False,
        "prediction_runtime_changed": False,
        "hosted_action": "NONE",
        "records": records,
    }
    PROMOTION_ROOT.mkdir(parents=True, exist_ok=True)
    report = PROMOTION_ROOT / (
        "OFFICIAL_DRAW_TRUTH_PROMOTION_MANIFEST.json"
        if args.apply
        else "OFFICIAL_DRAW_TRUTH_PROMOTION_DRY_RUN.json"
    )
    report.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
