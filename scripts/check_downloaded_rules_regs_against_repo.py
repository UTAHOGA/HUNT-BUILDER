from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

try:
    from pypdf import PdfReader
except Exception as exc:  # pragma: no cover
    PdfReader = None
    PYPDF_IMPORT_ERROR = str(exc)
else:
    PYPDF_IMPORT_ERROR = ""


REPO_ROOT = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")
DOWNLOAD_FILES = [
    Path(r"D:\DOWNLOADS\2017-18_cougar.pdf"),
    Path(r"D:\DOWNLOADS\2019_bear.pdf"),
    Path(r"D:\DOWNLOADS\2018_bear.pdf"),
    Path(r"D:\DOWNLOADS\2019_field_regs.pdf"),
    Path(r"D:\DOWNLOADS\2018_field_regs.pdf"),
    Path(r"D:\DOWNLOADS\2018_biggameapp.pdf"),
    Path(r"D:\DOWNLOADS\2017_field_regs.pdf"),
    Path(r"D:\DOWNLOADS\2019_biggameapp.pdf"),
    Path(r"D:\DOWNLOADS\2019-20_cougar.pdf"),
    Path(r"D:\DOWNLOADS\2018-19_cougar.pdf"),
]

TERM_GROUPS = {
    "ANTLERLESS": ["antlerless"],
    "BEAR": ["bear", "black bear"],
    "BIG_GAME": ["big game"],
    "COUGAR": ["cougar"],
    "CWMU": ["cwmu", "cooperative wildlife management unit"],
    "DRAW_ODDS": ["draw odds", "drawing odds"],
    "GENERAL_BULL_ELK": ["general bull elk", "general-season bull elk", "any bull elk"],
    "HARVEST_OBJECTIVE": ["harvest objective", "harvest-objective"],
    "LIMITED_ENTRY": ["limited entry", "limited-entry"],
    "ONCE_IN_A_LIFETIME": ["once in a lifetime", "once-in-a-lifetime"],
    "OVER_THE_COUNTER": ["over the counter", "over-the-counter", "otc"],
    "POINTS": ["bonus point", "preference point", "points"],
    "PREMIUM_LIMITED_ENTRY": ["premium limited entry", "premium limited-entry"],
    "PRIVATE_LANDS_ONLY_ANTLERLESS_ELK": [
        "private lands only antlerless elk",
        "private land only antlerless elk",
        "private lands only",
        "private land only",
    ],
    "PRONGHORN_ANTLERLESS": ["doe pronghorn", "antlerless pronghorn"],
    "SPIKE_ELK": ["spike elk"],
    "TURKEY": ["turkey"],
    "YOUTH": ["youth"],
    "YOUTH_ANTLERLESS": ["youth antlerless"],
    "YOUTH_BULL_ELK": ["youth any bull elk", "youth bull elk", "youth elk"],
}


EXPECTED_REPO_REGS = {
    "2017-18_cougar.pdf": (2017, "2017_REGULATIONS__18_COUGAR.pdf"),
    "2017_field_regs.pdf": (2017, "2017_REGULATIONS__FIELD_REGS.pdf"),
    "2018-19_cougar.pdf": (2018, "2018_REGULATIONS__19_COUGAR.pdf"),
    "2018_bear.pdf": (2018, "2018_REGULATIONS__BEAR.pdf"),
    "2018_biggameapp.pdf": (2018, "2018_REGULATIONS__BIGGAMEAPP.pdf"),
    "2018_field_regs.pdf": (2018, "2018_REGULATIONS__FIELD_REGS.pdf"),
    "2019-20_cougar.pdf": (2019, "2019_REGULATIONS__20_COUGAR.pdf"),
    "2019_bear.pdf": (2019, "2019_REGULATIONS__BEAR.pdf"),
    "2019_biggameapp.pdf": (2019, "2019_REGULATIONS__BIGGAMEAPP.pdf"),
    "2019_field_regs.pdf": (2019, "2019_REGULATIONS__FIELD_REGS.pdf"),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def page_count(path: Path) -> tuple[int, str]:
    if PdfReader is None:
        return 0, PYPDF_IMPORT_ERROR
    try:
        reader = PdfReader(str(path))
        return len(reader.pages), ""
    except Exception as exc:
        return 0, str(exc)


def term_page_counts(path: Path) -> tuple[Counter[str], str]:
    counts: Counter[str] = Counter()
    if PdfReader is None:
        return counts, PYPDF_IMPORT_ERROR
    try:
        reader = PdfReader(str(path))
        for page in reader.pages:
            text = re.sub(r"\s+", " ", page.extract_text() or "").lower()
            for group, terms in TERM_GROUPS.items():
                if any(term in text for term in terms):
                    counts[group] += 1
        return counts, ""
    except Exception as exc:
        return counts, str(exc)


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def repo_pdf_files() -> list[Path]:
    roots = [
        REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database",
        REPO_ROOT / "data_truth" / "draw_results_truth" / "raw_pdfs",
    ]
    files: list[Path] = []
    for root in roots:
        if root.exists():
            files.extend(path for path in root.rglob("*.pdf") if path.is_file())
    return files


def expected_repo_path(download_name: str) -> Path | None:
    expected = EXPECTED_REPO_REGS.get(download_name)
    if not expected:
        return None
    year, filename = expected
    return REPO_ROOT / "pipeline" / "RAW" / "hunt_unit_database" / str(year) / "pdf" / "regulations" / filename


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "audits" / f"downloaded_rules_regs_repo_check_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_hash_index: dict[str, list[Path]] = {}
    for path in repo_pdf_files():
        try:
            digest = sha256_file(path)
        except OSError:
            continue
        repo_hash_index.setdefault(digest, []).append(path)

    match_rows: list[dict[str, object]] = []
    term_rows: list[dict[str, object]] = []
    summary = Counter()

    for download in DOWNLOAD_FILES:
        exists = download.exists()
        size = download.stat().st_size if exists else ""
        digest = sha256_file(download) if exists else ""
        pages, page_error = page_count(download) if exists else (0, "missing_download")
        expected_path = expected_repo_path(download.name)
        expected_exists = bool(expected_path and expected_path.exists())
        expected_size = expected_path.stat().st_size if expected_exists and expected_path else ""
        expected_hash = sha256_file(expected_path) if expected_exists and expected_path else ""
        exact_matches = repo_hash_index.get(digest, []) if digest else []

        if not exists:
            status = "MISSING_DOWNLOAD"
        elif expected_exists and digest == expected_hash:
            status = "EXACT_MATCH_EXPECTED_REPO_REGULATION"
        elif exact_matches:
            status = "EXACT_MATCH_DIFFERENT_REPO_PATH"
        elif expected_exists:
            status = "EXPECTED_REPO_REGULATION_HASH_DIFF_REVIEW_REQUIRED"
        else:
            status = "NO_EXPECTED_REPO_REGULATION_REVIEW_REQUIRED"

        summary[status] += 1
        match_rows.append(
            {
                "download_file": str(download),
                "download_name": download.name,
                "download_exists": exists,
                "download_size_bytes": size,
                "download_page_count": pages,
                "download_sha256": digest,
                "expected_repo_path": str(expected_path) if expected_path else "",
                "expected_repo_exists": expected_exists,
                "expected_repo_size_bytes": expected_size,
                "expected_repo_sha256": expected_hash,
                "exact_repo_match_count": len(exact_matches),
                "exact_repo_match_paths": ";".join(str(p.relative_to(REPO_ROOT)) for p in exact_matches[:20]),
                "match_status": status,
                "text_extraction_error": page_error,
            }
        )

        if exists:
            counts, term_error = term_page_counts(download)
            for group in sorted(TERM_GROUPS):
                term_rows.append(
                    {
                        "download_name": download.name,
                        "term_group": group,
                        "page_hit_count": counts.get(group, 0),
                        "text_extraction_error": term_error,
                    }
                )

    inventory_csv = out_dir / "DOWNLOADED_RULES_REGS_REPO_MATCH_AUDIT.csv"
    term_csv = out_dir / "DOWNLOADED_RULES_REGS_TERM_COVERAGE.csv"
    summary_csv = out_dir / "DOWNLOADED_RULES_REGS_REPO_CHECK_SUMMARY.csv"
    report_md = out_dir / "DOWNLOADED_RULES_REGS_REPO_CHECK_REPORT.md"

    write_csv(
        inventory_csv,
        [
            "download_file",
            "download_name",
            "download_exists",
            "download_size_bytes",
            "download_page_count",
            "download_sha256",
            "expected_repo_path",
            "expected_repo_exists",
            "expected_repo_size_bytes",
            "expected_repo_sha256",
            "exact_repo_match_count",
            "exact_repo_match_paths",
            "match_status",
            "text_extraction_error",
        ],
        match_rows,
    )
    write_csv(
        term_csv,
        ["download_name", "term_group", "page_hit_count", "text_extraction_error"],
        term_rows,
    )

    status = "PASS_REPO_REGS_CONFIRMED"
    if summary.get("EXPECTED_REPO_REGULATION_HASH_DIFF_REVIEW_REQUIRED") or summary.get(
        "NO_EXPECTED_REPO_REGULATION_REVIEW_REQUIRED"
    ) or summary.get("MISSING_DOWNLOAD"):
        status = "PASS_WITH_REVIEW_REQUIRED"

    summary_rows = [
        {"metric": "audit_output_dir", "value": str(out_dir)},
        {"metric": "download_files_expected", "value": len(DOWNLOAD_FILES)},
        {"metric": "download_files_found", "value": sum(1 for row in match_rows if row["download_exists"])},
        {"metric": "download_files_missing", "value": sum(1 for row in match_rows if not row["download_exists"])},
        {"metric": "exact_expected_repo_regulation_matches", "value": summary["EXACT_MATCH_EXPECTED_REPO_REGULATION"]},
        {"metric": "exact_different_repo_path_matches", "value": summary["EXACT_MATCH_DIFFERENT_REPO_PATH"]},
        {
            "metric": "expected_repo_regulation_hash_diff_review_required",
            "value": summary["EXPECTED_REPO_REGULATION_HASH_DIFF_REVIEW_REQUIRED"],
        },
        {
            "metric": "no_expected_repo_regulation_review_required",
            "value": summary["NO_EXPECTED_REPO_REGULATION_REVIEW_REQUIRED"],
        },
        {"metric": "check_status", "value": status},
    ]
    write_csv(summary_csv, ["metric", "value"], summary_rows)

    match_lines = "\n".join(
        f"- {row['download_name']}: {row['match_status']} "
        f"({row['download_size_bytes']} bytes, {row['download_page_count']} pages)"
        for row in match_rows
    )
    review_lines = "\n".join(
        f"- {row['download_name']}: expected {row['expected_repo_path'] or 'NONE'}"
        for row in match_rows
        if "REVIEW_REQUIRED" in str(row["match_status"])
    )

    report_md.write_text(
        "\n".join(
            [
                "# Downloaded Rules / Regulations Repo Check",
                "",
                f"AUDIT_TIMESTAMP={timestamp}",
                f"DOWNLOADED_RULES_REGS_REPO_CHECK_STATUS={status}",
                "",
                "## Scope",
                "",
                "Compared the user-provided PDFs in D:/DOWNLOADS against repo-visible PDF sources under pipeline/RAW/hunt_unit_database and data_truth/draw_results_truth/raw_pdfs.",
                "",
                "This audit did not patch truth, DATABASE.csv, source aliases, or raw source folders.",
                "",
                "## Match Results",
                "",
                match_lines or "- NONE",
                "",
                "## Review Required",
                "",
                review_lines or "- NONE",
                "",
                "## Outputs",
                "",
                f"- {inventory_csv}",
                f"- {term_csv}",
                f"- {summary_csv}",
            ]
        ),
        encoding="utf-8",
    )

    print(f"DOWNLOADED_RULES_REGS_REPO_CHECK_OUTPUT_DIR={out_dir}")
    print(f"DOWNLOAD_FILES_FOUND={sum(1 for row in match_rows if row['download_exists'])}")
    print(f"EXACT_EXPECTED_REPO_REGULATION_MATCHES={summary['EXACT_MATCH_EXPECTED_REPO_REGULATION']}")
    print(f"EXPECTED_REPO_REGULATION_HASH_DIFF_REVIEW_REQUIRED={summary['EXPECTED_REPO_REGULATION_HASH_DIFF_REVIEW_REQUIRED']}")
    print(f"DOWNLOADED_RULES_REGS_REPO_CHECK_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
