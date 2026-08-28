"""Verify the official 2020 draw-odds PDF package used for 2021 modeling.

The raw PDFs are retained under their report-generation year (2020).  This
source-anchor audit verifies that the retained package still hashes to the
provenance captured when the 2020-for-2021 canonical was extracted.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "draw_odds"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "draw_2020_for_2021_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2020_for_2021_source_parity_summary.json"
EXTRACTION_SUMMARY = VALIDATION_DIR / "draw_results_2020_for_2021_pdf_extraction_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2020_for_2021_source_parity.md"

EXPECTED_FILES = [
    "20_deer_odds.pdf",
    "20_lifetime_deer.pdf",
    "20_youth_deer.pdf",
    "20_dh_odds.pdf",
    "20_youth_dh_odds.pdf",
    "20-21_sportsman_odds.pdf",
    "20_youth_bull_elk.pdf",
    "20_bg-odds.pdf",
    "20_antlerless_drawing_odds_report.pdf",
    "20_youth_antlerless_drawing_odds_report.pdf",
    "5213601e__turkey_2020_turkey_bonus_points_draw_results.pdf",
    "68991b97__turkey_2020_youth_turkey_draw_results.pdf",
    "97ffae94__black_bear_20_drawing_odds.pdf",
]


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def draw_year(row: dict[str, str]) -> str:
    return norm(
        row.get("actual_draw_year")
        or row.get("year")
        or row.get("draw_year")
        or row.get("reported_hunt_year_inferred")
        or row.get("publish_year")
    )


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def current_2020_draw_truth_summary() -> dict[str, object]:
    rows = [row for row in read_rows(DRAW_LONG) if draw_year(row) == "2020"]
    source_counts = Counter(norm(row.get("source_file")) for row in rows)
    source_files = sorted(key for key in source_counts if key)
    expected_set = set(EXPECTED_FILES)
    return {
        "draw_truth_2020_rows": len(rows),
        "draw_truth_2020_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}),
        "draw_truth_2020_source_file_count": len(source_files),
        "draw_truth_2020_source_files": source_files,
        "draw_truth_2020_source_file_counts": dict(source_counts),
        "draw_truth_source_label_status": "SOURCE_LABELS_MATCH_EXPECTED_FILES"
        if set(source_files) == expected_set
        else "SOURCE_LABEL_LINEAGE_REVIEW",
    }


def build_markdown(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 2020 Draw Odds Source Parity For 2021 Modeling",
            "",
            "Verifies the retained official 2020 DWR draw-odds PDF package against the extraction provenance hashes.",
            "",
            "## Source Result",
            "",
            f"- Expected PDFs: {summary['expected_file_count']}",
            f"- PDFs matching extraction provenance hashes: {summary['byte_match_count']}",
            f"- Missing source PDFs: {summary['missing_source_files']}",
            "",
            "## 2020 Draw Truth Anchor",
            "",
            f"- 2020 draw truth rows: {summary['draw_truth_2020_rows']}",
            f"- 2020 native unique draw hunt codes: {summary['draw_truth_2020_unique_hunt_codes']}",
            f"- Current normalized source labels: {', '.join(summary['draw_truth_2020_source_files'])}",
            f"- Source label status: {summary['draw_truth_source_label_status']}",
            "",
            "## Guardrail",
            "",
            "This audit verifies source integrity only. It does not change draw truth rows or compare 2020 to the 2026 active hunt-code universe.",
            "",
        ]
    )


def main() -> int:
    extraction_summary = json.loads(EXTRACTION_SUMMARY.read_text(encoding="utf-8"))
    expected_hashes = extraction_summary["source_sha256"]
    parity_rows = []
    for name in EXPECTED_FILES:
        source_path = SOURCE_DIR / name
        expected_hash = expected_hashes.get(name, "")
        source_hash = sha256(source_path)
        byte_match = source_path.exists() and source_hash == expected_hash
        parity_rows.append(
            {
                "file_name": name,
                "source_path": relative(source_path),
                "source_exists": "YES" if source_path.exists() else "NO",
                "source_size_bytes": str(source_path.stat().st_size) if source_path.exists() else "",
                "expected_extraction_sha256": expected_hash,
                "source_sha256": source_hash,
                "byte_hash_match": "YES" if byte_match else "NO",
                "status": "PASS" if byte_match else "REVIEW",
            }
        )

    truth_summary = current_2020_draw_truth_summary()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2020_draw_odds_source_parity_for_2021_modeling",
        "source_dir": relative(SOURCE_DIR),
        "expected_file_count": len(EXPECTED_FILES),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_source_files": sum(1 for row in parity_rows if row["source_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "model_target_year": "2021",
        "source_draw_result_year": "2020",
        **truth_summary,
        "guardrails": [
            "Source-integrity audit only; no PDF extraction or draw truth rewrite is performed.",
            "2020 draw truth is native-year evidence and is not judged against the 2026 active hunt-code universe.",
            "The current normalized source label is flagged for lineage review if it does not match the extraction source set.",
        ],
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(SUMMARY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }
    fields = [
        "file_name",
        "source_path",
        "source_exists",
        "source_size_bytes",
        "expected_extraction_sha256",
        "source_sha256",
        "byte_hash_match",
        "status",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "2020 draw odds source parity complete: "
        f"{summary['byte_match_count']}/{summary['expected_file_count']} PDFs match extraction provenance; "
        f"2020 draw truth has {summary['draw_truth_2020_unique_hunt_codes']} native hunt codes."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
