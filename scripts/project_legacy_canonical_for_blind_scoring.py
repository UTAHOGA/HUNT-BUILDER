"""Create read-only scoring projections for legacy combined-residency canonicals.

The projection is an evaluator adapter, not a truth rewrite: it expands a
frozen legacy point row's published resident/nonresident fields into two
scoring lanes and reduces forecast draw-pool labels to the legacy canonical
contract.  Probabilities and raw source values are not changed.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def number(value: object) -> float | None:
    text = clean(value).replace(",", "")
    if not text or text.upper() in {"N/A", "NA", "TOTALS"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


def write_csv(path: Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def p_draw(row: dict[str, str], prefix: str) -> str:
    direct = number(row.get(f"{prefix}_p_draw"))
    if direct is not None and 0 <= direct <= 1:
        return f"{direct:.10f}".rstrip("0").rstrip(".")
    apps = number(row.get(f"{prefix}_eligible_applicants"))
    permits = number(row.get(f"{prefix}_total_permits"))
    if apps is None or permits is None or apps <= 0:
        return ""
    return f"{max(0.0, min(1.0, permits / apps)):.10f}".rstrip("0").rstrip(".")


def expand_actual(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    for row in rows:
        if "POINT" not in clean(row.get("record_type") or row.get("row_type")).upper():
            continue
        if clean(row.get("residency")):
            projected.append(dict(row))
            continue
        for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            apps = clean(row.get(f"{prefix}_eligible_applicants"))
            permits = clean(row.get(f"{prefix}_total_permits"))
            if number(apps) is None and number(permits) is None:
                continue
            item = dict(row)
            item["residency"] = residency
            item["metric_scope"] = residency.lower()
            item["eligible_applicants"] = apps
            item["bonus_permits"] = clean(row.get(f"{prefix}_bonus_permits"))
            item["regular_permits"] = clean(row.get(f"{prefix}_regular_permits"))
            item["total_permits"] = permits
            item["success_ratio"] = clean(row.get(f"{prefix}_success_ratio"))
            item["p_draw"] = p_draw(row, prefix)
            item["p_draw_percent"] = "" if not item["p_draw"] else f"{float(item['p_draw']) * 100:.8f}".rstrip("0").rstrip(".")
            item["successful_applicants"] = permits
            item["unsuccessful_applicants"] = ""
            projected.append(item)
    return projected


def legacy_pool(row: dict[str, str]) -> str:
    family = clean(row.get("family"))
    source_file = clean(row.get("source_file")).lower()
    if family in {"bonus_le_big_game", "bonus_ple_big_game"}:
        return "LIMITED_ENTRY"
    if family == "bonus_oil_big_game":
        return "ONCE_IN_A_LIFETIME"
    if family == "bonus_cwmu_big_game":
        return "CWMU_ANTLERLESS" if "antlerless" in source_file else "CWMU_BIG_GAME"
    if family == "preference_general_deer":
        return "GENERAL_SEASON_DEER"
    if family == "dedicated_hunter":
        return "DEDICATED_HUNTER_DEER"
    if family == "preference_antlerless_deer":
        return "ANTLERLESS_DEER"
    if family == "preference_antlerless_elk":
        return "ANTLERLESS_ELK"
    if family == "preference_doe_pronghorn":
        return "DOE_PRONGHORN"
    if family == "youth_draw":
        if "youth_any_bull_elk" in source_file:
            return "YOUTH_GENERAL_ANY_BULL_ELK"
        if "youth_general_deer" in source_file:
            return "YOUTH_GENERAL_SEASON_DEER"
        if "youth" in source_file and "antlerless" in source_file:
            species = clean(row.get("species")).lower()
            return "YOUTH_ANTLERLESS_ELK" if species == "elk" else "YOUTH_ANTLERLESS_DEER"
    return clean(row.get("draw_pool"))


def project_predictions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["draw_pool"] = legacy_pool(item)
        output.append(item)
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-truth", type=Path, required=True)
    parser.add_argument("--frozen-forecast", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    truth_fields, truth_rows = read_csv(args.frozen_truth)
    prediction_fields, prediction_rows = read_csv(args.frozen_forecast)
    actual_projection = expand_actual(truth_rows)
    prediction_projection = project_predictions(prediction_rows)
    actual_path = args.out_dir / "2018_frozen_actual_residency_scoring_projection.csv"
    prediction_path = args.out_dir / "2017_to_2018_frozen_forecast_legacy_pool_scoring_projection.csv"
    write_csv(actual_path, truth_fields, actual_projection)
    write_csv(prediction_path, prediction_fields, prediction_projection)
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "purpose": "read_only_legacy_canonical_scoring_adapter",
        "frozen_truth": str(args.frozen_truth).replace("\\", "/"),
        "frozen_truth_sha256": sha256(args.frozen_truth),
        "frozen_forecast": str(args.frozen_forecast).replace("\\", "/"),
        "frozen_forecast_sha256": sha256(args.frozen_forecast),
        "actual_projection_rows": len(actual_projection),
        "actual_projection_sha256": sha256(actual_path),
        "forecast_projection_rows": len(prediction_projection),
        "forecast_projection_sha256": sha256(prediction_path),
        "actual_residency_rows": dict(Counter(clean(row.get("residency")) for row in actual_projection)),
        "forecast_legacy_pool_rows": dict(Counter(clean(row.get("draw_pool")) for row in prediction_projection)),
        "truth_values_changed": False,
        "forecast_probabilities_changed": False,
        "status": "READ_ONLY_SCORING_PROJECTION_READY",
    }
    (args.out_dir / "scoring_projection_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
