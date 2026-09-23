"""Create read-only scoring projections for legacy combined-residency canonicals.

The projection is an evaluator adapter, not a truth rewrite: it expands a
frozen legacy point row's published resident/nonresident fields into two
scoring lanes and reduces forecast draw-pool labels to the legacy canonical
contract. Forecast probabilities and raw source values are not changed.
An explicit hash-linked endpoint audit can authorize filling missing observed
frequencies in the scoring projection only; empty applicant rows stay empty.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
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


def cwmu_parent_design_from_actual_fields(row: dict[str, str]) -> str:
    """Return the official parent design beneath the CWMU access overlay."""
    pool = cwmu_pool_from_actual_fields(row)
    return {
        "cwmu_antlerless_deer": "PREFERENCE_ANTLERLESS_DEER",
        "cwmu_antlerless_elk": "PREFERENCE_ANTLERLESS_ELK",
        "cwmu_doe_pronghorn": "PREFERENCE_DOE_PRONGHORN",
    }.get(pool, "BONUS_CWMU_BIG_GAME" if pool else "")


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
    return any(
        token in text
        for token in ("premium le", "premium limited entry", "premium limited-entry", "big game:premium")
    )


def verified_outcome_lines(audit_dir: Path, truth: Path, rows: list[dict[str, str]]) -> set[int]:
    """Recheck retained endpoint evidence; never trust a prior PASS label alone."""
    sys.path.insert(0, str(REPO))
    from engine.utah.quality import build_source_mapping_and_hunt_crosswalk as source

    summary = json.loads((audit_dir / 'summary.json').read_text(encoding='utf-8'))
    relative = truth.resolve().relative_to(REPO).as_posix()
    if summary['input_hashes'].get(relative) != sha256(truth):
        raise ValueError('Outcome audit does not match frozen canonical hash')
    _fields, evidence = read_csv(audit_dir / 'canonical_endpoint_probability_review.csv')
    indices, accepted, seen = {}, set(), set()
    for item in evidence:
        if item['parity'] != 'ENDPOINT_POPULATED_FIELDS_MATCH':
            continue
        line = int(item['canonical_csv_line'])
        if line in seen or not 2 <= line < len(rows) + 2:
            raise ValueError('Invalid/duplicate canonical evidence line')
        seen.add(line)
        row = rows[line - 2]
        for key in ('hunt_code', 'residency', 'points', 'source_is_youth'):
            if item[key] != row.get(key, ''):
                raise ValueError(f'Outcome evidence identity mismatch at line {line}')
        endpoint = source.local(item['endpoint'])
        if endpoint not in indices:
            digest = sha256(endpoint)
            if digest != item['endpoint_sha256'] or digest != summary['input_hashes'].get(source.rel(endpoint)):
                raise ValueError(f'Endpoint evidence hash changed: {endpoint}')
            indices[endpoint] = source.raw_endpoint_index(endpoint)
        status, _ = source.endpoint_parity(row, indices[endpoint])
        if status != 'ENDPOINT_POPULATED_FIELDS_MATCH':
            raise ValueError(f'Endpoint numeric evidence no longer matches line {line}')
        accepted.add(line)
    return accepted


def prepare_verified_outcome(row: dict[str, str]) -> dict[str, str]:
    """Observed frequency only; never called on a forecast or unaudited row."""
    item = dict(row)
    if ('point' not in clean(row.get('record_type') or row.get('row_type')).lower()
            or clean(row.get('scoring_allowed')).lower() in {'false', '0', 'no'}
            or clean(row.get('source_is_youth')).lower() not in {'true', 'false'}
            or not clean(row.get('source_file'))):
        return item
    design = clean(row.get('draw_design')).upper()
    if set(design.split('_')) & {'REFERENCE', 'AVAILABILITY', 'ALLOCATION', 'OTC'}:
        return item
    # Preserve existing explicit outcomes, including zero and malformed values
    # which require their own review. Never replace a probability to improve error.
    probability_fields = ('actual_p', 'p_draw', 'p_draw_percent', 'total_p_draw', 'total_p_draw_percent',
                          'resident_p_draw', 'resident_p_draw_percent', 'nonresident_p_draw', 'nonresident_p_draw_percent')
    if any(clean(row.get(key)) for key in probability_fields):
        return item
    counts = [number(row.get(k)) for k in ('eligible_applicants', 'bonus_permits', 'regular_permits', 'total_permits')]
    if any(n is None or not math.isfinite(n) or n < 0 or not n.is_integer() for n in counts):
        return item
    applicants, bonus, regular, awarded = counts
    if applicants <= 0 or awarded > applicants or bonus + regular != awarded:
        return item
    if clean(row.get('successful_applicants')) and number(row['successful_applicants']) != awarded:
        return item
    probability = awarded / applicants
    item['p_draw'] = f'{probability:.10f}'.rstrip('0').rstrip('.') if probability else '0'
    item['p_draw_percent'] = f'{probability * 100:.8f}'.rstrip('0').rstrip('.') if probability else '0'
    item['actual_probability_source'] = 'HASH_VERIFIED_ENDPOINT_COUNTS_AWARDS_DIVIDED_BY_APPLICANTS'
    return item


def expand_actual(rows: list[dict[str, str]], verified_lines: set[int] | None = None) -> list[dict[str, str]]:
    projected: list[dict[str, str]] = []
    for line, row in enumerate(rows, 2):
        if "POINT" not in clean(row.get("record_type") or row.get("row_type")).upper():
            continue
        # Lifetime-holder/reference rows can appear in a historical point table,
        # but are explicitly not public-draw probability rows.
        if clean(row.get("draw_design")).upper().startswith("REFERENCE_"):
            continue
        base = dict(row)
        cwmu_pool = cwmu_pool_from_actual_fields(base)
        if cwmu_pool:
            parent_design = cwmu_parent_design_from_actual_fields(base)
            base["draw_design"] = parent_design
            base["draw_system_type"] = parent_design
            base["draw_pool"] = cwmu_pool
        elif is_premium_limited_entry_actual(base):
            base["draw_design"] = "BONUS_PLE_BIG_GAME"
            base["draw_system_type"] = "BONUS_PLE_BIG_GAME"
            base["hunt_class"] = "PREMIUM_LIMITED_ENTRY"
            base["draw_pool"] = "MAX_WEIGHTED_SPLIT"
        if clean(base.get("residency")):
            if verified_lines is not None and line in verified_lines:
                base = prepare_verified_outcome(base)
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


def dedicated_pool(row: dict[str, str]) -> str:
    """Preserve the archived report/endpoint youth identity, not the code alone."""
    flag = clean(row.get('source_is_youth')).lower()
    text = ' '.join(clean(row.get(k)).lower() for k in
                    ('source_family', 'source_scope', 'source_file', 'draw_pool', 'hunt_class', 'model_strategy'))
    youth = flag == 'true' or (flag != 'false' and 'youth' in text)
    return 'youth_dedicated_hunter' if youth else 'DEDICATED_HUNTER'


def source_pool_identity(row: dict[str, str], family: str) -> str:
    """Keep an explicit source youth dimension in the evaluator's pool key."""
    if family == 'dedicated_hunter':
        return dedicated_pool(row)
    flag = clean(row.get('source_is_youth')).lower()
    text = ' '.join(clean(row.get(k)).lower() for k in
                    ('source_family', 'source_scope', 'source_file', 'draw_pool', 'hunt_class'))
    youth = flag == 'true' or (flag != 'false' and 'youth' in text)
    if not youth:
        return clean(row.get('draw_pool'))
    design = clean(row.get('draw_system_type') or row.get('draw_design')).upper()
    if family in {'bonus_turkey', 'youth_turkey'} or design == 'BONUS_TURKEY':
        return 'youth_turkey'
    if family == 'bonus_cwmu_big_game' or 'CWMU' in design:
        if clean(row.get('species')).lower() == 'turkey':
            return 'youth_cwmu_turkey'
        return clean(row.get('draw_pool'))  # species/sex/youth resolved separately
    pools = {'PREFERENCE_GENERAL_SEASON_BUCK_DEER': 'youth_general_season_deer',
             'YOUTH_GENERAL_DEER_RESERVE': 'youth_general_season_deer',
             'PREFERENCE_ANTLERLESS_DEER': 'youth_antlerless_deer',
             'PREFERENCE_ANTLERLESS_ELK': 'youth_antlerless_elk',
             'PREFERENCE_DOE_PRONGHORN': 'youth_doe_pronghorn'}
    return pools.get(design, clean(row.get('draw_pool')))


def reconcile_scoring_identities(actual, forecasts):
    """Source-only projection repair. Never select a forecast by its outcome.

    OIL/Sportsman fallback is used only when the primary owner is absent.
    An explicit blank primary also wins: a fallback must not bypass abstention.
    Other same-key conflicts fail closed rather than choosing min/max/first.
    """
    sys.path.insert(0, str(REPO))
    from tools.prediction_accuracy_backtest import score_full_engine_draw_line_aware as scorer
    projected_actual = []
    for row in actual:
        item = dict(row)
        item['draw_pool'] = source_pool_identity(item, scorer.family_from_actual(item))
        projected_actual.append(item)
    groups = defaultdict(list)
    for line, row in enumerate(forecasts, 2):
        item = dict(row)
        item['draw_pool'] = source_pool_identity(item, item.get('family', ''))
        key = scorer.prediction_alignment_key(item)[:5]
        groups[key].append((line, item))
    retained, decisions = [], []
    for key, members in groups.items():
        if len(members) == 1:
            retained.extend(members)
            continue
        if all(row == members[0][1] for _, row in members[1:]):
            retained.append(members[0])
            decisions.extend(dict(draw_design=key[0], draw_pool=key[1], hunt_code=key[2],
                residency=key[3], points=key[4], retained_csv_line=members[0][0], superseded_csv_line=n,
                retained_algorithm_status=row.get('algorithm_status', ''),
                superseded_algorithm_status=row.get('algorithm_status', ''),
                retained_official_score_key=row.get('official_score_key_v2', ''),
                superseded_official_score_key=row.get('official_score_key_v2', ''),
                reason='IDENTICAL_FINAL_RECORD_COUNTED_ONCE') for n, row in members[1:])
            continue
        owners = {'bonus_oil_big_game': 'generic_big_game_bonus', 'sportsman': 'SPORTSMAN_RANDOM_ONLY'}
        primary = [(n, r) for n, r in members if r.get('family') in owners
                   and r.get('model_strategy') == owners[r['family']]]
        fallback = [(n, r) for n, r in members if r.get('family') in owners
                    and r.get('model_strategy') == r['family'] + '_source_backed_roll_forward']
        if len(primary) != 1 or len(primary) + len(fallback) != len(members):
            raise ValueError(f'Unresolved forecast identity collision: {key}; rows {[n for n, _ in members]}')
        retained.extend(primary)
        decisions.extend(dict(draw_design=key[0], draw_pool=key[1], hunt_code=key[2],
                              residency=key[3], points=key[4], retained_csv_line=primary[0][0],
                              superseded_csv_line=n, retained_algorithm_status=primary[0][1].get('algorithm_status', ''),
                              superseded_algorithm_status=r.get('algorithm_status', ''),
                              retained_official_score_key=primary[0][1].get('official_score_key_v2', ''),
                              superseded_official_score_key=r.get('official_score_key_v2', ''),
                              reason='PRIMARY_OWNER_PRESENT_FALLBACK_NOT_APPLICABLE')
                         for n, r in fallback)
    retained.sort(key=lambda pair: pair[0])
    return projected_actual, [r for _, r in retained], decisions


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
    parser.add_argument('--verified-outcome-audit', type=Path,
                        help='Hash-linked endpoint audit required to derive missing already-split observed outcomes.')
    parser.add_argument('--reconcile-scoring-identities', action='store_true',
                        help='Keep Dedicated Hunter youth separate and suppress OIL fallback where primary exists; audit every selection.')
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
    verified_lines = verified_outcome_lines(args.verified_outcome_audit, args.frozen_truth, truth_rows) if args.verified_outcome_audit else None
    actual_projection = expand_actual(truth_rows, verified_lines)
    if any(row.get('actual_probability_source') for row in actual_projection):
        truth_fields = list(dict.fromkeys([*truth_fields, 'actual_probability_source']))
    prediction_projection = project_predictions(prediction_rows)
    identity_decisions = []
    if args.reconcile_scoring_identities:
        actual_projection, prediction_projection, identity_decisions = reconcile_scoring_identities(actual_projection, prediction_projection)
        write_csv(args.out_dir / 'forecast_identity_resolution.csv',
                  ['draw_design', 'draw_pool', 'hunt_code', 'residency', 'points', 'retained_csv_line',
                   'superseded_csv_line', 'retained_algorithm_status', 'superseded_algorithm_status',
                   'retained_official_score_key', 'superseded_official_score_key', 'reason'], identity_decisions)
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
        "observed_outcomes_derived_in_projection": sum(bool(r.get('actual_probability_source')) for r in actual_projection),
        "verified_outcome_audit": str(args.verified_outcome_audit) if args.verified_outcome_audit else None,
        "forecast_probabilities_changed": False,
        "scoring_identity_reconciliation": args.reconcile_scoring_identities,
        "superseded_fallback_rows": len(identity_decisions),
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
