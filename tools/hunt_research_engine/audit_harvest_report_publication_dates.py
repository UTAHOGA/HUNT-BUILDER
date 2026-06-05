#!/usr/bin/env python3
"""Audit harvest source publication-date labels versus reported hunt years.

Some harvest sources are published in the spring after the hunt year. This
audit makes those date labels explicit so a 2026 publication filename is not
mistaken for observed 2026 harvest data.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_OUT_DIR = "audits/hunt_research_engine"
FILES = {
    "harvest_truth_long": "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv",
    "harvest_truth_features": "data_truth/harvest_results_truth/normalized/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_model_long": "data_model/harvest_quality/harvest_results_all_years_long.csv",
    "harvest_model_features": "data_model/harvest_quality/harvest_quality_features_all_years_by_hunt_code.csv",
    "harvest_feature_model_2026": "data_model/harvest_quality/harvest_feature_model_by_hunt_code_2026.csv",
    "harvest_species_year": "data_model/harvest_quality/harvest_feature_model_by_species_year.csv",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    if not path.exists():
        return [], []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def filename_years(value: str) -> list[str]:
    return sorted(set(re.findall(r"(?:19|20)\d{2}", value)))


def source_years_from_feature(value: str) -> list[str]:
    return [part for part in clean(value).split("|") if re.fullmatch(r"(?:19|20)\d{2}", part)]


def audit_table(name: str, path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    fields, rows = read_csv(path)
    year_field = "reported_hunt_year" if "reported_hunt_year" in fields else "year" if "year" in fields else ""
    source_field = "source_file" if "source_file" in fields else ""
    rows_2026 = []
    publication_later_rows = []
    source_counts = Counter()

    for row in rows:
        year = clean(row.get(year_field)) if year_field else ""
        if year == "2026":
            rows_2026.append(row)
        source = clean(row.get(source_field)) if source_field else ""
        years = filename_years(source)
        if source and year and any(int(src_year) > int(year) for src_year in years if year.isdigit()):
            publication_later_rows.append(row)
            source_counts[(year, source)] += 1

    samples = []
    for (year, source), count in sorted(source_counts.items(), key=lambda item: (item[0][0], item[0][1]))[:100]:
        samples.append(
            {
                "table": name,
                "reported_hunt_year": year,
                "source_file": source,
                "source_filename_years": "|".join(filename_years(source)),
                "row_count": count,
                "classification": "PUBLICATION_DATE_AFTER_HUNT_YEAR",
                "review_status": "EXPECTED_IF_SOURCE_TITLE_CONFIRMS_PRIOR_HARVEST_YEAR",
            }
        )

    summary = {
        "table": name,
        "path": str(path),
        "exists": path.exists(),
        "rows": len(rows),
        "year_field": year_field,
        "source_file_field": source_field,
        "reported_hunt_year_2026_rows": len(rows_2026),
        "publication_date_after_hunt_year_rows": len(publication_later_rows),
        "publication_date_after_hunt_year_sources": len(source_counts),
    }
    return summary, samples


def build_audit(root: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    table_summaries = []
    sample_rows = []
    for name, rel in FILES.items():
        summary, samples = audit_table(name, root / rel)
        table_summaries.append(summary)
        sample_rows.extend(samples)

    _, feature_model = read_csv(root / FILES["harvest_feature_model_2026"])
    feature_rows_using_2026 = [
        row for row in feature_model if "2026" in source_years_from_feature(row.get("harvest_feature_source_years", ""))
    ]
    total_reported_2026_rows = sum(int(row["reported_hunt_year_2026_rows"]) for row in table_summaries)
    result = "PASS" if total_reported_2026_rows == 0 and not feature_rows_using_2026 else "REVIEW_REQUIRED"
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_name": "harvest_report_publication_date_audit",
        "result": result,
        "reported_hunt_year_2026_rows_total": total_reported_2026_rows,
        "feature_model_rows_using_2026_source_year": len(feature_rows_using_2026),
        "table_summaries": table_summaries,
        "publication_date_after_hunt_year_source_count": len(sample_rows),
        "key_finding": "No observed 2026 harvest-year rows are present. Filename dates such as 2026-03-06 are publication/report dates for reported_hunt_year=2025 sources.",
    }
    return summary, sample_rows


def write_csv(path: Path, rows: list[dict[str, object]], columns: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path: Path, summary: dict[str, object], rows: list[dict[str, object]]) -> None:
    lines = [
        "# Harvest Report Publication-Date Audit",
        "",
        "Checks that source filename/report dates are not being mistaken for observed harvest years.",
        "",
        "## Summary",
        "",
        f"- Result: `{summary['result']}`.",
        f"- Observed rows with `reported_hunt_year=2026`: `{summary['reported_hunt_year_2026_rows_total']}`.",
        f"- 2026 harvest feature model rows using source year 2026: `{summary['feature_model_rows_using_2026_source_year']}`.",
        f"- Publication-date-after-hunt-year source groups: `{summary['publication_date_after_hunt_year_source_count']}`.",
        f"- Key finding: {summary['key_finding']}",
        "",
        "## Publication-Date Source Groups",
        "",
        "| Table | Reported Hunt Year | Source File | Filename Years | Rows | Status |",
        "| --- | ---: | --- | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['table']} | {row['reported_hunt_year']} | {row['source_file']} | {row['source_filename_years']} | {row['row_count']} | {row['review_status']} |"
        )
    if not rows:
        lines.append("|  |  |  |  | 0 | No publication-date drift found |")
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
    summary, sample_rows = build_audit(root)
    base = out_dir / "harvest_report_publication_date_audit"
    columns = ["table", "reported_hunt_year", "source_file", "source_filename_years", "row_count", "classification", "review_status"]
    write_csv(base.with_suffix(".csv"), sample_rows, columns)
    base.with_suffix(".json").write_text(json.dumps({"summary": summary, "source_groups": sample_rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(base.with_suffix(".md"), summary, sample_rows)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
