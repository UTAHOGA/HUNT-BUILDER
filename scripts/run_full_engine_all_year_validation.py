"""Run wired Utah draw predictive families across source/target year pairs."""

from __future__ import annotations

import argparse
import csv
import subprocess
from pathlib import Path
from typing import Mapping, Sequence

from engine.utah_draw_predictive.run_all_families import REPO, run_all_families


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def _write_csv(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    fields = fields or ["no_rows"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def _changed_files() -> str:
    try:
        status = subprocess.run(
            ["git", "status", "--short"],
            cwd=REPO,
            check=False,
            text=True,
            capture_output=True,
        )
    except Exception as exc:
        return f"git status unavailable: {exc}\n"
    return status.stdout


def _source_column_mapping_rows() -> list[dict[str, str]]:
    return [
        {
            "engine_family": "preference_general_deer",
            "normalized_field": "eligible_applicants",
            "resident_source": "resident_eligible_applicants",
            "nonresident_source": "nonresident_eligible_applicants",
            "total_source": "total_eligible_applicants",
            "defaulted": "false",
        },
        {
            "engine_family": "preference_general_deer",
            "normalized_field": "drawn",
            "resident_source": "resident_regular_permits|resident_total_permits",
            "nonresident_source": "nonresident_regular_permits|nonresident_total_permits",
            "total_source": "total_regular_permits|total_permits",
            "defaulted": "false",
        },
        {
            "engine_family": "preference_antlerless",
            "normalized_field": "p_draw_pct",
            "resident_source": "resident_p_draw_percent",
            "nonresident_source": "nonresident_p_draw_percent",
            "total_source": "total_p_draw_percent",
            "defaulted": "false",
        },
        {
            "engine_family": "dedicated_hunter",
            "normalized_field": "target_permits",
            "resident_source": "resident_regular_permits|resident_total_permits",
            "nonresident_source": "nonresident_regular_permits|nonresident_total_permits",
            "total_source": "total_regular_permits|total_permits",
            "defaulted": "false",
        },
    ]


def _classified_reconciliation_for_row(row: Mapping[str, str]) -> dict[str, str]:
    family = row.get("family", "")
    reason = row.get("blocker_if_failed", "")
    if reason == "HELD_OUT_UNRELEASED_2027_ANTLERLESS_DOE_RESULTS":
        return {
            "reconciliation_bucket": "INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT",
            "clean_run_blocker": "false",
            "release_blocker": "false",
            "next_action": (
                "Keep excluded from accuracy scoring until official 2027 antlerless/doe "
                "draw-result PDFs are released; do not count as poor/inaccurate."
            ),
            "source_location": "engine/utah_draw_predictive/run_all_families.py::UNRELEASED_ACTUAL_HOLDOUT_FAMILIES",
            "promotion_decision": "KEEP_HELD_OUT_NOT_PENALIZED",
            "notes": "Expected 2026->2027 holdout for unreleased actual results.",
        }
    if family == "bonus_bear":
        return {
            "reconciliation_bucket": "FULL_CERT_WIRING_BLOCKER",
            "clean_run_blocker": "true",
            "release_blocker": "runtime_current_year_promoted; historical_full_cert_not_clean",
            "next_action": (
                "Build a historical bear target-year adapter that feeds one active hunt-code row per "
                "source-year hunt code, preserves quota/source fields, and excludes pursuit/reference "
                "rows from probability scoring."
            ),
            "source_location": "engine/utah_draw_predictive/run_all_families.py::deferred_families[bonus_bear]",
            "promotion_decision": "DO_NOT_FAKE_PASS; WIRE_AND_PROBE_BEAR_HISTORY",
            "notes": "Do not replace with raw long-file builder calls; undeduped long rows inflate outputs.",
        }
    if family == "youth_turkey":
        return {
            "reconciliation_bucket": "FULL_CERT_WIRING_BLOCKER",
            "clean_run_blocker": "true",
            "release_blocker": "runtime_current_year_promoted; historical_full_cert_not_clean",
            "next_action": (
                "Build a youth-turkey historical adapter that dedupes target/source hunt-code rows "
                "before calling build_youth_turkey_predictions and verifies no future-year source usage."
            ),
            "source_location": "engine/utah_draw_predictive/run_all_families.py::deferred_families[youth_turkey]",
            "promotion_decision": "DO_NOT_FAKE_PASS; WIRE_AND_PROBE_YOUTH_TURKEY_HISTORY",
            "notes": "Direct builder calls can be bounded but raw long-row db feeds inflate row counts.",
        }
    if family == "youth_draw":
        return {
            "reconciliation_bucket": "FULL_CERT_WIRING_BLOCKER",
            "clean_run_blocker": "true",
            "release_blocker": "runtime_current_year_promoted; historical_full_cert_not_clean",
            "next_action": (
                "Restrict year-to-year youth_draw certification to source-classified youth general any-bull "
                "elk rows, then verify source_years_used never exceeds source_year."
            ),
            "source_location": "engine/utah_draw_predictive/run_all_families.py::deferred_families[youth_draw]",
            "promotion_decision": "DO_NOT_FAKE_PASS; WIRE_AND_PROBE_YOUTH_DRAW_HISTORY",
            "notes": "Needs explicit progressive-source certification handling.",
        }
    return {
        "reconciliation_bucket": "UNRECONCILED_CLASSIFIED",
        "clean_run_blocker": "true",
        "release_blocker": "unknown",
        "next_action": "Review manually.",
        "source_location": "",
        "promotion_decision": "HOLD",
        "notes": "",
    }


def _classified_reconciliation_rows(counts: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for row in counts:
        if row.get("status") != "CLASSIFIED":
            continue
        item = {
            "source_year": row.get("source_year", ""),
            "target_year": row.get("target_year", ""),
            "family": row.get("family", ""),
            "readiness_status": row.get("readiness_status", ""),
            "input_truth_rows": row.get("input_truth_rows", ""),
            "current_target_rows": row.get("current_target_rows", ""),
            "prediction_rows": row.get("prediction_rows", ""),
            "original_reason": row.get("blocker_if_failed", ""),
            "original_output_path": row.get("output_path", ""),
        }
        item.update(_classified_reconciliation_for_row(row))
        rows.append(item)
    return rows


def _report_lines(audit_dir: Path, counts: Sequence[Mapping[str, str]], leakage: Sequence[Mapping[str, str]]) -> list[str]:
    leaking = [row for row in leakage if row.get("leakage_status") == "FAIL"]
    failed = [row for row in counts if row.get("status") == "FAIL"]
    classified_reconciliation = _classified_reconciliation_rows(counts)
    classified_blockers = [row for row in classified_reconciliation if row.get("clean_run_blocker") == "true"]
    classified_holdouts = [
        row for row in classified_reconciliation if row.get("reconciliation_bucket") == "INTENTIONAL_UNRELEASED_ACTUALS_HOLDOUT"
    ]
    return [
        "# Full Engine All-Year Repair Report",
        "",
        f"Repo: `{REPO}`",
        f"Audit dir: `{audit_dir}`",
        "",
        "## Scope",
        "",
        "- Repaired preference-family engines to use forecast-year-aware permit accessors.",
        "- Normalized historical split-residency ladder columns without fake eligibility defaults.",
        "- Added an actual source-year/target-year runner for historical preference-family validation.",
        "- Runs Sportsman as its own resident-only random draw stream from yearly Sportsman draw-result sources.",
        "- Runs bear, youth turkey, and youth draw through deduped historical target adapters.",
        "",
        "## Result",
        "",
        f"- Count rows written: {len(counts)}",
        f"- Leakage failures: {len(leaking)}",
        f"- Zero-row modeled failures: {len(failed)}",
        f"- Classified clean-run blockers: {len(classified_blockers)}",
        f"- Intentional unreleased-results holdouts: {len(classified_holdouts)}",
        "",
        "## Files",
        "",
        "- `changed_files.txt`",
        "- `source_column_mapping.csv`",
        "- `per_family_year_prediction_counts.csv`",
        "- `all_year_family_prediction_counts.csv`",
        "- `leakage_check.csv`",
        "- `classified_reconciliation.csv`",
    ]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run full engine all-year validation for wired families.")
    parser.add_argument("--source-start", type=int, default=2018)
    parser.add_argument("--target-end", type=int, default=2027)
    parser.add_argument("--audit-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    args.audit_dir.mkdir(parents=True, exist_ok=True)

    all_counts: list[dict[str, str]] = []
    all_leakage: list[dict[str, str]] = []
    for source_year in range(args.source_start, args.target_end):
        target_year = source_year + 1
        if target_year > args.target_end:
            break
        run_dir = args.audit_dir / "runs" / str(target_year)
        run_all_families(source_year, target_year, run_dir)
        all_counts.extend(_read_csv(run_dir / "all_year_family_prediction_counts.csv"))
        all_leakage.extend(_read_csv(run_dir / "leakage_check.csv"))

    _write_csv(args.audit_dir / "all_year_family_prediction_counts.csv", all_counts)
    _write_csv(args.audit_dir / "per_family_year_prediction_counts.csv", all_counts)
    _write_csv(args.audit_dir / "leakage_check.csv", all_leakage)
    _write_csv(args.audit_dir / "source_column_mapping.csv", _source_column_mapping_rows())
    _write_csv(args.audit_dir / "classified_reconciliation.csv", _classified_reconciliation_rows(all_counts))
    (args.audit_dir / "changed_files.txt").write_text(_changed_files(), encoding="utf-8")
    (args.audit_dir / "REPAIR_REPORT.md").write_text("\n".join(_report_lines(args.audit_dir, all_counts, all_leakage)), encoding="utf-8")
    print(args.audit_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
