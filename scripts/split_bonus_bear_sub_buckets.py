#!/usr/bin/env python3
"""Split bonus bear prediction rows into explicit sub-buckets.

The Utah bonus-bear pile contains multiple semantic row groups:

- limited-entry draw odds rows
- restricted pursuit rows
- unlimited pursuit rows
- harvest-objective availability rows
- non-public / conservation rows

This splitter keeps those piles separate so scoring and auditing can treat the
actual draw-odds rows differently from pursuit and harvest-objective rows.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_ROOT = ROOT / "audits" / "prediction_blind_year_to_year"

LIMITED_ENTRY_BUCKET = "limited_entry_draw_odds"
RESTRICTED_PURSUIT_BUCKET = "restricted_pursuit"
UNLIMITED_PURSUIT_BUCKET = "unlimited_pursuit"
HARVEST_OBJECTIVE_BUCKET = "harvest_objective"
NON_PUBLIC_BUCKET = "non_public"
UNKNOWN_BUCKET = "unknown"

SCORABLE_STATUSES = {
    "MODELED_SOURCE_BACKED_ROLL_FORWARD",
    "MODELED_PREFERENCE",
    "MODELED_BONUS",
}

EXCLUDED_STATUSES = {
    "EXCLUDED_NOT_PREDICTIVE_DRAW",
    "SOURCE_DATA_INCOMPLETE_NO_PUBLIC_DRAW_PROBABILITY",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def bonus_bear_bucket(row: Mapping[str, object]) -> str:
    subtype = clean(row.get("bear_draw_subtype")).upper()
    hunt_type = clean(row.get("hunt_type")).lower()
    draw_method = clean(row.get("draw_method")).lower()
    text = " ".join(
        clean(row.get(field)).lower()
        for field in (
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type",
            "hunt_class",
            "weapon",
            "draw_pool",
            "bear_draw_subtype",
            "permit_availability_type",
            "classification_status",
            "reason_codes",
        )
    )

    if subtype in {"", "LIMITED_ENTRY_BEAR_HUNT"}:
        if "bear" in text and draw_method == "bonus":
            return LIMITED_ENTRY_BUCKET
        if clean(row.get("probability_metric")).lower() == "p_draw":
            return LIMITED_ENTRY_BUCKET
        return LIMITED_ENTRY_BUCKET
    if subtype == "RESTRICTED_BEAR_PURSUIT":
        return RESTRICTED_PURSUIT_BUCKET
    if subtype == "UNLIMITED_PURSUIT_PERMIT":
        return UNLIMITED_PURSUIT_BUCKET
    if subtype == "HARVEST_OBJECTIVE_AVAILABILITY":
        return HARVEST_OBJECTIVE_BUCKET
    if subtype == "CONSERVATION_OR_NON_PUBLIC":
        return NON_PUBLIC_BUCKET
    if "pursuit" in text:
        return RESTRICTED_PURSUIT_BUCKET if "restricted" in text else UNLIMITED_PURSUIT_BUCKET
    if "harvest objective" in text or "harvest_objective" in text:
        return HARVEST_OBJECTIVE_BUCKET
    if "conservation" in text or "non public" in text or "non-public" in text:
        return NON_PUBLIC_BUCKET
    return UNKNOWN_BUCKET


def bonus_bear_bucket_reason(row: Mapping[str, object], bucket: str) -> str:
    status = clean(row.get("classification_status")).upper()
    reason_codes = clean(row.get("reason_codes"))
    probability_metric = clean(row.get("probability_metric")).lower()
    if bucket == LIMITED_ENTRY_BUCKET:
        if status in EXCLUDED_STATUSES:
            return "DRAW_ODDS_PENDING_NO_PUBLIC_PROBABILITY"
        if probability_metric == "p_draw":
            return "DRAW_ODDS_SCORABLE"
        return "DRAW_ODDS_NON_DRAW_METRIC"
    if bucket == RESTRICTED_PURSUIT_BUCKET:
        return "RESTRICTED_PURSUIT"
    if bucket == UNLIMITED_PURSUIT_BUCKET:
        return "UNLIMITED_PURSUIT"
    if bucket == HARVEST_OBJECTIVE_BUCKET:
        return "HARVEST_OBJECTIVE"
    if bucket == NON_PUBLIC_BUCKET:
        return "NON_PUBLIC"
    return reason_codes or status or "UNKNOWN"


def is_scorable_bonus_bear_row(row: Mapping[str, object]) -> bool:
    bucket = bonus_bear_bucket(row)
    status = clean(row.get("classification_status")).upper()
    probability_metric = clean(row.get("probability_metric")).lower()
    return bucket == LIMITED_ENTRY_BUCKET and probability_metric == "p_draw" and status in SCORABLE_STATUSES


def split_bonus_bear_rows(rows: Sequence[Mapping[str, object]]) -> tuple[list[dict[str, object]], dict[str, list[dict[str, object]]], dict[str, int]]:
    bucketed_rows: list[dict[str, object]] = []
    buckets: dict[str, list[dict[str, object]]] = defaultdict(list)
    counts = Counter()
    for row in rows:
        item = dict(row)
        bucket = bonus_bear_bucket(item)
        item["bonus_bear_bucket"] = bucket
        item["bonus_bear_bucket_reason"] = bonus_bear_bucket_reason(item, bucket)
        item["bonus_bear_bucket_is_scorable"] = str(is_scorable_bonus_bear_row(item)).lower()
        bucketed_rows.append(item)
        buckets[bucket].append(item)
        counts[bucket] += 1
    return bucketed_rows, buckets, dict(counts)


def _row_sort_key(row: Mapping[str, object]) -> tuple[str, str, str, str]:
    return (
        clean(row.get("hunt_code")).upper(),
        clean(row.get("hunt_name")),
        clean(row.get("classification_status")),
        clean(row.get("probability_metric")),
    )


def build_manifest(rows: Sequence[Mapping[str, object]], buckets: Mapping[str, Sequence[Mapping[str, object]]], input_path: Path, output_root: Path) -> dict[str, object]:
    total_rows = len(rows)
    scorable_rows = sum(1 for row in rows if clean(row.get("bonus_bear_bucket_is_scorable")).lower() == "true")
    excluded_rows = total_rows - scorable_rows
    by_bucket = []
    for bucket in sorted(buckets):
        bucket_rows = list(buckets[bucket])
        by_bucket.append(
            {
                "bucket": bucket,
                "row_count": len(bucket_rows),
                "scorable_row_count": sum(1 for row in bucket_rows if clean(row.get("bonus_bear_bucket_is_scorable")).lower() == "true"),
                "excluded_row_count": sum(1 for row in bucket_rows if clean(row.get("bonus_bear_bucket_is_scorable")).lower() != "true"),
                "probability_metric_counts": json.dumps(Counter(clean(row.get("probability_metric")) or "(blank)" for row in bucket_rows), sort_keys=True),
                "classification_status_counts": json.dumps(Counter(clean(row.get("classification_status")) or "(blank)" for row in bucket_rows), sort_keys=True),
                "unique_hunt_codes": len({clean(row.get("hunt_code")).upper() for row in bucket_rows if clean(row.get("hunt_code"))}),
            }
        )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input_path": str(input_path),
        "output_root": str(output_root),
        "total_rows": total_rows,
        "scorable_rows": scorable_rows,
        "excluded_rows": excluded_rows,
        "bonus_indicator_note": "bonus is the draw-method flag; bucketing is based on bear subtype and scoreability.",
        "bucket_count": len(buckets),
        "bucket_rows": by_bucket,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True, help="Bonus bear prediction CSV to split.")
    parser.add_argument(
        "--output-root",
        type=Path,
        default=DEFAULT_OUTPUT_ROOT,
        help="Root folder for the bucketed bonus-bear artifacts.",
    )
    args = parser.parse_args(argv)

    fieldnames, rows = read_csv(args.input)
    bucketed_rows, buckets, _ = split_bonus_bear_rows(rows)
    ordered_fieldnames = list(fieldnames)
    for extra in ("bonus_bear_bucket", "bonus_bear_bucket_reason", "bonus_bear_bucket_is_scorable"):
        if extra not in ordered_fieldnames:
            ordered_fieldnames.append(extra)

    run_name = args.input.stem
    out_dir = args.output_root / "bonus_bear_sub_buckets" / run_name
    out_dir.mkdir(parents=True, exist_ok=True)

    write_csv(out_dir / "bonus_bear_bucketed.csv", bucketed_rows, ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_draw_odds_scorable.csv", [row for row in bucketed_rows if row["bonus_bear_bucket"] == LIMITED_ENTRY_BUCKET and clean(row.get("bonus_bear_bucket_is_scorable")).lower() == "true"], ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_draw_odds_unscorable.csv", [row for row in bucketed_rows if row["bonus_bear_bucket"] == LIMITED_ENTRY_BUCKET and clean(row.get("bonus_bear_bucket_is_scorable")).lower() != "true"], ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_restricted_pursuit.csv", buckets.get(RESTRICTED_PURSUIT_BUCKET, []), ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_unlimited_pursuit.csv", buckets.get(UNLIMITED_PURSUIT_BUCKET, []), ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_harvest_objective.csv", buckets.get(HARVEST_OBJECTIVE_BUCKET, []), ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_non_public.csv", buckets.get(NON_PUBLIC_BUCKET, []), ordered_fieldnames)
    write_csv(out_dir / "bonus_bear_unknown.csv", buckets.get(UNKNOWN_BUCKET, []), ordered_fieldnames)

    manifest = build_manifest(bucketed_rows, buckets, args.input, out_dir)
    (out_dir / "bonus_bear_bucket_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    md_lines = [
        "# Bonus Bear Sub-Buckets",
        "",
        f"Input: `{args.input}`",
        f"Output: `{out_dir}`",
        "",
        "## Note",
        "",
        "The word `bonus` indicates the draw-method family. It does not mean every row is a scorable draw-odds row.",
        "",
        "## Buckets",
        "",
    ]
    for item in manifest["bucket_rows"]:
        md_lines.append(
            f"- `{item['bucket']}`: rows={item['row_count']}, scorable={item['scorable_row_count']}, excluded={item['excluded_row_count']}"
        )
    (out_dir / "bonus_bear_bucket_report.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
