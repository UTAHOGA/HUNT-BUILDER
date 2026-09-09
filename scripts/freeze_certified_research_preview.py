#!/usr/bin/env python3
"""Freeze the current certified materialization and build a local Research preview.

The generated preview reuses the normal ``research.html`` and
``hunt-research.js`` implementation.  Its local canonical contract removes raw
future-probability fields so the UI can read only ``certified_p_draw*`` for the
four designs that passed the family certification registry.

No file under ``processed_data`` is changed and this script has no network or
deployment behavior.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from engine.utah_draw_predictive.certification import has_publishable_probability_basis


DEFAULT_MATERIALIZATION = (
    ROOT
    / "audits"
    / "prediction_blind_year_to_year"
    / "certification_repair_clean_2017_2025_20260909"
    / "materialization"
)
DEFAULT_OUTPUT = (
    ROOT
    / "audits"
    / "prediction_release_candidates"
    / "certified_core_20260909_33875"
)
CERTIFIED_DESIGNS = (
    "BONUS_LE_BIG_GAME",
    "BONUS_OIL_BIG_GAME",
    "BONUS_PLE_BIG_GAME",
    "PREFERENCE_GENERAL_SEASON_BUCK_DEER",
)
CERTIFIED_FIELDS = (
    "certified_p_draw",
    "certified_p_draw_mean",
    "certified_p_draw_pct",
)

# These are future probability estimates or display aliases. Historical actual
# result fields are intentionally not in this set and remain available.
RAW_FUTURE_PROBABILITY_FIELDS = {
    "p_draw",
    "p_draw_mean",
    "p_draw_pct",
    "p_draw_p10",
    "p_draw_p50",
    "p_draw_p90",
    "p_max_pool_mean",
    "p_random_mean",
    "p_preference_draw",
    "p_bonus_pool",
    "p_random_pool",
    "p_bonus_pool_pct",
    "p_random_pool_pct",
    "p_prior_year_baseline",
    "p_quota_adjusted",
    "p_rollover_adjusted",
    "p_harvest_adjusted",
    "display_odds_pct",
    "display_odds_text",
    "odds_2026_projected",
    "max_pool_projection_2026",
    "random_draw_odds_2026",
    "random_draw_projection_2026",
    "preference_draw_odds_2026",
    "preference_projection_2026",
    "modeled_preference_probability",
    "draw_probability",
    "guaranteed_probability",
    "p50",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(ROOT)).replace("\\", "/")


def artifact(path: Path) -> dict[str, object]:
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256(path),
    }


def read_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        if len(fields) != len(set(fields)):
            raise RuntimeError("Prediction materialization contains duplicate CSV field names.")
        return list(reader), fields


def copy_verified(source: Path, target: Path) -> dict[str, object]:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    source_hash = sha256(source)
    target_hash = sha256(target)
    if source_hash != target_hash:
        raise RuntimeError(f"Hash mismatch after freezing {source}")
    return {
        "source": relative(source),
        "frozen": relative(target),
        "bytes": target.stat().st_size,
        "sha256": target_hash,
    }


def preview_row(row: dict[str, str], build_id: str) -> dict[str, str]:
    result = {
        field: value
        for field, value in row.items()
        if field not in RAW_FUTURE_PROBABILITY_FIELDS and clean(value)
    }
    # Keep the three allowed fields explicit, including blank values, so the
    # preview contract is directly auditable without relying on missing-key
    # behavior.
    probability_is_publishable = (
        clean(row.get("prediction_certification_status")) == "CERTIFIED"
        and has_publishable_probability_basis(row)
    )
    for field in CERTIFIED_FIELDS:
        result[field] = clean(row.get(field)) if probability_is_publishable else ""
    result["preview_probability_contract"] = "CERTIFIED_P_DRAW_FIELDS_ONLY"
    result["preview_build_id"] = build_id
    return result


def preview_group(row: dict[str, str]) -> tuple[str, str, str]:
    residency = "Nonresident" if clean(row.get("residency")).lower() == "nonresident" else "Resident"
    return (
        clean(row.get("hunt_code")).upper(),
        residency,
        clean(row.get("draw_pool")).lower() or "standard",
    )


def preview_index_row(row: dict[str, str]) -> dict[str, str]:
    fields = (
        "hunt_code",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "hunt_class",
        "weapon",
        "draw_pool",
        "draw_design",
        "draw_system_type",
        "prediction_certification_design",
        "prediction_certification_status",
        "prediction_publication_status",
        "permits_2026_res",
        "permits_2026_nr",
        "permits_2026_total",
    )
    result = {field: clean(row.get(field)) for field in fields if clean(row.get(field))}
    result["detail_path"] = f"hunts/{clean(row.get('hunt_code')).upper()}.json"
    return result


def write_preview_csv(path: Path, rows: list[dict[str, str]], source_fields: list[str]) -> None:
    fields = [field for field in source_fields if field not in RAW_FUTURE_PROBABILITY_FIELDS]
    for field in (*CERTIFIED_FIELDS, "preview_probability_contract", "preview_build_id"):
        if field not in fields:
            fields.append(field)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_harness(
    output: Path,
    summary_json: Path,
    index_json: Path,
    detail_json: Path,
    ladder_csv: Path,
    build_id: str,
    include_all_statuses: bool,
) -> Path:
    source = (ROOT / "research.html").read_text(encoding="utf-8")
    replacements = {
        'href="./style.css': 'href="/style.css',
        'src="./embed-mode.js': 'src="/embed-mode.js',
        'src="./sentry-browser-init.js': 'src="/sentry-browser-init.js',
        'src="./config.js': 'src="/config.js',
        'src="./ui.js': 'src="/ui.js',
        'src="./hunt-research.js': 'src="/hunt-research.js',
        'src="./assets/': 'src="/assets/',
        'href="./assets/': 'href="/assets/',
    }
    for before, after in replacements.items():
        source = source.replace(before, after)
    title_prefix = "LOCAL CERTIFICATION STATUS AUDIT" if include_all_statuses else "LOCAL CERTIFIED PREVIEW"
    source = source.replace(
        "<title>Hunt Research",
        f"<title>{title_prefix} | Hunt Research",
        1,
    )

    summary_url = "/" + relative(summary_json)
    index_url = "/" + relative(index_json)
    detail_url = "/" + relative(detail_json)
    ladder_url = "/" + relative(ladder_csv)
    override = f'''
  <script>
    Object.assign(window.UOGA_CONFIG, {{
      HUNT_RESEARCH_USE_SPLIT_CONTRACT: true,
      HUNT_RESEARCH_ALLOW_LEGACY_FALLBACK: false,
      HUNT_RESEARCH_ENGINE_MODE: 'predictive',
      HUNT_RESEARCH_DATA_VERSION: '{build_id}',
      HUNT_RESEARCH_SUMMARY_SOURCES: ['{summary_url}'],
      HUNT_RESEARCH_SPLIT_INDEX_SOURCES: ['{index_url}'],
      HUNT_RESEARCH_LADDER_SOURCES: ['{ladder_url}'],
      HUNT_RESEARCH_SPLIT_DETAIL_BUNDLE_SOURCES: ['{detail_url}'],
    }});
    window.UOGA_CERTIFIED_PREVIEW = {{
      buildId: '{build_id}',
      probabilityContract: 'CERTIFIED_P_DRAW_FIELDS_ONLY',
      certifiedDesigns: {json.dumps(list(CERTIFIED_DESIGNS))},
      production: false,
    }};
  </script>'''
    config_tag = r'(<script\s+src="/config\.js[^>]*></script>)'
    source, count = re.subn(config_tag, lambda match: match.group(1) + override, source, count=1)
    if count != 1:
        raise RuntimeError("Could not locate the Research config script tag.")

    banner_message = (
        "LOCAL CERTIFICATION STATUS AUDIT — NOT LIVE — Certified designs use only certified_p_draw fields; "
        "all other families display evidence status with future probability withheld."
        if include_all_statuses
        else "LOCAL CERTIFIED PREVIEW — NOT LIVE — Future probability is restricted to certified_p_draw fields for four certified designs."
    )
    banner = f'''
  <div id="certifiedPreviewBanner" role="status" style="position:sticky;top:0;z-index:10000;padding:10px 18px;background:#2f3b2b;color:#fff4dc;border-bottom:3px solid #b98952;font:700 13px/1.35 system-ui,sans-serif;letter-spacing:.04em;text-align:center;">
    {banner_message}
  </div>'''
    source, count = re.subn(r"(<body[^>]*>)", lambda match: match.group(1) + banner, source, count=1)
    if count != 1:
        raise RuntimeError("Could not locate the Research body tag.")

    harness = output / "preview" / "research-certified-preview.html"
    harness.parent.mkdir(parents=True, exist_ok=True)
    harness.write_text(source, encoding="utf-8")
    return harness


def build(
    materialization: Path,
    output: Path,
    *,
    replace_preview: bool = False,
    include_all_statuses: bool = False,
) -> dict[str, object]:
    if output.exists() and not replace_preview:
        raise RuntimeError(f"Refusing to overwrite frozen candidate: {output}")
    if replace_preview:
        existing_frozen = output / "frozen" / "ml_draw_predictions_v1.csv"
        if not existing_frozen.exists():
            raise RuntimeError("Preview replacement requires the previously frozen prediction copy.")

    source = materialization / "ml_draw_predictions_v1.csv"
    materialization_manifest = materialization / "utah_bonus_predictive_manifest.json"
    certification_report = materialization / "prediction_family_certification_report.json"
    registry = ROOT / "governance" / "prediction-family-certification.json"
    acceptance_manifest = (
        ROOT
        / "audits"
        / "prediction_blind_year_to_year"
        / "certification_repair_clean_2017_2025_20260909"
        / "acceptance_review"
        / "acceptance_review_manifest.json"
    )
    required = (source, materialization_manifest, certification_report, registry, acceptance_manifest)
    missing = [relative(path) for path in required if not path.exists()]
    if missing:
        raise RuntimeError(f"Required freeze evidence is missing: {missing}")

    rows, fields = read_csv(source)
    if len(rows) != 33_875:
        raise RuntimeError(f"Expected the reviewed 33,875-row materialization; found {len(rows):,} rows.")

    certification_counts = Counter(clean(row.get("prediction_certification_status")) for row in rows)
    design_counts: dict[str, dict[str, int]] = {}
    certified_designs_seen: set[str] = set()
    unauthorized_certified_design_rows = 0
    uncertified_probability_leaks = 0
    certified_rows_without_probability = 0
    for row in rows:
        status = clean(row.get("prediction_certification_status"))
        design = clean(row.get("prediction_certification_design"))
        has_certified_probability = any(clean(row.get(field)) for field in CERTIFIED_FIELDS)
        bucket = design_counts.setdefault(
            design or "UNCLASSIFIED",
            {"rows": 0, "certified_rows": 0, "rows_with_certified_probability": 0},
        )
        bucket["rows"] += 1
        if status == "CERTIFIED":
            bucket["certified_rows"] += 1
            certified_designs_seen.add(design)
            if design not in CERTIFIED_DESIGNS:
                unauthorized_certified_design_rows += 1
            if not has_certified_probability:
                certified_rows_without_probability += 1
        elif has_certified_probability:
            uncertified_probability_leaks += 1
        if has_certified_probability:
            bucket["rows_with_certified_probability"] += 1

    if certified_designs_seen != set(CERTIFIED_DESIGNS):
        raise RuntimeError(
            f"Certified design set changed: {sorted(certified_designs_seen)}"
        )
    if unauthorized_certified_design_rows or uncertified_probability_leaks:
        raise RuntimeError("The source materialization violates the certification publication boundary.")

    build_id = re.sub(r"[^a-z0-9]+", "-", output.name.lower()).strip("-")
    frozen_prediction = output / "frozen" / "ml_draw_predictions_v1.csv"
    frozen_registry = output / "frozen" / "prediction-family-certification.json"
    frozen_materialization_manifest = output / "frozen" / "utah_bonus_predictive_manifest.json"
    frozen_certification_report = output / "frozen" / "prediction_family_certification_report.json"
    frozen_acceptance_manifest = output / "frozen" / "acceptance_review_manifest.json"
    frozen_records = [
        copy_verified(source, frozen_prediction),
        copy_verified(registry, frozen_registry),
        copy_verified(materialization_manifest, frozen_materialization_manifest),
        copy_verified(certification_report, frozen_certification_report),
        copy_verified(acceptance_manifest, frozen_acceptance_manifest),
    ]

    preview_rows = [
        preview_row(row, build_id)
        for row in rows
        if include_all_statuses
        or (
            clean(row.get("prediction_certification_status")) == "CERTIFIED"
            and clean(row.get("prediction_certification_design")) in CERTIFIED_DESIGNS
        )
    ]
    preview_processed = output / "preview" / "processed_data"
    ladder_csv = preview_processed / "certified_prediction_ladder.csv"
    write_preview_csv(ladder_csv, preview_rows, fields)

    summary_by_group: dict[tuple[str, str, str], dict[str, str]] = {}
    index_by_code: dict[str, dict[str, str]] = {}
    for row in preview_rows:
        group = preview_group(row)
        summary_by_group.setdefault(group, row)
        hunt_code = clean(row.get("hunt_code")).upper()
        if hunt_code:
            index_by_code.setdefault(hunt_code, preview_index_row(row))
    summary_rows = [summary_by_group[group] for group in sorted(summary_by_group)]
    index_rows = [index_by_code[hunt_code] for hunt_code in sorted(index_by_code)]

    summary_json = preview_processed / "hunt_research_2026_summary.json"
    index_json = preview_processed / "hunt_research_2026_split" / "hunt_research_2026.index.json"
    detail_json = preview_processed / "hunt_research_2026_split" / "hunt_research_2026.details.json"
    summary_json.parent.mkdir(parents=True, exist_ok=True)
    index_json.parent.mkdir(parents=True, exist_ok=True)
    with summary_json.open("w", encoding="utf-8") as handle:
        json.dump(summary_rows, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    with index_json.open("w", encoding="utf-8") as handle:
        json.dump(index_rows, handle, ensure_ascii=False, separators=(",", ":"))
        handle.write("\n")
    with detail_json.open("w", encoding="utf-8") as handle:
        json.dump(
            {
                "details_by_hunt_code": {},
                "candidate_source": "CERTIFIED_PREVIEW_SUMMARY_AND_LADDER",
                "candidate_build_id": build_id,
            },
            handle,
            separators=(",", ":"),
        )
        handle.write("\n")
    replaced_monolith = preview_processed / "hunt_research_certified_preview.json"
    if replace_preview and replaced_monolith.exists():
        replaced_monolith.write_text(
            json.dumps(
                {
                    "status": "REPLACED_BY_SPLIT_PREVIEW_CONTRACT",
                    "summary": summary_json.name,
                    "index": f"hunt_research_2026_split/{index_json.name}",
                    "ladder": ladder_csv.name,
                },
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
    harness = build_harness(
        output,
        summary_json,
        index_json,
        detail_json,
        ladder_csv,
        build_id,
        include_all_statuses,
    )

    preview_raw_probability_values = sum(
        1
        for row in preview_rows
        for field in RAW_FUTURE_PROBABILITY_FIELDS
        if clean(row.get(field))
    )
    preview_uncertified_probability_leaks = sum(
        1
        for row in preview_rows
        if clean(row.get("prediction_certification_status")) != "CERTIFIED"
        and any(clean(row.get(field)) for field in CERTIFIED_FIELDS)
    )
    if preview_raw_probability_values or preview_uncertified_probability_leaks:
        raise RuntimeError("Generated preview did not preserve the certified-only probability contract.")
    preview_probability_rows = sum(
        1 for row in preview_rows if any(clean(row.get(field)) for field in CERTIFIED_FIELDS)
    )
    preview_certified_design_rows = sum(
        1
        for row in preview_rows
        if clean(row.get("prediction_certification_status")) == "CERTIFIED"
    )

    materialization_artifacts = {
        path.name: artifact(path)
        for path in sorted(materialization.iterdir())
        if path.is_file()
    }
    manifest = {
        "schema_version": "certified-research-preview-freeze.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": (
            "FROZEN_LOCAL_CERTIFICATION_STATUS_AUDIT_READY"
            if include_all_statuses
            else "FROZEN_LOCAL_CERTIFIED_PREVIEW_READY"
        ),
        "mode": "LOCAL_ONLY_NO_PROCESSED_DATA_R2_SITE_OR_DEPLOYMENT_WRITE",
        "build_id": build_id,
        "source_materialization": relative(materialization),
        "source_materialization_artifacts": materialization_artifacts,
        "primary_prediction": {
            **artifact(frozen_prediction),
            "source_path": relative(source),
            "source_sha256": sha256(source),
            "row_count": len(rows),
            "column_count": len(fields),
            "unique_column_count": len(set(fields)),
            "certification_status_counts": dict(sorted(certification_counts.items())),
            "certified_designs": list(CERTIFIED_DESIGNS),
            "certified_design_counts": {
                design: design_counts[design]
                for design in CERTIFIED_DESIGNS
            },
            "certified_rows_without_probability": certified_rows_without_probability,
            "uncertified_rows_with_certified_probability": uncertified_probability_leaks,
        },
        "frozen_evidence": frozen_records,
        "preview": {
            "harness": artifact(harness),
            "summary_contract": artifact(summary_json),
            "split_index": artifact(index_json),
            "split_details": artifact(detail_json),
            "point_ladder": artifact(ladder_csv),
            "summary_row_count": len(summary_rows),
            "index_hunt_code_count": len(index_rows),
            "point_ladder_row_count": len(preview_rows),
            "certified_design_row_count": preview_certified_design_rows,
            "rows_with_certified_probability": preview_probability_rows,
            "certified_design_rows_without_probability": preview_certified_design_rows - preview_probability_rows,
            "scope": (
                "ALL_MATERIALIZED_ROWS_CERTIFICATION_STATUS_AUDIT"
                if include_all_statuses
                else "FOUR_CERTIFIED_DESIGNS_ONLY"
            ),
            "excluded_materialization_rows": len(rows) - len(preview_rows),
            "excluded_noncertified_materialization_rows": len(rows) - len(preview_rows),
            "probability_contract": "CERTIFIED_P_DRAW_FIELDS_ONLY",
            "allowed_probability_fields": list(CERTIFIED_FIELDS),
            "removed_raw_future_probability_fields": sorted(RAW_FUTURE_PROBABILITY_FIELDS),
            "nonblank_raw_future_probability_values": preview_raw_probability_values,
            "uncertified_rows_with_certified_probability": preview_uncertified_probability_leaks,
            "production": False,
        },
        "explicit_non_actions": [
            "No processed_data file was replaced.",
            "No R2 object was uploaded or changed.",
            "No pages-dist or production site file was changed.",
            "No deployment, Git staging, commit, or push was performed.",
        ],
    }
    manifest_path = output / "freeze_manifest.json"
    with manifest_path.open("w" if replace_preview else "x", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)
        handle.write("\n")
    return {**manifest, "manifest": artifact(manifest_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materialization", type=Path, default=DEFAULT_MATERIALIZATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--replace-preview",
        action="store_true",
        help="Replace only a previously generated local preview after validating its frozen source copy.",
    )
    parser.add_argument(
        "--include-all-statuses",
        action="store_true",
        help="Build an isolated audit preview containing every row while still stripping raw future probability fields.",
    )
    args = parser.parse_args()
    materialization = args.materialization if args.materialization.is_absolute() else ROOT / args.materialization
    output = args.output if args.output.is_absolute() else ROOT / args.output
    result = build(
        materialization.resolve(),
        output.resolve(),
        replace_preview=args.replace_preview,
        include_all_statuses=args.include_all_statuses,
    )
    print("CERTIFIED_RESEARCH_PREVIEW_FREEZE=PASS")
    print(f"MANIFEST={result['manifest']['path']}")
    print(f"PRIMARY_SHA256={result['primary_prediction']['sha256']}")
    print(f"PREVIEW={result['preview']['harness']['path']}")
    print(f"ROWS={result['primary_prediction']['row_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
