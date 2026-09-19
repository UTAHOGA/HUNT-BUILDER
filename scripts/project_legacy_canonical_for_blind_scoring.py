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


REPO = Path(__file__).resolve().parents[1]


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


def cwmu_pool_from_actual_fields(row: dict[str, str]) -> str:
    """Resolve the official CWMU sub-pool from the actual row itself."""
    text = " ".join(
        clean(row.get(field)).lower()
        for field in ("hunt_name", "raw_hunt_name", "hunt_type", "hunt_class", "draw_system_type", "draw_pool")
    )
    if "cwmu" not in text:
        return ""
    if any(token in text for token in ("private", "landowner", "voucher")):
        return ""

    species = clean(row.get("species")).lower()
    sex = " ".join(clean(row.get(field)).lower() for field in ("sex_type", "sex", "hunt_name", "raw_hunt_name"))
    youth = clean(row.get("source_is_youth")).lower() in {"true", "1", "yes", "y"}
    antlerless = any(token in sex for token in ("antlerless", "doe", "cow", "female", "either sex"))
    male = any(token in sex for token in ("buck", "bull", "male"))

    if species == "deer":
        if youth:
            return "cwmu_youth_antlerless_deer"
        return "cwmu_antlerless_deer" if antlerless else "cwmu_big_game_deer_buck" if male else ""
    if species == "elk":
        if youth:
            return "cwmu_youth_antlerless_elk"
        return "cwmu_antlerless_elk" if antlerless else "cwmu_big_game_elk_bull" if male else ""
    if species == "pronghorn":
        if youth:
            return "cwmu_youth_doe_pronghorn"
        return "cwmu_doe_pronghorn" if antlerless else "cwmu_big_game_pronghorn_buck" if male else ""
    if species == "moose" and male:
        return "cwmu_big_game_moose_bull"
    return ""


def is_premium_limited_entry_actual(row: dict[str, str]) -> bool:
    text = " ".join(
        clean(row.get(field)).lower()
        for field in (
            "hunt_name",
            "raw_hunt_name",
            "hunt_type",
            "hunt_class",
            "hunt_draw_class",
            "draw_design",
            "draw_system_type",
            "source_file",
        )
    )
    return any(token in text for token in ("premium le", "premium limited entry", "big game:premium"))


def expand_actual(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    for row in rows:
        if "POINT" not in clean(row.get("record_type") or row.get("row_type")).upper():
            continue
        # Lifetime-holder/reference rows can appear in a historical point table,
        # but are explicitly not public-draw probability rows.
        if clean(row.get("draw_design")).upper().startswith("REFERENCE_"):
            continue
        base = dict(row)
        cwmu_pool = cwmu_pool_from_actual_fields(base)
        if cwmu_pool:
            base["draw_design"] = "BONUS_CWMU_BIG_GAME"
            base["draw_system_type"] = "BONUS_CWMU_BIG_GAME"
            base["draw_pool"] = cwmu_pool
        elif is_premium_limited_entry_actual(base):
            base["draw_design"] = "BONUS_PLE_BIG_GAME"
            base["draw_system_type"] = "BONUS_PLE_BIG_GAME"
            base["hunt_class"] = "PREMIUM_LIMITED_ENTRY"
            base["draw_pool"] = "MAX_WEIGHTED_SPLIT"
        if clean(base.get("residency")):
            projected.append(base)
            continue
        for residency, prefix in (("Resident", "resident"), ("Nonresident", "nonresident")):
            apps = clean(base.get(f"{prefix}_eligible_applicants"))
            permits = clean(base.get(f"{prefix}_total_permits"))
            if number(apps) is None and number(permits) is None:
                continue
            item = dict(base)
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
            # The legacy antlerless parser routed MA (antlerless moose) to
            # the DOE fallback. The official hunt-code prefix plus retained
            # antlerless-report scope identify this as its own bonus design.
            source_scope = clean(item.get("source_scope")).upper()
            if item["hunt_code"].upper().startswith("MA") and "ANTLERLESS" in source_scope:
                item["draw_design"] = "BONUS_ANTLERLESS_MOOSE"
                item["draw_system_type"] = "BONUS_ANTLERLESS_MOOSE"
                item["hunt_class"] = "BONUS_ANTLERLESS_MOOSE"
                item["draw_pool"] = "BONUS_ANTLERLESS_MOOSE"
            projected.append(item)
    return projected


def legacy_pool(row: dict[str, str]) -> str:
    family = clean(row.get("family"))
    source_file = clean(row.get("source_file")).lower()
    if family in {"bonus_le_big_game", "bonus_ple_big_game"}:
        # Older canonicals used LIMITED_ENTRY while the normalized series uses
        # one stable MAX_WEIGHTED_SPLIT pool for Utah's bonus/max mechanics.
        # This is an identity-label normalization only; forecast values remain
        # untouched.
        return "MAX_WEIGHTED_SPLIT"
    if family == "bonus_oil_big_game":
        return "MAX_WEIGHTED_SPLIT"
    if family == "bonus_cwmu_big_game":
        # Keep the source-year species/sex/youth pool when the family runner
        # has already resolved it.  Replacing it with a filename-level
        # CWMU_BIG_GAME/CWMU_ANTLERLESS label collapses separate official
        # ladders before the blind scorer can match them.
        explicit_pool = clean(row.get("draw_pool"))
        if explicit_pool.lower() not in {"", "standard", "cwmu", "cwmu_big_game", "cwmu_antlerless"}:
            return explicit_pool
        return "CWMU_ANTLERLESS" if "antlerless" in source_file else "CWMU_BIG_GAME"
    if family == "preference_general_deer":
        return "ADULT_GENERAL_DEER"
    if family == "dedicated_hunter":
        return "DEDICATED_HUNTER"
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
            if species == "elk":
                return "YOUTH_ANTLERLESS_ELK"
            if species == "pronghorn":
                return "YOUTH_DOE_PRONGHORN"
            return "YOUTH_ANTLERLESS_DEER"
    return clean(row.get("draw_pool"))


def project_predictions(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    output: list[dict[str, str]] = []
    for row in rows:
        item = dict(row)
        item["draw_pool"] = legacy_pool(item)
        output.append(item)
    return output


def load_reviewed_identity_crosswalk(path: Path) -> dict[str, list[dict[str, str]]]:
    """Load the audit-reviewed source-to-target hunt identity decisions."""
    _fields, rows = read_csv(path)
    required = {
        "from_hunt_code",
        "to_hunt_code",
        "transition_type",
        "applicant_stack_carry_forward_allowed",
    }
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"Reviewed identity crosswalk is missing required fields: {path}")
    by_source: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        source_code = clean(row.get("from_hunt_code")).upper()
        if source_code:
            by_source.setdefault(source_code, []).append(row)
    return by_source


def inspect_identity_crosswalk_contract(path: Path) -> dict[str, object]:
    """Determine whether a crosswalk is pre-draw certification evidence.

    Target-reviewed full crosswalks remain useful diagnostics, but only an
    exceptions-only table whose rows explicitly prohibit target-result use may
    participate in a source-only fold.
    """
    fields, rows = read_csv(path)
    pre_draw_fields = {
        "evidence_timing",
        "target_draw_results_used",
        "crosswalk_scope",
        "certification_use",
        "from_draw_year",
        "to_draw_year",
        "target_application_evidence_file",
        "target_application_evidence_sha256",
        "target_application_evidence_pages",
        "target_application_evidence_excerpt",
        "pre_draw_timing_evidence",
    }
    errors: list[str] = []
    if not rows:
        errors.append("EMPTY_CROSSWALK")
    if not pre_draw_fields.issubset(fields):
        errors.append("MISSING_PRE_DRAW_CONTRACT_FIELDS")
    if not errors:
        year_pairs = {
            (clean(row.get("from_draw_year")), clean(row.get("to_draw_year")))
            for row in rows
        }
        if len(year_pairs) != 1:
            errors.append("MIXED_YEAR_PAIRS")
        else:
            from_year, to_year = next(iter(year_pairs))
            if not from_year.isdigit() or not to_year.isdigit() or int(to_year) != int(from_year) + 1:
                errors.append("INVALID_ADJACENT_YEAR_PAIR")
            expected_name = f"pre_draw_hunt_identity_crosswalk_{from_year}_to_{to_year}.csv"
            if path.name != expected_name:
                errors.append("NONCANONICAL_PRE_DRAW_FILENAME")
        for index, row in enumerate(rows, start=2):
            if clean(row.get("evidence_timing")).upper() != "PRE_DRAW":
                errors.append(f"ROW_{index}_NOT_PRE_DRAW")
            if clean(row.get("target_draw_results_used")).upper() != "FALSE":
                errors.append(f"ROW_{index}_TARGET_RESULT_USE_NOT_PROHIBITED")
            if clean(row.get("crosswalk_scope")).upper() != "EXCEPTIONS_ONLY_PRE_DRAW":
                errors.append(f"ROW_{index}_INVALID_SCOPE")
            if clean(row.get("certification_use")).upper() != "ELIGIBLE_PRE_DRAW_IDENTITY_ONLY":
                errors.append(f"ROW_{index}_NOT_CERTIFICATION_ELIGIBLE")
            if not clean(row.get("target_application_evidence_pages")):
                errors.append(f"ROW_{index}_MISSING_EVIDENCE_PAGE")
            if not clean(row.get("target_application_evidence_excerpt")):
                errors.append(f"ROW_{index}_MISSING_EVIDENCE_EXCERPT")
            if not clean(row.get("pre_draw_timing_evidence")):
                errors.append(f"ROW_{index}_MISSING_TIMING_EVIDENCE")
            evidence_path = Path(clean(row.get("target_application_evidence_file")))
            if not evidence_path.is_absolute():
                evidence_path = REPO / evidence_path
            expected_sha = clean(row.get("target_application_evidence_sha256")).lower()
            if not evidence_path.is_file():
                errors.append(f"ROW_{index}_EVIDENCE_FILE_MISSING")
            elif not expected_sha or sha256(evidence_path) != expected_sha:
                errors.append(f"ROW_{index}_EVIDENCE_HASH_MISMATCH")
    is_pre_draw = not errors
    return {
        "crosswalk_contract": (
            "EXCEPTIONS_ONLY_PRE_DRAW" if is_pre_draw else "FULL_TARGET_REVIEWED_DIAGNOSTIC"
        ),
        "unlisted_source_code_behavior": "PASS_THROUGH" if is_pre_draw else "EXCLUDE",
        "certification_eligible": is_pre_draw,
        "target_draw_results_used": False if is_pre_draw else None,
        "crosswalk_contract_validation_errors": errors,
    }


def apply_reviewed_identity_crosswalk(
    rows: list[dict[str, str]],
    crosswalk: dict[str, list[dict[str, str]]],
    *,
    unlisted_source_code_behavior: str = "EXCLUDE",
) -> tuple[list[dict[str, str]], dict[str, object]]:
    """Carry only reviewed one-to-one identities into the target-year score.

    This is an audit projection, not a truth or model rewrite. A source hunt
    may continue only when the reviewed table explicitly says that its stack
    can carry. Splits, boundary/program changes, eliminations, unresolved
    rows, and missing decisions are excluded rather than guessed.
    """
    output: list[dict[str, str]] = []
    reason_counts: Counter[str] = Counter()
    mapped_code_counts: Counter[str] = Counter()
    passthrough_rows = 0
    for row in rows:
        source_code = clean(row.get("hunt_code")).upper()
        decisions = crosswalk.get(source_code, [])
        if not decisions and unlisted_source_code_behavior == "PASS_THROUGH":
            item = dict(row)
            item["identity_crosswalk_from_hunt_code"] = source_code
            item["identity_crosswalk_to_hunt_code"] = source_code
            item["identity_crosswalk_transition_type"] = "UNCHANGED_CODE_NO_EXCEPTION"
            item["identity_crosswalk_transition_id"] = ""
            item["identity_crosswalk_status"] = "PRE_DRAW_NO_EXCEPTION_PASS_THROUGH"
            output.append(item)
            passthrough_rows += 1
            continue
        allowed = [
            decision
            for decision in decisions
            if clean(decision.get("applicant_stack_carry_forward_allowed")).upper() == "TRUE"
            and clean(decision.get("to_hunt_code"))
        ]
        if len(allowed) != 1:
            if not decisions:
                reason = "NO_REVIEWED_CROSSWALK_DECISION"
            elif not allowed:
                transition_types = sorted({clean(item.get("transition_type")) for item in decisions})
                reason = "BLOCKED_" + "_OR_".join(transition_types)
            else:
                reason = "AMBIGUOUS_MULTIPLE_ALLOWED_SUCCESSORS"
            reason_counts[reason] += 1
            continue

        decision = allowed[0]
        target_code = clean(decision.get("to_hunt_code")).upper()
        item = dict(row)
        item["identity_crosswalk_from_hunt_code"] = source_code
        item["identity_crosswalk_to_hunt_code"] = target_code
        item["identity_crosswalk_transition_type"] = clean(decision.get("transition_type"))
        item["identity_crosswalk_transition_id"] = clean(decision.get("transition_id"))
        item["identity_crosswalk_status"] = "REVIEWED_STACK_CARRY_ALLOWED"
        item["hunt_code"] = target_code
        # This projection is scored in the legacy structural-key mode. Do not
        # leave a pre-crosswalk v2 key that still embeds the source hunt code.
        if clean(item.get("official_score_key_v2")):
            item["official_score_key_v2"] = ""
        output.append(item)
        mapped_code_counts[f"{source_code}->{target_code}"] += 1

    return output, {
        "input_prediction_rows": len(rows),
        "projected_prediction_rows": len(output),
        "excluded_prediction_rows": len(rows) - len(output),
        "passthrough_prediction_rows": passthrough_rows,
        "excluded_reason_counts": dict(sorted(reason_counts.items())),
        "mapped_code_row_counts": dict(sorted(mapped_code_counts.items())),
    }


def _single_year(rows: list[dict[str, str]], *fields: str, label: str) -> int:
    years = {
        int(clean(row.get(field)))
        for row in rows
        for field in fields
        if clean(row.get(field)).isdigit()
    }
    if len(years) != 1:
        raise ValueError(f"Expected one {label} year for scoring projection; found {sorted(years)}")
    return years.pop()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frozen-truth", type=Path, required=True)
    parser.add_argument("--frozen-forecast", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--source-year",
        type=int,
        help="Physical source draw year for the audit label. Required when the combined forecast carries mixed score-key years.",
    )
    parser.add_argument(
        "--forecast-year",
        type=int,
        help="Physical forecast draw year for the audit label. Required when the combined forecast carries mixed score-key years.",
    )
    parser.add_argument(
        "--identity-crosswalk",
        type=Path,
        help="Optional reviewed adjacent-year identity table used only to gate/remap the scoring projection.",
    )
    args = parser.parse_args()
    truth_fields, truth_rows = read_csv(args.frozen_truth)
    prediction_fields, prediction_rows = read_csv(args.frozen_forecast)
    actual_projection = expand_actual(truth_rows)
    prediction_projection = project_predictions(prediction_rows)
    identity_crosswalk_report: dict[str, object] | None = None
    identity_crosswalk_contract: dict[str, object] | None = None
    if args.identity_crosswalk is not None:
        identity_crosswalk_contract = inspect_identity_crosswalk_contract(args.identity_crosswalk)
        identity_crosswalk = load_reviewed_identity_crosswalk(args.identity_crosswalk)
        prediction_projection, identity_crosswalk_report = apply_reviewed_identity_crosswalk(
            prediction_projection,
            identity_crosswalk,
            unlisted_source_code_behavior=str(
                identity_crosswalk_contract["unlisted_source_code_behavior"]
            ),
        )
    actual_year = _single_year(truth_rows, "actual_draw_year", "draw_year", "year", label="actual draw")
    source_year = args.source_year or _single_year(prediction_rows, "source_year", label="forecast source")
    forecast_year = args.forecast_year or _single_year(prediction_rows, "forecast_year", "year", label="forecast draw")
    actual_path = args.out_dir / f"{actual_year}_frozen_actual_residency_scoring_projection.csv"
    prediction_path = args.out_dir / f"{source_year}_to_{forecast_year}_frozen_forecast_legacy_pool_scoring_projection.csv"
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
        "projection_years": {
            "source_year": source_year,
            "forecast_year": forecast_year,
            "actual_draw_year": actual_year,
        },
        "truth_values_changed": False,
        "forecast_probabilities_changed": False,
        "certification_eligible": (
            args.identity_crosswalk is None
            or bool(identity_crosswalk_contract and identity_crosswalk_contract["certification_eligible"])
        ),
        "certification_note": (
            "The exceptions-only identity table is frozen from pre-draw application guides and does not use target draw results."
            if identity_crosswalk_contract and identity_crosswalk_contract["certification_eligible"]
            else "Reviewed target-transition crosswalk is used for identity gating; this run is diagnostic and cannot itself certify the model."
            if args.identity_crosswalk is not None
            else "No target-transition identity crosswalk was used."
        ),
        "identity_crosswalk": (
            {
                "path": str(args.identity_crosswalk).replace("\\", "/"),
                "sha256": sha256(args.identity_crosswalk),
                **(identity_crosswalk_contract or {}),
                **(identity_crosswalk_report or {}),
            }
            if args.identity_crosswalk is not None
            else None
        ),
        "identity_label_overrides": {
            "actual_ma_antlerless": "BONUS_ANTLERLESS_MOOSE",
            "actual_cwmu_pool": "SPECIES_SEX_SOURCE_FIELDS",
            "forecast_youth_pronghorn_pool": "YOUTH_DOE_PRONGHORN",
        },
        "status": "READ_ONLY_SCORING_PROJECTION_READY",
    }
    (args.out_dir / "scoring_projection_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
