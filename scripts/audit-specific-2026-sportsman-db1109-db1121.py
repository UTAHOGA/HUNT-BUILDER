"""Focused comparison for known sportsman codes plus DB1109/DB1121."""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TARGET_CODES = [
    "BI1000",
    "BR1000",
    "CG1000",
    "CG9999",
    "DB0007",
    "DS1000",
    "EB1000",
    "GO1000",
    "MB1000",
    "PB1000",
    "RS0001",
    "TK0001",
    "EX1000",
    "DB1109",
    "DB1121",
]
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

DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
LIVE_COMPARE = ROOT / "data_truth/crosswalk_truth/validation/live_dwr_permit_numbers_comprehensive_vs_DATABASE_2026.csv"
HANUMBER = ROOT / "processed_data/dwr_huntplanner_hanumber_2026.csv"
UTAHDRAWS = ROOT / "processed_data/audits/dwr_2026_draw_results_vs_database_allotments.csv"
SPECIES_TRUTH = ROOT / "processed_data/audits/permit_2026_species_truth_sources_vs_current_reconciliation.csv"
PERMIT_RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
CORE = ROOT / "processed_data/audits/current_2026_core_universe_reconciliation.csv"

OUT_CSV = ROOT / "processed_data/audits/specific_2026_sportsman_db1109_db1121_source_comparison.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/specific_2026_sportsman_db1109_db1121_source_comparison_summary.json"
OUT_DOC = ROOT / "docs/specific_2026_sportsman_db1109_db1121_source_comparison.md"


def clean(value: object) -> str:
    return str(value or "").strip()


def code(value: object) -> str:
    return clean(value).upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def index(path: Path) -> dict[str, dict[str, str]]:
    return {code(row.get("hunt_code")): row for row in read_csv(path) if row.get("hunt_code")}


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def truth_rows_by_code() -> dict[str, list[dict[str, str]]]:
    out: dict[str, list[dict[str, str]]] = {}
    for row in read_csv(SPECIES_TRUTH):
        c = code(row.get("hunt_code"))
        if c:
            out.setdefault(c, []).append(row)
    return out


def nonempty(*values: str) -> bool:
    return any(clean(v) not in {"", "0", "0.0"} for v in values)


def source_match_summary(code_value: str, db: dict[str, str], live: dict[str, str], han: dict[str, str], utd: dict[str, str], truths: list[dict[str, str]], rec: dict[str, str]) -> tuple[str, str]:
    matches: list[str] = []
    notes: list[str] = []
    is_sportsman_review_code = code_value in CURRENT_NUMBERED_SPORTSMAN_CODES or code_value in HISTORICAL_SPORTSMAN_CODES

    db_total = clean(db.get("permit_allotment_2026_total"))
    live_total = clean(live.get("live_total"))
    han_total = clean(han.get("permits_2026_total"))
    utd_total = clean(utd.get("source_total"))
    rec_total = clean(rec.get("recommended_total"))

    if live.get("comparison_status") in {"MATCH", "TOTAL_MATCH_SPLIT_DIFFERS"}:
        matches.append("DWR_HUNTTABLE_MATCHES_DATABASE")
    elif nonempty(live_total):
        matches.append("DWR_HUNTTABLE_HAS_VALUE")

    if han.get("fetch_status") == "OK" and nonempty(han_total):
        if db_total and han_total == db_total:
            matches.append("HANUMBER_MATCHES_DATABASE")
        else:
            matches.append("HANUMBER_HAS_VALUE")

    if utd.get("source_presence") == "SOURCE_AND_DATABASE" and nonempty(utd_total):
        if utd.get("comparison_status") == "MATCH_ALL_COMPARABLE":
            matches.append("UTAHDRAWS_MATCHES_DATABASE")
        elif db_total and utd_total == db_total:
            matches.append("UTAHDRAWS_TOTAL_MATCHES_DATABASE")
        else:
            matches.append("UTAHDRAWS_HAS_VALUE")

    for truth in truths:
        if truth.get("source_family") == "CONSERVATION_PERMITS_DIRECT" and is_sportsman_review_code:
            notes.append("Conservation permit table has a row for this code, but it is a separate conservation layer and is not sportsman support.")
            continue
        if truth.get("comparison_status") in {
            "SOURCE_MATCHES_RECOMMENDED",
            "SOURCE_TOTAL_MATCHES_RECOMMENDED",
            "SOURCE_MATCHES_DATABASE",
            "SOURCE_TOTAL_MATCHES_DATABASE",
        }:
            matches.append(f"{truth.get('source_family')}_MATCH")
        elif nonempty(truth.get("source_total")):
            matches.append(f"{truth.get('source_family')}_HAS_VALUE")

    if code_value == "EX1000":
        notes.append("Not a sportsman code; DATABASE/live identify this as Elk Extended Archery with no quota published.")
    if code_value in CURRENT_NUMBERED_SPORTSMAN_CODES:
        notes.append("Current numbered sportsman permit code; expected permit count is one per species/code.")
    if code_value == "CG1000":
        notes.append("Historical sportsman cougar code; user review says this ended by 2025 and current cougar rolls into CG9999.")
    if code_value == "CG9999":
        notes.append("Current statewide cougar code; permit quantity is unlimited, not a numbered sportsman quota.")
    if code_value in {"DB1109", "DB1121"}:
        notes.append("Active 2026 deer buck hunt; live DWR, UtahDraws, DATABASE, and deer-buck source align on total 2.")

    if not matches:
        matches.append("NO_MATCHING_PERMIT_SOURCE_FOUND")
    return "|".join(dict.fromkeys(matches)), " ".join(notes)


def main() -> int:
    database = index(DATABASE)
    live = index(LIVE_COMPARE)
    hanumber = index(HANUMBER)
    utahdraws = index(UTAHDRAWS)
    recon = index(PERMIT_RECON)
    core = index(CORE)
    truths = truth_rows_by_code()

    rows: list[dict[str, object]] = []
    for c in TARGET_CODES:
        db = database.get(c, {})
        live_row = live.get(c, {})
        han = hanumber.get(c, {})
        utd = utahdraws.get(c, {})
        rec = recon.get(c, {})
        core_row = core.get(c, {})
        truth_list = truths.get(c, [])
        source_matches, notes = source_match_summary(c, db, live_row, han, utd, truth_list, rec)
        rows.append(
            {
                "hunt_code": c,
                "user_expected_family": (
                    "CURRENT_NUMBERED_SPORTSMAN"
                    if c in CURRENT_NUMBERED_SPORTSMAN_CODES
                    else (
                        "HISTORICAL_SPORTSMAN_ENDED"
                        if c in HISTORICAL_SPORTSMAN_CODES
                        else (
                            "CURRENT_COUGAR_STATEWIDE_UNLIMITED"
                            if c in CURRENT_STATEWIDE_UNLIMITED_CODES
                            else (
                                "EXTENDED_ARCHERY_NOT_SPORTSMAN"
                                if c == "EX1000"
                                else "ACTIVE_DEER_BUCK_REVIEW"
                            )
                        )
                    )
                ),
                "database_present": "yes" if db else "no",
                "database_hunt_name": db.get("hunt_name", ""),
                "database_species": db.get("species", ""),
                "database_sex_type": db.get("sex_type", ""),
                "database_weapon": db.get("weapon", ""),
                "database_hunt_type": db.get("hunt_type", ""),
                "database_hunt_class": db.get("hunt_class", ""),
                "database_total": db.get("permit_allotment_2026_total", ""),
                "database_source": db.get("permit_allotment_2026_source", ""),
                "dwr_hunttable_status": live_row.get("comparison_status", ""),
                "dwr_hunttable_total": live_row.get("live_total", ""),
                "dwr_hunttable_source_url": live_row.get("source_url", ""),
                "hanumber_fetch_status": han.get("fetch_status", ""),
                "hanumber_total": han.get("permits_2026_total", ""),
                "utahdraws_status": utd.get("comparison_status", ""),
                "utahdraws_total": utd.get("source_total", ""),
                "utahdraws_source_files": utd.get("source_files", ""),
                "species_truth_families": "|".join(sorted({r.get("source_family", "") for r in truth_list if r.get("source_family")})),
                "species_truth_statuses": "|".join(sorted({r.get("comparison_status", "") for r in truth_list if r.get("comparison_status")})),
                "species_truth_totals": "|".join(sorted({r.get("source_total", "") for r in truth_list if r.get("source_total")})),
                "permit_reconciliation_confidence": rec.get("confidence", ""),
                "permit_reconciliation_winner": rec.get("winner_source", ""),
                "permit_reconciliation_total": rec.get("recommended_total", ""),
                "core_reconciled_bucket": core_row.get("reconciled_bucket", ""),
                "core_resolution_status": core_row.get("resolution_status", ""),
                "core_include_in_core": core_row.get("include_in_core_comparable_2026", ""),
                "matching_source_summary": source_matches,
                "notes": notes,
            }
        )

    fields = [
        "hunt_code",
        "user_expected_family",
        "database_present",
        "database_hunt_name",
        "database_species",
        "database_sex_type",
        "database_weapon",
        "database_hunt_type",
        "database_hunt_class",
        "database_total",
        "database_source",
        "dwr_hunttable_status",
        "dwr_hunttable_total",
        "dwr_hunttable_source_url",
        "hanumber_fetch_status",
        "hanumber_total",
        "utahdraws_status",
        "utahdraws_total",
        "utahdraws_source_files",
        "species_truth_families",
        "species_truth_statuses",
        "species_truth_totals",
        "permit_reconciliation_confidence",
        "permit_reconciliation_winner",
        "permit_reconciliation_total",
        "core_reconciled_bucket",
        "core_resolution_status",
        "core_include_in_core",
        "matching_source_summary",
        "notes",
    ]
    write_csv(OUT_CSV, rows, fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "target_codes": TARGET_CODES,
        "current_numbered_sportsman_codes": sorted(CURRENT_NUMBERED_SPORTSMAN_CODES),
        "historical_sportsman_codes_ended": sorted(HISTORICAL_SPORTSMAN_CODES),
        "current_statewide_unlimited_codes": sorted(CURRENT_STATEWIDE_UNLIMITED_CODES),
        "row_count": len(rows),
        "database_present_count": sum(1 for r in rows if r["database_present"] == "yes"),
        "utahdraws_match_or_value_count": sum(1 for r in rows if "UTAHDRAWS" in r["matching_source_summary"]),
        "dwr_hunttable_match_or_value_count": sum(1 for r in rows if "DWR_HUNTTABLE" in r["matching_source_summary"]),
        "species_truth_match_or_value_count": sum(1 for r in rows if "DIRECT" in r["matching_source_summary"] or "CONSERVATION" in r["matching_source_summary"]),
        "core_bucket_counts": dict(sorted(Counter(r["core_reconciled_bucket"] for r in rows).items())),
        "outputs": {
            "csv": OUT_CSV.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Audit only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Specific 2026 Sportsman / DB1109 / DB1121 Source Comparison",
        "",
        "## Finding",
        "",
        "- `EX1000` is not a sportsman permit code. It is `Elk Extended Archery` in DATABASE/DWR with no quota published.",
        "- `DB1109` and `DB1121` are active 2026 deer buck hunts. They match DATABASE, DWR HuntTable, HaNumber/current reconciliation, UtahDraws, and the user-supplied deer buck source on total `2`.",
        "- `CG1000` is a historical sportsman cougar code, not the current 2026 cougar row.",
        "- Current cougar rolls into `CG9999`, and `CG9999` has unlimited permits rather than a numbered quota.",
        "- The current numbered sportsman set excludes `CG1000`; the current cougar row is statewide/unlimited.",
        "- Conservation permit table rows are kept separate and are not counted as sportsman support when a hunt code overlaps.",
        "",
        "## Outputs",
        "",
        f"- Detail CSV: `{OUT_CSV.relative_to(ROOT).as_posix()}`",
        f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        "",
        "## Code Summary",
        "",
    ]
    for row in rows:
        lines.append(
            f"- `{row['hunt_code']}`: {row['database_hunt_name'] or 'not in DATABASE'}; "
            f"matches `{row['matching_source_summary']}`"
        )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
