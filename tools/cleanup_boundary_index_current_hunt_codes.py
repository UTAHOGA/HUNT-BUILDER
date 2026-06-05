#!/usr/bin/env python3
"""Close source-backed current hunt-code gaps in the display boundary index."""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FIELDNAMES = [
    "hunt_code",
    "boundary_id",
    "member_boundary_ids",
    "source_boundary_ids",
    "boundary_source_authority",
    "boundary_source_file",
    "merged_boundary_id",
    "boundary_geometry_type",
    "geometry_status",
    "boundary_geojson_path",
    "boundary_kmz_path",
    "boundary_kml_path",
    "dwr_boundary_link",
    "member_boundary_count",
]


def norm(value: Any) -> str:
    return str(value or "").strip().upper()


def norm_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"\bcwmu\b", "", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def extract_records(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return [row for row in data if isinstance(row, dict)]
    if isinstance(data, dict):
        for key in ("records", "hunts", "rows", "data"):
            if isinstance(data.get(key), list):
                return [row for row in data[key] if isinstance(row, dict)]
    return []


def geo_feature_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = read_json(path)
    return [
        feature.get("properties") or {}
        for feature in data.get("features", [])
        if isinstance(feature, dict)
    ]


def boundary_id_from_props(props: dict[str, Any]) -> str:
    for key in ("boundary_id", "BoundaryID", "BOUNDARYID", "Boundary_Id", "assigned_boundary_id"):
        value = norm(props.get(key))
        if value:
            return value
    return ""


def boundary_name_from_props(props: dict[str, Any]) -> str:
    for key in ("Boundary_Name", "boundary_name", "NAME", "Name"):
        value = str(props.get(key) or "").strip()
        if value:
            return value
    return ""


def build_boundary_name_lookup(features: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    by_name: dict[str, list[tuple[str, str]]] = {}
    for props in features:
        boundary_id = boundary_id_from_props(props)
        name = boundary_name_from_props(props)
        normalized = norm_name(name)
        if boundary_id and normalized:
            by_name.setdefault(normalized, []).append((boundary_id, name))
    return by_name


def unique_pairs(values: list[tuple[str, str]]) -> list[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for pair in values:
        if pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def index_row(
    *,
    hunt_code: str,
    boundary_id: str,
    source_file: str,
    geometry_type: str,
    boundary_geojson_path: str = "",
    kmz_path: str = "",
    kml_path: str = "",
) -> dict[str, Any]:
    return {
        "hunt_code": hunt_code,
        "boundary_id": boundary_id,
        "member_boundary_ids": [],
        "source_boundary_ids": [boundary_id] if boundary_id else [],
        "boundary_source_authority": "Utah DWR",
        "boundary_source_file": source_file,
        "merged_boundary_id": None,
        "boundary_geometry_type": geometry_type,
        "geometry_status": "mapped",
        "boundary_geojson_path": boundary_geojson_path or None,
        "boundary_kmz_path": kmz_path or None,
        "boundary_kml_path": kml_path or None,
        "dwr_boundary_link": None,
        "member_boundary_count": 0,
    }


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return ";".join(str(item) for item in value)
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--out-dir", default="audits/boundary_runtime")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    master_path = root / "data/hunt-master-canonical-2026-source-of-truth.json"
    index_json_path = root / "processed_data/display-boundary-index-2026.json"
    index_csv_path = root / "processed_data/display-boundary-index-2026.csv"
    boundary_geo_dir = root / "processed_data/boundaries"
    kmz_dir = root / "data/boundaries/kmz"
    kml_dir = root / "data/boundaries/kml"
    loaded_boundary_path = root / "data/hunt_boundaries.geojson"

    master_rows = extract_records(read_json(master_path))
    master_by_code = {norm(row.get("hunt_code")): row for row in master_rows if norm(row.get("hunt_code"))}

    index_data = read_json(index_json_path)
    index_rows = extract_records(index_data)
    indexed_codes = {norm(row.get("hunt_code")) for row in index_rows if norm(row.get("hunt_code"))}

    loaded_features = geo_feature_rows(loaded_boundary_path)
    loaded_boundary_ids = {boundary_id_from_props(props) for props in loaded_features}
    loaded_boundary_ids.discard("")
    by_boundary_name = build_boundary_name_lookup(loaded_features)

    missing_codes = sorted(set(master_by_code) - indexed_codes)
    audit_rows: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []

    for code in missing_codes:
        master = master_by_code[code]
        master_boundary_id = str(master.get("boundary_id") or master.get("boundaryId") or "").strip()
        hunt_name = str(master.get("hunt_name") or master.get("unit_name") or "").strip()
        per_geo = boundary_geo_dir / f"{code}.geojson"
        kmz = kmz_dir / f"{code}.kmz"
        kml = kml_dir / f"{code}.kml"
        source = ""
        decision = "unresolved"
        reason = ""
        new_row: dict[str, Any] | None = None

        per_geo_boundary_id = ""
        if per_geo.exists():
            props_rows = geo_feature_rows(per_geo)
            per_ids = sorted({boundary_id_from_props(props) for props in props_rows if boundary_id_from_props(props)})
            if len(per_ids) == 1:
                per_geo_boundary_id = per_ids[0]
                new_row = index_row(
                    hunt_code=code,
                    boundary_id=master_boundary_id or per_geo_boundary_id,
                    source_file=f"processed_data/boundaries/{code}.geojson",
                    geometry_type="single_geojson_path",
                    boundary_geojson_path=f"processed_data/boundaries/{code}.geojson",
                    kmz_path=f"data/boundaries/kmz/{code}.kmz" if kmz.exists() else "",
                    kml_path=f"data/boundaries/kml/{code}.kml" if kml.exists() else "",
                )
                decision = "add_index_row"
                source = "per_hunt_geojson"
                reason = "Per-hunt GeoJSON exists and contains one boundary id."
            elif len(per_ids) > 1:
                decision = "review_multi_feature_geojson"
                source = "per_hunt_geojson"
                reason = "Per-hunt GeoJSON exists but contains multiple boundary ids; needs explicit merged-row review."

        if new_row is None and master_boundary_id:
            if master_boundary_id in loaded_boundary_ids:
                new_row = index_row(
                    hunt_code=code,
                    boundary_id=master_boundary_id,
                    source_file="data/hunt-master-canonical-2026-source-of-truth.json",
                    geometry_type="single_boundary_id",
                )
                decision = "add_index_row"
                source = "master_boundary_id"
                reason = "Master boundary_id exists in loaded boundary GeoJSON."
            else:
                decision = "unresolved_boundary_id_not_loaded"
                source = "master_boundary_id"
                reason = "Master boundary_id exists but was not found in the loaded boundary geometry file."

        if new_row is None and not master_boundary_id:
            candidates = unique_pairs(by_boundary_name.get(norm_name(hunt_name), []))
            if len(candidates) == 1:
                boundary_id, matched_name = candidates[0]
                new_row = index_row(
                    hunt_code=code,
                    boundary_id=boundary_id,
                    source_file="data/hunt_boundaries.geojson",
                    geometry_type="single_boundary_id_exact_name_match",
                )
                decision = "add_index_row"
                source = "exact_unique_boundary_name_match"
                reason = f"Exact normalized hunt name matched one loaded boundary name: {matched_name}."
            elif len(candidates) > 1:
                decision = "unresolved_ambiguous_name_match"
                source = "data/hunt_boundaries.geojson"
                reason = f"Exact normalized hunt name matched multiple boundary ids: {', '.join(x[0] for x in candidates)}."
            else:
                decision = "unresolved_no_boundary_evidence"
                reason = "No master boundary_id, no per-hunt GeoJSON, and no exact unique boundary-name match."

        if new_row is not None:
            additions.append(new_row)

        audit_rows.append({
            "hunt_code": code,
            "hunt_name": hunt_name,
            "species": master.get("species") or "",
            "sex_type": master.get("sex_type") or "",
            "weapon": master.get("weapon") or "",
            "master_boundary_id": master_boundary_id,
            "per_hunt_geojson_exists": per_geo.exists(),
            "per_hunt_geojson_boundary_id": per_geo_boundary_id,
            "decision": decision,
            "source": source,
            "reason": reason,
            "added_boundary_id": new_row.get("boundary_id") if new_row else "",
            "added_boundary_geojson_path": new_row.get("boundary_geojson_path") if new_row else "",
        })

    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    audit_csv = out_dir / "boundary_index_current_hunt_code_cleanup.csv"
    with audit_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(audit_rows[0].keys()) if audit_rows else [])
        writer.writeheader()
        writer.writerows(audit_rows)

    counts: dict[str, int] = {}
    for row in audit_rows:
        counts[row["decision"]] = counts.get(row["decision"], 0) + 1

    summary = {
        "generated_at": timestamp,
        "applied": bool(args.apply),
        "master_rows": len(master_rows),
        "master_unique_hunt_codes": len(master_by_code),
        "index_rows_before": len(index_rows),
        "index_unique_hunt_codes_before": len(indexed_codes),
        "missing_current_hunt_codes_before": len(missing_codes),
        "additions_planned": len(additions),
        "decision_counts": counts,
        "audit_csv": str(audit_csv.relative_to(root)),
    }

    if args.apply and additions:
        new_records = sorted(index_rows + additions, key=lambda row: norm(row.get("hunt_code")))
        if isinstance(index_data, dict):
            index_data["records"] = new_records
            index_data["count"] = len(new_records)
            index_data["generated_at"] = timestamp
            index_data["cleanup_note"] = "Added source-backed current hunt-code boundary rows."
        else:
            index_data = new_records
        tmp_json = index_json_path.with_suffix(".json.tmp")
        tmp_json.write_text(json.dumps(index_data, indent=2) + "\n", encoding="utf-8")
        tmp_json.replace(index_json_path)

        tmp_csv = index_csv_path.with_suffix(".csv.tmp")
        with tmp_csv.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            for row in new_records:
                writer.writerow({field: csv_value(row.get(field)) for field in FIELDNAMES})
        tmp_csv.replace(index_csv_path)

        summary["index_rows_after"] = len(new_records)
        summary["index_unique_hunt_codes_after"] = len({norm(row.get("hunt_code")) for row in new_records})
        summary["missing_current_hunt_codes_after"] = len(set(master_by_code) - {norm(row.get("hunt_code")) for row in new_records})

    summary_json = out_dir / "boundary_index_current_hunt_code_cleanup.json"
    summary_json.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# Boundary Index Current Hunt-Code Cleanup",
        "",
        f"- Generated: `{timestamp}`",
        f"- Applied: `{bool(args.apply)}`",
        f"- Master unique hunt codes: `{len(master_by_code)}`",
        f"- Boundary index unique hunt codes before: `{len(indexed_codes)}`",
        f"- Missing current hunt codes before: `{len(missing_codes)}`",
        f"- Additions planned: `{len(additions)}`",
        "",
        "## Decision Counts",
        "",
    ]
    for key in sorted(counts):
        lines.append(f"- `{key}`: `{counts[key]}`")
    if args.apply:
        lines.extend([
            "",
            "## Apply Result",
            "",
            f"- Boundary index rows after: `{summary.get('index_rows_after')}`",
            f"- Boundary index unique hunt codes after: `{summary.get('index_unique_hunt_codes_after')}`",
            f"- Missing current hunt codes after: `{summary.get('missing_current_hunt_codes_after')}`",
        ])
    (out_dir / "boundary_index_current_hunt_code_cleanup.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
