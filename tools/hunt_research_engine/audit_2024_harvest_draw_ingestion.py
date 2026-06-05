#!/usr/bin/env python3
"""Audit 2024 draw/harvest ingestion for Hunt Research engine feeds.

This is a read-only proof pass for the 2024 harvest source CSVs and 2024 draw
results. It checks whether normalized harvest truth reached the engine-facing
harvest feature tables and identifies narrow feature-feeder gaps that can be
repaired from normalized truth without touching raw sources.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"

RAW_HARVEST_CSVS = [
    "big_game_oil_hunt_number_harvest_supplement_2024.csv",
    "bison_oial_hunt_harvest_2024.csv",
    "desert_bighorn_hunt_harvest_2024.csv",
    "elk_general_season_harvest_additional_2024.csv",
    "harvest_quality_features_by_hunt_code_2024_for_2025.csv",
    "harvest_quality_features_elk_age_2024_for_2025.csv",
    "harvest_quality_features_extra_oil_2024_for_2025.csv",
    "harvest_results_2024_for_2025_all_long.csv",
    "harvest_results_2024_for_2025_ANTLERLESS_DEER.csv",
    "harvest_results_2024_for_2025_ANTLERLESS_ELK.csv",
    "harvest_results_2024_for_2025_BISON.csv",
    "harvest_results_2024_for_2025_BLACK_BEAR.csv",
    "harvest_results_2024_for_2025_DESERT_BIGHORN_SHEEP.csv",
    "harvest_results_2024_for_2025_ELK.csv",
    "harvest_results_2024_for_2025_extra_goat_bison_desert_sheep_long.csv",
]

FILES = {
    "raw_harvest_dir": "pipeline/RAW/hunt_unit_database/2025/csv/harvest data",
    "harvest_truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "harvest_model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "draw_truth_long": "data_truth/draw_results_truth/normalized/draw_results_long.csv",
    "draw_reality_engine": "processed_data/draw_reality_engine.csv",
    "draw_reality_engine_v2": "processed_data/draw_reality_engine_v2.csv",
}


@dataclass(frozen=True)
class Paths:
    root: Path
    out_dir: Path

    def file(self, key: str) -> Path:
        return self.root / FILES[key]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def code_count(rows: list[dict[str, str]]) -> int:
    return len({clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))})


def summarize_year(rows: list[dict[str, str]], year_field: str, year: str) -> dict[str, object]:
    hits = [row for row in rows if clean(row.get(year_field)) == year]
    source_counts = Counter(clean(row.get("source_file")) for row in hits if clean(row.get("source_file")))
    species_counts = Counter(clean(row.get("species")) for row in hits if clean(row.get("species")))
    return {
        "rows": len(hits),
        "hunt_codes": code_count(hits),
        "source_counts_top": dict(source_counts.most_common(20)),
        "species_counts": dict(sorted(species_counts.items())),
    }


def feature_key(row: dict[str, str]) -> tuple[str, str]:
    return clean(row.get("reported_hunt_year")), clean(row.get("hunt_code")).upper()


def source_summary(path: Path) -> dict[str, object]:
    fields, rows = read_csv(path)
    return {
        "source_csv": path.name,
        "raw_path": str(path),
        "raw_exists": path.exists(),
        "raw_size_bytes": path.stat().st_size if path.exists() else 0,
        "raw_rows": len(rows),
        "raw_columns": len(fields),
        "has_hunt_code": "hunt_code" in fields,
        "hunt_codes": code_count(rows),
        "status": "RAW_GENERATED_CSV_PRESENT" if path.exists() else "RAW_GENERATED_CSV_MISSING",
    }


def build_audit(paths: Paths) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    _, truth_long = read_csv(paths.file("harvest_truth_long"))
    _, truth_features = read_csv(paths.file("harvest_truth_features"))
    _, model_long = read_csv(paths.file("harvest_model_long"))
    _, model_features = read_csv(paths.file("harvest_model_features"))
    _, feature_model = read_csv(paths.file("harvest_feature_model_2026"))
    _, draw_truth = read_csv(paths.file("draw_truth_long"))
    _, draw_engine = read_csv(paths.file("draw_reality_engine"))
    _, draw_v2 = read_csv(paths.file("draw_reality_engine_v2"))

    raw_dir = paths.file("raw_harvest_dir")
    raw_rows = [source_summary(raw_dir / name) for name in RAW_HARVEST_CSVS]

    truth_2024_keys = {feature_key(row) for row in truth_features if feature_key(row)[0] == "2024" and feature_key(row)[1]}
    model_2024_keys = {feature_key(row) for row in model_features if feature_key(row)[0] == "2024" and feature_key(row)[1]}
    missing_model_keys = sorted(truth_2024_keys - model_2024_keys)
    truth_by_key = {feature_key(row): row for row in truth_features if feature_key(row)[0] == "2024" and feature_key(row)[1]}
    missing_rows = [
        {
            "reported_hunt_year": key[0],
            "hunt_code": key[1],
            "species": clean(truth_by_key[key].get("species")),
            "hunt_name": clean(truth_by_key[key].get("hunt_name")),
            "source_file": clean(truth_by_key[key].get("source_file")),
            "recommended_action": "APPEND_TO_ENGINE_FEATURE_FEEDER_FROM_NORMALIZED_TRUTH",
        }
        for key in missing_model_keys
    ]

    feature_source_years = Counter()
    feature_codes_using_2024 = set()
    for row in feature_model:
        years = clean(row.get("harvest_feature_source_years")).split("|")
        if "2024" in years:
            feature_source_years["feature_rows_using_2024"] += 1
            if clean(row.get("hunt_code")):
                feature_codes_using_2024.add(clean(row.get("hunt_code")).upper())

    draw_engine_2024 = summarize_year(draw_engine, "year", "2024")
    draw_v2_2024 = summarize_year(draw_v2, "year", "2024")
    status_counts = Counter(clean(row["status"]) for row in raw_rows)
    if missing_rows:
        result = "PASS_WITH_SOURCE_BACKED_ENGINE_FEATURE_GAPS"
        recommended_next_step = "Run ingest_2024_harvest_features_to_engine.py --apply to append only the missing source-backed normalized truth feature rows, then rematerialize the harvest feature model."
    else:
        result = "PASS"
        recommended_next_step = "No 2024 source-backed harvest feature feeder gaps remain. Continue with downstream engine/runtime regeneration only when the broader production phase calls for it."

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "2024_harvest_draw_ingestion",
        "result": result,
        "reported_hunt_year": 2024,
        "model_target_year": 2025,
        "raw_harvest_csvs_checked": len(raw_rows),
        "raw_harvest_status_counts": dict(sorted(status_counts.items())),
        "harvest_truth_2024": summarize_year(truth_long, "reported_hunt_year", "2024"),
        "harvest_truth_features_2024": summarize_year(truth_features, "reported_hunt_year", "2024"),
        "harvest_model_long_2024": summarize_year(model_long, "reported_hunt_year", "2024"),
        "harvest_model_features_2024": summarize_year(model_features, "reported_hunt_year", "2024"),
        "draw_truth_2024": summarize_year(draw_truth, "year", "2024"),
        "draw_reality_engine_2024": draw_engine_2024,
        "draw_reality_engine_v2_2024": draw_v2_2024,
        "draw_engine_v2_matches_draw_truth_rows": draw_v2_2024["rows"] == summarize_year(draw_truth, "year", "2024")["rows"],
        "draw_engine_legacy_has_2024_rows": draw_engine_2024["rows"] > 0,
        "truth_feature_keys_2024": len(truth_2024_keys),
        "engine_feature_keys_2024": len(model_2024_keys),
        "missing_engine_feature_keys_2024": len(missing_rows),
        "feature_model_rows_using_2024": feature_source_years["feature_rows_using_2024"],
        "feature_model_hunt_codes_using_2024": len(feature_codes_using_2024),
        "guardrail": "2024 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.",
        "recommended_next_step": recommended_next_step,
    }
    return summary, raw_rows, missing_rows


def write_csv_safe(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, summary: dict[str, object], raw_rows: list[dict[str, object]], missing_rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2024 Harvest/Draw Ingestion Audit",
        "",
        "Read-only alignment proof for the 2024 draw and harvest data feeding Hunt Research.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Reported hunt year: `{summary['reported_hunt_year']}`.",
        f"- Model target year: `{summary['model_target_year']}`.",
        f"- Raw generated harvest CSVs checked: `{summary['raw_harvest_csvs_checked']}`.",
        f"- Harvest truth rows for 2024: `{summary['harvest_truth_2024']['rows']}`.",
        f"- Harvest truth hunt codes for 2024: `{summary['harvest_truth_2024']['hunt_codes']}`.",
        f"- Engine harvest long rows for 2024: `{summary['harvest_model_long_2024']['rows']}`.",
        f"- Engine harvest feature rows for 2024 before repair: `{summary['harvest_model_features_2024']['rows']}`.",
        f"- Missing engine feature rows sourced from normalized truth: `{summary['missing_engine_feature_keys_2024']}`.",
        f"- Draw truth rows for 2024: `{summary['draw_truth_2024']['rows']}`.",
        f"- Draw truth hunt codes for 2024: `{summary['draw_truth_2024']['hunt_codes']}`.",
        f"- Draw reality engine v2 rows for 2024: `{summary['draw_reality_engine_v2_2024']['rows']}`.",
        f"- Draw reality engine v2 matches draw truth row count: `{summary['draw_engine_v2_matches_draw_truth_rows']}`.",
        f"- Legacy draw_reality_engine.csv has 2024 rows: `{summary['draw_engine_legacy_has_2024_rows']}`.",
        "",
        "## Missing Engine Feature Rows",
        "",
        "| Hunt Code | Species | Hunt Name | Source | Action |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in missing_rows:
        lines.append(f"| {row['hunt_code']} | {row['species']} | {row['hunt_name']} | {row['source_file']} | {row['recommended_action']} |")
    if not missing_rows:
        lines.append("|  |  |  |  | No source-backed gaps found |")
    lines.extend(
        [
            "",
            "## Raw Generated CSV Inventory",
            "",
            "| CSV | Rows | Hunt Codes | Status |",
            "| --- | ---: | ---: | --- |",
        ]
    )
    for row in raw_rows:
        lines.append(f"| {row['source_csv']} | {row['raw_rows']} | {row['hunt_codes']} | {row['status']} |")
    lines.extend(
        [
            "",
            "## Guardrail",
            "",
            str(summary["guardrail"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Repository root.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Audit output directory.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    out_dir = (root / args.out_dir).resolve()
    summary, raw_rows, missing_rows = build_audit(Paths(root=root, out_dir=out_dir))
    base = out_dir / "harvest_draw_ingestion_2024"
    raw_columns = [
        "source_csv",
        "raw_path",
        "raw_exists",
        "raw_size_bytes",
        "raw_rows",
        "raw_columns",
        "has_hunt_code",
        "hunt_codes",
        "status",
    ]
    gap_columns = ["reported_hunt_year", "hunt_code", "species", "hunt_name", "source_file", "recommended_action"]
    write_csv_safe(base.with_suffix(".csv"), raw_rows, raw_columns)
    write_csv_safe(out_dir / "harvest_draw_ingestion_2024_engine_feature_gaps.csv", missing_rows, gap_columns)
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "raw_rows": raw_rows, "missing_rows": missing_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(base.with_suffix(".md"), summary, raw_rows, missing_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
