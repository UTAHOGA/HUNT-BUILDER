#!/usr/bin/env python3
"""Create a source-preserving review of Bear false-guarantee audit rows.

This is an evaluator only.  It reads scored row-level comparison artifacts and
records the exact hunt/residency/point cases where an emitted 100% forecast did
not draw at 100% in the following frozen official result.  It neither changes
truth, quotas, forecasts, nor engine behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
FIELDS = (
    "source_year",
    "target_year",
    "hunt_code",
    "hunt_name_predicted",
    "actual_hunt_name",
    "residency",
    "points",
    "predicted_probability",
    "actual_probability",
    "actual_eligible_applicants",
    "point_relation_to_draw_line",
    "mixed_cutoff_point",
    "lowest_guaranteed_stack_point",
    "top_applicant_point",
    "source_years_used",
    "draw_system_type",
    "algorithm_status",
)


def probability(value: str) -> float:
    try:
        return float(value or 0)
    except ValueError:
        return 0.0


def read_false_guarantees(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        if not rows.fieldnames:
            raise ValueError(f"No header in comparison artifact: {path}")
        required = {"family", "scoring_decision", "predicted_probability", "actual_probability"}
        if not required.issubset(rows.fieldnames):
            raise ValueError(f"Comparison artifact lacks required fields: {path}")
        return [
            {field: row.get(field, "") for field in FIELDS}
            for row in rows
            if row.get("family") == "bonus_bear"
            and row.get("scoring_decision") == "score_probability"
            and probability(row.get("predicted_probability", "")) >= 0.999999
            and probability(row.get("actual_probability", "")) < 0.999999
        ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", type=Path, nargs="+", required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        raise FileExistsError(f"Refusing to overwrite an existing review: {args.out_dir}")

    rows: list[dict[str, str]] = []
    for artifact in args.comparison:
        if not artifact.exists():
            raise FileNotFoundError(artifact)
        rows.extend(read_false_guarantees(artifact))
    rows.sort(key=lambda row: (int(row["source_year"]), row["hunt_code"], row["residency"], -int(row["points"])))

    args.out_dir.mkdir(parents=True, exist_ok=False)
    out_csv = args.out_dir / "bear_false_guarantee_rows.csv"
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    by_fold = Counter(f"{row['source_year']}→{row['target_year']}" for row in rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "read_only_bear_false_guarantee_cohort_review",
        "definition": "bonus_bear score_probability row with forecast probability >= 0.999999 and following-year official actual probability < 0.999999",
        "input_artifacts": [str(path.resolve().relative_to(REPO)).replace("\\", "/") for path in args.comparison],
        "false_guarantee_rows": len(rows),
        "by_fold": dict(sorted(by_fold.items())),
        "by_residency": dict(sorted(Counter(row["residency"] for row in rows).items())),
        "by_actual_draw_line_relation": dict(sorted(Counter(row["point_relation_to_draw_line"] for row in rows).items())),
        "by_draw_system_type": dict(sorted(Counter(row["draw_system_type"] for row in rows).items())),
        "output": out_csv.name,
        "status": "PASS_READ_ONLY_REVIEW_READY",
    }
    (args.out_dir / "bear_false_guarantee_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
