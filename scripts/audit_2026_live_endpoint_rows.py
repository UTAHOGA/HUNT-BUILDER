"""Resolve 2026 UtahDraws canonical rows to retained endpoint evidence.

The audit works at hunt code, residency, point, and exact source-package
level. It does not use broad report-family labels as proof and it does not
modify canonical truth.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
SNAPSHOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results" / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_allowed_draw_odds_all_flat_rows.csv"
PLANNER = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_popup_deep_20260826_205700" / "dwr_huntplanner_hanumber_2026.csv"
OUT_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
OUT_CSV = OUT_DIR / "draw_2026_live_endpoint_rows.csv"
OUT_JSON = OUT_DIR / "draw_2026_live_endpoint_rows.json"


SPORTSMAN_ENDPOINT_BY_SPECIES = {
    "deer": "2026_sportsman_22_sportsman_deer.json",
    "elk": "2026_sportsman_23_sportsman_elk.json",
    "pronghorn": "2026_sportsman_24_sportsman_pronghorn.json",
    "moose": "2026_sportsman_25_sportsman_moose.json",
    "bison": "2026_sportsman_26_sportsman_bison.json",
    "rocky mountain bighorn sheep": "2026_sportsman_27_sportsman_rocky_mtn_bighorn_sheep.json",
    "desert bighorn sheep": "2026_sportsman_28_sportsman_desert_bighorn_sheep.json",
    "mountain goat": "2026_sportsman_29_sportsman_mountain_goat.json",
    "black bear": "2026_sportsman_30_sportsman_black_bear.json",
    "turkey": "2026_sportsman_31_sportsman_turkey.json",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def integer(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def point(value: object) -> str:
    number = integer(value)
    return str(number) if number is not None else clean(value)


def identity(code: object, residency: object, points: object) -> tuple[str, str, str]:
    return clean(code).upper(), clean(residency).lower(), point(points)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def expected_endpoint(row: dict[str, str]) -> str:
    scope = clean(row.get("source_scope")).upper()
    species = clean(row.get("species")).lower()
    mapping = {
        "YOUTH_GENERAL_SEASON_ELK": "2026_big_game_06_draw_only_youth_elk.json",
        "LIMITED_ENTRY_DEER": "2026_big_game_08_limited_entry_buck_deer.json",
        "LIMITED_ENTRY_ELK": "2026_big_game_09_limited_entry_bull_elk.json",
        "LIMITED_ENTRY_PRONGHORN": "2026_big_game_10_limited_entry_buck_pronghorn.json",
        "OIL_BULL_MOOSE": "2026_big_game_11_bull_moose.json",
        "OIL_BISON": "2026_big_game_12_bison.json",
        "OIL_DESERT_BIGHORN_SHEEP": "2026_big_game_13_desert_bighorn_sheep.json",
        "OIL_ROCKY_MTN_SHEEP": "2026_big_game_14_rocky_mtn_bighorn_sheep.json",
        "OIL_MTN_GOAT": "2026_big_game_15_mountain_goat.json",
        "BLACK_BEAR_RESTRICTED_PURSUIT": "2026_black_bear_16_black_bear_restricted_pursuit.json",
        "BLACK_BEAR": "2026_black_bear_01_black_bear.json",
        "TURKEY": "2026_turkey_03_turkey.json",
    }
    if scope == "SPORTSMAN_RANDOM_ONLY":
        return SPORTSMAN_ENDPOINT_BY_SPECIES[species]
    return mapping[scope]


def adjusted_point(row: dict[str, str]) -> tuple[str, str]:
    """Sportsman results have a source point of zero, not a blank point lane."""
    raw_point = point(row.get("points"))
    if clean(row.get("source_scope")).upper() == "SPORTSMAN_RANDOM_ONLY" and not raw_point:
        return "0", "SPORTSMAN_ZERO_POINT_SOURCE_CONVENTION"
    return raw_point, "EXACT_CANONICAL_POINT"


def values_match(canonical: dict[str, str], raw: dict[str, str]) -> bool:
    return (
        integer(canonical.get("eligible_applicants")) == integer(raw.get("ParticipantCount"))
        and integer(canonical.get("successful_applicants")) == integer(raw.get("SuccessfulCount"))
    )


def resolve(canonical: dict[str, str], matches: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    source_youth = clean(canonical.get("source_is_youth")).lower()
    if source_youth in {"true", "false"}:
        matches = [row for row in matches if clean(row.get("IsYouth")).lower() == source_youth]
    if not matches:
        return "NO_ENDPOINT_IDENTITY", []
    parity = [row for row in matches if values_match(canonical, row)]
    if len(matches) == 1:
        return ("VALUE_PARITY_DIRECT" if parity else "VALUE_MISMATCH_DIRECT"), parity
    if len(parity) == 1:
        return "VALUE_PARITY_UNIQUE_SOURCE_DIMENSION", parity
    if len(parity) > 1:
        return "AMBIGUOUS_MULTIPLE_EQUAL_ENDPOINT_ROWS", parity
    return "AMBIGUOUS_ENDPOINT_DIMENSION_VALUE_MISMATCH", []


def disposition(row: dict[str, str], status: str) -> str:
    scorable = (integer(row.get("eligible_applicants")) or 0) > 0 or (integer(row.get("successful_applicants")) or 0) > 0
    if not scorable:
        return "UNSCORABLE_NO_APPLICANT_OR_SUCCESS"
    if status in {"VALUE_PARITY_DIRECT", "VALUE_PARITY_UNIQUE_SOURCE_DIMENSION"}:
        return "CERTIFIABLE_SOURCE_VALUE_PARITY"
    return "EXCLUDE_FROM_CERTIFIABLE_SCORING_PENDING_SOURCE_RECONCILIATION"


def main() -> None:
    raw_index: dict[tuple[tuple[str, str, str], str], list[dict[str, str]]] = defaultdict(list)
    for raw in read_csv(SNAPSHOT):
        raw_index[(identity(raw.get("HuntCode"), raw.get("residency_label"), raw.get("Point")), clean(raw.get("source_json_file")))].append(raw)
    planner_index = {
        clean(row.get("hunt_code")).upper(): row
        for row in read_csv(PLANNER)
        if clean(row.get("fetch_status")) == "OK"
    }

    output: list[dict[str, str]] = []
    for canonical in read_csv(CANONICAL):
        if not clean(canonical.get("source_dataset")).startswith("UTAHDRAWS_2026_LIVE_DRAW_ODDS_REFRESH"):
            continue
        source_point, point_policy = adjusted_point(canonical)
        row_identity = identity(canonical.get("hunt_code"), canonical.get("residency"), source_point)
        endpoint = expected_endpoint(canonical)
        matches = raw_index.get((row_identity, endpoint), [])
        parity_status, equal_rows = resolve(canonical, matches)
        planner = planner_index.get(row_identity[0])
        selected = equal_rows[0] if len(equal_rows) == 1 else (matches[0] if len(matches) == 1 else None)
        output.append({
            "hunt_code": row_identity[0],
            "residency": clean(canonical.get("residency")),
            "canonical_points": point(canonical.get("points")),
            "source_comparison_points": source_point,
            "point_policy": point_policy,
            "canonical_source_file": clean(canonical.get("source_file")),
            "canonical_source_scope": clean(canonical.get("source_scope")),
            "canonical_source_is_youth": clean(canonical.get("source_is_youth")),
            "canonical_eligible_applicants": clean(canonical.get("eligible_applicants")),
            "canonical_successful_applicants": clean(canonical.get("successful_applicants")),
            "expected_snapshot_source_json_file": endpoint,
            "snapshot_matches_in_expected_endpoint": str(len(matches)),
            "snapshot_candidate_source_dimensions": " | ".join(sorted({clean(row.get("IsYouth")) for row in matches})),
            "snapshot_participant_count": clean(selected.get("ParticipantCount")) if selected else "",
            "snapshot_successful_count": clean(selected.get("SuccessfulCount")) if selected else "",
            "snapshot_selected_is_youth": clean(selected.get("IsYouth")) if selected else "",
            "parity_status": parity_status,
            "certification_disposition": disposition(canonical, parity_status),
            "planner_context_status": "DWR_PLANNER_HUNT_CODE_FOUND" if planner else "DWR_PLANNER_HUNT_CODE_NOT_IN_1433_CAPTURE",
            "planner_source_url": clean(planner.get("source_url")) if planner else "",
            "planner_res_quota": clean(planner.get("permits_2026_res")) if planner else "",
            "planner_nr_quota": clean(planner.get("permits_2026_nr")) if planner else "",
            "planner_total_quota": clean(planner.get("permits_2026_total")) if planner else "",
        })

    fields = list(output[0]) if output else []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_live_rows": len(output),
        "parity_status_counts": dict(sorted(Counter(row["parity_status"] for row in output).items())),
        "certification_disposition_counts": dict(sorted(Counter(row["certification_disposition"] for row in output).items())),
        "planner_context_counts": dict(sorted(Counter(row["planner_context_status"] for row in output).items())),
        "comparison_identity": "hunt_code + residency + point + exact expected UtahDraws endpoint package",
        "sportsman_point_policy": "Blank canonical Sportsman point maps to the endpoint's zero-point source convention.",
        "output_csv": OUT_CSV.relative_to(ROOT).as_posix(),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
