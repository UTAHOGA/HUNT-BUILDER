#!/usr/bin/env python3
"""Build a non-promoting 2017 Black Bear truth extension for audit folds.

The normal normalized truth series begins with the 2018 physical draw year.
This utility reuses the source-only 2017 PDF reconstruction and appends only
its explicit Black Bear hunt-level residency ladders to a *new audit file*.
It never modifies canonical yearly files, normalized truth, DATABASE.csv, or
runtime artifacts.

The purpose is deliberately narrow: let the existing all-family engine inspect
the 2017 Bear ladder as historical evidence while an adjacent-year audit is
running.  A statewide 2017 Bear point-purchase table is not substituted or
invented here; DWR did not retain one in its 2017 archive.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = (
    REPO
    / "audits"
    / "2017_blind_source_truth_20260905"
    / "official_2017_pdf_reconstructed_source_truth.csv"
)
DEFAULT_LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-2017", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--active-long", type=Path, default=DEFAULT_LONG)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()

    if not args.source_2017.exists():
        raise FileNotFoundError(f"Missing source-only 2017 reconstruction: {args.source_2017}")
    if not args.active_long.exists():
        raise FileNotFoundError(f"Missing active normalized truth: {args.active_long}")

    long_header, active_rows = read_rows(args.active_long)
    source_header, source_rows = read_rows(args.source_2017)
    if any(row.get("actual_draw_year") == "2017" for row in active_rows):
        raise ValueError("Active normalized truth already contains 2017 rows; refusing to duplicate them")
    required_source = {"actual_draw_year", "source_scope", "hunt_code", "residency", "points", "source_file"}
    if not required_source.issubset(source_header):
        raise ValueError(f"2017 source reconstruction lacks required fields: {sorted(required_source - set(source_header))}")

    bear_rows = [
        row
        for row in source_rows
        if row.get("actual_draw_year") == "2017"
        and row.get("source_scope") == "BLACK_BEAR"
        and row.get("hunt_code", "").startswith("BR")
        and row.get("residency") in {"Resident", "Nonresident"}
        and row.get("record_type") == "point_level_draw_result"
    ]
    if len(bear_rows) != 3600:
        raise ValueError(f"Expected 3,600 explicit 2017 Black Bear lane rows; found {len(bear_rows)}")
    lane_keys = {(row["hunt_code"], row["residency"], row["points"]) for row in bear_rows}
    if len(lane_keys) != len(bear_rows):
        raise ValueError("2017 Black Bear source contains duplicate hunt/residency/point lanes")
    if len({row["hunt_code"] for row in bear_rows}) != 90:
        raise ValueError("2017 Black Bear source does not contain the expected 90 official hunt codes")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    output = args.out_dir / "draw_results_long_with_2017_black_bear_audit_only.csv"
    manifest_path = args.out_dir / "2017_black_bear_audit_truth_manifest.json"
    if output.exists() or manifest_path.exists():
        raise FileExistsError(f"Refusing to overwrite existing audit output: {args.out_dir}")

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=long_header, lineterminator="\n", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(bear_rows)
        writer.writerows(active_rows)

    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASS_AUDIT_ONLY_2017_BEAR_EXTENSION",
        "purpose": "source_only_2017_to_2018_and_2018_to_2019_bear_history_audit",
        "non_promotion_boundary": {
            "canonical_yearly_files_modified": False,
            "normalized_truth_modified": False,
            "database_csv_modified": False,
            "runtime_artifacts_modified": False,
        },
        "inputs": {
            "source_2017": str(args.source_2017.relative_to(REPO)).replace("\\", "/"),
            "source_2017_sha256": sha256(args.source_2017),
            "active_long": str(args.active_long.relative_to(REPO)).replace("\\", "/"),
            "active_long_sha256": sha256(args.active_long),
        },
        "black_bear_source": {
            "rows": len(bear_rows),
            "hunt_codes": len({row["hunt_code"] for row in bear_rows}),
            "lane_identity": "hunt_code + residency + points",
            "official_source_files": sorted({row["source_file"] for row in bear_rows}),
        },
        "point_purchase_boundary": {
            "statewide_2017_point_purchase_table_retained": False,
            "substitute_or_inferred_rows_added": False,
            "reason": "DWR 2017 Black Bear archive exposes hunt-level draw results but no standalone statewide point-purchase report.",
        },
        "output": {
            "path": output.name,
            "rows": len(active_rows) + len(bear_rows),
            "sha256": sha256(output),
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
