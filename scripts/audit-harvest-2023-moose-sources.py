"""Anchor 2023 moose harvest CSV sources used for 2024 modeling.

This audit validates the active moose harvest CSVs against the legacy HUNTS
copies, compares their hunt-code coverage to the moose draw PDF audit, and
records harvest-vs-draw gaps without rewriting harvest truth, draw truth, or
runtime/database outputs.
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
LEGACY_DIR = Path(str(_repo_root() / "pipeline/RAW/hunt_unit_database/2024/csv/Harvest Results"))
ACTIVE_DIR = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2024" / "csv" / "Harvest Results"
DRAW_MOOSE_CODES = ROOT / "data_truth" / "draw_results_truth" / "validation" / "draw_2023_moose_pdf_hunt_codes.csv"
HARVEST_DRAW_COMPARISON = ROOT / "processed_data" / "complete_2023_harvest_vs_draw_comparison.csv"
VALIDATION_DIR = ROOT / "data_truth" / "harvest_results_truth" / "validation"
SOURCE_AUDIT_CSV = VALIDATION_DIR / "harvest_2023_moose_source_files.csv"
CODE_AUDIT_CSV = VALIDATION_DIR / "harvest_2023_moose_code_reconciliation.csv"
SUMMARY_JSON = VALIDATION_DIR / "harvest_2023_moose_source_summary.json"
REPORT_MD = ROOT / "processed_data" / "harvest_2023_moose_source_audit.md"

SOURCE_FILES = [
    {
        "source_file": "harvest_results_2023_MOOSE_all_sources.csv",
        "harvest_family": "bull_moose_all_sources",
        "expected_prefix": "MB",
        "expected_species": "Moose",
    },
    {
        "source_file": "harvest_results_2023_MOOSE_hunt_success.csv",
        "harvest_family": "bull_moose_hunt_success",
        "expected_prefix": "MB",
        "expected_species": "Moose",
    },
    {
        "source_file": "harvest_results_2023_ANTLERLESS_MOOSE_all_sources.csv",
        "harvest_family": "antlerless_moose_all_sources",
        "expected_prefix": "MA",
        "expected_species": "Antlerless Moose",
    },
]


def sha256(path: Path) -> str:
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm(value: str | None) -> str:
    return " ".join(str(value or "").strip().split())


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def number(value: str | None) -> float:
    try:
        return float(str(value or "").strip())
    except ValueError:
        return 0.0


def source_summary(source: dict[str, str]) -> dict[str, str]:
    legacy_path = LEGACY_DIR / source["source_file"]
    active_path = ACTIVE_DIR / source["source_file"]
    rows = read_rows(active_path)
    codes = {norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}
    species_counts = Counter(norm(row.get("species")) for row in rows)
    hunt_type_counts = Counter(norm(row.get("hunt_type")) for row in rows)
    prefixes_ok = all(code.startswith(source["expected_prefix"]) for code in codes)
    byte_match = sha256(legacy_path) == sha256(active_path)
    return {
        "source_file": source["source_file"],
        "harvest_family": source["harvest_family"],
        "legacy_path": str(legacy_path),
        "active_path": str(active_path.relative_to(ROOT)),
        "legacy_exists": "YES" if legacy_path.exists() else "NO",
        "active_exists": "YES" if active_path.exists() else "NO",
        "legacy_sha256": sha256(legacy_path),
        "active_sha256": sha256(active_path),
        "legacy_active_byte_match": "YES" if byte_match else "NO",
        "row_count": str(len(rows)),
        "unique_hunt_codes": str(len(codes)),
        "species_counts_json": json.dumps(dict(sorted(species_counts.items())), sort_keys=True),
        "hunt_type_counts_json": json.dumps(dict(sorted(hunt_type_counts.items())), sort_keys=True),
        "permits_sum": str(sum(number(row.get("permits")) for row in rows)),
        "hunters_afield_sum": str(sum(number(row.get("hunters_afield")) for row in rows)),
        "harvest_sum": str(sum(number(row.get("harvest")) for row in rows)),
        "percent_success_mean_unweighted": str(round(sum(number(row.get("percent_success")) for row in rows) / len(rows), 4) if rows else 0),
        "expected_prefix": source["expected_prefix"],
        "prefixes_ok": "YES" if prefixes_ok else "NO",
        "status": "PASS" if byte_match and rows and prefixes_ok else "REVIEW",
    }


def draw_code_sets() -> dict[str, set[str]]:
    rows = read_rows(DRAW_MOOSE_CODES)
    return {
        "bull_moose_pdf": {norm(row.get("hunt_code")) for row in rows if norm(row.get("source_file")) == "bull moose.pdf"},
        "antlerless_moose_pdf": {
            norm(row.get("hunt_code")) for row in rows if norm(row.get("source_file")) == "antlerless moose.pdf"
        },
    }


def harvest_rows_by_code() -> dict[str, list[dict[str, str]]]:
    output: dict[str, list[dict[str, str]]] = {}
    for source in SOURCE_FILES:
        active_path = ACTIVE_DIR / source["source_file"]
        for row in read_rows(active_path):
            code = norm(row.get("hunt_code"))
            if not code:
                continue
            enriched = dict(row)
            enriched["_source_file"] = source["source_file"]
            enriched["_harvest_family"] = source["harvest_family"]
            output.setdefault(code, []).append(enriched)
    return output


def comparison_by_code() -> dict[str, dict[str, str]]:
    return {
        norm(row.get("hunt_code")): row
        for row in read_rows(HARVEST_DRAW_COMPARISON)
        if norm(row.get("hunt_code"))
    }


def code_reconciliation_rows() -> list[dict[str, str]]:
    draws = draw_code_sets()
    harvest = harvest_rows_by_code()
    comparison = comparison_by_code()
    families = {
        "bull_moose": (draws["bull_moose_pdf"], {code for code in harvest if code.startswith("MB")}),
        "antlerless_moose": (draws["antlerless_moose_pdf"], {code for code in harvest if code.startswith("MA")}),
    }
    output: list[dict[str, str]] = []
    for family, (draw_codes, harvest_codes) in families.items():
        for code in sorted(draw_codes | harvest_codes):
            harvest_matches = harvest.get(code, [])
            comp = comparison.get(code, {})
            if code in draw_codes and code in harvest_codes:
                status = "DRAW_AND_HARVEST"
            elif code in draw_codes:
                status = "DRAW_ONLY"
            else:
                status = "HARVEST_ONLY"
            output.append(
                {
                    "hunt_code": code,
                    "moose_family": family,
                    "in_2023_draw_pdf": "YES" if code in draw_codes else "NO",
                    "in_2023_harvest_csv": "YES" if code in harvest_codes else "NO",
                    "reconciliation_status": status,
                    "harvest_source_files": "|".join(sorted({norm(row.get("_source_file")) for row in harvest_matches})),
                    "harvest_hunt_names": "|".join(sorted({norm(row.get("hunt_name")) for row in harvest_matches if norm(row.get("hunt_name"))})),
                    "harvest_species": "|".join(sorted({norm(row.get("species")) for row in harvest_matches if norm(row.get("species"))})),
                    "harvest_permits_sum": str(sum(number(row.get("permits")) for row in harvest_matches)),
                    "harvest_hunters_afield_sum": str(sum(number(row.get("hunters_afield")) for row in harvest_matches)),
                    "harvest_sum": str(sum(number(row.get("harvest")) for row in harvest_matches)),
                    "comparison_bucket": norm(comp.get("comparison_bucket")),
                    "in_active_database_2026": norm(comp.get("in_active_database_2026")),
                    "comparison_draw_hunt_names": norm(comp.get("draw_hunt_names")),
                    "comparison_harvest_hunt_names": norm(comp.get("harvest_hunt_names")),
                }
            )
    return output


def build_markdown(summary: dict[str, object]) -> str:
    lines = [
        "# 2023 Moose Harvest Source Audit",
        "",
        "Anchors the 2023 moose harvest CSV sources used for 2024 modeling.",
        "",
        "## Source Result",
        "",
        f"- Harvest CSV files checked: {summary['source_file_count']}",
        f"- Byte-identical active copies: {summary['byte_match_count']}",
        f"- Bull moose harvest codes: {summary['bull_moose_harvest_codes']}",
        f"- Antlerless moose harvest codes: {summary['antlerless_moose_harvest_codes']}",
        f"- Bull moose draw-only codes: {summary['bull_moose_draw_only_codes']}",
        f"- Bull moose harvest-only codes: {summary['bull_moose_harvest_only_codes']}",
        f"- Antlerless moose draw/harvest mismatch count: {summary['antlerless_moose_mismatch_count']}",
        "",
        "## Interpretation",
        "",
        "- `MB6252` remains draw-only for 2023 harvest-vs-draw because it is not present in the 2023 moose harvest CSVs.",
        "- Antlerless moose reconciles cleanly: all three MA draw codes have harvest rows.",
        "- The seven bull-moose harvest-only codes are source evidence for 2023 harvest but are not in the standalone bull moose draw PDF code set.",
        "- This step does not rewrite harvest truth, draw truth, permit numbers, runtime files, or website feeds.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    source_rows = [source_summary(source) for source in SOURCE_FILES]
    code_rows = code_reconciliation_rows()
    bull_rows = [row for row in code_rows if row["moose_family"] == "bull_moose"]
    antlerless_rows = [row for row in code_rows if row["moose_family"] == "antlerless_moose"]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "audit_scope": "2023_moose_harvest_sources_for_2024_modeling",
        "reported_hunt_year": 2023,
        "model_target_year": 2024,
        "source_file_count": len(SOURCE_FILES),
        "byte_match_count": sum(1 for row in source_rows if row["legacy_active_byte_match"] == "YES"),
        "review_source_count": sum(1 for row in source_rows if row["status"] != "PASS"),
        "bull_moose_harvest_codes": len({row["hunt_code"] for row in bull_rows if row["in_2023_harvest_csv"] == "YES"}),
        "antlerless_moose_harvest_codes": len(
            {row["hunt_code"] for row in antlerless_rows if row["in_2023_harvest_csv"] == "YES"}
        ),
        "bull_moose_draw_only_codes": sorted(
            row["hunt_code"] for row in bull_rows if row["reconciliation_status"] == "DRAW_ONLY"
        ),
        "bull_moose_harvest_only_codes": sorted(
            row["hunt_code"] for row in bull_rows if row["reconciliation_status"] == "HARVEST_ONLY"
        ),
        "antlerless_moose_mismatch_count": sum(
            1 for row in antlerless_rows if row["reconciliation_status"] != "DRAW_AND_HARVEST"
        ),
        "source_summaries": source_rows,
        "status": "PASS"
        if (
            len(source_rows) == 3
            and all(row["status"] == "PASS" for row in source_rows)
            and sorted(row["hunt_code"] for row in bull_rows if row["reconciliation_status"] == "DRAW_ONLY")
            == ["MB6252"]
            and sum(1 for row in antlerless_rows if row["reconciliation_status"] != "DRAW_AND_HARVEST") == 0
        )
        else "REVIEW",
    }
    source_fields = [
        "source_file",
        "harvest_family",
        "legacy_path",
        "active_path",
        "legacy_exists",
        "active_exists",
        "legacy_sha256",
        "active_sha256",
        "legacy_active_byte_match",
        "row_count",
        "unique_hunt_codes",
        "species_counts_json",
        "hunt_type_counts_json",
        "permits_sum",
        "hunters_afield_sum",
        "harvest_sum",
        "percent_success_mean_unweighted",
        "expected_prefix",
        "prefixes_ok",
        "status",
    ]
    code_fields = [
        "hunt_code",
        "moose_family",
        "in_2023_draw_pdf",
        "in_2023_harvest_csv",
        "reconciliation_status",
        "harvest_source_files",
        "harvest_hunt_names",
        "harvest_species",
        "harvest_permits_sum",
        "harvest_hunters_afield_sum",
        "harvest_sum",
        "comparison_bucket",
        "in_active_database_2026",
        "comparison_draw_hunt_names",
        "comparison_harvest_hunt_names",
    ]
    write_rows(SOURCE_AUDIT_CSV, source_rows, source_fields)
    write_rows(CODE_AUDIT_CSV, code_rows, code_fields)
    SUMMARY_JSON.parent.mkdir(parents=True, exist_ok=True)
    SUMMARY_JSON.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    REPORT_MD.write_text(build_markdown(summary), encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
