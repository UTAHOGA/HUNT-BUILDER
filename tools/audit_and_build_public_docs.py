from __future__ import annotations

import csv
import html
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

AUDIT_DIR = REPO / "audits" / "public_release_certification" / STAMP
PUBLIC_ARCHIVE_DIR = REPO / "public" / "hunt-docs" / STAMP
PUBLIC_LATEST_DIR = REPO / "public" / "hunt-docs" / "latest"

AUDIT_DIR.mkdir(parents=True, exist_ok=True)
PUBLIC_ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

FEED_FILES = {
    "PREFERENCE_DRAW": REPO / "processed_data" / "engine_feeds" / "preference_draw_feed.csv",
    "YOUTH_RANDOM": REPO / "processed_data" / "engine_feeds" / "youth_random_feed.csv",
    "AVAILABILITY_ONLY": REPO / "processed_data" / "engine_feeds" / "availability_only_feed.csv",
    "HOLD_BONUS_OR_NONPREFERENCE": REPO / "processed_data" / "engine_feeds" / "hold_bonus_or_nonpreference_feed.csv",
    "REVIEW_REQUIRED": REPO / "processed_data" / "engine_feeds" / "routing_review_required.csv",
}

ENGINE_OUTPUT_ROOT = REPO / "processed_data" / "engine_outputs"

PUBLIC_ROUTES = {
    "PREFERENCE_DRAW",
    "YOUTH_RANDOM",
    "AVAILABILITY_ONLY",
}

BLOCK_PRIVATE_ROUTES = {
    "HOLD_BONUS_OR_NONPREFERENCE",
    "REVIEW_REQUIRED",
}

PUBLIC_COLUMNS = [
    "hunt_code",
    "hunt_name",
    "species",
    "sex",
    "sex_class",
    "weapon",
    "season",
    "hunt_category",
    "hunt_type",
    "hunt_class",
    "draw_design",
    "draw_method",
    "point_system",
    "permits_2026_res",
    "permits_2026_nr",
    "permits_2026_total",
    "permit_allotment_2026_res",
    "permit_allotment_2026_nr",
    "permit_allotment_2026_total",
    "permits_2025_res",
    "permits_2025_nr",
    "permits_2025_total",
    "permits_2024_res",
    "permits_2024_nr",
    "permits_2024_total",
    "permits_2023_res",
    "permits_2023_nr",
    "permits_2023_total",
    "percent_harvest_success_previous_hunting_season",
    "average_harvest_age",
    "dwr_huntplanner_age_objective",
    "dwr_huntplanner_population_objective",
    "dwr_huntplanner_current_population_estimate",
    "resident_p_draw_percent",
    "nonresident_p_draw_percent",
    "total_p_draw_percent",
    "p_draw_percent",
    "engine_route",
]

PRIVATE_COLUMN_PATTERNS = [
    r"^_",
    r"source_path",
    r"source_pdf",
    r"source_file",
    r"draw_source_file",
    r"source_namespace",
    r"draw_source_namespace",
    r"source_scope",
    r"source_line",
    r"source_dataset",
    r"parse_method",
    r"qa_notes",
    r"algorithm_status",
    r"candidate_promotion_status",
    r"collapse_conflict_count",
    r"raw_",
    r"notes$",
    r"^NOTES$",
]

PREFERENCE_FORBIDDEN_TERMS = [
    "limited entry",
    "premium limited",
    "once-in-a-lifetime",
    "oil",
    "o.i.l",
    "bonus",
    "max/weighted",
    "weighted split",
    "bison",
    "moose",
    "sheep",
    "goat",
    "bear",
    "cougar",
    "turkey",
]

REQUIRED_PUBLIC_IDENTITY_GROUPS = [
    ("hunt_code", "hunt_code_normalized", "code"),
    ("hunt_name", "hunt_name_normalized", "name", "unit"),
    ("species",),
    ("engine_route",),
]


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(REPO))
    except ValueError:
        return str(path)


def normalize_header_name(name: str) -> str:
    name = (name or "").strip()
    return name if name else "blank_column"


def make_unique_headers(headers: list[str], source_path: Path):
    seen_lower = Counter()
    used_lower = set()
    output = []
    duplicates = []

    for idx, raw in enumerate(headers, start=1):
        base = normalize_header_name(raw)
        key = base.lower()
        seen_lower[key] += 1

        if seen_lower[key] == 1 and key not in used_lower:
            new_name = base
        else:
            n = seen_lower[key]
            new_name = f"{base}__duplicate_{n}"
            while new_name.lower() in used_lower:
                n += 1
                new_name = f"{base}__duplicate_{n}"

            duplicates.append({
                "source_file": rel(source_path),
                "column_number": idx,
                "original_header": base,
                "renamed_to": new_name,
                "issue": "case_insensitive_duplicate_header",
            })

        output.append(new_name)
        used_lower.add(new_name.lower())

    return output, duplicates


def read_csv_unique(path: Path):
    duplicate_header_rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], [], []

        headers, duplicate_header_rows = make_unique_headers(raw_headers, path)
        rows = []

        for line_no, values in enumerate(reader, start=2):
            if len(values) < len(headers):
                values = values + [""] * (len(headers) - len(values))
            elif len(values) > len(headers):
                values = values[:len(headers)]

            row = dict(zip(headers, values))
            row["_audit_source_file"] = rel(path)
            row["_audit_source_line"] = line_no
            rows.append(row)

    return headers, rows, duplicate_header_rows


def write_csv(path: Path, rows: list[dict], preferred_headers: list[str] | None = None):
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = []
    seen = set()

    if preferred_headers:
        for h in preferred_headers:
            if h not in seen:
                headers.append(h)
                seen.add(h)

    for row in rows:
        for h in row:
            if h not in seen:
                headers.append(h)
                seen.add(h)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean_text(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def get(row: dict, *names: str) -> str:
    lower_map = {k.lower(): k for k in row.keys()}
    for name in names:
        k = lower_map.get(name.lower())
        if k is not None:
            value = clean_text(row.get(k, ""))
            if value:
                return value
    return ""


def route_text(row: dict) -> str:
    fields = [
        "engine_route",
        "hunt_category",
        "hunt_type",
        "hunt_class",
        "draw_design",
        "draw_method",
        "draw_system",
        "point_system",
        "permit_pool",
        "species",
        "sex",
        "sex_class",
        "weapon",
    ]
    return " | ".join(get(row, f).lower() for f in fields)


def has_required_identity(row: dict, group: tuple[str, ...]) -> bool:
    return bool(get(row, *group))


def is_private_column(col: str) -> bool:
    for pattern in PRIVATE_COLUMN_PATTERNS:
        if re.search(pattern, col, flags=re.IGNORECASE):
            return True
    return False


def public_row(row: dict) -> dict:
    out = {}

    out["hunt_code"] = get(row, "hunt_code_normalized", "hunt_code", "code")
    out["hunt_name"] = get(row, "hunt_name_normalized", "hunt_name", "name", "unit")
    out["species"] = get(row, "species")
    out["sex"] = get(row, "sex", "sex_type")
    out["sex_class"] = get(row, "sex_class", "animal_class", "sex_type")
    out["weapon"] = get(row, "weapon")
    out["season"] = get(row, "season")
    out["hunt_category"] = get(row, "hunt_category")
    out["hunt_type"] = get(row, "hunt_type")
    out["hunt_class"] = get(row, "hunt_class")
    out["draw_design"] = get(row, "draw_design")
    out["draw_method"] = get(row, "draw_method")
    out["point_system"] = get(row, "point_system")

    for col in PUBLIC_COLUMNS:
        if col not in out:
            out[col] = get(row, col)

    out["engine_route"] = get(row, "engine_route")

    return out


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def write_html_table(path: Path, title: str, rows: list[dict], max_preview: int = 500):
    cols = PUBLIC_COLUMNS
    preview_rows = rows[:max_preview]

    th = "".join(f"<th>{html.escape(c)}</th>" for c in cols)

    trs = []
    for row in preview_rows:
        tds = "".join(f"<td>{html.escape(clean_text(row.get(c, '')))}</td>" for c in cols)
        trs.append(f"<tr>{tds}</tr>")

    note = ""
    if len(rows) > max_preview:
        note = f"<p>Showing first {max_preview:,} rows. Use the CSV or JSON file for full data.</p>"

    body = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>{html.escape(title)}</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px; vertical-align: top; }}
th {{ background: #f2f2f2; position: sticky; top: 0; }}
.summary {{ margin-bottom: 16px; }}
</style>
</head>
<body>
<h1>{html.escape(title)}</h1>
<div class="summary">
<p>Total rows: {len(rows):,}</p>
{note}
</div>
<table>
<thead><tr>{th}</tr></thead>
<tbody>
{''.join(trs)}
</tbody>
</table>
</body>
</html>
"""
    path.write_text(body, encoding="utf-8")


def summarize_rows(rows: list[dict]) -> list[dict]:
    grouped = defaultdict(lambda: {"row_count": 0, "hunt_codes": set()})

    for row in rows:
        route = get(row, "engine_route") or "UNKNOWN"
        species = get(row, "species") or "UNKNOWN"
        category = get(row, "hunt_category", "hunt_type", "hunt_class") or "UNKNOWN"
        key = (route, species, category)
        grouped[key]["row_count"] += 1
        code = get(row, "hunt_code", "hunt_code_normalized", "code")
        if code:
            grouped[key]["hunt_codes"].add(code)

    out = []
    for (route, species, category), payload in sorted(grouped.items()):
        out.append({
            "engine_route": route,
            "species": species,
            "hunt_category": category,
            "row_count": payload["row_count"],
            "unique_hunt_codes": len(payload["hunt_codes"]),
        })

    return out


def main():
    blockers = []
    warnings = []
    file_inventory = []
    duplicate_header_report = []
    contamination_report = []
    missing_required_report = []
    route_mismatch_report = []

    route_rows = defaultdict(list)
    all_feed_rows = []

    # Catch accidental directory named like a CSV output.
    if ENGINE_OUTPUT_ROOT.exists():
        for item in ENGINE_OUTPUT_ROOT.rglob("*"):
            if item.is_dir() and item.name.lower().endswith(".csv"):
                blockers.append({
                    "severity": "BLOCKER",
                    "issue": "directory_named_like_csv",
                    "path": rel(item),
                    "detail": "This is a folder with a .csv name. PowerShell Import-Csv will fail on it.",
                })

    # Audit feed files.
    for expected_route, path in FEED_FILES.items():
        record = {
            "path": rel(path),
            "expected_route": expected_route,
            "exists": path.exists(),
            "is_file": path.is_file(),
            "is_dir": path.is_dir(),
            "size_bytes": path.stat().st_size if path.exists() and path.is_file() else "",
            "row_count": 0,
            "status": "UNKNOWN",
        }

        if not path.exists():
            blockers.append({
                "severity": "BLOCKER",
                "issue": "missing_feed_file",
                "path": rel(path),
                "detail": f"Missing expected engine feed for {expected_route}.",
            })
            record["status"] = "MISSING"
            file_inventory.append(record)
            continue

        if path.is_dir():
            blockers.append({
                "severity": "BLOCKER",
                "issue": "feed_path_is_directory",
                "path": rel(path),
                "detail": "Expected a CSV file, found a directory.",
            })
            record["status"] = "DIRECTORY"
            file_inventory.append(record)
            continue

        headers, rows, dupes = read_csv_unique(path)
        record["row_count"] = len(rows)
        record["status"] = "OK"
        file_inventory.append(record)
        duplicate_header_report.extend(dupes)

        if dupes:
            warnings.append({
                "severity": "WARNING",
                "issue": "duplicate_headers_renamed_for_audit",
                "path": rel(path),
                "detail": f"{len(dupes)} duplicate/case-duplicate headers were renamed in the audit reader.",
            })

        for row in rows:
            all_feed_rows.append(row)
            actual_route = get(row, "engine_route") or "UNKNOWN"
            route_rows[actual_route].append(row)

            if actual_route != expected_route:
                route_mismatch_report.append({
                    "source_file": rel(path),
                    "source_line": row.get("_audit_source_line"),
                    "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                    "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                    "expected_route": expected_route,
                    "actual_route": actual_route,
                })

            for group in REQUIRED_PUBLIC_IDENTITY_GROUPS:
                if not has_required_identity(row, group):
                    missing_required_report.append({
                        "source_file": rel(path),
                        "source_line": row.get("_audit_source_line"),
                        "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                        "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                        "missing_one_of": " | ".join(group),
                        "engine_route": actual_route,
                    })

            if actual_route == "PREFERENCE_DRAW":
                text = route_text(row)
                hits = [term for term in PREFERENCE_FORBIDDEN_TERMS if term in text]
                # Doe pronghorn is preference; buck pronghorn/LE pronghorn is not.
                if hits and "doe pronghorn" not in text:
                    contamination_report.append({
                        "source_file": rel(path),
                        "source_line": row.get("_audit_source_line"),
                        "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
                        "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
                        "engine_route": actual_route,
                        "matched_terms": "; ".join(hits),
                        "route_text": text,
                    })

    if route_mismatch_report:
        blockers.append({
            "severity": "BLOCKER",
            "issue": "route_mismatch",
            "path": "processed_data/engine_feeds",
            "detail": f"{len(route_mismatch_report)} rows are in the wrong feed file.",
        })

    if contamination_report:
        blockers.append({
            "severity": "BLOCKER",
            "issue": "preference_feed_contamination",
            "path": "processed_data/engine_feeds/preference_draw_feed.csv",
            "detail": f"{len(contamination_report)} preference rows contain bonus/LE/OIL-style classification terms.",
        })

    review_count = len(route_rows.get("REVIEW_REQUIRED", []))
    if review_count:
        blockers.append({
            "severity": "BLOCKER",
            "issue": "routing_review_required_not_empty",
            "path": rel(FEED_FILES["REVIEW_REQUIRED"]),
            "detail": f"{review_count} rows still require routing review before promotion.",
        })

    if missing_required_report:
        blockers.append({
            "severity": "BLOCKER",
            "issue": "missing_required_identity_fields",
            "path": "processed_data/engine_feeds",
            "detail": f"{len(missing_required_report)} rows are missing required public identity fields.",
        })

    # Build public-safe rows.
    public_rows = []
    private_route_rows = []

    for row in all_feed_rows:
        route = get(row, "engine_route")

        if route in PUBLIC_ROUTES:
            pub = public_row(row)

            # Last defensive check: public docs must not contain private/internal columns.
            for col in list(pub.keys()):
                if is_private_column(col):
                    pub.pop(col, None)

            public_rows.append(pub)

        elif route in BLOCK_PRIVATE_ROUTES:
            private_route_rows.append(row)

    if not public_rows:
        blockers.append({
            "severity": "BLOCKER",
            "issue": "no_public_rows",
            "path": "processed_data/engine_feeds",
            "detail": "No public-safe rows were available to publish.",
        })

    # Reports.
    write_csv(AUDIT_DIR / "file_inventory.csv", file_inventory)
    write_csv(AUDIT_DIR / "duplicate_header_report.csv", duplicate_header_report)
    write_csv(AUDIT_DIR / "route_mismatch_report.csv", route_mismatch_report)
    write_csv(AUDIT_DIR / "contamination_report.csv", contamination_report)
    write_csv(AUDIT_DIR / "missing_required_report.csv", missing_required_report)

    route_counts = [
        {"engine_route": route, "row_count": len(rows)}
        for route, rows in sorted(route_rows.items())
    ]
    write_csv(AUDIT_DIR / "route_counts.csv", route_counts)

    public_summary = summarize_rows(public_rows)
    write_csv(AUDIT_DIR / "public_summary.csv", public_summary)

    status = "CERTIFIED" if not blockers else "NOT_CERTIFIED"

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "status": status,
        "blocker_count": len(blockers),
        "warning_count": len(warnings),
        "feed_row_count": len(all_feed_rows),
        "public_row_count": len(public_rows),
        "private_or_review_row_count": len(private_route_rows),
        "route_counts": route_counts,
        "audit_dir": rel(AUDIT_DIR),
        "public_archive_dir": rel(PUBLIC_ARCHIVE_DIR),
        "public_latest_dir": rel(PUBLIC_LATEST_DIR),
        "blockers": blockers,
        "warnings": warnings,
    }

    write_json(AUDIT_DIR / "audit_summary.json", summary)

    # Public docs.
    write_csv(PUBLIC_ARCHIVE_DIR / "public_all_hunts.csv", public_rows, PUBLIC_COLUMNS)
    write_json(PUBLIC_ARCHIVE_DIR / "public_all_hunts.json", public_rows)
    write_csv(PUBLIC_ARCHIVE_DIR / "public_summary.csv", public_summary)

    by_route = defaultdict(list)
    for row in public_rows:
        by_route[get(row, "engine_route")].append(row)

    for route, rows in sorted(by_route.items()):
        safe_name = route.lower()
        write_csv(PUBLIC_ARCHIVE_DIR / f"{safe_name}.csv", rows, PUBLIC_COLUMNS)
        write_json(PUBLIC_ARCHIVE_DIR / f"{safe_name}.json", rows)
        write_html_table(PUBLIC_ARCHIVE_DIR / f"{safe_name}.html", f"{route} Public Hunt Data", rows)

    # Index HTML.
    list_items = []
    for route in sorted(by_route):
        safe_name = route.lower()
        list_items.append(
            f'<li><a href="{safe_name}.html">{html.escape(route)} HTML</a> '
            f'| <a href="{safe_name}.csv">CSV</a> '
            f'| <a href="{safe_name}.json">JSON</a></li>'
        )

    blocker_html = ""
    if blockers:
        blocker_html = "<h2>Release blockers</h2><ul>"
        for b in blockers[:50]:
            blocker_html += f"<li><strong>{html.escape(b['issue'])}</strong>: {html.escape(b.get('detail', ''))}</li>"
        blocker_html += "</ul>"

    index_html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Hunt Builder Public Data Release</title>
<style>
body {{ font-family: Arial, sans-serif; margin: 24px; max-width: 1100px; }}
.status {{ padding: 12px; border: 1px solid #ddd; background: #f8f8f8; }}
</style>
</head>
<body>
<h1>Hunt Builder Public Data Release</h1>
<div class="status">
<p><strong>Status:</strong> {html.escape(status)}</p>
<p><strong>Created:</strong> {html.escape(summary["created_at"])}</p>
<p><strong>Public rows:</strong> {len(public_rows):,}</p>
<p><strong>Blockers:</strong> {len(blockers):,}</p>
</div>

<h2>Public documents</h2>
<ul>
<li><a href="public_all_hunts.csv">All public hunts CSV</a></li>
<li><a href="public_all_hunts.json">All public hunts JSON</a></li>
<li><a href="public_summary.csv">Public summary CSV</a></li>
{''.join(list_items)}
</ul>

{blocker_html}

<p>Internal audit details are stored outside the public folder under: {html.escape(rel(AUDIT_DIR))}</p>
</body>
</html>
"""
    (PUBLIC_ARCHIVE_DIR / "index.html").write_text(index_html, encoding="utf-8")

    certification_md = [
        f"# Hunt Builder Public Data Release — {status}",
        "",
        f"Created: {summary['created_at']}",
        "",
        f"Public rows: {len(public_rows):,}",
        f"Blockers: {len(blockers):,}",
        f"Warnings: {len(warnings):,}",
        "",
        "## Public files",
        "- public_all_hunts.csv",
        "- public_all_hunts.json",
        "- public_summary.csv",
        "- route-specific CSV / JSON / HTML files",
        "",
        "## Release rule",
        "Only publish from this folder if status is CERTIFIED.",
        "",
    ]

    if blockers:
        certification_md.append("## Blockers")
        for b in blockers:
            certification_md.append(f"- {b['issue']}: {b.get('detail', '')}")

    (PUBLIC_ARCHIVE_DIR / "RELEASE_STATUS.md").write_text("\n".join(certification_md), encoding="utf-8")

    # Refresh latest.
    if PUBLIC_LATEST_DIR.exists():
        shutil.rmtree(PUBLIC_LATEST_DIR)
    shutil.copytree(PUBLIC_ARCHIVE_DIR, PUBLIC_LATEST_DIR)

    # Main markdown audit report.
    md = [
        f"# Public Release Certification — {status}",
        "",
        f"Created: {summary['created_at']}",
        "",
        "## Counts",
        f"- Feed rows: {len(all_feed_rows):,}",
        f"- Public-safe rows: {len(public_rows):,}",
        f"- Private/hold/review rows: {len(private_route_rows):,}",
        f"- Blockers: {len(blockers):,}",
        f"- Warnings: {len(warnings):,}",
        "",
        "## Route counts",
    ]

    for row in route_counts:
        md.append(f"- {row['engine_route']}: {row['row_count']}")

    md.extend([
        "",
        "## Audit outputs",
        f"- `{rel(AUDIT_DIR / 'file_inventory.csv')}`",
        f"- `{rel(AUDIT_DIR / 'duplicate_header_report.csv')}`",
        f"- `{rel(AUDIT_DIR / 'route_mismatch_report.csv')}`",
        f"- `{rel(AUDIT_DIR / 'contamination_report.csv')}`",
        f"- `{rel(AUDIT_DIR / 'missing_required_report.csv')}`",
        f"- `{rel(AUDIT_DIR / 'route_counts.csv')}`",
        f"- `{rel(AUDIT_DIR / 'audit_summary.json')}`",
        "",
        "## Public outputs",
        f"- Archive: `{rel(PUBLIC_ARCHIVE_DIR)}`",
        f"- Latest: `{rel(PUBLIC_LATEST_DIR)}`",
        "",
    ])

    if blockers:
        md.append("## Blockers")
        for b in blockers:
            md.append(f"- `{b['issue']}` — {b.get('detail', '')}")
    else:
        md.append("## Certification")
        md.append("No blockers found. Public-facing files are certified for static-site use.")

    (AUDIT_DIR / "AUDIT_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps({
        "status": status,
        "blockers": len(blockers),
        "warnings": len(warnings),
        "feed_rows": len(all_feed_rows),
        "public_rows": len(public_rows),
        "audit_report": rel(AUDIT_DIR / "AUDIT_REPORT.md"),
        "public_index": rel(PUBLIC_LATEST_DIR / "index.html"),
    }, indent=2))


if __name__ == "__main__":
    main()