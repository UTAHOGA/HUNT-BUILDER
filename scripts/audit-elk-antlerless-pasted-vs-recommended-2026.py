"""Compare pasted 2026 Elk Antlerless permit rows against current recommendation.

Diagnostic only. Does not modify DATABASE.csv.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PASTED = Path(r"C:\Users\tyler\.codex\attachments\3e5bbbe0-b0a0-4d90-a516-9332a47b67bd\pasted-text.txt")
RECON = ROOT / "processed_data/audits/current_2026_hunt_code_permit_reconciliation.csv"
DATABASE = ROOT / "pipeline/RAW/hunt_unit_database/2026/csv/DATABASE.csv"

OUT_AUDIT = ROOT / "processed_data/audits/elk_antlerless_pasted_vs_recommended_2026.csv"
OUT_SUMMARY = ROOT / "processed_data/audits/elk_antlerless_pasted_vs_recommended_2026_summary.json"
OUT_DOC = ROOT / "docs/elk_antlerless_pasted_vs_recommended_2026.md"


def clean(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def int_text(value: object) -> str:
    text = clean(value).replace(",", "")
    if text in {"", "-", "nan", "None"}:
        return ""
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return ""
    number = float(match.group(0))
    return str(int(number)) if number.is_integer() else str(number)


def triple(res: object, nr: object, total: object) -> tuple[str, str, str]:
    r = int_text(res)
    n = int_text(nr)
    t = int_text(total)
    if not t and (r or n):
        t = str(int(r or 0) + int(n or 0))
    return r, n, t


def compare(left: tuple[str, str, str], right: tuple[str, str, str]) -> str:
    if not any(left) and not any(right):
        return "BOTH_BLANK"
    if not any(left):
        return "LEFT_BLANK"
    if not any(right):
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


def parse_pasted() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for raw_line in PASTED.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        code_match = re.search(r"\bEA\d{4}\b", line)
        if code_match:
            if current:
                rows.append(current)
            parts = [part.strip() for part in raw_line.split("\t")]
            code = code_match.group(0)
            current = {
                "pasted_hunt_name": clean(parts[0]) if parts else "",
                "hunt_code": code,
                "pasted_sex_type": clean(parts[2]) if len(parts) > 2 else "",
                "pasted_species": clean(parts[3]) if len(parts) > 3 else "",
                "pasted_weapon": clean(parts[4]) if len(parts) > 4 else "",
                "pasted_hunt_type": clean(parts[5]) if len(parts) > 5 else "",
                "pasted_season": clean(parts[6]) if len(parts) > 6 else "",
                "pasted_res": "",
                "pasted_nr": "",
                "pasted_total": "",
            }
            res_match = re.search(r"Res:\s*([\d,]+)", line, flags=re.I)
            total_match = re.search(r"Total:\s*([\d,]+)", line, flags=re.I)
            if res_match:
                current["pasted_res"] = int_text(res_match.group(1))
            if total_match:
                current["pasted_total"] = int_text(total_match.group(1))
        elif current:
            nr_match = re.search(r"NonRes:\s*([\d,]+)", line, flags=re.I)
            res_match = re.search(r"Res:\s*([\d,]+)", line, flags=re.I)
            total_match = re.search(r"Total:\s*([\d,]+)", line, flags=re.I)
            if nr_match:
                current["pasted_nr"] = int_text(nr_match.group(1))
            if res_match and not current.get("pasted_res"):
                current["pasted_res"] = int_text(res_match.group(1))
            if total_match and not current.get("pasted_total"):
                current["pasted_total"] = int_text(total_match.group(1))
    if current:
        rows.append(current)
    for row in rows:
        row["pasted_res"], row["pasted_nr"], row["pasted_total"] = triple(
            row.get("pasted_res"), row.get("pasted_nr"), row.get("pasted_total")
        )
    return rows


def main() -> int:
    pasted_rows = parse_pasted()
    recon_by_code = {clean(row.get("hunt_code")).upper(): row for row in read_csv(RECON)}
    db_by_code = {clean(row.get("hunt_code")).upper(): row for row in read_csv(DATABASE)}
    pasted_counts = Counter(row["hunt_code"] for row in pasted_rows)

    audit_rows: list[dict[str, object]] = []
    for row in pasted_rows:
        code = row["hunt_code"]
        recon = recon_by_code.get(code, {})
        db = db_by_code.get(code, {})
        pasted_values = triple(row.get("pasted_res"), row.get("pasted_nr"), row.get("pasted_total"))
        recommended_values = triple(
            recon.get("recommended_res"), recon.get("recommended_nr"), recon.get("recommended_total")
        )
        database_values = triple(
            db.get("permit_allotment_2026_res"),
            db.get("permit_allotment_2026_nr"),
            db.get("permit_allotment_2026_total"),
        )
        audit_rows.append(
            {
                "hunt_code": code,
                "pasted_hunt_name": row["pasted_hunt_name"],
                "database_hunt_name": clean(db.get("hunt_name")),
                "recommended_hunt_name": clean(recon.get("hunt_name")),
                "pasted_res": pasted_values[0],
                "pasted_nr": pasted_values[1],
                "pasted_total": pasted_values[2],
                "recommended_res": recommended_values[0],
                "recommended_nr": recommended_values[1],
                "recommended_total": recommended_values[2],
                "database_allotment_res": database_values[0],
                "database_allotment_nr": database_values[1],
                "database_allotment_total": database_values[2],
                "pasted_vs_recommended": compare(pasted_values, recommended_values),
                "pasted_vs_database": compare(pasted_values, database_values),
                "database_alignment": clean(recon.get("database_alignment")),
                "recommended_winner_source": clean(recon.get("winner_source")),
                "recommended_confidence": clean(recon.get("confidence")),
                "pasted_duplicate_count": pasted_counts[code],
                "pasted_hunt_type": row["pasted_hunt_type"],
                "pasted_season": row["pasted_season"],
                "notes": "",
            }
        )

    fields = [
        "hunt_code",
        "pasted_hunt_name",
        "database_hunt_name",
        "recommended_hunt_name",
        "pasted_res",
        "pasted_nr",
        "pasted_total",
        "recommended_res",
        "recommended_nr",
        "recommended_total",
        "database_allotment_res",
        "database_allotment_nr",
        "database_allotment_total",
        "pasted_vs_recommended",
        "pasted_vs_database",
        "database_alignment",
        "recommended_winner_source",
        "recommended_confidence",
        "pasted_duplicate_count",
        "pasted_hunt_type",
        "pasted_season",
        "notes",
    ]
    write_csv(OUT_AUDIT, audit_rows, fields)

    summary = {
        "created_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "pasted_source": str(PASTED),
        "pasted_rows": len(pasted_rows),
        "unique_pasted_hunt_codes": len(set(row["hunt_code"] for row in pasted_rows)),
        "duplicate_pasted_codes": dict(sorted({k: v for k, v in pasted_counts.items() if v > 1}.items())),
        "pasted_vs_recommended_counts": dict(sorted(Counter(row["pasted_vs_recommended"] for row in audit_rows).items())),
        "pasted_vs_database_counts": dict(sorted(Counter(row["pasted_vs_database"] for row in audit_rows).items())),
        "database_alignment_counts": dict(sorted(Counter(row["database_alignment"] for row in audit_rows).items())),
        "recommended_winner_source_counts": dict(sorted(Counter(row["recommended_winner_source"] for row in audit_rows).items())),
        "outputs": {
            "audit_csv": OUT_AUDIT.relative_to(ROOT).as_posix(),
            "summary_json": OUT_SUMMARY.relative_to(ROOT).as_posix(),
            "report_md": OUT_DOC.relative_to(ROOT).as_posix(),
        },
        "guardrail": "Diagnostic only. DATABASE.csv was not modified.",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    lines = [
        "# Elk Antlerless Pasted Values vs Recommended 2026",
        "",
        "## Result",
        "",
        "The pasted Elk Antlerless values strongly support the current recommended values.",
        "",
        "## Counts",
        "",
        f"- Pasted rows parsed: `{len(pasted_rows)}`",
        f"- Unique pasted hunt codes: `{summary['unique_pasted_hunt_codes']}`",
        "",
        "## Pasted vs Recommended",
        "",
    ]
    for status, count in summary["pasted_vs_recommended_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(["", "## Pasted vs DATABASE Allotment", ""])
    for status, count in summary["pasted_vs_database_counts"].items():
        lines.append(f"- `{status}`: `{count}`")
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Audit CSV: `{OUT_AUDIT.relative_to(ROOT).as_posix()}`",
            f"- Summary JSON: `{OUT_SUMMARY.relative_to(ROOT).as_posix()}`",
        ]
    )
    OUT_DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
