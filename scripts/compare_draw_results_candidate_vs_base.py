"""Compare draw-results candidate promotion files against draw_results_long by year.

This is a focused parity audit, used to confirm whether candidate source rows align
with the normalized base truth surface for the same draw year.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

DRAW_LONG_PATH = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
OUT_DIR = ROOT / "audits" / "draw_truth_rebuild"

KEY_FIELDS = ("year", "hunt_code", "residency", "points", "draw_pool")

COMPARE_FIELDS = (
    "draw_method",
    "hunt_name",
    "species",
    "sex_type",
    "hunt_type",
    "hunt_class",
    "weapon",
    "season",
    "eligible_applicants",
    "bonus_permits",
    "preference_permits",
    "regular_permits",
    "total_permits",
    "total_drawn",
    "success_ratio",
    "p_draw_percent",
    "resident_eligible_applicants",
    "resident_bonus_permits",
    "resident_regular_permits",
    "resident_total_permits",
    "nonresident_eligible_applicants",
    "nonresident_bonus_permits",
    "nonresident_regular_permits",
    "nonresident_total_permits",
    "total_public_permits",
    "total_public_draw_permits",
    "total_quota",
    "record_kind",
    "draw_type",
)

PAIR_JOBS = [
    (
        "2021_to_2022",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2021_for_2022_candidate_promotion_file_records.csv",
        "2021",
        "draw_results_2021 candidate to 2021 base",
    ),
    (
        "2022_to_2023",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2022_for_2023_candidate_promotion_file_records.csv",
        "2022",
        "draw_results_2022 candidate to 2022 base",
    ),
    (
        "2023_to_2024",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2023_for_2024_candidate_promotion_file_records.csv",
        "2023",
        "draw_results_2023 candidate to 2023 base",
    ),
    (
        "2024_to_2025",
        ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_2024_for_2025_candidate_promotion_file_records.csv",
        "2024",
        "draw_results_2024 candidate to 2024 base",
    ),
]


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        rows = [dict(row) for row in reader]
        return list(reader.fieldnames or []), rows


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def normalize_numeric(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    if text.lower() in {"na", "n/a", "none", "null", "nan"}:
        return ""
    if "," in text:
        text = text.replace(",", "")
    try:
        if "." in text:
            return str(int(float(text)))
        return str(int(text))
    except Exception:
        return text


def key_for(row: dict[str, str]) -> tuple[str, ...]:
    return (
        normalize_text(row.get("year") or row.get("draw_year") or row.get("reported_hunt_year_inferred") or row.get("publish_year")),
        normalize_text(row.get("hunt_code")),
        normalize_text(row.get("residency")).title(),
        normalize_numeric(row.get("points")),
        normalize_text(row.get("draw_pool")).lower(),
    )


def rows_by_key(rows: list[dict[str, str]]) -> dict[tuple[str, ...], list[dict[str, str]]]:
    buckets: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        buckets.setdefault(key_for(row), []).append(row)
    return buckets


def build_base_year_rows(year: str) -> list[dict[str, str]]:
    fields, all_rows = read_csv(DRAW_LONG_PATH)
    wanted = []
    for row in all_rows:
        row_year = normalize_text(row.get("year") or row.get("draw_year") or row.get("reported_draw_year_inferred") or row.get("publish_year"))
        if row_year == year:
            wanted.append(row)
    return wanted


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def compare_pair(pair_label: str, candidate_path: Path, base_year: str, description: str) -> dict[str, Any]:
    candidate_fields, candidate_rows = read_csv(candidate_path)
    base_rows = build_base_year_rows(base_year)

    base_by_key = rows_by_key(base_rows)
    candidate_by_key = rows_by_key(candidate_rows)

    base_keys = set(base_by_key.keys())
    candidate_keys = set(candidate_by_key.keys())

    shared_keys = base_keys & candidate_keys
    core_shared_keys = len(shared_keys)
    candidate_only_keys = sorted(candidate_keys - base_keys)
    base_only_keys = sorted(base_keys - candidate_keys)
    candidate_only_rows = sum(max(0, len(candidate_by_key[key]) - len(base_by_key[key])) for key in shared_keys) + len(
        candidate_only_keys
    )
    base_only_rows = sum(max(0, len(base_by_key[key]) - len(candidate_by_key[key])) for key in shared_keys) + len(base_only_keys)

    core_overlap_rows = 0
    mismatched_value_fields_on_overlaps = 0
    mismatch_samples: list[dict[str, str]] = []
    for key in sorted(shared_keys):
        candidate_bucket = candidate_by_key[key]
        base_bucket = base_by_key[key]
        overlap_count = min(len(candidate_bucket), len(base_bucket))
        core_overlap_rows += overlap_count
        for idx in range(overlap_count):
            c_row = candidate_bucket[idx]
            b_row = base_bucket[idx]
            diff_fields = []
            for field in COMPARE_FIELDS:
                if normalize_text(c_row.get(field)) != normalize_text(b_row.get(field)):
                    diff_fields.append(field)
            if diff_fields:
                mismatched_value_fields_on_overlaps += 1
                if len(mismatch_samples) < 200:
                    sample = {
                        "year": c_row.get("year", ""),
                        "hunt_code": c_row.get("hunt_code", ""),
                        "residency": c_row.get("residency", ""),
                        "points": c_row.get("points", ""),
                        "draw_pool": c_row.get("draw_pool", ""),
                        "mismatched_fields": "|".join(diff_fields),
                        "delta": str(1),
                    }
                    write_mismatch_row(sample, mismatch_samples)

    candidate_only_samples: list[dict[str, str]] = []
    for key in list(candidate_only_keys)[:100]:
        sample_row = candidate_by_key[key][0]
        candidate_only_samples.append(
            {
                "year": sample_row.get("year", ""),
                "hunt_code": sample_row.get("hunt_code", ""),
                "species": sample_row.get("species", ""),
                "sex_type": sample_row.get("sex_type", ""),
                "hunt_type": sample_row.get("hunt_type", ""),
                "weapon": sample_row.get("weapon", ""),
                "hunt_class": sample_row.get("hunt_class", ""),
                "draw_pool": sample_row.get("draw_pool", ""),
                "residency": sample_row.get("residency", ""),
                "points": sample_row.get("points", ""),
                "delta": str(len(candidate_by_key[key]) - len(base_by_key.get(key, []))),
            }
        )

    base_only_samples: list[dict[str, str]] = []
    for key in list(base_only_keys)[:100]:
        sample_row = base_by_key[key][0]
        base_only_samples.append(
            {
                "year": sample_row.get("year", ""),
                "hunt_code": sample_row.get("hunt_code", ""),
                "species": sample_row.get("species", ""),
                "sex_type": sample_row.get("sex_type", ""),
                "hunt_type": sample_row.get("hunt_type", ""),
                "weapon": sample_row.get("weapon", ""),
                "hunt_class": sample_row.get("hunt_class", ""),
                "draw_pool": sample_row.get("draw_pool", ""),
                "residency": sample_row.get("residency", ""),
                "points": sample_row.get("points", ""),
                "delta": str(len(base_by_key[key]) - len(candidate_by_key.get(key, []))),
            }
        )

    report: dict[str, Any] = {
        "pair": pair_label,
        "description": description,
        "candidate_file": str(candidate_path.relative_to(ROOT)),
        "base_file": str(DRAW_LONG_PATH.relative_to(ROOT)),
        "base_year": base_year,
        "candidate_rows": len(candidate_rows),
        "base_rows": len(base_rows),
        "core_shared_keys": core_shared_keys,
        "core_overlap_rows": core_overlap_rows,
        "candidate_only_rows": candidate_only_rows,
        "base_only_rows": base_only_rows,
        "candidate_only_keys": len(candidate_only_keys),
        "base_only_keys": len(base_only_keys),
        "mismatched_value_fields_on_overlaps": mismatched_value_fields_on_overlaps,
        "candidate_only_samples": candidate_only_samples[:25],
        "base_only_samples": base_only_samples[:25],
        "mismatch_sample_count": len(mismatch_samples),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
    }

    return {
        "report": report,
        "candidate_rows": candidate_rows,
        "base_rows": base_rows,
        "candidate_by_key": candidate_by_key,
        "base_by_key": base_by_key,
        "candidate_only_rows_data": candidate_only_rows,
        "base_only_rows_data": base_only_rows,
        "mismatch_samples": mismatch_samples,
        "candidate_only_samples_full": candidate_only_samples,
        "base_only_samples_full": base_only_samples,
    }


def write_mismatch_row(sample: dict[str, str], bucket: list[dict[str, str]]) -> None:
    bucket.append(sample)


def main() -> int:
    summaries: dict[str, Any] = {}
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for pair_label, candidate_path, base_year, description in PAIR_JOBS:
        if not candidate_path.exists():
            continue

        result = compare_pair(pair_label, candidate_path, base_year, description)
        report = result["report"]
        summaries[pair_label] = report

        mismatch_path = OUT_DIR / f"{pair_label}_truth_vs_base_mismatch.csv"
        only_path = OUT_DIR / f"{pair_label}_truth_vs_base_only_rows.csv"

        write_csv(
            mismatch_path,
            result["mismatch_samples"],
            ["year", "hunt_code", "residency", "draw_pool", "points", "mismatched_fields", "delta"],
        )
        write_csv(
            only_path,
            result["candidate_only_samples_full"] + result["base_only_samples_full"],
            ["year", "hunt_code", "species", "sex_type", "hunt_type", "weapon", "hunt_class", "draw_pool", "residency", "points", "delta"],
        )

        report["outputs"] = {
            "mismatch_csv": str(mismatch_path.relative_to(ROOT)),
            "only_rows_csv": str(only_path.relative_to(ROOT)),
        }

        with (OUT_DIR / f"{pair_label}_truth_vs_base_report.json").open("w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")

    with (OUT_DIR / "truth_vs_base_candidate_parity_2021_2022_and_2022_2023_report.json").open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "generated_utc": datetime.now(timezone.utc).isoformat(),
                "pairs": summaries,
            },
            handle,
            indent=2,
            ensure_ascii=False,
        )
        handle.write("\n")

    print(f"Wrote parity pass outputs under: {OUT_DIR}")
    for key, summary in summaries.items():
        print(
            f"{key}: candidate_rows={summary['candidate_rows']} base_rows={summary['base_rows']} "
            f"shared_keys={summary['core_shared_keys']} overlap_rows={summary['core_overlap_rows']} "
            f"candidate_only={summary['candidate_only_rows']} base_only={summary['base_only_rows']} "
            f"mismatch_rows={summary['mismatched_value_fields_on_overlaps']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
