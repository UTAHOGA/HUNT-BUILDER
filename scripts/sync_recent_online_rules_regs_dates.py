from __future__ import annotations

import csv
import ctypes
import hashlib
import os
import shutil
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path


REPO_ROOT = Path(r"D:\DESKTOP\GitHub\HUNT-BUILDER")

SOURCES = [
    {
        "source_year": 2024,
        "family": "big_game_application",
        "url": "https://wildlife.utah.gov/guidebooks/2024_biggameapp.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__BIGGAMEAPP.pdf"],
    },
    {
        "source_year": 2024,
        "family": "big_game_field_regs",
        "url": "https://wildlife.utah.gov/guidebooks/2024_field_regs.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__FIELD_REGS.pdf"],
    },
    {
        "source_year": 2024,
        "family": "bear",
        "url": "https://wildlife.utah.gov/guidebooks/2024_bear.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__BEAR.pdf"],
    },
    {
        "source_year": 2024,
        "family": "cougar",
        "url": "https://wildlife.utah.gov/guidebooks/2024_cougar.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__COUGAR.pdf"],
    },
    {
        "source_year": 2024,
        "family": "turkey_combined_guidebook",
        "url": "https://wildlife.utah.gov/guidebooks/2024-25_upland_turkey.pdf",
        "repo_candidates": [
            "pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__UPLAND_TURKEY.pdf",
        ],
    },
    {
        "source_year": 2024,
        "family": "furbearer",
        "url": "https://wildlife.utah.gov/guidebooks/2024-25_furbearer.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2024/pdf/regulation/2024_REGULATIONS__FURBEARER.pdf"],
    },
    {
        "source_year": 2025,
        "family": "big_game_application",
        "url": "https://wildlife.utah.gov/guidebooks/2025_biggameapp.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__BIGGAMEAPP.pdf"],
    },
    {
        "source_year": 2025,
        "family": "big_game_field_regs",
        "url": "https://wildlife.utah.gov/guidebooks/2025_field_regs.pdf",
        "repo_candidates": [
            "pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__FIELD_REGS.pdf",
        ],
    },
    {
        "source_year": 2025,
        "family": "bear_cougar_combined",
        "url": "https://wildlife.utah.gov/guidebooks/black-bear-and-cougar-guidebook-2025.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__BEAR_COUGAR.pdf"],
    },
    {
        "source_year": 2025,
        "family": "cougar",
        "url": "https://wildlife.utah.gov/guidebooks/2025_cougar.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__COUGAR.pdf"],
    },
    {
        "source_year": 2025,
        "family": "turkey_combined_guidebook",
        "url": "https://wildlife.utah.gov/guidebooks/upland_turkey_guidebook.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__UPLAND_TURKEY.pdf"],
    },
    {
        "source_year": 2025,
        "family": "furbearer",
        "url": "https://wildlife.utah.gov/guidebooks/2025-26_furbearer.pdf",
        "repo_candidates": ["pipeline/RAW/hunt_unit_database/2025/pdf/regulation/2025_REGULATIONS__FURBEARER.pdf"],
    },
]

PUBLICATION_YEAR_RULE = (
    "For split-year guidebooks, use the first listed year as the published/source year "
    "across all years; example: 2024-25 is published_year 2024."
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_http_date(value: str) -> datetime | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str:
    if not dt:
        return ""
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def set_file_times(path: Path, dt: datetime) -> str:
    """Set CreationTime and LastWriteTime on Windows; set mtime everywhere."""
    timestamp = dt.timestamp()
    os.utime(path, (timestamp, timestamp))
    if os.name != "nt":
        return "LASTWRITE_SET_TO_HTTP_LAST_MODIFIED_CREATION_UNCHANGED"

    class FILETIME(ctypes.Structure):
        _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

    filetime_value = int(timestamp * 10_000_000) + 116_444_736_000_000_000
    filetime = FILETIME(filetime_value & 0xFFFFFFFF, filetime_value >> 32)
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateFileW(
        str(path),
        0x40000000,
        0x00000001 | 0x00000002 | 0x00000004,
        None,
        3,
        0x00000080,
        None,
    )
    if handle == -1:
        return "LASTWRITE_SET_TO_HTTP_LAST_MODIFIED_CREATION_UNCHANGED"
    try:
        ok = kernel32.SetFileTime(handle, ctypes.byref(filetime), None, ctypes.byref(filetime))
        return (
            "CREATION_AND_LASTWRITE_SET_TO_HTTP_LAST_MODIFIED"
            if ok
            else "LASTWRITE_SET_TO_HTTP_LAST_MODIFIED_CREATION_UNCHANGED"
        )
    finally:
        kernel32.CloseHandle(handle)


def year_folder_from_repo_path(path: Path | None) -> str:
    if not path:
        return ""
    parts = path.parts
    try:
        idx = parts.index("hunt_unit_database")
    except ValueError:
        return ""
    return parts[idx + 1] if idx + 1 < len(parts) else ""


def download(url: str, target: Path) -> tuple[Path, dict[str, str], str]:
    req = urllib.request.Request(url, headers={"User-Agent": "HUNT-BUILDER source audit"})
    try:
        with urllib.request.urlopen(req, timeout=60) as response:
            headers = dict(response.headers.items())
            with target.open("wb") as f:
                shutil.copyfileobj(response, f)
        return target, headers, ""
    except Exception as exc:
        return target, {}, str(exc)


def main() -> int:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = REPO_ROOT / "audits" / f"recent_online_rules_regs_date_sync_{timestamp}"
    downloads_dir = out_dir / "downloaded_online_pdfs"
    downloads_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, object]] = []
    timestamp_rows: list[dict[str, object]] = []
    status_counts: dict[str, int] = {}

    for source in SOURCES:
        download_name = Path(source["url"]).name
        downloaded_path = downloads_dir / download_name
        _, headers, download_error = download(source["url"], downloaded_path)
        online_exists = not download_error and downloaded_path.exists()
        online_sha = sha256_file(downloaded_path) if online_exists else ""
        online_size = downloaded_path.stat().st_size if online_exists else ""
        last_modified_raw = headers.get("Last-Modified", "")
        last_modified_dt = parse_http_date(last_modified_raw)

        candidates = source["repo_candidates"] or [""]
        any_exact = False
        any_missing = False
        for candidate in candidates:
            repo_path = REPO_ROOT / candidate if candidate else None
            repo_exists = bool(repo_path and repo_path.exists())
            any_missing = any_missing or not repo_exists
            before_ctime = repo_path.stat().st_ctime if repo_exists and repo_path else None
            before_mtime = repo_path.stat().st_mtime if repo_exists and repo_path else None
            before_creation = (
                datetime.fromtimestamp(before_ctime, timezone.utc).isoformat().replace("+00:00", "Z")
                if before_ctime
                else ""
            )
            before_write = (
                datetime.fromtimestamp(before_mtime, timezone.utc).isoformat().replace("+00:00", "Z")
                if before_mtime
                else ""
            )
            repo_sha = sha256_file(repo_path) if repo_exists and repo_path else ""
            repo_size = repo_path.stat().st_size if repo_exists and repo_path else ""
            repo_year_folder = year_folder_from_repo_path(repo_path)
            year_folder_status = (
                "YEAR_FOLDER_MATCHES_FIRST_LISTED_PUBLISHED_YEAR"
                if repo_year_folder and repo_year_folder == str(source["source_year"])
                else "YEAR_FOLDER_REVIEW_REQUIRED_FIRST_YEAR_RULE"
                if repo_year_folder
                else ""
            )
            hash_equal = bool(online_sha and repo_sha and online_sha == repo_sha)
            date_update_status = "NOT_UPDATED"
            after_creation = before_creation
            after_write = before_write

            if not online_exists:
                match_status = "ONLINE_DOWNLOAD_FAILED"
            elif not repo_exists:
                match_status = "REPO_FILE_MISSING_REVIEW_REQUIRED"
            elif hash_equal:
                any_exact = True
                match_status = "ONLINE_HASH_MATCHES_REPO"
                if last_modified_dt:
                    new_ts = last_modified_dt.timestamp()
                    # Keep bytes unchanged; align visible saved dates with the official online source timestamp.
                    repo_path.stat()
                    date_update_status = set_file_times(repo_path, last_modified_dt)
                    after_creation = datetime.fromtimestamp(repo_path.stat().st_ctime, timezone.utc).isoformat().replace(
                        "+00:00", "Z"
                    )
                    after_write = datetime.fromtimestamp(repo_path.stat().st_mtime, timezone.utc).isoformat().replace(
                        "+00:00", "Z"
                    )
                else:
                    date_update_status = "HASH_MATCH_NO_HTTP_LAST_MODIFIED"
            else:
                match_status = "ONLINE_REPO_HASH_DIFF_REVIEW_REQUIRED"

            status_counts[match_status] = status_counts.get(match_status, 0) + 1
            row = {
                "published_year": source["source_year"],
                "publication_year_rule": PUBLICATION_YEAR_RULE,
                "family": source["family"],
                "official_url": source["url"],
                "online_download_path": str(downloaded_path.relative_to(REPO_ROOT)),
                "online_download_status": "OK" if online_exists else "ERROR",
                "online_download_error": download_error,
                "http_last_modified": last_modified_raw,
                "http_last_modified_utc": iso(last_modified_dt),
                "online_size_bytes": online_size,
                "online_sha256": online_sha,
                "repo_path": str(repo_path.relative_to(REPO_ROOT)) if repo_path else "",
                "repo_year_folder": repo_year_folder,
                "year_folder_status": year_folder_status,
                "repo_exists": repo_exists,
                "repo_size_bytes": repo_size,
                "repo_sha256": repo_sha,
                "hash_equal": hash_equal,
                "match_status": match_status,
                "before_creation_time_utc": before_creation,
                "before_last_write_time_utc": before_write,
                "after_creation_time_utc": after_creation,
                "after_last_write_time_utc": after_write,
                "date_update_status": date_update_status,
            }
            rows.append(row)
            if hash_equal:
                timestamp_rows.append(row)

        if not candidates:
            status_counts["NO_REPO_CANDIDATE_CONFIGURED_REVIEW_REQUIRED"] = (
                status_counts.get("NO_REPO_CANDIDATE_CONFIGURED_REVIEW_REQUIRED", 0) + 1
            )
        elif online_exists and not any_exact and not any_missing:
            pass

    summary_rows = [
        {"metric": "audit_output_dir", "value": str(out_dir)},
        {"metric": "official_online_sources_checked", "value": len(SOURCES)},
        {"metric": "repo_candidate_rows_checked", "value": len(rows)},
        {"metric": "hash_matched_repo_rows", "value": sum(1 for row in rows if row["hash_equal"])},
        {
            "metric": "timestamp_updates_attempted",
            "value": sum(1 for row in rows if str(row["date_update_status"]).startswith(("CREATION", "LASTWRITE"))),
        },
    ]
    for status, count in sorted(status_counts.items()):
        summary_rows.append({"metric": f"match_status_{status}", "value": count})

    audit_csv = out_dir / "RECENT_ONLINE_RULES_REGS_HASH_AND_DATE_AUDIT.csv"
    updated_csv = out_dir / "RECENT_ONLINE_RULES_REGS_DATE_UPDATES.csv"
    summary_csv = out_dir / "RECENT_ONLINE_RULES_REGS_DATE_SYNC_SUMMARY.csv"
    report_md = out_dir / "RECENT_ONLINE_RULES_REGS_DATE_SYNC_REPORT.md"

    fields = [
        "published_year",
        "publication_year_rule",
        "family",
        "official_url",
        "online_download_path",
        "online_download_status",
        "online_download_error",
        "http_last_modified",
        "http_last_modified_utc",
        "online_size_bytes",
        "online_sha256",
        "repo_path",
        "repo_year_folder",
        "year_folder_status",
        "repo_exists",
        "repo_size_bytes",
        "repo_sha256",
        "hash_equal",
        "match_status",
        "before_creation_time_utc",
        "before_last_write_time_utc",
        "after_creation_time_utc",
        "after_last_write_time_utc",
        "date_update_status",
    ]
    write_csv(audit_csv, fields, rows)
    write_csv(updated_csv, fields, timestamp_rows)
    write_csv(summary_csv, ["metric", "value"], summary_rows)

    status = "PASS_ONLINE_HASH_MATCH_DATES_SYNCED"
    blockers = [
        row
        for row in rows
        if row["match_status"]
        in {
            "ONLINE_DOWNLOAD_FAILED",
            "REPO_FILE_MISSING_REVIEW_REQUIRED",
            "ONLINE_REPO_HASH_DIFF_REVIEW_REQUIRED",
        }
    ]
    if blockers:
        status = "PASS_WITH_REVIEW_REQUIRED"

    report_lines = [
        "# Recent Online Rules / Regulations Hash and Date Sync",
        "",
        f"AUDIT_TIMESTAMP={timestamp}",
        f"RECENT_ONLINE_RULES_REGS_DATE_SYNC_STATUS={status}",
        "",
        "## Scope",
        "",
        "Checked the official Utah DWR online guidebook PDFs for 2024 and 2025 against repo-visible regulation PDFs.",
        "",
        PUBLICATION_YEAR_RULE,
        "",
        "When an online PDF hash matched the repo file hash and the server supplied an HTTP Last-Modified value, the repo file timestamp was updated to that online source date. PDF bytes were not changed.",
        "",
        "## Summary",
        "",
    ]
    report_lines.extend(f"- {row['metric']}: {row['value']}" for row in summary_rows)
    report_lines.extend(["", "## Review Required", ""])
    if blockers:
        report_lines.extend(
            f"- {row['published_year']} {row['family']}: {row['match_status']} -> {row['repo_path']}"
            for row in blockers
        )
    else:
        report_lines.append("- NONE")
    report_lines.extend(["", "## Outputs", "", f"- {audit_csv}", f"- {updated_csv}", f"- {summary_csv}"])
    report_md.write_text("\n".join(report_lines), encoding="utf-8")

    print(f"RECENT_ONLINE_RULES_REGS_DATE_SYNC_OUTPUT_DIR={out_dir}")
    print(f"OFFICIAL_ONLINE_SOURCES_CHECKED={len(SOURCES)}")
    print(f"HASH_MATCHED_REPO_ROWS={sum(1 for row in rows if row['hash_equal'])}")
    print(
        "TIMESTAMP_UPDATES_ATTEMPTED="
        f"{sum(1 for row in rows if str(row['date_update_status']).startswith(('CREATION', 'LASTWRITE')))}"
    )
    print(f"RECENT_ONLINE_RULES_REGS_DATE_SYNC_STATUS={status}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
