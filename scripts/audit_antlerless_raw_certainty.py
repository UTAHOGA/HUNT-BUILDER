"""Expose preference cutoffs hidden by the antlerless display calibration.

Read an existing exact-website, source-only joined-row diagnostic. This does
not alter forecasts or official truth. A displayed 99.5% is not a statistical
repair when the underlying preference calculation says 100%.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path


DESIGNS = {
    "PREFERENCE_ANTLERLESS_DEER",
    "PREFERENCE_ANTLERLESS_ELK",
    "PREFERENCE_DOE_PRONGHORN",
}


def raw_preference_probability(row: dict[str, str]) -> float:
    quota = int(row["forecast_public_permits_target"])
    above = int(row["forecast_applicants_above"])
    at_level = int(row["forecast_applicants_at_level"])
    if quota <= 0 or at_level <= 0:
        return 0.0
    return max(0.0, min(1.0, (quota - above) / at_level))


def audit(rows: list[dict[str, str]]) -> tuple[dict[str, object], list[dict[str, str]]]:
    seen: set[tuple[str, ...]] = set()
    counts: Counter[str] = Counter()
    affected: list[dict[str, str]] = []
    for row in rows:
        design = row["draw_design"]
        if design not in DESIGNS:
            continue
        key = tuple(row[field] for field in (
            "fold", "draw_design", "hunt_code", "residency", "points", "draw_pool_key"
        ))
        if key in seen:
            raise ValueError(f"Repeated exact scoring key: {key}")
        seen.add(key)
        counts["joined_rows"] += 1
        raw = raw_preference_probability(row)
        actual = float(row["actual_probability"])
        displayed = float(row["predicted_probability"])
        if raw < 0.999999 or actual >= 0.999999:
            continue
        counts["raw_certainty_misses"] += 1
        counts[f"{design}|{row['residency']}"] += 1
        counts[f"fold:{row['fold']}"] += 1
        counts[f"quota:{row.get('quota_direction', 'UNKNOWN')}"] += 1
        counts[f"stack:{row.get('forecast_above_direction', 'UNKNOWN')}"] += 1
        counts[f"class:{design}|{row.get('forecast_hunt_class', 'UNKNOWN')}"] += 1
        if displayed < 0.999999:
            counts["masked_by_display_calibration"] += 1
        affected.append({
            **row,
            "raw_preference_probability": f"{raw:.6f}",
            "displayed_probability": f"{displayed:.6f}",
            "raw_certainty_miss": "true",
        })
    return {
        "status": "CERTIFICATION_REVIEW_BLOCKED_BY_RAW_CERTAINTY_MISSES" if affected else "NO_RAW_CERTAINTY_MISSES",
        "joined_rows": counts["joined_rows"],
        "raw_certainty_misses": counts["raw_certainty_misses"],
        "masked_by_display_calibration": counts["masked_by_display_calibration"],
        "by_design_residency": {
            key: count for key, count in sorted(counts.items())
            if key.split("|", 1)[0] in DESIGNS
        },
        "by_fold": {key.removeprefix("fold:"): value for key, value in sorted(counts.items()) if key.startswith("fold:")},
        "by_quota_direction": {key.removeprefix("quota:"): value for key, value in sorted(counts.items()) if key.startswith("quota:")},
        "by_forecast_stack_direction": {key.removeprefix("stack:"): value for key, value in sorted(counts.items()) if key.startswith("stack:")},
        "by_design_hunt_class": {key.removeprefix("class:"): value for key, value in sorted(counts.items()) if key.startswith("class:")},
        "interpretation": (
            "Diagnostic of pre-calibration preference mechanics; these are not "
            "ADR-0006 emitted-probability false guarantees. A 0.995 display "
            "ceiling cannot establish that the underlying certainty is sound."
        ),
    }, affected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--error-rows", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error(f"Refusing to overwrite existing audit: {args.output_dir}")
    with args.error_rows.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    summary, affected = audit(rows)
    summary["source_file"] = str(args.error_rows)
    summary["source_sha256"] = hashlib.sha256(args.error_rows.read_bytes()).hexdigest()
    args.output_dir.mkdir(parents=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    with (args.output_dir / "raw_certainty_misses.csv").open("w", encoding="utf-8", newline="") as handle:
        fields = list(affected[0]) if affected else ["fold", "draw_design", "hunt_code", "residency", "points"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(affected)
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
