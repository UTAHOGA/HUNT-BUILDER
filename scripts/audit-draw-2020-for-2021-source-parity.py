"""Verify 2020 draw-odds PDF sources used for 2021 modeling.

This is a source-anchor audit only. It checks the user-supplied PDFs from the
older HUNTS repo against the active HUNT-BUILDER copies and records how the
current normalized 2021 draw truth is labeled.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    repo_root = Path(__file__).resolve()
    while repo_root.name != "HUNT-BUILDER" and repo_root.parent != repo_root:
        repo_root = repo_root.parent
    if repo_root.name != "HUNT-BUILDER":
        raise RuntimeError("Could not locate HUNT-BUILDER repo root")
    return repo_root


ROOT = Path(__file__).resolve().parents[1]
LEGACY_SOURCE_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2021/pdf/draw_odds"))
ACTIVE_SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2021" / "pdf" / "draw_odds"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "draw_2020_for_2021_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2020_for_2021_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2020_for_2021_source_parity.md"

EXPECTED_FILES = [
    "20_deer_odds.pdf",
    "20_lifetime_deer.pdf",
    "20_youth_deer.pdf",
    "20_dh_odds.pdf",
    "20_drawing_odds.pdf",
    "20_youth_dh_odds.pdf",
    "20-21_sportsman_odds.pdf",
    "80165f60__cougar_Drawing odds.pdf",
    "baa2fb5d__turkey_2021_turkey_bonus_points_draw_results.pdf",
    "20_youth_bull_elk.pdf",
    "3deb930b__turkey_2021_youth_turkey_draw_results.pdf",
    "98e761bc__Youth general-season deer draw results.pdf",
    "20_bg-odds.pdf",
    "20_antlerless_drawing_odds_report.pdf",
    "20_youth_antlerless_drawing_odds_report.pdf",
    "897696d1__Youth antlerless big game draw results.pdf",
    "c4618029__General-season buck deer draw results.pdf",
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
    return norm(row.get("year") or row.get("draw_year") or row.get("reported_hunt_year_inferred") or row.get("publish_year"))


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def current_2021_draw_truth_summary() -> dict[str, object]:
    rows = [row for row in read_rows(DRAW_LONG) if draw_year(row) == "2021"]
    source_counts = Counter(norm(row.get("source_file")) for row in rows)
    source_files = sorted(key for key in source_counts if key)
    expected_set = set(EXPECTED_FILES)
    return {
        "draw_truth_2021_rows": len(rows),
        "draw_truth_2021_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}),
        "draw_truth_2021_source_file_count": len(source_files),
        "draw_truth_2021_source_files": source_files,
        "draw_truth_2021_source_file_counts": dict(source_counts),
        "draw_truth_source_label_status": (
            "SOURCE_LABEL_LINEAGE_REVIEW"
            if any(source and source not in expected_set for source in source_files)
            else "SOURCE_LABELS_MATCH_EXPECTED_FILES"
        ),
    }


def build_markdown(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 2020 Draw Odds Source Parity For 2021 Modeling",
            "",
            "Compares the user-supplied 2020 draw-odds PDFs in `HUNTS` to the active `HUNT-BUILDER` copies.",
            "",
            "## Source Result",
            "",
            f"- Expected PDFs: {summary['expected_file_count']}",
            f"- Byte-identical active copies: {summary['byte_match_count']}",
            f"- Missing legacy PDFs: {summary['missing_legacy_source_files']}",
            f"- Missing active PDFs: {summary['missing_active_source_files']}",
            "",
            "## 2021 Draw Truth Anchor",
            "",
            f"- 2021 draw truth rows: {summary['draw_truth_2021_rows']}",
            f"- 2021 native unique draw hunt codes: {summary['draw_truth_2021_unique_hunt_codes']}",
            f"- Current normalized source labels: {', '.join(summary['draw_truth_2021_source_files'])}",
            f"- Source label status: {summary['draw_truth_source_label_status']}",
            "",
            "## Guardrail",
            "",
            "This is source-anchor evidence only. It does not extract PDF values, change draw truth rows, or compare 2021 to the 2026 active hunt-code universe.",
            "",
        ]
    )


def main() -> int:
    parity_rows = []
    for name in EXPECTED_FILES:
        legacy_path = LEGACY_SOURCE_DIR / name
        active_path = ACTIVE_SOURCE_DIR / name
        legacy_hash = sha256(legacy_path)
        active_hash = sha256(active_path)
        byte_match = legacy_path.exists() and active_path.exists() and legacy_hash == active_hash
        parity_rows.append(
            {
                "file_name": name,
                "legacy_source_path": str(legacy_path),
                "active_source_path": relative(active_path),
                "legacy_exists": "YES" if legacy_path.exists() else "NO",
                "active_exists": "YES" if active_path.exists() else "NO",
                "legacy_size_bytes": str(legacy_path.stat().st_size) if legacy_path.exists() else "",
                "active_size_bytes": str(active_path.stat().st_size) if active_path.exists() else "",
                "legacy_sha256": legacy_hash,
                "active_sha256": active_hash,
                "byte_hash_match": "YES" if byte_match else "NO",
                "status": "PASS" if byte_match else "REVIEW",
            }
        )

    truth_summary = current_2021_draw_truth_summary()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2020_draw_odds_source_parity_for_2021_modeling",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_source_dir": relative(ACTIVE_SOURCE_DIR),
        "expected_file_count": len(EXPECTED_FILES),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_legacy_source_files": sum(1 for row in parity_rows if row["legacy_exists"] == "NO"),
        "missing_active_source_files": sum(1 for row in parity_rows if row["active_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "model_target_year": "2021",
        "source_draw_result_year": "2020",
        **truth_summary,
        "guardrails": [
            "Source-anchor audit only; no PDF extraction or draw truth rewrite is performed.",
            "2021 draw truth is native-year evidence and is not judged against the 2026 active hunt-code universe.",
            "The current normalized source label is flagged for lineage review if it does not match this expected PDF source set.",
        ],
        "outputs": {
            "parity_csv": relative(PARITY_CSV),
            "summary_json": relative(SUMMARY_JSON),
            "summary_md": relative(REPORT_MD),
        },
    }
    fields = [
        "file_name",
        "legacy_source_path",
        "active_source_path",
        "legacy_exists",
        "active_exists",
        "legacy_size_bytes",
        "active_size_bytes",
        "legacy_sha256",
        "active_sha256",
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
        f"{summary['byte_match_count']}/{summary['expected_file_count']} PDFs byte-match; "
        f"2021 draw truth has {summary['draw_truth_2021_unique_hunt_codes']} native hunt codes."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
