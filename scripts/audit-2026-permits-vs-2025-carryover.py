"""Audit whether current 2026 permit fields match same-code 2025 permits.

This is a diagnostic pass only. It does not modify DATABASE.csv.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"
RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"

OUT_AUDIT = ROOT / "processed_data/audits/permit_2026_vs_2025_same_code_carryover_audit.csv"
OUT_REVIEW = ROOT / "processed_data/audits/permit_2026_vs_2025_same_code_carryover_review.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/permit_2026_vs_2025_same_code_carryover_summary.json"
OUT_DOC = ROOT / "docs/permit_2026_vs_2025_same_code_carryover_audit.md"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    try:
        number = float(text)
    except ValueError:
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        if not match:
            return ""
        number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


def triple(row: dict[str, str], res: str, nr: str, total: str) -> tuple[str, str, str]:
    res_text = int_text(row.get(res))
    nr_text = int_text(row.get(nr))
    total_text = int_text(row.get(total))
    if not total_text and (res_text or nr_text):
        total_text = str(int(res_text or 0) + int(nr_text or 0))
    return res_text, nr_text, total_text


def has_value(values: tuple[str, str, str]) -> bool:
    return any(value not in {"", "0"} for value in values)


def compare(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    if not has_value(left) and not has_value(right):
        return "BOTH_BLANK"
    if not has_value(left):
        return "LEFT_BLANK"
    if not has_value(right):
        return "RIGHT_BLANK"
    if left == right:
        return "EXACT_MATCH"
    if left[2] and right[2] and left[2] == right[2]:
        return "TOTAL_MATCH_ONLY"
    return "DIFFERS"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def risk_classification(
    allotment_status: str,
    recommended_status: str,
    source: str,
    winner_source: str,
    confidence: str,
) -> str:
    match_statuses = {"EXACT_MATCH", "TOTAL_MATCH_ONLY"}
    any_match = allotment_status in match_statuses or recommended_status in match_statuses
    if not any_match:
        return "NO_2025_NUMERIC_MATCH"
    source_text = f"{source} {winner_source}".upper()
    if "2026_LIVE_DWR" in source_text or winner_source in {"HANUMBER", "HUNTTABLE", "UTAHDRAWS", "BUCK_DEER"}:
        if "CONFLICT" in confidence.upper():
            return "MATCHES_2025_BUT_CURRENT_SOURCE_CONFLICT_REVIEW"
        return "MATCHES_2025_WITH_CURRENT_SOURCE_SUPPORT"
    return "MATCHES_2025_CARRYOVER_REVIEW"


def main() -> int:
    db_rows = read_csv(DATABASE)
    recon_by_code = {
        clean(row.get("hunt_code")).upper(): row
        for row in read_csv(RECON)
        if clean(row.get("hunt_code"))
    }

    rows: list[dict[str, object]] = []
    review_rows: list[dict[str, object]] = []
    status_counts: Counter[str] = Counter()
    species_review_counts: Counter[str] = Counter()

    for db in db_rows:
        code = clean(db.get("hunt_code")).upper()
        rec_row = recon_by_code.get(code, {})
        p2025 = triple(db, "permits_2025_res", "permits_2025_nr", "permits_2025_total")
        allotment = triple(
            db,
            "permit_allotment_2026_res",
            "permit_allotment_2026_nr",
            "permit_allotment_2026_total",
        )
        recommended = (
            int_text(rec_row.get("recommended_res")),
            int_text(rec_row.get("recommended_nr")),
            int_text(rec_row.get("recommended_total")),
        )
        if not recommended[2] and (recommended[0] or recommended[1]):
            recommended = (recommended[0], recommended[1], str(int(recommended[0] or 0) + int(recommended[1] or 0)))

        allotment_status = compare(allotment, p2025)
        recommended_status = compare(recommended, p2025)
        source = clean(db.get("permit_allotment_2026_source"))
        winner_source = clean(rec_row.get("winner_source")).upper()
        confidence = clean(rec_row.get("confidence"))
        risk = risk_classification(allotment_status, recommended_status, source, winner_source, confidence)
        status_counts[risk] += 1
        if risk != "NO_2025_NUMERIC_MATCH":
            species_review_counts[clean(db.get("species")) or "UNKNOWN"] += 1

        notes: list[str] = []
        if allotment_status in {"EXACT_MATCH", "TOTAL_MATCH_ONLY"}:
            notes.append("DATABASE allotment matches same-code 2025 permits.")
        if recommended_status in {"EXACT_MATCH", "TOTAL_MATCH_ONLY"}:
            notes.append("Recommended value matches same-code 2025 permits.")
        if risk == "MATCHES_2025_WITH_CURRENT_SOURCE_SUPPORT":
            notes.append("Numeric match exists, but current-source lineage also supports the 2026 value.")
        elif risk == "MATCHES_2025_CARRYOVER_REVIEW":
            notes.append("Numeric match exists without clear current-source support; review for possible carryover.")

        out = {
            "hunt_code": code,
            "hunt_name": clean(db.get("hunt_name")),
            "species": clean(db.get("species")),
            "sex_type": clean(db.get("sex_type")),
            "weapon": clean(db.get("weapon")),
            "hunt_type": clean(db.get("hunt_type")),
            "permits_2025_res": p2025[0],
            "permits_2025_nr": p2025[1],
            "permits_2025_total": p2025[2],
            "database_allotment_2026_res": allotment[0],
            "database_allotment_2026_nr": allotment[1],
            "database_allotment_2026_total": allotment[2],
            "recommended_2026_res": recommended[0],
            "recommended_2026_nr": recommended[1],
            "recommended_2026_total": recommended[2],
            "allotment_vs_2025_status": allotment_status,
            "recommended_vs_2025_status": recommended_status,
            "permit_allotment_2026_source": source,
            "permit_allotment_2026_status": clean(db.get("permit_allotment_2026_status")),
            "recommended_winner_source": winner_source,
            "recommended_confidence": confidence,
            "recommended_source_support_count": clean(rec_row.get("source_support_count")),
            "risk_classification": risk,
            "notes": " ".join(notes),
        }
        rows.append(out)
        if risk != "NO_2025_NUMERIC_MATCH":
            review_rows.append(out)

    fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "permits_2025_res",
        "permits_2025_nr",
        "permits_2025_total",
        "database_allotment_2026_res",
        "database_allotment_2026_nr",
        "database_allotment_2026_total",
        "recommended_2026_res",
        "recommended_2026_nr",
        "recommended_2026_total",
        "allotment_vs_2025_status",
        "recommended_vs_2025_status",
        "permit_allotment_2026_source",
        "permit_allotment_2026_status",
        "recommended_winner_source",
        "recommended_confidence",
        "recommended_source_support_count",
        "risk_classification",
        "notes",
    ]
    write_csv(OUT_AUDIT, sorted(rows, key=lambda row: str(row["hunt_code"])), fields)
    write_csv(OUT_REVIEW, sorted(review_rows, key=lambda row: str(row["hunt_code"])), fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "database_path": DATABASE.relative_to(ROOT).as_posix(),
        "reconciliation_path": RECON.relative_to(ROOT).as_posix(),
        "total_database_rows": len(rows),
        "rows_with_any_2025_match": len(review_rows),
        "risk_classification_counts": dict(sorted(status_counts.items())),
        "allotment_vs_2025_counts": dict(sorted(Counter(row["allotment_vs_2025_status"] for row in rows).items())),
        "recommended_vs_2025_counts": dict(sorted(Counter(row["recommended_vs_2025_status"] for row in rows).items())),
        "species_rows_with_any_2025_match": dict(sorted(species_review_counts.items())),
        "outputs": {
            "audit_csv": OUT_AUDIT.relative_to(ROOT).as_posix(),
            "review_csv": OUT_REVIEW.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Diagnostic only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# 2026 Permits vs Same-Code 2025 Carryover Audit",
        "",
        "## Question",
        "",
        "Could the `DATABASE.csv` 2026 allotment fields or the current recommended fields simply match same-code 2025 permit numbers?",
        "",
        "## Short Answer",
        "",
        "Yes, some rows numerically match same-code 2025 permit values. A numeric match alone does not prove carryover, because many rows also have current 2026 source support from HaNumber, HuntTable, UtahDraws, or the repaired Buck Deer current source.",
        "",
        "## Counts",
        "",
        f"- DATABASE rows audited: `{len(rows)}`",
        f"- Rows where allotment or recommendation matched same-code 2025 numbers: `{len(review_rows)}`",
        "",
        "## Risk Classification",
        "",
    ]
    for status, count in summary["risk_classification_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Allotment vs 2025", ""])
    for status, count in summary["allotment_vs_2025_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Recommended vs 2025", ""])
    for status, count in summary["recommended_vs_2025_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Full audit: `{OUT_AUDIT.relative_to(ROOT).as_posix()}`",
            f"- Review subset: `{OUT_REVIEW.relative_to(ROOT).as_posix()}`",
            f"- Summary: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
