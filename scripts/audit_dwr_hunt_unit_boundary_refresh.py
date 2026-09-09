#!/usr/bin/env python3
"""Compare a fresh official DWR boundary pull with the working geometry layer."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform


ROOT = Path(__file__).resolve().parents[1]
AREA_CRS = "EPSG:26912"


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def feature_index(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for feature in payload.get("features", []):
        props = feature.get("properties", {})
        boundary_id = clean(props.get("boundary_id") or props.get("BoundaryID"))
        if not boundary_id:
            continue
        if boundary_id in index:
            raise ValueError(f"Duplicate boundary ID {boundary_id}")
        index[boundary_id] = feature
    return index


def valid_projected(feature: dict[str, Any], transformer: Transformer):
    geometry = shape(feature["geometry"])
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    return transform(transformer.transform, geometry)


def sortable_id(value: str) -> tuple[int, str]:
    try:
        return int(value), value
    except ValueError:
        return 10**12, value


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fresh", required=True)
    parser.add_argument("--working", default="data/hunt_units.geojson")
    parser.add_argument("--output-dir", default="")
    args = parser.parse_args()

    fresh_path = Path(args.fresh)
    working_path = Path(args.working)
    if not fresh_path.is_absolute():
        fresh_path = ROOT / fresh_path
    if not working_path.is_absolute():
        working_path = ROOT / working_path
    output_dir = Path(args.output_dir) if args.output_dir else fresh_path.parent
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    fresh = feature_index(read_json(fresh_path))
    working = feature_index(read_json(working_path))
    fresh_ids = set(fresh)
    working_ids = set(working)
    transformer = Transformer.from_crs("EPSG:4326", AREA_CRS, always_xy=True)

    rows: list[dict[str, Any]] = []
    for boundary_id in sorted(fresh_ids | working_ids, key=sortable_id):
        old = working.get(boundary_id)
        new = fresh.get(boundary_id)
        old_props = old.get("properties", {}) if old else {}
        new_props = new.get("properties", {}) if new else {}
        row: dict[str, Any] = {
            "boundary_id": boundary_id,
            "inventory_status": "MATCHED" if old and new else "ADDED_BY_FRESH_DWR" if new else "REMOVED_FROM_DWR",
            "working_name": clean(old_props.get("boundary_name") or old_props.get("Boundary_Name")),
            "fresh_dwr_name": clean(new_props.get("Boundary_Name") or new_props.get("boundary_name")),
            "fresh_dwr_status": clean(new_props.get("Status")),
            "fresh_dwr_boundary_type": clean(new_props.get("BTYPE")),
            "name_changed": False,
            "working_area_sq_m": "",
            "fresh_area_sq_m": "",
            "area_change_percent": "",
            "symmetric_difference_percent_of_fresh": "",
        }
        if old and new:
            row["name_changed"] = row["working_name"] != row["fresh_dwr_name"]
            old_geometry = valid_projected(old, transformer)
            new_geometry = valid_projected(new, transformer)
            old_area = old_geometry.area
            new_area = new_geometry.area
            row["working_area_sq_m"] = round(old_area, 3)
            row["fresh_area_sq_m"] = round(new_area, 3)
            row["area_change_percent"] = round((new_area - old_area) / new_area * 100.0, 6) if new_area else ""
            row["symmetric_difference_percent_of_fresh"] = (
                round(old_geometry.symmetric_difference(new_geometry).area / new_area * 100.0, 6)
                if new_area
                else ""
            )
        rows.append(row)

    csv_path = output_dir / "working_vs_fresh_dwr_boundary_comparison.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    matched = [row for row in rows if row["inventory_status"] == "MATCHED"]
    geometric = [
        float(row["symmetric_difference_percent_of_fresh"])
        for row in matched
        if row["symmetric_difference_percent_of_fresh"] != ""
    ]
    summary = {
        "freshSource": str(fresh_path.relative_to(ROOT)).replace("\\", "/"),
        "freshSourceSha256": sha256(fresh_path),
        "workingSource": str(working_path.relative_to(ROOT)).replace("\\", "/"),
        "workingSourceSha256": sha256(working_path),
        "freshFeatureCount": len(fresh),
        "workingFeatureCount": len(working),
        "matchedBoundaryCount": len(fresh_ids & working_ids),
        "addedBoundaryCount": len(fresh_ids - working_ids),
        "addedBoundaries": [
            {
                "boundaryId": row["boundary_id"],
                "name": row["fresh_dwr_name"],
                "status": row["fresh_dwr_status"],
            }
            for row in rows
            if row["inventory_status"] == "ADDED_BY_FRESH_DWR"
        ],
        "removedBoundaryCount": len(working_ids - fresh_ids),
        "removedBoundaries": [
            {"boundaryId": row["boundary_id"], "name": row["working_name"]}
            for row in rows
            if row["inventory_status"] == "REMOVED_FROM_DWR"
        ],
        "nameChangedCount": sum(bool(row["name_changed"]) for row in matched),
        "nameChanges": [
            {
                "boundaryId": row["boundary_id"],
                "workingName": row["working_name"],
                "freshDwrName": row["fresh_dwr_name"],
            }
            for row in matched
            if row["name_changed"]
        ],
        "geometryComparison": {
            "areaCrs": AREA_CRS,
            "maximumSymmetricDifferencePercentOfFresh": round(max(geometric), 6) if geometric else 0,
            "matchedBoundariesOver0_01Percent": sum(value > 0.01 for value in geometric),
            "matchedBoundariesOver0_1Percent": sum(value > 0.1 for value in geometric),
            "matchedBoundariesOver1Percent": sum(value > 1.0 for value in geometric),
            "note": "Differences include the working layer's deliberate browser-safe simplification.",
        },
        "comparisonCsv": str(csv_path.relative_to(ROOT)).replace("\\", "/"),
    }
    summary_path = output_dir / "working_vs_fresh_dwr_boundary_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
