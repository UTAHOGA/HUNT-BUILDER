#!/usr/bin/env python3
"""Validate and promote the reproducible 2017 PDF truth candidate.

The 2017 candidate is generated only from retained official DWR documents.
This promotion utility deliberately does not read ``draw_results_long.csv``,
``DATABASE.csv``, actual 2018 outcomes, or prediction artifacts.  It proves
the candidate's source and roster coverage, then writes the yearly canonical
only when ``--write`` is supplied.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly"
CANONICAL_PATH = CANONICAL_DIR / "draw_results_2017_for_2018_canonical_yearly_draw_results.csv"
CANDIDATE = (
    ROOT
    / "audits"
    / "2017_blind_source_truth_20260905"
    / "official_2017_pdf_reconstructed_canonical_yearly_candidate.csv"
)
SOURCE_MANIFEST = (
    ROOT
    / "data_truth"
    / "draw_results_truth"
    / "source_file_aliases"
    / "2017_PERMITS=2018_MODEL_source_alias_manifest.csv"
)
LOCKED_ROSTER = (
    ROOT
    / "data_truth"
    / "hunt_code_universe_truth"
    / "locked"
    / "2017"
    / "LOCKED_2017_HUNT_CODE_UNIVERSE_SUMMARY.json"
)
AUDIT_ROOT = ROOT / "audits" / "2017_canonical_promotion"
LINEAGE_CSV = ROOT / "data_truth" / "draw_results_truth" / "validation" / "canonical_parent_source_mapping_2017.csv"
LINEAGE_JSON = ROOT / "data_truth" / "draw_results_truth" / "validation" / "canonical_parent_source_mapping_2017.json"

LINEAGE_FIELDS = [
    "draw_year", "canonical_source_label", "canonical_rows", "canonical_pdf_pages",
    "source_dataset_values", "source_scope_values", "mapping_status", "mapping_method",
    "scorable_rows", "certifiable_scorable_rows", "scorable_exclusions", "unscorable_structural_rows",
    "scoring_lineage_status", "parent_report_year", "parent_archive_paths", "parent_official_urls",
    "parent_sha256s", "notes",
]


def clean(value: object) -> str:
    return str(value or "").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def number(value: object) -> int:
    text = clean(value).replace(",", "")
    return int(float(text)) if text else 0


def official_key(row: dict[str, str]) -> tuple[str, ...]:
    return tuple(
        clean(row.get(field))
        for field in (
            "actual_draw_year",
            "model_target_year",
            "source_file",
            "pdf_page",
            "hunt_code",
            "points",
            "record_type",
        )
    )


def validate(candidate: Path) -> tuple[list[str], list[dict[str, str]], dict[str, object]]:
    headers, rows = read_csv(candidate)
    reconstruction_manifest = candidate.parent / "official_2017_pdf_reconstructed_source_manifest.json"
    with reconstruction_manifest.open(encoding="utf-8") as handle:
        reconstruction = json.load(handle)
    with LOCKED_ROSTER.open(encoding="utf-8") as handle:
        roster = json.load(handle)
    _, manifest_rows = read_csv(SOURCE_MANIFEST)

    errors: list[str] = []
    if not rows:
        errors.append("Candidate contains zero rows")
    expected_candidate_hash = clean(
        (reconstruction.get("canonical_yearly_candidate") or {}).get("output_sha256")
    )
    actual_candidate_hash = sha256(candidate)
    if expected_candidate_hash != actual_candidate_hash:
        errors.append("Candidate hash differs from the source-only reconstruction manifest")
    if clean(reconstruction.get("status")) != "PASS_SOURCE_ONLY_RECONSTRUCTION":
        errors.append("Source-only reconstruction manifest is not PASS_SOURCE_ONLY_RECONSTRUCTION")

    aliases = {
        clean(row.get("standardized_raw_pdf_relative_path")).replace("\\", "/"): row
        for row in manifest_rows
    }
    candidate_sources = {clean(row.get("source_file")).replace("\\", "/") for row in rows}
    missing_aliases = sorted(candidate_sources - set(aliases))
    if missing_aliases:
        errors.append(f"Candidate references source files absent from alias manifest: {missing_aliases}")
    source_hash_failures: list[str] = []
    for source, alias in aliases.items():
        path = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2017" / "pdf" / "draw_odds" / source
        if not path.exists() or sha256(path) != clean(alias.get("sha256")):
            source_hash_failures.append(source)
    if source_hash_failures:
        errors.append(f"Retained source SHA-256 mismatch or missing files: {source_hash_failures}")

    duplicate_count = sum(count - 1 for count in Counter(official_key(row) for row in rows).values() if count > 1)
    if duplicate_count:
        errors.append(f"Candidate has {duplicate_count} duplicate official table identities")
    wrong_year_rows = [row for row in rows if clean(row.get("actual_draw_year")) != "2017" or clean(row.get("model_target_year")) != "2018"]
    if wrong_year_rows:
        errors.append(f"Candidate has {len(wrong_year_rows)} rows outside the 2017-to-2018 boundary")
    blank_codes = [row for row in rows if not clean(row.get("hunt_code"))]
    if blank_codes:
        errors.append(f"Candidate has {len(blank_codes)} blank hunt-code rows")

    arithmetic_failures = []
    for row in rows:
        try:
            total_apps = number(row.get("total_eligible_applicants"))
            total_permits = number(row.get("total_permits"))
            lane_apps = number(row.get("resident_eligible_applicants")) + number(row.get("nonresident_eligible_applicants"))
            lane_permits = number(row.get("resident_total_permits")) + number(row.get("nonresident_total_permits"))
        except ValueError:
            arithmetic_failures.append(row)
            continue
        if total_apps != lane_apps or total_permits != lane_permits:
            arithmetic_failures.append(row)
    if arithmetic_failures:
        errors.append(f"Candidate has {len(arithmetic_failures)} resident/nonresident total mismatches")

    candidate_codes = {clean(row.get("hunt_code")) for row in rows if clean(row.get("hunt_code"))}
    roster_codes = set(roster.get("canonical_minus_long_codes") or [])
    if candidate_codes != roster_codes:
        errors.append(
            "Candidate hunt-code coverage differs from locked 2017 roster: "
            f"missing={len(roster_codes - candidate_codes)} extra={len(candidate_codes - roster_codes)}"
        )

    summary: dict[str, object] = {
        "source_year": 2017,
        "target_year": 2018,
        "candidate_path": candidate.relative_to(ROOT).as_posix(),
        "candidate_sha256": actual_candidate_hash,
        "candidate_rows": len(rows),
        "candidate_hunt_codes": len(candidate_codes),
        "locked_roster_hunt_codes": len(roster_codes),
        "candidate_source_files": len(candidate_sources),
        "alias_manifest_rows_hash_verified": len(aliases) - len(source_hash_failures),
        "duplicate_official_table_identity_rows": duplicate_count,
        "resident_nonresident_arithmetic_mismatches": len(arithmetic_failures),
        "source_scope_rows": dict(sorted(Counter(clean(row.get("source_scope")) for row in rows).items())),
        "source_file_rows": dict(sorted(Counter(clean(row.get("source_file")) for row in rows).items())),
        "truth_boundary": {
            "opened_draw_results_long": False,
            "opened_DATABASE_csv": False,
            "opened_2018_actual_truth": False,
            "opened_prediction_outputs": False,
        },
        "result": "PASS_2017_CANONICAL_PROMOTION_GATE" if not errors else "FAIL_2017_CANONICAL_PROMOTION_GATE",
        "errors": errors,
    }
    return headers, rows, summary


def write_csv(path: Path, header: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=header, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_lineage_mapping(candidate: Path, rows: list[dict[str, str]]) -> dict[str, object]:
    """Write the 2017 canonical-to-parent scope map from the validated manifest.

    Every parent link is exact: the canonical's recorded source-file path is
    an alias-manifest path whose retained PDF SHA-256 was verified by the
    promotion gate.  The source files that cannot form a hunt-level canonical
    remain visible as retained, noncanonical evidence instead of disappearing.
    """
    _, aliases_rows = read_csv(SOURCE_MANIFEST)
    aliases = {
        clean(row.get("standardized_raw_pdf_relative_path")).replace("\\", "/"): row
        for row in aliases_rows
    }
    exclusions_path = candidate.parent / "official_2017_pdf_page_identity_exclusions.csv"
    exclusion_counts: Counter[str] = Counter()
    if exclusions_path.exists():
        _, exclusions = read_csv(exclusions_path)
        exclusion_counts.update(clean(row.get("source_file")).replace("\\", "/") for row in exclusions)

    by_source: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_source.setdefault(clean(row.get("source_file")).replace("\\", "/"), []).append(row)

    mapping_rows: list[dict[str, str]] = []
    for source, alias in sorted(aliases.items()):
        canonical_rows = by_source.get(source, [])
        is_active = clean(alias.get("active_for_scoring")).lower() == "true"
        disposition = clean(alias.get("source_disposition"))
        if canonical_rows:
            mapping_status = "LINKED"
            mapping_method = "EXACT_ALIAS_MANIFEST_PATH_AND_SHA256"
            scoring_lineage = "SOURCE_LINEAGE_COMPLETE_ENGINE_SCORING_GATE_SEPARATE"
        else:
            mapping_status = "RETAINED_NONCANONICAL_SOURCE_SCOPE"
            mapping_method = "MANIFEST_RETAINED_EXCLUSION"
            scoring_lineage = "NOT_APPLICABLE_NO_HUNT_LEVEL_CANONICAL_ROWS"
        note_parts = [
            "Exact 2017 canonical-parent link through the retained alias manifest and SHA-256-verified official DWR PDF.",
            f"Manifest disposition: {disposition}.",
        ]
        if exclusion_counts[source]:
            note_parts.append(
                f"{exclusion_counts[source]} parsed page rows lacked an explicit official hunt code and were excluded rather than inferred."
            )
        mapping_rows.append(
            {
                "draw_year": "2017",
                "canonical_source_label": source,
                "canonical_rows": str(len(canonical_rows)),
                "canonical_pdf_pages": str(len({clean(row.get("pdf_page")) for row in canonical_rows})),
                "source_dataset_values": "; ".join(sorted({clean(row.get("source_dataset")) for row in canonical_rows if clean(row.get("source_dataset"))})),
                "source_scope_values": "; ".join(sorted({clean(row.get("source_scope")) for row in canonical_rows if clean(row.get("source_scope"))})),
                "mapping_status": mapping_status,
                "mapping_method": mapping_method,
                "scorable_rows": str(len(canonical_rows)) if is_active else "0",
                "certifiable_scorable_rows": "0",
                "scorable_exclusions": "" if is_active else disposition,
                "unscorable_structural_rows": "0",
                "scoring_lineage_status": scoring_lineage,
                "parent_report_year": "2017",
                "parent_archive_paths": (
                    "pipeline/RAW/hunt_unit_database/2017/pdf/draw_odds/" + source
                ),
                "parent_official_urls": "",
                "parent_sha256s": clean(alias.get("sha256")),
                "notes": " ".join(note_parts),
            }
        )

    LINEAGE_CSV.parent.mkdir(parents=True, exist_ok=True)
    write_csv(LINEAGE_CSV, LINEAGE_FIELDS, mapping_rows)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "2017 canonical row-source scope to archived-parent official PDF mapping",
        "source_scope_records": len(mapping_rows),
        "canonical_rows": len(rows),
        "canonical_sources_linked": sum(1 for row in mapping_rows if row["mapping_status"] == "LINKED"),
        "retained_noncanonical_source_scopes": sum(1 for row in mapping_rows if row["mapping_status"] != "LINKED"),
        "canonical_rows_by_mapping_status": {
            "LINKED": sum(int(row["canonical_rows"]) for row in mapping_rows if row["mapping_status"] == "LINKED"),
            "RETAINED_NONCANONICAL_SOURCE_SCOPE": sum(int(row["canonical_rows"]) for row in mapping_rows if row["mapping_status"] != "LINKED"),
        },
        "mapping_csv": LINEAGE_CSV.relative_to(ROOT).as_posix(),
        "status": "PASS_2017_CANONICAL_PARENT_SOURCE_LINEAGE_COMPLETE",
        "next_gate": "The map proves historical source lineage only; acceptance scoring remains governed by ADR-0006.",
    }
    LINEAGE_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="Create the canonical 2017 file after all gates pass.")
    parser.add_argument(
        "--candidate",
        type=Path,
        default=CANDIDATE,
        help="Audit-local source-only reconstruction candidate to validate and optionally promote.",
    )
    parser.add_argument(
        "--write-lineage",
        action="store_true",
        help="Write the durable 2017 canonical-parent source mapping after the gate passes.",
    )
    args = parser.parse_args()

    candidate = args.candidate.resolve()
    if not candidate.is_relative_to(ROOT):
        raise ValueError(f"Candidate must remain inside this repository: {candidate}")
    header, rows, summary = validate(candidate)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = AUDIT_ROOT / timestamp
    out_dir.mkdir(parents=True, exist_ok=True)
    summary["write_requested"] = args.write
    summary["canonical_path"] = CANONICAL_PATH.relative_to(ROOT).as_posix()
    summary["canonical_existed_before_run"] = CANONICAL_PATH.exists()

    if args.write and summary["result"] == "PASS_2017_CANONICAL_PROMOTION_GATE":
        if CANONICAL_PATH.exists():
            raise RuntimeError(f"Refusing to overwrite an existing canonical: {CANONICAL_PATH}")
        CANONICAL_DIR.mkdir(parents=True, exist_ok=True)
        promoted = []
        aliases = {clean(row.get("standardized_raw_pdf_relative_path")).replace("\\", "/"): row for row in read_csv(SOURCE_MANIFEST)[1]}
        for row in rows:
            promoted_row = dict(row)
            alias = aliases[clean(row.get("source_file")).replace("\\", "/")]
            active = clean(alias.get("active_for_scoring")).lower() == "true"
            promoted_row["candidate_promotion_status"] = (
                "CONFIRMED_CANONICAL_SCORABLE" if active else "CONFIRMED_CANONICAL_ENGINE_UNSUPPORTED_SOURCE_RETAINED"
            )
            promoted.append(promoted_row)
        write_csv(CANONICAL_PATH, header, promoted)
        summary["canonical_rows"] = len(promoted)
        summary["canonical_sha256"] = sha256(CANONICAL_PATH)
        summary["canonical_source_value_changes"] = 0
        summary["canonical_metadata_change"] = "candidate_promotion_status only"
        summary["promotion_result"] = "PROMOTED_2017_CANONICAL_FROM_HASH_VERIFIED_OFFICIAL_PDF_CANDIDATE"
    else:
        summary["promotion_result"] = "DRY_RUN_NO_CANONICAL_WRITE" if not args.write else "BLOCKED_BY_PROMOTION_GATE"

    if args.write_lineage and summary["result"] == "PASS_2017_CANONICAL_PROMOTION_GATE":
        summary["lineage_mapping"] = write_lineage_mapping(candidate, rows)
    elif args.write_lineage:
        summary["lineage_mapping"] = {"status": "BLOCKED_BY_PROMOTION_GATE"}

    (out_dir / "2017_canonical_promotion_manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["result"] == "PASS_2017_CANONICAL_PROMOTION_GATE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
