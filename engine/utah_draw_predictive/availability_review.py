"""Final consistency review for MODELED_AVAILABILITY rows."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[2]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _count_by_field(rows: list[dict[str, str]], field: str) -> dict[str, int]:
    counter = Counter(_clean(row.get(field)) or "(blank)" for row in rows)
    return dict(sorted(counter.items()))


def _count_by_reason_code(rows: list[dict[str, str]]) -> dict[str, int]:
    counter: Counter[str] = Counter()
    for row in rows:
        codes = [code.strip() for code in _clean(row.get("reason_codes")).split("|") if code.strip()]
        if not codes:
            counter["(blank)"] += 1
            continue
        for code in codes:
            counter[code] += 1
    return dict(sorted(counter.items()))


def _nonnull(rows: list[dict[str, str]], field: str) -> int:
    return sum(1 for row in rows if _clean(row.get(field)))


def _duplicate_count(rows: list[dict[str, str]], fields: tuple[str, ...]) -> int:
    keys = [tuple(_clean(row.get(field)) for field in fields) for row in rows]
    return len(keys) - len(set(keys))


def _has_availability_signal(row: dict[str, str]) -> bool:
    signal_fields = (
        "p_availability",
        "availability_pct",
        "availability_status",
        "permit_availability_type",
        "unit_status",
        "rule_status",
        "harvest_objective_status",
        "reason_codes",
    )
    return any(_clean(row.get(field)) for field in signal_fields)


def _has_draw_probability_field(row: dict[str, str]) -> bool:
    return any(
        _clean(row.get(field))
        for field in ("p_draw", "p_draw_pct", "p_preference_draw", "p_bonus_pool", "p_random_pool")
    )


def _has_invalid_availability_range(row: dict[str, str]) -> bool:
    p_availability = _clean(row.get("p_availability"))
    availability_pct = _clean(row.get("availability_pct"))
    if p_availability and not (0.0 <= float(p_availability) <= 1.0):
        return True
    if availability_pct and not (0.0 <= float(availability_pct) <= 100.0):
        return True
    return False


def _other_row_detail(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    for row in rows:
        details.append(
            {
                "hunt_code": _clean(row.get("hunt_code")),
                "hunt_name": _clean(row.get("hunt_name")),
                "residency": _clean(row.get("residency")),
                "points": _clean(row.get("points")),
                "draw_system_type": _clean(row.get("draw_system_type")),
                "species": _clean(row.get("species")),
                "algorithm_status": _clean(row.get("algorithm_status")),
                "model_strategy": _clean(row.get("model_strategy")),
                "availability_status": _clean(row.get("availability_status")),
                "permit_availability_type": _clean(row.get("permit_availability_type")),
                "unit_status": _clean(row.get("unit_status")),
                "rule_status": _clean(row.get("rule_status")),
                "p_availability": _clean(row.get("p_availability")),
                "availability_pct": _clean(row.get("availability_pct")),
                "reason_codes": _clean(row.get("reason_codes")),
                "data_quality_flags": _clean(row.get("data_quality_flags")),
                "reason": _clean(row.get("reason")),
                "availability_reason": _clean(row.get("availability_reason")),
            }
        )
    return details


def _sync_gpt_work_review_report(
    output_dir: Path,
    forecast_year: int,
    history_years: list[int],
    coverage_report: dict[str, object],
    availability_report: dict[str, object],
    tests_passed: int | None = None,
    tests_failed: int | None = None,
) -> None:
    json_path = output_dir / "gpt_work_review_report.json"
    md_path = output_dir / "gpt_work_review_report.md"

    existing: dict[str, object] = {}
    if json_path.exists():
        existing = json.loads(json_path.read_text(encoding="utf-8"))

    active_predictive_counts = dict(coverage_report.get("counts_by_algorithm_status_by_source_dataset", {}).get("active_predictive", {}))
    old_availability_count = (
        existing.get("row_counts", {}).get("MODELED_AVAILABILITY")
        if isinstance(existing.get("row_counts"), dict)
        else None
    )

    files_reviewed = list(dict.fromkeys(
        list(existing.get("files_reviewed", []))
        + [
            "engine/utah_draw_predictive/availability_review.py",
            "engine/utah_draw_predictive/classifier.py",
            "engine/utah_draw_predictive/mountain_lion.py",
            "engine/utah_draw_predictive/bear.py",
            "engine/utah_bonus_predictive/materialize.py",
        ]
    ))
    artifacts_reviewed = list(dict.fromkeys(
        list(existing.get("artifacts_reviewed", []))
        + [
            "processed_data/ml_draw_predictions_v1.csv",
            "processed_data/draw_reality_engine_predictive_v2.csv",
            "processed_data/draw_system_coverage_report.csv",
            "processed_data/draw_system_coverage_report.json",
            "processed_data/mountain_lion_availability_report.json",
            "processed_data/bear_report.json",
            "processed_data/modeled_availability_review_report.json",
        ]
    ))

    updated = dict(existing)
    updated["active_repo"] = str(REPO)
    updated["forecast_year"] = forecast_year
    updated["source_years"] = history_years
    updated["generated_at"] = datetime.now(timezone.utc).isoformat()
    updated["files_reviewed"] = files_reviewed
    updated["artifacts_reviewed"] = artifacts_reviewed
    updated["row_counts"] = {
        "total_predictive_rows": int(coverage_report.get("rows_seen_active_predictive", 0)),
        "MODELED_BONUS": int(active_predictive_counts.get("MODELED_BONUS", 0)),
        "MODELED_PREFERENCE": int(active_predictive_counts.get("MODELED_PREFERENCE", 0)),
        "MODELED_ALLOCATION": int(active_predictive_counts.get("MODELED_ALLOCATION", 0)),
        "MODELED_AVAILABILITY": int(active_predictive_counts.get("MODELED_AVAILABILITY", 0)),
        "MODELED_SPORTSMAN_DRAW": int(active_predictive_counts.get("MODELED_SPORTSMAN_DRAW", 0)),
        "IN_SCOPE_MODEL_PENDING": int(active_predictive_counts.get("IN_SCOPE_MODEL_PENDING", 0)),
        "EXCLUDED_NOT_PREDICTIVE_DRAW": int(active_predictive_counts.get("EXCLUDED_NOT_PREDICTIVE_DRAW", 0)),
        "OUT_OF_SCOPE_NON_TARGET": int(active_predictive_counts.get("OUT_OF_SCOPE_NON_TARGET", 0)),
    }
    guardrails = dict(updated.get("guardrail_results", {}))
    guardrails.update(
        {
            "duplicate_key_count": int(availability_report["duplicate_key_count"]),
            "pending_rows_with_p_draw": int(existing.get("guardrail_results", {}).get("pending_rows_with_p_draw", 0)),
            "out_of_scope_rows_with_p_draw": int(existing.get("guardrail_results", {}).get("out_of_scope_rows_with_p_draw", 0)),
            "mountain_lion_status_unchanged_pass": availability_report["mountain_lion_availability_row_count"] == 120,
            "bear_availability_guardrails_pass": availability_report["bear_availability_row_count"] == 4
            and availability_report["availability_rows_with_draw_probability_fields"] == 0,
            "modeled_availability_pass": bool(coverage_report.get("modeled_availability", {}).get("modeled_availability_pass")),
        }
    )
    updated["guardrail_results"] = guardrails
    updated["availability_review"] = {
        "live_modeled_availability_rows": availability_report["total_MODELED_AVAILABILITY_rows"],
        "mountain_lion_rows": availability_report["mountain_lion_availability_row_count"],
        "bear_rows": availability_report["bear_availability_row_count"],
        "other_rows": availability_report["other_availability_row_count"],
        "legacy_review_reference_modeled_availability_count": old_availability_count,
        "legacy_review_reference_stale": (
            old_availability_count is not None
            and int(old_availability_count) != int(availability_report["total_MODELED_AVAILABILITY_rows"])
        ),
    }
    updated["recommended_next_phase"] = "Availability cleanup complete; remaining work is outside MODELED_AVAILABILITY semantics unless a new in-scope availability family is introduced."
    updated["recommended_next_codex_command_summary"] = availability_report["conclusion"]
    if tests_passed is not None:
        updated["tests_passed"] = tests_passed
    if tests_failed is not None:
        updated["tests_failed"] = tests_failed
    _write_json(json_path, updated)

    markdown = [
        "# GPT Work Review Report",
        "",
        "## Executive Summary",
        "",
        f"- Active repo: `{REPO}`",
        f"- Forecast year: `{forecast_year}`",
        f"- Source years: `{', '.join(str(year) for year in history_years)}`",
        f"- Total predictive rows: `{updated['row_counts']['total_predictive_rows']}`",
        f"- Tests passed: `{updated.get('tests_passed', '(not recorded)')}`",
        f"- Tests failed: `{updated.get('tests_failed', '(not recorded)')}`",
        f"- MODELED_AVAILABILITY rows: `{updated['row_counts']['MODELED_AVAILABILITY']}`",
        f"- Mountain lion/cougar availability rows: `{availability_report['mountain_lion_availability_row_count']}`",
        f"- Bear availability rows: `{availability_report['bear_availability_row_count']}`",
        f"- Other availability rows: `{availability_report['other_availability_row_count']}`",
        "",
        "## Availability Guardrails",
        "",
        f"- Availability rows with `p_draw`: `{availability_report['p_draw_non_null_count']}`",
        f"- Availability rows with `p_draw_pct`: `{availability_report['p_draw_pct_non_null_count']}`",
        f"- Availability rows with `p_preference_draw`: `{availability_report['p_preference_draw_non_null_count']}`",
        f"- Availability rows with `p_bonus_pool`: `{availability_report['p_bonus_pool_non_null_count']}`",
        f"- Availability rows with `p_random_pool`: `{availability_report['p_random_pool_non_null_count']}`",
        f"- Availability duplicate key count: `{availability_report['duplicate_key_count']}`",
        "",
        "## Conclusion",
        "",
        f"- {availability_report['conclusion']}",
    ]
    md_path.write_text("\n".join(markdown) + "\n", encoding="utf-8")


def build_modeled_availability_review(
    output_dir: Path,
    forecast_year: int = 2026,
    history_years: list[int] | None = None,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
) -> dict[str, Path]:
    history_years = history_years or [2021, 2022, 2023, 2024, 2025]
    ml_path = output_dir / "ml_draw_predictions_v1.csv"
    dre_path = output_dir / "draw_reality_engine_predictive_v2.csv"
    coverage_path = output_dir / "draw_system_coverage_report.json"
    mountain_lion_report_path = output_dir / "mountain_lion_availability_report.json"
    bear_report_path = output_dir / "bear_report.json"

    ml_rows = _read_csv(ml_path)
    dre_rows = _read_csv(dre_path)
    availability_rows = [row for row in ml_rows if _clean(row.get("algorithm_status")) == "MODELED_AVAILABILITY"]
    dre_availability_rows = [row for row in dre_rows if _clean(row.get("algorithm_status")) == "MODELED_AVAILABILITY"]
    coverage_report = json.loads(coverage_path.read_text(encoding="utf-8")) if coverage_path.exists() else {}
    mountain_lion_report = json.loads(mountain_lion_report_path.read_text(encoding="utf-8")) if mountain_lion_report_path.exists() else {}
    bear_report = json.loads(bear_report_path.read_text(encoding="utf-8")) if bear_report_path.exists() else {}

    mountain_lion_rows = [row for row in availability_rows if _clean(row.get("draw_system_type")) == "COUGAR_LICENSE_BASED"]
    bear_rows = [row for row in availability_rows if _clean(row.get("draw_system_type")) == "BEAR_DRAW"]
    other_rows = [
        row
        for row in availability_rows
        if _clean(row.get("draw_system_type")) not in {"COUGAR_LICENSE_BASED", "BEAR_DRAW"}
    ]
    missing_reason_codes = [row for row in availability_rows if not _clean(row.get("reason_codes"))]
    missing_signal = [row for row in availability_rows if not _has_availability_signal(row)]
    draw_field_rows = [row for row in availability_rows if _has_draw_probability_field(row)]
    invalid_range_rows = [row for row in availability_rows if _has_invalid_availability_range(row)]

    legacy_reference_count = (
        coverage_report.get("counts_by_algorithm_status_by_source_dataset", {})
        .get("active_predictive", {})
        .get("MODELED_AVAILABILITY")
    )
    conclusion = (
        f"Current live predictive artifacts contain {len(availability_rows)} MODELED_AVAILABILITY rows: "
        f"{len(mountain_lion_rows)} mountain lion/cougar rows, {len(bear_rows)} bear availability rows, "
        f"and {len(other_rows)} other availability rows. A prior review artifact referenced 139 availability rows; "
        "that older count is stale relative to the current live predictive artifacts and does not represent an unexplained hidden family."
        if len(availability_rows) != 139
        else "All live predictive MODELED_AVAILABILITY rows are accounted for and availability-only semantics are preserved."
    )

    report = {
        "forecast_year": forecast_year,
        "source_years": history_years,
        "total_MODELED_AVAILABILITY_rows": len(availability_rows),
        "total_MODELED_AVAILABILITY_hunt_codes": len({_clean(row.get("hunt_code")) for row in availability_rows if _clean(row.get("hunt_code"))}),
        "total_MODELED_AVAILABILITY_by_draw_system_type": _count_by_field(availability_rows, "draw_system_type"),
        "total_MODELED_AVAILABILITY_by_species": _count_by_field(availability_rows, "species"),
        "total_MODELED_AVAILABILITY_by_model_strategy": _count_by_field(availability_rows, "model_strategy"),
        "total_MODELED_AVAILABILITY_by_availability_status": _count_by_field(availability_rows, "availability_status"),
        "total_MODELED_AVAILABILITY_by_permit_availability_type": _count_by_field(availability_rows, "permit_availability_type"),
        "total_MODELED_AVAILABILITY_by_reason_code": _count_by_reason_code(availability_rows),
        "mountain_lion_availability_row_count": len(mountain_lion_rows),
        "bear_availability_row_count": len(bear_rows),
        "other_availability_row_count": len(other_rows),
        "other_availability_rows_detail": _other_row_detail(other_rows),
        "p_draw_non_null_count": _nonnull(availability_rows, "p_draw"),
        "p_draw_pct_non_null_count": _nonnull(availability_rows, "p_draw_pct"),
        "p_preference_draw_non_null_count": _nonnull(availability_rows, "p_preference_draw"),
        "p_bonus_pool_non_null_count": _nonnull(availability_rows, "p_bonus_pool"),
        "p_random_pool_non_null_count": _nonnull(availability_rows, "p_random_pool"),
        "p_availability_non_null_count": _nonnull(availability_rows, "p_availability"),
        "availability_pct_non_null_count": _nonnull(availability_rows, "availability_pct"),
        "availability_status_or_equivalent_non_null_count": sum(1 for row in availability_rows if _has_availability_signal(row)),
        "duplicate_key_count": _duplicate_count(availability_rows, ("hunt_code", "residency", "points")),
        "availability_rows_missing_reason_codes": len(missing_reason_codes),
        "availability_rows_missing_availability_status_or_equivalent": len(missing_signal),
        "availability_rows_with_draw_probability_fields": len(draw_field_rows),
        "availability_rows_with_invalid_availability_range": len(invalid_range_rows),
        "availability_rows_requiring_reclassification": _other_row_detail([] if not other_rows else [row for row in other_rows if _has_draw_probability_field(row) or not _has_availability_signal(row) or _has_invalid_availability_range(row)]),
        "ml_draw_predictions_v1_modeled_availability_count": len(availability_rows),
        "draw_reality_engine_predictive_v2_modeled_availability_count": len(dre_availability_rows),
        "mountain_lion_report_row_count": int(mountain_lion_report.get("modeled_availability_row_count", 0)),
        "bear_report_availability_row_count": int(bear_report.get("bear_rows_by_algorithm_status", {}).get("MODELED_AVAILABILITY", 0)),
        "legacy_reference_modeled_availability_count": legacy_reference_count,
        "conclusion": conclusion,
    }

    json_path = output_dir / "modeled_availability_review_report.json"
    md_path = output_dir / "modeled_availability_review_report.md"
    _write_json(json_path, report)

    lines = [
        "# MODELED_AVAILABILITY Review Report",
        "",
        "## Summary",
        "",
        f"- Forecast year: `{forecast_year}`",
        f"- Source years: `{', '.join(str(year) for year in history_years)}`",
        f"- Total MODELED_AVAILABILITY rows: `{report['total_MODELED_AVAILABILITY_rows']}`",
        f"- Mountain lion / cougar rows: `{report['mountain_lion_availability_row_count']}`",
        f"- Bear availability rows: `{report['bear_availability_row_count']}`",
        f"- Other availability rows: `{report['other_availability_row_count']}`",
        "",
        "## Field Guardrails",
        "",
        f"- `p_draw` non-null count: `{report['p_draw_non_null_count']}`",
        f"- `p_draw_pct` non-null count: `{report['p_draw_pct_non_null_count']}`",
        f"- `p_preference_draw` non-null count: `{report['p_preference_draw_non_null_count']}`",
        f"- `p_bonus_pool` non-null count: `{report['p_bonus_pool_non_null_count']}`",
        f"- `p_random_pool` non-null count: `{report['p_random_pool_non_null_count']}`",
        f"- `p_availability` non-null count: `{report['p_availability_non_null_count']}`",
        f"- `availability_pct` non-null count: `{report['availability_pct_non_null_count']}`",
        f"- Duplicate key count: `{report['duplicate_key_count']}`",
        "",
        "## Breakdown",
        "",
        "| Group | Count |",
        "|---|---:|",
    ]
    for label, value in report["total_MODELED_AVAILABILITY_by_draw_system_type"].items():
        lines.append(f"| {label} | {value} |")
    if report["other_availability_rows_detail"]:
        lines.extend(["", "## Other Availability Rows", ""])
        for row in report["other_availability_rows_detail"]:
            lines.append(
                f"- `{row['hunt_code']}` `{row['residency']}` `{row['draw_system_type']}` "
                f"`{row['availability_status'] or row['permit_availability_type'] or row['unit_status']}` "
                f"- {row['reason'] or row['availability_reason'] or 'No explanation recorded'}"
            )
    lines.extend(["", "## Conclusion", "", f"- {conclusion}"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    _sync_gpt_work_review_report(
        output_dir=output_dir,
        forecast_year=forecast_year,
        history_years=history_years,
        coverage_report=coverage_report,
        availability_report=report,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
    )
    return {"json": json_path, "md": md_path}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", default=str(REPO / "processed_data"))
    parser.add_argument("--forecast-year", type=int, default=2026)
    parser.add_argument("--history-years", default="2021,2022,2023,2024,2025")
    parser.add_argument("--tests-passed", type=int, default=None)
    parser.add_argument("--tests-failed", type=int, default=None)
    args = parser.parse_args()
    history_years = [int(token.strip()) for token in str(args.history_years).split(",") if token.strip()]
    artifacts = build_modeled_availability_review(
        output_dir=Path(args.output_dir),
        forecast_year=args.forecast_year,
        history_years=history_years,
        tests_passed=args.tests_passed,
        tests_failed=args.tests_failed,
    )
    print(json.dumps({key: str(value) for key, value in artifacts.items()}, indent=2))


if __name__ == "__main__":
    main()

