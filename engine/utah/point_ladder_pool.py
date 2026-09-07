from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path
from typing import Iterable


REPO = Path(__file__).resolve().parents[2]

DEFAULT_PROCESSED_ROOT = REPO / "processed_data"
DEFAULT_LADDER_FILE = "point_ladder_view.csv"
DEFAULT_HISTORY_FILE = "draw_reality_engine_v2.csv"
DEFAULT_PREDICTIVE_FILE = "draw_reality_engine_predictive_v2.csv"

DWR_FIELDS = [
    "point",
    "applicants",
    "bonus_permits",
    "regular_permits",
    "total_permits",
    "success_ratio",
    "dwr_result_display",
    "max_point_pool_boundary",
    "random_pool_start_point",
    "point_pool_zone",
    "historical_result_pool",
    "p_max_pool_mean",
    "p_random_mean",
    "p_draw_mean",
    "forecast_applicants_at_level",
    "forecast_applicants_above",
    "quota_source_status",
    "quota_source_year",
    "quota_source_file",
    "quota_2026_total",
    "quota_2026_max_pool",
    "quota_2026_random_pool",
    "projected_2026_max_cutoff_point",
    "projected_2026_random_pool_start_point",
    "is_2026_max_point_pool",
    "is_2026_mixed_cutoff",
    "is_2026_random_pool",
    "data_cutoff_date",
    "reason_codes",
    "display_2025_draw_results",
    "display_2026_max_point_pool",
    "display_2026_random_draw",
    "random_draw_model_source",
]


def _read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _text(value: object) -> str:
    return str(value if value is not None else "").strip()


def _norm_key(value: object) -> str:
    return _text(value).upper()


def _norm_residency(value: object) -> str:
    text = _text(value).lower()
    if text in {"resident", "res"}:
        return "Resident"
    if text in {"nonresident", "non-resident", "non res", "nonres"}:
        return "Nonresident"
    return _text(value)


def _norm_draw_pool(value: object) -> str:
    text = _text(value)
    return text or "standard"


def _to_float(value: object) -> float | None:
    text = _text(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_int(value: object) -> int | None:
    parsed = _to_float(value)
    if parsed is None:
        return None
    return int(parsed)


def _row_key(row: dict[str, str]) -> tuple[str, str, int | None, str]:
    return (
        _norm_key(row.get("hunt_code")),
        _norm_residency(row.get("residency")),
        _to_int(row.get("points")),
        _norm_draw_pool(row.get("draw_pool")),
    )


def _group_key(row: dict[str, str]) -> tuple[str, str, str]:
    return (
        _norm_key(row.get("hunt_code")),
        _norm_residency(row.get("residency")),
        _norm_draw_pool(row.get("draw_pool")),
    )


def _history_key(row: dict[str, str]) -> tuple[str, str, int | None, str]:
    return (
        _norm_key(row.get("hunt_code")),
        _norm_residency(row.get("residency")),
        _to_int(row.get("points")),
        _norm_draw_pool(row.get("draw_pool")),
    )


def _latest_year(rows: list[dict[str, str]], fallback: int = 2025) -> int:
    years = [_to_int(row.get("year")) for row in rows]
    years = [year for year in years if year is not None and year <= fallback]
    return max(years) if years else fallback


def _format_one_decimal(value: float) -> str:
    return f"{value:.1f}"


def format_historical_draw_result(applicants: object, total_permits: object, success_ratio: object = "") -> str:
    total = _to_float(total_permits)
    if total is None or total <= 0:
        return ""

    ratio_text = _text(success_ratio)
    match = re.search(r"1\s*in\s*([0-9]+(?:\.[0-9]+)?)", ratio_text, flags=re.IGNORECASE)
    if match:
        # Historical results are displayed exactly as DWR prints the Success
        # Ratio. The count fields remain the calculation authority elsewhere.
        return ratio_text

    applicant_count = _to_float(applicants)
    denominator = applicant_count / total if applicant_count is not None and applicant_count > 0 else None

    if denominator is None or denominator <= 0:
        return ""

    return f"1 in {_format_one_decimal(denominator)}"


def format_modeled_draw_result(percent_value: object) -> str:
    percent = _to_float(percent_value)
    if percent is None:
        return ""
    if percent <= 0:
        return "No modeled chance"
    capped = min(100.0, max(0.0, percent))
    percent_text = f"{int(capped)}%" if capped.is_integer() else f"{float(f'{capped:.1f}')}%"
    if capped >= 99.9:
        return f"~1 in 1 or {percent_text}"
    denominator = 100.0 / capped
    if denominator < 10:
        denominator_text = str(float(f"{denominator:.1f}")).rstrip("0").rstrip(".")
    else:
        denominator_text = str(round(denominator))
    return f"~1 in {denominator_text} or {percent_text}"


def _prediction_percent(row: dict[str, str]) -> tuple[float | None, str]:
    p_random = _to_float(row.get("p_random_pool"))
    if p_random is not None:
        return p_random * 100.0, "p_random_pool"
    p_random_pct = _to_float(row.get("p_random_pool_pct"))
    if p_random_pct is not None:
        return p_random_pct, "p_random_pool_pct"
    random_odds = _to_float(row.get("random_draw_odds_2026"))
    if random_odds is not None:
        return random_odds, "random_draw_odds_2026"
    return None, ""


def _max_pool_percent(row: dict[str, str]) -> tuple[float | None, str]:
    p_max = _to_float(row.get("p_max_pool_mean"))
    if p_max is not None:
        return p_max * 100.0, "p_max_pool_mean"
    p_bonus = _to_float(row.get("p_bonus_pool"))
    if p_bonus is not None:
        return p_bonus * 100.0, "p_bonus_pool"
    p_reserved = _to_float(row.get("p_reserved_mean"))
    if p_reserved is not None:
        return p_reserved * 100.0, "p_reserved_mean"
    max_projection = _to_float(row.get("max_pool_projection_2026"))
    if max_projection is not None:
        return max_projection, "max_pool_projection_2026"
    return None, ""


def _draw_percent(row: dict[str, str]) -> tuple[float | None, str]:
    p_draw = _to_float(row.get("p_draw_mean"))
    if p_draw is not None:
        return p_draw * 100.0, "p_draw_mean"
    p_draw = _to_float(row.get("p_draw"))
    if p_draw is not None:
        return p_draw * 100.0, "p_draw"
    p_draw_pct = _to_float(row.get("p_draw_pct"))
    if p_draw_pct is not None:
        return p_draw_pct, "p_draw_pct"
    return None, ""


def _classify_prediction_zone(prediction: dict[str, str], points: int | None, random_start: int | None) -> str:
    explicit = _text(prediction.get("point_pool_zone"))
    if explicit:
        return explicit
    max_percent, _ = _max_pool_percent(prediction)
    if max_percent is not None:
        if max_percent >= 99.9:
            return "max_pool_guaranteed"
        if max_percent > 0:
            return "max_pool_cutoff_mixed"
        if points is not None and random_start is not None and points <= random_start:
            return "random_pool"
    return ""


def _latest_history_by_key(history_rows: list[dict[str, str]], source_year: int) -> dict[tuple[str, str, int | None, str], dict[str, str]]:
    latest: dict[tuple[str, str, int | None, str], dict[str, str]] = {}
    for row in history_rows:
        if _to_int(row.get("year")) != source_year:
            continue
        key = _history_key(row)
        if key[2] is None:
            continue
        latest[key] = row
    return latest


def _boundaries(history_rows: list[dict[str, str]], source_year: int) -> dict[tuple[str, str, str], dict[str, int]]:
    bonus_points: dict[tuple[str, str, str], list[int]] = {}
    for row in history_rows:
        if _to_int(row.get("year")) != source_year:
            continue
        points = _to_int(row.get("points"))
        if points is None:
            continue
        bonus_permits = _to_float(row.get("bonus_permits")) or 0
        if bonus_permits <= 0:
            continue
        bonus_points.setdefault(_group_key(row), []).append(points)

    return {
        group: {
            "max_point_pool_boundary": min(points),
            "random_pool_start_point": min(points) - 1,
        }
        for group, points in bonus_points.items()
        if points
    }


def enrich_ladder_rows(
    ladder_rows: list[dict[str, str]],
    history_rows: list[dict[str, str]],
    predictive_rows: list[dict[str, str]],
    *,
    source_year: int | None = None,
) -> tuple[list[dict[str, str]], dict[str, object]]:
    selected_source_year = source_year or _latest_year(history_rows)
    history_by_key = _latest_history_by_key(history_rows, selected_source_year)
    predictive_by_key = {_row_key(row): row for row in predictive_rows if _row_key(row)[2] is not None}
    boundaries_by_group = _boundaries(history_rows, selected_source_year)

    enriched: list[dict[str, str]] = []
    max_rows = 0
    random_rows = 0
    historical_random_successes = 0
    historical_blank_rows = 0

    for row in ladder_rows:
        next_row = dict(row)
        key = _row_key(row)
        group = (key[0], key[1], key[3])
        history = history_by_key.get(key, {})
        prediction = predictive_by_key.get(key, {})
        boundary = boundaries_by_group.get(group, {})
        points = key[2]

        applicants = history.get("eligible_applicants", "")
        bonus_permits = history.get("bonus_permits", "")
        regular_permits = history.get("regular_permits", "")
        total_permits = history.get("total_permits", "")
        success_ratio = history.get("success_ratio", "")

        next_row["point"] = "" if points is None else str(points)
        next_row["applicants"] = applicants
        next_row["bonus_permits"] = bonus_permits
        next_row["regular_permits"] = regular_permits
        next_row["total_permits"] = total_permits
        next_row["success_ratio"] = success_ratio
        next_row["dwr_result_display"] = format_historical_draw_result(applicants, total_permits, success_ratio)

        max_boundary = boundary.get("max_point_pool_boundary")
        random_start = boundary.get("random_pool_start_point")
        next_row["max_point_pool_boundary"] = "" if max_boundary is None else str(max_boundary)
        next_row["random_pool_start_point"] = "" if random_start is None else str(random_start)

        row_bonus = _to_float(bonus_permits) or 0
        row_total = _to_float(total_permits) or 0
        row_regular = _to_float(regular_permits) or 0
        historical_zone = ""
        historical_pool = ""
        if points is not None and max_boundary is not None and random_start is not None:
            if points >= max_boundary and row_bonus > 0:
                historical_zone = "max_point_pool"
                historical_pool = "max_point_pool"
                max_rows += 1
            elif points <= random_start:
                historical_zone = "random_pool"
                random_rows += 1
                if row_total > 0:
                    historical_pool = "random_pool"
                    if row_regular > 0:
                        historical_random_successes += 1

        prediction_max_percent, _ = _max_pool_percent(prediction)
        prediction_random_percent, random_source = _prediction_percent(prediction)
        prediction_draw_percent, _ = _draw_percent(prediction)
        prediction_zone = _classify_prediction_zone(prediction, points, random_start)

        next_row["point_pool_zone"] = prediction_zone or historical_zone
        next_row["historical_result_pool"] = historical_pool
        next_row["p_max_pool_mean"] = "" if prediction_max_percent is None else f"{prediction_max_percent / 100.0:.6f}"
        next_row["p_random_mean"] = "" if prediction_random_percent is None else f"{prediction_random_percent / 100.0:.6f}"
        next_row["p_draw_mean"] = "" if prediction_draw_percent is None else f"{prediction_draw_percent / 100.0:.6f}"
        next_row["forecast_applicants_at_level"] = prediction.get("forecast_applicants_at_level", "")
        next_row["forecast_applicants_above"] = prediction.get("forecast_applicants_above", "")
        next_row["quota_source_status"] = prediction.get("quota_source_status", "")
        next_row["quota_source_year"] = prediction.get("quota_source_year", "")
        next_row["quota_source_file"] = prediction.get("quota_source_file", "")
        next_row["quota_2026_total"] = prediction.get("quota_2026_total", "")
        next_row["quota_2026_max_pool"] = prediction.get("quota_2026_max_pool", "")
        next_row["quota_2026_random_pool"] = prediction.get("quota_2026_random_pool", "")
        next_row["projected_2026_max_cutoff_point"] = prediction.get("projected_2026_max_cutoff_point", "")
        next_row["projected_2026_random_pool_start_point"] = prediction.get("projected_2026_random_pool_start_point", "")
        next_row["is_2026_max_point_pool"] = prediction.get("is_2026_max_point_pool", "")
        next_row["is_2026_mixed_cutoff"] = prediction.get("is_2026_mixed_cutoff", "")
        next_row["is_2026_random_pool"] = prediction.get("is_2026_random_pool", "")
        next_row["data_cutoff_date"] = prediction.get("data_cutoff_date", "")
        next_row["reason_codes"] = prediction.get("reason_codes", "")
        if prediction.get("status"):
            next_row["status"] = prediction.get("status", "")
        next_row["display_2025_draw_results"] = next_row["dwr_result_display"] if row_total > 0 else ""
        if not next_row["display_2025_draw_results"]:
            historical_blank_rows += 1

        next_row["display_2026_max_point_pool"] = (
            format_modeled_draw_result(prediction_max_percent)
            if prediction_zone in {"max_pool_guaranteed", "max_pool_cutoff_mixed"} and prediction_max_percent is not None
            else ""
        )

        random_percent = prediction_random_percent
        if random_percent is None:
            random_percent, random_source = _prediction_percent(row)
        next_row["display_2026_random_draw"] = (
            format_modeled_draw_result(random_percent)
            if prediction_zone in {"random_pool", "max_pool_cutoff_mixed"} and random_percent is not None
            else ""
        )
        next_row["random_draw_model_source"] = random_source if next_row["display_2026_random_draw"] else ""
        enriched.append(next_row)

    summary = {
        "source_year": selected_source_year,
        "ladder_rows": len(ladder_rows),
        "history_rows_used": sum(1 for row in history_rows if _to_int(row.get("year")) == selected_source_year),
        "groups_with_max_point_boundary": len(boundaries_by_group),
        "modeled_max_point_pool_rows": max_rows,
        "modeled_random_pool_rows": random_rows,
        "historical_random_pool_success_rows": historical_random_successes,
        "historical_blank_rows": historical_blank_rows,
    }
    return enriched, summary


def enrich_ladder_file(
    processed_root: Path,
    *,
    ladder_file: str = DEFAULT_LADDER_FILE,
    history_file: str = DEFAULT_HISTORY_FILE,
    predictive_file: str = DEFAULT_PREDICTIVE_FILE,
    source_year: int | None = None,
) -> dict[str, object]:
    ladder_path = processed_root / ladder_file
    history_path = processed_root / history_file
    predictive_path = processed_root / predictive_file

    ladder_headers, ladder_rows = _read_csv(ladder_path)
    _, history_rows = _read_csv(history_path)
    _, predictive_rows = _read_csv(predictive_path)
    enriched_rows, summary = enrich_ladder_rows(ladder_rows, history_rows, predictive_rows, source_year=source_year)
    headers = list(dict.fromkeys([*ladder_headers, *DWR_FIELDS]))
    _write_csv(ladder_path, headers, enriched_rows)
    summary.update(
        {
            "ladder_file": str(ladder_path),
            "history_file": str(history_path),
            "predictive_file": str(predictive_path),
            "columns_added_or_verified": DWR_FIELDS,
        }
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Enrich point ladder rows with DWR historical pool boundaries and display fields.")
    parser.add_argument("--processed-root", type=Path, default=DEFAULT_PROCESSED_ROOT)
    parser.add_argument("--ladder-file", default=DEFAULT_LADDER_FILE)
    parser.add_argument("--history-file", default=DEFAULT_HISTORY_FILE)
    parser.add_argument("--predictive-file", default=DEFAULT_PREDICTIVE_FILE)
    parser.add_argument("--source-year", type=int, default=None)
    args = parser.parse_args(argv)
    summary = enrich_ladder_file(
        args.processed_root,
        ladder_file=args.ladder_file,
        history_file=args.history_file,
        predictive_file=args.predictive_file,
        source_year=args.source_year,
    )
    for key, value in summary.items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
