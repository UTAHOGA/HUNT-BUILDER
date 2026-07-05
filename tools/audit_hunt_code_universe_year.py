#!/usr/bin/env python3
"""Audit a permit year's hunt-code universe across PDFs and normalized truth.

This is read-only. It does not mutate DATABASE.csv, canonical yearly files,
runtime outputs, or locked hunt-code universe folders.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

import pdfplumber
from pypdf import PdfReader


REPO = Path(__file__).resolve().parents[1]
CODE_RE = re.compile(r"\b[A-Z]{2,3}\d{4}\b")
SCORABLE_RECORD_TYPES = {
    "point_level_draw_result",
    "point_row",
    "sportsman_total_draw_result",
    "sportsman_total",
}


def clean(value: Any) -> str:
    return str(value if value is not None else "").strip()


def norm_code(value: Any) -> str:
    return re.sub(r"\s+", "", clean(value).upper())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dedupe_pdf_paths(paths: list[Path]) -> tuple[list[Path], list[dict[str, Any]]]:
    """Keep one copy of byte-identical PDFs and report skipped duplicates."""
    seen: dict[str, Path] = {}
    kept: list[Path] = []
    duplicates: list[dict[str, Any]] = []
    for path in paths:
        try:
            digest = sha256(path)
        except FileNotFoundError:
            kept.append(path)
            continue
        if digest in seen:
            duplicates.append(
                {
                    "kept_source_file": str(seen[digest].relative_to(REPO)),
                    "duplicate_source_file": str(path.relative_to(REPO)),
                    "sha256": digest,
                }
            )
            continue
        seen[digest] = path
        kept.append(path)
    return kept, duplicates


def source_role(path: Path) -> str:
    parts = [part.lower() for part in path.parts]
    name = path.name.lower()
    is_regulation_source = any(part in {"regulations", "regulation", "rules regulations", "rules regs"} for part in parts)
    is_draw_source = any(
        part in {"draw results", "draw_results", "draw_odds"} or ("draw" in part and "result" in part)
        for part in parts
    )
    if is_draw_source and "permit quota" in name:
        return "PERMIT_QUOTA_PDF"
    if is_regulation_source:
        if "biggameapp" in name:
            return "REGULATION_BIG_GAME_APPLICATION"
        if "field_regs" in name or "field" in name:
            return "REGULATION_FIELD_REGS"
        if "bear" in name:
            return "REGULATION_BEAR"
        if "cougar" in name:
            return "REGULATION_COUGAR"
        if "furbearer" in name:
            return "REGULATION_FURBEARER"
        if "upland" in name or "turkey" in name:
            return "REGULATION_UPLAND_TURKEY"
        return "REGULATION_OTHER"
    if is_draw_source:
        return "DRAW_RESULT_PDF"
    return "SOURCE_PDF_OTHER"


def extract_pdf_codes(pdf_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    unique_codes: set[str] = set()
    page_count = 0
    status = "OK"
    error = ""
    pdf_bytes = 0
    pdf_sha256 = ""
    try:
        pdf_bytes = pdf_path.stat().st_size
        pdf_sha256 = sha256(pdf_path)
        reader = PdfReader(str(pdf_path))
        page_count = len(reader.pages)
        for page_number, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            for line_number, line in enumerate(text.splitlines(), start=1):
                codes = sorted({norm_code(match.group(0)) for match in CODE_RE.finditer(line)})
                for code in codes:
                    unique_codes.add(code)
                    evidence.append(
                        {
                            "hunt_code": code,
                            "source_role": source_role(pdf_path),
                            "source_file": str(pdf_path.relative_to(REPO)),
                            "pdf_page": page_number,
                            "line_number": line_number,
                            "line_text": " ".join(line.split())[:500],
                        }
                    )
    except FileNotFoundError as exc:  # pragma: no cover - audit report path
        status = "MISSING"
        error = str(exc)
    except Exception as exc:  # pragma: no cover - audit report path
        status = "ERROR"
        error = str(exc)
    summary = {
        "source_role": source_role(pdf_path),
        "source_file": str(pdf_path.relative_to(REPO)),
        "bytes": pdf_bytes,
        "sha256": pdf_sha256,
        "page_count": page_count,
        "status": status,
        "error": error,
        "unique_hunt_codes": len(unique_codes),
        "evidence_rows": len(evidence),
    }
    return evidence, summary


def first_nonblank(rows: list[dict[str, str]], fields: Iterable[str]) -> str:
    for row in rows:
        for field in fields:
            value = clean(row.get(field))
            if value:
                return value
    return ""


def group_by_code(rows: Iterable[dict[str, str]], code_field: str = "hunt_code") -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        code = norm_code(row.get(code_field))
        if code:
            grouped[code].append(row)
    return grouped


def actual_year(row: dict[str, str]) -> str:
    return clean(row.get("actual_draw_year") or row.get("year"))


def model_target_year(row: dict[str, str]) -> str:
    return clean(row.get("model_target_year") or row.get("forecast_year") or row.get("target_year"))


def record_type(row: dict[str, str]) -> str:
    return clean(row.get("record_type") or row.get("row_type") or row.get("algorithm_status")).lower()


def canonical_path(year: int) -> Path:
    return REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / (
        f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
    )


def load_canonical_rows(year: int) -> list[dict[str, str]]:
    rows = read_csv(canonical_path(year))
    return [
        row
        for row in rows
        if (actual_year(row).replace(".0", "") == str(year) or model_target_year(row).replace(".0", "") == str(year + 1))
    ]


def load_long_rows(year: int) -> list[dict[str, str]]:
    path = REPO / "data_truth" / "draw_results_truth" / "normalized" / "draw_results_long.csv"
    rows = read_csv(path)
    return [
        row
        for row in rows
        if (actual_year(row).replace(".0", "") == str(year) or model_target_year(row).replace(".0", "") == str(year + 1))
    ]


def database_support_rows(year: int) -> list[dict[str, str]]:
    path = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
    rows = read_csv(path)
    permit_fields = [f"permits_{year + 1}_res", f"permits_{year + 1}_nr", f"permits_{year + 1}_total", f"permits_{year + 1}_source"]
    boundary_year_fields = [f"boundary_id_{year}", f"hunt_name_{year}"]
    if year == 2026:
        permit_fields = [
            "permits_2026_res",
            "permits_2026_nr",
            "permits_2026_total",
            "permits_2026_source",
            "permit_allotment_2026_source",
        ]
        boundary_year_fields = ["boundary_id", "hunt_name"]
    out = []
    for row in rows:
        if any(clean(row.get(field)) for field in permit_fields + boundary_year_fields):
            out.append(row)
    return out


def locked_2026_rows() -> dict[str, dict[str, str]]:
    path = REPO / "data_truth" / "hunt_code_universe_truth" / "locked" / "2026" / "LOCKED_2026_HUNT_CODE_UNIVERSE_WITH_BOUNDARY_ID.csv"
    return {norm_code(row.get("hunt_code")): row for row in read_csv(path) if norm_code(row.get("hunt_code"))}


def classify(
    year: int,
    code: str,
    canonical_rows: list[dict[str, str]],
    regulation_sources: set[str],
    draw_pdf_sources: set[str],
    db_rows: list[dict[str, str]],
    long_rows: list[dict[str, str]],
) -> tuple[str, str, str]:
    has_scorable = any(record_type(row) in SCORABLE_RECORD_TYPES for row in canonical_rows)
    has_reference = any(canonical_rows)
    if has_scorable:
        return (
            f"MODEL_WORKBOOK_{year}_PERMITS_{year + 1}_MODEL",
            "CANDIDATE_MODEL_SCORABLE_REQUIRES_ENGINE_GATES",
            "Present as scorable canonical yearly draw-result truth.",
        )
    if has_reference:
        return (
            f"MODEL_WORKBOOK_{year}_PERMITS_{year + 1}_MODEL",
            "REFERENCE_ONLY_REVIEW",
            "Present in canonical yearly truth but not as a scorable point-level row.",
        )
    if draw_pdf_sources:
        return (
            "DRAW_RESULT_PDF_ONLY_REVIEW",
            "DRAW_RESULT_SOURCE_REVIEW_NOT_IN_CANONICAL",
            f"Hunt code appears in {year} draw-result PDFs but not in canonical yearly truth.",
        )
    if regulation_sources:
        return (
            "REGULATION_PDF_ONLY_REVIEW",
            "REGULATION_SOURCE_REVIEW_NOT_IN_CANONICAL",
            f"Hunt code appears in {year} regulation/guidebook PDFs but not in canonical yearly truth.",
        )
    if db_rows:
        return (
            "DATABASE_NONSCORABLE_REFERENCE_APPENDIX",
            "SUPPORT_ONLY_REVIEW",
            "Hunt code appears only in DATABASE reference fields for this year; retain as non-scorable appendix unless confirmed by next-year canonical truth.",
        )
    if long_rows:
        return (
            "LONG_FILE_REFERENCE",
            "SUPPORT_ONLY_REVIEW",
            "Hunt code appears in draw_results_long for this year but not in canonical/PDF extraction.",
        )
    return ("UNCLASSIFIED_REVIEW", "NEEDS_REVIEW", "No source bucket could be assigned.")


def build_audit(
    year: int,
    out_dir: Path,
    exclude_prefixes: set[str] | None = None,
    pdf_source_scope: str = "all",
) -> dict[str, Any]:
    exclude_prefixes = exclude_prefixes or set()
    pdf_root = REPO / "pipeline" / "RAW" / "hunt_unit_database" / str(year) / "pdf"
    regulation_dirs = [
        pdf_root / "regulations",
        pdf_root / "regulation",
        pdf_root / "Rules Regulations",
        pdf_root / "Rules Regs",
    ]
    draw_pdf_dirs = [pdf_root / "draw results", pdf_root / "draw_results", pdf_root / "draw_odds"]
    if pdf_root.exists():
        draw_pdf_dirs.extend(
            sorted(path for path in pdf_root.iterdir() if path.is_dir() and "draw" in path.name.lower() and "result" in path.name.lower())
        )
    pdfs: list[Path] = []
    if pdf_source_scope in {"all", "regulation-only"}:
        for regulation_dir in regulation_dirs:
            if regulation_dir.exists():
                pdfs.extend(sorted(regulation_dir.glob("*.pdf")))
    if pdf_source_scope in {"all", "draw-odds-only"}:
        for draw_pdf_dir in draw_pdf_dirs:
            if draw_pdf_dir.exists():
                pdfs.extend(sorted(draw_pdf_dir.glob("*.pdf")))
    pdfs, duplicate_pdfs = dedupe_pdf_paths(pdfs)

    evidence: list[dict[str, Any]] = []
    pdf_inventory: list[dict[str, Any]] = []
    for pdf in pdfs:
        pdf_evidence, pdf_summary = extract_pdf_codes(pdf)
        evidence.extend(pdf_evidence)
        pdf_inventory.append(pdf_summary)

    evidence_by_code: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        evidence_by_code[norm_code(row.get("hunt_code"))].append(row)

    canonical_by_code = group_by_code(load_canonical_rows(year))
    long_by_code = group_by_code(load_long_rows(year))
    db_by_code = group_by_code(database_support_rows(year))
    locked_2026 = locked_2026_rows()

    raw_all_codes = sorted(set(evidence_by_code) | set(canonical_by_code) | set(long_by_code) | set(db_by_code))
    excluded_codes = [
        code
        for code in raw_all_codes
        if any(code.startswith(prefix) for prefix in exclude_prefixes)
    ]
    all_codes = [code for code in raw_all_codes if code not in set(excluded_codes)]
    rows: list[dict[str, Any]] = []
    for code in all_codes:
        code_evidence = evidence_by_code.get(code, [])
        regulation_sources = {
            clean(row.get("source_file"))
            for row in code_evidence
            if clean(row.get("source_role")).startswith("REGULATION")
        }
        draw_pdf_sources = {
            clean(row.get("source_file"))
            for row in code_evidence
            if clean(row.get("source_role")) == "DRAW_RESULT_PDF"
        }
        permit_quota_sources = {
            clean(row.get("source_file"))
            for row in code_evidence
            if clean(row.get("source_role")) == "PERMIT_QUOTA_PDF"
        }
        canon = canonical_by_code.get(code, [])
        db_rows = db_by_code.get(code, [])
        long_rows = long_by_code.get(code, [])
        locked = locked_2026.get(code, {})
        primary_bucket, scoring_bucket, note = classify(
            year,
            code,
            canon,
            regulation_sources | permit_quota_sources,
            draw_pdf_sources,
            db_rows,
            long_rows,
        )
        if permit_quota_sources and not draw_pdf_sources and not canon and primary_bucket == "REGULATION_PDF_ONLY_REVIEW":
            primary_bucket = "PERMIT_QUOTA_PDF_ONLY_REVIEW"
            scoring_bucket = "PERMIT_QUOTA_SOURCE_REVIEW_NOT_IN_CANONICAL"
            note = f"Hunt code appears in {year} permit-quota PDFs but not in canonical yearly truth."
        boundary_id = (
            first_nonblank(canon, ["boundary_id"])
            or first_nonblank(db_rows, [f"boundary_id_{year}", "boundary_id"])
            or first_nonblank(long_rows, ["boundary_id"])
            or clean(locked.get("boundary_id"))
        )
        boundary_source = ""
        if first_nonblank(canon, ["boundary_id"]):
            boundary_source = "canonical_yearly.boundary_id"
        elif first_nonblank(db_rows, [f"boundary_id_{year}", "boundary_id"]):
            boundary_source = "DATABASE.boundary_id"
        elif first_nonblank(long_rows, ["boundary_id"]):
            boundary_source = "draw_results_long.boundary_id"
        elif clean(locked.get("boundary_id")):
            boundary_source = "LOCKED_2026.boundary_id_reference"
        rows.append(
            {
                "hunt_code": code,
                "boundary_id": boundary_id,
                "boundary_id_source": boundary_source,
                "primary_universe_bucket": primary_bucket,
                "scoring_bucket": scoring_bucket,
                "hunt_name": first_nonblank(canon, ["hunt_name", "raw_hunt_name", "unit"])
                or first_nonblank(db_rows, [f"hunt_name_{year}", "hunt_name"])
                or first_nonblank(long_rows, ["hunt_name", "raw_hunt_name", "unit"])
                or clean(locked.get("hunt_name")),
                "species": first_nonblank(canon, ["species"])
                or first_nonblank(db_rows, ["species"])
                or first_nonblank(long_rows, ["species"])
                or clean(locked.get("species")),
                "sex_type": first_nonblank(canon, ["sex_type", "sex"])
                or first_nonblank(db_rows, ["sex_type"])
                or first_nonblank(long_rows, ["sex_type", "sex"])
                or clean(locked.get("sex_type")),
                "hunt_type": first_nonblank(canon, ["hunt_type"])
                or first_nonblank(db_rows, ["hunt_type"])
                or first_nonblank(long_rows, ["hunt_type"])
                or clean(locked.get("hunt_type")),
                "weapon": first_nonblank(canon, ["weapon"])
                or first_nonblank(db_rows, ["weapon"])
                or first_nonblank(long_rows, ["weapon"])
                or clean(locked.get("weapon")),
                "prefix": re.match(r"^[A-Z]+", code).group(0) if re.match(r"^[A-Z]+", code) else "",
                "present_regulation_pdf": "YES" if regulation_sources else "NO",
                "present_draw_result_pdf": "YES" if draw_pdf_sources else "NO",
                "present_canonical_yearly": "YES" if canon else "NO",
                "present_database_year_support": "YES" if db_rows else "NO",
                "present_long_file": "YES" if long_rows else "NO",
                "present_locked_2026_reference": "YES" if locked else "NO",
                "canonical_row_count": len(canon),
                "canonical_scorable_row_count": sum(1 for row in canon if record_type(row) in SCORABLE_RECORD_TYPES),
                "pdf_evidence_row_count": len(code_evidence),
                "regulation_pdf_sources": ";".join(sorted(regulation_sources)),
                "permit_quota_pdf_sources": ";".join(sorted(permit_quota_sources)),
                "draw_result_pdf_sources": ";".join(sorted(draw_pdf_sources)),
                "audit_note": note,
            }
        )

    fields = [
        "hunt_code",
        "boundary_id",
        "boundary_id_source",
        "primary_universe_bucket",
        "scoring_bucket",
        "hunt_name",
        "species",
        "sex_type",
        "hunt_type",
        "weapon",
        "prefix",
        "present_regulation_pdf",
        "present_draw_result_pdf",
        "present_canonical_yearly",
        "present_database_year_support",
        "present_long_file",
        "present_locked_2026_reference",
        "canonical_row_count",
        "canonical_scorable_row_count",
        "pdf_evidence_row_count",
        "regulation_pdf_sources",
        "permit_quota_pdf_sources",
        "draw_result_pdf_sources",
        "audit_note",
    ]
    write_csv(out_dir / f"{year}_HUNT_CODE_UNIVERSE_AUDIT.csv", rows, fields)
    write_csv(out_dir / f"{year}_PDF_HUNT_CODE_EVIDENCE.csv", evidence, ["hunt_code", "source_role", "source_file", "pdf_page", "line_number", "line_text"])
    write_csv(
        out_dir / f"{year}_SOURCE_PDF_INVENTORY.csv",
        pdf_inventory,
        ["source_role", "source_file", "bytes", "sha256", "page_count", "status", "error", "unique_hunt_codes", "evidence_rows"],
    )
    write_csv(
        out_dir / f"{year}_REVIEW_CODES.csv",
        [row for row in rows if "REVIEW" in clean(row.get("scoring_bucket"))],
        fields,
    )
    write_csv(
        out_dir / f"{year}_MODEL_SCORABLE_CODES.csv",
        [row for row in rows if row.get("scoring_bucket") == "CANDIDATE_MODEL_SCORABLE_REQUIRES_ENGINE_GATES"],
        fields,
    )

    primary_counts = Counter(row["primary_universe_bucket"] for row in rows)
    scoring_counts = Counter(row["scoring_bucket"] for row in rows)
    prefix_counts = Counter(row["prefix"] for row in rows)
    source_counts = {
        "regulation_pdf_codes": sum(1 for row in rows if row["present_regulation_pdf"] == "YES"),
        "draw_result_pdf_codes": sum(1 for row in rows if row["present_draw_result_pdf"] == "YES"),
        "permit_quota_pdf_codes": sum(1 for row in rows if clean(row.get("permit_quota_pdf_sources"))),
        "canonical_yearly_codes": sum(1 for row in rows if row["present_canonical_yearly"] == "YES"),
        "database_year_support_codes": sum(1 for row in rows if row["present_database_year_support"] == "YES"),
        "long_file_codes": sum(1 for row in rows if row["present_long_file"] == "YES"),
        "codes_with_boundary_id": sum(1 for row in rows if clean(row["boundary_id"])),
    }
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "year": year,
        "model_target_year": year + 1,
        "audit_dir": str(out_dir),
        "total_union_hunt_codes": len(rows),
        "primary_universe_bucket_counts": dict(sorted(primary_counts.items())),
        "scoring_bucket_counts": dict(sorted(scoring_counts.items())),
        "prefix_counts": dict(sorted(prefix_counts.items())),
        "source_counts": source_counts,
        "pdf_file_count": len(pdf_inventory),
        "pdf_source_scope": pdf_source_scope,
        "duplicate_pdf_count": len(duplicate_pdfs),
        "duplicate_pdfs": duplicate_pdfs,
        "excluded_prefixes": sorted(exclude_prefixes),
        "excluded_code_count": len(excluded_codes),
        "excluded_codes": excluded_codes,
        "pdf_inventory_errors": [row for row in pdf_inventory if row.get("status") != "OK"],
        "outputs": [
            f"{year}_HUNT_CODE_UNIVERSE_AUDIT.csv",
            f"{year}_PDF_HUNT_CODE_EVIDENCE.csv",
            f"{year}_SOURCE_PDF_INVENTORY.csv",
            f"{year}_REVIEW_CODES.csv",
            f"{year}_MODEL_SCORABLE_CODES.csv",
            f"{year}_HUNT_CODE_UNIVERSE_SUMMARY.json",
            f"{year}_HUNT_CODE_UNIVERSE_SUMMARY.md",
        ],
    }
    (out_dir / f"{year}_HUNT_CODE_UNIVERSE_SUMMARY.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    lines = [
        f"# {year} Hunt-Code Universe Audit",
        "",
        f"Generated: {summary['generated_at']}",
        f"Model target year: `{year + 1}`",
        "",
        "## Result",
        "",
        f"- Total union hunt codes: `{len(rows)}`",
        f"- PDF files audited: `{len(pdf_inventory)}`",
        f"- PDF source scope: `{pdf_source_scope}`",
        f"- Duplicate PDFs skipped: `{len(duplicate_pdfs)}`",
        f"- Excluded prefixes: `{', '.join(sorted(exclude_prefixes)) if exclude_prefixes else 'none'}`",
        f"- Excluded codes: `{len(excluded_codes)}`",
        f"- PDF inventory errors: `{len(summary['pdf_inventory_errors'])}`",
        "",
        "## Source Counts",
        "",
    ]
    for key, value in source_counts.items():
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Primary Buckets", ""])
    for key, value in sorted(primary_counts.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Scoring Buckets", ""])
    for key, value in sorted(scoring_counts.items()):
        lines.append(f"- {key}: `{value}`")
    lines.extend(["", "## Notes", ""])
    lines.append("This is an audit package, not a locked final universe. It does not mutate source truth or runtime outputs.")
    lines.append("Regulation PDF extraction is code-presence evidence; final locking still requires review of PDF table context for review buckets.")
    (out_dir / f"{year}_HUNT_CODE_UNIVERSE_SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit a hunt-code universe for one permit year.")
    parser.add_argument("--year", type=int, required=True)
    parser.add_argument("--output-root", type=Path, default=REPO / "audits" / "hunt_code_universe_truth")
    parser.add_argument("--exclude-prefix", action="append", default=[], help="Exclude hunt-code prefix from the universe.")
    parser.add_argument(
        "--pdf-source-scope",
        choices=["all", "draw-odds-only", "regulation-only"],
        default="all",
        help="Limit which local PDF source folders are audited.",
    )
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = args.output_root / str(args.year) / stamp
    summary = build_audit(
        args.year,
        out_dir,
        {clean(prefix).upper() for prefix in args.exclude_prefix if clean(prefix)},
        args.pdf_source_scope,
    )
    print(f"AUDIT_DIR: {out_dir}")
    print(f"TOTAL_UNION_HUNT_CODES: {summary['total_union_hunt_codes']}")
    print(f"SOURCE_COUNTS: {json.dumps(summary['source_counts'], sort_keys=True)}")
    print(f"SCORING_BUCKET_COUNTS: {json.dumps(summary['scoring_bucket_counts'], sort_keys=True)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
