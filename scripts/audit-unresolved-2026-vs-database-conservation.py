"""Compare unresolved 2026 hunt codes against DATABASE and conservation table.

Audit-only. Does not modify DATABASE.csv.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
CORE_REVIEW = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation_review.csv"
PERMIT_UNRESOLVED = ROOT / "processed_data/audits/current_2026_hunt_code_permit_unresolved.csv"
REMAINING_3_SOURCE = (
    ROOT / "processed_data/audits/current_2026_permit_unresolved_split/remaining_unresolved_after_3_source_rule.csv"
)
SPECIES_TRUTH = ROOT / "processed_data/audits/permit_2026_species_truth_sources_vs_current_reconciliation.csv"

OUT_CSV = ROOT / "processed_data/audits/unresolved_2026_vs_database_conservation_audit.csv"
OUT_CSV_FALLBACK = ROOT / "processed_data/audits/unresolved_2026_vs_database_conservation_audit_synthetic_policy_update.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/unresolved_2026_vs_database_conservation_audit_summary.json"
OUT_DOC = ROOT / "docs/unresolved_2026_vs_database_conservation_audit.md"
POLICY_CSV = ROOT / "processed_data/audits/conservation_synthetic_display_code_policy.csv"

CURRENT_NUMBERED_SPORTSMAN_CODES = {
    "BI1000",
    "BR1000",
    "DB0007",
    "DS1000",
    "EB1000",
    "GO1000",
    "MB1000",
    "PB1000",
    "RS0001",
    "TK0001",
}
HISTORICAL_SPORTSMAN_CODES = {"CG1000"}
CURRENT_STATEWIDE_UNLIMITED_CODES = {"CG9999"}
SYNTHETIC_CONSERVATION_CODES = {
    "Bison": "CBI1000",
    "Black Bear": "CBB1000",
    "Deer": "CD1000",
    "Desert Bighorn Sheep": "CDS1000",
    "Elk": "CE1000",
    "Mountain Goat": "CMG1000",
    "Moose": "CM1000",
    "Pronghorn": "CP1000",
    "Rocky Mountain Bighorn Sheep": "CRS1000",
    "Turkey": "CTK1000",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def code(value: object) -> str:
    return clean(value).upper()


def numeric_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if not text:
        return ""
    try:
        number = float(text)
    except ValueError:
        return text.lower() if text.lower() == "unlimited" else text
    return str(int(number)) if number.is_integer() else str(number)


def has_value(*values: object) -> bool:
    return any(numeric_text(value) not in {"", "0", "0.0"} for value in values)


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_policy_csv() -> None:
    rows = [
        {
            "synthetic_display_code": display_code,
            "permit_class": "CONSERVATION",
            "species": species,
            "official_hunt_code_status": "BLANK_UNLESS_DWR_ASSIGNS_ONE",
            "hunt_code_authority": "UOGA_SYNTHETIC_DISPLAY_CODE",
            "geometry_rule": "Use only when a conservation permit row needs display/map identity and no official conservation hunt code is available.",
            "truth_guardrail": "Do not treat as an official DWR hunt code and do not overwrite sportsman permit codes.",
        }
        for species, display_code in sorted(SYNTHETIC_CONSERVATION_CODES.items(), key=lambda item: item[1])
    ]
    write_csv(
        POLICY_CSV,
        rows,
        [
            "synthetic_display_code",
            "permit_class",
            "species",
            "official_hunt_code_status",
            "hunt_code_authority",
            "geometry_rule",
            "truth_guardrail",
        ],
    )


def index_by_code(path: Path) -> dict[str, dict[str, str]]:
    return {code(row.get("hunt_code")): row for row in read_csv(path) if code(row.get("hunt_code"))}


def grouped_species_truth() -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in read_csv(SPECIES_TRUTH):
        c = code(row.get("hunt_code"))
        if c:
            grouped[c].append(row)
    return grouped


def summarize_conservation(rows: list[dict[str, str]]) -> dict[str, str]:
    cons = [row for row in rows if row.get("source_family") == "CONSERVATION_PERMITS_DIRECT"]
    totals = sorted({numeric_text(row.get("source_total")) for row in cons if numeric_text(row.get("source_total"))})
    names = sorted({clean(row.get("source_hunt_name")) for row in cons if clean(row.get("source_hunt_name"))})
    statuses = sorted({clean(row.get("comparison_status")) for row in cons if clean(row.get("comparison_status"))})
    return {
        "present": "yes" if cons else "no",
        "total": "|".join(totals),
        "hunt_names": "|".join(names),
        "comparison_statuses": "|".join(statuses),
        "row_count": str(len(cons)),
    }


def source_family_summary(rows: list[dict[str, str]]) -> str:
    return "|".join(sorted({clean(row.get("source_family")) for row in rows if clean(row.get("source_family"))}))


def synthetic_code_for_species(species: str) -> str:
    return SYNTHETIC_CONSERVATION_CODES.get(clean(species), "")


def compare_values(source_total: str, db_allotment_total: str, db_conservation_total: str) -> str:
    if not source_total:
        return "NO_CONSERVATION_SOURCE_VALUE"
    if db_conservation_total and source_total == db_conservation_total:
        return "CONSERVATION_TABLE_MATCHES_DB_CONSERVATION_FIELD"
    if db_allotment_total and source_total == db_allotment_total:
        return "CONSERVATION_TABLE_MATCHES_DB_ALLOTMENT_FIELD_REVIEW"
    if not db_conservation_total and not db_allotment_total:
        return "CONSERVATION_TABLE_HAS_VALUE_DB_BLANK"
    return "CONSERVATION_TABLE_DIFFERS_FROM_DATABASE"


def classify_row(
    c: str,
    db: dict[str, str],
    core: dict[str, str],
    permit: dict[str, str],
    remaining: dict[str, str],
    cons: dict[str, str],
) -> tuple[str, str]:
    db_present = bool(db)
    db_allot_total = numeric_text(db.get("permit_allotment_2026_total"))
    db_cons_total = numeric_text(db.get("conservation_permits_2026_total"))
    rec_total = numeric_text(permit.get("recommended_total"))
    cons_total = cons["total"].split("|")[0] if cons["total"] and "|" not in cons["total"] else cons["total"]

    if c in HISTORICAL_SPORTSMAN_CODES:
        return "CLOSED_HISTORICAL_COUGAR", "CG1000 is historical-ended; current cougar rolls into CG9999."
    if c in CURRENT_STATEWIDE_UNLIMITED_CODES:
        return "CLOSED_CURRENT_STATEWIDE_UNLIMITED", "CG9999 is current statewide/unlimited cougar; no numbered quota expected."
    if not db_present:
        return "DATABASE_MISSING", "Hunt code is unresolved and is not present in DATABASE.csv."
    if cons["present"] == "yes" and c in CURRENT_NUMBERED_SPORTSMAN_CODES:
        return (
            "CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED",
            "Conservation table is using a current sportsman code for map/display identity; assign a synthetic conservation display code and keep sportsman permits separate.",
        )
    if cons["present"] == "yes":
        comparison = compare_values(cons_total, db_allot_total, db_cons_total)
        if comparison == "CONSERVATION_TABLE_MATCHES_DB_CONSERVATION_FIELD":
            return "CONSERVATION_TABLE_DB_MATCH", "Conservation source matches DATABASE conservation field."
        if comparison == "CONSERVATION_TABLE_MATCHES_DB_ALLOTMENT_FIELD_REVIEW":
            return "CONSERVATION_TABLE_MATCHES_ALLOTMENT_REVIEW", "Conservation source matches allotment field; verify field placement."
        if comparison == "CONSERVATION_TABLE_HAS_VALUE_DB_BLANK":
            return "CONSERVATION_TABLE_VALUE_DB_BLANK", "Conservation source has a direct code/value but DATABASE current fields are blank."
        return "CONSERVATION_TABLE_DATABASE_CONFLICT", "Conservation source differs from current DATABASE values."
    if rec_total and db_allot_total and rec_total == db_allot_total:
        return "DATABASE_MATCHES_RECOMMENDED", "Unresolved source recommendation matches DATABASE allotment total."
    if rec_total and not db_allot_total:
        return "SOURCE_HAS_VALUE_DATABASE_BLANK", "Unresolved source has a recommended value but DATABASE allotment total is blank."
    if db_allot_total and not rec_total:
        return "DATABASE_HAS_VALUE_NO_RECOMMENDED_VALUE", "DATABASE has an allotment value but unresolved source winner has no value."
    if core.get("reconciled_bucket") == "DATABASE_REFERENCE_NOT_LIVE_TABLE":
        return "DATABASE_REFERENCE_NOT_LIVE", "DATABASE row is not exposed by the fresh live DWR table."
    if core.get("reconciled_bucket") == "POSSIBLE_DROPPED_OR_NOT_EXPOSED_FROM_2025":
        return "POSSIBLE_DROPPED_DATABASE_PRESENT", "Present in DATABASE and 2025 BIBLE but absent from fresh live table."
    if remaining:
        return "REMAINING_UNRESOLVED_REVIEW", "Still present in remaining-after-3-source unresolved split."
    return "UNRESOLVED_DATABASE_PRESENT_REVIEW", "Present in DATABASE but unresolved status remains."


def main() -> int:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    write_policy_csv()
    database = index_by_code(DATABASE)
    core_review = index_by_code(CORE_REVIEW)
    permit_unresolved = index_by_code(PERMIT_UNRESOLVED)
    remaining_3_source = index_by_code(REMAINING_3_SOURCE)
    species_truth = grouped_species_truth()

    all_codes = sorted(set(core_review) | set(permit_unresolved) | set(remaining_3_source))
    rows: list[dict[str, object]] = []
    for c in all_codes:
        db = database.get(c, {})
        core = core_review.get(c, {})
        permit = permit_unresolved.get(c, {})
        remaining = remaining_3_source.get(c, {})
        truth_rows = species_truth.get(c, [])
        cons = summarize_conservation(truth_rows)
        classification, note = classify_row(c, db, core, permit, remaining, cons)
        synthetic_code = synthetic_code_for_species(db.get("species", ""))
        synthetic_required = classification == "CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED"
        row = {
            "hunt_code": c,
            "unresolved_sources": "|".join(
                source
                for source, present in [
                    ("CORE_REVIEW", bool(core)),
                    ("PERMIT_UNRESOLVED", bool(permit)),
                    ("REMAINING_AFTER_3_SOURCE_RULE", bool(remaining)),
                ]
                if present
            ),
            "classification": classification,
            "notes": note,
            "database_present": "yes" if db else "no",
            "database_hunt_name": db.get("hunt_name", ""),
            "database_species": db.get("species", ""),
            "database_sex_type": db.get("sex_type", ""),
            "database_weapon": db.get("weapon", ""),
            "database_hunt_type": db.get("hunt_type", ""),
            "database_hunt_class": db.get("hunt_class", ""),
            "database_boundary_id": db.get("boundary_id", ""),
            "db_allotment_res": numeric_text(db.get("permit_allotment_2026_res")),
            "db_allotment_nr": numeric_text(db.get("permit_allotment_2026_nr")),
            "db_allotment_total": numeric_text(db.get("permit_allotment_2026_total")),
            "db_allotment_status": db.get("permit_allotment_2026_status", ""),
            "db_allotment_source": db.get("permit_allotment_2026_source", ""),
            "db_conservation_total": numeric_text(db.get("conservation_permits_2026_total")),
            "db_conservation_source": db.get("conservation_permits_2026_source", ""),
            "conservation_synthetic_display_code": synthetic_code if synthetic_required else "",
            "conservation_display_code_status": (
                "UOGA_SYNTHETIC_DISPLAY_CODE_REQUIRED"
                if synthetic_required
                else ("OFFICIAL_OR_REVIEWED_HUNT_CODE_RETAINED" if cons["present"] == "yes" else "")
            ),
            "conservation_official_hunt_code": "" if synthetic_required else (c if cons["present"] == "yes" else ""),
            "conservation_geometry_source_hunt_code": c if synthetic_required else "",
            "conservation_hunt_code_authority": (
                "UOGA_SYNTHETIC_DISPLAY_CODE" if synthetic_required else ("DWR_OR_EXISTING_DATABASE_CODE" if cons["present"] == "yes" else "")
            ),
            "core_reconciled_bucket": core.get("reconciled_bucket", ""),
            "core_resolution_status": core.get("resolution_status", ""),
            "core_likely_cause": core.get("likely_cause", ""),
            "core_live_shape_status": core.get("live_shape_status", ""),
            "permit_confidence": permit.get("confidence", ""),
            "permit_winner_source": permit.get("winner_source", ""),
            "permit_recommended_res": numeric_text(permit.get("recommended_res")),
            "permit_recommended_nr": numeric_text(permit.get("recommended_nr")),
            "permit_recommended_total": numeric_text(permit.get("recommended_total")),
            "permit_conflicting_sources": permit.get("conflicting_sources", ""),
            "permit_database_alignment": permit.get("database_alignment", ""),
            "remaining_split_bucket": remaining.get("remaining_unresolved_bucket") or remaining.get("split_bucket", ""),
            "remaining_matching_sources": remaining.get("matching_non_database_sources", ""),
            "remaining_matching_source_count": remaining.get("matching_source_count", ""),
            "species_truth_families": source_family_summary(truth_rows),
            "conservation_table_present": cons["present"],
            "conservation_table_total": cons["total"],
            "conservation_table_hunt_names": cons["hunt_names"],
            "conservation_table_comparison_statuses": cons["comparison_statuses"],
            "conservation_table_row_count": cons["row_count"],
        }
        rows.append(row)

    fields = [
        "hunt_code",
        "unresolved_sources",
        "classification",
        "notes",
        "database_present",
        "database_hunt_name",
        "database_species",
        "database_sex_type",
        "database_weapon",
        "database_hunt_type",
        "database_hunt_class",
        "database_boundary_id",
        "db_allotment_res",
        "db_allotment_nr",
        "db_allotment_total",
        "db_allotment_status",
        "db_allotment_source",
        "db_conservation_total",
        "db_conservation_source",
        "conservation_synthetic_display_code",
        "conservation_display_code_status",
        "conservation_official_hunt_code",
        "conservation_geometry_source_hunt_code",
        "conservation_hunt_code_authority",
        "core_reconciled_bucket",
        "core_resolution_status",
        "core_likely_cause",
        "core_live_shape_status",
        "permit_confidence",
        "permit_winner_source",
        "permit_recommended_res",
        "permit_recommended_nr",
        "permit_recommended_total",
        "permit_conflicting_sources",
        "permit_database_alignment",
        "remaining_split_bucket",
        "remaining_matching_sources",
        "remaining_matching_source_count",
        "species_truth_families",
        "conservation_table_present",
        "conservation_table_total",
        "conservation_table_hunt_names",
        "conservation_table_comparison_statuses",
        "conservation_table_row_count",
    ]
    detail_csv = OUT_CSV
    try:
        write_csv(detail_csv, rows, fields)
    except PermissionError:
        detail_csv = OUT_CSV_FALLBACK
        write_csv(detail_csv, rows, fields)

    class_counts = Counter(row["classification"] for row in rows)
    source_counts = Counter()
    for row in rows:
        for source in str(row["unresolved_sources"]).split("|"):
            if source:
                source_counts[source] += 1
    conservation_rows = [row for row in rows if row["conservation_table_present"] == "yes"]
    summary = {
        "created_at_utc": timestamp,
        "total_unresolved_unique_codes": len(rows),
        "database_present_count": sum(1 for row in rows if row["database_present"] == "yes"),
        "database_missing_count": sum(1 for row in rows if row["database_present"] == "no"),
        "conservation_table_present_count": len(conservation_rows),
        "classification_counts": dict(sorted(class_counts.items())),
        "unresolved_source_counts": dict(sorted(source_counts.items())),
        "conservation_synthetic_display_code_required_codes": sorted(
            row["hunt_code"] for row in rows if row["classification"] == "CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED"
        ),
        "synthetic_conservation_codes": SYNTHETIC_CONSERVATION_CODES,
        "conservation_table_value_db_blank_codes": sorted(
            row["hunt_code"] for row in rows if row["classification"] == "CONSERVATION_TABLE_VALUE_DB_BLANK"
        ),
        "conservation_table_database_conflict_codes": sorted(
            row["hunt_code"] for row in rows if row["classification"] == "CONSERVATION_TABLE_DATABASE_CONFLICT"
        ),
        "outputs": {
            "csv": detail_csv.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
            "policy_csv": POLICY_CSV.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Audit only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Unresolved 2026 Hunt Codes Vs DATABASE / Conservation Table Audit",
        "",
        "## Scope",
        "",
        "This audit joins the current unresolved 2026 hunt-code lists to `DATABASE.csv` and the normalized 2026 conservation permit table evidence.",
        "",
        "Inputs:",
        f"- `{CORE_REVIEW.relative_to(ROOT).as_posix()}`",
        f"- `{PERMIT_UNRESOLVED.relative_to(ROOT).as_posix()}`",
        f"- `{REMAINING_3_SOURCE.relative_to(ROOT).as_posix()}`",
        f"- `{SPECIES_TRUTH.relative_to(ROOT).as_posix()}`",
        f"- `{DATABASE.relative_to(ROOT).as_posix()}`",
        "",
        "## Key Counts",
        "",
        f"- Unique unresolved codes audited: `{len(rows)}`",
        f"- Present in DATABASE: `{summary['database_present_count']}`",
        f"- Missing from DATABASE: `{summary['database_missing_count']}`",
            f"- Present in conservation table evidence: `{len(conservation_rows)}`",
            f"- Synthetic conservation display-code policy rows: `{len(SYNTHETIC_CONSERVATION_CODES)}`",
        "",
        "## Classification Counts",
        "",
    ]
    for classification, count in sorted(class_counts.items()):
        lines.append(f"- `{classification}`: `{count}`")
    lines.extend(
        [
            "",
            "## Locked Synthetic Conservation Display Codes",
            "",
            "These codes are UOGA synthetic display/map codes only. They are not official DWR hunt codes and must not overwrite sportsman permit codes.",
            "",
        ]
    )
    for species, display_code in sorted(SYNTHETIC_CONSERVATION_CODES.items(), key=lambda item: item[1]):
        lines.append(f"- `{display_code}`: Conservation {species}")
    lines.extend(
        [
            "",
            "## Conservation/Sportsman Finding",
            "",
            "Conservation permit rows are direct conservation-table evidence and are not counted as sportsman support. Any conservation-table row currently using a sportsman hunt code for website/map identity is flagged as `CONSERVATION_SYNTHETIC_DISPLAY_CODE_REQUIRED`, with the sportsman code preserved only as `conservation_geometry_source_hunt_code`.",
            "",
            "## Outputs",
            "",
            f"- Detail CSV: `{detail_csv.relative_to(ROOT).as_posix()}`",
            f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
            f"- Policy CSV: `{POLICY_CSV.relative_to(ROOT).as_posix()}`",
            "",
            "## Guardrail",
            "",
            "`DATABASE.csv` was not modified.",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
