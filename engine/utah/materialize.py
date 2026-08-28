"""Materialize Utah predictions into the processed CSV contract."""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence

from .constants import DEFAULT_PREDICTION_YEAR, LEGACY_OUTPUT_FIELDS, MODEL_VERSION, REQUIRED_MODELED_FIELDS, RULE_VERSION


def _num(value: object) -> float | None:
    if value is None:
        return None
    try:
        text = str(value).strip()
    except Exception:
        return None
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_percent(value: object) -> float | None:
    number = _num(value)
    if number is None:
        return None
    return number * 100.0 if number <= 1.0 else number


def _normalize_reason_codes(reason_codes: object) -> str:
    if reason_codes is None:
        return ""
    if isinstance(reason_codes, str):
        return reason_codes
    if isinstance(reason_codes, (list, tuple, set)):
        return "|".join(str(code) for code in reason_codes if str(code).strip())
    return str(reason_codes)


def _status_for_row(row: Mapping[str, object]) -> str:
    explicit = str(row.get("status") or "").strip()
    if explicit:
        return explicit.upper()
    guarantee = _num(row.get("guaranteed_probability"))
    if guarantee is not None and guarantee >= 0.999:
        return "MAX POOL"
    p_draw = _num(row.get("p_draw_mean"))
    if p_draw is not None:
        if p_draw >= 0.90:
            return "ABOVE CUTOFF"
        if p_draw >= 0.25:
            return "RESERVED SPLIT"
        if p_draw > 0:
            return "RANDOM ONLY"
        return "NO MODEL"
    return str(row.get("status") or "NO MODEL")


def _trend_for_row(row: Mapping[str, object]) -> str:
    explicit = str(row.get("trend") or "").strip()
    if explicit:
        return explicit.upper()
    creep = _num(row.get("point_creep_1yr"))
    if creep is None or creep == 0:
        return "YELLOW"
    return "GREEN" if creep < 0 else "RED"


def _draw_outlook_for_row(row: Mapping[str, object]) -> str:
    explicit = str(row.get("draw_outlook") or "").strip()
    if explicit:
        return explicit.upper()
    guarantee = _num(row.get("guaranteed_probability"))
    if guarantee is not None and guarantee >= 0.999:
        return "GREEN LIGHT"
    p_draw = _num(row.get("p_draw_mean"))
    if p_draw is None:
        return str(row.get("draw_outlook") or "NOT AVAILABLE")
    if p_draw >= 0.90:
        return "GREEN LIGHT"
    if p_draw >= 0.25:
        return "MAY DRAW IN 5-10 YEARS"
    if p_draw > 0:
        return "RANDOM CHANCE ONLY"
    return "POINT CREEP DEFEAT"


def _format_pct(value: float) -> str:
    text = f"{value:.1f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _format_display_odds(p_draw: float | None) -> str:
    if p_draw is None:
        return ""
    if p_draw <= 0:
        return "No modeled chance"
    capped = min(1.0, max(0.0, p_draw))
    pct = capped * 100.0
    if capped >= 0.999:
        return f"~1 in 1 or {_format_pct(pct)}%"
    denominator = 1.0 / capped
    denominator_text = _format_pct(denominator) if denominator < 10 else str(round(denominator))
    return f"~1 in {denominator_text} or {_format_pct(pct)}%"


def _legacy_projection(row: Mapping[str, object], key: str, fallback: float | None) -> float | None:
    value = _num(row.get(key))
    if value is not None:
        return value
    return fallback


def _first_nonempty(*values: object) -> object:
    for value in values:
        if value is None:
            continue
        if str(value).strip():
            return value
    return ""


def materialize_row(
    prediction: Mapping[str, object] | object,
    legacy_row: Mapping[str, object] | None = None,
    prediction_year: int = DEFAULT_PREDICTION_YEAR,
    model_version: str | None = None,
    rule_version: str | None = None,
    quota_source: str | None = None,
    applicant_pool_source: str | None = None,
) -> dict[str, object]:
    if is_dataclass(prediction):
        row = asdict(prediction)
    elif isinstance(prediction, Mapping):
        row = dict(prediction)
    else:
        row = dict(getattr(prediction, "__dict__", {}))
    legacy_row = dict(legacy_row or {})

    p_draw_mean = _num(row.get("p_draw_mean")) or 0.0
    p_reserved = _num(row.get("p_reserved_mean")) or 0.0
    p_random = _num(row.get("p_random_mean")) or 0.0
    p_preference = _num(row.get("p_preference_mean")) or 0.0
    p_youth = _num(row.get("p_youth_mean")) or 0.0
    guarantee = _num(row.get("guaranteed_probability")) or 0.0
    display_odds_pct = _num(row.get("display_odds_pct"))
    if display_odds_pct is None:
        display_odds_pct = p_draw_mean * 100.0
    projected_applicants = _first_nonempty(
        row.get("projected_applicants"),
        row.get("forecast_applicants_at_level"),
        legacy_row.get("projected_applicants"),
        legacy_row.get("forecast_applicants_at_level"),
    )
    display_odds_text = _first_nonempty(
        row.get("display_odds_text"),
        legacy_row.get("display_odds_text"),
        _format_display_odds(p_draw_mean),
    )

    materialized = {
        "prediction_year": int(row.get("draw_year") or prediction_year),
        "hunt_code": str(row.get("hunt_code") or legacy_row.get("hunt_code") or "").strip().upper(),
        "residency": str(row.get("residency") or legacy_row.get("residency") or "Resident").strip(),
        "points": int(row.get("points") if row.get("points") is not None else legacy_row.get("points") or 0),
        "p_draw_mean": p_draw_mean,
        "p_draw_p10": _num(row.get("p_draw_p10")) or p_draw_mean,
        "p_draw_p50": _num(row.get("p_draw_p50")) or p_draw_mean,
        "p_draw_p90": _num(row.get("p_draw_p90")) or p_draw_mean,
        "p_reserved_mean": p_reserved,
        "p_random_mean": p_random,
        "p_max_pool_mean": _num(row.get("p_max_pool_mean")) if _num(row.get("p_max_pool_mean")) is not None else p_reserved,
        "p_preference_mean": p_preference,
        "p_youth_mean": p_youth,
        "expected_cutoff_points": row.get("expected_cutoff_points"),
        "cutoff_bucket_probability": row.get("cutoff_bucket_probability"),
        "guaranteed_probability": guarantee,
        "point_creep_1yr": row.get("point_creep_1yr", 0.0),
        "point_creep_3yr": row.get("point_creep_3yr", 0.0),
        "quota_source": str(quota_source or row.get("quota_source") or legacy_row.get("quota_source") or "fixture"),
        "quota_source_status": str(row.get("quota_source_status") or legacy_row.get("quota_source_status") or ""),
        "quota_source_year": row.get("quota_source_year") or legacy_row.get("quota_source_year") or "",
        "quota_source_file": row.get("quota_source_file") or legacy_row.get("quota_source_file") or "",
        "quota_2026_total": _first_nonempty(row.get("quota_2026_total"), legacy_row.get("quota_2026_total")),
        "quota_2026_max_pool": _first_nonempty(row.get("quota_2026_max_pool"), legacy_row.get("quota_2026_max_pool")),
        "quota_2026_random_pool": _first_nonempty(row.get("quota_2026_random_pool"), legacy_row.get("quota_2026_random_pool")),
        "permit_allotment_2026_res": _first_nonempty(row.get("permit_allotment_2026_res"), legacy_row.get("permit_allotment_2026_res")),
        "permit_allotment_2026_nr": _first_nonempty(row.get("permit_allotment_2026_nr"), legacy_row.get("permit_allotment_2026_nr")),
        "permit_allotment_2026_total": _first_nonempty(row.get("permit_allotment_2026_total"), legacy_row.get("permit_allotment_2026_total")),
        "permit_allotment_2026_source": row.get("permit_allotment_2026_source") or legacy_row.get("permit_allotment_2026_source") or "",
        "permit_allotment_2026_source_file": row.get("permit_allotment_2026_source_file") or legacy_row.get("permit_allotment_2026_source_file") or "",
        "permit_allotment_2026_status": row.get("permit_allotment_2026_status") or legacy_row.get("permit_allotment_2026_status") or "",
        "projected_2026_max_cutoff_point": row.get("projected_2026_max_cutoff_point") or legacy_row.get("projected_2026_max_cutoff_point") or "",
        "projected_2026_random_pool_start_point": row.get("projected_2026_random_pool_start_point") or legacy_row.get("projected_2026_random_pool_start_point") or "",
        "is_2026_max_point_pool": row.get("is_2026_max_point_pool") if row.get("is_2026_max_point_pool") is not None else legacy_row.get("is_2026_max_point_pool", ""),
        "is_2026_mixed_cutoff": row.get("is_2026_mixed_cutoff") if row.get("is_2026_mixed_cutoff") is not None else legacy_row.get("is_2026_mixed_cutoff", ""),
        "is_2026_random_pool": row.get("is_2026_random_pool") if row.get("is_2026_random_pool") is not None else legacy_row.get("is_2026_random_pool", ""),
        "applicant_pool_source": str(applicant_pool_source or row.get("applicant_pool_source") or legacy_row.get("applicant_pool_source") or "fixture"),
        "model_version": str(model_version or row.get("model_version") or MODEL_VERSION),
        "rule_version": str(rule_version or row.get("rule_version") or RULE_VERSION),
        "data_cutoff_date": str(row.get("data_cutoff_date") or legacy_row.get("data_cutoff_date") or ""),
        "data_quality_grade": str(row.get("data_quality_grade") or legacy_row.get("data_quality_grade") or "F"),
        "reason_codes": _normalize_reason_codes(row.get("reason_codes")),
        "projected_applicants": projected_applicants,
        "projected_applicants_2026": _first_nonempty(row.get("projected_applicants_2026"), projected_applicants),
        "projected_applicants_source": _first_nonempty(row.get("projected_applicants_source"), row.get("applicant_pool_source"), "applicant_stack_rollover"),
        "projected_applicants_2026_source": _first_nonempty(row.get("projected_applicants_2026_source"), row.get("applicant_pool_source"), "applicant_stack_rollover"),
        "p_draw": f"{p_draw_mean:.6f}",
        "p_draw_pct": f"{display_odds_pct:.3f}",
        "display_odds_text": display_odds_text,
        "point_pool_zone": str(row.get("point_pool_zone") or legacy_row.get("point_pool_zone") or ""),
        "applicant_rollover_source_year": row.get("applicant_rollover_source_year") or legacy_row.get("applicant_rollover_source_year") or "",
        "retention_rate_raw": row.get("retention_rate_raw") or legacy_row.get("retention_rate_raw") or "",
        "retention_rate_smoothed": row.get("retention_rate_smoothed") or legacy_row.get("retention_rate_smoothed") or "",
        "rollover_rule": row.get("rollover_rule") or legacy_row.get("rollover_rule") or "",
        "rollover_cutoff_structure": row.get("rollover_cutoff_structure") or legacy_row.get("rollover_cutoff_structure") or "",
        "rollover_mixed_cutoff_point": row.get("rollover_mixed_cutoff_point") or legacy_row.get("rollover_mixed_cutoff_point") or "",
        "rollover_anchor_next_point": row.get("rollover_anchor_next_point") or legacy_row.get("rollover_anchor_next_point") or "",
        "structure_retention_rate_raw": row.get("structure_retention_rate_raw") or legacy_row.get("structure_retention_rate_raw") or "",
        "structure_retention_rate_smoothed": row.get("structure_retention_rate_smoothed") or legacy_row.get("structure_retention_rate_smoothed") or "",
        "structure_retention_prior": row.get("structure_retention_prior") or legacy_row.get("structure_retention_prior") or "",
        "structure_retention_matched_years": row.get("structure_retention_matched_years") or legacy_row.get("structure_retention_matched_years") or "",
        "structure_retention_unsuccessful_total": row.get("structure_retention_unsuccessful_total") or legacy_row.get("structure_retention_unsuccessful_total") or "",
        "forecast_applicants_at_level": row.get("forecast_applicants_at_level") or legacy_row.get("forecast_applicants_at_level") or "",
        "forecast_applicants_above": row.get("forecast_applicants_above") or legacy_row.get("forecast_applicants_above") or "",
        "probability_applicant_count": _first_nonempty(
            row.get("probability_applicant_count"),
            legacy_row.get("probability_applicant_count"),
            max(1, int(_num(row.get("forecast_applicants_at_level")) or _num(legacy_row.get("forecast_applicants_at_level")) or 0)),
        ),
        "rolled_forward_total_applicants": row.get("rolled_forward_total_applicants") or legacy_row.get("rolled_forward_total_applicants") or "",
        "display_odds_pct": round(display_odds_pct, 3),
        "odds_2026_projected": round(_num(row.get("odds_2026_projected")) if _num(row.get("odds_2026_projected")) is not None else display_odds_pct, 3),
        "max_pool_projection_2026": round(_num(row.get("max_pool_projection_2026")) if _num(row.get("max_pool_projection_2026")) is not None else p_reserved * 100.0, 3),
        "random_draw_odds_2026": round(_num(row.get("random_draw_odds_2026")) if _num(row.get("random_draw_odds_2026")) is not None else p_random * 100.0, 3),
        "random_draw_projection_2026": round(_num(row.get("random_draw_projection_2026")) if _num(row.get("random_draw_projection_2026")) is not None else p_random * 100.0, 3),
        "draw_outlook": _draw_outlook_for_row(row),
        "trend": _trend_for_row(row),
        "status": _status_for_row(row),
    }

    for field in LEGACY_OUTPUT_FIELDS:
        materialized.setdefault(field, legacy_row.get(field))

    return materialized


def materialize_rows(
    predictions: Sequence[Mapping[str, object] | object],
    legacy_rows: Sequence[Mapping[str, object]] | None = None,
    prediction_year: int = DEFAULT_PREDICTION_YEAR,
    model_version: str | None = None,
    rule_version: str | None = None,
    quota_source: str | None = None,
    applicant_pool_source: str | None = None,
) -> list[dict[str, object]]:
    legacy_index = {}
    for row in legacy_rows or []:
        key = (str(row.get("hunt_code") or "").strip().upper(), str(row.get("residency") or "").strip(), int(row.get("points") or 0))
        legacy_index[key] = dict(row)

    output: list[dict[str, object]] = []
    for prediction in predictions:
        if is_dataclass(prediction):
            row = asdict(prediction)
        elif isinstance(prediction, Mapping):
            row = dict(prediction)
        else:
            row = dict(getattr(prediction, "__dict__", {}))
        key = (str(row.get("hunt_code") or "").strip().upper(), str(row.get("residency") or "").strip(), int(row.get("points") or 0))
        output.append(
            materialize_row(
                row,
                legacy_index.get(key),
                prediction_year=prediction_year,
                model_version=model_version,
                rule_version=rule_version,
                quota_source=quota_source,
                applicant_pool_source=applicant_pool_source,
            )
        )
    return output


def write_materialized_csv(
    output_path: str | Path,
    rows: Sequence[Mapping[str, object]],
    fieldnames: Sequence[str] | None = None,
) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = list(rows[0].keys()) if rows else REQUIRED_MODELED_FIELDS + LEGACY_OUTPUT_FIELDS
        if "hunt_code" not in fieldnames:
            fieldnames = ["prediction_year", "hunt_code", "residency", "points", *[name for name in fieldnames if name not in {"prediction_year", "hunt_code", "residency", "points"}]]
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Rebuild the Utah processed CSV contract from fixtures.")
    parser.add_argument("--input-dir", default=str(Path(__file__).resolve().parents[2] / "data" / "utah" / "fixtures"), help="Directory containing synthetic Utah fixture CSVs.")
    parser.add_argument("--output-dir", default=str(Path(__file__).resolve().parents[2] / "processed_data"), help="Directory to write processed CSVs.")
    parser.add_argument("--draw-year", type=int, default=DEFAULT_PREDICTION_YEAR, help="Prediction year to stamp onto materialized rows.")
    parser.add_argument("--iterations", type=int, default=10000, help="Reserved Monte Carlo iteration count for future engine use.")
    parser.add_argument("--seed", type=int, default=2026, help="Reserved RNG seed for future engine use.")
    parser.add_argument("--model-version", default=MODEL_VERSION, help="Model version label to stamp into outputs.")
    parser.add_argument("--rule-version", default=RULE_VERSION, help="Rule version label to stamp into outputs.")
    parser.add_argument("--quota-source", default="fixture", help="Quota source label to stamp into outputs.")
    parser.add_argument("--applicant-pool-source", default="fixture", help="Applicant pool source label to stamp into outputs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)

    from .rebuild import rebuild_fixture_processed_csvs

    outputs = rebuild_fixture_processed_csvs(
        source_root=Path(args.input_dir),
        output_root=Path(args.output_dir),
        draw_year=args.draw_year,
        iterations=args.iterations,
        seed=args.seed,
        model_version=args.model_version,
        rule_version=args.rule_version,
        quota_source=args.quota_source,
        applicant_pool_source=args.applicant_pool_source,
    )

    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
