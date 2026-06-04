"""Split 2026 permit recommendations against current DATABASE allotment fields.

This reporting script does not modify DATABASE.csv. It reflects whatever
DATABASE state exists when it is run.
"""

from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
UNRESOLVED = ROOT / "processed_data/audits/unresolved_2026_vs_database_conservation_audit_synthetic_policy_update.csv"

OUT_RECONCILED = ROOT / "processed_data/audits/database_allotment_reconciled_2026.csv"
OUT_RECONCILED_UNRESOLVED = ROOT / "processed_data/audits/database_allotment_reconciled_2026_unresolved_subset.csv"
OUT_DISAGREEMENTS = ROOT / "processed_data/audits/database_allotment_disagreements_2026.csv"
OUT_REVIEW = ROOT / "processed_data/audits/database_allotment_no_recommendation_or_not_compared_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/database_allotment_reconciliation_2026_summary.json"
OUT_DOC = ROOT / "docs/database_allotment_reconciliation_2026.md"
OUT_LOCK_FALLBACK_SUFFIX = "_locked_fallback"

MATCH_STATUSES = {"DATABASE_MATCHES_RECOMMENDED", "DATABASE_TOTAL_MATCHES_RECOMMENDED"}
DISAGREE_STATUSES = {"DATABASE_DIFFERS_FROM_RECOMMENDED", "DATABASE_BLANK_RECOMMENDATION_HAS_VALUE"}
REVIEW_STATUSES = {"DATABASE_HAS_VALUE_NO_RECOMMENDATION", "NOT_COMPARED"}


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        handle = path.open("w", encoding="utf-8", newline="")
    except PermissionError:
        fallback = path.with_name(f"{path.stem}{OUT_LOCK_FALLBACK_SUFFIX}{path.suffix}")
        handle = fallback.open("w", encoding="utf-8", newline="")
        path = fallback
    with handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    return path


def base_row(row: dict[str, str], reconciliation_status: str) -> dict[str, object]:
    return {
        "hunt_code": clean(row.get("hunt_code")),
        "hunt_name": clean(row.get("hunt_name")),
        "species": clean(row.get("species")),
        "sex_type": clean(row.get("sex_type")),
        "weapon": clean(row.get("weapon")),
        "hunt_type": clean(row.get("hunt_type")),
        "season": clean(row.get("season")),
        "database_allotment_2026_res": clean(row.get("database_res_reference")),
        "database_allotment_2026_nr": clean(row.get("database_nr_reference")),
        "database_allotment_2026_total": clean(row.get("database_total_reference")),
        "recommended_res": clean(row.get("recommended_res")),
        "recommended_nr": clean(row.get("recommended_nr")),
        "recommended_total": clean(row.get("recommended_total")),
        "database_alignment": clean(row.get("database_alignment")),
        "reconciliation_status": reconciliation_status,
        "winner_source": clean(row.get("winner_source")),
        "confidence": clean(row.get("confidence")),
        "source_support_count": clean(row.get("source_support_count")),
        "source_presence": clean(row.get("source_presence")),
        "conflicting_sources": clean(row.get("conflicting_sources")),
        "recommended_action": clean(row.get("recommended_action")),
        "decision_reason": clean(row.get("decision_reason")),
        "hanumber_status": clean(row.get("hanumber_status")),
        "hunttable_status": clean(row.get("hunttable_status")),
        "utahdraws_status": clean(row.get("utahdraws_status")),
        "buck_deer_status": clean(row.get("buck_deer_status")),
        "database_status": clean(row.get("database_status")),
    }


def main() -> int:
    rows = read_csv(RECON)
    unresolved = {clean(row.get("hunt_code")): row for row in read_csv(UNRESOLVED)}

    reconciled: list[dict[str, object]] = []
    reconciled_unresolved: list[dict[str, object]] = []
    disagreements: list[dict[str, object]] = []
    review: list[dict[str, object]] = []

    for row in rows:
        alignment = clean(row.get("database_alignment"))
        if alignment in MATCH_STATUSES:
            status = (
                "RECONCILED_DATABASE_ALLOTMENT_EXACT_MATCH"
                if alignment == "DATABASE_MATCHES_RECOMMENDED"
                else "RECONCILED_DATABASE_ALLOTMENT_TOTAL_MATCH"
            )
            out = base_row(row, status)
            reconciled.append(out)
            unresolved_row = unresolved.get(clean(row.get("hunt_code")))
            if unresolved_row:
                reconciled_unresolved.append(
                    {
                        **out,
                        "prior_unresolved_classification": clean(unresolved_row.get("classification")),
                        "prior_unresolved_sources": clean(unresolved_row.get("unresolved_sources")),
                        "remaining_split_bucket": clean(unresolved_row.get("remaining_split_bucket")),
                        "remaining_matching_sources": clean(unresolved_row.get("remaining_matching_sources")),
                    }
                )
        elif alignment in DISAGREE_STATUSES:
            disagreements.append(base_row(row, "DATABASE_RECOMMENDATION_DISAGREEMENT_REVIEW"))
        elif alignment in REVIEW_STATUSES:
            review.append(base_row(row, "NO_RECONCILIATION_REVIEW"))

    fields = [
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "weapon",
        "hunt_type",
        "season",
        "database_allotment_2026_res",
        "database_allotment_2026_nr",
        "database_allotment_2026_total",
        "recommended_res",
        "recommended_nr",
        "recommended_total",
        "database_alignment",
        "reconciliation_status",
        "winner_source",
        "confidence",
        "source_support_count",
        "source_presence",
        "conflicting_sources",
        "recommended_action",
        "decision_reason",
        "hanumber_status",
        "hunttable_status",
        "utahdraws_status",
        "buck_deer_status",
        "database_status",
    ]
    unresolved_fields = fields + [
        "prior_unresolved_classification",
        "prior_unresolved_sources",
        "remaining_split_bucket",
        "remaining_matching_sources",
    ]
    out_reconciled = write_csv(OUT_RECONCILED, sorted(reconciled, key=lambda r: str(r["hunt_code"])), fields)
    out_reconciled_unresolved = write_csv(
        OUT_RECONCILED_UNRESOLVED, sorted(reconciled_unresolved, key=lambda r: str(r["hunt_code"])), unresolved_fields
    )
    out_disagreements = write_csv(OUT_DISAGREEMENTS, sorted(disagreements, key=lambda r: str(r["hunt_code"])), fields)
    out_review = write_csv(OUT_REVIEW, sorted(review, key=lambda r: str(r["hunt_code"])), fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source_reconciliation_csv": RECON.relative_to(ROOT).as_posix(),
        "database_alignment_counts": dict(sorted(Counter(clean(row.get("database_alignment")) for row in rows).items())),
        "reconciled_count": len(reconciled),
        "reconciled_exact_match_count": sum(
            1 for row in reconciled if row["database_alignment"] == "DATABASE_MATCHES_RECOMMENDED"
        ),
        "reconciled_total_match_count": sum(
            1 for row in reconciled if row["database_alignment"] == "DATABASE_TOTAL_MATCHES_RECOMMENDED"
        ),
        "reconciled_unresolved_subset_count": len(reconciled_unresolved),
        "database_disagreement_count": len(disagreements),
        "review_not_reconciled_count": len(review),
        "disagreement_counts": dict(sorted(Counter(row["database_alignment"] for row in disagreements).items())),
        "outputs": {
            "reconciled_csv": out_reconciled.relative_to(ROOT).as_posix(),
            "reconciled_unresolved_subset_csv": out_reconciled_unresolved.relative_to(ROOT).as_posix(),
            "database_disagreements_csv": out_disagreements.relative_to(ROOT).as_posix(),
            "review_csv": out_review.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "This split/reporting script does not modify DATABASE.csv; it reflects current DATABASE state at run time.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# DATABASE Allotment Reconciliation 2026",
        "",
        "## Scope",
        "",
        "This pass closes rows where recommended 2026 permit values already match `DATABASE.csv` `permit_allotment_2026_*` fields and splits out rows where DATABASE disagrees with the recommendation.",
        "",
        "This split/reporting script did not change `DATABASE.csv`; it reflects the current DATABASE state at run time.",
        "",
        "## Key Counts",
        "",
        f"- Reconciled allotment matches: `{len(reconciled)}`",
        f"- Exact resident/nonresident/total matches: `{summary['reconciled_exact_match_count']}`",
        f"- Total-only matches: `{summary['reconciled_total_match_count']}`",
        f"- Reconciled rows that were previously in unresolved subset: `{len(reconciled_unresolved)}`",
        f"- DATABASE disagreement rows: `{len(disagreements)}`",
        f"- Not reconciled / no recommendation / not compared rows: `{len(review)}`",
        "",
        "## Disagreement Counts",
        "",
    ]
    for status, count in summary["disagreement_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Reconciled: `{out_reconciled.relative_to(ROOT).as_posix()}`",
            f"- Reconciled unresolved subset: `{out_reconciled_unresolved.relative_to(ROOT).as_posix()}`",
            f"- DATABASE disagreements: `{out_disagreements.relative_to(ROOT).as_posix()}`",
            f"- Review/not reconciled: `{out_review.relative_to(ROOT).as_posix()}`",
            f"- Summary: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
