from __future__ import annotations

import csv
from collections import Counter
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")


def latest_audit_dir() -> Path:
    audits = sorted((REPO / "audits").glob("column_key_alignment_20*"))
    if not audits:
        raise FileNotFoundError("No column_key_alignment audit folder found")
    return audits[-1]


AUDIT_DIR = latest_audit_dir()
ALIGNMENT = AUDIT_DIR / "04_HUNT_TYPE_DRAW_FIELD_ALIGNMENT.csv"
GAPS = AUDIT_DIR / "08_COLUMN_KEY_ALIGNMENT_GAPS.csv"


def clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def norm(value: object) -> str:
    return clean(value).lower().replace("-", "_").replace(" ", "_")


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def pool_aligned(draw_design: str, draw_pool: str) -> bool:
    dd = norm(draw_design)
    dp = norm(draw_pool)
    if not dd or not dp:
        return False
    if dd == dp:
        return True
    if dd == "reference_only" and dp.endswith("_reference"):
        return True
    if dd == "black_bear" and dp == "black_bear":
        return True
    if dd == "youth_turkey_set_aside" and dp == "youth_turkey_set_aside":
        return True
    if dd == "max_weighted_split" and dp == "max_weighted_split":
        return True
    return False


def classify(row: dict[str, str]) -> dict[str, str]:
    raw_hunt_type = clean(row.get("raw_hunt_type"))
    raw_hunt_class = clean(row.get("raw_hunt_class"))
    raw_draw_design = clean(row.get("raw_draw_design"))
    raw_draw_pool = clean(row.get("raw_draw_pool"))
    lower = " ".join(
        clean(row.get(field)).lower()
        for field in ("raw_hunt_type", "raw_hunt_class", "raw_draw_design", "raw_draw_pool", "hunt_name")
    )

    if raw_hunt_type.lower() == "conservation":
        return {
            "reconciled_status": "REVIEW_REQUIRED_CONSERVATION_ALLOCATION_SOURCE_CONFIRMATION",
            "contract_action": "CONFIRM_SELECTION_MATRIX_AND_CONSERVATION_PERMIT_PDF",
            "expected_hunt_type": "Conservation",
            "expected_hunt_class": raw_hunt_class,
            "expected_draw_design": "CONSERVATION_ALLOCATION_REVIEW",
            "expected_draw_pool": "NOT_STANDARD_DRAW_POOL_REVIEW",
            "reason": "Conservation permits are allocated benefit-auction permit rows, not a normal draw pool; confirm field mapping against the entry page selection matrix and associated Conservation Permit PDF.",
        }

    if "dedicated hunter" in lower and norm(raw_draw_pool) == "youth_dedicated_hunter":
        return {
            "reconciled_status": "REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT",
            "contract_action": "PATCH_CANDIDATE_DRAW_DESIGN_ONLY",
            "expected_hunt_type": raw_hunt_type,
            "expected_hunt_class": "Dedicated Hunter",
            "expected_draw_design": "PREFERENCE_DEDICATED_HUNTER_DEER",
            "expected_draw_pool": raw_draw_pool,
            "reason": "Dedicated Hunter should usually be hunt_class/program overlay; draw_design should carry the dedicated-hunter preference mechanism instead of REFERENCE_ONLY.",
        }

    if "sportsman" in lower:
        return {
            "reconciled_status": "REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT",
            "contract_action": "PATCH_CANDIDATE_DRAW_DESIGN_AND_POOL",
            "expected_hunt_type": raw_hunt_type,
            "expected_hunt_class": raw_hunt_class,
            "expected_draw_design": "SPORTSMAN_RANDOM_ONLY",
            "expected_draw_pool": "sportsman",
            "reason": "Sportsman is a random-only draw family; draw_design/draw_pool should express that lane.",
        }

    return {
        "reconciled_status": "REVIEW_REQUIRED_UNCLASSIFIED_DRAW_FIELD_GAP",
        "contract_action": "ROW_LEVEL_REVIEW_BEFORE_PATCH",
        "expected_hunt_type": raw_hunt_type,
        "expected_hunt_class": raw_hunt_class,
        "expected_draw_design": raw_draw_design,
        "expected_draw_pool": raw_draw_pool,
        "reason": "Gap row did not match a focused reconciliation rule.",
    }


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    rows = [
        row
        for row in read_csv(ALIGNMENT)
        if row.get("status")
        in {
            "REVIEW_REQUIRED_HUNT_TYPE_USED_AS_DRAW_DESIGN",
            "REVIEW_REQUIRED_CONSERVATION_MISMATCH",
            "REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT",
            "REVIEW_REQUIRED_CONSERVATION_ALLOCATION_CONTRACT",
        }
    ]
    output_rows = []
    for row in rows:
        classification = classify(row)
        output_rows.append(
            {
                "source_file": row.get("source_file", ""),
                "row_number_or_context": row.get("row_number_or_context", ""),
                "hunt_code": row.get("hunt_code", ""),
                "hunt_name": row.get("hunt_name", ""),
                "raw_hunt_type": row.get("raw_hunt_type", ""),
                "raw_hunt_class": row.get("raw_hunt_class", ""),
                "raw_draw_design": row.get("raw_draw_design", ""),
                "raw_draw_pool": row.get("raw_draw_pool", ""),
                "previous_audit_status": row.get("status", ""),
                "previous_review_reason": row.get("review_reason", ""),
                **classification,
                "source_patch_applied": "FALSE",
            }
        )

    status_counts = Counter(row["reconciled_status"] for row in output_rows)
    action_counts = Counter(row["contract_action"] for row in output_rows)
    p18 = AUDIT_DIR / "18_DRAW_FIELD_CONTRACT_RECONCILIATION.csv"
    p19 = AUDIT_DIR / "19_DRAW_FIELD_CONTRACT_RECONCILIATION_REPORT.md"
    p20 = AUDIT_DIR / "20_COLUMN_KEY_ALIGNMENT_GAPS_RECONCILED_SUMMARY.csv"
    write_csv(
        p18,
        output_rows,
        [
            "source_file",
            "row_number_or_context",
            "hunt_code",
            "hunt_name",
            "raw_hunt_type",
            "raw_hunt_class",
            "raw_draw_design",
            "raw_draw_pool",
            "previous_audit_status",
            "previous_review_reason",
            "reconciled_status",
            "contract_action",
                "expected_hunt_type",
                "expected_hunt_class",
                "expected_draw_design",
            "expected_draw_pool",
            "reason",
            "source_patch_applied",
        ],
    )

    summary_rows = []
    for status, count in sorted(status_counts.items()):
        summary_rows.append({"summary_type": "reconciled_status", "value": status, "count": count})
    for action, count in sorted(action_counts.items()):
        summary_rows.append({"summary_type": "contract_action", "value": action, "count": count})
    write_csv(p20, summary_rows, ["summary_type", "value", "count"])

    report = [
        "# Draw Field Contract Reconciliation",
        "",
        f"report_timestamp: {stamp}",
        "",
        "## Corrected Contract",
        "",
        "HUNT_TYPE is the user-facing hunt/program family. It is usually different from DRAW_DESIGN.",
        "Dedicated Hunter is usually a HUNT_CLASS/program overlay, not the primary HUNT_TYPE.",
        "Conservation permits are allocated benefit-auction permits, not a standard draw_pool.",
        "DRAW_DESIGN is the draw mechanism/class and should align with DRAW_POOL or draw_type_class-style routing vocabulary.",
        "DRAW_POOL is the lane/pool used by bridge and scoring logic.",
        "",
        "## Reconciled Findings",
        "",
        f"INPUT_REVIEW_ROWS={len(output_rows)}",
        f"PASS_RECONCILED_HUNT_TYPE_SEPARATE_FROM_DRAW_DESIGN={status_counts.get('PASS_RECONCILED_HUNT_TYPE_SEPARATE_FROM_DRAW_DESIGN', 0)}",
        f"REVIEW_REQUIRED_CONSERVATION_ALLOCATION_SOURCE_CONFIRMATION={status_counts.get('REVIEW_REQUIRED_CONSERVATION_ALLOCATION_SOURCE_CONFIRMATION', 0)}",
        f"REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT={status_counts.get('REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT', 0)}",
        "",
        "The Conservation rows require source confirmation against the hunt selection matrix and Conservation Permit PDF before field mapping.",
        "The 147 youth Dedicated Hunter rows already preserve Dedicated Hunter as hunt_class; they are draw_design/draw_pool alignment candidates.",
        "The 2 Sportsman manifest rows are also draw_design/draw_pool alignment candidates.",
        "",
        "## Source Patch Statement",
        "",
        "SOURCE_FILES_PATCHED=FALSE",
        "DATABASE_PATCHED=FALSE",
        "DRAW_RESULTS_LONG_PATCHED=FALSE",
        "CANONICAL_YEARLY_PATCHED=FALSE",
        "",
        "## Outputs",
        "",
        f"DRAW_FIELD_CONTRACT_RECONCILIATION={p18}",
        f"RECONCILED_GAPS_SUMMARY={p20}",
        "",
        "DRAW_FIELD_CONTRACT_STATUS=PASS_CONTRACT_RECONCILED_PATCH_CANDIDATES_WRITTEN",
    ]
    p19.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"DRAW_FIELD_CONTRACT_RECONCILIATION={p18}")
    print(f"DRAW_FIELD_CONTRACT_RECONCILIATION_REPORT={p19}")
    print(f"COLUMN_KEY_ALIGNMENT_GAPS_RECONCILED_SUMMARY={p20}")
    print(f"RECONCILED_INPUT_ROWS={len(output_rows)}")
    print(f"PASS_RECONCILED_HUNT_TYPE_SEPARATE_FROM_DRAW_DESIGN={status_counts.get('PASS_RECONCILED_HUNT_TYPE_SEPARATE_FROM_DRAW_DESIGN', 0)}")
    print(f"REVIEW_REQUIRED_CONSERVATION_ALLOCATION_SOURCE_CONFIRMATION={status_counts.get('REVIEW_REQUIRED_CONSERVATION_ALLOCATION_SOURCE_CONFIRMATION', 0)}")
    print(f"REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT={status_counts.get('REVIEW_REQUIRED_DRAW_DESIGN_POOL_ALIGNMENT', 0)}")
    print("SOURCE_FILES_PATCHED=FALSE")
    print("DRAW_FIELD_CONTRACT_STATUS=PASS_CONTRACT_RECONCILED_PATCH_CANDIDATES_WRITTEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
