#!/usr/bin/env python3
"""Freeze and verify the normalized long truth file against yearly canonicals.

This validator is intentionally historical-truth-only.  It reads the yearly
canonical files and ``draw_results_long.csv``; it does not open DATABASE.csv,
runtime artifacts, forecasts, or following-year outcomes.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from rebuild_draw_results_long_from_canonical_yearly import canonical_files, read_header, union_header


ROOT = Path(__file__).resolve().parents[1]
LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
OUT = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_results_long_canonical_freeze_2017_2026.json"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    files = canonical_files()
    headers = {path: read_header(path) for path in files}
    expected_header = union_header(list(headers.values()))
    errors: list[str] = []
    canonical_rows_by_year: Counter[str] = Counter()
    canonical_hashes: dict[str, str] = {}
    total_canonical_rows = 0
    long_rows_by_year: Counter[str] = Counter()

    with LONG.open(encoding="utf-8-sig", newline="") as long_handle:
        long_reader = csv.DictReader(long_handle)
        actual_header = list(long_reader.fieldnames or [])
        if actual_header != expected_header:
            errors.append(
                f"Long header differs from deterministic canonical union: expected {len(expected_header)} columns, got {len(actual_header)}"
            )
        long_iter = iter(long_reader)
        row_index = 0
        for path in files:
            canonical_hashes[path.relative_to(ROOT).as_posix()] = sha256(path)
            with path.open(encoding="utf-8-sig", newline="") as canonical_handle:
                canonical_reader = csv.DictReader(canonical_handle)
                for canonical_row in canonical_reader:
                    row_index += 1
                    actual_row = next(long_iter, None)
                    if actual_row is None:
                        errors.append(f"Long file ends before canonical row {row_index}")
                        break
                    expected_row = {column: canonical_row.get(column, "") for column in expected_header}
                    actual_normalized = {column: actual_row.get(column, "") for column in expected_header}
                    if expected_row != actual_normalized:
                        errors.append(
                            f"First value mismatch at row {row_index}: canonical={path.name}, hunt={canonical_row.get('hunt_code', '')}, point={canonical_row.get('points', '')}"
                        )
                        break
                    year = (canonical_row.get("actual_draw_year") or "").strip()
                    canonical_rows_by_year[year] += 1
                    long_rows_by_year[(actual_row.get("actual_draw_year") or "").strip()] += 1
                    total_canonical_rows += 1
            if errors:
                break
        if not errors:
            extra = next(long_iter, None)
            if extra is not None:
                errors.append("Long file contains rows beyond the deterministic canonical concatenation")

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "frozen historical draw truth assembled solely from approved yearly canonicals",
        "truth_boundary": {
            "opened_DATABASE_csv": False,
            "opened_runtime_artifacts": False,
            "opened_prediction_outputs": False,
            "opened_following_year_actuals_for_scoring": False,
        },
        "canonical_file_count": len(files),
        "canonical_sha256": canonical_hashes,
        "long_path": LONG.relative_to(ROOT).as_posix(),
        "long_sha256": sha256(LONG),
        "columns": len(expected_header),
        "canonical_rows": total_canonical_rows,
        "canonical_rows_by_actual_draw_year": dict(sorted(canonical_rows_by_year.items())),
        "long_rows_by_actual_draw_year": dict(sorted(long_rows_by_year.items())),
        "strict_ordered_value_parity": not errors,
        "status": "PASS_FROZEN_LONG_TRUTH_FROM_YEARLY_CANONICALS" if not errors else "FAIL_LONG_TRUTH_CANONICAL_PARITY",
        "errors": errors,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
