"""Create a conservative 2026 hunt-code universe reconciliation.

This audit separates the comparable BIBLE/draw-results core from broader
current Hunt Planner categories. It does not modify DATABASE.csv.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LIVE_VS_BIBLE = ROOT / "processed_data/audits/current_2026_live_vs_bible_hunt_code_universe.csv"
SPECIES_TRUTH = ROOT / "processed_data/audits/permit_2026_species_truth_sources_vs_current_reconciliation.csv"
PERMIT_RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"

OUT_ALL = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation.csv"
OUT_CLOSED = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation_closed.csv"
OUT_REVIEW = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation_review.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation_summary.json"
OUT_DOC = ROOT / "docs/current_2026_core_universe_reconciliation.md"


DIRECT_SOURCE_FAMILIES = {
    "DEER_BUCK_DB_DIRECT",
    "DEER_DOE_DIRECT",
}
CONSERVATION_SOURCE_FAMILIES = {"CONSERVATION_PERMITS_DIRECT"}
SOURCE_MATCH_STATUSES = {
    "SOURCE_MATCHES_RECOMMENDED",
    "SOURCE_TOTAL_MATCHES_RECOMMENDED",
    "SOURCE_MATCHES_DATABASE",
    "SOURCE_TOTAL_MATCHES_DATABASE",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def code(value: object) -> str:
    return clean(value).upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_species_truth() -> dict[str, dict[str, object]]:
    grouped: dict[str, dict[str, object]] = defaultdict(
        lambda: {
            "source_families": set(),
            "comparison_statuses": set(),
            "direct_source_support": "no",
            "direct_source_match_support": "no",
            "conservation_source_support": "no",
            "conservation_source_match_support": "no",
            "source_permit_total_values": set(),
        }
    )
    for row in read_csv(SPECIES_TRUTH):
        c = code(row.get("hunt_code"))
        if not c:
            continue
        rec = grouped[c]
        family = row.get("source_family", "")
        status = row.get("comparison_status", "")
        rec["source_families"].add(family)
        rec["comparison_statuses"].add(status)
        if family in DIRECT_SOURCE_FAMILIES and row.get("source_total"):
            rec["direct_source_support"] = "yes"
            rec["source_permit_total_values"].add(row.get("source_total", ""))
        if family in DIRECT_SOURCE_FAMILIES and status in SOURCE_MATCH_STATUSES:
            rec["direct_source_match_support"] = "yes"
        if family in CONSERVATION_SOURCE_FAMILIES and row.get("source_total"):
            rec["conservation_source_support"] = "yes"
        if family in CONSERVATION_SOURCE_FAMILIES and status in SOURCE_MATCH_STATUSES:
            rec["conservation_source_match_support"] = "yes"
    return grouped


def build_permit_recon() -> dict[str, dict[str, str]]:
    return {code(row.get("hunt_code")): row for row in read_csv(PERMIT_RECON) if row.get("hunt_code")}


def classify(row: dict[str, str], species: dict[str, object], permit: dict[str, str]) -> tuple[str, str, str, str]:
    hunt_code = code(row.get("hunt_code"))
    status = row.get("universe_status", "")
    cause = row.get("likely_cause", "")
    direct = species.get("direct_source_support") == "yes"
    direct_match = species.get("direct_source_match_support") == "yes"
    conservation_direct = species.get("conservation_source_support") == "yes"
    confidence = permit.get("confidence", "")
    permit_total = clean(permit.get("recommended_total"))

    if status == "LIVE_2026_AND_2025_BIBLE":
        return (
            "CORE_DRAW_RESULTS_CONTINUING",
            "CLOSED_CORE",
            "yes",
            "Present in 2025 BIBLE and fresh 2026 DWR Hunt Planner table.",
        )

    if status == "BIBLE_2025_NOT_IN_LIVE_2026_TABLE":
        if direct_match:
            return (
                "CORE_DIRECT_SOURCE_NOT_IN_LIVE_TABLE_REVIEW",
                "REVIEW",
                "maybe",
                "Missing from live table but has direct 2026 source match; check if current table omitted this family.",
            )
        return (
            "POSSIBLE_DROPPED_OR_NOT_EXPOSED_FROM_2025",
            "REVIEW",
            "maybe",
            "Present in 2025 BIBLE but absent from fresh 2026 DWR table; needs drop/rename/crosswalk review.",
        )

    if status == "DATABASE_NOT_IN_LIVE_TABLE":
        return (
            "DATABASE_REFERENCE_NOT_LIVE_TABLE",
            "REVIEW",
            "no",
            "Database row is not exposed by the fresh DWR live table; do not count as active core without source review.",
        )

    if status == "BIBLE_HISTORICAL_ONLY":
        if hunt_code == "CG1000":
            return (
                "COUGAR_HISTORICAL_SPORTSMAN_ENDED",
                "CLOSED_HISTORICAL",
                "no",
                "Historical sportsman cougar code; user-reviewed 2026 rule is current cougar rolls into statewide CG9999 unlimited.",
            )
        return (
            "HISTORICAL_LIBRARY_ONLY",
            "CLOSED_HISTORICAL",
            "no",
            "Historical BIBLE-library code not part of current 2026 live table.",
        )

    if status == "LIVE_2026_NOT_IN_2025_BIBLE":
        if cause == "PRIVATE_LAND_OR_LANDOWNER_CURRENT_PLANNER":
            return (
                "SEPARATE_PRIVATE_LAND_LANDOWNER_LAYER",
                "CLOSED_SEPARATE_LAYER",
                "no",
                "Current Hunt Planner private-land/landowner family; separate from comparable BIBLE draw-results core.",
            )
        if cause == "CONSERVATION_CURRENT_PLANNER":
            return (
                "SEPARATE_CONSERVATION_LAYER",
                "CLOSED_SEPARATE_LAYER" if conservation_direct else "REVIEW",
                "no",
                "Conservation permit family; use separate conservation layer, not core-count inflation.",
            )
        if cause == "STATEWIDE_OR_UNLIMITED_CURRENT_PLANNER":
            if hunt_code == "CG9999":
                return (
                    "COUGAR_CURRENT_STATEWIDE_UNLIMITED_LAYER",
                    "CLOSED_SEPARATE_LAYER",
                    "no",
                    "Current statewide cougar code; DWR publishes unlimited permits rather than a numbered quota.",
                )
            return (
                "SEPARATE_STATEWIDE_UNLIMITED_LAYER",
                "CLOSED_SEPARATE_LAYER",
                "no",
                "Statewide/unlimited current planner family; not comparable to local draw-results rows.",
            )
        if cause == "TRIBAL_CURRENT_PLANNER":
            return (
                "SEPARATE_TRIBAL_LAYER",
                "CLOSED_SEPARATE_LAYER",
                "no",
                "Tribal current planner family; keep separate from core draw-results universe.",
            )
        if cause == "CWMU_CURRENT_PLANNER":
            return (
                "SEPARATE_CWMU_CURRENT_PLANNER_LAYER",
                "REVIEW",
                "maybe",
                "CWMU current-planner row not in 2025 BIBLE; review whether this is new, renamed, or omitted by source family.",
            )
        if cause == "EXTENDED_ARCHERY_CURRENT_PLANNER":
            return (
                "SEPARATE_EXTENDED_ARCHERY_NO_QUOTA_LAYER",
                "CLOSED_SEPARATE_LAYER",
                "no",
                "Extended-archery current planner row with no quota; not a sportsman code and not part of core draw-results count.",
            )
        if cause == "SPORTSMAN_CURRENT_PLANNER":
            return (
                "SPORTSMAN_CONTINUITY_LAYER_REVIEW",
                "REVIEW",
                "maybe",
                "Sportsman codes are known continuing active permit hunts, but this row was not in 2025 BIBLE extraction.",
            )
        if direct_match and permit_total:
            return (
                "CONFIRMED_2026_NEW_OR_OMITTED_DIRECT_SOURCE",
                "REVIEW",
                "maybe",
                "Not in 2025 BIBLE, but direct 2026 source matches current reconciliation; review as new or BIBLE omission.",
            )
        if confidence in {"HIGH_CONFIRMED_2PLUS", "MEDIUM_TOTAL_CONFIRMED"} and permit_total:
            return (
                "CURRENT_PLANNER_EXTRA_WITH_MULTI_SOURCE_PERMIT_SUPPORT",
                "REVIEW",
                "maybe",
                "Not in 2025 BIBLE, but current permit evidence is multi-source/total-confirmed.",
            )
        return (
            "CURRENT_PLANNER_EXTRA_REVIEW",
            "REVIEW",
            "maybe",
            "Fresh DWR current planner row not in 2025 BIBLE; unresolved source-family status.",
        )

    return ("UNCLASSIFIED_REVIEW", "REVIEW", "maybe", "Fallback review bucket.")


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    species_by_code = build_species_truth()
    permit_by_code = build_permit_recon()
    rows: list[dict[str, object]] = []
    for row in read_csv(LIVE_VS_BIBLE):
        c = code(row.get("hunt_code"))
        species = species_by_code.get(
            c,
            {
                "source_families": set(),
                "comparison_statuses": set(),
                "direct_source_support": "no",
                "direct_source_match_support": "no",
                "conservation_source_support": "no",
                "conservation_source_match_support": "no",
                "source_permit_total_values": set(),
            },
        )
        permit = permit_by_code.get(c, {})
        bucket, resolution, include_core, rationale = classify(row, species, permit)
        out = {
            **row,
            "reconciled_bucket": bucket,
            "resolution_status": resolution,
            "include_in_core_comparable_2026": include_core,
            "resolution_rationale": rationale,
            "species_truth_direct_source_support": species["direct_source_support"],
            "species_truth_direct_source_match_support": species["direct_source_match_support"],
            "species_truth_conservation_source_support": species["conservation_source_support"],
            "species_truth_conservation_source_match_support": species["conservation_source_match_support"],
            "species_truth_source_families": "|".join(sorted(species["source_families"])),
            "species_truth_comparison_statuses": "|".join(sorted(species["comparison_statuses"])),
            "species_truth_total_values": "|".join(sorted(species["source_permit_total_values"])),
            "permit_reconciliation_confidence": permit.get("confidence", ""),
            "permit_reconciliation_winner": permit.get("winner_source", ""),
            "permit_reconciliation_recommended_total": permit.get("recommended_total", ""),
            "permit_reconciliation_action": permit.get("recommended_action", ""),
        }
        rows.append(out)

    fields = [
        "hunt_code",
        "reconciled_bucket",
        "resolution_status",
        "include_in_core_comparable_2026",
        "resolution_rationale",
        "universe_status",
        "likely_cause",
        "prefix",
        "present_in_bible_years",
        "present_in_2025_bible",
        "present_in_2026_bible",
        "present_in_live_2026_hunttable",
        "present_in_database",
        "hanumber_fetch_status",
        "live_presence_status",
        "live_comparison_status",
        "live_shape_status",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "live_res",
        "live_nr",
        "live_total",
        "database_compared_res",
        "database_compared_nr",
        "database_compared_total",
        "species_truth_direct_source_support",
        "species_truth_direct_source_match_support",
        "species_truth_conservation_source_support",
        "species_truth_conservation_source_match_support",
        "species_truth_source_families",
        "species_truth_comparison_statuses",
        "species_truth_total_values",
        "permit_reconciliation_confidence",
        "permit_reconciliation_winner",
        "permit_reconciliation_recommended_total",
        "permit_reconciliation_action",
        "source_url",
    ]
    closed = [r for r in rows if str(r["resolution_status"]).startswith("CLOSED")]
    review = [r for r in rows if r["resolution_status"] == "REVIEW"]
    write_csv(OUT_ALL, rows, fields)
    write_csv(OUT_CLOSED, closed, fields)
    write_csv(OUT_REVIEW, review, fields)

    bucket_counts = Counter(r["reconciled_bucket"] for r in rows)
    resolution_counts = Counter(r["resolution_status"] for r in rows)
    core_counts = Counter(r["include_in_core_comparable_2026"] for r in rows)
    review_bucket_counts = Counter(r["reconciled_bucket"] for r in review)
    summary = {
        "created_at_utc": timestamp,
        "total_rows": len(rows),
        "closed_rows": len(closed),
        "review_rows": len(review),
        "include_in_core_comparable_2026_counts": dict(sorted(core_counts.items())),
        "resolution_status_counts": dict(sorted(resolution_counts.items())),
        "reconciled_bucket_counts": dict(sorted(bucket_counts.items())),
        "review_bucket_counts": dict(sorted(review_bucket_counts.items())),
        "core_comparable_closed_count": sum(1 for r in rows if r["include_in_core_comparable_2026"] == "yes"),
        "maybe_core_review_count": sum(1 for r in rows if r["include_in_core_comparable_2026"] == "maybe"),
        "separate_or_excluded_count": sum(1 for r in rows if r["include_in_core_comparable_2026"] == "no"),
        "outputs": {
            "all_csv": OUT_ALL.relative_to(ROOT).as_posix(),
            "closed_csv": OUT_CLOSED.relative_to(ROOT).as_posix(),
            "review_csv": OUT_REVIEW.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Audit only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# 2026 Core Hunt-Code Universe Reconciliation",
        "",
        "## Purpose",
        "",
        "This pass reconciles what can be safely classified now from the 2025 BIBLE draw-results universe, the fresh 2026 DWR Hunt Planner table, the popup/HaNumber pull, and the user-supplied 2026 species truth permit files.",
        "",
        "It does not treat the raw DWR Hunt Planner table count as the core BIBLE/draw-results universe.",
        "",
        "## Key Counts",
        "",
        f"- Total audit rows: `{len(rows)}`",
        f"- Closed/classified rows: `{len(closed)}`",
        f"- Review rows: `{len(review)}`",
        f"- Closed core comparable 2026 rows: `{summary['core_comparable_closed_count']}`",
        f"- Maybe-core rows requiring review: `{summary['maybe_core_review_count']}`",
        f"- Separate/excluded rows: `{summary['separate_or_excluded_count']}`",
        "",
        "## Bucket Counts",
        "",
    ]
    for bucket, count in sorted(bucket_counts.items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(["", "## Review Bucket Counts", ""])
    for bucket, count in sorted(review_bucket_counts.items()):
        lines.append(f"- `{bucket}`: `{count}`")
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `CORE_DRAW_RESULTS_CONTINUING` is the only closed core count in this pass.",
            "- Private-land/landowner, conservation, statewide/unlimited, tribal, and historical-only rows were separated from the core comparable universe where deterministic.",
            "- Rows marked `REVIEW` are the remaining place to spend human review time: possible drops, new additions, CWMU changes, sportsman continuity extraction gaps, or current-planner extras with source support.",
            "",
            "## Outputs",
            "",
            f"- All rows: `{OUT_ALL.relative_to(ROOT).as_posix()}`",
            f"- Closed rows: `{OUT_CLOSED.relative_to(ROOT).as_posix()}`",
            f"- Review rows: `{OUT_REVIEW.relative_to(ROOT).as_posix()}`",
            f"- Summary: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
