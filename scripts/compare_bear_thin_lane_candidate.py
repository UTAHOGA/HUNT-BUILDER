"""Compare an isolated Bear thin-lane candidate with an identical baseline."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def number(value: object) -> float | None:
    text = str(value or "").strip()
    return float(text) if text else None


def key(row: dict[str, str]) -> tuple[str, str, str]:
    return row["hunt_code"], row["residency"], row["points"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    args = parser.parse_args()

    differences: list[dict[str, object]] = []
    future_leaks: list[str] = []
    split_codes = {"BR7021", "BR7022", "BR7126", "BR7127", "BR7238", "BR7239", "BR7326"}
    split_numeric_rows: list[str] = []

    for candidate_fold in sorted(args.candidate.glob("20??_to_20??")):
        fold = candidate_fold.name
        baseline_fold = args.baseline / fold
        baseline_rows = {key(row): row for row in read_rows(baseline_fold / "prediction_phase/final_predictions.csv")}
        candidate_rows = {key(row): row for row in read_rows(candidate_fold / "prediction_phase/final_predictions.csv")}
        actual_rows = {key(row): row for row in read_rows(candidate_fold / "actual_projection.csv")}
        if baseline_rows.keys() != candidate_rows.keys():
            raise ValueError(f"Prediction coverage changed in {fold}")

        target_year = int(fold[-4:])
        for row_key, candidate in candidate_rows.items():
            years = [int(value) for value in candidate.get("source_years_used", "").split(",") if value]
            if any(year >= target_year for year in years):
                future_leaks.append(f"{fold}:{row_key}:{years}")
            if row_key[0] in split_codes and number(candidate.get("p_draw")) is not None:
                split_numeric_rows.append(f"{fold}:{row_key}")

            baseline = baseline_rows[row_key]
            before = number(baseline.get("p_draw"))
            after = number(candidate.get("p_draw"))
            if before is None or after is None or abs(after - before) <= 1e-12:
                continue
            actual = number(actual_rows.get(row_key, {}).get("p_draw"))
            differences.append(
                {
                    "fold": fold,
                    "draw_design": (
                        "BEAR_RESTRICTED_PURSUIT_BONUS"
                        if "PURSUIT" in candidate.get("bear_draw_subtype", "")
                        else "BEAR_LIMITED_ENTRY_HUNT_BONUS"
                    ),
                    "hunt_code": row_key[0],
                    "residency": row_key[1],
                    "points": row_key[2],
                    "forecast_quota_proxy": candidate.get("forecast_quota_proxy", ""),
                    "applicants_above": candidate.get("applicants_above", ""),
                    "applicants_at_level": candidate.get("applicants_at_level", ""),
                    "baseline_p_bonus_pool": baseline.get("p_bonus_pool", ""),
                    "candidate_p_bonus_pool": candidate.get("p_bonus_pool", ""),
                    "baseline_p_random_pool": baseline.get("p_random_pool", ""),
                    "candidate_p_random_pool": candidate.get("p_random_pool", ""),
                    "baseline_p_draw": f"{before:.6f}",
                    "candidate_p_draw": f"{after:.6f}",
                    "p_draw_delta": f"{after - before:.6f}",
                    "actual_p_draw": "" if actual is None else f"{actual:.10f}",
                    "baseline_absolute_error": "" if actual is None else f"{abs(before - actual):.10f}",
                    "candidate_absolute_error": "" if actual is None else f"{abs(after - actual):.10f}",
                    "absolute_error_delta": "" if actual is None else f"{abs(after - actual) - abs(before - actual):.10f}",
                    "source_years_used": candidate.get("source_years_used", ""),
                    "thin_nonresident_arrival_applied": candidate.get("thin_nonresident_arrival_applied", ""),
                }
            )

    write_rows(args.candidate / "thin_nonresident_p_draw_diff.csv", differences)
    summary = {
        "candidate_status": "REJECTED_NOT_CERTIFIED_DO_NOT_PROMOTE",
        "changed_probability_rows": len(differences),
        "changed_hunt_codes": sorted({row["hunt_code"] for row in differences}),
        "changed_rows_by_design": {
            design: sum(row["draw_design"] == design for row in differences)
            for design in ("BEAR_LIMITED_ENTRY_HUNT_BONUS", "BEAR_RESTRICTED_PURSUIT_BONUS")
        },
        "mean_p_draw_delta": (
            sum(float(row["p_draw_delta"]) for row in differences) / len(differences)
            if differences else 0.0
        ),
        "mean_absolute_error_delta": (
            sum(float(row["absolute_error_delta"]) for row in differences if row["absolute_error_delta"] != "")
            / sum(row["absolute_error_delta"] != "" for row in differences)
            if any(row["absolute_error_delta"] != "" for row in differences) else 0.0
        ),
        "future_year_leaks": future_leaks,
        "split_codes_with_numeric_probability": split_numeric_rows,
        "baseline_acceptance": json.loads((args.baseline / "acceptance_summary.json").read_text(encoding="utf-8")),
        "candidate_acceptance": json.loads((args.candidate / "acceptance_summary.json").read_text(encoding="utf-8")),
    }
    (args.candidate / "thin_nonresident_review.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
