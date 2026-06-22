from __future__ import annotations

import csv
import json
import re
import shutil
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HUNT_UNITS = ROOT / "data" / "hunt_units.geojson"
PUBLIC_CONTRACT = ROOT / "processed_data" / "public_contracts" / "hunt_units.geojson"
PAGES_DATA = ROOT / "pages-dist" / "data" / "hunt_units.geojson"
PAGES_PUBLIC_CONTRACT = ROOT / "pages-dist" / "processed_data" / "public_contracts" / "hunt_units.geojson"
ARCGIS_TABLE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "arcgis" / "udwr_huntnumber_boundary_table1.json"
AUDIT_DIR = ROOT / "audits" / "boundary_runtime"


def norm_name(value: object) -> str:
    text = str(value or "").lower().replace("&", "and")
    text = re.sub(r"\s*-\s*Hunt\s*#.*$", "", text, flags=re.I)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def boundary_id(value: object) -> str:
    return str(value or "").strip()


def load_arcgis() -> tuple[dict[str, list[dict[str, str]]], list[dict[str, str]]]:
    payload = read_json(ARCGIS_TABLE)
    by_boundary: dict[str, list[dict[str, str]]] = defaultdict(list)
    records: list[dict[str, str]] = []
    for feature in payload.get("features", []):
        attrs = feature.get("attributes", {})
        bid = boundary_id(attrs.get("BOUNDARYID"))
        if not bid:
            continue
        record = {
            "HUNT_NUMBER": str(attrs.get("HUNT_NUMBER") or "").strip(),
            "BOUNDARYID": bid,
            "BOUNDARY_NAME": str(attrs.get("BOUNDARY_NAME") or "").strip(),
            "SEASON": str(attrs.get("SEASON") or "").strip(),
        }
        records.append(record)
        by_boundary[bid].append(record)
    return by_boundary, records


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def reconcile(write: bool) -> dict[str, object]:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    hunt_units = read_json(HUNT_UNITS)
    by_boundary, arcgis_records = load_arcgis()

    features = hunt_units.get("features", [])
    geometry_ids = {
        boundary_id((feature.get("properties") or {}).get("boundary_id") or (feature.get("properties") or {}).get("BoundaryID"))
        for feature in features
    }
    geometry_ids.discard("")
    arcgis_ids = set(by_boundary)

    audit_rows: list[dict[str, object]] = []
    changed_features = 0
    arcgis_matched_features = 0
    name_match_features = 0
    name_drift_features = 0

    for feature in features:
        props = feature.setdefault("properties", {})
        bid = boundary_id(props.get("boundary_id") or props.get("BoundaryID"))
        if not bid:
            continue
        records = by_boundary.get(bid, [])
        hunt_numbers = sorted({record["HUNT_NUMBER"] for record in records if record.get("HUNT_NUMBER")})
        arcgis_names = sorted({record["BOUNDARY_NAME"] for record in records if record.get("BOUNDARY_NAME")})
        seasons = sorted({record["SEASON"] for record in records if record.get("SEASON")})

        canonical_name = str(props.get("boundary_name") or props.get("Boundary_Name") or "").strip()
        name_norms = {norm_name(name) for name in arcgis_names if norm_name(name)}
        current_norm = norm_name(canonical_name)
        name_match = current_norm in name_norms if records else False
        if records:
            arcgis_matched_features += 1
            if name_match:
                name_match_features += 1
            else:
                name_drift_features += 1

        before = json.dumps(props, sort_keys=True)
        props["boundary_id"] = bid
        props["BoundaryID"] = bid
        props["BOUNDARYID"] = bid
        props["boundary_name"] = canonical_name
        props["Boundary_Name"] = canonical_name
        props["BOUNDARY_NAME"] = canonical_name
        props["arcgis_hunt_numbers"] = hunt_numbers
        props["arcgis_hunt_count"] = len(hunt_numbers)
        props["arcgis_boundary_names"] = arcgis_names
        props["arcgis_seasons"] = seasons
        props["arcgis_boundary_name_match"] = bool(name_match)
        props["arcgis_reconcile_source"] = str(ARCGIS_TABLE.relative_to(ROOT)).replace("\\", "/") if records else ""
        props["source"] = props.get("source") or "arcgis_lite_individual"
        after = json.dumps(props, sort_keys=True)
        if before != after:
            changed_features += 1

        if records:
            audit_rows.append(
                {
                    "boundary_id": bid,
                    "hunt_units_boundary_name": canonical_name,
                    "arcgis_hunt_count": len(hunt_numbers),
                    "arcgis_hunt_numbers": "|".join(hunt_numbers),
                    "arcgis_boundary_names": "|".join(arcgis_names),
                    "arcgis_seasons": "|".join(seasons),
                    "arcgis_boundary_name_match": bool(name_match),
                }
            )

    arcgis_only_rows = []
    for bid in sorted(arcgis_ids - geometry_ids, key=lambda x: (len(x), x)):
        records = by_boundary[bid]
        arcgis_only_rows.append(
            {
                "boundary_id": bid,
                "arcgis_hunt_numbers": "|".join(sorted({record["HUNT_NUMBER"] for record in records if record.get("HUNT_NUMBER")})),
                "arcgis_boundary_names": "|".join(sorted({record["BOUNDARY_NAME"] for record in records if record.get("BOUNDARY_NAME")})),
                "arcgis_seasons": "|".join(sorted({record["SEASON"] for record in records if record.get("SEASON")})),
            }
        )

    geometry_only_rows = []
    for bid in sorted(geometry_ids - arcgis_ids, key=lambda x: (len(x), x)):
        feature = next(
            feature
            for feature in features
            if boundary_id((feature.get("properties") or {}).get("boundary_id") or (feature.get("properties") or {}).get("BoundaryID")) == bid
        )
        props = feature.get("properties", {})
        geometry_only_rows.append(
            {
                "boundary_id": bid,
                "boundary_name": props.get("boundary_name") or props.get("Boundary_Name") or "",
            }
        )

    write_csv(
        AUDIT_DIR / "hunt_units_arcgis_reconcile_matched_boundaries.csv",
        audit_rows,
        [
            "boundary_id",
            "hunt_units_boundary_name",
            "arcgis_hunt_count",
            "arcgis_hunt_numbers",
            "arcgis_boundary_names",
            "arcgis_seasons",
            "arcgis_boundary_name_match",
        ],
    )
    write_csv(
        AUDIT_DIR / "hunt_units_arcgis_reconcile_arcgis_only_boundary_ids.csv",
        arcgis_only_rows,
        ["boundary_id", "arcgis_hunt_numbers", "arcgis_boundary_names", "arcgis_seasons"],
    )
    write_csv(
        AUDIT_DIR / "hunt_units_arcgis_reconcile_geometry_only_boundary_ids.csv",
        geometry_only_rows,
        ["boundary_id", "boundary_name"],
    )

    summary = {
        "write": write,
        "hunt_units_file": str(HUNT_UNITS.relative_to(ROOT)).replace("\\", "/"),
        "arcgis_file": str(ARCGIS_TABLE.relative_to(ROOT)).replace("\\", "/"),
        "geometry_feature_count": len(features),
        "geometry_boundary_id_count": len(geometry_ids),
        "arcgis_record_count": len(arcgis_records),
        "arcgis_boundary_id_count": len(arcgis_ids),
        "matched_boundary_id_count": len(geometry_ids & arcgis_ids),
        "geometry_only_boundary_id_count": len(geometry_ids - arcgis_ids),
        "arcgis_only_boundary_id_count": len(arcgis_ids - geometry_ids),
        "arcgis_matched_features": arcgis_matched_features,
        "arcgis_boundary_name_match_features": name_match_features,
        "arcgis_boundary_name_drift_features": name_drift_features,
        "changed_features_if_written": changed_features,
        "matched_audit": "audits/boundary_runtime/hunt_units_arcgis_reconcile_matched_boundaries.csv",
        "arcgis_only_audit": "audits/boundary_runtime/hunt_units_arcgis_reconcile_arcgis_only_boundary_ids.csv",
        "geometry_only_audit": "audits/boundary_runtime/hunt_units_arcgis_reconcile_geometry_only_boundary_ids.csv",
        "note": "The GeoJSON is boundary geometry keyed by boundary_id. The ArcGIS table is a hunt-code-to-boundary crosswalk keyed by HUNT_NUMBER and BOUNDARYID, so reconciliation is by boundary_id and ArcGIS fields are preserved as aliases/lists on geometry features.",
    }

    if write:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / f"hunt_units.before_arcgis_reconcile_{timestamp}.geojson"
        shutil.copy2(HUNT_UNITS, backup)
        hunt_units.setdefault("metadata", {})
        hunt_units["metadata"]["arcgis_reconciled_at"] = datetime.now(timezone.utc).isoformat()
        hunt_units["metadata"]["arcgis_reconcile_source"] = str(ARCGIS_TABLE.relative_to(ROOT)).replace("\\", "/")
        hunt_units["metadata"]["arcgis_reconcile_note"] = summary["note"]
        HUNT_UNITS.write_text(json.dumps(hunt_units, separators=(",", ":")) + "\n", encoding="utf-8")
        for copy_path in [PUBLIC_CONTRACT, PAGES_DATA, PAGES_PUBLIC_CONTRACT]:
            copy_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(HUNT_UNITS, copy_path)
        summary["backup_path"] = str(backup.relative_to(ROOT)).replace("\\", "/")
        summary["synced_copies"] = [
            str(path.relative_to(ROOT)).replace("\\", "/")
            for path in [PUBLIC_CONTRACT, PAGES_DATA, PAGES_PUBLIC_CONTRACT]
        ]

    summary_path = AUDIT_DIR / "hunt_units_arcgis_reconcile_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(reconcile(write=args.write), indent=2))
