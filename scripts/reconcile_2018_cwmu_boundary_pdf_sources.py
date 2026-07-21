from __future__ import annotations

import csv
import hashlib
import os
import re
from datetime import datetime
from pathlib import Path

import pdfplumber


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
PDF_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "draw_odds_deep_pull_20260721_031919" / "wildlife_pdfs"
PDF_SEARCH_DIRS = [
    PDF_ROOT / "big_game" / "2018",
    PDF_ROOT / "big_game_antlerless" / "2018",
]
BRIDGE_AUDIT = REPO / "audits" / "2018_full_year_official_score_key_v2_bridge_20260721_134332" / "2018_CWMU_BLIND_BOUNDARY_ID_REPAIR_AUDIT.csv"
CANONICAL = REPO / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2018_for_2019_canonical_yearly_draw_results.csv"
AUDIT_DIR = Path(os.environ.get("PDF_RECONCILIATION_AUDIT_DIR", "")) if os.environ.get("PDF_RECONCILIATION_AUDIT_DIR") else REPO / "audits" / "2018_full_year_official_score_key_v2_bridge_20260721_134332"

EXTRA_TARGETS = [
    {
        "hunt_code": "MB6205",
        "hunt_name": "Coyote Little Pole",
        "boundary_id": "",
        "boundary_id_source": "USER_PROVIDED_PRINTED_PAGE_412_EVIDENCE_TARGET",
        "notes": "User pasted 2018 Draw 5 printed page 412 evidence.",
    }
]


def clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in rows)


def hunt_line(text: str) -> tuple[str, str]:
    page_match = re.search(r"\bPage\s+(\d+)\b", text)
    printed_page = page_match.group(1) if page_match else ""
    for line in text.splitlines():
        if line.startswith("Hunt:"):
            line_page_match = re.search(r"\bPage\s+(\d+)\b", line)
            return line.strip(), line_page_match.group(1) if line_page_match else printed_page
    return "", printed_page


def context_snippet(text: str, term: str) -> str:
    compact = re.sub(r"\s+", " ", text)
    pos = compact.lower().find(term.lower())
    if pos < 0:
        return compact[:260]
    start = max(0, pos - 120)
    end = min(len(compact), pos + len(term) + 160)
    return compact[start:end]


def bridge_targets() -> list[dict[str, str]]:
    _, rows = read_csv(BRIDGE_AUDIT)
    wanted_codes = {"DB1220", "DB1247", "EA1199", "EB3605", "MB6204", "MB6255"}
    targets: dict[str, dict[str, str]] = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code not in wanted_codes or code in targets:
            continue
        targets[code] = {
            "hunt_code": code,
            "hunt_name": clean(row.get("hunt_name")),
            "boundary_id": clean(row.get("boundary_id")),
            "boundary_id_source": clean(row.get("boundary_id_source")),
            "notes": "Former CWMU blind boundary gap resolved in 2018 bridge audit.",
        }
    for row in EXTRA_TARGETS:
        targets[row["hunt_code"]] = row
    return list(targets.values())


def canonical_rows_by_code(codes: set[str]) -> dict[str, int]:
    _, rows = read_csv(CANONICAL)
    counts = {code: 0 for code in codes}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if code in counts and clean(row.get("cwmu_blind_embed_status")) == "EMBEDDED_FROM_LOCKED_BLIND_CWMU_TRUTH":
            counts[code] += 1
    return counts


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    targets = bridge_targets()
    code_set = {target["hunt_code"] for target in targets}
    canonical_counts = canonical_rows_by_code(code_set)

    target_terms: list[tuple[str, str, str]] = []
    for target in targets:
        if target["hunt_code"]:
            target_terms.append((target["hunt_code"], "hunt_code", target["hunt_code"]))
        if target["hunt_name"]:
            target_terms.append((target["hunt_code"], "hunt_name", target["hunt_name"]))

    pdfs = []
    for directory in PDF_SEARCH_DIRS:
        pdfs.extend(sorted(directory.glob("*.pdf")))
    pdf_inventory_rows = []
    hit_rows = []
    pdf_hash_cache: dict[Path, str] = {}

    for pdf in pdfs:
        rel = pdf.relative_to(REPO)
        try:
            file_hash = sha256(pdf)
            pdf_hash_cache[pdf] = file_hash
            with pdfplumber.open(str(pdf)) as doc:
                page_count = len(doc.pages)
                pdf_inventory_rows.append(
                    {
                        "pdf_path": str(rel),
                        "size_bytes": pdf.stat().st_size,
                        "sha256": file_hash,
                        "page_count": page_count,
                        "scan_status": "SCANNED",
                        "scan_error": "",
                    }
                )
                for page_index, page in enumerate(doc.pages, start=1):
                    text = page.extract_text() or ""
                    if not text:
                        continue
                    text_lower = text.lower()
                    line, printed_page = hunt_line(text)
                    for target_code, term_type, term in target_terms:
                        if term.lower() not in text_lower:
                            continue
                        target = next(item for item in targets if item["hunt_code"] == target_code)
                        hit_rows.append(
                            {
                                "hunt_code": target_code,
                                "hunt_name": target["hunt_name"],
                                "boundary_id": target["boundary_id"],
                                "boundary_id_source": target["boundary_id_source"],
                                "term_type": term_type,
                                "matched_term": term,
                                "pdf_path": str(rel),
                                "pdf_size_bytes": pdf.stat().st_size,
                                "pdf_sha256": file_hash,
                                "pdf_page_index_1based": page_index,
                                "printed_report_page": printed_page,
                                "hunt_line": line,
                                "context_snippet": context_snippet(text, term),
                                "evidence_status": "PDF_TEXT_HIT",
                            }
                        )
        except Exception as exc:
            pdf_inventory_rows.append(
                {
                    "pdf_path": str(rel),
                    "size_bytes": pdf.stat().st_size if pdf.exists() else "",
                    "sha256": pdf_hash_cache.get(pdf, ""),
                    "page_count": "",
                    "scan_status": "SCAN_FAILED",
                    "scan_error": str(exc),
                }
            )

    summary_rows = []
    for target in targets:
        code = target["hunt_code"]
        hits = [row for row in hit_rows if row["hunt_code"] == code]
        exact_code_hits = [row for row in hits if row["term_type"] == "hunt_code"]
        name_hits = [row for row in hits if row["term_type"] == "hunt_name"]
        printed_pages = sorted({clean(row["printed_report_page"]) for row in hits if clean(row["printed_report_page"])}, key=lambda value: int(value) if value.isdigit() else value)
        exact_code_printed_pages = sorted({clean(row["printed_report_page"]) for row in exact_code_hits if clean(row["printed_report_page"])}, key=lambda value: int(value) if value.isdigit() else value)
        name_match_printed_pages = sorted({clean(row["printed_report_page"]) for row in name_hits if clean(row["printed_report_page"])}, key=lambda value: int(value) if value.isdigit() else value)
        source_pdfs = sorted({row["pdf_path"] for row in hits})
        summary_rows.append(
            {
                "hunt_code": code,
                "hunt_name": target["hunt_name"],
                "boundary_id": target["boundary_id"],
                "boundary_id_source": target["boundary_id_source"],
                "canonical_embedded_cwmu_rows": canonical_counts.get(code, 0),
                "pdf_hit_count": len(hits),
                "exact_hunt_code_pdf_hit_count": len(exact_code_hits),
                "hunt_name_pdf_hit_count": len(name_hits),
                "printed_report_pages": ";".join(printed_pages),
                "exact_hunt_code_printed_pages": ";".join(exact_code_printed_pages),
                "hunt_name_match_printed_pages": ";".join(name_match_printed_pages),
                "source_pdf_count": len(source_pdfs),
                "source_pdfs": ";".join(source_pdfs),
                "reconciliation_status": "PDF_CONFIRMED_BY_EXACT_HUNT_CODE" if exact_code_hits else ("PDF_NAME_ONLY_REVIEW_REQUIRED" if name_hits else "PDF_EVIDENCE_NOT_FOUND"),
                "notes": target["notes"],
            }
        )

    hits_path = AUDIT_DIR / "2018_CWMU_BOUNDARY_SOURCE_PDF_RECONCILIATION_HITS.csv"
    summary_path = AUDIT_DIR / "2018_CWMU_BOUNDARY_SOURCE_PDF_RECONCILIATION_SUMMARY.csv"
    inventory_path = AUDIT_DIR / "2018_CWMU_BOUNDARY_SOURCE_PDF_RECONCILIATION_PDF_INVENTORY.csv"
    report_path = AUDIT_DIR / "2018_CWMU_BOUNDARY_SOURCE_PDF_RECONCILIATION_REPORT.md"

    write_csv(
        hits_path,
        hit_rows,
        [
            "hunt_code",
            "hunt_name",
            "boundary_id",
            "boundary_id_source",
            "term_type",
            "matched_term",
            "pdf_path",
            "pdf_size_bytes",
            "pdf_sha256",
            "pdf_page_index_1based",
            "printed_report_page",
            "hunt_line",
            "context_snippet",
            "evidence_status",
        ],
    )
    write_csv(
        summary_path,
        summary_rows,
        [
            "hunt_code",
            "hunt_name",
            "boundary_id",
            "boundary_id_source",
            "canonical_embedded_cwmu_rows",
            "pdf_hit_count",
            "exact_hunt_code_pdf_hit_count",
            "hunt_name_pdf_hit_count",
            "printed_report_pages",
            "exact_hunt_code_printed_pages",
            "hunt_name_match_printed_pages",
            "source_pdf_count",
            "source_pdfs",
            "reconciliation_status",
            "notes",
        ],
    )
    write_csv(
        inventory_path,
        pdf_inventory_rows,
        ["pdf_path", "size_bytes", "sha256", "page_count", "scan_status", "scan_error"],
    )

    exact_confirmed = sum(1 for row in summary_rows if row["reconciliation_status"] == "PDF_CONFIRMED_BY_EXACT_HUNT_CODE")
    name_only = sum(1 for row in summary_rows if row["reconciliation_status"] == "PDF_NAME_ONLY_REVIEW_REQUIRED")
    missing = sum(1 for row in summary_rows if row["reconciliation_status"] == "PDF_EVIDENCE_NOT_FOUND")
    failed_scans = sum(1 for row in pdf_inventory_rows if row["scan_status"] != "SCANNED")

    report = [
        "# 2018 CWMU Boundary Source PDF Reconciliation",
        "",
        f"SCAN_TIMESTAMP={stamp}",
        f"PDF_ROOT={PDF_ROOT}",
        f"BRIDGE_AUDIT={BRIDGE_AUDIT}",
        f"CANONICAL={CANONICAL}",
        "",
        "## Status",
        "",
        f"TARGET_HUNT_CODES={len(targets)}",
        f"PDFS_SCANNED={sum(1 for row in pdf_inventory_rows if row['scan_status'] == 'SCANNED')}",
        f"PDF_SCAN_FAILURES={failed_scans}",
        f"EXACT_HUNT_CODE_CONFIRMED={exact_confirmed}",
        f"NAME_ONLY_REVIEW_REQUIRED={name_only}",
        f"PDF_EVIDENCE_NOT_FOUND={missing}",
        "PREDICTION_OUTPUTS_READ=FALSE",
        "DATABASE_PATCHED=FALSE",
        "",
        "## Outputs",
        "",
        f"HITS={hits_path}",
        f"SUMMARY={summary_path}",
        f"PDF_INVENTORY={inventory_path}",
        "",
        "## Target Summary",
        "",
    ]
    for row in summary_rows:
        report.append(
            f"- {row['hunt_code']} {row['hunt_name']}: {row['reconciliation_status']}; "
            f"boundary_id={row['boundary_id']}; exact_code_pages={row['exact_hunt_code_printed_pages'] or 'NONE'}; "
            f"name_match_pages={row['hunt_name_match_printed_pages'] or 'NONE'}"
        )
    report_path.write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"PDF_ROOT={PDF_ROOT}")
    print(f"PDFS_SCANNED={sum(1 for row in pdf_inventory_rows if row['scan_status'] == 'SCANNED')}")
    print(f"PDF_SCAN_FAILURES={failed_scans}")
    print(f"TARGET_HUNT_CODES={len(targets)}")
    print(f"EXACT_HUNT_CODE_CONFIRMED={exact_confirmed}")
    print(f"NAME_ONLY_REVIEW_REQUIRED={name_only}")
    print(f"PDF_EVIDENCE_NOT_FOUND={missing}")
    print(f"PDF_RECONCILIATION_REPORT={report_path}")
    print(f"PDF_RECONCILIATION_SUMMARY={summary_path}")
    print(f"PDF_RECONCILIATION_HITS={hits_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
