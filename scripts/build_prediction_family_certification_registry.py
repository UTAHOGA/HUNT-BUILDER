#!/usr/bin/env python3
"""Build a compact per-design certification registry from a frozen review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any


REPO = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = REPO / "audits" / "prediction_blind_year_to_year" / "frozen_canonical_long_2017_2025_deterministic_20260906_current_identity_audited_bg_bear_subtype_reporting" / "acceptance_review"
DEFAULT_OUTPUT = REPO / "governance" / "prediction-family-certification.json"

CERTIFIED = "CERTIFIED"
EXPERIMENTAL = "EXPERIMENTAL_NOT_CERTIFIED"
INSUFFICIENT = "INSUFFICIENT_EVIDENCE"

INSUFFICIENT_FAILURES = {
    "INSUFFICIENT_INDEPENDENT_FOLDS",
    "INSUFFICIENT_JOINED_ROWS",
    "UNCLASSIFIED_ACTUAL_GAPS_NOT_REPORTED",
}


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def relative_or_absolute(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(REPO).as_posix()
    except ValueError:
        return str(resolved)


def number(value: object) -> float | None:
    try:
        return float(clean(value))
    except ValueError:
        return None


def integer(value: object) -> int | None:
    parsed = number(value)
    return int(parsed) if parsed is not None and parsed.is_integer() else None


def gate_failures(row: dict[str, str], thresholds: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    fold_count = integer(row.get("fold_count"))
    joined_rows = integer(row.get("joined_rows"))
    mae = number(row.get("mae"))
    p90 = number(row.get("p90_absolute_error"))
    tail = number(row.get("tail_error_rate_over_25pp"))
    false_guarantees = integer(row.get("false_guarantee_rows"))

    if fold_count is None or fold_count < int(thresholds["minimum_independent_following_year_folds"]):
        failures.append("INSUFFICIENT_INDEPENDENT_FOLDS")
    if joined_rows is None or joined_rows < int(thresholds["minimum_joined_rows_per_design"]):
        failures.append("INSUFFICIENT_JOINED_ROWS")
    if mae is None or mae > float(thresholds["maximum_mae"]):
        failures.append("MAE_EXCEEDS_LIMIT")
    if p90 is None or p90 > float(thresholds["maximum_p90_absolute_error"]):
        failures.append("P90_ERROR_EXCEEDS_LIMIT")
    if tail is None or tail > float(thresholds["maximum_tail_error_rate_over_25pp"]):
        failures.append("TAIL_ERROR_RATE_EXCEEDS_LIMIT")
    if false_guarantees is None or false_guarantees > int(thresholds["maximum_false_guarantee_rows"]):
        failures.append("FALSE_GUARANTEE")

    # Older reviews declared this gate but did not report it by design.  Such
    # evidence can remain useful development evidence, but it cannot produce a
    # machine-certified family.
    if "unclassified_actual_gap_rows" not in row:
        failures.append("UNCLASSIFIED_ACTUAL_GAPS_NOT_REPORTED")
    else:
        gaps = integer(row.get("unclassified_actual_gap_rows"))
        if gaps is None or gaps > int(thresholds["required_unclassified_actual_gaps"]):
            failures.append("UNCLASSIFIED_ACTUAL_GAPS")
    return failures


def certification_status(failures: list[str]) -> str:
    if not failures:
        return CERTIFIED
    if any(failure in INSUFFICIENT_FAILURES for failure in failures):
        return INSUFFICIENT
    return EXPERIMENTAL


def build_registry(review_dir: Path) -> dict[str, Any]:
    csv_path = review_dir / "acceptance_by_draw_design.csv"
    manifest_path = review_dir / "acceptance_review_manifest.json"
    if not csv_path.exists() or not manifest_path.exists():
        raise FileNotFoundError(f"Acceptance review is incomplete: {review_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    thresholds = manifest.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("Acceptance review manifest has no thresholds.")
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    families: dict[str, dict[str, Any]] = {}
    for row in rows:
        design = clean(row.get("draw_design"))
        if not design or design in families:
            raise ValueError(f"Invalid or duplicate certification design: {design!r}")
        failures = gate_failures(row, thresholds)
        recomputed_acceptance = "ACCEPTED" if not failures else "NOT_ACCEPTED"
        # A legacy review can say ACCEPTED while omitting a newly enforced gate;
        # that is evidence incompleteness, not evidence tampering.  All other
        # disagreements stop the registry build.
        reported = clean(row.get("acceptance_status"))
        legacy_gap_only = failures == ["UNCLASSIFIED_ACTUAL_GAPS_NOT_REPORTED"] and reported == "ACCEPTED"
        if reported and reported != recomputed_acceptance and not legacy_gap_only:
            raise ValueError(
                f"Review acceptance status disagrees with recomputed gates for {design}: "
                f"reported={reported} recomputed={recomputed_acceptance} failures={failures}"
            )
        status = certification_status(failures)
        families[design] = {
            "certification_status": status,
            "evidence_sufficiency": "SUFFICIENT" if not any(item in INSUFFICIENT_FAILURES for item in failures) else "INSUFFICIENT",
            "fold_count": integer(row.get("fold_count")),
            "joined_rows": integer(row.get("joined_rows")),
            "mae": number(row.get("mae")),
            "p90_absolute_error": number(row.get("p90_absolute_error")),
            "tail_error_rate_over_25pp": number(row.get("tail_error_rate_over_25pp")),
            "false_guarantee_rows": integer(row.get("false_guarantee_rows")),
            "unclassified_actual_gap_rows": integer(row.get("unclassified_actual_gap_rows")) if "unclassified_actual_gap_rows" in row else None,
            "failure_reasons": ";".join(failures),
        }

    certified = sorted(design for design, evidence in families.items() if evidence["certification_status"] == CERTIFIED)
    return {
        "schema_version": "prediction-family-certification.v1",
        "registry_id": f"adr-0006-{sha256(csv_path)[:12]}",
        "certification_standard": clean(manifest.get("acceptance_standard")),
        "thresholds": thresholds,
        "evidence": {
            "acceptance_by_draw_design": relative_or_absolute(csv_path),
            "acceptance_by_draw_design_sha256": sha256(csv_path),
            "acceptance_review_manifest": relative_or_absolute(manifest_path),
            "acceptance_review_manifest_sha256": sha256(manifest_path),
        },
        "families": dict(sorted(families.items())),
        "certified_designs": certified,
        "overall_certification_status": "CERTIFIED" if families and len(certified) == len(families) else "NOT_CERTIFIED",
        "publication_policy": "Only certified_p_draw fields from CERTIFIED designs may be presented as certified future draw probability.",
        "line_semantics": "projected_draw_line fields are structural forecasts and never guarantees of a future draw.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    review_dir = args.review_dir if args.review_dir.is_absolute() else REPO / args.review_dir
    output = args.output if args.output.is_absolute() else REPO / args.output
    payload = build_registry(review_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "output": output.resolve().relative_to(REPO).as_posix(),
        "registry_id": payload["registry_id"],
        "certified_designs": payload["certified_designs"],
        "overall_certification_status": payload["overall_certification_status"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
