from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_DIR = REPO / "audits" / f"find_2020_conservation_pdf_{STAMP}"

SEARCH_ROOTS = [
    REPO / "pipeline" / "RAW" / "hunt_unit_database",
    REPO / "pipeline" / "RAW",
    REPO / "pipeline" / "manifests",
    REPO / "processed_data",
    REPO / "processed_data" / "hard_data_exports",
    REPO / "canonical",
    REPO / "audits",
    REPO / "data_model",
    REPO / "data_truth",
]

MANIFEST_FILES = [
    REPO / "pipeline" / "manifests" / "pdf_misplacement_audit_20260506.csv",
    REPO / "pipeline" / "manifests" / "pdf_misplacement_doc_type_fix_execution_20260506.csv",
    REPO / "pipeline" / "manifests" / "pdf_misplacement_hashsafe_audit_20260506.csv",
    REPO / "pipeline" / "manifests" / "pdf_model_ready_manifest_with_target_year_v3.csv",
    REPO / "pipeline" / "manifests" / "staging_ingest_plan_20260506.csv",
    REPO / "pipeline" / "manifests" / "staging_ingest_execution_20260506.csv",
    REPO / "processed_data" / "hard_data_exports" / "hard_copy_pdf_manifest.web.json",
    REPO / "canonical" / "hard-copies-2026.json",
    REPO / "data_model" / "quality" / "promoted_draw_sources.csv",
    REPO / "data_model" / "quality" / "promoted_source_year_map.csv",
]

SCRIPT_FILES = [
    REPO / "scripts" / "reconcile-expo-conservation-rows.py",
    REPO / "scripts" / "build-conservation-area-crosswalk-2026.js",
    REPO / "scripts" / "match-conservation-permits-to-database-2026.js",
    REPO / "scripts" / "align_conservation_permits_with_database.py",
    REPO / "scripts" / "apply_conservation_codes_truth_to_pdf_rows.py",
    REPO / "scripts" / "audit-unresolved-2026-vs-database-conservation.py",
    REPO / "scripts" / "backfill-conservation-boundary-ids-from-database-2025-27.js",
]

USER_PROVIDED_PDF_CANDIDATES = [
    Path(r"B:\CLOUD DRIVES\GOOGLE DRIVE\Documents\2019_conservation_permits.pdf"),
    Path(r"B:\CLOUD DRIVES\GOOGLE DRIVE\Documents\2022-24_conservation_permits.pdf"),
]

TERMS = [
    "Conservation",
    "conservation",
    "conservation permit",
    "Conservation Permit",
    "2020",
    "2019",
    "2018",
    "2017",
    "2020-22",
    "2019-21",
    "2018-20",
    "2017-19",
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def clean(value: object) -> str:
    return str(value if value is not None else "").strip()


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def infer_years(text: str) -> tuple[str, str, str]:
    years = [int(y) for y in re.findall(r"20\d{2}", text)]
    years += [int(y) for y in re.findall(r"\b(201[0-9])\b", text)]
    years = sorted(set(y for y in years if 2010 <= y <= 2030))
    if not years:
        return "", "", ""
    return str(years[0]), str(years[-1]), "|".join(str(y) for y in years)


def skip_path(path: Path) -> bool:
    lower = str(path).lower()
    return "\\pytest_deps\\" in lower or "\\__pycache__\\" in lower or "\\predictions\\" in lower


def iter_files(roots: list[Path]) -> list[Path]:
    found: dict[str, Path] = {}
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            if not skip_path(root):
                found[str(root).lower()] = root
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() == ".pdf" and not skip_path(path):
                found[str(path).lower()] = path
    for path in USER_PROVIDED_PDF_CANDIDATES:
        if path.exists() and not skip_path(path):
            found[str(path).lower()] = path
    return sorted(found.values(), key=lambda p: str(p).lower())


def candidate_reasons(path: Path, manifest_refs: set[str], script_refs: set[str]) -> list[str]:
    hay = str(path).lower()
    reasons = []
    if "conservation" in path.name.lower():
        reasons.append("FILENAME_CONTAINS_CONSERVATION")
    if "permit" in path.name.lower():
        reasons.append("FILENAME_CONTAINS_PERMIT")
    if "conservation" in hay:
        reasons.append("PATH_CONTAINS_CONSERVATION")
    if str(path).lower() in manifest_refs or rel(path).lower() in manifest_refs:
        reasons.append("MANIFEST_REFERENCED")
    if str(path).lower() in script_refs or rel(path).lower() in script_refs:
        reasons.append("SCRIPT_REFERENCED")
    return reasons


def read_text(path: Path, max_bytes: int = 2_000_000) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")[:max_bytes]
    except Exception:
        return ""


def extract_paths_and_urls(text: str) -> tuple[str, str]:
    path_match = re.search(r"([A-Za-z]:\\[^,\"]+|(?:pipeline|data_truth|processed_data|canonical|audits|tmp)[^,\"]+)", text)
    url_match = re.search(r"https?://[^\s,\"')]+", text)
    return (path_match.group(1) if path_match else "", url_match.group(0) if url_match else "")


def manifest_hits(files: list[Path]) -> list[dict[str, object]]:
    hits = []
    focused = sorted(set(MANIFEST_FILES + SCRIPT_FILES))
    for path in focused:
        if not path.exists() or skip_path(path):
            continue
        text = read_text(path)
        if not text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, start=1):
            low = line.lower()
            if "conservation" not in low:
                continue
            if not any(term.lower() in low for term in TERMS):
                continue
            referenced_path, referenced_url = extract_paths_and_urls(line)
            start, end, years = infer_years(line)
            confidence = "HIGH" if "permit" in low and (start or referenced_url or referenced_path) else "MEDIUM"
            hits.append(
                {
                    "manifest_file": rel(path),
                    "line_or_record_number": i,
                    "matched_text": line[:500],
                    "referenced_path": referenced_path,
                    "referenced_url": referenced_url,
                    "inferred_year_start": start,
                    "inferred_year_end": end,
                    "confidence": confidence,
                    "notes": f"years={years}" if years else "",
                }
            )
    return hits


def referenced_paths_from_hits(hits: list[dict[str, object]]) -> set[str]:
    refs = set()
    for hit in hits:
        for field in ("referenced_path",):
            value = clean(hit.get(field))
            if not value:
                continue
            refs.add(value.lower())
            p = (REPO / value).resolve() if not re.match(r"^[A-Za-z]:\\", value) else Path(value)
            refs.add(str(p).lower())
            try:
                refs.add(str(p.relative_to(REPO)).lower())
            except ValueError:
                pass
    return refs


def pdf_text_confirmation(path: Path) -> dict[str, object]:
    try:
        import pdfplumber
    except Exception as exc:
        return {
            "candidate_path": rel(path),
            "file_name": path.name,
            "page_count": "",
            "text_search_status": "REVIEW_REQUIRED_TEXT_UNAVAILABLE",
            "matched_terms": "",
            "first_matching_page": "",
            "evidence_excerpt_short": "",
            "inferred_document_title": "",
            "inferred_year_start": "",
            "inferred_year_end": "",
            "official_source_confidence": "REVIEW_REQUIRED",
            "notes": f"pdfplumber unavailable: {exc}",
        }
    try:
        with pdfplumber.open(path) as pdf:
            page_count = len(pdf.pages)
            all_text = []
            first_page = ""
            first_excerpt = ""
            matched_terms: set[str] = set()
            for index, page in enumerate(pdf.pages[:5], start=1):
                text = page.extract_text() or ""
                all_text.append(text)
                low = text.lower()
                page_matches = [term for term in TERMS if term.lower() in low]
                if page_matches:
                    matched_terms.update(page_matches)
                    if not first_page:
                        first_page = str(index)
                        compact = re.sub(r"\s+", " ", text).strip()
                        first_excerpt = compact[:300]
            joined = "\n".join(all_text)
            start, end, _ = infer_years(joined + " " + path.name)
            title = ""
            for line in joined.splitlines():
                if "conservation" in line.lower() and "permit" in line.lower():
                    title = re.sub(r"\s+", " ", line).strip()[:160]
                    break
            low_joined = joined.lower()
            is_conservation = "conservation" in low_joined and "permit" in low_joined
            is_dwr = "utah division of wildlife resources" in low_joined or "dwr" in low_joined
            year_ok = any(y in {2017, 2018, 2019, 2020} for y in [int(x) for x in re.findall(r"20\d{2}|201[0-9]", joined + path.name)])
            if is_conservation and year_ok:
                status = "CONFIRMED_CONSERVATION_PERMIT_PDF" if is_dwr else "LIKELY_CONSERVATION_PERMIT_PDF"
            elif is_conservation:
                status = "REVIEW_REQUIRED_YEAR_AMBIGUOUS"
            elif joined.strip():
                status = "REJECT_NOT_CONSERVATION_PERMIT"
            else:
                status = "REVIEW_REQUIRED_TEXT_UNAVAILABLE"
            confidence = "CONFIRMED" if status == "CONFIRMED_CONSERVATION_PERMIT_PDF" else ("LIKELY" if status == "LIKELY_CONSERVATION_PERMIT_PDF" else "REVIEW_REQUIRED")
            return {
                "candidate_path": rel(path),
                "file_name": path.name,
                "page_count": page_count,
                "text_search_status": status,
                "matched_terms": "|".join(sorted(matched_terms)),
                "first_matching_page": first_page,
                "evidence_excerpt_short": first_excerpt,
                "inferred_document_title": title,
                "inferred_year_start": start,
                "inferred_year_end": end,
                "official_source_confidence": confidence,
                "notes": "",
            }
    except Exception as exc:
        return {
            "candidate_path": rel(path),
            "file_name": path.name,
            "page_count": "",
            "text_search_status": "REVIEW_REQUIRED_TEXT_UNAVAILABLE",
            "matched_terms": "",
            "first_matching_page": "",
            "evidence_excerpt_short": "",
            "inferred_document_title": "",
            "inferred_year_start": "",
            "inferred_year_end": "",
            "official_source_confidence": "REVIEW_REQUIRED",
            "notes": str(exc),
        }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    all_files = iter_files(SEARCH_ROOTS)
    hits = manifest_hits(all_files)
    manifest_refs = referenced_paths_from_hits(hits)
    script_hits = [hit for hit in hits if rel(REPO / clean(hit["manifest_file"])) in {rel(p) for p in SCRIPT_FILES}]
    script_refs = referenced_paths_from_hits(script_hits)

    pdfs = [p for p in all_files if p.suffix.lower() == ".pdf"]
    candidates = []
    candidate_paths = []
    for path in pdfs:
        reasons = candidate_reasons(path, manifest_refs, script_refs)
        filename_years = infer_years(path.name)[2]
        year_values = [int(y) for y in re.findall(r"20\d{2}|201[0-9]", str(path))]
        has_2020_or_earlier = any(2010 <= y <= 2020 for y in year_values)
        if "conservation" in str(path).lower() and ("permit" in path.name.lower() or has_2020_or_earlier):
            if not reasons:
                reasons = ["PATH_CONTAINS_CONSERVATION"]
            start, end, _ = infer_years(str(path))
            status = "CANDIDATE_2020_OR_EARLIER" if has_2020_or_earlier else "CANDIDATE_AFTER_2020_REFERENCE_ONLY"
            candidates.append(
                {
                    "candidate_path": rel(path),
                    "file_name": path.name,
                    "extension": path.suffix,
                    "size_bytes": path.stat().st_size,
                    "modified_time": path.stat().st_mtime,
                    "inferred_year_start": start,
                    "inferred_year_end": end,
                    "filename_years": filename_years,
                    "candidate_reason": "|".join(sorted(set(reasons))),
                    "status": status,
                    "notes": "",
                }
            )
            candidate_paths.append(path)

    confirmations = [pdf_text_confirmation(path) for path in candidate_paths]
    for candidate in candidates:
        match = next((row for row in confirmations if row["candidate_path"] == candidate["candidate_path"]), None)
        if match and match["text_search_status"] in {"CONFIRMED_CONSERVATION_PERMIT_PDF", "LIKELY_CONSERVATION_PERMIT_PDF"}:
            reasons = set(clean(candidate["candidate_reason"]).split("|")) if candidate["candidate_reason"] else set()
            reasons.add("PDF_TEXT_CONFIRMED")
            candidate["candidate_reason"] = "|".join(sorted(reasons))

    p01 = OUT_DIR / "01_CONSERVATION_PDF_FILESYSTEM_CANDIDATES.csv"
    p02 = OUT_DIR / "02_CONSERVATION_PDF_MANIFEST_HITS.csv"
    p03 = OUT_DIR / "03_CONSERVATION_PDF_TEXT_CONFIRMATION.csv"
    write_csv(p01, candidates, ["candidate_path", "file_name", "extension", "size_bytes", "modified_time", "inferred_year_start", "inferred_year_end", "filename_years", "candidate_reason", "status", "notes"])
    write_csv(p02, hits, ["manifest_file", "line_or_record_number", "matched_text", "referenced_path", "referenced_url", "inferred_year_start", "inferred_year_end", "confidence", "notes"])
    write_csv(p03, confirmations, ["candidate_path", "file_name", "page_count", "text_search_status", "matched_terms", "first_matching_page", "evidence_excerpt_short", "inferred_document_title", "inferred_year_start", "inferred_year_end", "official_source_confidence", "notes"])

    best = None
    for row in confirmations:
        path = REPO / row["candidate_path"]
        year_values = [int(y) for y in re.findall(r"20\d{2}|201[0-9]", str(path) + " " + clean(row.get("inferred_year_start")) + " " + clean(row.get("inferred_year_end")))]
        if row["text_search_status"] == "CONFIRMED_CONSERVATION_PERMIT_PDF" and any(2010 <= y <= 2020 for y in year_values):
            best = row
            break

    if best:
        best_path = str(REPO / clean(best["candidate_path"]))
        confidence = "CONFIRMED"
        next_action = "REVIEW_BEST_CONSERVATION_PDF_CANDIDATE"
    else:
        best_path = "NONE_FOUND"
        confidence = "NONE_FOUND"
        next_action = "SEARCH_EXTERNAL_DWR_ARCHIVE"

    p04 = OUT_DIR / "04_BEST_2020_OR_EARLIER_CONSERVATION_PDF_SELECTION.md"
    p05 = OUT_DIR / "05_CONSERVATION_PDF_PROMOTION_PLAN.md"
    p06 = OUT_DIR / "06_FIND_2020_CONSERVATION_PDF_REPORT.md"

    local_2020 = [row for row in confirmations if row["text_search_status"] == "CONFIRMED_CONSERVATION_PERMIT_PDF" and any(2010 <= int(y) <= 2020 for y in re.findall(r"20\d{2}|201[0-9]", row["candidate_path"] + " " + clean(row.get("inferred_year_start")) + " " + clean(row.get("inferred_year_end"))))]
    best_rel = clean(best["candidate_path"]) if best else "NONE_FOUND"
    sha = sha256_file(REPO / best_rel) if best else ""
    p04.write_text(
        "\n".join(
            [
                "# Best 2020 Or Earlier Conservation PDF Selection",
                "",
                f"1. Is a 2020-or-earlier Conservation Permit PDF present in the repo or staging? {'YES' if best else 'NO'}",
                f"2. Best candidate path: {best_path}",
                f"3. Years covered: {clean(best.get('inferred_year_start')) + '-' + clean(best.get('inferred_year_end')) if best else 'NONE_FOUND'}",
                f"4. Is it official DWR/source material? {'YES' if confidence == 'CONFIRMED' else 'NOT CONFIRMED LOCALLY'}",
                f"5. Does filename or PDF text prove it? {'YES' if best else 'NO LOCAL 2020-OR-EARLIER PDF CONFIRMED'}",
                f"6. Is it already referenced by a manifest? {'REVIEW_MANIFEST_HITS' if hits else 'NO'}",
                "7. Should it be copied/promoted later into a canonical raw folder? Only in a separate promotion mission after review.",
                "8. Recommended destination if promoted later: pipeline\\RAW\\hunt_unit_database\\<source_year>\\pdf\\conservation_permits\\<filename>.pdf",
                "9. What should not be done yet? Do not move PDFs, patch DATABASE.csv, patch draw_results_long.csv, patch canonical yearly files, commit, push, or use prediction outputs.",
                "",
                f"BEST_CANDIDATE_SHA256={sha}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    p05.write_text(
        "\n".join(
            [
                "# Conservation PDF Promotion Plan",
                "",
                f"source_candidate_path={best_path}",
                "recommended_destination_path=pipeline\\RAW\\hunt_unit_database\\<source_year>\\pdf\\conservation_permits\\<filename>.pdf",
                "backup_manifest_required=TRUE",
                "sha256_required=TRUE",
                "source_url_required_if_available=TRUE",
                "validation_required_before_promotion=PDF text must confirm Conservation Permit list/report and year coverage.",
                "PDF_NOT_MOVED_OR_PROMOTED_IN_THIS_MISSION=TRUE",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    p06.write_text(
        "\n".join(
            [
                "# Find 2020 Conservation PDF Report",
                "",
                f"report_timestamp={STAMP}",
                f"candidates_found={len(candidates)}",
                f"manifest_hits={len(hits)}",
                f"pdf_text_confirmations={len(confirmations)}",
                f"confirmed_2020_or_earlier_candidates={len(local_2020)}",
                f"best_candidate={best_path}",
                f"confidence={confidence}",
                "",
                "## Conservation Contract Note",
                "",
                "Conservation permits are allocated benefit-auction permit sources, not normal draw_pool rows. Field mapping should be confirmed against the hunt selection matrix and associated Conservation Permit PDF before any source patch.",
                "",
                "## Source Modification Statement",
                "",
                "SOURCE_FILES_MODIFIED=FALSE",
                "DATABASE_PATCHED=FALSE",
                "DRAW_RESULTS_LONG_PATCHED=FALSE",
                "CANONICAL_YEARLY_PATCHED=FALSE",
                "PREDICTION_OUTPUTS_USED=FALSE",
                "",
                "## Next Action",
                "",
                f"NEXT_ACTION={next_action}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    print(f"FIND_2020_CONSERVATION_PDF_OUTPUT_DIR={OUT_DIR}")
    print(f"FILESYSTEM_CANDIDATES={p01}")
    print(f"MANIFEST_HITS={p02}")
    print(f"PDF_TEXT_CONFIRMATION={p03}")
    print(f"BEST_SOURCE_SELECTION={p04}")
    print(f"PROMOTION_PLAN={p05}")
    print(f"FIND_REPORT={p06}")
    print(f"BEST_2020_OR_EARLIER_CONSERVATION_PDF={best_path}")
    print(f"BEST_CANDIDATE_CONFIDENCE={confidence}")
    print("SOURCE_FILES_MODIFIED=FALSE")
    print(f"NEXT_ACTION={next_action}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
