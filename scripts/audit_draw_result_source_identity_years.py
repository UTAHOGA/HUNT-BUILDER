#!/usr/bin/env python3
"""Find source-label and hunt-identity conflicts in normalized draw truth."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "audits"
    / "source_pdf_revalidation"
    / "dwr_draw_results_2017_2026_20260907"
    / "normalized_source_identity"
)


def clean(value: object) -> str:
    return str(value or "").strip()


def number(value: object) -> float:
    try:
        return float(clean(value))
    except ValueError:
        return 0.0


def source_family(value: object) -> str:
    source = clean(value).upper().replace("_", " ")
    if "COUGAR" in source:
        return "cougar"
    if "SPORTSMAN" in source:
        return "sportsman"
    if "TURKEY" in source:
        return "turkey"
    if "BEAR" in source or re.search(r"(?:^|/)\d{2} DRAWING ODDS\.PDF$", source):
        return "black_bear"
    if "YOUTH" in source and ("BULL ELK" in source or "ANY BULL ELK" in source or "YOUTH ELK" in source):
        return "youth_elk"
    if "ANTLERLESS" in source or "DOE PRONGHORN" in source:
        return "antlerless"
    if "LIFETIME" in source:
        return "lifetime_deer"
    if "YOUTH" in source and ("D.H" in source or "DEDICATED HUNTER" in source):
        return "youth_dedicated_hunter_deer"
    if "D.H" in source or "DEDICATED HUNTER" in source:
        return "dedicated_hunter_deer"
    if "YOUTH" in source and "DEER" in source:
        return "youth_general_deer"
    if (
        "GENERAL DEER" in source
        or "G.S. BUCK DEER" in source
        or "G.S. DEER" in source
        or "DEER ODDS" in source
        or "GENERAL-SEASON BUCK DEER" in source
    ) and not any(term in source for term in ("L.E.", "O.I.L.", "BIG GAME", "BG-ODDS")):
        return "adult_general_deer"
    if any(term in source for term in ("BIG GAME", "BG-ODDS", "L.E.", "O.I.L.")):
        return "limited_entry_or_oil_big_game"
    return "unclassified"


EXPECTED_PREFIXES = {
    "cougar": {"CG"},
    "turkey": {"TK"},
    "black_bear": {"BR"},
    "youth_elk": {"EB"},
    "antlerless": {"DA", "EA", "MA", "PD", "RE"},
    "lifetime_deer": {"DB"},
    "youth_dedicated_hunter_deer": {"DB"},
    "dedicated_hunter_deer": {"DB"},
    "youth_general_deer": {"DB"},
    "adult_general_deer": {"DB"},
    "limited_entry_or_oil_big_game": {"BI", "DB", "DS", "EB", "GO", "MB", "PB", "RS"},
}


def prefix(code: str) -> str:
    match = re.match(r"([A-Z]{2})", code.upper())
    return match.group(1) if match else ""


def row_issues(row: dict[str, str], family: str) -> list[str]:
    issues: list[str] = []
    code = clean(row.get("hunt_code")).upper()
    code_prefix = prefix(code)
    expected = EXPECTED_PREFIXES.get(family)
    if expected and code_prefix and code_prefix not in expected:
        issues.append("HUNT_CODE_PREFIX_CONFLICT")

    pool = clean(row.get("draw_pool")).lower()
    if family == "adult_general_deer" and pool == "youth_general_deer":
        issues.append("ADULT_DEER_SOURCE_ROUTED_TO_YOUTH_POOL")
    if family == "youth_general_deer" and pool and pool not in {
        "youth_general_deer",
        "youth_general_season_deer",
        "availability_only",
    }:
        issues.append("YOUTH_DEER_SOURCE_ROUTED_TO_NON_DEER_POOL")
    return issues


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2017)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    summaries: list[dict[str, object]] = []
    for year in range(args.start_year, args.end_year + 1):
        canonical = (
            ROOT
            / "data_truth"
            / "draw_results_truth"
            / "normalized"
            / "canonical_yearly"
            / f"draw_results_{year}_for_{year + 1}_canonical_yearly_draw_results.csv"
        )
        conflicts: list[dict[str, object]] = []
        total_rows = 0
        with canonical.open("r", encoding="utf-8-sig", newline="") as handle:
            for row_number, row in enumerate(csv.DictReader(handle), start=2):
                total_rows += 1
                family = source_family(row.get("source_file"))
                for issue in row_issues(row, family):
                    scorable = (
                        number(row.get("eligible_applicants")) > 0
                        or number(row.get("successful_applicants")) > 0
                    )
                    conflicts.append(
                        {
                            "year": year,
                            "canonical_row": row_number,
                            "issue": issue,
                            "source_family": family,
                            "source_file": clean(row.get("source_file")),
                            "hunt_code": clean(row.get("hunt_code")),
                            "hunt_name": clean(row.get("hunt_name")),
                            "species": clean(row.get("species")),
                            "points": clean(row.get("points")),
                            "residency": clean(row.get("residency")),
                            "eligible_applicants": clean(row.get("eligible_applicants")),
                            "successful_applicants": clean(row.get("successful_applicants")),
                            "draw_system_type": clean(row.get("draw_system_type")),
                            "draw_pool": clean(row.get("draw_pool")),
                            "pdf_page": clean(row.get("pdf_page")),
                            "scorable": str(scorable).lower(),
                        }
                    )

        csv_path = output_dir / f"draw_result_source_identity_conflicts_{year}.csv"
        fields = [
            "year",
            "canonical_row",
            "issue",
            "source_family",
            "source_file",
            "hunt_code",
            "hunt_name",
            "species",
            "points",
            "residency",
            "eligible_applicants",
            "successful_applicants",
            "draw_system_type",
            "draw_pool",
            "pdf_page",
            "scorable",
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(conflicts)

        summary = {
            "year": year,
            "canonical_rows": total_rows,
            "conflict_rows": len({row["canonical_row"] for row in conflicts}),
            "conflict_issue_occurrences": len(conflicts),
            "scorable_conflict_rows": len(
                {
                    row["canonical_row"]
                    for row in conflicts
                    if row["scorable"] == "true"
                }
            ),
            "conflict_hunt_codes": len({row["hunt_code"] for row in conflicts}),
            "issue_counts": dict(sorted(Counter(row["issue"] for row in conflicts).items())),
            "source_counts": dict(sorted(Counter(row["source_file"] for row in conflicts).items())),
            "conflict_csv": csv_path.relative_to(ROOT).as_posix(),
        }
        (output_dir / f"draw_result_source_identity_conflicts_{year}.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        summaries.append(summary)

    summary_path = output_dir / "draw_result_source_identity_conflicts_2017_2025.json"
    summary_path.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summaries, indent=2))


if __name__ == "__main__":
    main()
