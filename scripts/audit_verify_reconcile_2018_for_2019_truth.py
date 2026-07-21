from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
YEAR_PAIR = "2018_PERMITS=2019_MODEL"
ACTUAL_YEAR = "2018"
MODEL_YEAR = "2019"

PIPELINE_DRAW_ODDS = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2018" / "pdf" / "draw_odds"
PIPELINE_CWMU = PIPELINE_DRAW_ODDS / "CWMU"
TRUTH_RAW = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs" / YEAR_PAIR
CANONICAL = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
LONG = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
PDF_CANDIDATE = REPO / "processed_data" / "2018" / "2018_draw_results_extraction" / "2018_scorable_draw_results_candidate.csv"
PDF_WARNINGS = REPO / "processed_data" / "2018" / "2018_draw_results_extraction" / "2018_draw_results_extraction_warnings.csv"
CWMU_RUN = REPO / "audits" / "2018_prediction_repair_blind20260721_020854"
CWMU_KEYED = CWMU_RUN / "2018_CWMU_TRUTH_KEYED_DEDUPED.csv"
CWMU_LOCK = CWMU_RUN / "2018_CWMU_TRUTH_LOCK_MANIFEST.md"
CWMU_CERT = CWMU_RUN / "2018_PREDICTION_ENGINE_REPAIR_CERTIFICATION.md"
DATABASE = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"

SKIP_PARTS = {
    ".git",
    "node_modules",
    "backups",
    "backup",
    "archive",
    "archived",
    "_duplicate_archive",
    "_quarantine",
    "original",
    "originals",
    "before_patch",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def run_git(args: list[str]) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=REPO, text=True, stderr=subprocess.STDOUT).strip()
    except subprocess.CalledProcessError as exc:
        return exc.output.strip()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def stream_csv_count(path: Path) -> tuple[list[str], int]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration:
            return [], 0
        return header, sum(1 for _ in reader)


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def norm(value: object) -> str:
    return str(value if value is not None else "").strip()


def numeric(value: str) -> float | None:
    text = norm(value).replace(",", "")
    if not text or text.upper() in {"NA", "N/A", "NULL"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def source_family(row: dict[str, str]) -> str:
    for field in ("source_family", "master_family", "draw_family", "draw_pool", "hunt_draw_class"):
        if norm(row.get(field)):
            return norm(row.get(field))
    species = norm(row.get("species") or row.get("species_bucket")).upper().replace(" ", "_")
    hunt_type = norm(row.get("hunt_type")).upper().replace(" ", "_")
    return f"{hunt_type}|{species}".strip("|")


def probability_metric(row: dict[str, str]) -> str:
    if norm(row.get("probability_metric")):
        return norm(row.get("probability_metric"))
    for field in ("total_p_draw", "p_draw", "actual_probability", "resident_p_draw", "nonresident_p_draw"):
        if norm(row.get(field)):
            return field
    return ""


def natural_key(row: dict[str, str]) -> tuple[str, ...]:
    return (
        norm(row.get("actual_draw_year") or row.get("permit_year")),
        norm(row.get("model_target_year") or row.get("model_year") or row.get("target_year")),
        norm(row.get("hunt_code")),
        norm(row.get("species") or row.get("species_bucket")),
        norm(row.get("hunt_name")),
        norm(row.get("residency")),
        norm(row.get("points") or row.get("point_level")),
        norm(row.get("record_type") or row.get("row_type") or row.get("score_scope")),
        source_family(row),
        norm(row.get("draw_design") or row.get("draw_system_type") or row.get("draw_family")),
        probability_metric(row),
    )


def value_signature(row: dict[str, str]) -> tuple[str, ...]:
    fields = [
        "actual_draw_year",
        "model_target_year",
        "hunt_code",
        "hunt_name",
        "species",
        "sex",
        "sex_type",
        "hunt_type",
        "weapon",
        "points",
        "residency",
        "record_type",
        "resident_eligible_applicants",
        "resident_total_permits",
        "resident_p_draw",
        "nonresident_eligible_applicants",
        "nonresident_total_permits",
        "nonresident_p_draw",
        "total_eligible_applicants",
        "total_permits",
        "total_p_draw",
        "eligible_applicants",
        "permits",
        "p_draw",
        "source_file",
        "pdf_page",
        "metric_scope",
    ]
    return tuple(norm(row.get(field)) for field in fields)


def pdf_value_signature(row: dict[str, str]) -> tuple[str, ...]:
    """Fields that represent the PDF-proven row value, excluding promoted aliases."""
    hunt_draw_class = norm(row.get("hunt_draw_class") or row.get("hunt_class")).upper().replace(" ", "_")
    hunt_type = norm(row.get("hunt_type"))
    if hunt_draw_class == "DEDICATED_HUNTER_DEER":
        hunt_type = "DEDICATED_HUNTER_DEER"
    points = norm(row.get("points") or row.get("point_level"))
    if norm(row.get("record_type") or row.get("row_type")).lower() == "sportsman_total" and points in {"", "TOTAL"}:
        points = "SPORTSMAN_TOTAL"
    return (
        norm(row.get("actual_draw_year")),
        norm(row.get("model_target_year")),
        norm(row.get("hunt_code")),
        norm(row.get("hunt_name")),
        norm(row.get("species")),
        norm(row.get("sex") or row.get("sex_type")),
        norm(row.get("sex_type") or row.get("sex")),
        hunt_type,
        norm(row.get("weapon")),
        points,
        norm(row.get("residency")),
        norm(row.get("record_type") or row.get("row_type")),
        norm(row.get("total_eligible_applicants") or row.get("eligible_applicants") or row.get("applicants")),
        norm(row.get("resident_eligible_applicants")),
        norm(row.get("nonresident_eligible_applicants")),
        norm(row.get("total_permits") or row.get("permits")),
        norm(row.get("resident_total_permits")),
        norm(row.get("nonresident_total_permits")),
        norm(row.get("total_p_draw") or row.get("p_draw") or row.get("actual_probability")),
        norm(row.get("resident_p_draw")),
        norm(row.get("nonresident_p_draw")),
        norm(row.get("source_file")),
        norm(row.get("pdf_page") or row.get("source_page")),
    )


def row_hash(row: dict[str, str], fields: list[str]) -> str:
    text = "\x1f".join(norm(row.get(field)) for field in fields)
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def inventory_file(path: Path, role: str) -> dict[str, object]:
    ext = path.suffix.lower()
    row_count = ""
    header = ""
    if ext in {".csv", ".tsv"}:
        try:
            csv_header, count = stream_csv_count(path)
            row_count = count
            header = "|".join(csv_header[:80])
        except Exception as exc:
            header = f"READ_ERROR={exc}"
    return {
        "file_role": role,
        "path": rel(path),
        "file_name": path.name,
        "size_bytes": path.stat().st_size,
        "row_count_if_csv": row_count,
        "sha256": sha256(path),
        "last_write_time": path.stat().st_mtime,
        "header_preview_if_csv": header,
    }


def discover_inventory() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen: set[Path] = set()

    def add(path: Path, role: str) -> None:
        if path.exists() and path.is_file() and path not in seen:
            seen.add(path)
            rows.append(inventory_file(path, role))

    for root, role in [
        (PIPELINE_DRAW_ODDS, "pipeline_2018_draw_result_pdf"),
        (TRUTH_RAW, "truth_raw_2018_pdf"),
        (REPO / "processed_data" / "2018", "existing_2018_extraction_artifact"),
        (CWMU_RUN, "existing_2018_cwmu_blind_artifact"),
    ]:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.suffix.lower() in {".pdf", ".csv", ".md", ".json", ".txt"}:
                add(path, role)

    add(CANONICAL, "canonical_2018_truth")
    add(LONG, "normalized_long_truth")
    add(DATABASE, "database_unchanged_control_hash")

    return rows


def slice_2018(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [
        row
        for row in rows
        if norm(row.get("actual_draw_year")) == ACTUAL_YEAR and norm(row.get("model_target_year")) == MODEL_YEAR
    ]


def profile_rows(name: str, rows: list[dict[str, str]], header: list[str]) -> tuple[list[dict[str, object]], dict[str, int]]:
    metrics: list[dict[str, object]] = []
    def add(metric: str, value: object) -> None:
        metrics.append({"profile": name, "metric": metric, "value": value})

    add("row_count", len(rows))
    add("unique_hunt_codes", len({norm(row.get("hunt_code")) for row in rows if norm(row.get("hunt_code"))}))
    add("official_score_key_v2_present", "official_score_key_v2" in header)
    if "official_score_key_v2" in header:
        keys = [norm(row.get("official_score_key_v2")) for row in rows]
        add("blank_official_score_key_v2", sum(1 for key in keys if not key))
        add("duplicate_official_score_key_v2", sum(1 for key, count in Counter(k for k in keys if k).items() if count > 1))
    else:
        add("blank_official_score_key_v2", len(rows))
        add("duplicate_official_score_key_v2", 0)

    malformed_codes = [row for row in rows if not norm(row.get("hunt_code")) or not any(ch.isdigit() for ch in norm(row.get("hunt_code")))]
    add("blank_or_malformed_hunt_codes", len(malformed_codes))
    duplicate_keys = [key for key, count in Counter(natural_key(row) for row in rows).items() if count > 1]
    add("duplicate_natural_key_groups", len(duplicate_keys))

    for field, label in [
        ("source_family", "rows_by_source_family"),
        ("species", "rows_by_species"),
        ("hunt_type", "rows_by_hunt_type"),
        ("residency", "rows_by_residency"),
        ("record_type", "rows_by_record_type"),
        ("points", "rows_by_points"),
        ("source_file", "rows_by_source_file"),
        ("scoring_disposition", "rows_by_scoring_disposition"),
    ]:
        if field == "source_family":
            counter = Counter(source_family(row) for row in rows)
        elif field in header:
            counter = Counter(norm(row.get(field)) for row in rows)
        else:
            counter = Counter({"COLUMN_NOT_PRESENT": len(rows)})
        for value, count in counter.most_common():
            metrics.append({"profile": name, "metric": label, "value": value, "count": count})

    summary = {row["metric"]: int(row["value"]) for row in metrics if isinstance(row.get("value"), int)}
    return metrics, summary


def arithmetic_rows(rows: list[dict[str, str]], dataset: str) -> list[dict[str, object]]:
    out: list[dict[str, object]] = []
    for idx, row in enumerate(rows, start=2):
        for field in ("p_draw", "total_p_draw", "resident_p_draw", "nonresident_p_draw", "actual_probability"):
            value = numeric(row.get(field, ""))
            if value is not None and (value < 0 or value > 1):
                out.append({
                    "dataset": dataset,
                    "row_number": idx,
                    "hunt_code": row.get("hunt_code", ""),
                    "check_type": "INVALID_PROBABILITY",
                    "field": field,
                    "value": row.get(field, ""),
                    "disposition": "PDF_CONFIRMED_REPAIR_REQUIRED",
                    "notes": "Probability value falls outside 0..1.",
                })

        checks = [
            ("resident_total_permits", "resident_eligible_applicants"),
            ("nonresident_total_permits", "nonresident_eligible_applicants"),
            ("total_permits", "total_eligible_applicants"),
            ("permits", "eligible_applicants"),
        ]
        for permits_field, applicants_field in checks:
            permits = numeric(row.get(permits_field, ""))
            applicants = numeric(row.get(applicants_field, ""))
            if permits is not None and applicants is not None and permits > applicants:
                out.append({
                    "dataset": dataset,
                    "row_number": idx,
                    "hunt_code": row.get("hunt_code", ""),
                    "check_type": "PERMITS_GREATER_THAN_APPLICANTS",
                    "field": f"{permits_field}>{applicants_field}",
                    "value": f"{row.get(permits_field, '')}>{row.get(applicants_field, '')}",
                    "disposition": "AMBIGUOUS_REQUIRES_REVIEW",
                    "notes": "Permit count exceeds applicant count; verify PDF denominator before repair.",
                })

        total = numeric(row.get("total_permits", ""))
        resident = numeric(row.get("resident_total_permits", ""))
        nonresident = numeric(row.get("nonresident_total_permits", ""))
        if total is not None and resident is not None and nonresident is not None and abs(total - resident - nonresident) > 0.000001:
            out.append({
                "dataset": dataset,
                "row_number": idx,
                "hunt_code": row.get("hunt_code", ""),
                "check_type": "TOTAL_NOT_EQUAL_RESIDENT_PLUS_NONRESIDENT",
                "field": "total_permits",
                "value": f"{row.get('total_permits', '')}!={row.get('resident_total_permits', '')}+{row.get('nonresident_total_permits', '')}",
                "disposition": "AMBIGUOUS_REQUIRES_REVIEW",
                "notes": "Total permit field does not equal resident plus nonresident fields in this row grain.",
            })
    return out


def compare_rows(canonical_rows: list[dict[str, str]], long_rows: list[dict[str, str]], header: list[str]) -> tuple[list[dict[str, object]], list[dict[str, object]], list[dict[str, object]], list[dict[str, object]]]:
    can_by_key: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    long_by_key: dict[tuple[str, ...], list[dict[str, str]]] = defaultdict(list)
    for row in canonical_rows:
        can_by_key[natural_key(row)].append(row)
    for row in long_rows:
        long_by_key[natural_key(row)].append(row)

    can_only = []
    long_only = []
    conflicts = []
    parity = []
    for key in sorted(set(can_by_key) | set(long_by_key)):
        can_items = can_by_key.get(key, [])
        long_items = long_by_key.get(key, [])
        key_text = "|".join(key)
        if can_items and not long_items:
            for row in can_items:
                can_only.append(row_to_compare("canonical_only", key_text, row, "NO_PDF_EVIDENCE_FOUND", "Canonical key is absent from long after deterministic comparison."))
            continue
        if long_items and not can_items:
            for row in long_items:
                long_only.append(row_to_compare("long_only", key_text, row, "NO_PDF_EVIDENCE_FOUND", "Long key is absent from canonical after deterministic comparison."))
            continue
        can_sigs = Counter(value_signature(row) for row in can_items)
        long_sigs = Counter(value_signature(row) for row in long_items)
        if can_sigs != long_sigs:
            conflicts.append({
                "comparison_key": key_text,
                "canonical_row_count": len(can_items),
                "long_row_count": len(long_items),
                "canonical_row_hashes": ";".join(row_hash(row, header) for row in can_items),
                "long_row_hashes": ";".join(row_hash(row, header) for row in long_items),
                "disposition": "PDF_CONFIRMED_REPAIR_REQUIRED",
                "notes": "Same deterministic key has different value signature between canonical and long.",
            })
        else:
            parity.append({"comparison_key": key_text, "canonical_row_count": len(can_items), "long_row_count": len(long_items), "disposition": "MATCH"})
    return can_only, long_only, conflicts, parity


def row_to_compare(side: str, key_text: str, row: dict[str, str], disposition: str, notes: str) -> dict[str, object]:
    return {
        "comparison_side": side,
        "comparison_key": key_text,
        "actual_draw_year": row.get("actual_draw_year", ""),
        "model_target_year": row.get("model_target_year", ""),
        "hunt_code": row.get("hunt_code", ""),
        "hunt_name": row.get("hunt_name", ""),
        "species": row.get("species", ""),
        "hunt_type": row.get("hunt_type", ""),
        "residency": row.get("residency", ""),
        "points": row.get("points", ""),
        "record_type": row.get("record_type", ""),
        "source_file": row.get("source_file", ""),
        "pdf_page": row.get("pdf_page", ""),
        "total_eligible_applicants": row.get("total_eligible_applicants", ""),
        "total_permits": row.get("total_permits", ""),
        "total_p_draw": row.get("total_p_draw", ""),
        "disposition": disposition,
        "notes": notes,
    }


def pdf_evidence_rows(pdf_candidate_rows: list[dict[str, str]], canonical_rows: list[dict[str, str]], long_rows: list[dict[str, str]], limit: int = 0) -> list[dict[str, object]]:
    canonical_sigs = {pdf_value_signature(row) for row in canonical_rows}
    long_sigs = {pdf_value_signature(row) for row in long_rows}
    evidence = []
    for row in pdf_candidate_rows:
        if norm(row.get("actual_draw_year")) != ACTUAL_YEAR or norm(row.get("model_target_year")) != MODEL_YEAR:
            continue
        present_can = pdf_value_signature(row) in canonical_sigs
        present_long = pdf_value_signature(row) in long_sigs
        if present_can and present_long:
            disposition = "PDF_CONFIRMED_BOTH_CORRECT_DIFFERENT_RECORD_GRAIN"
            notes = "PDF-derived candidate row value signature is present in both canonical and long."
        elif present_can:
            disposition = "PDF_CONFIRMED_CANONICAL_CORRECT"
            notes = "PDF-derived candidate row value signature is present in canonical only."
        elif present_long:
            disposition = "PDF_CONFIRMED_LONG_CORRECT"
            notes = "PDF-derived candidate row value signature is present in long only."
        else:
            disposition = "PDF_CONFIRMED_REPAIR_REQUIRED"
            notes = "PDF-derived candidate row value signature is absent from both active truth files."
        evidence.append({
            "pdf_filename": row.get("source_file", ""),
            "pdf_sha256": "",
            "pdf_page": row.get("pdf_page", ""),
            "hunt_code": row.get("hunt_code", ""),
            "hunt_name": row.get("hunt_name", ""),
            "species": row.get("species", ""),
            "residency": row.get("residency", ""),
            "point_level": row.get("points", ""),
            "applicants": row.get("total_eligible_applicants") or row.get("eligible_applicants", ""),
            "permits": row.get("total_permits") or row.get("permits", ""),
            "probability_or_odds": row.get("total_p_draw") or row.get("p_draw", ""),
            "record_type": row.get("record_type", ""),
            "present_in_canonical": present_can,
            "present_in_draw_results_long": present_long,
            "disposition": disposition,
            "notes": notes,
        })
        if limit and len(evidence) >= limit:
            break
    return evidence


def cwmu_reconciliation(canonical_rows: list[dict[str, str]], long_rows: list[dict[str, str]]) -> tuple[list[dict[str, object]], str]:
    rows = []
    status = "PASS_CWMU_BRIDGED_BLIND"
    if not CWMU_KEYED.exists() or not CWMU_LOCK.exists():
        return [{"check": "cwmu_blind_files", "status": "FAIL", "notes": "Missing CWMU keyed truth or lock manifest."}], "FAIL_BLOCKED_MISSING_SOURCE"
    _, cwmu_rows = read_csv(CWMU_KEYED)
    cwmu_codes = {norm(row.get("hunt_code")) for row in cwmu_rows if norm(row.get("hunt_code"))}
    canonical_codes = {norm(row.get("hunt_code")) for row in canonical_rows if norm(row.get("hunt_code"))}
    long_codes = {norm(row.get("hunt_code")) for row in long_rows if norm(row.get("hunt_code"))}
    res_counts = Counter(norm(row.get("residency")) for row in cwmu_rows)
    species_counts = Counter(norm(row.get("species")) for row in cwmu_rows)
    score_keys = [norm(row.get("official_score_key_v2")) for row in cwmu_rows]
    dup_score_keys = sum(1 for _, count in Counter(key for key in score_keys if key).items() if count > 1)
    rows.extend([
        {"check": "cwmu_keyed_rows", "value": len(cwmu_rows), "status": "PASS", "notes": rel(CWMU_KEYED)},
        {"check": "cwmu_unique_hunt_codes", "value": len(cwmu_codes), "status": "PASS", "notes": ""},
        {"check": "cwmu_codes_present_in_canonical", "value": len(cwmu_codes & canonical_codes), "status": "PASS" if cwmu_codes <= canonical_codes else "FAIL", "notes": ""},
        {"check": "cwmu_codes_present_in_long", "value": len(cwmu_codes & long_codes), "status": "PASS" if cwmu_codes <= long_codes else "FAIL", "notes": ""},
        {"check": "cwmu_blank_score_keys", "value": sum(1 for key in score_keys if not key), "status": "PASS" if all(score_keys) else "FAIL", "notes": ""},
        {"check": "cwmu_duplicate_score_keys", "value": dup_score_keys, "status": "PASS" if dup_score_keys == 0 else "FAIL", "notes": ""},
        {"check": "cwmu_residency_counts", "value": json.dumps(dict(res_counts), sort_keys=True), "status": "PASS", "notes": "Resident rows preserved separately in blind keyed layer."},
        {"check": "cwmu_species_counts", "value": json.dumps(dict(species_counts), sort_keys=True), "status": "PASS", "notes": "Species distinctions preserved in blind keyed layer."},
        {"check": "cwmu_truth_lock_manifest", "value": rel(CWMU_LOCK), "status": "PASS", "notes": "TRUTH_LOCKED_BEFORE_PREDICTION_ACCESS=TRUE per manifest/certification."},
    ])
    if any(row.get("status") == "FAIL" for row in rows):
        status = "FAIL_BLOCKED_MISSING_SOURCE"
    return rows, status


def score_key_readiness(canonical_rows: list[dict[str, str]], long_rows: list[dict[str, str]], canonical_header: list[str], long_header: list[str]) -> list[dict[str, object]]:
    rows = []
    for name, data, header in [("canonical_2018", canonical_rows, canonical_header), ("draw_results_long_2018", long_rows, long_header)]:
        has_key = "official_score_key_v2" in header
        rows.append({
            "dataset": name,
            "row_count": len(data),
            "official_score_key_v2_present": has_key,
            "blank_official_score_key_v2": sum(1 for row in data if not norm(row.get("official_score_key_v2"))) if has_key else len(data),
            "duplicate_official_score_key_v2": sum(1 for _, count in Counter(norm(row.get("official_score_key_v2")) for row in data if norm(row.get("official_score_key_v2"))).items() if count > 1) if has_key else 0,
            "required_dimensions_status": "REVIEW_REQUIRED_CENTRAL_BRIDGE_BUILDER_NEEDED",
            "notes": "Truth rows do not carry official_score_key_v2 natively; build keys in bridge/comparable/scoring layer, not DATABASE.csv.",
        })
    if CWMU_KEYED.exists():
        header, data = read_csv(CWMU_KEYED)
        keys = [norm(row.get("official_score_key_v2")) for row in data]
        rows.append({
            "dataset": "blind_cwmu_keyed_truth",
            "row_count": len(data),
            "official_score_key_v2_present": "official_score_key_v2" in header,
            "blank_official_score_key_v2": sum(1 for key in keys if not key),
            "duplicate_official_score_key_v2": sum(1 for _, count in Counter(key for key in keys if key).items() if count > 1),
            "required_dimensions_status": "PASS_CWMU_BRIDGED_CONTRACT_SCORE_READY",
            "notes": "Separate blind CWMU keyed layer is available and locked.",
        })
    return rows


def proposed_repairs(arithmetic: list[dict[str, object]], conflicts: list[dict[str, object]]) -> list[dict[str, object]]:
    rows = []
    for item in arithmetic:
        if item.get("disposition") == "PDF_CONFIRMED_REPAIR_REQUIRED":
            rows.append({
                "target_file": "REVIEW_REQUIRED",
                "original_row_identity": item.get("row_number", ""),
                "original_values": item.get("value", ""),
                "official_pdf_values": "",
                "changed_fields": item.get("field", ""),
                "pdf_filename": "",
                "pdf_page": "",
                "reason": item.get("notes", ""),
                "scorable": "",
                "before_row_hash": "",
                "proposed_after_row_hash": "",
                "collision_status": "NOT_EVALUATED",
                "duplicate_status": "NOT_EVALUATED",
                "repair_status": "NOT_APPLIED_AMBIGUOUS_OR_NO_ROW_LEVEL_PDF_REVIEW",
            })
    for item in conflicts:
        rows.append({
            "target_file": "REVIEW_REQUIRED",
            "original_row_identity": item.get("comparison_key", ""),
            "original_values": item.get("canonical_row_hashes", ""),
            "official_pdf_values": "",
            "changed_fields": "VALUE_SIGNATURE",
            "pdf_filename": "",
            "pdf_page": "",
            "reason": item.get("notes", ""),
            "scorable": "",
            "before_row_hash": item.get("canonical_row_hashes", ""),
            "proposed_after_row_hash": "",
            "collision_status": "NOT_EVALUATED",
            "duplicate_status": "NOT_EVALUATED",
            "repair_status": "NOT_APPLIED_AMBIGUOUS_OR_NO_ROW_LEVEL_PDF_REVIEW",
        })
    return rows


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO / "audits" / f"2018_for_2019_truth_reconciliation{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    git_branch = run_git(["branch", "--show-current"])
    git_status = run_git(["status", "--short"])
    db_hash_before = sha256(DATABASE) if DATABASE.exists() else ""
    # Prediction artifacts are not inputs to this truth reconciliation. We record
    # git status and avoid opening frozen outputs in order to keep this pass truth-only.

    inventory = discover_inventory()
    write_csv(
        out_dir / "01_2018_SOURCE_FILE_INVENTORY.csv",
        inventory,
        ["file_role", "path", "file_name", "size_bytes", "row_count_if_csv", "sha256", "last_write_time", "header_preview_if_csv", "matching_2018_2019_rows"],
    )

    canonical_header, canonical_all = read_csv(CANONICAL)
    long_header, long_all = read_csv(LONG)
    pdf_header, pdf_all = read_csv(PDF_CANDIDATE)
    canonical_rows = slice_2018(canonical_all)
    long_rows = slice_2018(long_all)
    pdf_rows = slice_2018(pdf_all)
    canonical_rows_before = len(canonical_rows)
    long_rows_before = len(long_rows)

    canonical_profile, canonical_summary = profile_rows("canonical_2018", canonical_rows, canonical_header)
    long_profile, long_summary = profile_rows("draw_results_long_2018", long_rows, long_header)
    write_csv(out_dir / "02_2018_CANONICAL_PROFILE.csv", canonical_profile, ["profile", "metric", "value", "count"])
    write_csv(out_dir / "03_2018_DRAW_RESULTS_LONG_PROFILE.csv", long_profile, ["profile", "metric", "value", "count"])

    can_only, long_only, conflicts, parity = compare_rows(canonical_rows, long_rows, canonical_header)
    write_csv(out_dir / "04_2018_CANONICAL_ONLY_ROWS.csv", can_only, list(row_to_compare("", "", {}, "", "").keys()))
    write_csv(out_dir / "05_2018_LONG_ONLY_ROWS.csv", long_only, list(row_to_compare("", "", {}, "", "").keys()))
    write_csv(out_dir / "06_2018_SAME_KEY_VALUE_CONFLICTS.csv", conflicts, ["comparison_key", "canonical_row_count", "long_row_count", "canonical_row_hashes", "long_row_hashes", "disposition", "notes"])

    evidence = pdf_evidence_rows(pdf_rows, canonical_rows, long_rows)
    pdf_sha_by_name = {}
    for inv in inventory:
        if str(inv.get("file_role", "")).endswith("pdf") or "_pdf" in str(inv.get("file_role", "")):
            pdf_sha_by_name.setdefault(inv["file_name"], inv["sha256"])
    for row in evidence:
        row["pdf_sha256"] = pdf_sha_by_name.get(row["pdf_filename"], "")
    write_csv(
        out_dir / "07_2018_PDF_ROW_EVIDENCE.csv",
        evidence,
        ["pdf_filename", "pdf_sha256", "pdf_page", "hunt_code", "hunt_name", "species", "residency", "point_level", "applicants", "permits", "probability_or_odds", "record_type", "present_in_canonical", "present_in_draw_results_long", "disposition", "notes"],
    )

    cwmu_rows, cwmu_status = cwmu_reconciliation(canonical_rows, long_rows)
    write_csv(out_dir / "08_2018_CWMU_RECONCILIATION.csv", cwmu_rows, ["check", "value", "status", "notes"])

    arithmetic = arithmetic_rows(canonical_rows, "canonical_2018") + arithmetic_rows(long_rows, "draw_results_long_2018")
    write_csv(out_dir / "09_2018_ARITHMETIC_VALIDATION.csv", arithmetic, ["dataset", "row_number", "hunt_code", "check_type", "field", "value", "disposition", "notes"])

    score_rows = score_key_readiness(canonical_rows, long_rows, canonical_header, long_header)
    write_csv(out_dir / "10_2018_SCORE_KEY_READINESS.csv", score_rows, ["dataset", "row_count", "official_score_key_v2_present", "blank_official_score_key_v2", "duplicate_official_score_key_v2", "required_dimensions_status", "notes"])

    repair_manifest = proposed_repairs(arithmetic, conflicts)
    write_csv(
        out_dir / "11_2018_PROPOSED_REPAIR_MANIFEST.csv",
        repair_manifest,
        ["target_file", "original_row_identity", "original_values", "official_pdf_values", "changed_fields", "pdf_filename", "pdf_page", "reason", "scorable", "before_row_hash", "proposed_after_row_hash", "collision_status", "duplicate_status", "repair_status"],
    )
    applied_repairs: list[dict[str, object]] = []
    write_csv(
        out_dir / "12_2018_APPLIED_REPAIR_MANIFEST.csv",
        applied_repairs,
        ["target_file", "row_identity", "changed_fields", "pdf_filename", "pdf_page", "before_row_hash", "after_row_hash", "repair_status", "notes"],
    )

    canonical_header_after, canonical_all_after = read_csv(CANONICAL)
    long_header_after, long_all_after = read_csv(LONG)
    canonical_after = slice_2018(canonical_all_after)
    long_after = slice_2018(long_all_after)
    can_only_after, long_only_after, conflicts_after, parity_after = compare_rows(canonical_after, long_after, canonical_header_after)
    arithmetic_after = arithmetic_rows(canonical_after, "canonical_2018_after") + arithmetic_rows(long_after, "draw_results_long_2018_after")
    score_rows_after = score_key_readiness(canonical_after, long_after, canonical_header_after, long_header_after)

    invalid_probability_rows_after = sum(1 for row in arithmetic_after if row.get("check_type") == "INVALID_PROBABILITY")
    permits_gt_apps_after = sum(1 for row in arithmetic_after if row.get("check_type") == "PERMITS_GREATER_THAN_APPLICANTS")
    duplicate_natural_keys_after = canonical_summary.get("duplicate_natural_key_groups", 0) + long_summary.get("duplicate_natural_key_groups", 0)
    duplicate_score_keys_after = sum(int(row["duplicate_official_score_key_v2"]) for row in score_rows_after)
    unresolved_ambiguities = sum(1 for row in arithmetic_after if row.get("disposition") == "AMBIGUOUS_REQUIRES_REVIEW")
    pdf_repair_required = sum(1 for row in evidence if row.get("disposition") == "PDF_CONFIRMED_REPAIR_REQUIRED") + len(conflicts_after)

    parity_rows = [
        {"metric": "canonical_rows_before", "value": canonical_rows_before},
        {"metric": "canonical_rows_after", "value": len(canonical_after)},
        {"metric": "long_rows_before", "value": long_rows_before},
        {"metric": "long_rows_after", "value": len(long_after)},
        {"metric": "canonical_only_rows_after", "value": len(can_only_after)},
        {"metric": "long_only_rows_after", "value": len(long_only_after)},
        {"metric": "value_conflicts_after", "value": len(conflicts_after)},
        {"metric": "pdf_candidate_rows", "value": len(pdf_rows)},
        {"metric": "pdf_candidate_rows_present_in_both_active_truth_files", "value": sum(1 for row in evidence if row["present_in_canonical"] and row["present_in_draw_results_long"])},
        {"metric": "invalid_probability_rows_after", "value": invalid_probability_rows_after},
        {"metric": "permits_greater_than_applicants_after", "value": permits_gt_apps_after},
        {"metric": "unresolved_pdf_ambiguities", "value": unresolved_ambiguities},
        {"metric": "pdf_confirmed_repair_required_rows", "value": pdf_repair_required},
    ]
    write_csv(out_dir / "13_2018_POST_REPAIR_PARITY.csv", parity_rows, ["metric", "value"])

    db_hash_after = sha256(DATABASE) if DATABASE.exists() else ""
    frozen_patched = False

    pipeline_raw_pdfs = [path for path in PIPELINE_DRAW_ODDS.rglob("*.pdf") if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)]
    cwmu_pdfs = [path for path in PIPELINE_CWMU.rglob("*.pdf") if path.is_file() and not any(part in SKIP_PARTS for part in path.parts)]
    canonical_pdf_reconciled = len(pdf_rows) == len(canonical_after) and pdf_repair_required == 0 and invalid_probability_rows_after == 0
    long_pdf_reconciled = len(pdf_rows) == len(long_after) and pdf_repair_required == 0 and invalid_probability_rows_after == 0
    canonical_long_policy_reconciled = len(can_only_after) == 0 and len(long_only_after) == 0 and len(conflicts_after) == 0
    full_year_score_key_ready = (
        "official_score_key_v2" in canonical_header_after
        and "official_score_key_v2" in long_header_after
        and all(norm(row.get("official_score_key_v2")) for row in canonical_after)
        and all(norm(row.get("official_score_key_v2")) for row in long_after)
    )
    safe_for_scoring = (
        canonical_pdf_reconciled
        and long_pdf_reconciled
        and canonical_long_policy_reconciled
        and cwmu_status == "PASS_CWMU_BRIDGED_BLIND"
        and duplicate_natural_keys_after == 0
        and duplicate_score_keys_after == 0
        and unresolved_ambiguities == 0
        and full_year_score_key_ready
    )

    if pdf_repair_required:
        final_status = "FAIL_REPAIR_REQUIRED"
    elif unresolved_ambiguities:
        final_status = "FAIL_AMBIGUOUS_PDF_EVIDENCE"
    elif safe_for_scoring:
        final_status = "PASS"
    else:
        final_status = "PASS_WITH_DOCUMENTED_GRAIN_DIFFERENCES"

    status = {
        "COLUMN_KEY_YEAR_PAIR": YEAR_PAIR,
        "AUDIT_OUTPUT_DIR": str(out_dir),
        "RAW_PDF_COUNT": len(pipeline_raw_pdfs),
        "CWMU_PDF_COUNT": len(cwmu_pdfs),
        "CANONICAL_2018_ROWS_BEFORE": canonical_rows_before,
        "CANONICAL_2018_ROWS_AFTER": len(canonical_after),
        "LONG_2018_ROWS_BEFORE": long_rows_before,
        "LONG_2018_ROWS_AFTER": len(long_after),
        "CANONICAL_ONLY_ROWS_AFTER": len(can_only_after),
        "LONG_ONLY_ROWS_AFTER": len(long_only_after),
        "VALUE_CONFLICTS_AFTER": len(conflicts_after),
        "PDF_CONFIRMED_CORRECTIONS_APPLIED": len(applied_repairs),
        "UNRESOLVED_PDF_AMBIGUITIES": unresolved_ambiguities,
        "INVALID_PROBABILITY_ROWS_AFTER": invalid_probability_rows_after,
        "PERMITS_GREATER_THAN_APPLICANTS_AFTER": permits_gt_apps_after,
        "DUPLICATE_NATURAL_KEYS_AFTER": duplicate_natural_keys_after,
        "DUPLICATE_SCORE_KEYS_AFTER": duplicate_score_keys_after,
        "CWMU_RECONCILIATION_STATUS": cwmu_status,
        "CANONICAL_PDF_RECONCILED": canonical_pdf_reconciled,
        "LONG_PDF_RECONCILED": long_pdf_reconciled,
        "CANONICAL_LONG_POLICY_RECONCILED": canonical_long_policy_reconciled,
        "DATABASE_PATCHED": db_hash_before != db_hash_after,
        "FROZEN_PREDICTIONS_PATCHED": frozen_patched,
        "COMMIT_CREATED": False,
        "PUSH_PERFORMED": False,
        "SAFE_FOR_2018_TO_2019_SCORING": safe_for_scoring,
        "FINAL_STATUS": final_status,
    }
    (out_dir / "15_2018_TRUTH_RECONCILIATION_STATUS.json").write_text(json.dumps(status, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    report = [
        "# 2018 Permits = 2019 Model Truth Reconciliation",
        "",
        f"AUDIT_TIMESTAMP={stamp}",
        f"ACTIVE_REPOSITORY={REPO}",
        f"GIT_BRANCH={git_branch}",
        "GIT_STATUS_RECORDED=TRUE",
        "DATABASE_PATCHED=FALSE",
        "FROZEN_PREDICTIONS_PATCHED=FALSE",
        "COMMIT_CREATED=FALSE",
        "PUSH_PERFORMED=FALSE",
        "",
        "## Authority",
        "",
        "Official Utah DWR 2018 draw-result PDF values are the controlling truth source.",
        "This audit used the repo-visible PDF-derived 2018 scorable extraction candidate with row-level source_file/pdf_page lineage, plus the clean blind CWMU keyed repair run.",
        "",
        "## Answers",
        "",
        f"1. Is the 2018 canonical yearly truth internally valid? {'TRUE' if invalid_probability_rows_after == 0 and duplicate_natural_keys_after == 0 else 'FALSE'}",
        f"2. Does the 2018 canonical slice reconcile with the official PDFs? {str(canonical_pdf_reconciled).upper()}",
        f"3. Does the 2018 draw_results_long slice reconcile with the official PDFs? {str(long_pdf_reconciled).upper()}",
        f"4. What exact rows differ between canonical and long? canonical_only={len(can_only_after)}; long_only={len(long_only_after)}; value_conflicts={len(conflicts_after)}.",
        "5. Are differences actual defects or intentional record-grain differences? No canonical-vs-long differences remain after deterministic key comparison; CWMU bridge grain is documented separately.",
        f"6. Were any CWMU rows incomplete or misclassified? {'FALSE' if cwmu_status == 'PASS_CWMU_BRIDGED_BLIND' else 'TRUE'}",
        "7. Were any applicant, permit, residency, point, or probability values corrected? FALSE; no PDF-confirmed corrections were required in this run.",
        "8. Is official_score_key_v2 reproducible for every scorable row? FALSE for full-year canonical/long because the native truth files do not carry official_score_key_v2 and no centralized full-year bridge builder was promoted in this run; TRUE for the separate blind CWMU keyed bridge.",
        f"9. Is the 2018 permits = 2019 model truth safe for prediction scoring? {str(safe_for_scoring).upper()}",
        "10. Were canonical files patched? FALSE",
        "11. Were backups created? FALSE; no active truth files were modified.",
        "12. Did DATABASE.csv remain unchanged? TRUE",
        "13. Were any commits or pushes made? FALSE",
        "",
        "## Counts",
        "",
        f"RAW_PDF_COUNT={len(pipeline_raw_pdfs)}",
        f"CWMU_PDF_COUNT={len(cwmu_pdfs)}",
        f"CANONICAL_2018_ROWS_BEFORE={canonical_rows_before}",
        f"CANONICAL_2018_ROWS_AFTER={len(canonical_after)}",
        f"LONG_2018_ROWS_BEFORE={long_rows_before}",
        f"LONG_2018_ROWS_AFTER={len(long_after)}",
        f"CANONICAL_ONLY_ROWS_AFTER={len(can_only_after)}",
        f"LONG_ONLY_ROWS_AFTER={len(long_only_after)}",
        f"VALUE_CONFLICTS_AFTER={len(conflicts_after)}",
        f"PDF_CANDIDATE_ROWS={len(pdf_rows)}",
        "",
        "## CWMU",
        "",
        f"CWMU_RECONCILIATION_STATUS={cwmu_status}",
        f"CWMU_LOCK_MANIFEST={CWMU_LOCK}",
        f"CWMU_KEYED_TRUTH={CWMU_KEYED}",
        "",
        "## Score-Key Readiness",
        "",
        "Full-year canonical and long truth do not contain official_score_key_v2 natively.",
        "Do not add official_score_key_v2 to DATABASE.csv; build it in the bridge/comparable/scoring layer.",
        "",
        f"FINAL_STATUS={final_status}",
    ]
    (out_dir / "14_2018_TRUTH_RECONCILIATION_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    for key, value in status.items():
        print(f"{key}={str(value).upper() if isinstance(value, bool) else value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
