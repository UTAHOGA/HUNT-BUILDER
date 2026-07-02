from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
DATABASE_FILE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"


def clean(value: object) -> str:
    return str(value or "").strip()


def union_fields(fieldnames: list[str] | None) -> list[str]:
    fields = list(fieldnames or [])
    if "draw_design" not in fields:
        fields.append("draw_design")
    if "draw_system_type" not in fields:
        fields.append("draw_system_type")
    return fields


def flag_contract(row: dict[str, str], before_draw_design: str, before_draw_system_type: str) -> list[str]:
    flags: list[str] = []
    hunt_class = clean(row.get("hunt_class"))
    hunt_draw_class = clean(row.get("hunt_draw_class"))
    after_draw_system_type = clean(row.get("draw_system_type"))
    if before_draw_design and before_draw_system_type and before_draw_design != before_draw_system_type:
        flags.append("DRAW_DESIGN_DRAW_SYSTEM_TYPE_MISMATCH_REPAIRED")
    if hunt_draw_class and hunt_class and hunt_draw_class != hunt_class:
        flags.append("HUNT_DRAW_CLASS_HUNT_CLASS_CONFLICT_IGNORED")
    if hunt_draw_class and after_draw_system_type and hunt_draw_class != after_draw_system_type:
        flags.append("HUNT_DRAW_CLASS_DRAW_SYSTEM_TYPE_CONFLICT_IGNORED")
    return flags


def target_files() -> list[Path]:
    files = sorted(CANONICAL_DIR.glob("*.csv"))
    if LONG_FILE.exists():
        files.append(LONG_FILE)
    if DATABASE_FILE.exists():
        files.append(DATABASE_FILE)
    return files


def sync_file(path: Path, audit_dir: Path) -> tuple[dict[str, object], list[dict[str, object]], list[dict[str, object]]]:
    changed_rows: list[dict[str, object]] = []
    conflict_rows: list[dict[str, object]] = []
    tmp_path = path.with_suffix(path.suffix + ".draw_design_sync_tmp")
    rows_seen = 0
    rows_changed = 0
    missing_before = 0
    mismatch_before = 0
    missing_after = 0
    mismatch_after = 0

    with path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        original_fields = list(reader.fieldnames or [])
        fields = union_fields(original_fields)
        with tmp_path.open("w", encoding="utf-8", newline="") as target:
            writer = csv.DictWriter(target, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for index, row in enumerate(reader, start=2):
                rows_seen += 1
                before_draw_design = clean(row.get("draw_design"))
                before_draw_system_type = clean(row.get("draw_system_type"))
                if not before_draw_design or not before_draw_system_type:
                    missing_before += 1
                if before_draw_design and before_draw_system_type and before_draw_design != before_draw_system_type:
                    mismatch_before += 1

                authoritative = before_draw_design or before_draw_system_type
                row["draw_design"] = authoritative
                row["draw_system_type"] = authoritative

                after_draw_design = clean(row.get("draw_design"))
                after_draw_system_type = clean(row.get("draw_system_type"))
                if not after_draw_design or not after_draw_system_type:
                    missing_after += 1
                if after_draw_design and after_draw_system_type and after_draw_design != after_draw_system_type:
                    mismatch_after += 1

                flags = flag_contract(row, before_draw_design, before_draw_system_type)
                changed = (
                    before_draw_design != after_draw_design
                    or before_draw_system_type != after_draw_system_type
                    or "draw_design" not in original_fields
                    or "draw_system_type" not in original_fields
                )
                if changed:
                    rows_changed += 1
                    if len(changed_rows) < 5000:
                        changed_rows.append(
                            {
                                "file": str(path.relative_to(REPO)),
                                "line_number": index,
                                "hunt_code": clean(row.get("hunt_code")),
                                "before_draw_design": before_draw_design,
                                "before_draw_system_type": before_draw_system_type,
                                "after_draw_design": after_draw_design,
                                "after_draw_system_type": after_draw_system_type,
                                "contract_flags": "|".join(flags),
                            }
                        )
                if flags:
                    if len(conflict_rows) < 10000:
                        conflict_rows.append(
                            {
                                "file": str(path.relative_to(REPO)),
                                "line_number": index,
                                "hunt_code": clean(row.get("hunt_code")),
                                "hunt_class": clean(row.get("hunt_class")),
                                "hunt_draw_class": clean(row.get("hunt_draw_class")),
                                "draw_design": after_draw_design,
                                "draw_system_type": after_draw_system_type,
                                "contract_flags": "|".join(flags),
                            }
                        )
                writer.writerow(row)

    os.replace(tmp_path, path)
    summary = {
        "file": str(path.relative_to(REPO)),
        "rows_seen": rows_seen,
        "rows_changed": rows_changed,
        "had_draw_design_column_before": "draw_design" in original_fields,
        "had_draw_system_type_column_before": "draw_system_type" in original_fields,
        "missing_or_one_sided_before": missing_before,
        "mismatch_before": mismatch_before,
        "missing_or_one_sided_after": missing_after,
        "mismatch_after": mismatch_after,
    }
    return summary, changed_rows, conflict_rows


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = REPO / "audits" / f"draw_design_authority_sync_{timestamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    changed_rows: list[dict[str, object]] = []
    conflict_rows: list[dict[str, object]] = []
    failed_files: list[dict[str, object]] = []

    for path in target_files():
        try:
            summary, changed, conflicts = sync_file(path, audit_dir)
            summaries.append(summary)
            changed_rows.extend(changed)
            conflict_rows.extend(conflicts)
        except Exception as exc:  # pragma: no cover - audit script defensive path
            failed_files.append({"file": str(path.relative_to(REPO)), "error": repr(exc)})

    write_csv(
        audit_dir / "draw_design_authority_file_summary.csv",
        summaries,
        [
            "file",
            "rows_seen",
            "rows_changed",
            "had_draw_design_column_before",
            "had_draw_system_type_column_before",
            "missing_or_one_sided_before",
            "mismatch_before",
            "missing_or_one_sided_after",
            "mismatch_after",
        ],
    )
    write_csv(
        audit_dir / "draw_design_authority_changed_rows.csv",
        changed_rows,
        [
            "file",
            "line_number",
            "hunt_code",
            "before_draw_design",
            "before_draw_system_type",
            "after_draw_design",
            "after_draw_system_type",
            "contract_flags",
        ],
    )
    write_csv(
        audit_dir / "draw_design_contract_conflicts.csv",
        conflict_rows,
        [
            "file",
            "line_number",
            "hunt_code",
            "hunt_class",
            "hunt_draw_class",
            "draw_design",
            "draw_system_type",
            "contract_flags",
        ],
    )
    write_csv(audit_dir / "draw_design_authority_failed_files.csv", failed_files, ["file", "error"])

    result = {
        "draw_design_authority_sync_complete": not failed_files,
        "files_processed": len(summaries),
        "failed_files": len(failed_files),
        "rows_changed": sum(int(row["rows_changed"]) for row in summaries),
        "mismatches_before": sum(int(row["mismatch_before"]) for row in summaries),
        "mismatches_after": sum(int(row["mismatch_after"]) for row in summaries),
        "missing_or_one_sided_before": sum(int(row["missing_or_one_sided_before"]) for row in summaries),
        "missing_or_one_sided_after": sum(int(row["missing_or_one_sided_after"]) for row in summaries),
        "contract_conflict_rows_sampled": len(conflict_rows),
        "audit_dir": str(audit_dir.relative_to(REPO)),
    }
    (audit_dir / "draw_design_authority_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (audit_dir / "DRAW_DESIGN_AUTHORITY_SYNC_REPORT.md").write_text(
        "\n".join(
            [
                "# Draw Design Authority Sync",
                "",
                f"- Files processed: {result['files_processed']}",
                f"- Failed files: {result['failed_files']}",
                f"- Rows changed: {result['rows_changed']}",
                f"- draw_design/draw_system_type mismatches before: {result['mismatches_before']}",
                f"- draw_design/draw_system_type mismatches after: {result['mismatches_after']}",
                f"- Missing or one-sided values before: {result['missing_or_one_sided_before']}",
                f"- Missing or one-sided values after: {result['missing_or_one_sided_after']}",
                f"- Contract conflict rows sampled: {result['contract_conflict_rows_sampled']}",
                "",
                "Policy: draw_design and draw_system_type are kept equal for now. "
                "hunt_draw_class is not routing authority; conflicts are flagged for review.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0 if not failed_files else 1


if __name__ == "__main__":
    raise SystemExit(main())
