"""Same-year harvest-vs-draw hunt-code alignment audit.

This compares native harvest reported years to native draw years. It does not
score old years against the 2026 active database and does not combine features
for prediction yet.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HARVEST_BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "comparison_outputs" / "validation"
SUMMARY_JSON = VALIDATION_DIR / "harvest_draw_same_year_alignment_2026_summary.json"
YEAR_CSV = VALIDATION_DIR / "harvest_draw_same_year_alignment_2026.csv"
DETAIL_CSV = VALIDATION_DIR / "harvest_draw_same_year_alignment_2026_code_detail.csv"
REPORT_MD = ROOT / "processed_data" / "harvest_draw_same_year_alignment_2026.md"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def draw_year(row: dict[str, str]) -> str:
    return norm(
        row.get("actual_draw_year")
        or row.get("year")
        or row.get("draw_year")
        or row.get("reported_hunt_year_inferred")
        or row.get("publish_year")
    )


def pct(numerator: int, denominator: int) -> str:
    if denominator == 0:
        return ""
    return f"{(numerator / denominator * 100):.2f}"


def code_meta(rows: list[dict[str, str]], code: str) -> dict[str, str]:
    for row in rows:
        if norm(row.get("hunt_code")) == code:
            return {
                "species": norm(row.get("species")),
                "hunt_name": norm(row.get("hunt_name")),
                "hunt_type": norm(row.get("hunt_type")),
                "weapon": norm(row.get("weapon")),
                "source_file": norm(row.get("source_file")),
            }
    return {"species": "", "hunt_name": "", "hunt_type": "", "weapon": "", "source_file": ""}


def build_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# Harvest vs Draw Same-Year Alignment 2026",
        "",
        "Read-only native-year comparison of harvest reported years to draw-result years.",
        "",
        "## Rule",
        "",
        "- Compare `2021 harvest` to `2021 draw odds/results`, `2022 harvest` to `2022 draw odds/results`, and so on.",
        "- Do not judge older years against the 2026 active hunt-code universe in this report.",
        "- Keep harvest and draw data in separate lands; this audit is alignment evidence only.",
        "",
        "## Year Summary",
        "",
        "| Year | Harvest native codes | Draw native codes | Same-code overlap | Harvest-only | Draw-only | Harvest matched | Draw matched |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in summary["year_rows"]:
        lines.append(
            "| {year} | {harvest} | {draw} | {overlap} | {harvest_only} | {draw_only} | {harvest_pct}% | {draw_pct}% |".format(
                year=row["year"],
                harvest=row["harvest_native_unique_hunt_codes"],
                draw=row["draw_native_unique_hunt_codes"],
                overlap=row["same_year_overlap_hunt_codes"],
                harvest_only=row["harvest_only_hunt_codes"],
                draw_only=row["draw_only_hunt_codes"],
                harvest_pct=row["harvest_codes_matched_to_draw_pct"],
                draw_pct=row["draw_codes_matched_to_harvest_pct"],
            )
        )
    lines.extend(
        [
            "",
            "## 2021 Baseline",
            "",
            f"- 2021 harvest native unique hunt codes: {summary['baseline_2021']['harvest_native_unique_hunt_codes']}",
            f"- 2021 draw native unique hunt codes: {summary['baseline_2021']['draw_native_unique_hunt_codes']}",
            f"- 2021 same-code overlap: {summary['baseline_2021']['same_year_overlap_hunt_codes']}",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    harvest_rows = read_rows(HARVEST_BEST)
    draw_rows = read_rows(DRAW_LONG)

    harvest_by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    draw_by_year: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in harvest_rows:
        year = norm(row.get("reported_hunt_year"))
        if year:
            harvest_by_year[year].append(row)
    for row in draw_rows:
        year = draw_year(row)
        if year:
            draw_by_year[year].append(row)

    years = sorted(set(harvest_by_year) | set(draw_by_year))
    year_rows: list[dict[str, str]] = []
    detail_rows: list[dict[str, str]] = []
    for year in years:
        h_rows = harvest_by_year.get(year, [])
        d_rows = draw_by_year.get(year, [])
        h_codes = {norm(row.get("hunt_code")) for row in h_rows if norm(row.get("hunt_code"))}
        d_codes = {norm(row.get("hunt_code")) for row in d_rows if norm(row.get("hunt_code"))}
        overlap = h_codes & d_codes
        h_only = h_codes - d_codes
        d_only = d_codes - h_codes
        h_species = Counter(norm(row.get("species")) for row in h_rows)
        d_residency = Counter(norm(row.get("residency")) for row in d_rows)

        year_rows.append(
            {
                "year": year,
                "harvest_rows": str(len(h_rows)),
                "draw_rows": str(len(d_rows)),
                "harvest_native_unique_hunt_codes": str(len(h_codes)),
                "draw_native_unique_hunt_codes": str(len(d_codes)),
                "same_year_overlap_hunt_codes": str(len(overlap)),
                "harvest_only_hunt_codes": str(len(h_only)),
                "draw_only_hunt_codes": str(len(d_only)),
                "harvest_codes_matched_to_draw_pct": pct(len(overlap), len(h_codes)),
                "draw_codes_matched_to_harvest_pct": pct(len(overlap), len(d_codes)),
                "harvest_species_counts": "|".join(f"{key}:{h_species[key]}" for key in sorted(h_species) if key),
                "draw_residency_counts": "|".join(f"{key}:{d_residency[key]}" for key in sorted(d_residency) if key),
                "comparison_use": "SAME_YEAR_NATIVE_ALIGNMENT_NOT_2026_COMPLETENESS",
            }
        )

        for code in sorted(h_only):
            meta = code_meta(h_rows, code)
            detail_rows.append(
                {
                    "year": year,
                    "hunt_code": code,
                    "alignment_status": "HARVEST_ONLY_SAME_YEAR",
                    **meta,
                }
            )
        for code in sorted(d_only):
            meta = code_meta(d_rows, code)
            detail_rows.append(
                {
                    "year": year,
                    "hunt_code": code,
                    "alignment_status": "DRAW_ONLY_SAME_YEAR",
                    **meta,
                }
            )

    baseline_2021 = next((row for row in year_rows if row["year"] == "2021"), {})
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "same_year_harvest_draw_native_alignment",
        "harvest_best_path": str(HARVEST_BEST.relative_to(ROOT)),
        "draw_long_path": str(DRAW_LONG.relative_to(ROOT)),
        "years": years,
        "baseline_2021": baseline_2021,
        "year_rows": year_rows,
        "detail_rows": len(detail_rows),
        "blocker_count": 0,
        "guardrails": [
            "Same-year comparison only: 2021 harvest to 2021 draw odds/results, etc.",
            "No historical year is judged against the 2026 active hunt-code universe in this report.",
            "Harvest and draw data remain separate source domains until a later feature-combine step.",
        ],
        "outputs": {
            "year_summary_csv": str(YEAR_CSV.relative_to(ROOT)),
            "code_detail_csv": str(DETAIL_CSV.relative_to(ROOT)),
            "summary_json": str(SUMMARY_JSON.relative_to(ROOT)),
            "summary_md": str(REPORT_MD.relative_to(ROOT)),
        },
    }

    write_rows(YEAR_CSV, year_rows, list(year_rows[0].keys()) if year_rows else [])
    write_rows(
        DETAIL_CSV,
        detail_rows,
        ["year", "hunt_code", "alignment_status", "species", "hunt_name", "hunt_type", "weapon", "source_file"],
    )
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "Same-year harvest/draw alignment complete: "
        f"2021 harvest {baseline_2021.get('harvest_native_unique_hunt_codes')} codes vs "
        f"2021 draw {baseline_2021.get('draw_native_unique_hunt_codes')} codes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
