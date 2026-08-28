"""Audit 2026 PDF-derived rows against retained official UtahDraws and DWR data.

This is a read-only source-lineage audit. UtahDraws is the comparison source
for applicant/success outcomes. The DWR Hunt Planner supplies official hunt
identity and current quota context, not draw-outcome truth.
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CANONICAL = ROOT / "data_truth" / "draw_results_truth" / "normalized" / "canonical_yearly" / "draw_results_2026_for_2027_canonical_yearly_draw_results.csv"
SNAPSHOT = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "2026" / "json" / "draw_results" / "utahdraws_2026_20260826" / "utahdraws_2026" / "csv" / "2026_allowed_draw_odds_all_flat_rows.csv"
PLANNER = ROOT / "pipeline" / "RAW" / "hunt_unit_database" / "_staging" / "huntplanner_popup_deep_20260826_205700" / "dwr_huntplanner_hanumber_2026.csv"
OUT_DIR = ROOT / "data_truth" / "draw_results_truth" / "validation"
OUT_CSV = OUT_DIR / "draw_2026_pdf_rows_vs_utahdraws_snapshot.csv"
OUT_JSON = OUT_DIR / "draw_2026_pdf_rows_vs_utahdraws_snapshot.json"


SPORTSMAN_ENDPOINT_BY_SPECIES = {
    "deer": "2026_sportsman_22_sportsman_deer.json",
    "elk": "2026_sportsman_23_sportsman_elk.json",
    "pronghorn": "2026_sportsman_24_sportsman_pronghorn.json",
    "moose": "2026_sportsman_25_sportsman_moose.json",
    "bison": "2026_sportsman_26_sportsman_bison.json",
    "rocky mountain bighorn sheep": "2026_sportsman_27_sportsman_rocky_mtn_bighorn_sheep.json",
    "desert bighorn sheep": "2026_sportsman_28_sportsman_desert_bighorn_sheep.json",
    "mountain goat": "2026_sportsman_29_sportsman_mountain_goat.json",
    "black bear": "2026_sportsman_30_sportsman_black_bear.json",
    "turkey": "2026_sportsman_31_sportsman_turkey.json",
}


def clean(value: object) -> str:
    return str(value or "").strip()


def points(value: object) -> str:
    text = clean(value)
    try:
        return str(int(float(text)))
    except ValueError:
        return text


def integer(value: object) -> int | None:
    text = clean(value)
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def identity(code: object, residency: object, point: object) -> tuple[str, str, str]:
    return clean(code).upper(), clean(residency).lower(), points(point)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def expected_endpoint(canonical: dict[str, str]) -> str:
    """Return the retained endpoint corresponding to the PDF source scope."""
    source = clean(canonical.get("source_file")).upper()
    ordered = (
        ("L.E. ELK", "2026_big_game_09_limited_entry_bull_elk.json"),
        ("L.E. DEER", "2026_big_game_08_limited_entry_buck_deer.json"),
        ("G.S. BUCK DEER", "2026_big_game_05_general_season_buck_deer.json"),
        ("BEAR RESTRICTED", "2026_black_bear_16_black_bear_restricted_pursuit.json"),
        ("BEAR DRAW", "2026_black_bear_01_black_bear.json"),
        ("L.E. PRONGHORN", "2026_big_game_10_limited_entry_buck_pronghorn.json"),
        ("BULL MOOSE", "2026_big_game_11_bull_moose.json"),
        ("DESERT BIGHORN", "2026_big_game_13_desert_bighorn_sheep.json"),
        ("O.I.L. BISON", "2026_big_game_12_bison.json"),
        ("D.H. DEER", "2026_big_game_32_dedicated_hunter_buck_deer.json"),
        ("MTN GOAT", "2026_big_game_15_mountain_goat.json"),
        ("ROCKY MTN", "2026_big_game_14_rocky_mtn_bighorn_sheep.json"),
        ("TURKEY DRAW", "2026_turkey_03_turkey.json"),
    )
    for phrase, endpoint in ordered:
        if phrase in source:
            return endpoint
    if "SPORTSMAN" in source:
        return SPORTSMAN_ENDPOINT_BY_SPECIES[clean(canonical.get("species")).lower()]
    raise ValueError(f"No expected UtahDraws endpoint mapping for {canonical.get('source_file')!r}")


def values_match(canonical: dict[str, str], endpoint: dict[str, str]) -> bool:
    return (
        integer(canonical.get("eligible_applicants")) == integer(endpoint.get("ParticipantCount"))
        and integer(canonical.get("successful_applicants")) == integer(endpoint.get("SuccessfulCount"))
    )


def endpoint_status(canonical: dict[str, str], matches: list[dict[str, str]]) -> tuple[str, list[dict[str, str]]]:
    """Resolve only through retained, same-package endpoint evidence."""
    if not matches:
        return "NO_EXPECTED_ENDPOINT_IDENTITY", []
    equal_value_rows = [row for row in matches if values_match(canonical, row)]
    if len(matches) == 1:
        return ("VALUE_PARITY_DIRECT" if equal_value_rows else "VALUE_MISMATCH_DIRECT"), equal_value_rows
    if len(equal_value_rows) == 1:
        return "VALUE_PARITY_UNIQUE_SOURCE_DIMENSION", equal_value_rows
    if len(equal_value_rows) > 1:
        return "AMBIGUOUS_MULTIPLE_EQUAL_ENDPOINT_ROWS", equal_value_rows
    return "AMBIGUOUS_ENDPOINT_DIMENSION_VALUE_MISMATCH", []


def certification_disposition(canonical: dict[str, str], parity_status: str) -> str:
    scorable = (integer(canonical.get("eligible_applicants")) or 0) > 0 or (integer(canonical.get("successful_applicants")) or 0) > 0
    if not scorable:
        return "UNSCORABLE_NO_APPLICANT_OR_SUCCESS"
    if parity_status in {"VALUE_PARITY_DIRECT", "VALUE_PARITY_UNIQUE_SOURCE_DIMENSION"}:
        return "CERTIFIABLE_SOURCE_VALUE_PARITY"
    return "EXCLUDE_FROM_CERTIFIABLE_SCORING_PENDING_SOURCE_RECONCILIATION"


def main() -> None:
    raw_index: dict[tuple[tuple[str, str, str], str], list[dict[str, str]]] = defaultdict(list)
    for raw in read_csv(SNAPSHOT):
        raw_index[(identity(raw.get("HuntCode"), raw.get("residency_label"), raw.get("Point")), clean(raw.get("source_json_file")))].append(raw)

    planner_index = {clean(row.get("hunt_code")).upper(): row for row in read_csv(PLANNER) if clean(row.get("fetch_status")) == "OK"}
    output: list[dict[str, str]] = []
    for canonical in read_csv(CANONICAL):
        if clean(canonical.get("source_dataset")) != "OFFICIAL_DWR_2026_PDF_DRAW_RESULTS":
            continue
        row_identity = identity(canonical.get("hunt_code"), canonical.get("residency"), canonical.get("points"))
        endpoint = expected_endpoint(canonical)
        matches = raw_index.get((row_identity, endpoint), [])
        parity_status, equal_value_rows = endpoint_status(canonical, matches)
        planner = planner_index.get(row_identity[0])
        selected = equal_value_rows[0] if len(equal_value_rows) == 1 else (matches[0] if len(matches) == 1 else None)
        scorable = (integer(canonical.get("eligible_applicants")) or 0) > 0 or (integer(canonical.get("successful_applicants")) or 0) > 0
        output.append({
            "hunt_code": row_identity[0],
            "residency": clean(canonical.get("residency")),
            "points": row_identity[2],
            "canonical_source_file": clean(canonical.get("source_file")),
            "canonical_pdf_page": clean(canonical.get("pdf_page")),
            "canonical_eligible_applicants": clean(canonical.get("eligible_applicants")),
            "canonical_successful_applicants": clean(canonical.get("successful_applicants")),
            "canonical_is_scorable": str(scorable).lower(),
            "expected_snapshot_source_json_file": endpoint,
            "snapshot_matches_in_expected_endpoint": str(len(matches)),
            "snapshot_candidate_source_dimensions": " | ".join(sorted({clean(row.get("IsYouth")) for row in matches})),
            "snapshot_participant_count": clean(selected.get("ParticipantCount")) if selected else "",
            "snapshot_successful_count": clean(selected.get("SuccessfulCount")) if selected else "",
            "snapshot_selected_is_youth": clean(selected.get("IsYouth")) if selected else "",
            "parity_status": parity_status,
            "certification_disposition": certification_disposition(canonical, parity_status),
            "planner_context_status": "DWR_PLANNER_HUNT_CODE_FOUND" if planner else "DWR_PLANNER_HUNT_CODE_NOT_IN_1433_CAPTURE",
            "planner_source_url": clean(planner.get("source_url")) if planner else "",
            "planner_res_quota": clean(planner.get("permits_2026_res")) if planner else "",
            "planner_nr_quota": clean(planner.get("permits_2026_nr")) if planner else "",
            "planner_total_quota": clean(planner.get("permits_2026_total")) if planner else "",
            "notes": (
                "UtahDraws outcome values are the parity source; DWR Planner is identity/quota context only."
                if parity_status.startswith("VALUE_PARITY")
                else "Do not use as certifiable scoring truth until source-value reconciliation is complete."
            ),
        })

    fields = list(output[0]) if output else []
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output)

    disposition_counts = Counter(row["certification_disposition"] for row in output)
    scorable_rows = [row for row in output if row["canonical_is_scorable"] == "true"]
    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_pdf_derived_rows": len(output),
        "canonical_pdf_derived_scorable_rows": len(scorable_rows),
        "certifiable_scorable_rows": disposition_counts["CERTIFIABLE_SOURCE_VALUE_PARITY"],
        "scorable_rows_excluded_pending_reconciliation": disposition_counts["EXCLUDE_FROM_CERTIFIABLE_SCORING_PENDING_SOURCE_RECONCILIATION"],
        "unscorable_zero_applicant_or_success_rows": disposition_counts["UNSCORABLE_NO_APPLICANT_OR_SUCCESS"],
        "parity_status_counts": dict(sorted(Counter(row["parity_status"] for row in output).items())),
        "certification_disposition_counts": dict(sorted(disposition_counts.items())),
        "planner_context_counts": dict(sorted(Counter(row["planner_context_status"] for row in output).items())),
        "comparison_identity": "hunt_code + residency + points + expected UtahDraws source package",
        "comparison_metrics": ["eligible_applicants == ParticipantCount", "successful_applicants == SuccessfulCount"],
        "planner_scope": "DWR Planner validates hunt identity/current quota context but is not applicant/success outcome truth.",
        "output_csv": OUT_CSV.relative_to(ROOT).as_posix(),
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
