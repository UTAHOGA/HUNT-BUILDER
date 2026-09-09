#!/usr/bin/env python3
"""Summarize changes between two internal outfitter/unit coverage calculations."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def row_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("Species") or "").strip(),
        str(row.get("UnitCode") or "").strip(),
        str(row.get("UnitName") or "").strip(),
    )


def detail_map(row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("outfitterId") or "").strip(): item
        for item in row.get("FederalPermitCoverageDetails", [])
        if str(item.get("outfitterId") or "").strip()
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    before_path = Path(args.before)
    after_path = Path(args.after)
    output_path = Path(args.output)
    for name in ("before_path", "after_path", "output_path"):
        value = locals()[name]
        if not value.is_absolute():
            locals()[name] = ROOT / value
    before_path = before_path if before_path.is_absolute() else ROOT / before_path
    after_path = after_path if after_path.is_absolute() else ROOT / after_path
    output_path = output_path if output_path.is_absolute() else ROOT / output_path

    before = {row_key(row): row for row in read_json(before_path)}
    after = {row_key(row): row for row in read_json(after_path)}
    if set(before) != set(after):
        raise ValueError("Before/after coverage row identities differ")

    match_status_changes: list[dict[str, Any]] = []
    service_status_changes: list[dict[str, Any]] = []
    threshold_membership_changes: list[dict[str, Any]] = []
    percentage_changes: list[dict[str, Any]] = []
    for key in sorted(before):
        old = before[key]
        new = after[key]
        identity = {"species": key[0], "unitCode": key[1], "unitName": key[2]}
        if old.get("UnitBoundaryMatchStatus") != new.get("UnitBoundaryMatchStatus"):
            match_status_changes.append(
                {
                    **identity,
                    "before": old.get("UnitBoundaryMatchStatus"),
                    "after": new.get("UnitBoundaryMatchStatus"),
                    "boundaryIds": new.get("UnitBoundaryIds", []),
                }
            )
        if old.get("UnitServiceClaimStatus") != new.get("UnitServiceClaimStatus"):
            service_status_changes.append(
                {
                    **identity,
                    "before": old.get("UnitServiceClaimStatus"),
                    "after": new.get("UnitServiceClaimStatus"),
                }
            )
        old_details = detail_map(old)
        new_details = detail_map(new)
        for outfitter_id in sorted(set(old_details) | set(new_details)):
            old_detail = old_details.get(outfitter_id, {})
            new_detail = new_details.get(outfitter_id, {})
            old_qualifies = bool(old_detail.get("qualifiesAt75Percent"))
            new_qualifies = bool(new_detail.get("qualifiesAt75Percent"))
            if old_qualifies != new_qualifies:
                threshold_membership_changes.append(
                    {
                        **identity,
                        "outfitterId": outfitter_id,
                        "displayName": new_detail.get("displayName") or old_detail.get("displayName"),
                        "beforeQualifies": old_qualifies,
                        "afterQualifies": new_qualifies,
                        "beforePercent": old_detail.get("coveredUnitAreaPercent"),
                        "afterPercent": new_detail.get("coveredUnitAreaPercent"),
                    }
                )
            if old_detail and new_detail:
                old_percent = float(old_detail.get("coveredUnitAreaPercent") or 0)
                new_percent = float(new_detail.get("coveredUnitAreaPercent") or 0)
                delta = new_percent - old_percent
                if abs(delta) >= 0.00005:
                    percentage_changes.append(
                        {
                            **identity,
                            "outfitterId": outfitter_id,
                            "displayName": new_detail.get("displayName"),
                            "beforePercent": old_percent,
                            "afterPercent": new_percent,
                            "deltaPercentagePoints": round(delta, 4),
                        }
                    )

    percentage_changes.sort(key=lambda row: abs(row["deltaPercentagePoints"]), reverse=True)
    summary = {
        "before": str(before_path.relative_to(ROOT)).replace("\\", "/"),
        "after": str(after_path.relative_to(ROOT)).replace("\\", "/"),
        "coverageRows": len(after),
        "beforeExactBoundaryRows": sum(
            row.get("UnitBoundaryMatchStatus") == "MATCHED_EXACT_NAME_OR_HUNT_CODE"
            for row in before.values()
        ),
        "afterExactBoundaryRows": sum(
            row.get("UnitBoundaryMatchStatus") == "MATCHED_EXACT_NAME_OR_HUNT_CODE"
            for row in after.values()
        ),
        "boundaryMatchStatusChangeCount": len(match_status_changes),
        "boundaryMatchStatusChanges": match_status_changes,
        "unitServiceClaimStatusChangeCount": len(service_status_changes),
        "unitServiceClaimStatusChanges": service_status_changes,
        "outfitterThresholdMembershipChangeCount": len(threshold_membership_changes),
        "outfitterThresholdMembershipChanges": threshold_membership_changes,
        "coveragePercentageChangeCount": len(percentage_changes),
        "coveragePercentageChangesOver0_1Points": sum(
            abs(row["deltaPercentagePoints"]) > 0.1 for row in percentage_changes
        ),
        "maximumAbsoluteCoverageChangePoints": (
            abs(percentage_changes[0]["deltaPercentagePoints"]) if percentage_changes else 0
        ),
        "largestCoveragePercentageChanges": percentage_changes[:25],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
