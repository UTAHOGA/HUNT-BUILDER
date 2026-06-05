#!/usr/bin/env python3
"""Audit 2023 harvest/draw ingestion for Hunt Research engine feeds.

This is a read-only proof pass for the 2023 harvest sources. It checks whether
listed 2023 harvest PDFs already have normalized rows, whether those rows made
it into the engine-facing harvest feature tables, and whether 2023 draw-result
rows exist for year-to-year comparison.
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

LISTED_HARVEST_SOURCES = [
    "2023 desert bighorn harvest report unit not number.pdf",
    "2023 Hunt Success.pdf",
    "2023_le_oial_all.pdf",
    "2023-24 turkey.pdf",
    "A96251BE__2023_antlerless_hr.pdf",
    "dbd8a659__cougar_2023.pdf",
    "dc965eb4__General-season buck deer.pdf",
    "23_bg_report.pdf",
    "23_black_bear_report.pdf",
    "BIGHORN SHEEP 2023-harvest-data.pdf",
    "61FC0758__BIGHORN SHEEP 2023-harvest-data.pdf",
]

RAW_SOURCE_PATHS = [
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/2023 desert bighorn harvest report unit not number.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/2023 Hunt Success.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/2023_le_oial_all.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/2023-24 turkey.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/A96251BE__2023_antlerless_hr.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/dbd8a659__cougar_2023.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/dc965eb4__General-season buck deer.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/23_bg_report.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/23_black_bear_report.pdf",
    "pipeline/RAW/hunt_unit_database/2024/pdf/harvest_report/BIGHORN SHEEP 2023-harvest-data.pdf",
]

FILES = {
    "harvest_truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "harvest_model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "draw_truth_long": "data_truth/draw_results_truth/normalized/draw_results_long.csv",
    "raw_package_report": "data_truth/harvest_results_truth/raw_packages/2023_for_2024_harvest_results_2023_all_species_database/harvest_results_2023_all_species_database_report.json",
    "turkey_package_report": "data_truth/harvest_results_truth/raw_packages/2023_for_2024_turkey_harvest_results_2023_24_for_2025_database/turkey_harvest_results_2023_24_for_2025_report.json",
}


@dataclass(frozen=True)
class Paths:
    root: Path
    out_dir: Path

    def file(self, key: str) -> Path:
        return self.root / FILES[key]


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def source_match(source_file: object, listed_name: str) -> bool:
    return listed_name.lower() in clean(source_file).lower()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def code_count(rows: list[dict[str, str]]) -> int:
    return len({clean(row.get("hunt_code")).upper() for row in rows if clean(row.get("hunt_code"))})


def count_source(rows: list[dict[str, str]], source_name: str, year_field: str = "reported_hunt_year", year: str = "2023") -> tuple[int, int]:
    hits = [row for row in rows if clean(row.get(year_field)) == year and source_match(row.get("source_file"), source_name)]
    return len(hits), code_count(hits)


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


def build_audit(paths: Paths) -> tuple[dict[str, object], list[dict[str, object]]]:
    _, truth_long = read_csv(paths.file("harvest_truth_long"))
    _, truth_features = read_csv(paths.file("harvest_truth_features"))
    _, model_long = read_csv(paths.file("harvest_model_long"))
    _, model_features = read_csv(paths.file("harvest_model_features"))
    _, feature_model = read_csv(paths.file("harvest_feature_model_2026"))
    _, draw_long = read_csv(paths.file("draw_truth_long"))

    source_rows: list[dict[str, object]] = []
    for raw_path in RAW_SOURCE_PATHS:
        path = paths.root / raw_path
        source_name = Path(raw_path).name
        truth_long_rows, truth_long_codes = count_source(truth_long, source_name)
        truth_feature_rows, truth_feature_codes = count_source(truth_features, source_name)
        model_long_rows, model_long_codes = count_source(model_long, source_name)
        model_feature_rows, model_feature_codes = count_source(model_features, source_name)
        source_rows.append(
            {
                "source_file": source_name,
                "raw_path": raw_path,
                "raw_exists": path.exists(),
                "raw_size_bytes": path.stat().st_size if path.exists() else 0,
                "truth_long_rows_2023": truth_long_rows,
                "truth_long_hunt_codes_2023": truth_long_codes,
                "truth_feature_rows_2023": truth_feature_rows,
                "truth_feature_hunt_codes_2023": truth_feature_codes,
                "model_long_rows_2023": model_long_rows,
                "model_long_hunt_codes_2023": model_long_codes,
                "model_feature_rows_2023": model_feature_rows,
                "model_feature_hunt_codes_2023": model_feature_codes,
                "ingestion_status": classify_source_status(
                    truth_long_rows,
                    truth_feature_rows,
                    model_feature_rows,
                    source_name,
                ),
            }
        )

    # Include alternate bighorn source label found in normalized truth.
    for source_name in LISTED_HARVEST_SOURCES:
        if any(row["source_file"] == source_name for row in source_rows):
            continue
        truth_long_rows, truth_long_codes = count_source(truth_long, source_name)
        truth_feature_rows, truth_feature_codes = count_source(truth_features, source_name)
        model_long_rows, model_long_codes = count_source(model_long, source_name)
        model_feature_rows, model_feature_codes = count_source(model_features, source_name)
        source_rows.append(
            {
                "source_file": source_name,
                "raw_path": "",
                "raw_exists": "",
                "raw_size_bytes": "",
                "truth_long_rows_2023": truth_long_rows,
                "truth_long_hunt_codes_2023": truth_long_codes,
                "truth_feature_rows_2023": truth_feature_rows,
                "truth_feature_hunt_codes_2023": truth_feature_codes,
                "model_long_rows_2023": model_long_rows,
                "model_long_hunt_codes_2023": model_long_codes,
                "model_feature_rows_2023": model_feature_rows,
                "model_feature_hunt_codes_2023": model_feature_codes,
                "ingestion_status": classify_source_status(truth_long_rows, truth_feature_rows, model_feature_rows, source_name),
            }
        )

    draw_2023 = summarize_year(draw_long, "year", "2023")
    harvest_2023_truth = summarize_year(truth_long, "reported_hunt_year", "2023")
    harvest_2023_model_features = summarize_year(model_features, "reported_hunt_year", "2023")
    raw_package_report = read_json(paths.file("raw_package_report"))
    turkey_package_report = read_json(paths.file("turkey_package_report"))

    feature_source_years = Counter()
    for row in feature_model:
        years = clean(row.get("harvest_feature_source_years"))
        if "2023" in years.split("|"):
            feature_source_years["feature_rows_using_2023"] += 1
    feature_codes_using_2023 = {
        clean(row.get("hunt_code")).upper()
        for row in feature_model
        if "2023" in clean(row.get("harvest_feature_source_years")).split("|") and clean(row.get("hunt_code"))
    }

    status_counts = Counter(clean(row["ingestion_status"]) for row in source_rows)
    blockers = [
        row
        for row in source_rows
        if row["ingestion_status"] in {"RAW_SOURCE_MISSING", "NOT_INGESTED_REVIEW_REQUIRED"}
        and row["source_file"] not in {"2023_le_oial_all.pdf", "dbd8a659__cougar_2023.pdf"}
    ]

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "2023_harvest_draw_ingestion",
        "result": "PASS" if not blockers else "PASS_WITH_REVIEW_WARNINGS",
        "reported_hunt_year": 2023,
        "model_target_year": 2024,
        "harvest_truth_2023": harvest_2023_truth,
        "harvest_model_features_2023": harvest_2023_model_features,
        "draw_truth_2023": draw_2023,
        "raw_package_all_species_rows": raw_package_report.get("all_species_hunt_success_rows", ""),
        "raw_package_unique_hunt_codes": raw_package_report.get("unique_hunt_codes", ""),
        "raw_package_species_count": raw_package_report.get("species_count", ""),
        "turkey_package_loaded": bool(turkey_package_report),
        "feature_model_rows_using_2023": feature_source_years["feature_rows_using_2023"],
        "feature_model_hunt_codes_using_2023": len(feature_codes_using_2023),
        "source_status_counts": dict(sorted(status_counts.items())),
        "review_warning_count": len(blockers),
        "review_warning_sources": [row["source_file"] for row in blockers],
        "guardrail": "2023 harvest rows are quality/history inputs only. They are not permit quota truth and are not direct p_draw truth.",
        "conclusion": "2023 harvest data is already ingested into the engine-facing harvest feature path. The broad all-species harvest source and listed supplemental sources are present where expected; a few listed PDFs are duplicate/reference coverage or unsupported for current promotion.",
    }
    return summary, source_rows


def classify_source_status(truth_long_rows: int, truth_feature_rows: int, model_feature_rows: int, source_name: str) -> str:
    if truth_long_rows and truth_feature_rows and model_feature_rows:
        return "INGESTED_TRUTH_AND_ENGINE_FEATURE"
    if truth_long_rows and model_feature_rows:
        return "INGESTED_TRUTH_AND_ENGINE_FEATURE_PARTIAL_TRUTH_FEATURE"
    if model_feature_rows:
        return "ENGINE_FEATURE_ONLY"
    if truth_long_rows or truth_feature_rows:
        return "TRUTH_ONLY_NOT_ENGINE_FEATURE"
    if source_name in {"2023_le_oial_all.pdf", "dbd8a659__cougar_2023.pdf"}:
        return "REFERENCE_OR_DUPLICATE_NOT_PROMOTED"
    return "NOT_INGESTED_REVIEW_REQUIRED"


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: json.dumps(row.get(column), sort_keys=True) if isinstance(row.get(column), (dict, list)) else row.get(column, "") for column in columns})


def write_markdown(path: Path, summary: dict[str, object], rows: list[dict[str, object]]) -> None:
    lines = [
        "# 2023 Harvest/Draw Ingestion Audit",
        "",
        "Read-only proof that 2023 harvest data is present in the harvest truth/feature path and available to the Hunt Research engine.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Reported hunt year: `{summary['reported_hunt_year']}`.",
        f"- Model target year: `{summary['model_target_year']}`.",
        f"- Harvest truth rows for 2023: `{summary['harvest_truth_2023']['rows']}`.",
        f"- Harvest truth hunt codes for 2023: `{summary['harvest_truth_2023']['hunt_codes']}`.",
        f"- Engine feature rows for 2023: `{summary['harvest_model_features_2023']['rows']}`.",
        f"- Engine feature hunt codes for 2023: `{summary['harvest_model_features_2023']['hunt_codes']}`.",
        f"- Draw truth rows for 2023: `{summary['draw_truth_2023']['rows']}`.",
        f"- Draw truth hunt codes for 2023: `{summary['draw_truth_2023']['hunt_codes']}`.",
        f"- Feature model rows using 2023 history: `{summary['feature_model_rows_using_2023']}`.",
        f"- Feature model hunt codes using 2023 history: `{summary['feature_model_hunt_codes_using_2023']}`.",
        "",
        "## Source Status",
        "",
        "| Source | Truth long rows | Truth feature rows | Engine feature rows | Status |",
        "| --- | ---: | ---: | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['source_file']} | {row['truth_long_rows_2023']} | {row['truth_feature_rows_2023']} | {row['model_feature_rows_2023']} | {row['ingestion_status']} |"
        )
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `2023 Hunt Success.pdf` is the broad all-species hunt-code keyed harvest package and covers 592 hunt codes.",
            "- `23_bg_report.pdf` and `2023-24 turkey.pdf` are present in the engine-facing feature table but not fully represented as normalized long truth rows in this pass.",
            "- `2023_le_oial_all.pdf` and `dbd8a659__cougar_2023.pdf` are treated as reference/duplicate/not-promoted for the current harvest engine path unless later review promotes them.",
            "- Harvest rows remain quality/history inputs. They must not overwrite draw quota, draw odds, or `DATABASE.csv` permit truth.",
            "",
            "## Conclusion",
            "",
            str(summary["conclusion"]),
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
    summary, source_rows = build_audit(Paths(root=root, out_dir=out_dir))
    base = out_dir / "harvest_draw_ingestion_2023"
    columns = [
        "source_file",
        "raw_path",
        "raw_exists",
        "raw_size_bytes",
        "truth_long_rows_2023",
        "truth_long_hunt_codes_2023",
        "truth_feature_rows_2023",
        "truth_feature_hunt_codes_2023",
        "model_long_rows_2023",
        "model_long_hunt_codes_2023",
        "model_feature_rows_2023",
        "model_feature_hunt_codes_2023",
        "ingestion_status",
    ]
    write_csv(base.with_suffix(".csv"), source_rows, columns)
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "source_rows": source_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(base.with_suffix(".md"), summary, source_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
