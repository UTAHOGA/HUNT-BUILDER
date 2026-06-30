from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from engine.utah_bonus_predictive.materialize import expand_collapsed_truth_rows_for_engine
from engine.utah_draw_predictive.preference_antlerless import (
    _build_retention_and_zero_growth,
    _build_truth_ladders,
    _forecast_applicant_ladder,
    _forecast_quota_for_residency,
    _target_draw_system_type,
    _to_int,
    _looks_like_standard_pool,
    build_preference_antlerless_predictions,
)


DRAW_RESULTS_LONG = REPO_ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_CSV = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
OUTPUT_DIR = REPO_ROOT / "processed_data" / "engine_resources" / "antlerless_preference"


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def db_permit_total(row: dict[str, str]) -> int:
    return _to_int(row.get("permits_2026_total")) or _to_int(row.get("permits_2026_res")) + _to_int(row.get("permits_2026_nr"))


def main() -> None:
    long_rows_raw = read_csv(DRAW_RESULTS_LONG)
    truth_rows = expand_collapsed_truth_rows_for_engine(long_rows_raw)
    db_rows = read_csv(DATABASE_CSV)
    history_years = set(range(2018, 2026))

    ladders, meta, total_drawn_by_code_year = _build_truth_ladders(truth_rows, history_years)
    retention_by_band, zero_growth = _build_retention_and_zero_growth(ladders)

    ladder_rows: list[dict[str, object]] = []
    years_by_code_res: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for draw_system_type, year, hunt_code, residency in sorted(ladders):
        years_by_code_res[(draw_system_type, hunt_code, residency)].add(year)
        for points, values in sorted(ladders[(draw_system_type, year, hunt_code, residency)].items()):
            eligible = int(values.get("eligible", 0))
            drawn = int(values.get("drawn", 0))
            ladder_rows.append(
                {
                    "actual_draw_year": year,
                    "draw_system_type": draw_system_type,
                    "hunt_code": hunt_code,
                    "hunt_name": meta.get(hunt_code, {}).get("hunt_name", ""),
                    "species": meta.get(hunt_code, {}).get("species", ""),
                    "sex_type": meta.get(hunt_code, {}).get("sex_type", ""),
                    "weapon": meta.get(hunt_code, {}).get("weapon", ""),
                    "hunt_type": meta.get(hunt_code, {}).get("hunt_type", ""),
                    "residency": residency,
                    "points": points,
                    "eligible_applicants": eligible,
                    "drawn_applicants": drawn,
                    "unsuccessful_applicants": max(eligible - drawn, 0),
                    "observed_p_draw": "" if eligible <= 0 else round(drawn / eligible, 8),
                }
            )

    rollover_rows: list[dict[str, object]] = []
    for draw_system_type, hunt_code, residency in sorted(years_by_code_res):
        years = sorted(years_by_code_res[(draw_system_type, hunt_code, residency)])
        for year in years:
            next_year = year + 1
            if next_year not in years_by_code_res[(draw_system_type, hunt_code, residency)]:
                continue
            prior = ladders[(draw_system_type, year, hunt_code, residency)]
            nxt = ladders[(draw_system_type, next_year, hunt_code, residency)]
            for points, values in sorted(prior.items()):
                unsuccessful = max(int(values.get("eligible", 0)) - int(values.get("drawn", 0)), 0)
                next_count = int(nxt.get(points + 1, {}).get("eligible", 0))
                rollover_rows.append(
                    {
                        "from_year": year,
                        "to_year": next_year,
                        "draw_system_type": draw_system_type,
                        "hunt_code": hunt_code,
                        "hunt_name": meta.get(hunt_code, {}).get("hunt_name", ""),
                        "residency": residency,
                        "prior_points": points,
                        "next_points": points + 1,
                        "prior_unsuccessful_applicants": unsuccessful,
                        "next_year_eligible_applicants": next_count,
                        "observed_retention": "" if unsuccessful <= 0 else round(next_count / unsuccessful, 8),
                    }
                )

    prediction_rows = build_preference_antlerless_predictions(truth_rows, db_rows, 2026, sorted(history_years))
    modeled_prediction_codes = {
        clean(row.get("hunt_code")).upper()
        for row in prediction_rows
        if clean(row.get("p_draw"))
    }
    accounted_no_prior_codes = {
        clean(row.get("hunt_code")).upper()
        for row in prediction_rows
        if "ANTLERLESS_CURRENT_TARGET_NO_PRIOR_LADDER_NO_PUBLIC_P_DRAW" in clean(row.get("reason_codes"))
    }

    current_rows: list[dict[str, object]] = []
    for row in db_rows:
        draw_system_type = _target_draw_system_type(row)
        if not draw_system_type or not _looks_like_standard_pool(row):
            continue
        hunt_code = clean(row.get("hunt_code")).upper()
        if not hunt_code:
            continue
        source_years = sorted(
            {
                year
                for (system, code, _residency), years in years_by_code_res.items()
                if system == draw_system_type and code == hunt_code
                for year in years
            }
        )
        permit_total = db_permit_total(row)
        if hunt_code in modeled_prediction_codes:
            status = "MODELED_FROM_ENGINE_RESOURCE"
        elif hunt_code in accounted_no_prior_codes:
            status = "ACCOUNTED_NO_PRIOR_LADDER_NO_PUBLIC_P_DRAW"
        elif permit_total <= 0:
            status = "HOLD_NO_2026_PERMIT_AUTHORITY"
        elif not source_years:
            status = "HOLD_NO_PRIOR_LADDER"
        else:
            status = "REVIEW_HISTORY_EXISTS_NOT_MODELED"
        current_rows.append(
            {
                "hunt_code": hunt_code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "weapon": clean(row.get("weapon")),
                "hunt_type": clean(row.get("hunt_type")),
                "hunt_class": clean(row.get("hunt_class")),
                "draw_system_type": draw_system_type,
                "permits_2026_res": clean(row.get("permits_2026_res")),
                "permits_2026_nr": clean(row.get("permits_2026_nr")),
                "permits_2026_total": clean(row.get("permits_2026_total")),
                "history_years": ",".join(str(year) for year in source_years),
                "engine_resource_status": status,
            }
        )

    forecast_seed_rows: list[dict[str, object]] = []
    current_by_code = {row["hunt_code"]: row for row in current_rows}
    for draw_system_type, hunt_code, residency in sorted(years_by_code_res):
        current = current_by_code.get(hunt_code)
        if not current:
            continue
        years = sorted(years_by_code_res[(draw_system_type, hunt_code, residency)])
        if not years:
            continue
        latest_year = max(years)
        latest_ladder = ladders[(draw_system_type, latest_year, hunt_code, residency)]
        forecast_ladder = _forecast_applicant_ladder(latest_ladder, retention_by_band, zero_growth)
        forecast_quota = _forecast_quota_for_residency(
            hunt_code,
            residency,
            db_permit_total(current),
            latest_year,
            total_drawn_by_code_year,
        )
        for points, projected in sorted(forecast_ladder.items()):
            forecast_seed_rows.append(
                {
                    "forecast_year": 2026,
                    "draw_system_type": draw_system_type,
                    "hunt_code": hunt_code,
                    "residency": residency,
                    "source_latest_year": latest_year,
                    "source_years": ",".join(str(year) for year in years),
                    "points": points,
                    "projected_applicants": projected,
                    "forecast_quota": forecast_quota,
                    "resource_status": current["engine_resource_status"],
                }
            )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(
        OUTPUT_DIR / "antlerless_preference_historical_ladders_2018_2025.csv",
        ladder_rows,
        [
            "actual_draw_year",
            "draw_system_type",
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "weapon",
            "hunt_type",
            "residency",
            "points",
            "eligible_applicants",
            "drawn_applicants",
            "unsuccessful_applicants",
            "observed_p_draw",
        ],
    )
    write_csv(
        OUTPUT_DIR / "antlerless_preference_rollover_observations_2018_2025.csv",
        rollover_rows,
        [
            "from_year",
            "to_year",
            "draw_system_type",
            "hunt_code",
            "hunt_name",
            "residency",
            "prior_points",
            "next_points",
            "prior_unsuccessful_applicants",
            "next_year_eligible_applicants",
            "observed_retention",
        ],
    )
    write_csv(
        OUTPUT_DIR / "antlerless_preference_current_targets_2026.csv",
        current_rows,
        [
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "weapon",
            "hunt_type",
            "hunt_class",
            "draw_system_type",
            "permits_2026_res",
            "permits_2026_nr",
            "permits_2026_total",
            "history_years",
            "engine_resource_status",
        ],
    )
    write_csv(
        OUTPUT_DIR / "antlerless_preference_forecast_seed_2026.csv",
        forecast_seed_rows,
        [
            "forecast_year",
            "draw_system_type",
            "hunt_code",
            "residency",
            "source_latest_year",
            "source_years",
            "points",
            "projected_applicants",
            "forecast_quota",
            "resource_status",
        ],
    )

    summary = {
        "source_truth_file": str(DRAW_RESULTS_LONG.relative_to(REPO_ROOT)).replace("\\", "/"),
        "source_database_file": str(DATABASE_CSV.relative_to(REPO_ROOT)).replace("\\", "/"),
        "history_years": sorted(history_years),
        "historical_ladder_rows": len(ladder_rows),
        "historical_hunt_codes": len({row["hunt_code"] for row in ladder_rows}),
        "rollover_observation_rows": len(rollover_rows),
        "current_target_codes": len(current_rows),
        "current_status_counts": dict(Counter(row["engine_resource_status"] for row in current_rows)),
        "prediction_rows_from_current_engine": len(prediction_rows),
        "prediction_hunt_codes_from_current_engine": len(modeled_prediction_codes),
        "accounted_no_prior_ladder_hunt_codes_from_current_engine": len(accounted_no_prior_codes),
        "retention_by_band": retention_by_band,
        "zero_point_growth_factor": zero_growth,
        "outputs": {
            "historical_ladders": str((OUTPUT_DIR / "antlerless_preference_historical_ladders_2018_2025.csv").relative_to(REPO_ROOT)).replace("\\", "/"),
            "rollover_observations": str((OUTPUT_DIR / "antlerless_preference_rollover_observations_2018_2025.csv").relative_to(REPO_ROOT)).replace("\\", "/"),
            "current_targets": str((OUTPUT_DIR / "antlerless_preference_current_targets_2026.csv").relative_to(REPO_ROOT)).replace("\\", "/"),
            "forecast_seed": str((OUTPUT_DIR / "antlerless_preference_forecast_seed_2026.csv").relative_to(REPO_ROOT)).replace("\\", "/"),
        },
    }
    (OUTPUT_DIR / "antlerless_preference_engine_resource_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    md = [
        "# Antlerless Preference Engine Resource",
        "",
        "This is a derived engine resource. It does not overwrite master truth.",
        "",
        f"- Historical ladder rows: {summary['historical_ladder_rows']}",
        f"- Historical hunt codes: {summary['historical_hunt_codes']}",
        f"- Rollover observation rows: {summary['rollover_observation_rows']}",
        f"- Current target codes: {summary['current_target_codes']}",
        f"- Current status counts: {summary['current_status_counts']}",
        f"- Prediction rows from current engine: {summary['prediction_rows_from_current_engine']}",
        f"- Prediction hunt codes from current engine: {summary['prediction_hunt_codes_from_current_engine']}",
        "",
        "Outputs:",
        "",
        *[f"- `{path}`" for path in summary["outputs"].values()],
    ]
    (OUTPUT_DIR / "antlerless_preference_engine_resource.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
