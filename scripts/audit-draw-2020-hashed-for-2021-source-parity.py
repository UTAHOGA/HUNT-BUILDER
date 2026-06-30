"""Verify hashed-name 2020 draw-odds PDF sources used for 2021 modeling.

This is a source-anchor audit only. It checks the user-supplied hashed PDF
package from the older HUNTS repo against the active HUNT-BUILDER copies and
records how it overlaps the already anchored `20_*` 2020-for-2021 source set.
"""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
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
LEGACY_SOURCE_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds"))
ACTIVE_SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2020" / "pdf" / "draw_odds"
NAMED_2020_SOURCE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2021" / "pdf" / "draw_odds"
DRAW_LONG = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
VALIDATION_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
PARITY_CSV = VALIDATION_DIR / "draw_2020_hashed_for_2021_source_parity.csv"
SUMMARY_JSON = VALIDATION_DIR / "draw_2020_hashed_for_2021_source_parity_summary.json"
REPORT_MD = ROOT / "processed_data" / "draw_2020_hashed_for_2021_source_parity.md"


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv_rows(path: Path) -> list[dict[str, str]]:
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
    return norm(row.get("year") or row.get("draw_year") or row.get("reported_draw_year") or row.get("reported_hunt_year_inferred"))


def relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def pdf_files(path: Path) -> list[Path]:
    return sorted(path.glob("*.pdf"), key=lambda item: item.name.lower())


def duplicate_hash_groups(paths: list[Path]) -> list[dict[str, object]]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        by_hash[sha256(path)].append(path.name)
    return [
        {"sha256": key, "files": sorted(names), "file_count": len(names)}
        for key, names in sorted(by_hash.items())
        if len(names) > 1
    ]


def named_source_hash_index() -> dict[str, list[str]]:
    by_hash: dict[str, list[str]] = defaultdict(list)
    for path in pdf_files(NAMED_2020_SOURCE_DIR):
        by_hash[sha256(path)].append(path.name)
    return by_hash


def current_draw_truth_summary() -> dict[str, object]:
    rows = read_csv_rows(DRAW_LONG)
    rows_2020 = [row for row in rows if draw_year(row) == "2020"]
    rows_2021 = [row for row in rows if draw_year(row) == "2021"]
    source_counts = Counter(norm(row.get("source_file")) for row in rows_2021)
    source_files = sorted(key for key in source_counts if key)
    return {
        "draw_truth_2020_rows": len(rows_2020),
        "draw_truth_2020_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows_2020 if norm(row.get("hunt_code"))}),
        "draw_truth_2021_rows": len(rows_2021),
        "draw_truth_2021_unique_hunt_codes": len({norm(row.get("hunt_code")) for row in rows_2021 if norm(row.get("hunt_code"))}),
        "draw_truth_2021_source_file_count": len(source_files),
        "draw_truth_2021_source_files": source_files,
        "draw_truth_2021_source_file_counts": dict(source_counts),
        "draw_truth_source_label_status": "SOURCE_LABEL_LINEAGE_REVIEW",
    }


def build_markdown(summary: dict[str, object]) -> str:
    return "\n".join(
        [
            "# 2020 Hashed Draw PDF Source Parity For 2021 Modeling",
            "",
            "Compares the user-supplied hashed-name 2020 draw-odds PDFs in `HUNTS` to active `HUNT-BUILDER` copies.",
            "",
            "## Source Result",
            "",
            f"- Expected/source PDFs: {summary['expected_file_count']}",
            f"- Byte-identical active copies: {summary['byte_match_count']}",
            f"- Missing legacy PDFs: {summary['missing_legacy_source_files']}",
            f"- Missing active PDFs: {summary['missing_active_source_files']}",
            f"- Active-only PDFs: {summary['active_only_source_file_count']}",
            f"- Active duplicate hash groups: {summary['active_duplicate_hash_group_count']}",
            "",
            "## Relationship To Existing 20-Star Source Set",
            "",
            f"- Same-hash matches to existing `20_*` source folder: {summary['same_hash_named_2020_source_match_count']}",
            f"- Hashed PDFs unique to this folder lineage: {summary['hashed_sources_without_named_2020_match_count']}",
            "",
            "## 2021 Draw Truth Anchor",
            "",
            f"- Current normalized 2020 draw truth rows: {summary['draw_truth_2020_rows']}",
            f"- Current normalized 2021 draw truth rows: {summary['draw_truth_2021_rows']}",
            f"- Current normalized 2021 native hunt codes: {summary['draw_truth_2021_unique_hunt_codes']}",
            f"- Current 2021 source labels: {', '.join(summary['draw_truth_2021_source_files'])}",
            f"- Source label status: {summary['draw_truth_source_label_status']}",
            "",
            "## Guardrail",
            "",
            "This is source-anchor evidence only. It does not extract PDF values, change draw truth rows, or compare 2020/2021 to the 2026 active hunt-code universe.",
            "",
        ]
    )


def main() -> int:
    legacy_paths = pdf_files(LEGACY_SOURCE_DIR)
    active_paths = pdf_files(ACTIVE_SOURCE_DIR)
    legacy_names = {path.name for path in legacy_paths}
    active_names = {path.name for path in active_paths}
    named_index = named_source_hash_index()
    parity_rows: list[dict[str, str]] = []
    for legacy_path in legacy_paths:
        active_path = ACTIVE_SOURCE_DIR / legacy_path.name
        legacy_hash = sha256(legacy_path)
        active_hash = sha256(active_path)
        named_matches = sorted(named_index.get(legacy_hash, []))
        byte_match = legacy_path.exists() and active_path.exists() and legacy_hash == active_hash
        parity_rows.append(
            {
                "file_name": legacy_path.name,
                "legacy_source_path": str(legacy_path),
                "active_source_path": relative(active_path),
                "legacy_exists": "YES" if legacy_path.exists() else "NO",
                "active_exists": "YES" if active_path.exists() else "NO",
                "legacy_size_bytes": str(legacy_path.stat().st_size) if legacy_path.exists() else "",
                "active_size_bytes": str(active_path.stat().st_size) if active_path.exists() else "",
                "legacy_sha256": legacy_hash,
                "active_sha256": active_hash,
                "byte_hash_match": "YES" if byte_match else "NO",
                "same_hash_named_2020_source_files": "|".join(named_matches),
                "same_hash_named_2020_source_match": "YES" if named_matches else "NO",
                "status": "PASS" if byte_match else "REVIEW",
            }
        )

    truth_summary = current_draw_truth_summary()
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2020_hashed_draw_odds_source_parity_for_2021_modeling",
        "legacy_source_dir": str(LEGACY_SOURCE_DIR),
        "active_source_dir": relative(ACTIVE_SOURCE_DIR),
        "named_2020_source_dir": relative(NAMED_2020_SOURCE_DIR),
        "expected_file_count": len(legacy_paths),
        "active_source_file_count": len(active_paths),
        "byte_match_count": sum(1 for row in parity_rows if row["byte_hash_match"] == "YES"),
        "missing_legacy_source_files": sum(1 for row in parity_rows if row["legacy_exists"] == "NO"),
        "missing_active_source_files": sum(1 for row in parity_rows if row["active_exists"] == "NO"),
        "review_file_count": sum(1 for row in parity_rows if row["status"] != "PASS"),
        "active_only_source_file_count": len(active_names - legacy_names),
        "active_only_source_files": sorted(active_names - legacy_names),
        "legacy_duplicate_hash_groups": duplicate_hash_groups(legacy_paths),
        "active_duplicate_hash_groups": duplicate_hash_groups(active_paths),
        "active_duplicate_hash_group_count": len(duplicate_hash_groups(active_paths)),
        "same_hash_named_2020_source_match_count": sum(1 for row in parity_rows if row["same_hash_named_2020_source_match"] == "YES"),
        "hashed_sources_without_named_2020_match_count": sum(1 for row in parity_rows if row["same_hash_named_2020_source_match"] == "NO"),
        "hashed_sources_without_named_2020_match": [
            row["file_name"] for row in parity_rows if row["same_hash_named_2020_source_match"] == "NO"
        ],
        "source_draw_result_year": "2020",
        "model_target_year": "2021",
        **truth_summary,
        "guardrails": [
            "Source-anchor audit only; no PDF extraction or draw truth rewrite is performed.",
            "2020 hashed PDF sources are model-target-year 2021 source evidence.",
            "Do not merge hashed-name and named `20_*` lineages without retaining both filename/hash evidence.",
            "Do not compare this historical source package to the 2026 active hunt-code universe as a completeness score.",
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
        "same_hash_named_2020_source_files",
        "same_hash_named_2020_source_match",
        "status",
    ]
    write_rows(PARITY_CSV, parity_rows, fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    REPORT_MD.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(
        "2020 hashed draw PDF source parity complete: "
        f"{summary['byte_match_count']}/{summary['expected_file_count']} PDFs byte-match; "
        f"{summary['same_hash_named_2020_source_match_count']} match named 20-star sources."
    )
    return 0 if summary["review_file_count"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
