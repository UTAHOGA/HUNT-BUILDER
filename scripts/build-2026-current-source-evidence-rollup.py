"""Split current 2026 permit reconciliation into promotion-strength buckets."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
SOLID_OUT = ROOT / "processed_data/audits/current_2026_live_source_solid_codes.csv"
CANDIDATE_OUT = ROOT / "processed_data/audits/current_2026_live_source_single_source_candidates.csv"
REVIEW_OUT = ROOT / "processed_data/audits/current_2026_live_source_review_required.csv"
NO_VALUE_OUT = ROOT / "processed_data/audits/current_2026_live_source_no_permit_value.csv"
SUMMARY_OUT = ROOT / "processed_data/audits/current_2026_live_source_evidence_rollup_summary.json"

SOLID_CONFIDENCE = {"HIGH_CONFIRMED_2PLUS", "MEDIUM_TOTAL_CONFIRMED"}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    rows = read_csv(SOURCE)
    fields = list(rows[0].keys()) if rows else []
    solid = [r for r in rows if r.get("confidence") in SOLID_CONFIDENCE and r.get("recommended_total")]
    single = [
        r
        for r in rows
        if r.get("confidence") == "MEDIUM_SINGLE_SOURCE" and r.get("recommended_total")
    ]
    review = [
        r
        for r in rows
        if r.get("confidence") in {"REVIEW_REQUIRED", "REVIEW_SOURCE_CONFLICT"}
        or r.get("recommended_action") in {"FIND_EXTERNAL_SOURCE_BEFORE_PROMOTION", "REVIEW_BEFORE_PROMOTION"}
    ]
    no_value = [r for r in rows if r.get("confidence") == "NO_PERMIT_VALUE"]

    write_csv(SOLID_OUT, solid, fields)
    write_csv(CANDIDATE_OUT, single, fields)
    write_csv(REVIEW_OUT, review, fields)
    write_csv(NO_VALUE_OUT, no_value, fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": SOURCE.relative_to(ROOT).as_posix(),
        "total_rows": len(rows),
        "solid_definition": "HIGH_CONFIRMED_2PLUS or MEDIUM_TOTAL_CONFIRMED with recommended_total populated.",
        "solid_rows": len(solid),
        "single_source_candidate_rows": len(single),
        "review_required_rows": len(review),
        "no_permit_value_rows": len(no_value),
        "confidence_counts": dict(sorted(Counter(r.get("confidence", "") for r in rows).items())),
        "solid_winner_source_counts": dict(sorted(Counter(r.get("winner_source", "") for r in solid).items())),
        "solid_prefix_counts": dict(sorted(Counter(r.get("hunt_code", "")[:2] for r in solid).items())),
        "single_source_winner_counts": dict(sorted(Counter(r.get("winner_source", "") for r in single).items())),
        "review_prefix_counts": dict(sorted(Counter(r.get("hunt_code", "")[:2] for r in review).items())),
        "outputs": {
            "solid_csv": SOLID_OUT.relative_to(ROOT).as_posix(),
            "single_source_candidates_csv": CANDIDATE_OUT.relative_to(ROOT).as_posix(),
            "review_required_csv": REVIEW_OUT.relative_to(ROOT).as_posix(),
            "no_permit_value_csv": NO_VALUE_OUT.relative_to(ROOT).as_posix(),
            "summary_json": SUMMARY_OUT.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Read-only split. No DATABASE.csv values are modified.",
    }
    SUMMARY_OUT.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
