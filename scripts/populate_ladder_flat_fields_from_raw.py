from __future__ import annotations

import csv
import json
import os
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
CANONICAL_DIR = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
LONG_FILE = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"

TARGET_FIELDS = [
    "metric_scope",
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
    "successful_applicants",
    "unsuccessful_applicants",
]

RAW_FIELDS = [
    "eligible_applicants",
    "bonus_permits",
    "regular_permits",
    "success_ratio",
    "p_draw",
    "p_draw_percent",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "NULL", "NONE"}:
        return None
    try:
        return float(text)
    except Exception:
        return None


def render_number(value: float) -> str:
    if abs(value - round(value)) < 0.0000001:
        return str(int(round(value)))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def target_files() -> list[Path]:
    files = [
        path
        for path in sorted(CANONICAL_DIR.glob("draw_results_*_canonical_yearly_draw_results.csv"))
        if ".backup" not in path.name.lower()
    ]
    if LONG_FILE.exists():
        files.append(LONG_FILE)
    return files


def infer_prefix(row: dict[str, str]) -> str:
    residency = clean(row.get("residency")).lower().replace("-", "").replace(" ", "")
    if residency in {"nonresident", "nonres", "nr"}:
        return "nonresident"
    if residency in {"resident", "res", "r"}:
        return "resident"
    if residency in {"total", "all"}:
        return "total"
    if any(clean(row.get(f"total_{field}")) for field in RAW_FIELDS):
        return "total"
    if any(clean(row.get(f"resident_{field}")) for field in RAW_FIELDS) and not any(
        clean(row.get(f"nonresident_{field}")) for field in RAW_FIELDS
    ):
        return "resident"
    if any(clean(row.get(f"nonresident_{field}")) for field in RAW_FIELDS) and not any(
        clean(row.get(f"resident_{field}")) for field in RAW_FIELDS
    ):
        return "nonresident"
    return "flat"


def metric_scope_for_prefix(row: dict[str, str], prefix: str) -> str:
    if prefix in {"resident", "nonresident", "total"}:
        return prefix
    residency = clean(row.get("residency")).lower().replace("-", "").replace(" ", "")
    if residency in {"nonresident", "nonres", "nr"}:
        return "nonresident"
    if residency in {"resident", "res", "r"}:
        return "resident"
    return "total"


def source_value(row: dict[str, str], prefix: str, field: str) -> str:
    if prefix == "flat":
        return clean(row.get(field))
    return clean(row.get(f"{prefix}_{field}"))


def changed_row_sample(
    path: Path,
    line_number: int,
    row: dict[str, str],
    prefix: str,
    before: dict[str, str],
    after: dict[str, str],
) -> dict[str, object]:
    return {
        "file": str(path.relative_to(REPO)),
        "line_number": line_number,
        "hunt_code": clean(row.get("hunt_code")),
        "points": clean(row.get("points")),
        "residency": clean(row.get("residency")),
        "source_prefix": prefix,
        **{f"before_{field}": before.get(field, "") for field in TARGET_FIELDS},
        **{f"after_{field}": after.get(field, "") for field in TARGET_FIELDS},
    }


def populate_row(row: dict[str, str]) -> tuple[bool, str, dict[str, str], dict[str, str]]:
    prefix = infer_prefix(row)
    before = {field: clean(row.get(field)) for field in TARGET_FIELDS}
    row["metric_scope"] = metric_scope_for_prefix(row, prefix)

    for field in RAW_FIELDS:
        value = source_value(row, prefix, field)
        if value:
            row[field] = value

    bonus = number(row.get("bonus_permits"))
    regular = number(row.get("regular_permits"))
    eligible = number(row.get("eligible_applicants"))
    if bonus is not None or regular is not None:
        successful = (bonus or 0.0) + (regular or 0.0)
        row["successful_applicants"] = render_number(successful)
        if eligible is not None:
            row["unsuccessful_applicants"] = render_number(max(0.0, eligible - successful))

    after = {field: clean(row.get(field)) for field in TARGET_FIELDS}
    return before != after, prefix, before, after


def process_file(path: Path) -> tuple[dict[str, object], list[dict[str, object]]]:
    tmp_path = path.with_suffix(path.suffix + ".ladder_flat_tmp")
    changed_samples: list[dict[str, object]] = []
    rows_seen = 0
    rows_changed = 0
    source_prefix_counts: dict[str, int] = {}
    nonblank_after = {field: 0 for field in TARGET_FIELDS}

    with path.open("r", encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        fields = list(reader.fieldnames or [])
        for field in TARGET_FIELDS:
            if field not in fields:
                fields.append(field)
        with tmp_path.open("w", encoding="utf-8", newline="") as dst:
            writer = csv.DictWriter(dst, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for line_number, row in enumerate(reader, start=2):
                rows_seen += 1
                changed, prefix, before, after = populate_row(row)
                source_prefix_counts[prefix] = source_prefix_counts.get(prefix, 0) + 1
                if changed:
                    rows_changed += 1
                    if len(changed_samples) < 10000:
                        changed_samples.append(changed_row_sample(path, line_number, row, prefix, before, after))
                for field in TARGET_FIELDS:
                    if clean(row.get(field)):
                        nonblank_after[field] += 1
                writer.writerow(row)

    os.replace(tmp_path, path)
    summary = {
        "file": str(path.relative_to(REPO)),
        "rows_seen": rows_seen,
        "rows_changed": rows_changed,
        "source_prefix_counts_json": json.dumps(source_prefix_counts, sort_keys=True),
        **{f"nonblank_after_{field}": nonblank_after[field] for field in TARGET_FIELDS},
    }
    return summary, changed_samples


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    audit_dir = REPO / "audits" / f"ladder_flat_field_population_{timestamp}"
    audit_dir.mkdir(parents=True, exist_ok=True)
    summaries: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []

    for path in target_files():
        try:
            summary, changed = process_file(path)
            summaries.append(summary)
            samples.extend(changed)
        except Exception as exc:  # pragma: no cover - defensive audit path
            failures.append({"file": str(path.relative_to(REPO)), "error": repr(exc)})

    summary_fields = [
        "file",
        "rows_seen",
        "rows_changed",
        "source_prefix_counts_json",
        *[f"nonblank_after_{field}" for field in TARGET_FIELDS],
    ]
    sample_fields = [
        "file",
        "line_number",
        "hunt_code",
        "points",
        "residency",
        "source_prefix",
        *[f"before_{field}" for field in TARGET_FIELDS],
        *[f"after_{field}" for field in TARGET_FIELDS],
    ]
    write_csv(audit_dir / "ladder_flat_field_population_summary.csv", summaries, summary_fields)
    write_csv(audit_dir / "ladder_flat_field_population_changed_rows_sample.csv", samples, sample_fields)
    write_csv(audit_dir / "ladder_flat_field_population_failures.csv", failures, ["file", "error"])

    result = {
        "ladder_flat_field_population_complete": not failures,
        "files_processed": len(summaries),
        "failed_files": len(failures),
        "rows_seen": sum(int(row["rows_seen"]) for row in summaries),
        "rows_changed": sum(int(row["rows_changed"]) for row in summaries),
        "audit_dir": str(audit_dir.relative_to(REPO)),
        "target_fields": TARGET_FIELDS,
        "rule": "Flat fields populated from resident/nonresident/total raw ladder columns; successful=bonus+regular; unsuccessful=eligible-successful.",
    }
    (audit_dir / "ladder_flat_field_population_summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    (audit_dir / "LADDER_FLAT_FIELD_POPULATION_REPORT.md").write_text(
        "\n".join(
            [
                "# Ladder Flat Field Population",
                "",
                f"- Files processed: {result['files_processed']}",
                f"- Failed files: {result['failed_files']}",
                f"- Rows seen: {result['rows_seen']}",
                f"- Rows changed: {result['rows_changed']}",
                "",
                "The flat ladder fields were populated from raw point-ladder columns, not from hunt-level permit totals.",
                "Rows with explicit residency use the matching residency lane; wide rows use the total lane.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
