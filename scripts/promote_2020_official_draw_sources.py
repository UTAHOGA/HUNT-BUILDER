#!/usr/bin/env python3
"""Promote the verified complete 2020 DWR draw source set.

The fresh-pull directory is immutable acquisition evidence. This command
copies each verified PDF into the durable report-year archive without
overwriting different bytes, refreshes the small retention catalog, and writes
an explicit 2020 import manifest. It does not modify canonical draw truth,
draw_results_long.csv, predictions, or hosted data.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
YEAR = 2020
SOURCE_LIST = (
    ROOT
    / "audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909"
    / "2020/OFFICIAL_DWR_LIVE_SOURCE_URLS_DRAW_YEAR_2020_COMPLETE.csv"
)
FRESH_ROOT = (
    ROOT
    / "audits/prediction_rebuilds/fresh_official_draw_truth_rebuild_2017_forward_20260909"
    / "2020/source_pull_complete_2020_20260910"
)
FRESH_MANIFEST = FRESH_ROOT / "OFFICIAL_DWR_DRAW_PDF_FRESH_PULL_MANIFEST.csv"
FRESH_SUMMARY = FRESH_ROOT / "OFFICIAL_DWR_DRAW_PDF_FRESH_PULL_SUMMARY.json"
CATALOG_DIR = ROOT / "data_truth/draw_results_truth/raw_inventory"
CATALOG_CSV = CATALOG_DIR / "official_draw_source_retention_2017_2026.csv"
CATALOG_JSON = CATALOG_DIR / "official_draw_source_retention_2017_2026.json"
IMPORT_CSV = CATALOG_DIR / "official_draw_source_import_2020.csv"
IMPORT_DETAIL_JSON = CATALOG_DIR / "official_draw_source_import_2020.json"
IMPORT_JSON = CATALOG_DIR / "official_draw_source_import_2020_summary.json"

CATALOG_FIELDS = [
    "report_year",
    "source_family",
    "source_kind",
    "official_url",
    "official_page",
    "official_title",
    "staging_or_snapshot_path",
    "durable_archive_path",
    "sha256",
    "size_bytes",
    "manifest_sha256_status",
    "durable_sha256_status",
    "archive_action",
    "canonical_pdf_source_labels",
    "canonical_source_linkage",
    "notes",
]
IMPORT_FIELDS = CATALOG_FIELDS + ["page_count", "retrieved_at_utc", "ingestion_status"]


def clean(value: object) -> str:
    return str(value or "").strip()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def official_page(source_family: str) -> str:
    if source_family in {"big_game", "big_game_antlerless"}:
        return "wildlife_biggame_odds"
    return "wildlife_historical_odds"


def durable_path(source_family: str, official_url: str) -> Path:
    filename = Path(urlparse(official_url).path).name
    if not filename.lower().endswith(".pdf"):
        raise ValueError(f"Official URL does not end in PDF: {official_url}")
    return (
        ROOT
        / "pipeline/RAW/hunt_unit_database/2020/pdf/draw_odds/official_dwr_archive"
        / source_family
        / filename
    )


def build_import_rows(apply: bool) -> list[dict[str, str]]:
    source_rows = read_csv(SOURCE_LIST)
    fresh_rows = read_csv(FRESH_MANIFEST)
    fresh_by_url = {clean(row["official_url"]): row for row in fresh_rows}
    if len(source_rows) != 16 or len(fresh_rows) != 16:
        raise ValueError(f"Expected 16 complete 2020 sources; found list={len(source_rows)} fresh={len(fresh_rows)}")
    if len(fresh_by_url) != 16:
        raise ValueError("Fresh manifest contains duplicate official URLs")

    fresh_summary = json.loads(FRESH_SUMMARY.read_text(encoding="utf-8"))
    if fresh_summary.get("status") != "PASS_FRESH_OFFICIAL_PULL":
        raise ValueError("Fresh source pull has not passed")
    retrieved_at = clean(fresh_summary.get("generated_at_utc"))

    output: list[dict[str, str]] = []
    for source in source_rows:
        url = clean(source["official_url"])
        fresh = fresh_by_url.get(url)
        if fresh is None or clean(fresh.get("download_status")) != "OK":
            raise ValueError(f"Missing successful fresh pull for {url}")
        fresh_path = ROOT / clean(fresh["fresh_path"])
        expected_hash = clean(fresh["fresh_sha256"])
        if not fresh_path.exists() or sha256(fresh_path) != expected_hash:
            raise ValueError(f"Fresh source hash mismatch: {fresh_path}")

        family = clean(source["source_family"])
        destination = durable_path(family, url)
        action = "PLANNED_COPY"
        if destination.exists():
            if sha256(destination) != expected_hash:
                raise ValueError(f"Refusing to overwrite different durable bytes: {destination}")
            action = "ALREADY_ARCHIVED"
        elif apply:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(fresh_path, destination)
            if sha256(destination) != expected_hash:
                raise ValueError(f"Durable copy hash mismatch: {destination}")
            action = "COPIED_FROM_FRESH_OFFICIAL_2020_PULL"

        ingestion_status = clean(source["ingestion_status"])
        model_source = ingestion_status in {"MODEL_SOURCE", "MODEL_REFERENCE"}
        source_kind = "official_dwr_pdf" if model_source else "official_dwr_pdf_reference_only"
        durable_status = "MATCH" if destination.exists() and sha256(destination) == expected_hash else "NOT_WRITTEN"
        linkage = "CANONICAL_2020_SOURCE_LINKED" if model_source else ingestion_status
        output.append(
            {
                "report_year": str(YEAR),
                "source_family": family,
                "source_kind": source_kind,
                "official_url": url,
                "official_page": official_page(family),
                "official_title": clean(source["official_title"]),
                "staging_or_snapshot_path": relative(fresh_path),
                "durable_archive_path": relative(destination),
                "sha256": expected_hash,
                "size_bytes": clean(fresh["size_bytes"]),
                "manifest_sha256_status": "MATCH",
                "durable_sha256_status": durable_status,
                "archive_action": action,
                "canonical_pdf_source_labels": "14" if model_source else "0",
                "canonical_source_linkage": linkage,
                "notes": clean(source["notes"]),
                "page_count": clean(fresh["page_count"]),
                "retrieved_at_utc": retrieved_at,
                "ingestion_status": ingestion_status,
            }
        )
    return output


def write_csv(path: Path, rows: list[dict[str, str]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def replace_catalog_2020(import_rows: list[dict[str, str]]) -> list[dict[str, str]]:
    catalog = read_csv(CATALOG_CSV)
    indexes = [index for index, row in enumerate(catalog) if clean(row["report_year"]) == str(YEAR)]
    if len(indexes) not in {14, 16}:
        raise ValueError(f"Expected the prior 14-row or promoted 16-row 2020 catalog; found {len(indexes)}")
    insertion = indexes[0]
    retained = [row for row in catalog if clean(row["report_year"]) != str(YEAR)]
    replacement = [{field: clean(row.get(field)) for field in CATALOG_FIELDS} for row in import_rows]
    return retained[:insertion] + replacement + retained[insertion:]


def catalog_summary(catalog: list[dict[str, str]], generated_at: str) -> dict[str, object]:
    return {
        "generated_at_utc": generated_at,
        "scope": "official Utah DWR draw PDFs 2017-2025 plus durable UtahDraws 2026 endpoint snapshot",
        "rows": len(catalog),
        "by_report_year": dict(sorted(Counter(row["report_year"] for row in catalog).items())),
        "manifest_hash_status": dict(sorted(Counter(row["manifest_sha256_status"] for row in catalog).items())),
        "durable_hash_status": dict(sorted(Counter(row["durable_sha256_status"] for row in catalog).items())),
        "archive_actions": dict(sorted(Counter(row["archive_action"] for row in catalog).items())),
        "catalog_csv": relative(CATALOG_CSV),
        "policy": "No raw source is overwritten. Source PDFs stay outside Git; this catalog records official URLs and SHA-256 values.",
        "remaining_lineage_work": "Years other than the promoted 2020 source set retain their prior source-linkage status.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    rows = build_import_rows(args.apply)
    if args.apply and IMPORT_CSV.exists():
        prior_by_url = {clean(row.get("official_url")): row for row in read_csv(IMPORT_CSV)}
        for row in rows:
            prior = prior_by_url.get(row["official_url"], {})
            if (
                prior.get("sha256") == row["sha256"]
                and prior.get("archive_action") == "COPIED_FROM_FRESH_OFFICIAL_2020_PULL"
            ):
                row["archive_action"] = prior["archive_action"]
    status_counts = Counter(row["ingestion_status"] for row in rows)
    action_counts = Counter(row["archive_action"] for row in rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS_READY_TO_APPLY" if not args.apply else "PASS_IMPORTED",
        "report_year": YEAR,
        "official_pdf_count": len(rows),
        "model_source_pdf_count": sum(row["ingestion_status"] != "REFERENCE_ONLY_OUTSIDE_CURRENT_MODEL_SCOPE" for row in rows),
        "reference_only_pdf_count": sum(row["ingestion_status"] == "REFERENCE_ONLY_OUTSIDE_CURRENT_MODEL_SCOPE" for row in rows),
        "total_pages": sum(int(row["page_count"]) for row in rows),
        "ingestion_status_counts": dict(sorted(status_counts.items())),
        "archive_action_counts": dict(sorted(action_counts.items())),
        "all_fresh_hashes_verified": all(row["manifest_sha256_status"] == "MATCH" for row in rows),
        "all_durable_hashes_verified": all(row["durable_sha256_status"] == "MATCH" for row in rows),
        "canonical_truth_changed": False,
        "draw_results_long_changed": False,
        "prediction_runtime_changed": False,
        "hosted_action": "NONE",
        "detail_manifest": relative(IMPORT_DETAIL_JSON),
    }

    if args.apply:
        catalog = replace_catalog_2020(rows)
        write_csv(IMPORT_CSV, rows, IMPORT_FIELDS)
        IMPORT_DETAIL_JSON.write_text(
            json.dumps(
                {
                    "generated_at_utc": summary["generated_at_utc"],
                    "report_year": YEAR,
                    "official_pdf_count": len(rows),
                    "sources": rows,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        write_csv(CATALOG_CSV, catalog, CATALOG_FIELDS)
        CATALOG_JSON.write_text(json.dumps(catalog_summary(catalog, summary["generated_at_utc"]), indent=2) + "\n", encoding="utf-8")
        IMPORT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if summary["all_fresh_hashes_verified"] and (not args.apply or summary["all_durable_hashes_verified"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
