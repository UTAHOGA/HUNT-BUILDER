"""Find obvious local/online source gaps for short modeled years.

This is a read-only evidence audit. It does not rewrite normalized draw truth,
harvest truth, DATABASE.csv, runtime feeds, or website outputs.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
HARVEST_BEST = ROOT / "data_truth" / "harvest_results_truth" / "normalized" / "harvest_quality_features_all_years_by_hunt_code.csv"
ALIGNMENT_DETAIL = ROOT / "data_truth" / "comparison_outputs" / "validation" / "harvest_draw_same_year_alignment_2026_code_detail.csv"
VALIDATION_DIR = ROOT / "data_truth" / "comparison_outputs" / "validation"
OUTPUT_CSV = VALIDATION_DIR / "short_modeled_year_source_gap_audit.csv"
SUMMARY_JSON = VALIDATION_DIR / "short_modeled_year_source_gap_audit_summary.json"
REPORT_MD = ROOT / "processed_data" / "short_modeled_year_source_gap_audit.md"

DWR_BIG_GAME_ODDS_URL = "https://wildlife.utah.gov/biggame/odds"
DWR_OTHER_ODDS_URL = "https://wildlife.utah.gov/odds"
DWR_HARVEST_REPORTS_URL = "https://wildlife.utah.gov/biggame/reports"
DWR_ANNUAL_REPORTS_URL = "https://wildlife.utah.gov/hunting/reports"


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: object) -> str:
    return " ".join(str(value or "").strip().split())


def path_list(paths: list[Path]) -> str:
    return "|".join(str(path.relative_to(ROOT)).replace("\\", "/") for path in sorted(paths))


def find_files(patterns: list[str]) -> list[Path]:
    found: list[Path] = []
    for pattern in patterns:
        found.extend(ROOT.glob(pattern))
    unique = {path.resolve(): path for path in found if path.is_file()}
    return list(unique.values())


def source_counts_for_draw_year(year: str) -> Counter[str]:
    counts: Counter[str] = Counter()
    for row in read_rows(DRAW_LONG):
        if norm(row.get("year")) == year:
            counts[norm(row.get("source_file"))] += 1
    return counts


def harvest_numeric_counts(year: str) -> dict[str, int]:
    fields = ["permits", "hunters_afield", "harvest_total", "percent_success", "average_days", "hunter_satisfaction", "average_age"]
    counts = {field: 0 for field in fields}
    rows = [row for row in read_rows(HARVEST_BEST) if norm(row.get("reported_hunt_year")) == year]
    for row in rows:
        for field in fields:
            if norm(row.get(field)):
                counts[field] += 1
    counts["rows"] = len(rows)
    counts["unique_codes"] = len({row.get("hunt_code") for row in rows})
    return counts


def local_csv_numeric_rows(paths: list[Path], fields: list[str]) -> int:
    total = 0
    for path in paths:
        try:
            rows = read_rows(path)
        except UnicodeDecodeError:
            continue
        for row in rows:
            if any(norm(row.get(field)) for field in fields):
                total += 1
    return total


def alignment_counts(year: str) -> dict[str, object]:
    rows = [row for row in read_rows(ALIGNMENT_DETAIL) if norm(row.get("year")) == year]
    status_counts = Counter(norm(row.get("alignment_status")) for row in rows)
    species_by_status = Counter((norm(row.get("alignment_status")), norm(row.get("species"))) for row in rows)
    return {
        "rows": len(rows),
        "status_counts": dict(status_counts),
        "harvest_only_species_top": [
            {"species": species, "count": count}
            for (status, species), count in species_by_status.most_common()
            if status == "HARVEST_ONLY_SAME_YEAR"
        ][:8],
        "draw_only_species_top": [
            {"species": species, "count": count}
            for (status, species), count in species_by_status.most_common()
            if status == "DRAW_ONLY_SAME_YEAR"
        ][:8],
    }


DRAW_SOURCE_FAMILIES = [
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "big_game_limited_entry_oil",
        "patterns": [
            "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Big game limited*",
            "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_bg-odds.pdf",
        ],
        "normalized_markers": ["21_bg-odds.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "general_season_deer_preference",
        "patterns": [
            "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*General-season buck deer*",
            "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_deer_odds.pdf",
        ],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "lifetime_deer_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Lifetime general-season deer*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_lifetime_deer.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "youth_general_deer_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Youth general-season deer*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_youth_deer.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "dedicated_hunter_deer_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Dedicated Hunter deer*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_dh_odds.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "youth_dedicated_hunter_deer_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Youth Dedicated Hunter deer*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_youth_dh_odds.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "antlerless_big_game_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Antlerless big game*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_antlerless_drawing_odds_report.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "youth_antlerless_big_game_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Youth antlerless big game*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_youth_antlerless_drawing_odds_report.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "youth_draw_only_elk_bonus",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Youth draw-only elk*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20_youth_bull_elk.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "sportsman",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*Sportsman*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/20-21_sportsman_odds.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "black_bear",
        "patterns": ["pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/*black_bear_20*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/*black_bear_21*"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "cougar",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*cougar*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/80165f60__cougar_Drawing odds.pdf"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "turkey_bonus",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*turkey_2020_turkey_bonus*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/baa2fb5d__turkey_2021_turkey_bonus_points_draw_results.pdf"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2021",
        "reported_source_year": "2020",
        "source_family": "turkey_youth",
        "patterns": ["pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/*turkey_2020_youth*", "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds/3deb930b__turkey_2021_youth_turkey_draw_results.pdf"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "big_game_limited_entry_oil",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/23_bg-odds.pdf", "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 ELK + OTHER BIG GAME.pdf"],
        "normalized_markers": ["24_bg-draw-results.pdf", "24_le_bull_elk.pdf", "24_le_deer.pdf", "24_OIL_ALL.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "general_season_deer_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 draw results General Season Deer Draw Odds.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "general_deer_youth_lifetime_dedicated_bundle",
        "patterns": [
            "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 Youth general-season deer draw results.pdf",
            "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 Lifetime general-season deer draw results.pdf",
            "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 _Dedicated Hunter deer draw results.pdf",
            "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/23_youth_dh_odds.pdf",
        ],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "antlerless_and_youth_antlerless_preference",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 Antlerless big game draw results.pdf", "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 Youth antlerless big game draw results.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "youth_draw_only_elk_bonus",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 Youth draw-only elk bonus point draw results.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "sportsman",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2022-23 Sportsman draw odds report.pdf"],
        "online_url": DWR_BIG_GAME_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "cougar",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023_cougar_odds_report.pdf"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "turkey_bonus_and_youth",
        "patterns": ["pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 _turkey_2023_turkey_bonus_points_draw_results.pdf", "pipeline/RAW/hunt_unit_database/2024/pdf/draw_odds/2023 turkey_2023_youth_turkey_draw_results.pdf"],
        "online_url": DWR_OTHER_ODDS_URL,
    },
    {
        "modeled_year": "2024",
        "reported_source_year": "2023",
        "source_family": "points_purchase_reference",
        "online_url": DWR_BIG_GAME_ODDS_URL,
        "not_draw_rows": True,
    },
]


def build_draw_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    draw_counts = {year: source_counts_for_draw_year(year) for year in ["2021", "2024"]}
    for source in DRAW_SOURCE_FAMILIES:
        year = source["modeled_year"]
        local_files = find_files(source["patterns"])
        normalized_counts = draw_counts[year]
        markers = source.get("normalized_markers", [])
        marker_hits = {marker: normalized_counts.get(marker, 0) for marker in markers if normalized_counts.get(marker, 0)}
        source_labels = ",".join(f"{label}:{count}" for label, count in sorted(normalized_counts.items()))
        if source.get("not_draw_rows"):
            fill_status = "REFERENCE_ONLY_NOT_DRAW_ROWS"
        elif marker_hits:
            fill_status = "NORMALIZED_PRESENT_WITH_SOURCE_LABEL_REVIEW"
        elif local_files:
            fill_status = "LOCAL_SOURCE_READY_FOR_EXTRACTION"
        else:
            fill_status = "ONLINE_SOURCE_AVAILABLE_DOWNLOAD_NEEDED"
        rows.append(
            {
                "modeled_year": year,
                "domain": "draw",
                "reported_source_year": source["reported_source_year"],
                "source_family": source["source_family"],
                "local_source_count": str(len(local_files)),
                "local_sources": path_list(local_files),
                "normalized_year_source_labels": source_labels,
                "normalized_marker_hits": json.dumps(marker_hits, sort_keys=True),
                "fill_status": fill_status,
                "promotion_allowed_now": "NO",
                "recommended_next_step": "extract_or_reconcile_source_family" if fill_status == "LOCAL_SOURCE_READY_FOR_EXTRACTION" else "lineage_review_or_reference_only",
                "official_online_source": source["online_url"],
                "notes": "Evidence row only; do not promote without extraction/reconciliation.",
            }
        )
    return rows


def build_harvest_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for year, patterns, source_family, notes in [
        (
            "2021",
            ["data_truth/harvest_results_truth/raw_packages/2021_for_2022_harvest_results_2021_for_2022_database/harvest_results_2021_for_2022_all_long.csv"],
            "value_bearing_harvest_metrics",
            "Best-by-code 2021 rows exist but numeric metrics are blank; all_long has value-bearing metrics ready for re-normalization.",
        ),
        (
            "2024",
            ["data_truth/harvest_results_truth/raw_packages/2024_for_2025_harvest_results_2024_for_2025_elk_age_supplement/elk_average_age_limited_entry_units_2015_2024.csv"],
            "elk_average_age_supplement",
            "2024 best harvest has average_age blank; local elk age supplement has 2015-2024 age trend data.",
        ),
        (
            "2024",
            ["data_truth/harvest_results_truth/raw_packages/2024_for_2025_harvest_results_2024_for_2025_black_bear_supplement/black_bear_harvest_objective_2024.csv"],
            "black_bear_harvest_objective_supplement",
            "2024 black bear supplement carries objective/mortality data not fully exposed in best-by-code harvest features.",
        ),
    ]:
        local_files = find_files(patterns)
        numeric_counts = harvest_numeric_counts(year)
        local_numeric = local_csv_numeric_rows(local_files, ["harvest_total", "permits", "hunters_afield", "average_days", "percent_success", "average_age", "harvest_objective"])
        if year == "2021" and numeric_counts["harvest_total"] == 0 and local_numeric:
            fill_status = "LOCAL_VALUE_BEARING_HARVEST_READY_FOR_RENORMALIZATION"
        elif year == "2024" and local_files:
            fill_status = "LOCAL_SUPPLEMENT_READY_FOR_FEATURE_ENRICHMENT"
        else:
            fill_status = "REVIEW_NEEDED"
        rows.append(
            {
                "modeled_year": year,
                "domain": "harvest",
                "reported_source_year": year,
                "source_family": source_family,
                "local_source_count": str(len(local_files)),
                "local_sources": path_list(local_files),
                "normalized_year_source_labels": json.dumps(numeric_counts, sort_keys=True),
                "normalized_marker_hits": "",
                "fill_status": fill_status,
                "promotion_allowed_now": "NO",
                "recommended_next_step": "renormalize_harvest_features_from_local_source",
                "official_online_source": DWR_HARVEST_REPORTS_URL if year == "2024" else DWR_ANNUAL_REPORTS_URL,
                "notes": notes,
            }
        )
    return rows


def build_report(summary: dict[str, object], rows: list[dict[str, str]]) -> str:
    lines = [
        "# Short Modeled Year Source Gap Audit",
        "",
        "Read-only search of local and official DWR source availability for modeled years 2021 and 2024.",
        "",
        "## Result",
        "",
        f"- Source evidence rows: {summary['source_evidence_rows']}",
        f"- Local extraction-ready rows: {summary['local_extraction_ready_rows']}",
        f"- Local harvest re-normalization rows: {summary['local_harvest_renormalization_rows']}",
        f"- Runtime/database changes made: {summary['runtime_database_changes_made']}",
        "",
        "## Modeled Year 2021",
        "",
        "- Draw: normalized truth currently has one source label (`21_bg-odds.pdf`) and bonus-only rows, while local files include general deer, lifetime deer, dedicated hunter, antlerless, youth, sportsman, black bear, cougar, and turkey draw sources.",
        "- Harvest: the value-bearing `harvest_results_2021_for_2022_all_long.csv` exists locally, but the current best-by-code 2021 normalized file has blank numeric metrics.",
        "",
        "## Modeled Year 2024",
        "",
        "- Draw: local 2023-for-2024 PDF/CSV packages include preference/youth/dedicated/turkey/cougar/sportsman families that are not fully represented in normalized 2024 draw truth.",
        "- Harvest: 2024 harvest metrics are mostly populated, but local supplement files can fill richer features such as elk average age and black bear objectives.",
        "",
        "## Official DWR Source Pages",
        "",
        f"- Big game draw odds: {DWR_BIG_GAME_ODDS_URL}",
        f"- Other species draw odds: {DWR_OTHER_ODDS_URL}",
        f"- Harvest and survey reports: {DWR_HARVEST_REPORTS_URL}",
        f"- Annual reports: {DWR_ANNUAL_REPORTS_URL}",
        "",
    ]
    for year in ["2021", "2024"]:
        alignment = summary["alignment"][year]
        lines.extend(
            [
                f"## Same-Year Alignment {year}",
                "",
                f"- Status counts: {alignment['status_counts']}",
                f"- Harvest-only top species: {alignment['harvest_only_species_top']}",
                f"- Draw-only top species: {alignment['draw_only_species_top']}",
                "",
            ]
        )
    return "\n".join(lines)


def main() -> int:
    rows = build_draw_rows() + build_harvest_rows()
    fields = [
        "modeled_year",
        "domain",
        "reported_source_year",
        "source_family",
        "local_source_count",
        "local_sources",
        "normalized_year_source_labels",
        "normalized_marker_hits",
        "fill_status",
        "promotion_allowed_now",
        "recommended_next_step",
        "official_online_source",
        "notes",
    ]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "short_modeled_year_source_gap_audit",
        "modeled_years": ["2021", "2024"],
        "source_evidence_rows": len(rows),
        "local_extraction_ready_rows": sum(1 for row in rows if row["fill_status"] == "LOCAL_SOURCE_READY_FOR_EXTRACTION"),
        "local_harvest_renormalization_rows": sum(1 for row in rows if row["fill_status"].startswith("LOCAL_") and row["domain"] == "harvest"),
        "runtime_database_changes_made": "NO",
        "alignment": {year: alignment_counts(year) for year in ["2021", "2024"]},
        "official_sources": {
            "big_game_draw_odds": DWR_BIG_GAME_ODDS_URL,
            "other_species_draw_odds": DWR_OTHER_ODDS_URL,
            "harvest_reports": DWR_HARVEST_REPORTS_URL,
            "annual_reports": DWR_ANNUAL_REPORTS_URL,
        },
        "status": "PASS",
    }
    write_rows(OUTPUT_CSV, rows, fields)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_report(summary, rows), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
