#!/usr/bin/env python3
"""Download and validate the current Utah DWR hunt-boundary polygons.

The live ArcGIS layer is large enough that a one-shot GeoJSON query is
occasionally rejected by the DWR web adaptor.  This puller requests the object
ID inventory first, downloads small deterministic batches, and combines them
into one source-faithful GeoJSON snapshot with a hash manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
SERVICE_URL = (
    "https://dwrmapserv.utah.gov/arcgis/rest/services/hunt/"
    "Boundaries_and_Tables_for_HuntP/FeatureServer"
)
LAYER_URL = f"{SERVICE_URL}/0"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, value: Any, *, compact: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if compact:
        text = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        text = json.dumps(value, ensure_ascii=False, indent=2)
    path.write_text(text + "\n", encoding="utf-8")


def fetch_json(url: str, *, attempts: int = 6, timeout: int = 180) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            request = Request(url, headers={"User-Agent": "HUNT-BUILDER boundary source pull"})
            with urlopen(request, timeout=timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                body = response.read()
            if b"Could not access any server machines" in body:
                raise RuntimeError("Utah DWR ArcGIS web adaptor temporarily unavailable")
            payload = json.loads(body.decode("utf-8-sig"))
            if payload.get("error"):
                raise RuntimeError(f"ArcGIS error: {payload['error']}")
            return payload
        except Exception as exc:  # network endpoint is known to be intermittently unavailable
            last_error = exc
            if attempt < attempts:
                time.sleep(min(2**attempt, 20))
    raise RuntimeError(f"Unable to download {url}: {last_error}")


def layer_query_url(params: dict[str, Any]) -> str:
    return f"{LAYER_URL}/query?{urlencode(params)}"


def as_sortable_int(value: Any) -> tuple[int, str]:
    text = str(value or "").strip()
    try:
        return int(float(text)), text
    except ValueError:
        return 10**12, text


def pull(output_dir: Path, batch_size: int) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    service_metadata = fetch_json(f"{SERVICE_URL}?f=pjson")
    layer_metadata = fetch_json(f"{LAYER_URL}?f=pjson")
    ids_payload = fetch_json(
        layer_query_url({"where": "1=1", "returnIdsOnly": "true", "f": "json"})
    )
    object_id_field = ids_payload.get("objectIdFieldName") or layer_metadata.get(
        "objectIdField", "OBJECTID"
    )
    object_ids = sorted({int(value) for value in ids_payload.get("objectIds", [])})
    if not object_ids:
        raise RuntimeError("The ArcGIS service returned no object IDs")

    features: list[dict[str, Any]] = []
    for start in range(0, len(object_ids), batch_size):
        batch = object_ids[start : start + batch_size]
        payload = fetch_json(
            layer_query_url(
                {
                    "objectIds": ",".join(str(value) for value in batch),
                    "outFields": "*",
                    "returnGeometry": "true",
                    "outSR": "4326",
                    "f": "geojson",
                }
            )
        )
        page = payload.get("features", [])
        if len(page) != len(batch):
            returned_ids = {
                int(feature.get("properties", {}).get(object_id_field))
                for feature in page
                if feature.get("properties", {}).get(object_id_field) is not None
            }
            missing = sorted(set(batch) - returned_ids)
            raise RuntimeError(
                f"Batch {start // batch_size + 1} returned {len(page)} of "
                f"{len(batch)} features; missing object IDs: {missing}"
            )
        features.extend(page)

    features.sort(
        key=lambda feature: (
            as_sortable_int(feature.get("properties", {}).get("BoundaryID")),
            as_sortable_int(feature.get("properties", {}).get(object_id_field)),
        )
    )
    returned_object_ids = [
        int(feature.get("properties", {}).get(object_id_field)) for feature in features
    ]
    if len(features) != len(object_ids) or set(returned_object_ids) != set(object_ids):
        raise RuntimeError("Combined GeoJSON does not match the ArcGIS object-ID inventory")

    geojson_path = output_dir / "udwr_hunt_boundaries_combined.geojson"
    service_path = output_dir / "feature_service_metadata.json"
    layer_path = output_dir / "layer_0_metadata.json"
    ids_path = output_dir / "object_ids.json"
    write_json(service_path, service_metadata)
    write_json(layer_path, layer_metadata)
    write_json(ids_path, ids_payload)
    write_json(
        geojson_path,
        {
            "type": "FeatureCollection",
            "name": layer_metadata.get("name"),
            "source": {
                "agency": "Utah Division of Wildlife Resources",
                "service": SERVICE_URL,
                "layer": LAYER_URL,
                "retrievedAt": generated_at,
                "outSpatialReference": 4326,
                "query": "all object IDs in deterministic batches",
            },
            "features": features,
        },
        compact=True,
    )

    boundary_ids = [
        str(feature.get("properties", {}).get("BoundaryID") or "").strip()
        for feature in features
    ]
    duplicate_boundary_ids = sorted(
        boundary_id
        for boundary_id, count in Counter(boundary_ids).items()
        if boundary_id and count > 1
    )
    statuses = Counter(
        str(feature.get("properties", {}).get("Status") or "(blank)").strip()
        for feature in features
    )
    boundary_types = Counter(
        str(feature.get("properties", {}).get("BTYPE") or "(blank)").strip()
        for feature in features
    )
    manifest = {
        "generatedAt": generated_at,
        "agency": "Utah Division of Wildlife Resources",
        "sourceService": SERVICE_URL,
        "sourceLayer": LAYER_URL,
        "sourceLayerName": layer_metadata.get("name"),
        "sourceDescription": layer_metadata.get("description"),
        "geometryType": layer_metadata.get("geometryType"),
        "sourceSpatialReference": layer_metadata.get("sourceSpatialReference"),
        "outputSpatialReference": 4326,
        "objectIdField": object_id_field,
        "batchSize": batch_size,
        "batchCount": (len(object_ids) + batch_size - 1) // batch_size,
        "featureCount": len(features),
        "uniqueObjectIdCount": len(set(returned_object_ids)),
        "nonblankBoundaryIdCount": sum(bool(value) for value in boundary_ids),
        "uniqueBoundaryIdCount": len({value for value in boundary_ids if value}),
        "duplicateBoundaryIds": duplicate_boundary_ids,
        "missingGeometryCount": sum(not feature.get("geometry") for feature in features),
        "statusCounts": dict(sorted(statuses.items())),
        "boundaryTypeCounts": dict(sorted(boundary_types.items())),
        "files": {},
    }
    for path in (service_path, layer_path, ids_path, geojson_path):
        manifest["files"][path.name] = {
            "bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
    manifest_path = output_dir / "manifest.json"
    write_json(manifest_path, manifest)
    return {"outputDir": str(output_dir), "manifest": str(manifest_path), **manifest}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output-dir",
        default=(
            "audits/dwr_hunt_unit_boundaries/arcgis_pull_"
            + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        ),
    )
    parser.add_argument("--batch-size", type=int, default=10)
    args = parser.parse_args()
    if args.batch_size < 1 or args.batch_size > 50:
        raise SystemExit("--batch-size must be between 1 and 50")
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = ROOT / output_dir
    result = pull(output_dir, args.batch_size)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
