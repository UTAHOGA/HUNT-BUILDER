#!/usr/bin/env python3
"""Audit harvest-vs-draw year alignment hypotheses.

This read-only tool compares harvest permit counts against draw-result permit
counts under several year alignments:

- same_year: harvest reported_hunt_year == draw year
- prior_draw_year: harvest reported_hunt_year - 1 == draw year
- next_draw_year: harvest reported_hunt_year + 1 == draw year

The purpose is to test whether harvest reports were normalized by actual hunt
season or by publication/report year. It does not edit source or runtime files.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_HARVEST = "data_truth/harvest_results_truth/normalized/harvest_results_all_years_long.csv"
DEFAULT_DRAW = "data_truth/draw_results_truth/normalized/draw_results_long.csv"
DEFAULT_OUT_DIR = "audits/hunt_research_engine"


@dataclass(frozen=True)
class Paths:
    root: Path
    harvest: Path
    draw: Path
    out_dir: Path


def norm(value: object) -> str:
    return "" if value is None else str(value).strip()


def number(value: object) -> float | None:
    text = norm(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "UNLIMITED"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def year_int(value: object) -> int | None:
    num = number(value)
    if num is None:
        return None
    return int(num)


def format_number(value: float | None) -> str:
    if value is None:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.4f}".rstrip("0").rstrip(".")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def aggregate_draw(rows: Iterable[dict[str, str]]) -> dict[tuple[str, int], dict[str, object]]:
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = norm(row.get("hunt_code"))
        year = year_int(row.get("year"))
        if code and year is not None:
            groups[(code, year)].append(row)

    out: dict[tuple[str, int], dict[str, object]] = {}
    for key, group in groups.items():
        by_residency: dict[str, float] = defaultdict(float)
        source_files = set()
        for row in group:
            value = number(row.get("total_drawn"))
            if value is None:
                value = number(row.get("total_permits"))
            if value is None:
                continue
            by_residency[norm(row.get("residency")) or "UNSPECIFIED"] += value
            if norm(row.get("source_file")):
                source_files.add(norm(row.get("source_file")))
        if by_residency:
            residency_keys = {key.lower() for key in by_residency}
            if {"resident", "nonresident"} & residency_keys:
                total = sum(
                    value
                    for residency, value in by_residency.items()
                    if residency.lower() in {"resident", "nonresident"}
                )
            else:
                total = sum(by_residency.values())
        else:
            total = None
        out[key] = {
            "draw_total": total,
            "draw_by_residency": {k: format_number(v) for k, v in sorted(by_residency.items())},
            "draw_row_count": len(group),
            "draw_source_files": sorted(source_files),
        }
    return out


def aggregate_harvest(rows: Iterable[dict[str, str]]) -> dict[tuple[str, int], dict[str, object]]:
    groups: dict[tuple[str, int], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = norm(row.get("hunt_code"))
        year = year_int(row.get("reported_hunt_year"))
        if code and year is not None:
            groups[(code, year)].append(row)

    out: dict[tuple[str, int], dict[str, object]] = {}
    for key, group in groups.items():
        permit_values = [number(row.get("permits")) for row in group]
        permit_values = [value for value in permit_values if value is not None]
        source_files = sorted({norm(row.get("source_file")) for row in group if norm(row.get("source_file"))})
        names = Counter(norm(row.get("hunt_name")) for row in group if norm(row.get("hunt_name")))
        out[key] = {
            "harvest_permits": max(permit_values) if permit_values else None,
            "harvest_permits_unique": sorted({format_number(value) for value in permit_values}, key=lambda item: float(item)),
            "harvest_row_count": len(group),
            "harvest_source_files": source_files,
            "harvest_hunt_name": names.most_common(1)[0][0] if names else "",
        }
    return out


def compare_status(harvest_value: float | None, draw_value: float | None) -> str:
    if harvest_value is None and draw_value is None:
        return "NO_VALUES"
    if harvest_value is None:
        return "HARVEST_BLANK_DRAW_AVAILABLE"
    if draw_value is None:
        return "DRAW_BLANK_HARVEST_AVAILABLE"
    if abs(harvest_value - draw_value) < 0.0001:
        return "PERMIT_MATCH"
    return "PERMIT_CONFLICT"


def build_audit(paths: Paths) -> tuple[dict[str, object], list[dict[str, object]]]:
    harvest_rows = read_csv(paths.harvest)
    draw_rows = read_csv(paths.draw)
    harvest = aggregate_harvest(harvest_rows)
    draw = aggregate_draw(draw_rows)

    alignments = {
        "same_year": 0,
        "prior_draw_year": -1,
        "next_draw_year": 1,
    }
    rows: list[dict[str, object]] = []
    alignment_counts: dict[str, Counter[str]] = {name: Counter() for name in alignments}

    for (code, harvest_year), harvest_item in sorted(harvest.items(), key=lambda item: (item[0][1], item[0][0])):
        result: dict[str, object] = {
            "hunt_code": code,
            "harvest_reported_hunt_year": harvest_year,
            "harvest_permits": format_number(harvest_item["harvest_permits"]),
            "harvest_permits_unique": "|".join(harvest_item["harvest_permits_unique"]),
            "harvest_hunt_name": harvest_item["harvest_hunt_name"],
            "harvest_row_count": harvest_item["harvest_row_count"],
            "harvest_source_files": "|".join(harvest_item["harvest_source_files"][:6]),
        }
        best_alignment = ""
        best_status = ""
        for alignment_name, offset in alignments.items():
            draw_year = harvest_year + offset
            draw_item = draw.get((code, draw_year))
            draw_total = draw_item["draw_total"] if draw_item else None
            status = compare_status(harvest_item["harvest_permits"], draw_total)
            alignment_counts[alignment_name][status] += 1
            result[f"{alignment_name}_draw_year"] = draw_year
            result[f"{alignment_name}_draw_total"] = format_number(draw_total)
            result[f"{alignment_name}_status"] = status
            result[f"{alignment_name}_draw_row_count"] = draw_item["draw_row_count"] if draw_item else 0
            result[f"{alignment_name}_draw_by_residency"] = json.dumps(draw_item["draw_by_residency"], sort_keys=True) if draw_item else "{}"
            if status == "PERMIT_MATCH" and not best_alignment:
                best_alignment = alignment_name
                best_status = status
        if not best_alignment:
            # Prefer the alignment with an available draw value over no-value.
            ranked = sorted(
                alignments,
                key=lambda name: (
                    result[f"{name}_status"] in {"PERMIT_CONFLICT", "PERMIT_MATCH"},
                    result[f"{name}_status"] == "PERMIT_MATCH",
                ),
                reverse=True,
            )
            best_alignment = ranked[0]
            best_status = str(result[f"{best_alignment}_status"])
        result["best_alignment"] = best_alignment
        result["best_alignment_status"] = best_status
        rows.append(result)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "harvest_file": str(paths.harvest),
        "draw_file": str(paths.draw),
        "harvest_input_rows": len(harvest_rows),
        "draw_input_rows": len(draw_rows),
        "harvest_hunt_year_keys": len(harvest),
        "draw_hunt_year_keys": len(draw),
        "alignment_status_counts": {name: dict(sorted(counter.items())) for name, counter in alignment_counts.items()},
        "permit_match_counts": {name: counter.get("PERMIT_MATCH", 0) for name, counter in alignment_counts.items()},
        "best_alignment_counts": dict(sorted(Counter(row["best_alignment"] for row in rows).items())),
        "interpretation": "If prior_draw_year beats same_year, harvest reported_hunt_year is likely acting like publication/report year. If same_year beats prior_draw_year, harvest reported_hunt_year is likely actual hunt season year.",
    }
    same = summary["permit_match_counts"]["same_year"]
    prior = summary["permit_match_counts"]["prior_draw_year"]
    if prior > same:
        summary["recommended_year_contract"] = "USE_PRIOR_DRAW_YEAR_FOR_HARVEST_REPORT_YEAR"
    else:
        summary["recommended_year_contract"] = "USE_SAME_YEAR_REPORTED_HUNT_YEAR_AS_ACTUAL_HUNT_YEAR"
    return summary, rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    fieldnames = [
        "hunt_code",
        "harvest_reported_hunt_year",
        "harvest_permits",
        "harvest_permits_unique",
        "harvest_hunt_name",
        "harvest_row_count",
        "harvest_source_files",
        "same_year_draw_year",
        "same_year_draw_total",
        "same_year_status",
        "same_year_draw_row_count",
        "same_year_draw_by_residency",
        "prior_draw_year_draw_year",
        "prior_draw_year_draw_total",
        "prior_draw_year_status",
        "prior_draw_year_draw_row_count",
        "prior_draw_year_draw_by_residency",
        "next_draw_year_draw_year",
        "next_draw_year_draw_total",
        "next_draw_year_status",
        "next_draw_year_draw_row_count",
        "next_draw_year_draw_by_residency",
        "best_alignment",
        "best_alignment_status",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def write_markdown(path: Path, summary: dict[str, object]) -> None:
    lines = [
        "# Harvest Draw Year Alignment Audit",
        "",
        "This read-only audit tests whether harvest permit rows line up better with same-year draw results or prior-year draw results.",
        "",
        "## Verdict",
        "",
        f"`{summary['recommended_year_contract']}`",
        "",
        "## Permit Match Counts",
        "",
    ]
    for key, value in summary["permit_match_counts"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Alignment Status Counts", ""])
    for alignment, counts in summary["alignment_status_counts"].items():
        lines.append(f"### `{alignment}`")
        for status, count in counts.items():
            lines.append(f"- `{status}`: `{count}`")
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            str(summary["interpretation"]),
            "",
            "This audit only tests year alignment. It does not decide whether Expo, Conservation, CWMU, LOA or Sportsman overlays explain the remaining field-permit gap.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--harvest", default=DEFAULT_HARVEST)
    parser.add_argument("--draw", default=DEFAULT_DRAW)
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    paths = Paths(
        root=root,
        harvest=(root / args.harvest).resolve(),
        draw=(root / args.draw).resolve(),
        out_dir=(root / args.out_dir).resolve(),
    )
    for path in [paths.harvest, paths.draw]:
        if not path.exists():
            raise FileNotFoundError(path)
    summary, rows = build_audit(paths)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(paths.out_dir / "harvest_draw_year_alignment_audit.csv", rows)
    (paths.out_dir / "harvest_draw_year_alignment_audit.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8"
    )
    write_markdown(paths.out_dir / "harvest_draw_year_alignment_audit.md", summary)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
