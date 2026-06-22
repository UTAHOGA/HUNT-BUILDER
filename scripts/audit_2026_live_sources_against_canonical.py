import csv
import json
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRESH = ROOT / "audits" / "2025_canonical_finalization" / "fresh_live_pulls_20260621_192945"
AUDIT_DIR = ROOT / "audits" / "2026_live_source_comparison"
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"


ANTLERLESS_FILES = [
    "dwr_huntboundary_deer_antlerless.json",
    "dwr_huntboundary_elk_antlerless.json",
    "dwr_huntboundary_moose_antlerless.json",
    "dwr_huntboundary_pronghorn_doe.json",
    "dwr_huntboundary_rocky_mountain_bighorn_sheep_ewe.json",
    "dwr_huntboundary_bison_cow_only.json",
]


def clean(value):
    return " ".join(str(value or "").replace("\r", "\n").split())


def int_text(value):
    if value is None or value == "":
        return ""
    try:
        return str(int(value))
    except (TypeError, ValueError):
        return clean(value)


def source_permits(row):
    quota_res = int(row.get("QUOTA_RES") or 0)
    quota_nr = int(row.get("QUOTA_NRES") or 0)
    quota = int(row.get("QUOTA") or 0)
    if quota > 0 and quota_res == 0 and quota_nr == 0:
        return "", "", str(quota)
    if quota_res + quota_nr > 0:
        return str(quota_res), str(quota_nr), str(quota_res + quota_nr)
    if quota > 0:
        return "", "", str(quota)
    return "", "", "0"


def load_canonical():
    with CANONICAL.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    by_code = {}
    for row in rows:
        code = clean(row.get("hunt_code")).upper()
        if not code:
            continue
        by_code.setdefault(code, []).append(row)
    return rows, by_code


def compare_permits(source_res, source_nr, source_total, canonical_rows):
    for row in canonical_rows:
        can_res = clean(row.get("permits_2026_res"))
        can_nr = clean(row.get("permits_2026_nr"))
        can_total = clean(row.get("permits_2026_total"))
        if source_res == can_res and source_nr == can_nr and source_total == can_total:
            return "matched"
    for row in canonical_rows:
        can_total = clean(row.get("permits_2026_total"))
        if source_total == can_total:
            return "matched_total_only_or_split_diff"
    return "permit_mismatch"


def audit_antlerless(by_code):
    rows = []
    for filename in ANTLERLESS_FILES:
        for source in json.loads((FRESH / filename).read_text(encoding="utf-8-sig")):
            code = clean(source.get("HUNT_NBR")).upper()
            source_res, source_nr, source_total = source_permits(source)
            canonical_rows = by_code.get(code, [])
            if not canonical_rows:
                status = "missing_from_canonical"
            else:
                status = compare_permits(source_res, source_nr, source_total, canonical_rows)
            rows.append(
                {
                    "hunt_code": code,
                    "hunt_name": clean(source.get("HUNT_NAME")),
                    "species": clean(source.get("SPECIES")),
                    "sex_type": clean(source.get("GENDER")),
                    "hunt_type_raw": clean(source.get("HUNT_TYPE")),
                    "weapon": clean(source.get("WEAPON")),
                    "season": clean(source.get("SEASON_DATE_TEXT")),
                    "source_permits_res": source_res,
                    "source_permits_nr": source_nr,
                    "source_permits_total": source_total,
                    "canonical_match_count": len(canonical_rows),
                    "status": status,
                    "source_file": filename,
                }
            )
    return rows


def main():
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    canonical_rows, by_code = load_canonical()
    antlerless = audit_antlerless(by_code)

    audit_path = AUDIT_DIR / "dwr_hunt_planner_2026_antlerless_vs_canonical_hunt_code_audit.csv"
    with audit_path.open("w", newline="", encoding="utf-8") as f:
        fields = [
            "hunt_code",
            "hunt_name",
            "species",
            "sex_type",
            "hunt_type_raw",
            "weapon",
            "season",
            "source_permits_res",
            "source_permits_nr",
            "source_permits_total",
            "canonical_match_count",
            "status",
            "source_file",
        ]
        writer = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(antlerless)

    missing = [row["hunt_code"] for row in antlerless if row["status"] == "missing_from_canonical"]
    (AUDIT_DIR / "dwr_hunt_planner_2026_antlerless_missing_from_canonical_codes.txt").write_text(
        "\n".join(sorted(set(missing))),
        encoding="utf-8",
    )

    summary = {
        "canonical_rows": len(canonical_rows),
        "canonical_unique_hunt_codes": len(by_code),
        "antlerless_source_rows": len(antlerless),
        "antlerless_unique_hunt_codes": len({row["hunt_code"] for row in antlerless}),
        "antlerless_status_counts": dict(sorted(Counter(row["status"] for row in antlerless).items())),
        "antlerless_missing_unique_codes": len(set(missing)),
    }
    (AUDIT_DIR / "comparison_summary_after_antlerless_append.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
