#!/usr/bin/env python3
"""Build confirmed federal-permit intersections with Utah DWR hunt units.

The calculation reuses the federal map sources configured on the Hunt Builder
entry page. A confirmed permit area authorizes guide service on the federal
land where that area intersects a DWR unit; whole-unit percentage is retained
only as descriptive context:

    area(DWR unit intersect permitted federal geometry) / area(DWR unit)

USFS permits use the mapped administrative-forest polygons. BLM permits use
the mapped BLM surface-management polygons clipped to the named administrative
unit. Results are an operational geographic crosswalk, not an independent legal
determination or a statement that a permit names a DWR unit.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform, unary_union


ROOT = Path(__file__).resolve().parents[1]
LOCAL_DIR = ROOT / "local_data" / "outfitters"
BOUNDARY_DIR = LOCAL_DIR / "federal-boundaries"
MASTER_PATH = LOCAL_DIR / "outfitters-master.internal.json"
EVIDENCE_PATH = LOCAL_DIR / "outfitter-federal-service-area-evidence.internal.json"
COVERAGE_PATH = LOCAL_DIR / "outfitter-federal-unit-coverage-review.internal.json"
HUNT_UNITS_PATH = ROOT / "data" / "hunt_units.geojson"
HUNT_BOUNDARY_INFO_PATH = ROOT / "processed_data" / "dwr_huntplanner_hanumber_2026.json"
SNAPSHOT_MANIFEST_PATH = BOUNDARY_DIR / "manifest.json"
INTERNAL_MANIFEST_PATH = ROOT / "data" / "outfitter-internal-master-manifest.json"
PUBLIC_COVERAGE_PATH = ROOT / "processed_data" / "outfitter-federal-unit-coverage-review.json"
PUBLIC_OUTFITTERS_PATH = ROOT / "data" / "outfitters-public.json"
PUBLIC_CONTRACT_OUTFITTERS_PATH = (
    ROOT / "processed_data" / "public_contracts" / "outfitters-public.json"
)

PUBLIC_NAME_OVERRIDES = {
    "outfitter-battleground-guides-outfitters-llc": "Battleground G/O",
    "outfitter-travis-kruckenberg-outfitting-and-cisco-outfitters": (
        "Cisco Outfitting Travis Kruckenberg Outfitting"
    ),
}

USFS_LAYER_URL = (
    "https://apps.fs.usda.gov/arcx/rest/services/EDW/"
    "EDW_ForestSystemBoundaries_01/MapServer/0"
)
USFS_DISTRICT_LAYER_URL = (
    "https://apps.fs.usda.gov/arcx/rest/services/EDW/"
    "EDW_RangerDistricts_01/MapServer/0"
)
BLM_ADMIN_LAYER_URL = (
    "https://gis.blm.gov/utarcgis/rest/services/AdminBoundaries/"
    "BLM_UT_ADMU/FeatureServer/0"
)
BLM_SURFACE_LAYER_URL = (
    "https://gis.blm.gov/utarcgis/rest/services/Lands/"
    "BLM_UT_SMA/FeatureServer/0"
)

USFS_FOREST_NAMES = {
    "ashley": "Ashley National Forest",
    "dixie": "Dixie National Forest",
    "fishlake": "Fishlake National Forest",
    "manti-la-sal": "Manti-La Sal National Forest",
    "uwc": "Uinta-Wasatch-Cache National Forest",
}

USFS_DISTRICT_ORG_CODES = {
    "ashley-duchesne": ("040104",),
    "ashley-roosevelt": ("040103",),
    "ashley-vernal": ("040102",),
    "dixie-cedar": ("040702",),
    "dixie-escalante": ("040704",),
    "dixie-lake-powell": ("040703",),
    "dixie-pine-valley": ("040701",),
    "manti-la-sal-north-zone": ("041001", "041002", "041003"),
    "manti-la-sal-south-zone": ("041004", "041005"),
    "uwc-evanston": ("041904",),
    "uwc-heber-kamas": ("041903",),
    "uwc-pleasant-grove": ("041902",),
    "uwc-spanish-fork": ("041908",),
}

USFS_DISTRICT_PARENT_FOREST = {
    identifier: "ashley"
    if identifier.startswith("ashley-")
    else "dixie"
    if identifier.startswith("dixie-")
    else "manti-la-sal"
    if identifier.startswith("manti-la-sal-")
    else "uwc"
    for identifier in USFS_DISTRICT_ORG_CODES
}

BLM_ADMIN_NAME_HINTS = {
    "blm-cedar-city": ("cedar city",),
    "blm-kanab": ("kanab",),
    "blm-grand-staircase": (
        "grand staircase-escalante national monument",
        "grand staircase escalante national monument",
        "grand staircase escalante nat monument",
    ),
}

THRESHOLD_PERCENT = 75.0
MIN_OVERLAP_ACRES = 0.1
AREA_CRS = "EPSG:26912"
SQ_METERS_PER_ACRE = 4046.8564224


def clean(value: Any) -> str:
    return " ".join(str(value or "").replace("\u00a0", " ").split()).strip()


def ascii_text(value: Any) -> str:
    return unicodedata.normalize("NFKD", clean(value)).encode("ascii", "ignore").decode().lower()


def slugify(value: Any) -> str:
    return re.sub(r"^-|-$", "", re.sub(r"[^a-z0-9]+", "-", ascii_text(value)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def fetch_arcgis_geojson(
    layer_url: str,
    where: str,
    out_fields: str,
    *,
    page_size: int = 2000,
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    offset = 0
    while True:
        query = urlencode(
            {
                "where": where,
                "outFields": out_fields,
                "returnGeometry": "true",
                "outSR": "4326",
                "resultOffset": offset,
                "resultRecordCount": page_size,
                "f": "geojson",
            }
        )
        with urlopen(f"{layer_url}/query?{query}", timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("error"):
            raise RuntimeError(f"ArcGIS query failed for {layer_url}: {payload['error']}")
        page = payload.get("features", [])
        features.extend(page)
        exceeded = bool(payload.get("properties", {}).get("exceededTransferLimit"))
        if len(page) < page_size and not exceeded:
            break
        if not page:
            break
        offset += len(page)
    return {"type": "FeatureCollection", "features": features}


def refresh_snapshots(generated_at: str) -> dict[str, Any]:
    BOUNDARY_DIR.mkdir(parents=True, exist_ok=True)
    forest_names = ",".join(f"'{name}'" for name in USFS_FOREST_NAMES.values())
    snapshots = {
        "usfsForests": {
            "path": BOUNDARY_DIR / "usfs-forest-system-boundaries.geojson",
            "layerUrl": USFS_LAYER_URL,
            "where": f"FORESTNAME IN ({forest_names})",
            "outFields": "FORESTNAME,FORESTNUMBER,FORESTORGCODE,GIS_ACRES",
        },
        "usfsRangerDistricts": {
            "path": BOUNDARY_DIR / "usfs-ranger-district-boundaries.geojson",
            "layerUrl": USFS_DISTRICT_LAYER_URL,
            "where": "districtorgcode IN ("
            + ",".join(
                f"'{code}'"
                for code in sorted(
                    {code for codes in USFS_DISTRICT_ORG_CODES.values() for code in codes}
                )
            )
            + ")",
            "outFields": (
                "rangerdistrictid,region,forestnumber,forestname,districtnumber,"
                "districtname,districtorgcode"
            ),
        },
        "blmAdminUnits": {
            "path": BOUNDARY_DIR / "blm-utah-administrative-units.geojson",
            "layerUrl": BLM_ADMIN_LAYER_URL,
            "where": "1=1",
            "outFields": "ADM_UNIT_CD,ADMU_NAME,BLM_ORG_TYPE,PARENT_CD,PARENT_NAME",
        },
        "blmSurface": {
            "path": BOUNDARY_DIR / "blm-utah-surface-management.geojson",
            "layerUrl": BLM_SURFACE_LAYER_URL,
            "where": "UT_LGD IN ('Bureau of Land Management (BLM)','BLM Wilderness Area')",
            "outFields": "OBJECTID,UT_LGD,ADM_UNIT_CD,GIS_ACRES",
        },
    }
    for item in snapshots.values():
        payload = fetch_arcgis_geojson(item["layerUrl"], item["where"], item["outFields"])
        write_json(item["path"], payload)
        item["featureCount"] = len(payload["features"])
        item["sha256"] = sha256(item["path"])

    manifest = {
        "metadata": {
            "id": "outfitter-federal-boundary-snapshots",
            "generatedAt": generated_at,
            "relationship": "HUNT_BUILDER_ENTRY_MAP_SOURCE_SNAPSHOT",
            "areaCrs": AREA_CRS,
        },
        "sources": {
            key: {
                "path": str(item["path"].relative_to(ROOT)).replace("\\", "/"),
                "layerUrl": item["layerUrl"],
                "where": item["where"],
                "featureCount": item["featureCount"],
                "sha256": item["sha256"],
            }
            for key, item in snapshots.items()
        },
    }
    write_json(SNAPSHOT_MANIFEST_PATH, manifest)
    return manifest


def require_snapshots() -> dict[str, Any]:
    paths = (
        BOUNDARY_DIR / "usfs-forest-system-boundaries.geojson",
        BOUNDARY_DIR / "usfs-ranger-district-boundaries.geojson",
        BOUNDARY_DIR / "blm-utah-administrative-units.geojson",
        BOUNDARY_DIR / "blm-utah-surface-management.geojson",
        SNAPSHOT_MANIFEST_PATH,
    )
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError(f"Federal map snapshots are missing: {missing}. Run with --refresh-boundaries.")
    manifest = read_json(SNAPSHOT_MANIFEST_PATH)
    for item in manifest["sources"].values():
        path = ROOT / item["path"]
        if sha256(path) != item["sha256"]:
            raise ValueError(f"Federal map snapshot hash mismatch: {path}")
    return manifest


def projected_geometry(feature: dict[str, Any], transformer: Transformer):
    geometry = shape(feature["geometry"])
    if not geometry.is_valid:
        geometry = geometry.buffer(0)
    return transform(transformer.transform, geometry)


def property_value(properties: dict[str, Any], name: str) -> Any:
    target = name.casefold()
    return next((value for key, value in properties.items() if key.casefold() == target), None)


def build_federal_geometries(transformer: Transformer) -> tuple[dict[str, Any], dict[str, str]]:
    usfs_payload = read_json(BOUNDARY_DIR / "usfs-forest-system-boundaries.geojson")
    usfs_by_name: dict[str, list[Any]] = {}
    for feature in usfs_payload["features"]:
        name = ascii_text(property_value(feature["properties"], "FORESTNAME"))
        usfs_by_name.setdefault(name, []).append(projected_geometry(feature, transformer))

    federal_geometries: dict[str, Any] = {}
    labels: dict[str, str] = {}
    for identifier, forest_name in USFS_FOREST_NAMES.items():
        candidates = usfs_by_name.get(ascii_text(forest_name), [])
        if not candidates:
            raise ValueError(f"USFS snapshot does not contain {forest_name}")
        federal_geometries[identifier] = unary_union(candidates)
        labels[identifier] = forest_name

    district_payload = read_json(BOUNDARY_DIR / "usfs-ranger-district-boundaries.geojson")
    districts_by_org_code: dict[str, list[Any]] = {}
    district_names_by_org_code: dict[str, set[str]] = {}
    for feature in district_payload["features"]:
        props = feature["properties"]
        org_code = clean(property_value(props, "districtorgcode"))
        if not org_code:
            continue
        districts_by_org_code.setdefault(org_code, []).append(projected_geometry(feature, transformer))
        district_names_by_org_code.setdefault(org_code, set()).add(
            clean(property_value(props, "districtname"))
        )
    for identifier, org_codes in USFS_DISTRICT_ORG_CODES.items():
        pieces = [geometry for code in org_codes for geometry in districts_by_org_code.get(code, [])]
        if not pieces:
            raise ValueError(f"USFS ranger-district snapshot does not resolve {identifier}: {org_codes}")
        federal_geometries[identifier] = unary_union(pieces)
        labels[identifier] = " | ".join(
            sorted(
                {
                    name
                    for code in org_codes
                    for name in district_names_by_org_code.get(code, set())
                    if name
                }
            )
        )

    admin_payload = read_json(BOUNDARY_DIR / "blm-utah-administrative-units.geojson")
    admin_codes: dict[str, set[str]] = {identifier: set() for identifier in BLM_ADMIN_NAME_HINTS}
    admin_names: dict[str, list[str]] = {identifier: [] for identifier in BLM_ADMIN_NAME_HINTS}
    for feature in admin_payload["features"]:
        props = feature["properties"]
        name = ascii_text(props.get("ADMU_NAME"))
        for identifier, hints in BLM_ADMIN_NAME_HINTS.items():
            if any(ascii_text(hint) in name for hint in hints):
                code = clean(props.get("ADM_UNIT_CD"))
                if code:
                    admin_codes[identifier].add(code)
                    admin_names[identifier].append(clean(props.get("ADMU_NAME")))

    unresolved = [identifier for identifier, codes in admin_codes.items() if not codes]
    if unresolved:
        available = sorted(
            clean(feature["properties"].get("ADMU_NAME")) for feature in admin_payload["features"]
        )
        raise ValueError(f"BLM administrative units did not resolve {unresolved}; available names: {available}")

    surface_payload = read_json(BOUNDARY_DIR / "blm-utah-surface-management.geojson")
    surface_by_code: dict[str, list[Any]] = {}
    for feature in surface_payload["features"]:
        code = clean(feature["properties"].get("ADM_UNIT_CD"))
        if code:
            surface_by_code.setdefault(code, []).append(projected_geometry(feature, transformer))

    for identifier, codes in admin_codes.items():
        pieces = [geometry for code in codes for geometry in surface_by_code.get(code, [])]
        if not pieces:
            raise ValueError(f"BLM surface snapshot has no pieces for {identifier} codes {sorted(codes)}")
        federal_geometries[identifier] = unary_union(pieces)
        labels[identifier] = " | ".join(sorted(set(admin_names[identifier])))
    return federal_geometries, labels


def build_hunt_geometry_index(
    transformer: Transformer,
    hunt_units_path: Path,
    alias_source_path: Path | None = None,
    hunt_boundary_info_path: Path | None = None,
) -> dict[str, list[dict[str, Any]]]:
    payload = read_json(hunt_units_path)
    aliases_by_boundary_id: dict[str, dict[str, set[str]]] = {}
    if alias_source_path and alias_source_path.resolve() != hunt_units_path.resolve():
        alias_payload = read_json(alias_source_path)
        for feature in alias_payload.get("features", []):
            props = feature.get("properties", {})
            boundary_id = clean(props.get("boundary_id") or props.get("BoundaryID"))
            if not boundary_id:
                continue
            alias_entry = aliases_by_boundary_id.setdefault(
                boundary_id, {"names": set(), "huntCodes": set()}
            )
            alias_entry["names"].update(
                clean(value)
                for value in [
                    props.get("Boundary_Name"),
                    props.get("boundary_name"),
                    *props.get("arcgis_boundary_names", []),
                ]
                if clean(value)
            )
            alias_entry["huntCodes"].update(
                clean(value) for value in props.get("arcgis_hunt_numbers", []) if clean(value)
            )
    if hunt_boundary_info_path:
        info_payload = read_json(hunt_boundary_info_path)
        info_rows = (
            info_payload
            if isinstance(info_payload, list)
            else info_payload.get("records") or info_payload.get("data") or []
        )
        for row in info_rows:
            hunt_code = clean(row.get("hunt_code") or row.get("HUNT_NUMBER") or row.get("HUNT_NBR"))
            raw_infos = row.get("hunt_boundary_infos_json") or []
            try:
                infos = json.loads(raw_infos) if isinstance(raw_infos, str) else raw_infos
            except json.JSONDecodeError:
                infos = []
            for info in infos:
                boundary_id = clean(info.get("BOUNDARY_ID") or info.get("BoundaryID"))
                if not boundary_id:
                    continue
                alias_entry = aliases_by_boundary_id.setdefault(
                    boundary_id, {"names": set(), "huntCodes": set()}
                )
                if hunt_code:
                    alias_entry["huntCodes"].add(hunt_code)
                boundary_name = clean(info.get("BOUNDARY_NAME") or info.get("Boundary_Name"))
                if boundary_name:
                    alias_entry["names"].add(boundary_name)
    index: dict[str, list[dict[str, Any]]] = {}
    for feature in payload["features"]:
        props = feature["properties"]
        boundary_id = clean(props.get("boundary_id") or props.get("BoundaryID"))
        preserved = aliases_by_boundary_id.get(boundary_id, {"names": set(), "huntCodes": set()})
        aliases = {
            slugify(props.get("Boundary_Name")),
            slugify(props.get("boundary_name")),
            *(slugify(value) for value in props.get("arcgis_boundary_names", [])),
            *(slugify(value) for value in preserved["names"]),
        }
        item = {
            "boundaryId": boundary_id,
            "huntCodes": {
                clean(value) for value in props.get("arcgis_hunt_numbers", []) if clean(value)
            }
            | preserved["huntCodes"],
            "geometry": projected_geometry(feature, transformer),
        }
        for alias in {value for value in aliases if value}:
            index.setdefault(alias, []).append(item)
        for hunt_code in item["huntCodes"]:
            index.setdefault(hunt_code.upper(), []).append(item)
    return index


def select_unit_geometry(row: dict[str, Any], index: dict[str, list[dict[str, Any]]]):
    example_codes = {
        value.strip().upper()
        for value in re.split(r"[|,]", clean(row.get("ExampleHuntCodes")))
        if value.strip()
    }
    candidates = index.get(clean(row.get("UnitCode")), [])
    if not candidates:
        candidates = index.get(slugify(row.get("UnitName")), [])
    if not candidates and example_codes:
        candidates = [item for code in example_codes for item in index.get(code, [])]
    if not candidates:
        return None, [], "NO_EXACT_DWR_BOUNDARY_MATCH"

    code_matches = [item for item in candidates if item["huntCodes"] & example_codes]
    selected = code_matches or candidates
    by_boundary: dict[str, Any] = {}
    for item in selected:
        by_boundary[item["boundaryId"]] = item["geometry"]
    geometry = unary_union(list(by_boundary.values()))
    return geometry, sorted(by_boundary), "MATCHED_EXACT_NAME_OR_HUNT_CODE"


def federal_ids_for_evidence(row: dict[str, Any]) -> list[str]:
    district_ids = set(row.get("confirmedUsfsDistrictIds", []))
    district_parent_forests = {
        USFS_DISTRICT_PARENT_FOREST[identifier]
        for identifier in district_ids
        if identifier in USFS_DISTRICT_PARENT_FOREST
    }
    forest_ids = set(row.get("confirmedUsfsForestIds", [])) - district_parent_forests
    return sorted(forest_ids | district_ids | set(row.get("confirmedBlmDistrictIds", [])))


def build_outfitter_geometries(
    evidence_rows: list[dict[str, Any]], federal_geometries: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    geometries: dict[str, Any] = {}
    area_ids_by_outfitter: dict[str, list[str]] = {}
    for row in evidence_rows:
        if clean(row.get("permitEvidenceStatus")) != "Confirmed":
            continue
        area_ids = [identifier for identifier in federal_ids_for_evidence(row) if identifier in federal_geometries]
        if not area_ids:
            continue
        geometries[row["outfitterId"]] = unary_union([federal_geometries[identifier] for identifier in area_ids])
        area_ids_by_outfitter[row["outfitterId"]] = area_ids
    return geometries, area_ids_by_outfitter


def update_coverage(
    coverage_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
    outfitter_geometries: dict[str, Any],
    area_ids_by_outfitter: dict[str, list[str]],
    federal_geometries: dict[str, Any],
    hunt_index: dict[str, list[dict[str, Any]]],
    labels: dict[str, str],
    hunt_unit_geometry_source: str,
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    evidence_by_id = {row["outfitterId"]: row for row in evidence_rows}
    confirmed_by_unit: dict[tuple[str, str], set[str]] = {}
    for evidence in evidence_rows:
        for claim in evidence.get("confirmedUnitServiceClaims", []):
            key = (ascii_text(claim.get("species")), clean(claim.get("unitCode")))
            confirmed_by_unit.setdefault(key, set()).add(evidence["outfitterId"])
    eligibility_by_outfitter: dict[str, list[dict[str, Any]]] = {}
    rebuilt: list[dict[str, Any]] = []

    for source_row in coverage_rows:
        row = copy.deepcopy(source_row)
        eligible = clean(row.get("FederalCoverageEligible")).lower() == "yes"
        unit_geometry, boundary_ids, match_status = select_unit_geometry(row, hunt_index)
        details: list[dict[str, Any]] = []
        if eligible and unit_geometry is not None and unit_geometry.area > 0:
            for outfitter_id, permit_geometry in outfitter_geometries.items():
                overlap_area = unit_geometry.intersection(permit_geometry).area
                overlap_acres = overlap_area / SQ_METERS_PER_ACRE
                if overlap_acres < MIN_OVERLAP_ACRES:
                    continue
                percent = min(100.0, overlap_area / unit_geometry.area * 100.0)
                area_ids = area_ids_by_outfitter[outfitter_id]
                contributing = [
                    identifier
                    for identifier in area_ids
                    if unit_geometry.intersection(federal_geometries[identifier]).area
                    / SQ_METERS_PER_ACRE
                    >= MIN_OVERLAP_ACRES
                ]
                qualifies = percent + 1e-9 >= THRESHOLD_PERCENT
                detail = {
                    "outfitterId": outfitter_id,
                    "displayName": evidence_by_id[outfitter_id]["displayName"],
                    "coveredUnitAreaPercent": round(percent, 4),
                    "coveredUnitAreaAcres": round(overlap_acres, 2),
                    "authorizedByFederalPermitAreaOverlap": True,
                    "qualifiesAt75Percent": qualifies,
                    "federalAreaIds": area_ids,
                    "contributingFederalAreaIds": contributing,
                    "contributingFederalAreas": [labels[identifier] for identifier in contributing],
                    "permitEvidenceReviewStatus": evidence_by_id[outfitter_id]["permitEvidenceStatus"],
                    "outfitterRecordReviewStatus": evidence_by_id[outfitter_id]["reviewStatus"],
                    "permitEvidenceBasis": evidence_by_id[outfitter_id]["evidenceBasis"],
                }
                details.append(detail)

        confirmed_ids = confirmed_by_unit.get(
            (ascii_text(row.get("Species")), clean(row.get("UnitCode"))), set()
        )
        detail_by_id = {item["outfitterId"]: item for item in details}
        for outfitter_id in confirmed_ids:
            detail = detail_by_id.get(outfitter_id)
            if detail is None:
                area_ids = area_ids_by_outfitter.get(outfitter_id, [])
                detail = {
                    "outfitterId": outfitter_id,
                    "displayName": evidence_by_id[outfitter_id]["displayName"],
                    "coveredUnitAreaPercent": 0.0,
                    "coveredUnitAreaAcres": 0.0,
                    "authorizedByFederalPermitAreaOverlap": False,
                    "qualifiesAt75Percent": False,
                    "federalAreaIds": area_ids,
                    "contributingFederalAreaIds": [],
                    "contributingFederalAreas": [],
                    "permitEvidenceReviewStatus": evidence_by_id[outfitter_id]["permitEvidenceStatus"],
                    "outfitterRecordReviewStatus": evidence_by_id[outfitter_id]["reviewStatus"],
                    "permitEvidenceBasis": evidence_by_id[outfitter_id]["evidenceBasis"],
                }
                details.append(detail)
                detail_by_id[outfitter_id] = detail
            detail["confirmedServiceClaim"] = True
            detail["confirmedServiceClaimStatus"] = "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
            detail["confirmedServiceClaimSource"] = (
                "data/source-evidence/wild-eyez-confirmed-elk-service-area-2026.json"
            )

        for detail in details:
            is_confirmed = bool(detail.get("confirmedServiceClaim"))
            if not detail.get("authorizedByFederalPermitAreaOverlap") and not is_confirmed:
                continue
            outfitter_id = detail["outfitterId"]
            eligibility_by_outfitter.setdefault(outfitter_id, []).append(
                {
                    "species": clean(row.get("Species")),
                    "unitName": clean(row.get("UnitName")),
                    "unitCode": clean(row.get("UnitCode")),
                    "boundaryIds": boundary_ids,
                    "coveredUnitAreaPercent": detail["coveredUnitAreaPercent"],
                    "coveredUnitAreaAcres": detail["coveredUnitAreaAcres"],
                    "federalAreaIds": detail["federalAreaIds"],
                    "contributingFederalAreaIds": detail["contributingFederalAreaIds"],
                    "contributingFederalAreas": detail["contributingFederalAreas"],
                    "permitEvidenceReviewStatus": detail["permitEvidenceReviewStatus"],
                    "outfitterRecordReviewStatus": detail["outfitterRecordReviewStatus"],
                    "permitEvidenceBasis": detail["permitEvidenceBasis"],
                    "status": (
                        "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
                        if is_confirmed
                        else "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
                    ),
                    "basis": (
                        "OPERATOR_CONFIRMED_SERVICE_AREA"
                        if is_confirmed
                        else "CONFIRMED_FEDERAL_PERMIT_SCOPE_GEOMETRIC_INTERSECTION"
                    ),
                }
            )

        details.sort(key=lambda item: (-item["coveredUnitAreaPercent"], ascii_text(item["displayName"])))
        qualifying = [item for item in details if item["qualifiesAt75Percent"]]
        confirmed = [item for item in details if item.get("confirmedServiceClaim")]
        effective = [item for item in details if item.get("authorizedByFederalPermitAreaOverlap") or item.get("confirmedServiceClaim")]
        usfs_qualifying = [
            item
            for item in effective
            if any(identifier in USFS_FOREST_NAMES for identifier in item["contributingFederalAreaIds"])
            or any(identifier in USFS_DISTRICT_ORG_CODES for identifier in item["contributingFederalAreaIds"])
        ]
        blm_qualifying = [
            item
            for item in effective
            if any(identifier in BLM_ADMIN_NAME_HINTS for identifier in item["contributingFederalAreaIds"])
        ]
        status = (
            "INELIGIBLE_EXISTING_CROSSWALK_RULE"
            if not eligible
            else "NOT_CALCULATED_NO_EXACT_DWR_BOUNDARY_MATCH"
            if unit_geometry is None
            else "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
            if confirmed
            else "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
            if effective
            else "NO_FEDERAL_PERMIT_AREA_INTERSECTION"
        )
        row.update(
            {
                "UnitBoundaryMatchStatus": match_status if eligible else "NOT_APPLICABLE",
                "UnitBoundaryIds": boundary_ids,
                "UnitAreaAcres": round(unit_geometry.area / SQ_METERS_PER_ACRE, 2)
                if unit_geometry is not None
                else None,
                "CoverageThresholdPercent": THRESHOLD_PERCENT,
                "MinimumOverlapToleranceAcres": MIN_OVERLAP_ACRES,
                "UsfsPermitMatchedOutfitterCount": len(usfs_qualifying),
                "UsfsPermitMatchedOutfitters": " | ".join(item["displayName"] for item in usfs_qualifying),
                "UsfsPermitMatchedOutfitterIds": [item["outfitterId"] for item in usfs_qualifying],
                "BlmPermitMatchedOutfitterCount": len(blm_qualifying),
                "BlmPermitMatchedOutfitters": " | ".join(item["displayName"] for item in blm_qualifying),
                "BlmPermitMatchedOutfitterIds": [item["outfitterId"] for item in blm_qualifying],
                "FederalPermitMatchedOutfitterCount": len(effective),
                "FederalPermitMatchedOutfitters": " | ".join(item["displayName"] for item in effective),
                "FederalPermitMatchedOutfitterIds": [item["outfitterId"] for item in effective],
                "ConfirmedServiceOutfitterCount": len(confirmed),
                "ConfirmedServiceOutfitters": " | ".join(item["displayName"] for item in confirmed),
                "ConfirmedServiceOutfitterIds": [item["outfitterId"] for item in confirmed],
                "FederalPermitCoverageDetails": details,
                "CoverageRelationship": "FEDERAL_PERMIT_AREA_GEOMETRIC_OVERLAP",
                "UnitServiceClaimStatus": status,
                "CoverageEvidenceSource": (
                    "local_data/outfitters/outfitter-federal-service-area-evidence.internal.json; "
                    "local_data/outfitters/federal-boundaries/manifest.json; "
                    + hunt_unit_geometry_source
                ),
                "Notes": (
                    "A confirmed USFS SUP or BLM SRP area intersecting a DWR hunt-unit polygon establishes guide "
                    "authorization only on the permitted federal land inside that unit. Overlap acres and percent "
                    "describe the extent; 75% is retained only as a comparison field. An operator-confirmed service "
                    "claim is recorded separately and does not expand the federal permit boundary."
                ),
            }
        )
        rebuilt.append(row)
    return rebuilt, eligibility_by_outfitter


def update_master(
    master_rows: list[dict[str, Any]], eligibility_by_outfitter: dict[str, list[dict[str, Any]]]
) -> list[dict[str, Any]]:
    for row in master_rows:
        eligibility = sorted(
            eligibility_by_outfitter.get(row["id"], []),
            key=lambda item: (ascii_text(item["species"]), ascii_text(item["unitName"])),
        )
        unique_units = sorted({item["unitName"] for item in eligibility}, key=ascii_text)
        row["serviceArea"]["unitsServed"] = unique_units
        row.setdefault("internal", {})["unitServiceEligibility"] = eligibility
        row["internal"]["sourceNotes"] = [
            note
            for note in row["internal"].get("sourceNotes", [])
            if "unitsServed is intentionally blank" not in clean(note)
        ]
        row["internal"]["sourceNotes"].append(
            "unitsServed is populated from confirmed service claims or confirmed federal permit-area intersections"
        )
        row["internal"]["unitServiceEligibilityRule"] = {
            "thresholdPercent": THRESHOLD_PERCENT,
            "status": "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT",
            "basis": "CONFIRMED_FEDERAL_PERMIT_SCOPE_GEOMETRIC_INTERSECTION",
            "minimumOverlapToleranceAcres": MIN_OVERLAP_ACRES,
            "legacyComparisonThresholdPercent": THRESHOLD_PERCENT,
            "publicExposure": "INTERNAL_ONLY_UNTIL_RECORD_IS_CONFIRMED_OR_VETTED",
            "legalScope": "OPERATIONAL_INFERENCE_NOT_PERMIT_OR_LICENSE_ADJUDICATION",
            "confirmedClaimOverride": "CONFIRMED_OUTFITTER_SERVICE_CLAIM",
        }
    return master_rows


def update_evidence(
    evidence_payload: dict[str, Any], eligibility_by_outfitter: dict[str, list[dict[str, Any]]]
) -> dict[str, Any]:
    for row in evidence_payload["records"]:
        eligibility = eligibility_by_outfitter.get(row["outfitterId"], [])
        row["qualifyingUnitSpeciesAssociationCount"] = len(eligibility)
        row["confirmedUnitSpeciesAssociationCount"] = sum(
            item["status"] == "CONFIRMED_OUTFITTER_SERVICE_CLAIM" for item in eligibility
        )
        row["qualifyingUnits"] = sorted({item["unitName"] for item in eligibility}, key=ascii_text)
        row["unitServiceClaimStatus"] = (
            "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
            if any(item["status"] == "CONFIRMED_OUTFITTER_SERVICE_CLAIM" for item in eligibility)
            else "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
            if eligibility
            else "NO_FEDERAL_PERMIT_AREA_INTERSECTION"
        )
    evidence_payload["metadata"]["unitAssociationBoundary"] = (
        "A confirmed USFS SUP or BLM SRP area intersecting a DWR hunt-unit polygon establishes guide "
        "authorization only on the permitted federal land inside that unit. A 0.1-acre minimum overlap "
        "tolerance excludes boundary-touch artifacts."
    )
    evidence_payload["metadata"]["unitAssociationStatus"] = (
        "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT; OPERATIONAL_INFERENCE_NOT_LEGAL_DETERMINATION"
    )
    return evidence_payload


def update_internal_manifest(
    generated_at: str,
    snapshot_manifest: dict[str, Any],
    coverage_rows: list[dict[str, Any]],
    eligibility_by_outfitter: dict[str, list[dict[str, Any]]],
    hunt_units_path: Path,
    hunt_unit_geometry_source: str,
    hunt_boundary_info_path: Path | None,
) -> None:
    manifest = read_json(INTERNAL_MANIFEST_PATH)
    qualifying_rows = [
        row
        for row in coverage_rows
        if any(item.get("qualifiesAt75Percent") for item in row.get("FederalPermitCoverageDetails", []))
    ]
    threshold_outfitters = {
        item["outfitterId"]
        for row in coverage_rows
        for item in row.get("FederalPermitCoverageDetails", [])
        if item.get("qualifiesAt75Percent")
    }
    confirmed_rows = [
        row for row in coverage_rows if row["UnitServiceClaimStatus"] == "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
    ]
    manifest["metadata"]["generatedAt"] = generated_at
    manifest["source"]["huntUnitGeometry"] = hunt_unit_geometry_source
    manifest["source"]["huntUnitGeometrySha256"] = sha256(hunt_units_path)
    if hunt_boundary_info_path:
        manifest["source"]["huntBoundaryInfo"] = str(
            hunt_boundary_info_path.relative_to(ROOT)
        ).replace("\\", "/")
        manifest["source"]["huntBoundaryInfoSha256"] = sha256(hunt_boundary_info_path)
    manifest["source"]["federalBoundarySnapshotManifest"] = (
        "local_data/outfitters/federal-boundaries/manifest.json"
    )
    manifest["source"]["federalBoundarySnapshotGeneratedAt"] = snapshot_manifest["metadata"][
        "generatedAt"
    ]
    manifest["localArtifacts"].pop("provisionalCoverage", None)
    manifest["localArtifacts"]["unitEligibilityCoverage"] = (
        "local_data/outfitters/outfitter-federal-unit-coverage-review.internal.json"
    )
    manifest["counts"]["coverageRows"] = len(coverage_rows)
    manifest["counts"].pop("provisionalCoverageRows", None)
    manifest["counts"].pop("qualifyingCoverageRows", None)
    manifest["counts"].pop("qualifyingOutfitters", None)
    manifest["counts"].pop("inferredOutfitterUnitSpeciesAssociations", None)
    manifest["counts"]["exactBoundaryRows"] = sum(
        row["UnitBoundaryMatchStatus"] == "MATCHED_EXACT_NAME_OR_HUNT_CODE" for row in coverage_rows
    )
    authorized_rows = [
        row
        for row in coverage_rows
        if any(
            item.get("authorizedByFederalPermitAreaOverlap")
            for item in row.get("FederalPermitCoverageDetails", [])
        )
    ]
    authorized_outfitters = {
        item["outfitterId"]
        for row in coverage_rows
        for item in row.get("FederalPermitCoverageDetails", [])
        if item.get("authorizedByFederalPermitAreaOverlap")
    }
    manifest["counts"]["authorizedCoverageRows"] = len(authorized_rows)
    manifest["counts"]["authorizedOutfitters"] = len(authorized_outfitters)
    manifest["counts"]["authorizedOutfitterUnitSpeciesAssociations"] = sum(
        item.get("authorizedByFederalPermitAreaOverlap", False)
        for row in coverage_rows
        for item in row.get("FederalPermitCoverageDetails", [])
    )
    manifest["counts"]["legacy75PercentCoverageRows"] = len(qualifying_rows)
    manifest["counts"]["confirmedServiceClaimRows"] = len(confirmed_rows)
    manifest["counts"]["confirmedServiceClaimOutfitters"] = len(
        {
            outfitter_id
            for row in coverage_rows
            for outfitter_id in row.get("ConfirmedServiceOutfitterIds", [])
        }
    )
    manifest["counts"]["legacy75PercentOutfitters"] = len(threshold_outfitters)
    manifest["counts"]["federalPermitIntersectionAssociations"] = sum(
        item["status"] == "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
        for rows in eligibility_by_outfitter.values()
        for item in rows
    )
    manifest["counts"]["effectiveOutfitters"] = len(eligibility_by_outfitter)
    manifest["counts"]["effectiveOutfitterUnitSpeciesAssociations"] = sum(
        len(rows) for rows in eligibility_by_outfitter.values()
    )
    manifest["rules"]["unitAssociation"] = (
        "CONFIRMED_OUTFITTER_SERVICE_CLAIM identifies an operator-confirmed offering; otherwise a confirmed "
        "USFS SUP or BLM SRP area intersecting a DWR unit establishes guide authorization only on the permitted "
        "federal land inside that unit"
    )
    manifest["rules"]["legalScope"] = "OPERATIONAL_INFERENCE_NOT_PERMIT_OR_LICENSE_ADJUDICATION"
    manifest["rules"]["publicExposure"] = "Confirmed or Vetted records only; no automatic publication"
    write_json(INTERNAL_MANIFEST_PATH, manifest)


def publish_public_coverage(
    generated_at: str,
    coverage_rows: list[dict[str, Any]],
    evidence_rows: list[dict[str, Any]],
) -> dict[str, int]:
    """Publish permit-confirmed names and unit intersections without private contacts."""
    existing_public = read_json(PUBLIC_OUTFITTERS_PATH)
    vetted_rows = [row for row in existing_public if row.get("verificationStatus") == "Vetted"]
    if len(vetted_rows) != 11:
        raise ValueError(f"Expected the retained 11-row vetted public feed, found {len(vetted_rows)}")

    existing_name_by_id: dict[str, str] = {}
    for row in vetted_rows:
        listing_name = clean(row.get("listingName"))
        if listing_name:
            existing_name_by_id.setdefault(f"outfitter-{slugify(listing_name)}", listing_name)

    confirmed_evidence = {
        row["outfitterId"]: row
        for row in evidence_rows
        if clean(row.get("permitEvidenceStatus")) == "Confirmed"
    }
    public_name_by_id = {
        outfitter_id: PUBLIC_NAME_OVERRIDES.get(
            outfitter_id,
            existing_name_by_id.get(outfitter_id, clean(row.get("displayName"))),
        )
        for outfitter_id, row in confirmed_evidence.items()
    }
    if not public_name_by_id or any(not name for name in public_name_by_id.values()):
        raise ValueError("Permit-confirmed hunting outfitters must all have a public business name")

    public_coverage: list[dict[str, Any]] = []
    public_association_count = 0
    public_outfitter_ids: set[str] = set()
    for row in coverage_rows:
        effective = [
            detail
            for detail in row.get("FederalPermitCoverageDetails", [])
            if detail.get("authorizedByFederalPermitAreaOverlap") or detail.get("confirmedServiceClaim")
        ]
        if not effective:
            continue
        names = sorted(
            {public_name_by_id[detail["outfitterId"]] for detail in effective}, key=ascii_text
        )
        confirmed_claim_names = sorted(
            {
                public_name_by_id[detail["outfitterId"]]
                for detail in effective
                if detail.get("confirmedServiceClaim")
            },
            key=ascii_text,
        )
        usfs_names = sorted(
            {
                public_name_by_id[detail["outfitterId"]]
                for detail in effective
                if any(
                    identifier in USFS_FOREST_NAMES or identifier in USFS_DISTRICT_ORG_CODES
                    for identifier in detail.get("contributingFederalAreaIds", [])
                )
            },
            key=ascii_text,
        )
        blm_names = sorted(
            {
                public_name_by_id[detail["outfitterId"]]
                for detail in effective
                if any(
                    identifier in BLM_ADMIN_NAME_HINTS
                    for identifier in detail.get("contributingFederalAreaIds", [])
                )
            },
            key=ascii_text,
        )
        public_outfitter_ids.update(detail["outfitterId"] for detail in effective)
        public_association_count += len(effective)
        public_coverage.append(
            {
                "Species": clean(row.get("Species")),
                "UnitCode": clean(row.get("UnitCode")),
                "UnitName": clean(row.get("UnitName")),
                "FederalCoverageEligible": "Yes",
                "FederalPermitMatchedOutfitterCount": len(names),
                "FederalPermitMatchedOutfitters": names,
                "UsfsPermitMatchedOutfitters": usfs_names,
                "BlmPermitMatchedOutfitters": blm_names,
                "ConfirmedServiceOutfitters": confirmed_claim_names,
                "UnitServiceClaimStatus": (
                    "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
                    if confirmed_claim_names
                    else "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
                ),
                "CoverageRelationship": "CONFIRMED_FEDERAL_PERMIT_AREA_INTERSECTION",
                "MinimumOverlapToleranceAcres": MIN_OVERLAP_ACRES,
                "GeneratedAt": generated_at,
                "Notes": (
                    "Permit-confirmed outfitter coverage applies only on authorized federal land inside "
                    "this DWR unit. Unit/species/sex selection does not expand the federal permit boundary."
                ),
            }
        )

    missing_from_coverage = set(confirmed_evidence) - public_outfitter_ids
    unexpected_in_coverage = public_outfitter_ids - set(confirmed_evidence)
    if missing_from_coverage or unexpected_in_coverage or not public_coverage or not public_association_count:
        raise ValueError(
            "Public coverage must contain every and only permit-confirmed outfitter: "
            f"missing={sorted(missing_from_coverage)}, "
            f"unexpected={sorted(unexpected_in_coverage)}"
        )
    write_json(PUBLIC_COVERAGE_PATH, public_coverage)

    existing_vetted_names = {clean(row.get("listingName")) for row in vetted_rows}
    permit_only_profiles: list[dict[str, Any]] = []
    for outfitter_id, evidence in confirmed_evidence.items():
        listing_name = public_name_by_id[outfitter_id]
        if listing_name in existing_vetted_names:
            continue
        permit_only_profiles.append(
            {
                "id": outfitter_id,
                "listingName": listing_name,
                "listingType": "Outfitter",
                "certLevel": "",
                "verificationStatus": "Permit Confirmed",
                "permitEvidenceStatus": "Confirmed",
                "website": "",
                "phone": [],
                "email": [],
                "region": "Utah",
                "city": "",
                "ownerName": [],
                "speciesServed": [],
                "unitsServed": [],
                "blmDistricts": [],
                "usfsForests": [],
                "notes": (
                    "Federal outfitting/guiding permit confirmed from supplied official USFS records. "
                    "Public contact information remains withheld pending separate verification."
                ),
            }
        )
    permit_only_profiles.sort(key=lambda row: ascii_text(row["listingName"]))
    expected_permit_only = {
        public_name_by_id[outfitter_id]
        for outfitter_id in confirmed_evidence
        if public_name_by_id[outfitter_id] not in existing_vetted_names
    }
    if {row["listingName"] for row in permit_only_profiles} != expected_permit_only:
        raise ValueError("Permit-only public profiles do not match confirmed non-vetted businesses")
    published_outfitters = vetted_rows + permit_only_profiles
    write_json(PUBLIC_OUTFITTERS_PATH, published_outfitters)
    write_json(PUBLIC_CONTRACT_OUTFITTERS_PATH, published_outfitters)

    manifest = read_json(INTERNAL_MANIFEST_PATH)
    manifest["metadata"]["generatedAt"] = generated_at
    manifest["counts"]["publicVettedRows"] = len(vetted_rows)
    manifest["counts"]["publicPermitConfirmedProfiles"] = len(permit_only_profiles)
    manifest["counts"]["publicCoverageRows"] = len(public_coverage)
    manifest["counts"]["publicCoverageOutfitters"] = len(public_outfitter_ids)
    manifest["counts"]["publicCoverageAssociations"] = public_association_count
    manifest["rules"]["publicExposure"] = (
        "Vetted profiles retain approved contacts; permit-confirmed profiles publish business name and "
        "coverage only, with contacts withheld until separately verified"
    )
    write_json(INTERNAL_MANIFEST_PATH, manifest)
    return {
        "publicCoverageRows": len(public_coverage),
        "publicCoverageOutfitters": len(public_outfitter_ids),
        "publicCoverageAssociations": public_association_count,
        "publicPermitConfirmedProfiles": len(permit_only_profiles),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-boundaries", action="store_true")
    parser.add_argument(
        "--publish-public",
        action="store_true",
        help="Write the public-safe confirmed coverage contract and name-only permit profiles.",
    )
    parser.add_argument("--generated-at", default="")
    parser.add_argument("--hunt-units", default=str(HUNT_UNITS_PATH.relative_to(ROOT)))
    parser.add_argument(
        "--hunt-unit-alias-source",
        default=str(HUNT_UNITS_PATH.relative_to(ROOT)),
        help="Optional prior layer whose names and hunt-code aliases are merged by boundary ID.",
    )
    parser.add_argument(
        "--hunt-boundary-info",
        default=str(HUNT_BOUNDARY_INFO_PATH.relative_to(ROOT)),
        help="Current DWR Hunt Planner popup records used to associate hunt codes with member boundaries.",
    )
    args = parser.parse_args()
    generated_at = args.generated_at or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    hunt_units_path = Path(args.hunt_units)
    if not hunt_units_path.is_absolute():
        hunt_units_path = ROOT / hunt_units_path
    alias_source_path = Path(args.hunt_unit_alias_source) if args.hunt_unit_alias_source else None
    if alias_source_path and not alias_source_path.is_absolute():
        alias_source_path = ROOT / alias_source_path
    hunt_boundary_info_path = Path(args.hunt_boundary_info) if args.hunt_boundary_info else None
    if hunt_boundary_info_path and not hunt_boundary_info_path.is_absolute():
        hunt_boundary_info_path = ROOT / hunt_boundary_info_path
    hunt_unit_geometry_source = str(hunt_units_path.relative_to(ROOT)).replace("\\", "/")

    if args.refresh_boundaries:
        snapshot_manifest = refresh_snapshots(generated_at)
    else:
        snapshot_manifest = require_snapshots()

    transformer = Transformer.from_crs("EPSG:4326", AREA_CRS, always_xy=True)
    federal_geometries, labels = build_federal_geometries(transformer)
    hunt_index = build_hunt_geometry_index(
        transformer,
        hunt_units_path,
        alias_source_path,
        hunt_boundary_info_path,
    )

    master_rows = read_json(MASTER_PATH)
    evidence_payload = read_json(EVIDENCE_PATH)
    evidence_rows = evidence_payload["records"]
    coverage_rows = read_json(COVERAGE_PATH)
    outfitter_geometries, area_ids_by_outfitter = build_outfitter_geometries(
        evidence_rows, federal_geometries
    )
    rebuilt, eligibility_by_outfitter = update_coverage(
        coverage_rows,
        evidence_rows,
        outfitter_geometries,
        area_ids_by_outfitter,
        federal_geometries,
        hunt_index,
        labels,
        hunt_unit_geometry_source,
    )
    updated_master = update_master(master_rows, eligibility_by_outfitter)
    evidence_payload = update_evidence(evidence_payload, eligibility_by_outfitter)
    write_json(COVERAGE_PATH, rebuilt)
    write_json(MASTER_PATH, updated_master)
    write_json(EVIDENCE_PATH, evidence_payload)
    update_internal_manifest(
        generated_at,
        snapshot_manifest,
        rebuilt,
        eligibility_by_outfitter,
        hunt_units_path,
        hunt_unit_geometry_source,
        hunt_boundary_info_path,
    )
    public_counts = (
        publish_public_coverage(generated_at, rebuilt, evidence_rows)
        if args.publish_public
        else {}
    )

    qualifying_rows = [
        row
        for row in rebuilt
        if any(item.get("qualifiesAt75Percent") for item in row.get("FederalPermitCoverageDetails", []))
    ]
    threshold_outfitters = {
        item["outfitterId"]
        for row in rebuilt
        for item in row.get("FederalPermitCoverageDetails", [])
        if item.get("qualifiesAt75Percent")
    }
    confirmed_rows = [
        row for row in rebuilt if row["UnitServiceClaimStatus"] == "CONFIRMED_OUTFITTER_SERVICE_CLAIM"
    ]
    output = {
        "ok": True,
        "generatedAt": generated_at,
        "thresholdPercent": THRESHOLD_PERCENT,
        "minimumOverlapToleranceAcres": MIN_OVERLAP_ACRES,
        "federalSnapshotGeneratedAt": snapshot_manifest["metadata"]["generatedAt"],
        "coverageRows": len(rebuilt),
        "exactBoundaryRows": sum(row["UnitBoundaryMatchStatus"] == "MATCHED_EXACT_NAME_OR_HUNT_CODE" for row in rebuilt),
        "authorizedCoverageRows": sum(
            any(item.get("authorizedByFederalPermitAreaOverlap") for item in row.get("FederalPermitCoverageDetails", []))
            for row in rebuilt
        ),
        "authorizedOutfitters": len(
            {
                item["outfitterId"]
                for row in rebuilt
                for item in row.get("FederalPermitCoverageDetails", [])
                if item.get("authorizedByFederalPermitAreaOverlap")
            }
        ),
        "authorizedOutfitterUnitSpeciesAssociations": sum(
            item.get("authorizedByFederalPermitAreaOverlap", False)
            for row in rebuilt
            for item in row.get("FederalPermitCoverageDetails", [])
        ),
        "legacy75PercentCoverageRows": len(qualifying_rows),
        "confirmedServiceClaimRows": len(confirmed_rows),
        "legacy75PercentOutfitters": len(threshold_outfitters),
        "federalPermitIntersectionAssociations": sum(
            item["status"] == "FEDERAL_PERMIT_AREA_INTERSECTS_DWR_UNIT"
            for rows in eligibility_by_outfitter.values()
            for item in rows
        ),
        "effectiveOutfitters": len(eligibility_by_outfitter),
        "effectiveOutfitterUnitSpeciesAssociations": sum(
            len(rows) for rows in eligibility_by_outfitter.values()
        ),
        **public_counts,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
