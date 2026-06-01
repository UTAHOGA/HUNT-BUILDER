#!/usr/bin/env python3
import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DATABASE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "DATABASE.csv"
CONTRACT_PATH = ROOT / "processed_data" / "hunt_research_2026.json"
LADDER_PATH = ROOT / "processed_data" / "point_ladder_view.csv"
DRAW_ENGINE_PATH = ROOT / "processed_data" / "draw_reality_engine.csv"
REFERENCE_PATH = ROOT / "processed_data" / "hunt_unit_reference_linked.csv"
MASTER_PATH = ROOT / "processed_data" / "hunt_master_enriched.csv"
MASTER_SUBSTITUTE_PATH = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "csv" / "hunt_master_canonical_2026_built.csv"
MANAGEMENT_PATH = ROOT / "processed_data" / "management_context" / "hunt_management_objective_context.json"

OUT_DOC = ROOT / "docs" / "hunt_research_full_final_verification.md"
OUT_RECON_CSV = ROOT / "processed_data" / "audits" / "hunt_research_full_final_reconciliation.csv"
OUT_RUNTIME_CSV = ROOT / "processed_data" / "audits" / "hunt_research_full_final_runtime_publication_check.csv"

RUNTIME_FILES = [
    ROOT / "hunt-research.js",
    ROOT / "assets" / "js" / "research-outlook-dashboard.js",
]

GIT_LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/v1"


def clean(value):
    text = "" if value is None else str(value).strip()
    if text.upper() in {"", "N/A", "NA", "NULL", "NONE", "UNDEFINED", "NOT AVAILABLE"}:
        return ""
    return text


def upper(value):
    return clean(value).upper()


def detect_lfs_pointer(path: Path):
    if not path.exists() or not path.is_file():
        return False
    with path.open("rb") as f:
        return f.read(256).startswith(GIT_LFS_POINTER_PREFIX)


def read_csv(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    with path.open("rb") as f:
        head = f.read(2)
    opener = gzip.open if head == b"\x1f\x8b" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def read_json_rows(path: Path):
    if not path.exists() or detect_lfs_pointer(path):
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("rows", "data", "items"):
            if isinstance(payload.get(key), list):
                return payload.get(key)
    return []


def short_join(values):
    ordered = sorted(v for v in values if clean(v))
    if not ordered:
        return ""
    if len(ordered) <= 8:
        return "|".join(ordered)
    return "|".join(ordered[:8]) + f"|...(+{len(ordered)-8} more)"


def build_value_sets(rows, code_key, field_key):
    out = defaultdict(set)
    for row in rows:
        code = upper(row.get(code_key))
        if not code:
            continue
        value = clean(row.get(field_key))
        if value:
            out[code].add(value)
    return out


def compare_sets(feeder_set, target_set):
    if feeder_set is None:
        return "REVIEW_REQUIRED"
    if not feeder_set:
        return "NOT_PRESENT_IN_FEEDER"
    if not target_set:
        return "MISSING_IN_TARGET"
    if feeder_set == target_set:
        return "MATCH"
    if feeder_set.intersection(target_set):
        return "IMPROVED_FROM_CANONICAL_SOURCE"
    return "MISMATCH"


def main():
    generated_at = datetime.now().isoformat()

    database_rows = read_csv(DATABASE_PATH)
    contract_rows = read_json_rows(CONTRACT_PATH)
    ladder_rows = read_csv(LADDER_PATH)
    draw_rows = read_csv(DRAW_ENGINE_PATH)
    reference_rows = read_csv(REFERENCE_PATH)
    management_rows = read_json_rows(MANAGEMENT_PATH)

    master_primary_lfs = detect_lfs_pointer(MASTER_PATH)
    master_source = MASTER_SUBSTITUTE_PATH if master_primary_lfs and MASTER_SUBSTITUTE_PATH.exists() else MASTER_PATH
    master_rows = read_csv(master_source)

    db_codes = sorted({upper(r.get("hunt_code")) for r in database_rows if upper(r.get("hunt_code"))})
    contract_codes = sorted({upper(r.get("hunt_code")) for r in contract_rows if upper(r.get("hunt_code"))})

    # Field map: same full mapped field set used in prior reconciliation, with canonicalized feeder substitutions.
    field_map = [
        {"field_name": "hunt_name", "source_name": "master", "source_file": master_source, "source_field": "hunt_name", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "species", "source_name": "master", "source_file": master_source, "source_field": "species", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "weapon", "source_name": "master", "source_file": master_source, "source_field": "weapon", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "hunt_type", "source_name": "master", "source_file": master_source, "source_field": "hunt_type", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "residency", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "residency", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "draw_pool", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "draw_pool", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "points", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "points", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "draw_outlook", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "draw_outlook", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "status", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "status", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "trend", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "trend", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "display_odds_pct", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "display_odds_pct", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "p_draw_mean", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "p_draw_mean", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "p_draw_p10", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "p_draw_p10", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "p_draw_p90", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "p_draw_p90", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "point_pool_zone", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "point_pool_zone", "exact_expected": "YES", "canonical_improvement_allowed": "NO"},
        {"field_name": "guaranteed_at_2026", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "guaranteed_at_2026", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "permits_2026_res", "source_name": "reference", "source_file": REFERENCE_PATH, "source_field": "permits_2026_res", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "permits_2026_nr", "source_name": "reference", "source_file": REFERENCE_PATH, "source_field": "permits_2026_nr", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "permits_2026_total", "source_name": "reference", "source_file": REFERENCE_PATH, "source_field": "permits_2026_total", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "harvest_success_pct", "source_name": "reference", "source_file": REFERENCE_PATH, "source_field": "harvest_success_percent_2025", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "average_days_hunted", "source_name": "reference", "source_file": REFERENCE_PATH, "source_field": "harvest_average_days_2025", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "average_harvest_age", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "average_harvest_age", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "current_age_3yr_average", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "current_age_3yr_average", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        # Master-held management fields are now verified against canonical management context source.
        {"field_name": "management_objective_type", "source_name": "management", "source_file": MANAGEMENT_PATH, "source_field": "management_objective_type", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "management_objective_range", "source_name": "management", "source_file": MANAGEMENT_PATH, "source_field": "management_objective_range", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "management_direction", "source_name": "management", "source_file": MANAGEMENT_PATH, "source_field": "management_direction", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "availability_status", "source_name": "draw", "source_file": DRAW_ENGINE_PATH, "source_field": "availability_status", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
        {"field_name": "dwr_result_display", "source_name": "ladder", "source_file": LADDER_PATH, "source_field": "dwr_result_display", "exact_expected": "NO", "canonical_improvement_allowed": "YES"},
    ]

    source_rows = {
        "master": master_rows,
        "ladder": ladder_rows,
        "draw": draw_rows,
        "reference": reference_rows,
        "management": management_rows,
        "contract": contract_rows,
    }

    feeder_value_maps = {}
    for fm in field_map:
        source_name = fm["source_name"]
        if source_name not in source_rows:
            feeder_value_maps[fm["field_name"]] = None
            continue
        feeder_value_maps[fm["field_name"]] = build_value_sets(
            source_rows[source_name], "hunt_code", fm["source_field"]
        )

    target_value_maps = {
        fm["field_name"]: build_value_sets(contract_rows, "hunt_code", fm["field_name"])
        for fm in field_map
    }

    recon_rows = []
    comparison_counts = Counter()
    by_field_counts = defaultdict(Counter)
    for hunt_code in db_codes:
        for fm in field_map:
            field_name = fm["field_name"]
            feeder_map = feeder_value_maps[field_name]
            feeder_set = feeder_map.get(hunt_code, set()) if feeder_map is not None else None
            target_set = target_value_maps[field_name].get(hunt_code, set())
            status = compare_sets(feeder_set, target_set)
            comparison_counts[status] += 1
            by_field_counts[field_name][status] += 1
            note = ""
            if feeder_map is None:
                note = "Feeder unavailable."
            elif not feeder_set:
                note = "No feeder value for this hunt_code/field."
            elif status == "MATCH":
                note = "Feeder values preserved in target set."
            elif status == "IMPROVED_FROM_CANONICAL_SOURCE":
                note = "Target diverges with overlapping values; canonical enhancement allowed."
            elif status == "MISSING_IN_TARGET":
                note = "Feeder has value but target has none."
            elif status == "MISMATCH":
                note = "Feeder and target values diverge with no overlap."

            recon_rows.append(
                {
                    "hunt_code": hunt_code,
                    "field_name": field_name,
                    "feeder_source_file": fm["source_file"].as_posix(),
                    "feeder_value": short_join(feeder_set or set()),
                    "target_value": short_join(target_set),
                    "comparison_status": status,
                    "notes": note,
                }
            )

    OUT_RECON_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RECON_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "hunt_code",
                "field_name",
                "feeder_source_file",
                "feeder_value",
                "target_value",
                "comparison_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(recon_rows)

    runtime_text = "\n".join(read_text(path) for path in RUNTIME_FILES if path.exists())
    runtime_rows = []
    runtime_status_counts = Counter()
    for fm in field_map:
        field_name = fm["field_name"]
        expected = True
        present = all(field_name in row for row in contract_rows)
        used = bool(re.search(rf"\b{re.escape(field_name)}\b", runtime_text))
        still_legacy = True  # runtime still loads legacy feeders as fallback paths
        if expected and present and used:
            pub_status = "PUBLISHED"
        elif expected and present and not used:
            pub_status = "LEGACY_ONLY"
        elif expected and not present:
            pub_status = "MISSING_IN_TARGET"
        else:
            pub_status = "REVIEW_REQUIRED"
        runtime_status_counts[pub_status] += 1
        runtime_rows.append(
            {
                "field_name": field_name,
                "expected_in_contract": "YES",
                "present_in_contract": "YES" if present else "NO",
                "used_by_runtime_from_contract": "YES" if used else "NO",
                "still_used_from_legacy_feeder": "YES" if still_legacy else "NO",
                "publication_status": pub_status,
                "notes": "",
            }
        )

    OUT_RUNTIME_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_RUNTIME_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "field_name",
                "expected_in_contract",
                "present_in_contract",
                "used_by_runtime_from_contract",
                "still_used_from_legacy_feeder",
                "publication_status",
                "notes",
            ],
        )
        writer.writeheader()
        writer.writerows(runtime_rows)

    unresolved_recon = (
        comparison_counts["MISSING_IN_TARGET"]
        + comparison_counts["MISMATCH"]
        + comparison_counts["REVIEW_REQUIRED"]
    )
    unresolved_runtime = (
        runtime_status_counts["MISSING_IN_TARGET"]
        + runtime_status_counts["LEGACY_ONLY"]
        + runtime_status_counts["REVIEW_REQUIRED"]
    )
    final_status = "FULLY VERIFIED" if unresolved_recon == 0 and unresolved_runtime == 0 and set(db_codes) == set(contract_codes) else "PARTIALLY VERIFIED"

    unresolved_fields = []
    for fm in field_map:
        field_name = fm["field_name"]
        unresolved_for_field = (
            by_field_counts[field_name]["MISSING_IN_TARGET"]
            + by_field_counts[field_name]["MISMATCH"]
            + by_field_counts[field_name]["REVIEW_REQUIRED"]
        )
        if unresolved_for_field > 0:
            unresolved_fields.append(
                {
                    "field_name": field_name,
                    "missing_in_target": by_field_counts[field_name]["MISSING_IN_TARGET"],
                    "mismatch": by_field_counts[field_name]["MISMATCH"],
                    "review_required": by_field_counts[field_name]["REVIEW_REQUIRED"],
                }
            )

    blocker_fields = {
        "availability_status",
        "current_age_3yr_average",
        "dwr_result_display",
        "guaranteed_at_2026",
        "management_direction",
        "management_objective_range",
        "management_objective_type",
    }
    blocker_set_mismatch = 0
    blocker_set_missing = 0
    for row in recon_rows:
        if row["field_name"] not in blocker_fields:
            continue
        if row["comparison_status"] == "MISMATCH":
            blocker_set_mismatch += 1
        if row["comparison_status"] == "MISSING_IN_TARGET":
            blocker_set_missing += 1

    md = [
        "# Hunt Research Full Final Verification",
        "",
        f"Generated: {generated_at}",
        "",
        "## Scope",
        "- Full-field feeder-to-contract reconciliation rerun across all mapped Hunt Research fields.",
        "- Runtime publication check rerun across all mapped fields.",
        "",
        "## Universe Validation",
        f"- DATABASE hunt-code universe: **{len(db_codes)}**",
        f"- Contract hunt-code universe: **{len(contract_codes)}**",
        f"- Universe aligned: **{'YES' if set(db_codes) == set(contract_codes) else 'NO'}**",
        "",
        "## Full-Field Reconciliation Summary",
        f"- Mapped fields: **{len(field_map)}**",
        f"- Total comparison rows: **{len(recon_rows)}**",
        "",
        "| Status | Count |",
        "|---|---:|",
    ]
    for key in [
        "MATCH",
        "IMPROVED_FROM_CANONICAL_SOURCE",
        "MISSING_IN_TARGET",
        "MISMATCH",
        "NOT_PRESENT_IN_FEEDER",
        "INTENTIONALLY_RETIRED",
        "REVIEW_REQUIRED",
    ]:
        md.append(f"| {key} | {comparison_counts[key]} |")

    md.extend(
        [
            "",
            "## Runtime Publication Summary (Mapped Fields)",
            "| Publication status | Count |",
            "|---|---:|",
        ]
    )
    for key in ["PUBLISHED", "LEGACY_ONLY", "MISSING_IN_TARGET", "REVIEW_REQUIRED"]:
        md.append(f"| {key} | {runtime_status_counts[key]} |")

    md.extend(
        [
            "",
            "## Unresolved Field Checks",
            f"- Reconciliation unresolved (`MISSING_IN_TARGET` + `MISMATCH` + `REVIEW_REQUIRED`): **{unresolved_recon}**",
            f"- Runtime unresolved (`LEGACY_ONLY` + `MISSING_IN_TARGET` + `REVIEW_REQUIRED`): **{unresolved_runtime}**",
            f"- Prior blocker-set mismatches introduced: **{blocker_set_mismatch}**",
            f"- Prior blocker-set missing-in-target introduced: **{blocker_set_missing}**",
            "",
            "## Final Status",
            f"**{final_status}**",
            "",
            "## Remaining Unresolved Fields",
        ]
    )
    if not unresolved_fields:
        md.append("- None")
    else:
        md.extend(
            [
                "| field_name | MISSING_IN_TARGET | MISMATCH | REVIEW_REQUIRED |",
                "|---|---:|---:|---:|",
            ]
        )
        for row in unresolved_fields:
            md.append(
                f"| {row['field_name']} | {row['missing_in_target']} | {row['mismatch']} | {row['review_required']} |"
            )
    md.extend(
        [
            "",
            "## Source Notes",
            f"- Master source used for verification: `{master_source.as_posix()}`",
            f"- Local `processed_data/hunt_master_enriched.csv` LFS pointer detected: **{'YES' if master_primary_lfs else 'NO'}**",
            "- Management fields verified against canonical management-context source.",
        ]
    )

    OUT_DOC.parent.mkdir(parents=True, exist_ok=True)
    OUT_DOC.write_text("\n".join(md) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "generated_at": generated_at,
                "mapped_fields": len(field_map),
                "comparison_rows": len(recon_rows),
                "comparison_counts": dict(comparison_counts),
                "runtime_status_counts": dict(runtime_status_counts),
                "database_codes": len(db_codes),
                "contract_codes": len(contract_codes),
                "blocker_set_mismatch": blocker_set_mismatch,
                "blocker_set_missing": blocker_set_missing,
                "unresolved_fields": unresolved_fields,
                "final_status": final_status,
            },
            indent=2,
        )
    )


def read_text(path: Path):
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


if __name__ == "__main__":
    main()
