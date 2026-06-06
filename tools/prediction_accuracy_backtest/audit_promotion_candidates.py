#!/usr/bin/env python
"""Audit prediction model run promotion candidates against production outputs.

This script is read-only except for writing small audit summaries under
audits/prediction_model_runs/.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


OUT_FIELDS = [
    "candidate_run",
    "candidate_status",
    "production_file",
    "candidate_file",
    "candidate_exists",
    "production_exists",
    "production_compatible",
    "overall_assessment",
    "promotion_recommendation",
    "row_count_candidate",
    "row_count_production",
    "column_count_candidate",
    "column_count_production",
    "unique_hunt_codes_candidate",
    "unique_hunt_codes_production",
    "probability_fields_candidate",
    "probability_fields_production",
    "draw_family_count_candidate",
    "draw_family_count_production",
    "draw_families_candidate",
    "draw_families_production",
    "missing_families_compared_to_production",
    "extra_families_compared_to_production",
    "rows_added_if_promoted",
    "rows_removed_if_promoted",
    "rows_changed_if_promoted",
    "shared_key_rows",
    "candidate_sha256",
    "production_sha256",
    "notes",
]

PRODUCTION_FILES = [
    "processed_data/ml_draw_predictions_v1.csv",
    "processed_data/draw_reality_engine_predictive_v2.csv",
    "data_model/runtime_drafts/predictive_bonus_engine_2026.materialized.csv",
    "processed_data/point_ladder_view.csv",
    "processed_data/hunt_research_2026.json",
    "processed_data/hunt_research_2026_ladder.json",
]

CANDIDATE_RUNS = [
    {
        "name": "2026_from_2025_truth_pdf_draw_results",
        "status": "PROMOTION_CANDIDATE_REVIEW_ONLY",
        "dir": "audits/prediction_model_runs/2026_from_2025_truth_pdf_draw_results",
    },
    {
        "name": "2027_from_2026_dwr_released_candidate",
        "status": "LIMITED_CANDIDATE_DO_NOT_PROMOTE_TO_PRODUCTION_ODDS",
        "dir": "audits/prediction_model_runs/2027_from_2026_dwr_released_candidate",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument(
        "--out-dir",
        default="audits/prediction_model_runs",
        help="Audit output directory.",
    )
    return parser.parse_args()


def sha256(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def norm(value: Any) -> str:
    return str(value or "").replace("\ufeff", "").strip()


def norm_hunt_code(value: Any) -> str:
    return norm(value).upper()


def probability_columns(header: list[str]) -> list[str]:
    markers = ("prob", "p_", "odds", "pct", "percent", "success_ratio")
    return [col for col in header if any(marker in col.lower() for marker in markers)]


def family_columns(header: list[str]) -> list[str]:
    preferred = [
        "draw_2026_system_type",
        "draw_system_type",
        "draw_system",
        "draw_2025_type",
        "source_family",
        "source_classification",
        "model_strategy",
        "hunt_type",
    ]
    return [col for col in preferred if col in header]


def key_columns(header: list[str]) -> list[str]:
    preferred = ["hunt_code", "residency", "points", "draw_pool"]
    keys = [col for col in preferred if col in header]
    return keys or [col for col in ["hunt_code"] if col in header]


def read_csv_profile(path: Path, relpath: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        header = list(reader.fieldnames or [])
        prob_cols = probability_columns(header)
        fam_cols = family_columns(header)
        keys = key_columns(header)
        row_count = 0
        hunt_codes: set[str] = set()
        families: Counter[str] = Counter()
        prob_nonblank: Counter[str] = Counter()
        row_hash_by_key: dict[tuple[str, ...], str] = {}
        duplicate_keys = 0
        for row in reader:
            row_count += 1
            hunt_code = norm_hunt_code(row.get("hunt_code"))
            if hunt_code:
                hunt_codes.add(hunt_code)
            family_value = first_nonblank(row, fam_cols)
            if family_value:
                families[family_value] += 1
            for col in prob_cols:
                if norm(row.get(col)):
                    prob_nonblank[col] += 1
            if keys:
                key = tuple(norm(row.get(col)) for col in keys)
                row_hash = hashlib.sha256(
                    "\x1f".join(norm(row.get(col)) for col in header).encode("utf-8")
                ).hexdigest()
                if key in row_hash_by_key:
                    duplicate_keys += 1
                else:
                    row_hash_by_key[key] = row_hash
    return {
        "path": relpath,
        "exists": True,
        "type": "csv",
        "row_count": row_count,
        "column_count": len(header),
        "header": header,
        "hunt_codes": hunt_codes,
        "families": families,
        "probability_columns": prob_cols,
        "probability_nonblank": prob_nonblank,
        "key_columns": keys,
        "row_hash_by_key": row_hash_by_key,
        "duplicate_keys": duplicate_keys,
        "sha256": sha256(path),
    }


def read_json_profile(path: Path, relpath: str) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as handle:
        data = json.load(handle)
    rows = data if isinstance(data, list) else data.get("rows", []) if isinstance(data, dict) else []
    if not isinstance(rows, list):
        rows = []
    header = sorted({key for row in rows if isinstance(row, dict) for key in row.keys()})
    prob_cols = probability_columns(header)
    fam_cols = family_columns(header)
    hunt_codes = {norm_hunt_code(row.get("hunt_code")) for row in rows if isinstance(row, dict) and norm_hunt_code(row.get("hunt_code"))}
    families: Counter[str] = Counter()
    prob_nonblank: Counter[str] = Counter()
    for row in rows:
        if not isinstance(row, dict):
            continue
        family_value = first_nonblank(row, fam_cols)
        if family_value:
            families[family_value] += 1
        for col in prob_cols:
            if norm(row.get(col)):
                prob_nonblank[col] += 1
    return {
        "path": relpath,
        "exists": True,
        "type": "json",
        "row_count": len(rows),
        "column_count": len(header),
        "header": header,
        "hunt_codes": hunt_codes,
        "families": families,
        "probability_columns": prob_cols,
        "probability_nonblank": prob_nonblank,
        "key_columns": [],
        "row_hash_by_key": {},
        "duplicate_keys": 0,
        "sha256": sha256(path),
    }


def missing_profile(relpath: str) -> dict[str, Any]:
    return {
        "path": relpath,
        "exists": False,
        "type": "",
        "row_count": 0,
        "column_count": 0,
        "header": [],
        "hunt_codes": set(),
        "families": Counter(),
        "probability_columns": [],
        "probability_nonblank": Counter(),
        "key_columns": [],
        "row_hash_by_key": {},
        "duplicate_keys": 0,
        "sha256": "",
    }


def profile(root: Path, relpath: str) -> dict[str, Any]:
    path = root / relpath
    if not path.exists() or not path.is_file():
        return missing_profile(relpath)
    if path.suffix.lower() == ".csv":
        return read_csv_profile(path, relpath)
    if path.suffix.lower() == ".json":
        return read_json_profile(path, relpath)
    return missing_profile(relpath)


def first_nonblank(row: dict[str, Any], columns: list[str]) -> str:
    for col in columns:
        value = norm(row.get(col))
        if value:
            return value
    return ""


def encode_counter(counter: Counter[str], limit: int = 30) -> str:
    return "; ".join(f"{name}:{count}" for name, count in counter.most_common(limit))


def encode_probability(profile_data: dict[str, Any]) -> str:
    columns = profile_data["probability_columns"]
    counts = profile_data["probability_nonblank"]
    return "; ".join(f"{col}:{counts.get(col, 0)}" for col in columns)


def compare_profiles(candidate: dict[str, Any], production: dict[str, Any], candidate_status: str) -> dict[str, Any]:
    candidate_keys = candidate["row_hash_by_key"]
    production_keys = production["row_hash_by_key"]
    shared = set(candidate_keys) & set(production_keys)
    rows_changed = sum(1 for key in shared if candidate_keys[key] != production_keys[key])
    rows_added = len(set(candidate_keys) - set(production_keys))
    rows_removed = len(set(production_keys) - set(candidate_keys))

    missing_families = set(production["families"]) - set(candidate["families"])
    extra_families = set(candidate["families"]) - set(production["families"])
    candidate_exists = candidate["exists"]
    production_exists = production["exists"]

    if not candidate_exists:
        compatible = "NO_CANDIDATE_OUTPUT"
        assessment = "worse"
        recommendation = "DO_NOT_PROMOTE"
        notes = "Candidate run did not generate this production surface."
    elif candidate_status == "LIMITED_CANDIDATE_DO_NOT_PROMOTE_TO_PRODUCTION_ODDS":
        compatible = "LIMITED_CANDIDATE"
        assessment = "worse"
        recommendation = "DO_NOT_PROMOTE_TO_PRODUCTION_ODDS"
        notes = "2027 candidate is explicitly limited because the 2026 released actual source has no scorable probability/applicant/drawn fields."
    elif not production_exists:
        compatible = "NO_PRODUCTION_BASELINE"
        assessment = "review"
        recommendation = "REVIEW_ONLY"
        notes = "Production baseline is missing; candidate cannot be safely compared."
    elif candidate["type"] != production["type"]:
        compatible = "TYPE_MISMATCH"
        assessment = "worse"
        recommendation = "DO_NOT_PROMOTE"
        notes = "Candidate and production file types differ."
    else:
        candidate_headers = set(candidate["header"])
        production_headers = set(production["header"])
        missing_columns = production_headers - candidate_headers
        compatible = "YES" if not missing_columns else "COLUMN_GAP_REVIEW"
        if rows_changed == 0 and rows_added == 0 and rows_removed == 0 and not missing_columns:
            assessment = "same"
            recommendation = "NO_PROMOTION_NEEDED"
            notes = "Candidate matches production at comparable key/hash level."
        elif missing_columns:
            assessment = "worse"
            recommendation = "DO_NOT_PROMOTE_WITHOUT_SCHEMA_REPAIR"
            notes = f"Candidate missing production columns: {len(missing_columns)}."
        elif candidate["row_count"] >= production["row_count"] and len(missing_families) == 0:
            assessment = "better_or_broader"
            recommendation = "PROMOTION_REVIEW_REQUIRED"
            notes = "Candidate has compatible schema and no missing production draw families; row-level changes require review."
        else:
            assessment = "worse_or_narrower"
            recommendation = "DO_NOT_PROMOTE_WITHOUT_COVERAGE_REVIEW"
            notes = "Candidate appears narrower than production or misses production draw families."

    return {
        "production_compatible": compatible,
        "overall_assessment": assessment,
        "promotion_recommendation": recommendation,
        "rows_added_if_promoted": rows_added,
        "rows_removed_if_promoted": rows_removed,
        "rows_changed_if_promoted": rows_changed,
        "shared_key_rows": len(shared),
        "missing_families_compared_to_production": "; ".join(sorted(missing_families)),
        "extra_families_compared_to_production": "; ".join(sorted(extra_families)),
        "notes": notes,
    }


def candidate_relpath(run_dir: str, production_relpath: str) -> str:
    name = Path(production_relpath).name
    return str(Path(run_dir) / name).replace("\\", "/")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUT_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in OUT_FIELDS})


def write_markdown(path: Path, rows: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    lines = [
        "# Promotion Candidate Review",
        "",
        "This is a read-only audit. No production/runtime files were modified.",
        "",
        "## Summary",
        "",
        f"- Candidate runs audited: {summary['candidate_runs_audited']}",
        f"- Production files compared per run: {summary['production_files_compared']}",
        f"- Comparable candidate outputs found: {summary['candidate_outputs_found']}",
        f"- Missing candidate outputs: {summary['candidate_outputs_missing']}",
        f"- Do-not-promote rows: {summary['do_not_promote_rows']}",
        "",
        "## Output Files Generated By This Audit",
        "",
        "- `audits/prediction_model_runs/04_promotion_candidate_comparison.csv`",
        "- `audits/prediction_model_runs/05_promotion_candidate_summary.json`",
        "- `audits/prediction_model_runs/PROMOTION_CANDIDATE_REVIEW.md`",
        "",
        "## Candidate Results",
        "",
        "| Candidate run | Production file | Candidate status | Compatible | Assessment | Rows changed | Hunt codes candidate/prod | Notes |",
        "| --- | --- | --- | --- | --- | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {candidate_run} | `{production_file}` | {candidate_status} | {production_compatible} | {overall_assessment} | {rows_changed_if_promoted} | {unique_hunt_codes_candidate}/{unique_hunt_codes_production} | {notes} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Coverage And Schema Detail",
            "",
            "| Candidate run | Production file | Rows cand/prod | Cols cand/prod | Probability fields candidate | Family coverage candidate/prod | Missing production families |",
            "| --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )
    for row in rows:
        lines.append(
            "| {candidate_run} | `{production_file}` | {row_count_candidate}/{row_count_production} | {column_count_candidate}/{column_count_production} | {probability_fields_candidate} | {draw_family_count_candidate}/{draw_family_count_production} | {missing_families_compared_to_production} |".format(
                **row
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- The 2026-from-2025 run can only be considered for surfaces it actually generated: `ml_draw_predictions_v1.csv` and `draw_reality_engine_predictive_v2.csv`.",
            "- Those two generated files are not production-compatible as direct replacements because they are missing production columns and would change most shared keyed rows.",
            "- The run did not generate replacements for the bonus materialized runtime draft, point ladder, or Hunt Research JSON files.",
            "- The 2027-from-2026 run is explicitly marked `LIMITED_CANDIDATE_DO_NOT_PROMOTE_TO_PRODUCTION_ODDS` because the source has no scorable probability/applicant/drawn fields.",
            "- Any promotion would require a separate, scripted mutation/overlay plan; this audit does not promote anything.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = root / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    production_profiles = {relpath: profile(root, relpath) for relpath in PRODUCTION_FILES}
    rows: list[dict[str, Any]] = []
    for run in CANDIDATE_RUNS:
        for production_relpath, production_profile in production_profiles.items():
            candidate_path = candidate_relpath(run["dir"], production_relpath)
            candidate_profile = profile(root, candidate_path)
            comparison = compare_profiles(candidate_profile, production_profile, run["status"])
            rows.append(
                {
                    "candidate_run": run["name"],
                    "candidate_status": run["status"],
                    "production_file": production_relpath,
                    "candidate_file": candidate_path,
                    "candidate_exists": str(candidate_profile["exists"]).upper(),
                    "production_exists": str(production_profile["exists"]).upper(),
                    "row_count_candidate": candidate_profile["row_count"],
                    "row_count_production": production_profile["row_count"],
                    "column_count_candidate": candidate_profile["column_count"],
                    "column_count_production": production_profile["column_count"],
                    "unique_hunt_codes_candidate": len(candidate_profile["hunt_codes"]),
                    "unique_hunt_codes_production": len(production_profile["hunt_codes"]),
                    "probability_fields_candidate": encode_probability(candidate_profile),
                    "probability_fields_production": encode_probability(production_profile),
                    "draw_family_count_candidate": len(candidate_profile["families"]),
                    "draw_family_count_production": len(production_profile["families"]),
                    "draw_families_candidate": encode_counter(candidate_profile["families"]),
                    "draw_families_production": encode_counter(production_profile["families"]),
                    "candidate_sha256": candidate_profile["sha256"],
                    "production_sha256": production_profile["sha256"],
                    **comparison,
                }
            )

    summary = {
        "candidate_runs_audited": len(CANDIDATE_RUNS),
        "production_files_compared": len(PRODUCTION_FILES),
        "rows_written": len(rows),
        "candidate_outputs_found": sum(1 for row in rows if row["candidate_exists"] == "TRUE"),
        "candidate_outputs_missing": sum(1 for row in rows if row["candidate_exists"] == "FALSE"),
        "do_not_promote_rows": sum(1 for row in rows if str(row["promotion_recommendation"]).startswith("DO_NOT")),
        "production_files": PRODUCTION_FILES,
        "candidate_runs": CANDIDATE_RUNS,
        "comparison_rows": rows,
    }

    write_csv(out_dir / "04_promotion_candidate_comparison.csv", rows)
    (out_dir / "05_promotion_candidate_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    write_markdown(out_dir / "PROMOTION_CANDIDATE_REVIEW.md", rows, summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
