from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UNRESOLVED = ROOT / "processed_data/audits/current_2026_hunt_code_permit_unresolved.csv"
OUT_DIR = ROOT / "processed_data/audits/current_2026_permit_unresolved_split"
SUMMARY = OUT_DIR / "current_2026_permit_unresolved_split_summary.json"

SOURCE_COLUMNS = {
    "HANUMBER": ("hanumber_res", "hanumber_nr", "hanumber_total"),
    "HUNTTABLE": ("hunttable_res", "hunttable_nr", "hunttable_total"),
    "UTAHDRAWS": ("utahdraws_res", "utahdraws_nr", "utahdraws_total"),
    "BUCK_DEER": ("buck_deer_res", "buck_deer_nr", "buck_deer_total"),
}


def clean(value: object) -> str:
    return str(value or "").strip()


def source_value(row: dict[str, str], source: str) -> tuple[str, str, str]:
    columns = SOURCE_COLUMNS[source]
    return tuple(clean(row.get(column)) for column in columns)  # type: ignore[return-value]


def has_value(value: tuple[str, str, str]) -> bool:
    return any(part not in {"", "0"} for part in value)


def matching_non_database_sources(row: dict[str, str]) -> tuple[list[str], tuple[str, str, str]]:
    values = {source: source_value(row, source) for source in SOURCE_COLUMNS}
    nonblank = {source: value for source, value in values.items() if has_value(value)}
    groups: dict[tuple[str, str, str], list[str]] = {}
    for source, value in nonblank.items():
        groups.setdefault(value, []).append(source)
    if not groups:
        return [], ("", "", "")
    best_value, best_sources = max(groups.items(), key=lambda item: (len(item[1]), item[0]))
    return best_sources, best_value


def bucket(row: dict[str, str]) -> str:
    matching_sources, _ = matching_non_database_sources(row)
    if row.get("confidence") == "REVIEW_SOURCE_CONFLICT" and len(matching_sources) >= 3:
        return "strong_3_source_current_matches"
    if row.get("confidence") == "REVIEW_SOURCE_CONFLICT":
        return "true_source_conflicts"
    if row.get("winner_source") == "NONE_EXTERNAL_DATABASE_REFERENCE_ONLY":
        return "database_only_external_missing"
    if row.get("confidence") == "NO_PERMIT_VALUE":
        return "true_no_permit_value"
    return "true_source_conflicts"


def enrich(row: dict[str, str], split_bucket: str) -> dict[str, str]:
    matching_sources, matching_value = matching_non_database_sources(row)
    out = dict(row)
    out["split_bucket"] = split_bucket
    out["matching_non_database_sources"] = "|".join(matching_sources)
    out["matching_source_count"] = str(len(matching_sources))
    out["matching_res"] = matching_value[0]
    out["matching_nr"] = matching_value[1]
    out["matching_total"] = matching_value[2]
    if split_bucket == "strong_3_source_current_matches":
        out["split_review_note"] = "Three or more non-database current sources match; unresolved only because another source conflicts."
    elif split_bucket == "true_source_conflicts":
        out["split_review_note"] = "Non-database sources conflict and fewer than three current sources match."
    elif split_bucket == "database_only_external_missing":
        out["split_review_note"] = "Only DATABASE reference value is present; external current source still needed before promotion."
    elif split_bucket == "true_no_permit_value":
        out["split_review_note"] = "No current permit value found in the compared sources."
    else:
        out["split_review_note"] = "Review bucket fallback."
    return out


def main() -> int:
    if not UNRESOLVED.exists():
        raise FileNotFoundError(UNRESOLVED)
    with UNRESOLVED.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    buckets: dict[str, list[dict[str, str]]] = {
        "strong_3_source_current_matches": [],
        "true_source_conflicts": [],
        "database_only_external_missing": [],
        "true_no_permit_value": [],
    }
    for row in rows:
        split_bucket = bucket(row)
        buckets[split_bucket].append(enrich(row, split_bucket))
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for name, bucket_rows in buckets.items():
        path = OUT_DIR / f"{name}.csv"
        outputs[name] = path.relative_to(ROOT).as_posix()
        fieldnames = list(bucket_rows[0].keys()) if bucket_rows else list(rows[0].keys()) + [
            "split_bucket",
            "matching_non_database_sources",
            "matching_source_count",
            "matching_res",
            "matching_nr",
            "matching_total",
            "split_review_note",
        ]
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(bucket_rows)
    total_split_rows = sum(len(bucket_rows) for bucket_rows in buckets.values())
    if total_split_rows != len(rows):
        raise RuntimeError(f"Split row count {total_split_rows} does not match unresolved row count {len(rows)}")
    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_unresolved_csv": UNRESOLVED.relative_to(ROOT).as_posix(),
        "source_unresolved_rows": len(rows),
        "split_total_rows": total_split_rows,
        "bucket_counts": {name: len(bucket_rows) for name, bucket_rows in buckets.items()},
        "bucket_prefix_counts": {
            name: dict(sorted(Counter(row["hunt_code"][:2] for row in bucket_rows).items()))
            for name, bucket_rows in buckets.items()
        },
        "bucket_species_counts": {
            name: dict(sorted(Counter(row.get("species") or "UNKNOWN" for row in bucket_rows).items()))
            for name, bucket_rows in buckets.items()
        },
        "outputs": outputs | {"summary_json": SUMMARY.relative_to(ROOT).as_posix()},
        "notes": [
            "No source data or DATABASE.csv values are modified by this split.",
            "strong_3_source_current_matches are unresolved only because another non-database source conflicts with three or more matching current sources.",
        ],
    }
    SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
