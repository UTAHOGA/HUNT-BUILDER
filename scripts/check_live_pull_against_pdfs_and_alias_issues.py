#!/usr/bin/env python3
"""Cross-check live draw-odds pull against active PDFs and alias issue rows.

No source files are patched. The script writes a compact audit covering:
- live official PDF pull rows versus active normalized raw PDFs
- source-alias unresolved rows versus live pull and active PDFs
- source-alias truth-hash conflicts versus live pull, active PDFs, and truth mirrors
"""

from __future__ import annotations

import csv
import hashlib
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
RAW_ROOT = REPO / "pipeline" / "RAW" / "hunt_unit_database"
TRUTH_RAW_ROOT = REPO / "data_truth" / "draw_results_truth" / "raw_pdfs"
LIVE_ROOT = RAW_ROOT / "_staging" / "draw_odds_deep_pull_20260721_031919"
LIVE_MANIFEST = LIVE_ROOT / "DRAW_ODDS_DEEP_PULL_MANIFEST.csv"
ALIAS_ISSUE_ROOT = REPO / "audits" / "source_alias_path_repair" / "20260721_153359Z"
UNRESOLVED = ALIAS_ISSUE_ROOT / "unresolved.csv"
CONFLICTS = ALIAS_ISSUE_ROOT / "conflicts.csv"
AUDIT_ROOT = REPO / "audits"

SKIP_PARTS = {
    "_archive",
    "_quarantine",
    "_staging",
    "ARTIFACTS",
    "draw_odds_artifacts",
    "draw_odds_ignored",
    "backups",
    "backup",
    "__pycache__",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_csv(path: Path, rows: list[dict[str, object]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def parse_years(manifest: str) -> tuple[str, str]:
    match = re.search(r"(\d{4})_PERMITS=(\d{4})_MODEL", manifest)
    if not match:
        return "", ""
    return match.group(1), match.group(2)


def active_pdf_inventory(read_errors: list[dict[str, object]]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for path in RAW_ROOT.rglob("*.pdf"):
        rel = path.relative_to(RAW_ROOT)
        if any(part in SKIP_PARTS for part in rel.parts):
            continue
        parts = rel.parts
        if not parts or not parts[0].isdigit():
            continue
        if len(parts) < 4 or parts[1] != "pdf" or parts[2] not in {"draw_odds", "harvest_report", "regulations"}:
            continue
        doc_type = parts[2]
        try:
            digest = sha256(path)
        except OSError as exc:
            read_errors.append(
                {
                    "relative_path": path.relative_to(REPO).as_posix(),
                    "source_year": parts[0],
                    "doc_type": doc_type,
                    "file_name": path.name,
                    "size_bytes": path.stat().st_size if path.exists() else "",
                    "error": str(exc),
                }
            )
            continue
        rows.append(
            {
                "path": path,
                "relative_path": path.relative_to(REPO).as_posix(),
                "source_year": parts[0],
                "doc_type": doc_type,
                "file_name": path.name,
                "size_bytes": path.stat().st_size,
                "sha256": digest,
                "title_key": title_key(path.name),
            }
        )
    return rows


def title_key(value: str) -> str:
    text = Path(str(value)).name.upper()
    text = re.sub(r"\.PDF$", "", text)
    text = text.replace("O.I.L.", "OIL")
    text = text.replace("P.L.E.", "PLE")
    text = text.replace("L.E.", "LE")
    text = text.replace("G.S.", "GS")
    text = text.replace("D.H.", "DH")
    text = text.replace("MTN", "MOUNTAIN")
    text = text.replace("&", " AND ")
    text = text.replace("+", " PLUS ")
    text = re.sub(r"\d{4}_PERMITS=\d{4}_MODEL__", " ", text)
    text = re.sub(r"\d{4}_HARVEST_REPORT__", " ", text)
    text = re.sub(r"\d{4}_REGULATIONS__", " ", text)
    text = re.sub(r"(^|[^A-Z0-9])\d{2,4}([^A-Z0-9]|$)", " ", text)
    stop = {
        "DRAW",
        "DRAWS",
        "ODDS",
        "RESULT",
        "RESULTS",
        "REPORT",
        "REPORTS",
        "POINT",
        "POINTS",
        "SUMMARY",
        "PERMIT",
        "PERMITS",
        "MODEL",
        "BONUS",
        "PREFERENCE",
        "DRAWING",
    }
    tokens = [tok for tok in re.findall(r"[A-Z0-9]+", text) if tok not in stop]
    return "".join(tokens)


def rel_from_repo(value: str) -> Path:
    value = str(value or "").strip()
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO / value.replace("/", "\\")


def truth_path_for(source_year: str, target_year: str, rel: str) -> Path:
    return TRUTH_RAW_ROOT / f"{source_year}_PERMITS={target_year}_MODEL" / rel.replace("/", "\\")


def joined_paths(paths: list[dict[str, object]], limit: int = 8) -> str:
    values = [str(row["relative_path"]) for row in paths[:limit]]
    if len(paths) > limit:
        values.append(f"...plus {len(paths) - limit} more")
    return ";".join(values)


def main() -> int:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = AUDIT_ROOT / f"live_pull_pdf_alias_issue_check_{stamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdf_read_errors: list[dict[str, object]] = []
    active_pdfs = active_pdf_inventory(pdf_read_errors)
    active_by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    active_by_year_title: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    active_by_year_name: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in active_pdfs:
        active_by_hash[str(row["sha256"])].append(row)
        active_by_year_title[(str(row["source_year"]), str(row["title_key"]))].append(row)
        active_by_year_name[(str(row["source_year"]), str(row["file_name"]).upper())].append(row)

    live_rows = read_csv(LIVE_MANIFEST)
    live_official = [row for row in live_rows if row.get("source_kind") == "official_pdf"]
    live_file_audit = []
    live_by_hash: dict[str, list[dict[str, object]]] = defaultdict(list)
    live_by_year_title: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for row in live_official:
        out_file = rel_from_repo(row.get("output_file", ""))
        exists = out_file.exists()
        actual_size = out_file.stat().st_size if exists else ""
        actual_hash = sha256(out_file) if exists else ""
        manifest_hash = str(row.get("sha256") or "").upper()
        year = str(row.get("website_matrix_year") or row.get("license_year") or "")
        if not year:
            match = re.search(r"/(20\d{2})/", str(row.get("output_file", "")).replace("\\", "/"))
            year = match.group(1) if match else ""
        key = title_key(row.get("output_file") or row.get("link_text") or "")
        live_ref = {
            "row": row,
            "path": out_file,
            "source_year": year,
            "title_key": key,
            "sha256": actual_hash or manifest_hash,
            "size_bytes": actual_size or row.get("size_bytes") or "",
        }
        if live_ref["sha256"]:
            live_by_hash[str(live_ref["sha256"])].append(live_ref)
        if year and key:
            live_by_year_title[(year, key)].append(live_ref)
        hash_matches = active_by_hash.get(actual_hash or manifest_hash, [])
        live_file_audit.append(
            {
                "live_source_url": row.get("source_url", ""),
                "live_link_text": row.get("link_text", ""),
                "live_category": row.get("category", ""),
                "live_year": year,
                "live_output_file": row.get("output_file", ""),
                "live_file_exists": str(exists).upper(),
                "live_manifest_size_bytes": row.get("size_bytes", ""),
                "live_actual_size_bytes": actual_size,
                "live_manifest_sha256": manifest_hash,
                "live_actual_sha256": actual_hash,
                "active_pdf_exact_hash_match_count": len(hash_matches),
                "active_pdf_exact_hash_match_paths": joined_paths(hash_matches),
                "live_vs_active_status": "EXACT_HASH_MATCH_ACTIVE_PDF" if hash_matches else "NO_ACTIVE_HASH_MATCH",
            }
        )

    def compare_issue(row: dict[str, str], kind: str) -> dict[str, object]:
        source_year, target_year = parse_years(row.get("manifest", ""))
        old_rel = row.get("old_relative_path", "")
        new_rel = row.get("new_relative_path", "") or old_rel
        canonical = row.get("canonical_source_value", "")
        active_candidate = RAW_ROOT / source_year / "pdf" / "draw_odds" / new_rel.replace("/", "\\")
        truth_candidate = truth_path_for(source_year, target_year, new_rel) if source_year and target_year else Path()

        active_exists = active_candidate.exists()
        truth_exists = truth_candidate.exists()
        active_hash = sha256(active_candidate) if active_exists else ""
        truth_hash = sha256(truth_candidate) if truth_exists else ""
        active_size = active_candidate.stat().st_size if active_exists else ""
        truth_size = truth_candidate.stat().st_size if truth_exists else ""

        query_keys = {title_key(canonical), title_key(old_rel), title_key(new_rel)}
        query_keys.discard("")
        title_pdf_matches: list[dict[str, object]] = []
        live_title_matches: list[dict[str, object]] = []
        for key in query_keys:
            title_pdf_matches.extend(active_by_year_title.get((source_year, key), []))
            live_title_matches.extend(live_by_year_title.get((source_year, key), []))

        active_live_hash_matches = live_by_hash.get(active_hash, []) if active_hash else []
        truth_live_hash_matches = live_by_hash.get(truth_hash, []) if truth_hash else []
        any_live_hash_matches = []
        for key in query_keys:
            any_live_hash_matches.extend(live_by_year_title.get((source_year, key), []))

        if active_live_hash_matches and truth_live_hash_matches and active_hash == truth_hash:
            resolution = "PIPELINE_AND_TRUTH_MATCH_LIVE"
        elif active_live_hash_matches:
            resolution = "PIPELINE_PDF_MATCHES_LIVE"
        elif truth_live_hash_matches:
            resolution = "TRUTH_MIRROR_MATCHES_LIVE"
        elif active_exists and not truth_exists and title_pdf_matches:
            resolution = "ACTIVE_PIPELINE_TITLE_MATCH_ONLY"
        elif live_title_matches and title_pdf_matches:
            resolution = "LIVE_AND_ACTIVE_TITLE_MATCH_REVIEW_HASH"
        elif live_title_matches:
            resolution = "LIVE_TITLE_MATCH_ONLY"
        elif title_pdf_matches:
            resolution = "ACTIVE_PIPELINE_TITLE_MATCH_ONLY"
        elif active_exists or truth_exists:
            resolution = "LOCAL_PATH_EXISTS_NO_LIVE_MATCH"
        else:
            resolution = "NO_MATCH_REVIEW_REQUIRED"

        return {
            "issue_kind": kind,
            "manifest": row.get("manifest", ""),
            "source_year": source_year,
            "target_year": target_year,
            "canonical_source_value": canonical,
            "old_relative_path": old_rel,
            "new_relative_path": row.get("new_relative_path", ""),
            "issue": row.get("issue", ""),
            "active_pipeline_candidate_path": active_candidate.relative_to(REPO).as_posix() if str(active_candidate) else "",
            "active_pipeline_exists": str(active_exists).upper(),
            "active_pipeline_size_bytes": active_size,
            "active_pipeline_sha256": active_hash,
            "truth_mirror_candidate_path": truth_candidate.relative_to(REPO).as_posix() if truth_candidate and str(truth_candidate) else "",
            "truth_mirror_exists": str(truth_exists).upper(),
            "truth_mirror_size_bytes": truth_size,
            "truth_mirror_sha256": truth_hash,
            "pipeline_truth_hash_equal": str(bool(active_hash and truth_hash and active_hash == truth_hash)).upper(),
            "live_matches_pipeline_hash_count": len(active_live_hash_matches),
            "live_matches_truth_hash_count": len(truth_live_hash_matches),
            "active_title_match_count": len(title_pdf_matches),
            "active_title_match_paths": joined_paths(title_pdf_matches),
            "live_title_match_count": len(live_title_matches),
            "live_title_match_outputs": ";".join(str(match["row"].get("output_file", "")) for match in live_title_matches[:8]),
            "live_resolution_status": resolution,
        }

    unresolved_rows = [compare_issue(row, "UNRESOLVED") for row in read_csv(UNRESOLVED)]
    conflict_rows = [compare_issue(row, "CONFLICT") for row in read_csv(CONFLICTS)]

    write_csv(
        out_dir / "LIVE_PULL_OFFICIAL_PDF_VS_ACTIVE_PDF_AUDIT.csv",
        live_file_audit,
        [
            "live_source_url",
            "live_link_text",
            "live_category",
            "live_year",
            "live_output_file",
            "live_file_exists",
            "live_manifest_size_bytes",
            "live_actual_size_bytes",
            "live_manifest_sha256",
            "live_actual_sha256",
            "active_pdf_exact_hash_match_count",
            "active_pdf_exact_hash_match_paths",
            "live_vs_active_status",
        ],
    )
    issue_fields = [
        "issue_kind",
        "manifest",
        "source_year",
        "target_year",
        "canonical_source_value",
        "old_relative_path",
        "new_relative_path",
        "issue",
        "active_pipeline_candidate_path",
        "active_pipeline_exists",
        "active_pipeline_size_bytes",
        "active_pipeline_sha256",
        "truth_mirror_candidate_path",
        "truth_mirror_exists",
        "truth_mirror_size_bytes",
        "truth_mirror_sha256",
        "pipeline_truth_hash_equal",
        "live_matches_pipeline_hash_count",
        "live_matches_truth_hash_count",
        "active_title_match_count",
        "active_title_match_paths",
        "live_title_match_count",
        "live_title_match_outputs",
        "live_resolution_status",
    ]
    write_csv(out_dir / "SOURCE_ALIAS_UNRESOLVED_LIVE_PDF_CHECK.csv", unresolved_rows, issue_fields)
    write_csv(out_dir / "SOURCE_ALIAS_CONFLICT_LIVE_PDF_CHECK.csv", conflict_rows, issue_fields)
    write_csv(
        out_dir / "ACTIVE_PDF_READ_ERRORS.csv",
        pdf_read_errors,
        ["relative_path", "source_year", "doc_type", "file_name", "size_bytes", "error"],
    )

    summary_rows = []
    def add_metric(metric: str, value: object) -> None:
        summary_rows.append({"metric": metric, "value": value})

    add_metric("live_manifest_path", LIVE_MANIFEST)
    add_metric("live_manifest_rows", len(live_rows))
    add_metric("live_official_pdf_rows", len(live_official))
    add_metric("live_official_pdf_exact_active_hash_matches", sum(1 for row in live_file_audit if row["live_vs_active_status"] == "EXACT_HASH_MATCH_ACTIVE_PDF"))
    add_metric("live_official_pdf_without_active_hash_match", sum(1 for row in live_file_audit if row["live_vs_active_status"] != "EXACT_HASH_MATCH_ACTIVE_PDF"))
    add_metric("active_pdf_count", len(active_pdfs))
    add_metric("active_pdf_read_errors", len(pdf_read_errors))
    add_metric("unresolved_rows_checked", len(unresolved_rows))
    add_metric("conflict_rows_checked", len(conflict_rows))
    for label, rows in [("unresolved", unresolved_rows), ("conflict", conflict_rows)]:
        counts = defaultdict(int)
        for row in rows:
            counts[str(row["live_resolution_status"])] += 1
        for status, count in sorted(counts.items()):
            add_metric(f"{label}_{status}", count)

    write_csv(out_dir / "LIVE_PULL_PDF_ALIAS_ISSUE_CHECK_SUMMARY.csv", summary_rows, ["metric", "value"])

    unresolved_blocked = sum(1 for row in unresolved_rows if row["live_resolution_status"] == "NO_MATCH_REVIEW_REQUIRED")
    conflict_supported = sum(
        1
        for row in conflict_rows
        if row["live_resolution_status"] in {"PIPELINE_PDF_MATCHES_LIVE", "TRUTH_MIRROR_MATCHES_LIVE", "PIPELINE_AND_TRUTH_MATCH_LIVE"}
    )
    status = "PASS_WITH_REVIEW_REQUIRED" if unresolved_blocked or conflict_rows else "PASS"
    report = [
        "# Live Pull vs Active PDF / Alias Issue Check",
        "",
        f"report_timestamp: {datetime.now().isoformat(timespec='seconds')}",
        "",
        f"live_manifest: {LIVE_MANIFEST}",
        f"alias_issue_root: {ALIAS_ISSUE_ROOT}",
        "",
        f"live_official_pdf_rows: {len(live_official)}",
        f"active_pdf_count: {len(active_pdfs)}",
        f"active_pdf_read_errors: {len(pdf_read_errors)}",
        f"live_official_pdf_exact_active_hash_matches: {sum(1 for row in live_file_audit if row['live_vs_active_status'] == 'EXACT_HASH_MATCH_ACTIVE_PDF')}",
        f"live_official_pdf_without_active_hash_match: {sum(1 for row in live_file_audit if row['live_vs_active_status'] != 'EXACT_HASH_MATCH_ACTIVE_PDF')}",
        "",
        f"unresolved_rows_checked: {len(unresolved_rows)}",
        f"unresolved_no_match_review_required: {unresolved_blocked}",
        f"conflict_rows_checked: {len(conflict_rows)}",
        f"conflict_rows_with_live_hash_support: {conflict_supported}",
        "",
        "No alias manifests or raw PDFs were patched by this check.",
        f"LIVE_PULL_PDF_ALIAS_CHECK_STATUS={status}",
    ]
    (out_dir / "LIVE_PULL_PDF_ALIAS_ISSUE_CHECK_REPORT.md").write_text("\n".join(report) + "\n", encoding="utf-8")

    print(f"LIVE_PULL_PDF_ALIAS_CHECK_OUTPUT_DIR={out_dir}")
    print(f"LIVE_OFFICIAL_PDF_ROWS={len(live_official)}")
    print(f"ACTIVE_PDF_COUNT={len(active_pdfs)}")
    print(f"ACTIVE_PDF_READ_ERRORS={len(pdf_read_errors)}")
    print(f"LIVE_OFFICIAL_PDF_EXACT_ACTIVE_HASH_MATCHES={sum(1 for row in live_file_audit if row['live_vs_active_status'] == 'EXACT_HASH_MATCH_ACTIVE_PDF')}")
    print(f"LIVE_OFFICIAL_PDF_WITHOUT_ACTIVE_HASH_MATCH={sum(1 for row in live_file_audit if row['live_vs_active_status'] != 'EXACT_HASH_MATCH_ACTIVE_PDF')}")
    print(f"UNRESOLVED_ROWS_CHECKED={len(unresolved_rows)}")
    print(f"UNRESOLVED_NO_MATCH_REVIEW_REQUIRED={unresolved_blocked}")
    print(f"CONFLICT_ROWS_CHECKED={len(conflict_rows)}")
    print(f"CONFLICT_ROWS_WITH_LIVE_HASH_SUPPORT={conflict_supported}")
    print(f"LIVE_PULL_PDF_ALIAS_CHECK_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
