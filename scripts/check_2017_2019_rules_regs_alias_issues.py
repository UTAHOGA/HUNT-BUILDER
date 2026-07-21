from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover - dependency check happens at runtime
    PdfReader = None
    PYPDF_IMPORT_ERROR = str(exc)
else:
    PYPDF_IMPORT_ERROR = ""


REPO_ROOT = Path(__file__).resolve().parents[1]
YEARS = (2017, 2019)
LATEST_LIVE_AUDIT = REPO_ROOT / "audits" / "live_pull_pdf_alias_issue_check_20260721_094109"

PROGRAM_TERMS = {
    "CWMU": ["CWMU", "Cooperative Wildlife Management Unit"],
    "ANTLERLESS": ["antlerless"],
    "YOUTH": ["youth"],
    "YOUTH_ANTLERLESS": ["youth antlerless", "youth any bull", "youth permits"],
    "BIG_GAME": ["big game"],
    "LIMITED_ENTRY": ["limited-entry", "limited entry"],
    "PREMIUM_LIMITED_ENTRY": ["premium limited-entry", "premium limited entry"],
    "ONCE_IN_A_LIFETIME": ["once-in-a-lifetime", "once in a lifetime"],
    "BLACK_BEAR": ["black bear", "bear"],
    "COUGAR": ["cougar"],
    "TURKEY": ["turkey"],
    "POINTS": ["bonus point", "preference point", "points"],
    "DRAW_ODDS": ["draw odds", "drawing odds"],
    "PERMIT": ["permit"],
    "OVER_THE_COUNTER": ["over-the-counter", "over the counter", "OTC"],
    "PRIVATE_LANDS_ONLY": ["private lands only"],
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK": [
        "private lands only antlerless elk",
        "private land only antlerless elk",
        "private-lands-only antlerless elk",
        "private lands only",
        "private land only",
    ],
    "SPIKE_ELK": ["spike elk"],
    "GENERAL_SEASON_ANTLERLESS_ELK": ["general-season antlerless elk", "general season antlerless elk", "antlerless elk"],
    "GENERAL_BULL_ELK": ["general-season bull elk", "general bull elk", "any bull elk"],
    "YOUTH_BULL_ELK": ["youth any bull elk", "youth bull elk", "youth elk"],
    "PRONGHORN_ANTLERLESS": ["doe pronghorn", "antlerless pronghorn"],
    "BEAR_PURSUIT": ["bear pursuit", "pursuit season", "pursuit permit"],
    "BEAR_LIMITED_ENTRY": ["limited-entry bear", "limited entry bear"],
    "COUGAR_LIMITED_ENTRY": ["limited-entry cougar", "limited entry cougar"],
    "TURKEY_YOUTH": ["youth turkey", "youth turkey hunt"],
    "HARVEST_OBJECTIVE": ["harvest-objective", "harvest objective"],
}


@dataclass
class PdfText:
    path: Path
    source_year: int
    size_bytes: int
    sha256: str
    page_count: int
    text_by_page: list[str]
    error: str = ""


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def read_pdf(path: Path, source_year: int) -> PdfText:
    size = path.stat().st_size
    digest = sha256_file(path)
    if PdfReader is None:
        return PdfText(path, source_year, size, digest, 0, [], PYPDF_IMPORT_ERROR)
    try:
        reader = PdfReader(str(path))
        pages: list[str] = []
        for page in reader.pages:
            try:
                pages.append(page.extract_text() or "")
            except Exception as exc:
                pages.append("")
        return PdfText(path, source_year, size, digest, len(reader.pages), pages)
    except Exception as exc:
        return PdfText(path, source_year, size, digest, 0, [], str(exc))


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def count_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return max(sum(1 for _ in csv.reader(f)) - 1, 0)


def load_issue_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def classify_issue(row: dict[str, str], hits_by_group: dict[tuple[int, str], int]) -> str:
    status = row.get("live_resolution_status", "")
    canonical = (row.get("canonical_source_value") or "").lower()
    old = (row.get("old_relative_path") or "").lower()
    joined = f"{canonical} {old}"
    source_year = int(row.get("source_year") or 0)
    target_year = int(row.get("target_year") or 0)

    year_candidates = [source_year, target_year]
    has_cwmu_hit = any(hits_by_group.get((year, "CWMU"), 0) for year in year_candidates)
    has_antlerless_hit = any(hits_by_group.get((year, "ANTLERLESS"), 0) for year in year_candidates)
    has_youth_hit = any(hits_by_group.get((year, "YOUTH"), 0) for year in year_candidates)
    has_bear_hit = any(hits_by_group.get((year, "BLACK_BEAR"), 0) for year in year_candidates)
    has_cougar_hit = any(hits_by_group.get((year, "COUGAR"), 0) for year in year_candidates)
    has_turkey_hit = any(hits_by_group.get((year, "TURKEY"), 0) for year in year_candidates)
    has_points_hit = any(hits_by_group.get((year, "POINTS"), 0) for year in year_candidates)

    if status in {"TRUTH_MIRROR_MATCHES_LIVE", "LIVE_TITLE_MATCH_ONLY"}:
        return "LIVE_PULL_EVIDENCE_ALREADY_PRESENT_REGS_CONTEXT_ONLY"
    if "cwmu" in joined and has_cwmu_hit:
        return "REGS_SUPPORT_CWMU_PROGRAM_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    if "antlerless" in joined and has_antlerless_hit:
        if "youth" in joined and has_youth_hit:
            return "REGS_SUPPORT_YOUTH_ANTLERLESS_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
        return "REGS_SUPPORT_ANTLERLESS_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    if ("bear" in joined or "black_bear" in joined) and has_bear_hit:
        return "REGS_SUPPORT_BEAR_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    if "cougar" in joined and has_cougar_hit:
        return "REGS_SUPPORT_COUGAR_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    if "turkey" in joined and has_turkey_hit:
        return "REGS_SUPPORT_TURKEY_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    if ("bonus" in joined or "point" in joined) and has_points_hit:
        return "REGS_SUPPORT_POINTS_CONTEXT_DO_NOT_RESOLVE_PDF_ALIAS"
    return "NO_REGS_EVIDENCE_FOR_ALIAS_RESOLUTION"


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "audits" / f"rules_regs_2017_2019_check_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    pdfs: list[Path] = []
    for year in YEARS:
        regs_dir = REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / str(year) / "pdf" / "regulations"
        pdfs.extend(sorted(p for p in regs_dir.glob("*.pdf") if p.is_file()))

    pdf_texts = [read_pdf(path, int(path.parts[path.parts.index("hunt_unit_database") + 1])) for path in pdfs]

    inventory_rows: list[dict[str, object]] = []
    extraction_error_rows: list[dict[str, object]] = []
    for item in pdf_texts:
        inventory_rows.append(
            {
                "source_year_folder": item.source_year,
                "model_target_year_inferred": item.source_year + 1,
                "path": str(item.path.relative_to(REPO_ROOT)),
                "file_name": item.path.name,
                "size_bytes": item.size_bytes,
                "page_count": item.page_count,
                "sha256": item.sha256,
                "text_extraction_status": "ERROR" if item.error else "OK",
                "text_extraction_error": item.error,
            }
        )
        if item.error:
            extraction_error_rows.append(
                {
                    "source_year_folder": item.source_year,
                    "path": str(item.path.relative_to(REPO_ROOT)),
                    "error": item.error,
                }
            )

    term_hit_rows: list[dict[str, object]] = []
    hits_by_group: dict[tuple[int, str], int] = defaultdict(int)
    for item in pdf_texts:
        if item.error:
            continue
        for page_index, page_text in enumerate(item.text_by_page, start=1):
            page_norm = normalize_text(page_text)
            page_lower = page_norm.lower()
            for group, terms in PROGRAM_TERMS.items():
                matched_terms = [term for term in terms if term.lower() in page_lower]
                if not matched_terms:
                    continue
                hits_by_group[(item.source_year, group)] += 1
                first = min((page_lower.find(term.lower()), term) for term in matched_terms)
                start = max(first[0] - 90, 0)
                end = min(first[0] + 180, len(page_norm))
                term_hit_rows.append(
                    {
                        "source_year_folder": item.source_year,
                        "model_target_year_inferred": item.source_year + 1,
                        "file_name": item.path.name,
                        "relative_path": str(item.path.relative_to(REPO_ROOT)),
                        "page": page_index,
                        "term_group": group,
                        "matched_terms": ";".join(matched_terms),
                        "context_snippet": page_norm[start:end],
                    }
                )

    unresolved_path = LATEST_LIVE_AUDIT / "SOURCE_ALIAS_UNRESOLVED_LIVE_PDF_CHECK.csv"
    conflict_path = LATEST_LIVE_AUDIT / "SOURCE_ALIAS_CONFLICT_LIVE_PDF_CHECK.csv"
    issue_rows = []
    for source, rows in [("unresolved", load_issue_rows(unresolved_path)), ("conflict", load_issue_rows(conflict_path))]:
        for row in rows:
            try:
                source_year = int(row.get("source_year") or 0)
                target_year = int(row.get("target_year") or 0)
            except ValueError:
                source_year = 0
                target_year = 0
            if source_year in YEARS or target_year in YEARS:
                review_status = classify_issue(row, hits_by_group)
                issue_rows.append(
                    {
                        "issue_source": source,
                        "issue_kind": row.get("issue_kind", ""),
                        "source_year": source_year,
                        "target_year": target_year,
                        "canonical_source_value": row.get("canonical_source_value", ""),
                        "old_relative_path": row.get("old_relative_path", ""),
                        "new_relative_path": row.get("new_relative_path", ""),
                        "live_resolution_status": row.get("live_resolution_status", ""),
                        "rules_regs_review_status": review_status,
                        "notes": "Rules/regs are supporting context only; use draw-odds PDFs/hash lineage to resolve exact alias conflicts.",
                    }
                )

    inventory_csv = out_dir / "RULES_REGS_SOURCE_FILE_INVENTORY.csv"
    hits_csv = out_dir / "RULES_REGS_ALIAS_ISSUE_TERM_HITS.csv"
    review_csv = out_dir / "RULES_REGS_ALIAS_ISSUE_REVIEW.csv"
    errors_csv = out_dir / "RULES_REGS_TEXT_EXTRACTION_ERRORS.csv"
    summary_csv = out_dir / "RULES_REGS_2017_2019_CHECK_SUMMARY.csv"
    report_md = out_dir / "RULES_REGS_2017_2019_CHECK_REPORT.md"

    write_csv(
        inventory_csv,
        [
            "source_year_folder",
            "model_target_year_inferred",
            "path",
            "file_name",
            "size_bytes",
            "page_count",
            "sha256",
            "text_extraction_status",
            "text_extraction_error",
        ],
        inventory_rows,
    )
    write_csv(
        hits_csv,
        [
            "source_year_folder",
            "model_target_year_inferred",
            "file_name",
            "relative_path",
            "page",
            "term_group",
            "matched_terms",
            "context_snippet",
        ],
        term_hit_rows,
    )
    write_csv(
        review_csv,
        [
            "issue_source",
            "issue_kind",
            "source_year",
            "target_year",
            "canonical_source_value",
            "old_relative_path",
            "new_relative_path",
            "live_resolution_status",
            "rules_regs_review_status",
            "notes",
        ],
        issue_rows,
    )
    write_csv(errors_csv, ["source_year_folder", "path", "error"], extraction_error_rows)

    term_counter = Counter(row["term_group"] for row in term_hit_rows)
    issue_counter = Counter(row["rules_regs_review_status"] for row in issue_rows)
    summary_rows = [
        {"metric": "audit_output_dir", "value": str(out_dir)},
        {"metric": "source_year_folders_checked", "value": ";".join(str(y) for y in YEARS)},
        {"metric": "regulation_pdf_count", "value": len(pdfs)},
        {"metric": "total_regulation_pdf_size_bytes", "value": sum(row["size_bytes"] for row in inventory_rows)},
        {"metric": "text_extraction_error_count", "value": len(extraction_error_rows)},
        {"metric": "term_hit_rows", "value": len(term_hit_rows)},
        {"metric": "alias_issue_rows_reviewed", "value": len(issue_rows)},
        {"metric": "latest_live_alias_audit_used", "value": str(LATEST_LIVE_AUDIT)},
    ]
    for group in sorted(PROGRAM_TERMS):
        summary_rows.append({"metric": f"term_pages_{group}", "value": term_counter.get(group, 0)})
    for status, count in sorted(issue_counter.items()):
        summary_rows.append({"metric": f"issue_review_{status}", "value": count})

    write_csv(summary_csv, ["metric", "value"], summary_rows)

    status = "PASS_WITH_REVIEW_REQUIRED"
    if extraction_error_rows:
        status = "REVIEW_REQUIRED_TEXT_EXTRACTION_ERRORS"

    status_lines = "\n".join(f"- {k}: {v}" for k, v in sorted(issue_counter.items()))
    term_lines = "\n".join(f"- {k}: {term_counter.get(k, 0)} page hits" for k in sorted(PROGRAM_TERMS))
    inv_lines = "\n".join(
        f"- {row['source_year_folder']} -> {row['model_target_year_inferred']}: {row['file_name']} "
        f"({row['size_bytes']} bytes, {row['page_count']} pages)"
        for row in inventory_rows
    )

    report_md.write_text(
        "\n".join(
            [
                "# 2017 and 2019 Rules / Regulations Check",
                "",
                f"AUDIT_TIMESTAMP={timestamp}",
                f"RULES_REGS_CHECK_STATUS={status}",
                "",
                "## Scope",
                "",
                "Checked repo-visible regulation PDFs only under:",
                "",
                "- pipeline/RAW/hunt_unit_database/2017/pdf/regulations",
                "- pipeline/RAW/hunt_unit_database/2019/pdf/regulations",
                "",
                "The repo folders are source-year folders. The inferred model target years are source_year + 1.",
                "",
                "This audit does not patch truth, source aliases, DATABASE.csv, or comparable files.",
                "",
                "## Regulation Source Inventory",
                "",
                inv_lines or "- NONE",
                "",
                "## Program / Family Term Evidence",
                "",
                term_lines or "- No term hits found.",
                "",
                "## Alias Issue Review",
                "",
                status_lines or "- No 2017/2019 alias issue rows were available to review.",
                "",
                "## Finding",
                "",
                "Rules and regulations support program/family existence and context, including CWMU, antlerless, youth, big game, bear, cougar, turkey, point-system, and OTC/reference-layer terms where hits are present.",
                "",
                "Rules and regulations do not, by themselves, resolve exact draw-odds PDF hash conflicts or source-alias parent/split PDF lineage. Those remain draw-odds/source-lineage issues and should be resolved against official draw-odds PDFs, live-pull PDF hashes, and canonical source alias manifests.",
                "",
                "## Outputs",
                "",
                f"- {inventory_csv}",
                f"- {hits_csv}",
                f"- {review_csv}",
                f"- {errors_csv}",
                f"- {summary_csv}",
            ]
        ),
        encoding="utf-8",
    )

    print(f"RULES_REGS_CHECK_OUTPUT_DIR={out_dir}")
    print(f"REGULATION_PDF_COUNT={len(pdfs)}")
    print(f"TEXT_EXTRACTION_ERROR_COUNT={len(extraction_error_rows)}")
    print(f"TERM_HIT_ROWS={len(term_hit_rows)}")
    print(f"ALIAS_ISSUE_ROWS_REVIEWED={len(issue_rows)}")
    print(f"RULES_REGS_CHECK_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
