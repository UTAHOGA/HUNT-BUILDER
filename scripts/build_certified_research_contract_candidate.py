#!/usr/bin/env python3
"""Build a non-production split Research contract from the frozen forecast.

The complete R2 review snapshot supplies the existing non-draw/reference lanes.
Frozen prediction rows replace matching forecastable rows and add any new
forecast keys.  Outputs are written only to a new audit candidate directory.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_ROOT = ROOT / "audits" / "prediction_blind_backtests" / "2025_to_2026_truth_2018_2026_20260827_certification_candidate"
REVIEW_ROOT = CANDIDATE_ROOT / "r2_review_copy_2026-08-27" / "r2_snapshot" / "processed_data"
DEFAULT_OUTPUT = CANDIDATE_ROOT / "research_split_contract_candidate_2026-08-27"
FROZEN_PREDICTION = ROOT / "processed_data" / "draw_reality_engine_predictive_v2.csv"
LOCAL_INDEX = ROOT / "processed_data" / "hunt_research_2026_split" / "hunt_research_2026.index.json"
FROZEN_SHA256 = "9e4c0f1a66678cd63df88512e45ba71d63746a6b21d7e4038fecb142f40e9d5e"


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def code(value: object) -> str:
    return clean(value).upper()


def residency(value: object) -> str:
    return "Nonresident" if clean(value).lower() in {"nonresident", "non-resident", "nr"} else "Resident"


def point(value: object) -> str:
    raw = clean(value)
    try:
        parsed = float(raw)
    except ValueError:
        return raw
    return str(int(parsed)) if parsed.is_integer() else str(parsed)


def draw_pool(value: object) -> str:
    return clean(value).lower() or "standard"


def row_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (code(row.get("hunt_code")), residency(row.get("residency")), point(row.get("points")), draw_pool(row.get("draw_pool")))


def group_key(row: dict[str, object]) -> tuple[str, str, str]:
    return row_key(row)[:2] + (draw_pool(row.get("draw_pool")),)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> object:
    with path.open("r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader), list(reader.fieldnames or [])


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def merge_row(base: dict[str, object], prediction: dict[str, str]) -> dict[str, object]:
    """Preserve all hosted compatibility fields; replace nonblank frozen facts."""
    merged: dict[str, object] = dict(base)
    for field, value in prediction.items():
        if clean(value):
            merged[field] = value
        elif field not in merged:
            merged[field] = value
    # This retired field is used only if someone intentionally enables legacy
    # fallback.  Derive it from the frozen forecast rather than carrying old odds.
    if clean(prediction.get("p_draw_pct")):
        merged["display_odds_pct"] = prediction["p_draw_pct"]
    return merged


def representative(rows: list[dict[str, str]], preferred_point: str = "") -> dict[str, str]:
    if preferred_point:
        for row in rows:
            if point(row.get("points")) == preferred_point:
                return row
    def sort_key(row: dict[str, str]) -> tuple[float, str]:
        raw = point(row.get("points"))
        try:
            return (float(raw), raw)
        except ValueError:
            return (float("inf"), raw)
    return sorted(rows, key=sort_key)[0]


def union_fields(rows: list[dict[str, object]], initial: list[str]) -> list[str]:
    fields: list[str] = []
    seen: set[str] = set()
    for field in initial:
        if field not in seen:
            fields.append(field)
            seen.add(field)
    for row in rows:
        for field in row:
            if field not in seen:
                fields.append(field)
                seen.add(field)
    return fields


def build() -> dict[str, object]:
    if DEFAULT_OUTPUT.exists():
        raise RuntimeError(f"Refusing to overwrite existing candidate: {DEFAULT_OUTPUT}")
    if not REVIEW_ROOT.exists():
        raise RuntimeError(f"R2 review snapshot missing: {REVIEW_ROOT}")
    if sha256(FROZEN_PREDICTION) != FROZEN_SHA256:
        raise RuntimeError("The local predictive CSV no longer matches the frozen certification hash.")

    out = DEFAULT_OUTPUT / "processed_data"
    summary_source = REVIEW_ROOT / "hunt_research_2026_summary.json"
    ladder_source = REVIEW_ROOT / "hunt_research_2026_ladder.json"
    details_source = REVIEW_ROOT / "hunt_research_2026_split" / "hunt_research_2026.details.json"
    index_source = REVIEW_ROOT / "hunt_research_2026_split" / "hunt_research_2026.index.json"
    point_ladder_source = REVIEW_ROOT / "point_ladder_view.csv"
    for path in (summary_source, ladder_source, details_source, index_source, point_ladder_source, FROZEN_PREDICTION, LOCAL_INDEX):
        if not path.exists():
            raise RuntimeError(f"Required candidate input is missing: {path}")

    forecast_rows, forecast_fields = read_csv(FROZEN_PREDICTION)
    forecast_by_key = {row_key(row): row for row in forecast_rows}
    if len(forecast_by_key) != len(forecast_rows):
        raise RuntimeError("Frozen forecast contains duplicate Research contract identity keys.")
    forecast_by_group: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in forecast_rows:
        forecast_by_group[group_key(row)].append(row)

    summary_base = read_json(summary_source)
    ladder_base = read_json(ladder_source)
    details_base = read_json(details_source)
    index_base = read_json(index_source)
    local_index = read_json(LOCAL_INDEX)
    point_ladder_base, point_ladder_fields = read_csv(point_ladder_source)
    if not all(isinstance(value, list) for value in (summary_base, ladder_base, index_base, local_index)) or not isinstance(details_base, dict):
        raise RuntimeError("Review snapshot has an unexpected Research contract shape.")

    summary_out: list[dict[str, object]] = []
    summary_groups: set[tuple[str, str, str]] = set()
    summary_exact_overlays = 0
    summary_group_overlays = 0
    for row in summary_base:
        base = dict(row)
        key = row_key(base)
        group = group_key(base)
        summary_groups.add(group)
        prediction = forecast_by_key.get(key)
        if prediction:
            summary_exact_overlays += 1
        elif group in forecast_by_group:
            prediction = representative(forecast_by_group[group], point(base.get("points")))
            summary_group_overlays += 1
        summary_out.append(merge_row(base, prediction) if prediction else base)
    for group, predictions in sorted(forecast_by_group.items()):
        if group not in summary_groups:
            summary_out.append(dict(representative(predictions)))

    ladder_out: list[dict[str, object]] = []
    ladder_keys: set[tuple[str, str, str, str]] = set()
    ladder_overlays = 0
    for row in ladder_base:
        base = dict(row)
        key = row_key(base)
        ladder_keys.add(key)
        prediction = forecast_by_key.get(key)
        if prediction:
            ladder_out.append(merge_row(base, prediction))
            ladder_overlays += 1
        else:
            ladder_out.append(base)
    ladder_appends = [dict(row) for key, row in forecast_by_key.items() if key not in ladder_keys]
    ladder_out.extend(ladder_appends)

    point_out: list[dict[str, object]] = []
    point_keys: set[tuple[str, str, str, str]] = set()
    point_overlays = 0
    for row in point_ladder_base:
        base = dict(row)
        key = row_key(base)
        point_keys.add(key)
        prediction = forecast_by_key.get(key)
        if prediction:
            point_out.append(merge_row(base, prediction))
            point_overlays += 1
        else:
            point_out.append(base)
    point_appends = [dict(row) for key, row in forecast_by_key.items() if key not in point_keys]
    point_out.extend(point_appends)

    summary_by_code: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in summary_out:
        if code(row.get("hunt_code")):
            summary_by_code[code(row.get("hunt_code"))].append(row)
    detail_bundle = dict(details_base)
    detail_map = dict(details_base.get("details_by_hunt_code") or {})
    for hunt_code, rows in summary_by_code.items():
        existing = dict(detail_map.get(hunt_code) or {})
        existing.update(
            {
                "hunt_code": hunt_code,
                "research_summary_rows": rows,
                "research_summary_row_count": len(rows),
                "candidate_source": "FROZEN_UNIFIED_FORECAST_OVERLAY",
                "candidate_frozen_prediction_sha256": FROZEN_SHA256,
            }
        )
        detail_map[hunt_code] = existing
    detail_bundle.update(
        {
            "details_by_hunt_code": detail_map,
            "bundled_hunt_count": len(detail_map),
            "candidate_source": "FROZEN_UNIFIED_FORECAST_OVERLAY",
            "candidate_frozen_prediction_sha256": FROZEN_SHA256,
        }
    )

    index_by_code = {code(row.get("hunt_code")): dict(row) for row in index_base if code(row.get("hunt_code"))}
    for row in local_index:
        hunt_code = code(row.get("hunt_code"))
        if hunt_code:
            index_by_code[hunt_code] = {**index_by_code.get(hunt_code, {}), **dict(row)}
    for hunt_code, rows in summary_by_code.items():
        representative_row = representative([{key: clean(value) for key, value in row.items()} for row in rows])
        index_row = index_by_code.get(hunt_code, {"hunt_code": hunt_code})
        for field in ("hunt_name", "species", "hunt_type", "hunt_class", "weapon", "sex_type", "draw_2026_system_type", "availability_status"):
            if not clean(index_row.get(field)) and clean(representative_row.get(field)):
                index_row[field] = representative_row[field]
        index_row["research_summary_row_count"] = len(rows)
        index_row["detail_path"] = f"hunts/{hunt_code}.json"
        index_by_code[hunt_code] = index_row
    index_out = [index_by_code[hunt_code] for hunt_code in sorted(index_by_code)]

    write_json(out / "hunt_research_2026_summary.json", summary_out)
    write_json(out / "hunt_research_2026_ladder.json", ladder_out)
    write_json(out / "hunt_research_2026_split" / "hunt_research_2026.index.json", index_out)
    write_json(out / "hunt_research_2026_split" / "hunt_research_2026.details.json", detail_bundle)
    write_csv(out / "point_ladder_view.csv", point_out, union_fields(point_out, point_ladder_fields + forecast_fields))

    candidate_paths = {
        "summary": out / "hunt_research_2026_summary.json",
        "ladder": out / "hunt_research_2026_ladder.json",
        "index": out / "hunt_research_2026_split" / "hunt_research_2026.index.json",
        "details": out / "hunt_research_2026_split" / "hunt_research_2026.details.json",
        "point_ladder": out / "point_ladder_view.csv",
    }
    timestamp = datetime.now(timezone.utc).isoformat()
    audit = {
        "schema_version": "1.0.0",
        "generated_at_utc": timestamp,
        "mode": "LOCAL_CANDIDATE_NO_PROCESSED_DATA_OR_R2_WRITE",
        "frozen_prediction": {
            "path": str(FROZEN_PREDICTION.relative_to(ROOT)).replace("\\", "/"),
            "sha256": FROZEN_SHA256,
            "rows": len(forecast_rows),
            "fields": len(forecast_fields),
        },
        "overlay": {
            "summary_exact_overlays": summary_exact_overlays,
            "summary_group_overlays": summary_group_overlays,
            "summary_new_groups": len(summary_out) - len(summary_base),
            "ladder_exact_overlays": ladder_overlays,
            "ladder_new_rows": len(ladder_appends),
            "point_ladder_exact_overlays": point_overlays,
            "point_ladder_new_rows": len(point_appends),
            "preserved_reference_rows": len(ladder_base) - ladder_overlays,
        },
        "outputs": {
            label: {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
            for label, path in candidate_paths.items()
        },
    }
    write_json(DEFAULT_OUTPUT / "candidate_build_audit.json", audit)
    return audit


if __name__ == "__main__":
    result = build()
    print("CERTIFIED_RESEARCH_CONTRACT_CANDIDATE=PASS")
    print(f"OUTPUT={DEFAULT_OUTPUT.relative_to(ROOT)}")
    print(json.dumps(result["overlay"], sort_keys=True))
