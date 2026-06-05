#!/usr/bin/env python3
"""Compare harvest-result rows to draw-result rows by hunt code and year.

This is a read-only reconciliation. It produces evidence files that identify
where harvest metadata/permit counts align with draw results, where values are
blank and source-fillable, and where conflicts require review. It does not edit
truth sources, draw files, runtime files, or DATABASE.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_HARVEST = "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv"
DEFAULT_DRAW = "data_truth/draw_results_truth/normalized/draw_results_long.csv"
DEFAULT_DATABASE = "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"

METADATA_COLUMNS = ["boundary_id", "hunt_name", "species", "sex_type", "hunt_type", "weapon", "hunt_class"]


@dataclass(frozen=True)
class Paths:
    root: Path
    harvest: Path
    draw: Path
    database: Path
    out_dir: Path


def norm(value: object) -> str:
    return "" if value is None else str(value).strip()


def norm_compare(value: object) -> str:
    text = norm(value).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def number(value: object) -> float | None:
    text = norm(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def most_common_nonblank(values: Iterable[str]) -> str:
    counts = Counter(norm(v) for v in values if norm(v))
    if not counts:
        return ""
    return counts.most_common(1)[0][0]


def sorted_unique(values: Iterable[object]) -> list[str]:
    return sorted({norm(v) for v in values if norm(v)})


def aggregate_draw(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = norm(row.get("hunt_code"))
        year = norm(row.get("year"))
        if code and year:
            groups[(code, year)].append(row)

    out: dict[tuple[str, str], dict[str, object]] = {}
    for key, group in groups.items():
        by_residency: dict[str, float] = defaultdict(float)
        all_values: list[float] = []
        for row in group:
            # In normalized draw results, permit counts are point-row outcomes.
            # Sum drawn/permit values across point rows to recover the
            # hunt-year total; do not take the max as though quota repeated.
            value = number(row.get("total_drawn"))
            if value is None:
                value = number(row.get("total_permits"))
            if value is None:
                continue
            all_values.append(value)
            residency = norm(row.get("residency")) or "UNSPECIFIED"
            by_residency[residency] += value

        residency_totals = dict(by_residency)
        res_keys = {key.lower() for key in residency_totals}
        if {"resident", "nonresident"} & res_keys:
            total = sum(
                value
                for residency, value in residency_totals.items()
                if residency.lower() in {"resident", "nonresident"}
            )
        elif residency_totals:
            total = sum(residency_totals.values())
        else:
            total = None

        out[key] = {
            "row_count": len(group),
            "metadata": {column: most_common_nonblank(row.get(column, "") for row in group) for column in METADATA_COLUMNS},
            "draw_total_permits": total,
            "draw_total_permits_unique": sorted({format_number(v) for v in all_values if v is not None}, key=lambda x: float(x)),
            "draw_permits_by_residency": {k: format_number(v) for k, v in sorted(residency_totals.items())},
            "draw_residencies": sorted_unique(row.get("residency") for row in group),
            "draw_points_count": len({norm(row.get("points")) for row in group if norm(row.get("points"))}),
            "source_files": sorted_unique(row.get("source_file") for row in group),
            "statuses": sorted_unique(row.get("status") for row in group),
        }
    return out


def aggregate_harvest(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, object]]:
    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = norm(row.get("hunt_code"))
        year = norm(row.get("reported_hunt_year"))
        if code and year:
            groups[(code, year)].append(row)

    out: dict[tuple[str, str], dict[str, object]] = {}
    for key, group in groups.items():
        permit_values = [number(row.get("permits")) for row in group]
        permit_values = [value for value in permit_values if value is not None]
        out[key] = {
            "row_count": len(group),
            "metadata": {column: most_common_nonblank(row.get(column, "") for row in group) for column in METADATA_COLUMNS},
            "harvest_permits": max(permit_values) if permit_values else None,
            "harvest_permits_unique": sorted({format_number(v) for v in permit_values}, key=lambda x: float(x)),
            "model_target_years": sorted_unique(row.get("model_target_year") for row in group),
            "source_files": sorted_unique(row.get("source_file") for row in group),
            "source_statuses": sorted_unique(row.get("source_status") for row in group),
            "parse_statuses": sorted_unique(row.get("parse_status") for row in group),
        }
    return out


def metadata_status(harvest_meta: dict[str, str], draw_meta: dict[str, str]) -> tuple[str, list[str], list[str], list[str]]:
    matches: list[str] = []
    fill_candidates: list[str] = []
    conflicts: list[str] = []
    for column in METADATA_COLUMNS:
        h_value = norm(harvest_meta.get(column))
        d_value = norm(draw_meta.get(column))
        if h_value and d_value and norm_compare(h_value) == norm_compare(d_value):
            matches.append(column)
        elif not h_value and d_value:
            fill_candidates.append(column)
        elif h_value and d_value:
            conflicts.append(column)
    if conflicts:
        status = "METADATA_CONFLICT"
    elif fill_candidates:
        status = "METADATA_FILL_CANDIDATE"
    elif matches:
        status = "METADATA_MATCH"
    else:
        status = "NO_METADATA_TO_COMPARE"
    return status, matches, fill_candidates, conflicts


def permit_status(harvest_permits: float | None, draw_permits: float | None) -> str:
    if harvest_permits is None and draw_permits is None:
        return "NO_PERMIT_VALUES"
    if harvest_permits is None and draw_permits is not None:
        return "HARVEST_PERMIT_BLANK_DRAW_AVAILABLE"
    if harvest_permits is not None and draw_permits is None:
        return "DRAW_PERMIT_BLANK_HARVEST_AVAILABLE"
    if abs(float(harvest_permits) - float(draw_permits)) < 0.0001:
        return "PERMIT_MATCH"
    return "PERMIT_CONFLICT_REVIEW"


def build_reconciliation(paths: Paths) -> tuple[dict[str, object], list[dict[str, object]]]:
    _, harvest_rows = read_csv(paths.harvest)
    _, draw_rows = read_csv(paths.draw)
    _, database_rows = read_csv(paths.database)

    draw = aggregate_draw(draw_rows)
    harvest = aggregate_harvest(harvest_rows)
    database_codes = {norm(row.get("hunt_code")) for row in database_rows if norm(row.get("hunt_code"))}

    all_keys = sorted(set(draw) | set(harvest), key=lambda item: (item[1], item[0]))
    rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    permit_counts: Counter[str] = Counter()
    metadata_counts: Counter[str] = Counter()

    for code, year in all_keys:
        draw_item = draw.get((code, year))
        harvest_item = harvest.get((code, year))
        draw_meta = draw_item["metadata"] if draw_item else {}
        harvest_meta = harvest_item["metadata"] if harvest_item else {}
        meta_status, matches, fills, conflicts = metadata_status(harvest_meta, draw_meta)
        h_permits = harvest_item["harvest_permits"] if harvest_item else None
        d_permits = draw_item["draw_total_permits"] if draw_item else None
        p_status = permit_status(h_permits, d_permits)

        if draw_item and harvest_item:
            overall = "MATCHED_HARVEST_AND_DRAW_YEAR"
        elif draw_item:
            overall = "DRAW_ONLY_YEAR"
        else:
            overall = "HARVEST_ONLY_YEAR"

        if p_status == "PERMIT_CONFLICT_REVIEW" or meta_status == "METADATA_CONFLICT":
            reconciliation_action = "REVIEW_CONFLICT_DO_NOT_AUTOFILL"
        elif p_status == "HARVEST_PERMIT_BLANK_DRAW_AVAILABLE" or fills:
            reconciliation_action = "SOURCE_BACKED_FILL_CANDIDATE"
        elif p_status == "PERMIT_MATCH" and meta_status in {"METADATA_MATCH", "METADATA_FILL_CANDIDATE"}:
            reconciliation_action = "RECONCILED"
        else:
            reconciliation_action = "NO_ACTION_OR_SOURCE_NEEDED"

        status_counts[overall] += 1
        permit_counts[p_status] += 1
        metadata_counts[meta_status] += 1

        row = {
            "hunt_code": code,
            "year": year,
            "in_2026_database": str(code in database_codes).upper(),
            "overall_status": overall,
            "reconciliation_action": reconciliation_action,
            "permit_status": p_status,
            "harvest_permits": format_number(h_permits),
            "draw_total_permits_reconciled": format_number(d_permits),
            "harvest_permits_unique": "|".join(harvest_item["harvest_permits_unique"]) if harvest_item else "",
            "draw_total_permits_unique": "|".join(draw_item["draw_total_permits_unique"]) if draw_item else "",
            "draw_permits_by_residency": json.dumps(draw_item["draw_permits_by_residency"], sort_keys=True) if draw_item else "{}",
            "metadata_status": meta_status,
            "metadata_matching_columns": "|".join(matches),
            "metadata_fill_candidate_columns": "|".join(fills),
            "metadata_conflict_columns": "|".join(conflicts),
            "harvest_row_count": harvest_item["row_count"] if harvest_item else 0,
            "draw_row_count": draw_item["row_count"] if draw_item else 0,
            "draw_points_count": draw_item["draw_points_count"] if draw_item else 0,
            "harvest_model_target_years": "|".join(harvest_item["model_target_years"]) if harvest_item else "",
            "harvest_source_files": "|".join(harvest_item["source_files"]) if harvest_item else "",
            "draw_source_files": "|".join(draw_item["source_files"]) if draw_item else "",
            "draw_statuses": "|".join(draw_item["statuses"]) if draw_item else "",
        }
        for column in METADATA_COLUMNS:
            row[f"harvest_{column}"] = norm(harvest_meta.get(column))
            row[f"draw_{column}"] = norm(draw_meta.get(column))
        rows.append(row)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "harvest_file": str(paths.harvest),
        "draw_file": str(paths.draw),
        "database_file": str(paths.database),
        "harvest_input_rows": len(harvest_rows),
        "draw_input_rows": len(draw_rows),
        "database_hunt_codes": len(database_codes),
        "harvest_hunt_year_keys": len(harvest),
        "draw_hunt_year_keys": len(draw),
        "union_hunt_year_keys": len(rows),
        "overall_status_counts": dict(sorted(status_counts.items())),
        "permit_status_counts": dict(sorted(permit_counts.items())),
        "metadata_status_counts": dict(sorted(metadata_counts.items())),
        "source_backed_fill_candidates": sum(1 for row in rows if row["reconciliation_action"] == "SOURCE_BACKED_FILL_CANDIDATE"),
        "conflict_review_rows": sum(1 for row in rows if row["reconciliation_action"] == "REVIEW_CONFLICT_DO_NOT_AUTOFILL"),
        "production_rule": "Harvest permit values are historical harvest context. Draw permit values remain draw truth. This audit identifies reconciliation candidates but does not mutate either source.",
    }
    return summary, rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "hunt_code",
        "year",
        "in_2026_database",
        "overall_status",
        "reconciliation_action",
        "permit_status",
        "harvest_permits",
        "draw_total_permits_reconciled",
        "harvest_permits_unique",
        "draw_total_permits_unique",
        "draw_permits_by_residency",
        "metadata_status",
        "metadata_matching_columns",
        "metadata_fill_candidate_columns",
        "metadata_conflict_columns",
        "harvest_row_count",
        "draw_row_count",
        "draw_points_count",
        "harvest_model_target_years",
        "harvest_source_files",
        "draw_source_files",
        "draw_statuses",
    ]
    for column in METADATA_COLUMNS:
        fieldnames.extend([f"harvest_{column}", f"draw_{column}"])
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_markdown(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# Harvest To Draw Results Reconciliation",
        "",
        "This is a read-only comparison of harvest-result hunt/year rows against draw-result hunt/year rows.",
        "",
        "## Key Rule",
        "",
        "Harvest `permits` are historical harvest-report context. Draw `total_permits` are draw-result context. This report can identify blanks, matches, and conflicts, but it does not overwrite draw truth, harvest truth, `DATABASE.csv`, or runtime files.",
        "",
        "## Counts",
        "",
        f"- Harvest input rows: `{summary['harvest_input_rows']}`",
        f"- Draw input rows: `{summary['draw_input_rows']}`",
        f"- Current DATABASE hunt codes: `{summary['database_hunt_codes']}`",
        f"- Harvest hunt/year keys: `{summary['harvest_hunt_year_keys']}`",
        f"- Draw hunt/year keys: `{summary['draw_hunt_year_keys']}`",
        f"- Union hunt/year keys: `{summary['union_hunt_year_keys']}`",
        "",
        "## Overall Status",
        "",
    ]
    for key, value in summary["overall_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Permit Status", ""])
    for key, value in summary["permit_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Metadata Status", ""])
    for key, value in summary["metadata_status_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(
        [
            "",
            "## Reconciliation Guidance",
            "",
            "- `RECONCILED`: harvest and draw agree at the hunt/year grain.",
            "- `SOURCE_BACKED_FILL_CANDIDATE`: draw metadata or draw permits can explain a harvest blank, but this still needs a controlled repair script before mutation.",
            "- `REVIEW_CONFLICT_DO_NOT_AUTOFILL`: harvest and draw disagree; do not force either side without checking the source PDF/table.",
            "- `DRAW_ONLY_YEAR` and `HARVEST_ONLY_YEAR`: expected in some families due to differing coverage, discontinued hunts, OTC/availability rows, or source package gaps.",
            "",
            f"- Source-backed fill candidates: `{summary['source_backed_fill_candidates']}`",
            f"- Conflict review rows: `{summary['conflict_review_rows']}`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--harvest", default=DEFAULT_HARVEST)
    parser.add_argument("--draw", default=DEFAULT_DRAW)
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--out-dir", default="audits/hunt_research_engine")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paths = Paths(
        root=root,
        harvest=(root / args.harvest).resolve(),
        draw=(root / args.draw).resolve(),
        database=(root / args.database).resolve(),
        out_dir=(root / args.out_dir).resolve(),
    )
    for path in [paths.harvest, paths.draw, paths.database]:
        if not path.exists():
            raise FileNotFoundError(path)
    summary, rows = build_reconciliation(paths)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(paths.out_dir / "harvest_draw_reconciliation.csv", rows)
    (paths.out_dir / "harvest_draw_reconciliation.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown(paths.out_dir / "harvest_draw_reconciliation.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
