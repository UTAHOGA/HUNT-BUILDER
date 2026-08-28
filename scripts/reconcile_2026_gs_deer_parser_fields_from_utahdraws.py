"""Repair 2026 adult general-deer outcome fields from retained UtahDraws truth.

The earlier PDF parser wrote the printed permit total into
``successful_applicants`` for a subset of the general-season buck-deer rows.
That is not an applicant outcome metric. This script only repairs rows where
the retained UtahDraws endpoint identifies one adult record with the same
hunt, residency, point level, and applicant count. It retains the PDF parent
reference and records every old/new value in a reproducible audit ledger.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
SNAPSHOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results" / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_allowed_draw_odds_all_flat_rows.csv"
AUDIT_DIR = ROOT / "audits" / "2026_gs_deer_parser_field_reconciliation"
ENDPOINT = "2026_big_game_05_general_season_buck_deer.json"


def clean(value: object) -> str:
    return str(value or "").strip()


def integer(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def point(value: object) -> str:
    number = integer(value)
    return str(number) if number is not None else clean(value)


def key(code: object, residency: object, points: object) -> tuple[str, str, str]:
    return clean(code).upper(), clean(residency).lower(), point(points)


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


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def probability(successful: int, applicants: int) -> tuple[str, str]:
    value = successful / applicants if applicants else 0.0
    return f"{value:.9f}".rstrip("0").rstrip("."), f"{value * 100:.6f}".rstrip("0").rstrip(".")


def is_target(row: dict[str, str]) -> bool:
    return (
        clean(row.get("source_dataset")) == "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS"
        and "G.S. BUCK DEER" in clean(row.get("source_file")).upper()
        and (integer(row.get("eligible_applicants")) or 0) > 0
    )


def target_candidate(canonical: dict[str, str], endpoint_index: dict[tuple[str, str, str], list[dict[str, str]]]) -> dict[str, str] | None:
    candidates = endpoint_index.get(key(canonical.get("hunt_code"), canonical.get("residency"), canonical.get("points")), [])
    adult_same_applicant = [
        row
        for row in candidates
        if clean(row.get("IsYouth")).lower() == "false"
        and integer(row.get("ParticipantCount")) == integer(canonical.get("eligible_applicants"))
    ]
    return adult_same_applicant[0] if len(adult_same_applicant) == 1 else None


def has_exact_endpoint_value(canonical: dict[str, str], endpoint_index: dict[tuple[str, str, str], list[dict[str, str]]]) -> bool:
    for row in endpoint_index.get(key(canonical.get("hunt_code"), canonical.get("residency"), canonical.get("points")), []):
        if (
            integer(canonical.get("eligible_applicants")) == integer(row.get("ParticipantCount"))
            and integer(canonical.get("successful_applicants")) == integer(row.get("SuccessfulCount"))
        ):
            return True
    return False


def canonical_needs_repair(canonical: dict[str, str], endpoint: dict[str, str]) -> bool:
    return integer(canonical.get("successful_applicants")) != integer(endpoint.get("SuccessfulCount"))


def apply_outcome_fields(row: dict[str, str], endpoint: dict[str, str]) -> dict[str, str]:
    repaired = dict(row)
    applicants = integer(endpoint.get("ParticipantCount")) or 0
    successful = integer(endpoint.get("SuccessfulCount")) or 0
    p_draw, p_draw_percent = probability(successful, applicants)
    source = f"UtahDraws DrawOddsData snapshot 2026-08-27: {ENDPOINT}"
    repaired["eligible_applicants"] = str(applicants)
    repaired["successful_applicants"] = str(successful)
    repaired["unsuccessful_applicants"] = str(max(applicants - successful, 0))
    repaired["success_ratio"] = p_draw
    repaired["p_draw"] = p_draw
    repaired["p_draw_percent"] = p_draw_percent
    repaired["source_is_youth"] = "false"
    repaired["source_row_identifier"] = "|".join((ENDPOINT, clean(endpoint.get("HuntCode")).upper(), clean(endpoint.get("residency_label")), point(endpoint.get("Point")), "is_youth=false"))
    repaired["draw_source_file"] = str(SNAPSHOT.relative_to(ROOT)).replace("\\", "/")
    repaired["source_path"] = str(SNAPSHOT.relative_to(ROOT)).replace("\\", "/")
    repaired["parse_method"] = "2026_PDF_SUCCESS_FIELD_REPAIRED_FROM_RETAINED_UTAHDRAWS"
    repaired["extraction_status"] = "retained_utahdraws_value_reconciliation"
    repaired["qa_status"] = "CONFIRMED_CANONICAL_SCORABLE_UTAHDRAWS_VALUE_RECONCILED"
    repaired["qa_notes"] = "PDF parser had populated successful_applicants from a permit field; applicant outcome values reconciled to retained UtahDraws evidence."
    repaired["notes"] = source
    return repaired


def audit_row(before: dict[str, str], after: dict[str, str], endpoint: dict[str, str]) -> dict[str, str]:
    return {
        "hunt_code": clean(before.get("hunt_code")).upper(),
        "residency": clean(before.get("residency")),
        "points": point(before.get("points")),
        "pdf_parent_source_file": clean(before.get("source_file")),
        "endpoint_source_json_file": ENDPOINT,
        "endpoint_is_youth": clean(endpoint.get("IsYouth")),
        "old_eligible_applicants": clean(before.get("eligible_applicants")),
        "new_eligible_applicants": clean(after.get("eligible_applicants")),
        "old_successful_applicants": clean(before.get("successful_applicants")),
        "new_successful_applicants": clean(after.get("successful_applicants")),
        "old_unsuccessful_applicants": clean(before.get("unsuccessful_applicants")),
        "new_unsuccessful_applicants": clean(after.get("unsuccessful_applicants")),
        "old_p_draw": clean(before.get("p_draw")),
        "new_p_draw": clean(after.get("p_draw")),
        "old_p_draw_percent": clean(before.get("p_draw_percent")),
        "new_p_draw_percent": clean(after.get("p_draw_percent")),
        "raw_participant_count": clean(endpoint.get("ParticipantCount")),
        "raw_successful_count": clean(endpoint.get("SuccessfulCount")),
        "reason": "PDF_PARSER_FIELD_ISSUE_SUCCESSFUL_APPLICANTS_WAS_PERMIT_DERIVED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write the verified 105-row outcome-field correction to canonical truth.")
    args = parser.parse_args()

    fields, canonical_rows = read_csv(CANONICAL)
    _, snapshot_rows = read_csv(SNAPSHOT)
    endpoint_index: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for raw in snapshot_rows:
        if clean(raw.get("source_json_file")) == ENDPOINT:
            endpoint_index[key(raw.get("HuntCode"), raw.get("residency_label"), raw.get("Point"))].append(raw)

    repaired_rows: list[dict[str, str]] = []
    ledger: list[dict[str, str]] = []
    unresolved: list[dict[str, str]] = []
    output_rows: list[dict[str, str]] = []
    for row in canonical_rows:
        if not is_target(row):
            output_rows.append(row)
            continue
        endpoint = target_candidate(row, endpoint_index)
        if endpoint is None:
            if not has_exact_endpoint_value(row, endpoint_index):
                unresolved.append({"hunt_code": clean(row.get("hunt_code")).upper(), "residency": clean(row.get("residency")), "points": point(row.get("points")), "reason": "NO_UNIQUE_ADULT_ENDPOINT_ROW_WITH_SAME_APPLICANT_COUNT"})
            output_rows.append(row)
            continue
        if not canonical_needs_repair(row, endpoint):
            output_rows.append(row)
            continue
        repaired = apply_outcome_fields(row, endpoint)
        repaired_rows.append(repaired)
        ledger.append(audit_row(row, repaired, endpoint))
        output_rows.append(repaired)

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    write_csv(AUDIT_DIR / "candidate_field_corrections.csv", list(ledger[0]) if ledger else [], ledger)
    write_csv(AUDIT_DIR / "unresolved_target_rows.csv", ["hunt_code", "residency", "points", "reason"], unresolved)
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "canonical_path": str(CANONICAL.relative_to(ROOT)).replace("\\", "/"),
        "snapshot_path": str(SNAPSHOT.relative_to(ROOT)).replace("\\", "/"),
        "expected_endpoint": ENDPOINT,
        "canonical_rows": len(canonical_rows),
        "target_general_deer_rows": sum(is_target(row) for row in canonical_rows),
        "candidate_field_corrections": len(repaired_rows),
        "unresolved_target_rows": len(unresolved),
        "canonical_sha256_before": sha256(CANONICAL),
    }
    if args.apply:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = AUDIT_DIR / "backups" / f"{CANONICAL.stem}.before_gs_deer_outcome_reconciliation_{stamp}{CANONICAL.suffix}"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(CANONICAL, backup)
        write_csv(CANONICAL, fields, output_rows)
        summary["backup_path"] = str(backup.relative_to(ROOT)).replace("\\", "/")
        summary["canonical_sha256_after"] = sha256(CANONICAL)
    (AUDIT_DIR / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
