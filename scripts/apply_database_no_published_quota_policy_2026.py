from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CLEANLINESS_AUDIT = ROOT / "processed_data" / "audits" / "database_current_cleanliness_audit_2026.csv"
CLEANLINESS_SUMMARY = ROOT / "processed_data" / "audits" / "database_current_cleanliness_audit_2026_summary.json"
OUT_CSV = ROOT / "processed_data" / "audits" / "database_2026_no_published_quota_policy_confirmation.csv"
OUT_JSON = ROOT / "processed_data" / "audits" / "database_2026_no_published_quota_policy_confirmation_summary.json"
OUT_MD = ROOT / "processed_data" / "audits" / "database_2026_no_published_quota_policy_confirmation.md"

OLD_ISSUE = "KNOWN_NO_PUBLISHED_2026_PERMIT_TOTAL"
NEW_ISSUE = "NO_PUBLISHED_PERMIT_AUTHORITY_EXCLUDED_FROM_PUBLIC_PREDICTION"
POLICY_NOTE = (
    "NO_PUBLISHED_PERMIT_AUTHORITY: DWR/Hunt Planner does not publish 2026 permit numbers for this row; "
    "do not render a total permit number and do not include in public prediction odds."
)


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return reader.fieldnames or [], list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def classify(row: dict[str, str]) -> tuple[str, str]:
    code = clean(row.get("hunt_code")).upper()
    species = clean(row.get("species")).lower()
    if code.startswith("EL") and species == "elk":
        return "PRIVATE_LAND_ELK_NO_PUBLISHED_PERMIT_COUNT", "NO_PUBLIC_DRAW_ODDS_PRIVATE_LAND"
    if code.startswith("LD") and species == "deer":
        return "PRIVATE_LAND_DEER_NO_PUBLISHED_PERMIT_COUNT", "NO_PUBLIC_DRAW_ODDS_PRIVATE_LAND"
    if code.startswith("LO"):
        return "LANDOWNER_PRIVATE_LAND_NO_PUBLISHED_PERMIT_COUNT", "NO_PUBLIC_DRAW_ODDS_LANDOWNER_PRIVATE_LAND"
    return "SOURCE_CONFIRMED_NO_PUBLISHED_PERMIT_COUNT_NON_PRIVATE_OUTLIER", "NO_PUBLIC_DRAW_ODDS_NO_PUBLISHED_PERMIT_DATA"


def append_note(existing: str, note: str) -> str:
    existing = clean(existing)
    if note in existing:
        return existing
    return f"{existing} | {note}" if existing else note


def main() -> int:
    audit_fields, audit_rows = read_csv(CLEANLINESS_AUDIT)
    no_published_codes = {
        clean(row.get("hunt_code")).upper()
        for row in audit_rows
        if clean(row.get("severity")) == "allowed_no_published"
    }
    db_fields, db_rows = read_csv(DATABASE)
    by_code = {clean(row.get("hunt_code")).upper(): row for row in db_rows}
    confirmations: list[dict[str, str]] = []
    class_counts: Counter[str] = Counter()
    route_counts: Counter[str] = Counter()

    for code in sorted(no_published_codes):
        row = by_code.get(code)
        if not row:
            continue
        classification, route = classify(row)
        class_counts[classification] += 1
        route_counts[route] += 1
        existing_source = clean(row.get("permits_2026_source"))
        row["permits_2026_source"] = existing_source or "2026_HUNT_PLANNER_PERMIT_DATA_NOT_PUBLISHED"
        row["permit_allotment_2026_source"] = row["permits_2026_source"]
        row["permit_allotment_2026_source_file"] = clean(row.get("permit_allotment_2026_source_file")) or "Utah DWR Hunt Planner"
        row["permit_allotment_2026_status"] = classification
        row["draw_2026_system_type"] = route
        row["NOTES"] = append_note(clean(row.get("NOTES")), POLICY_NOTE)
        confirmations.append(
            {
                "hunt_code": code,
                "hunt_name": clean(row.get("hunt_name")),
                "species": clean(row.get("species")),
                "sex_type": clean(row.get("sex_type")),
                "weapon": clean(row.get("weapon")),
                "hunt_class": clean(row.get("hunt_class")),
                "hunt_type": clean(row.get("hunt_type")),
                "classification": classification,
                "draw_2026_system_type": route,
                "private_land_confirmed": "yes" if classification != "SOURCE_CONFIRMED_NO_PUBLISHED_PERMIT_COUNT_NON_PRIVATE_OUTLIER" else "no",
                "permits_2026_source": row["permits_2026_source"],
                "permit_allotment_2026_status": row["permit_allotment_2026_status"],
            }
        )

    for audit_row in audit_rows:
        if clean(audit_row.get("severity")) != "allowed_no_published":
            continue
        audit_row["issue"] = NEW_ISSUE
        audit_row["detail"] = append_note(clean(audit_row.get("detail")), POLICY_NOTE)
        code = clean(audit_row.get("hunt_code")).upper()
        db_row = by_code.get(code, {})
        audit_row["permit_allotment_2026_status"] = clean(db_row.get("permit_allotment_2026_status")) or audit_row.get(
            "permit_allotment_2026_status", ""
        )

    summary = json.loads(CLEANLINESS_SUMMARY.read_text(encoding="utf-8"))
    issue_counts = summary.get("issue_counts_by_type", {})
    if OLD_ISSUE in issue_counts:
        issue_counts[NEW_ISSUE] = issue_counts.pop(OLD_ISSUE)
    summary["issue_counts_by_type"] = issue_counts
    summary["allowed_no_published_policy"] = (
        "Expected no-published permit authority: keep 2026 permit count fields blank, do not render a total permit count, "
        "and exclude from public prediction engines. Confirmed private-land/landowner rows use the private-land no-quota route; "
        "non-private outliers remain no-published reference rows."
    )

    write_csv(DATABASE, db_fields, db_rows)
    write_csv(CLEANLINESS_AUDIT, audit_fields, audit_rows)
    CLEANLINESS_SUMMARY.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out_fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_class",
        "hunt_type",
        "classification",
        "draw_2026_system_type",
        "private_land_confirmed",
        "permits_2026_source",
        "permit_allotment_2026_status",
    ]
    write_csv(OUT_CSV, out_fields, confirmations)
    out = {
        "artifact": "database_2026_no_published_quota_policy_confirmation",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(confirmations),
        "classification_counts": dict(class_counts),
        "route_counts": dict(route_counts),
        "private_land_or_landowner_confirmed_count": sum(
            1 for row in confirmations if row["private_land_confirmed"] == "yes"
        ),
        "non_private_no_published_outlier_count": sum(
            1 for row in confirmations if row["private_land_confirmed"] == "no"
        ),
        "policy": {
            "render": "Do not render a 2026 total permit count when DWR/Hunt Planner does not publish permit data.",
            "truth": "Blank 2026 permit fields are intentional for confirmed no-published rows, not missing data.",
            "engine": "Exclude from public prediction engines and skip quota-ratio/max-random/preference quota modeling.",
            "reason_codes": [
                "NO_PUBLISHED_PERMIT_AUTHORITY",
                "NO_QUOTA_PUBLISHED",
                "PUBLIC_DRAW_ODDS_EXCLUDED_NO_QUOTA",
                "NO_PUBLISHED_QUOTA_RATIO_SKIPPED",
            ],
        },
        "confirmation_csv": str(OUT_CSV.relative_to(ROOT)),
    }
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    lines = [
        "# 2026 No-Published Permit Authority Confirmation",
        "",
        f"- Rows audited: `{len(confirmations)}`",
        f"- Private-land / landowner confirmed rows: `{out['private_land_or_landowner_confirmed_count']}`",
        f"- Non-private no-published outliers: `{out['non_private_no_published_outlier_count']}`",
        "",
        "## Classification Counts",
        "",
    ]
    for key, count in class_counts.most_common():
        lines.append(f"- `{key}`: `{count}`")
    lines.extend(
        [
            "",
            "## Policy",
            "",
            "- Keep 2026 resident, nonresident, and total permit columns blank.",
            "- Do not render a total permit count for these rows.",
            "- Do not include these rows in public prediction engines.",
            "- If retained in reference/ladder/audit views, mark them with `NO_PUBLISHED_PERMIT_AUTHORITY`, `NO_QUOTA_PUBLISHED`, and `PUBLIC_DRAW_ODDS_EXCLUDED_NO_QUOTA`.",
        ]
    )
    OUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
