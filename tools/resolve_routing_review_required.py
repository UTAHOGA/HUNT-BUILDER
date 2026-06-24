from __future__ import annotations

import csv
import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

ENGINE_FEEDS = REPO / "processed_data" / "engine_feeds"
OUT_DIR = REPO / "audits" / "routing_review_resolution" / STAMP
CANDIDATE_DIR = REPO / "processed_data" / f"engine_feeds_resolved_candidate_{STAMP}"

OUT_DIR.mkdir(parents=True, exist_ok=True)
CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)

FEED_NAMES = {
    "PREFERENCE_DRAW": "preference_draw_feed.csv",
    "YOUTH_RANDOM": "youth_random_feed.csv",
    "AVAILABILITY_ONLY": "availability_only_feed.csv",
    "HOLD_BONUS_OR_NONPREFERENCE": "hold_bonus_or_nonpreference_feed.csv",
    "REVIEW_REQUIRED": "routing_review_required.csv",
}


def make_unique_headers(headers):
    seen = Counter()
    used = set()
    fixed = []
    renamed = []

    for h in headers:
        base = (h or "").strip() or "blank_column"
        key = base.lower()
        seen[key] += 1

        if key not in used:
            new = base
        else:
            new = f"{base}__duplicate_{seen[key]}"
            while new.lower() in used:
                seen[key] += 1
                new = f"{base}__duplicate_{seen[key]}"
            renamed.append({"original": base, "renamed_to": new})

        fixed.append(new)
        used.add(new.lower())

    return fixed, renamed


def read_csv(path: Path):
    if not path.exists():
        return [], [], []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], [], []

        headers, renamed = make_unique_headers(raw_headers)
        rows = []

        for line_no, values in enumerate(reader, start=2):
            if len(values) < len(headers):
                values = values + [""] * (len(headers) - len(values))
            elif len(values) > len(headers):
                values = values[:len(headers)]

            row = dict(zip(headers, values))
            row["_review_source_file"] = str(path.relative_to(REPO))
            row["_review_source_line"] = str(line_no)
            rows.append(row)

    return headers, rows, renamed


def write_csv(path: Path, rows, preferred_headers=None):
    path.parent.mkdir(parents=True, exist_ok=True)

    headers = []
    seen = set()

    if preferred_headers:
        for h in preferred_headers:
            if h not in seen:
                headers.append(h)
                seen.add(h)

    for row in rows:
        for h in row.keys():
            if h not in seen:
                headers.append(h)
                seen.add(h)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def clean(v):
    return re.sub(r"\s+", " ", str(v or "").strip())


def get(row, *names):
    lower = {k.lower(): k for k in row.keys()}
    for name in names:
        k = lower.get(name.lower())
        if k is not None:
            value = clean(row.get(k, ""))
            if value:
                return value
    return ""


def haystack(row):
    fields = [
        "hunt_code",
        "hunt_code_normalized",
        "code",
        "hunt_name",
        "hunt_name_normalized",
        "name",
        "raw_hunt_name",
        "unit",
        "species",
        "sex",
        "sex_class",
        "sex_type",
        "weapon",
        "season",
        "hunt_category",
        "hunt_type",
        "hunt_class",
        "hunt_draw_class",
        "draw_design",
        "draw_method",
        "draw_system",
        "point_system",
        "permit_pool",
        "draw_2026_system_type",
        "draw_2025_type",
        "row_type",
        "record_type",
        "source_dataset",
        "source_file",
    ]
    return " | ".join(get(row, f).lower() for f in fields)


def classify_review_row(row):
    text = haystack(row)
    species = get(row, "species").lower()
    code = get(row, "hunt_code", "hunt_code_normalized", "code").upper()

    # Explicit availability / non-odds rows.
    availability_terms = [
        "availability",
        "available only",
        "otc",
        "over the counter",
        "unlimited",
        "pursuit",
        "direct allocation",
        "no draw",
        "not applicable",
        "remaining permits",
        "leftover",
        "conservation",
        "expo",
        "cwmu",
        "private land",
        "private-land",
        "landowner",
    ]

    if any(term in text for term in availability_terms):
        return "AVAILABILITY_ONLY", "review_resolved_availability_term"

    # Known preference families.
    preference_terms = [
        "general season buck deer",
        "general-season buck deer",
        "g.s. buck deer",
        "gs buck deer",
        "dedicated hunter",
        "d.h. deer",
        "dh deer",
        "antlerless deer",
        "antlerless elk",
        "doe pronghorn",
        "doe antelope",
    ]

    if "preference" in text or any(term in text for term in preference_terms):
        # Guard against LE/OIL/bonus rows that also mention a preference-like word.
        forbidden = [
            "limited entry",
            "premium limited",
            "once-in-a-lifetime",
            "once in a lifetime",
            "max/weighted",
            "weighted split",
            "bonus point",
            "bonus draw",
            "oil",
            "o.i.l",
            "bison",
            "moose",
            "sheep",
            "goat",
            "bear",
            "cougar",
            "turkey",
        ]
        if not any(term in text for term in forbidden):
            return "PREFERENCE_DRAW", "review_resolved_known_preference_family"

    # Youth random-style rows.
    if "youth" in text:
        if "preference" not in text and "bonus" not in text and "limited entry" not in text:
            return "YOUTH_RANDOM", "review_resolved_youth_random"

    # Bonus / LE / OIL / non-preference hold rows.
    hold_terms = [
        "limited entry",
        "limited-entry",
        "premium limited",
        "once-in-a-lifetime",
        "once in a lifetime",
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
        "pronghorn buck",
        "buck pronghorn",
    ]

    if any(term in text for term in hold_terms):
        # Doe pronghorn is not a bonus hold.
        if "doe pronghorn" not in text and "doe antelope" not in text:
            return "HOLD_BONUS_OR_NONPREFERENCE", "review_resolved_hold_bonus_nonpreference"

    # Conservative code-prefix holds for known OIL/LE species families.
    hold_prefixes = ("BI", "MB", "RS", "DS", "GO", "EB", "PB", "BB")
    if code.startswith(hold_prefixes):
        return "HOLD_BONUS_OR_NONPREFERENCE", "review_resolved_hold_code_prefix"

    return "REVIEW_REQUIRED", "still_unresolved_after_review_resolution"


def main():
    all_rows_by_route = defaultdict(list)
    header_renames = []
    file_counts = []

    # Load existing feeds.
    for route, filename in FEED_NAMES.items():
        path = ENGINE_FEEDS / filename
        headers, rows, renamed = read_csv(path)
        header_renames.extend(
            [{"feed": route, "file": str(path.relative_to(REPO)), **r} for r in renamed]
        )
        file_counts.append({
            "route": route,
            "file": str(path.relative_to(REPO)),
            "rows": len(rows),
            "exists": path.exists(),
        })

        # Existing review rows get reclassified below.
        if route == "REVIEW_REQUIRED":
            review_rows = rows
        else:
            all_rows_by_route[route].extend(rows)

    resolution_rows = []
    remaining_review = []

    for row in review_rows:
        new_route, reason = classify_review_row(row)
        old_route = get(row, "engine_route") or "REVIEW_REQUIRED"

        row["previous_engine_route"] = old_route
        row["engine_route"] = new_route
        row["review_resolution_reason"] = reason

        resolution_rows.append({
            "hunt_code": get(row, "hunt_code", "hunt_code_normalized", "code"),
            "hunt_name": get(row, "hunt_name", "hunt_name_normalized", "name", "unit"),
            "species": get(row, "species"),
            "sex": get(row, "sex", "sex_class", "sex_type"),
            "weapon": get(row, "weapon"),
            "hunt_category": get(row, "hunt_category", "hunt_type", "hunt_class"),
            "draw_method": get(row, "draw_method"),
            "previous_engine_route": old_route,
            "new_engine_route": new_route,
            "review_resolution_reason": reason,
        })

        if new_route == "REVIEW_REQUIRED":
            remaining_review.append(row)

        all_rows_by_route[new_route].append(row)

    preferred = [
        "engine_route",
        "previous_engine_route",
        "review_resolution_reason",
        "hunt_code",
        "hunt_code_normalized",
        "hunt_name",
        "hunt_name_normalized",
        "species",
        "sex",
        "sex_class",
        "sex_type",
        "weapon",
        "season",
        "hunt_category",
        "hunt_type",
        "hunt_class",
        "draw_design",
        "draw_method",
        "draw_system",
        "point_system",
        "permit_pool",
        "_review_source_file",
        "_review_source_line",
    ]

    # Write candidate feed directory.
    for route, filename in FEED_NAMES.items():
        write_csv(CANDIDATE_DIR / filename, all_rows_by_route.get(route, []), preferred)

    # Write audit artifacts.
    write_csv(OUT_DIR / "review_resolution_detail.csv", resolution_rows)
    write_csv(OUT_DIR / "remaining_review_required.csv", remaining_review, preferred)
    write_csv(OUT_DIR / "header_renames.csv", header_renames)
    write_csv(OUT_DIR / "input_file_counts.csv", file_counts)

    route_counts = [
        {"engine_route": route, "row_count": len(rows)}
        for route, rows in sorted(all_rows_by_route.items())
    ]
    write_csv(OUT_DIR / "candidate_route_counts.csv", route_counts)

    summary = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "original_review_required_rows": len(review_rows),
        "remaining_review_required_rows": len(remaining_review),
        "candidate_feed_dir": str(CANDIDATE_DIR.relative_to(REPO)),
        "audit_dir": str(OUT_DIR.relative_to(REPO)),
        "candidate_route_counts": route_counts,
        "resolution_counts": dict(Counter(r["new_engine_route"] for r in resolution_rows)),
    }

    (OUT_DIR / "review_resolution_summary.json").write_text(
        json.dumps(summary, indent=2),
        encoding="utf-8",
    )

    md = [
        "# Routing Review Resolution",
        "",
        f"Created: {summary['created_at']}",
        "",
        f"Original REVIEW_REQUIRED rows: {len(review_rows):,}",
        f"Remaining REVIEW_REQUIRED rows: {len(remaining_review):,}",
        "",
        "## Resolution counts",
    ]

    for route, count in sorted(summary["resolution_counts"].items()):
        md.append(f"- {route}: {count:,}")

    md.extend([
        "",
        "## Candidate feeds",
        f"`{summary['candidate_feed_dir']}`",
        "",
        "## Audit files",
        f"- `{str((OUT_DIR / 'review_resolution_detail.csv').relative_to(REPO))}`",
        f"- `{str((OUT_DIR / 'remaining_review_required.csv').relative_to(REPO))}`",
        f"- `{str((OUT_DIR / 'candidate_route_counts.csv').relative_to(REPO))}`",
        "",
        "Promotion rule: do not overwrite `processed_data/engine_feeds` until remaining REVIEW_REQUIRED is zero or intentionally accepted as non-public hold.",
    ])

    (OUT_DIR / "REVIEW_RESOLUTION_REPORT.md").write_text("\n".join(md), encoding="utf-8")

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()