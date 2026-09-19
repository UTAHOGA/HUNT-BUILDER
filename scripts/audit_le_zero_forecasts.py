"""Retain every LE zero/positive error; diagnose without changing scored rows.

The requested six-way taxonomy is retained verbatim as a diagnostic hypothesis.
Its final catch-all is NOT proof of a zero-demand defect: positive-demand,
one-permit max-pool forecasts can legitimately have zero modeled probability.
"""
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from engine.utah_draw_predictive.run_all_families import _prepare_big_game_bonus_history_rows

OUT = ROOT / "audits/prediction_release_candidates/core_le_deer_repair_20260919"
CANON = ROOT / "data_truth/draw_results_truth/normalized/canonical_yearly"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def number(value):
    try:
        return float(str(value).replace(",", ""))
    except (ValueError, TypeError):
        return None


def key(row):
    return row.get("hunt_code"), row.get("residency"), row.get("points")


def source_index(year):
    path = CANON / f"draw_results_{year}_for_{year+1}_canonical_yearly_draw_results.csv"
    rows = _prepare_big_game_bonus_history_rows(read(path))
    points = defaultdict(list)
    lanes = defaultdict(dict)
    for row in rows:
        if not str(row.get("points", "")).isdigit():
            continue
        points[key(row)].append(row)
        lane = key(row)[:2]
        point = str(row["points"])
        value = number(row.get("total_permits"))
        if point in lanes[lane] and lanes[lane][point] != value:
            raise ValueError(f"Conflicting official awards: {year}:{lane}:{point}")
        lanes[lane][point] = value
    totals = {k: sum(v or 0 for v in d.values()) for k, d in lanes.items()}
    return points, totals, path


def lineage(rows):
    return sorted({(r.get("source_file", ""), r.get("pdf_page", ""), r.get("source_dataset", "")) for r in rows})


def lineage_ok(rows):
    return bool(rows) and all(file and (page or dataset.startswith("UTAHDRAWS_")) for file, page, dataset in lineage(rows))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    output, deer, inputs = [], [], {}
    for year in range(2017, 2026):
        source, source_totals, source_path = source_index(year)
        target, target_totals, target_path = source_index(year + 1)
        fold = OUT / f"historical_folds/{year}_to_{year+1}"
        prediction_path = fold / "prediction_phase/final_public_predictions.csv"
        predictions = read(prediction_path)
        by_key = defaultdict(list)
        for p in predictions:
            by_key[key(p)].append(p)
        scored_path = fold / "comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv"
        for path in (source_path, target_path, prediction_path, scored_path):
            with path.open("rb") as handle:
                inputs[str(path.relative_to(ROOT))] = hashlib.file_digest(handle, "sha256").hexdigest()
        for score in read(scored_path):
            if score["draw_design_key"] == "PREFERENCE_GENERAL_SEASON_BUCK_DEER" and score["scoring_decision"] == "score_probability":
                deer.append(score)
            if score["draw_design_key"] != "BONUS_LE_BIG_GAME" or number(score["predicted_probability"]) != 0 or (number(score["actual_probability"]) or 0) <= 0:
                continue
            identity = key(score)
            selected = [p for p in by_key[identity] if p["draw_system_type"] == "BONUS_LE_BIG_GAME"]
            if len(selected) != 1:
                raise ValueError(f"Ambiguous forecast key {year}:{identity}")
            p = selected[0]
            src = source.get(identity, [])
            tgt = target.get(identity, [])
            lane = identity[:2]
            source_quota, target_quota = source_totals.get(lane), target_totals.get(lane)
            primary = [r for r in by_key[identity] if r.get("model_strategy") == "generic_big_game_bonus"]
            emitted = bool(primary)
            fallback = p.get("algorithm_status") == "MODELED_SOURCE_BACKED_ROLL_FORWARD"
            quota = number(p.get("quota_2026_total"))
            # Fallback public_permits_target is a POINT AWARD annotation, not
            # the input to its copied source probability. Do not misdiagnose it
            # as a zero lane quota fed into the cohort engine.
            quota_type = "OFFICIAL_CANONICAL" if not fallback else "ZERO_FALLBACK" if number(p.get("public_permits_target")) == 0 else "OFFICIAL_CANONICAL"
            category = "COHORT_ENGINE_ZERO_DEMAND_FAILURE"
            if not lineage_ok(src) or not lineage_ok(tgt):
                category = "INSUFFICIENT_OFFICIAL_LINEAGE"
            elif lane not in source_totals:
                category = "NEW_OR_UNCOMPARABLE_OFFICIAL_LANE"
            elif not source_quota and target_quota:
                category = "TARGET_YEAR_OFFICIAL_PROGRAM_OR_QUOTA_CHANGE"
            elif source_quota and number(p.get("public_permits_target")) == 0 and quota_type != "OFFICIAL_CANONICAL":
                category = "SOURCE_PROXY_QUOTA_FAILURE"
            elif primary and fallback:
                category = "SOURCE_TO_ENGINE_IDENTITY_OR_KEY_MISMATCH"
            if fallback:
                finding = "SOURCE_PROBABILITY_FALLBACK_ERROR_POINT_AWARD_IS_NOT_LANE_QUOTA"
                if primary:
                    finding = "SOURCE_DESIGN_DIFFERS_FROM_PRIMARY_FAMILY"
            elif quota == source_quota and number(p.get("forecast_applicants_at_level")) and number(p.get("quota_2026_random_pool")) == 0:
                finding = "POSITIVE_COHORT_ZERO_RANDOM_POOL_BELOW_PROJECTED_MAX_CUTOFF"
            else:
                finding = "RETAINED_NUMERIC_FORECAST_ERROR"
            result = {
                "source_year": year, "target_year": year + 1, "hunt_code": identity[0], "residency": identity[1],
                "point_level": identity[2], "draw_pool": score["draw_pool_key"],
                "predicted_probability": score["predicted_probability"], "target_official_p": score["actual_probability"],
                "scoring_decision": score["scoring_decision"], "remains_in_frozen_accuracy_metrics": score["scoring_decision"] == "score_probability",
                "requested_v1_category": category, "verified_finding": finding,
                "source_official_total_permits_lane": source_quota, "target_official_total_permits_lane": target_quota,
                "hunt_code_exists_source_canonical": any(k[0] == identity[0] for k in source_totals),
                "hunt_code_exists_target_canonical": any(k[0] == identity[0] for k in target_totals),
                "residency_lane_exists_source_canonical": lane in source_totals,
                "residency_lane_exists_target_canonical": lane in target_totals,
                "hunt_code_continuity": "CONTINUOUS" if lane in source_totals else "NEW",
                "continuity_evidence_scope": "EXACT_OFFICIAL_CODE_LANE_ONLY_NOT_BOUNDARY_EQUIVALENCE",
                "quota_source_type_for_forecast": quota_type, "public_permits_target": p.get("public_permits_target"),
                "cohort_engine_lane_quota": quota, "cohort_random_pool": p.get("quota_2026_random_pool"),
                "cohort_engine_emitted_bool": emitted,
                "cohort_engine_p_draw": primary[0].get("p_draw_mean") if primary else "",
                "cohort_engine_applicant_forecast": primary[0].get("forecast_applicants_at_level") if primary else "",
                "cohort_engine_score_key": primary[0].get("official_score_key_v2") if primary else "",
                "fallback_score_key": p.get("official_score_key_v2") if fallback else "",
                "fallback_algorithm_status": p.get("algorithm_status") if fallback else "",
                "official_score_key_source": "|".join(map(str, (year, *identity))),
                "official_score_key_target": "|".join(map(str, (year + 1, *identity))),
                "source_pdf_page_lineage_present": bool(src) and all(r.get("pdf_page") for r in src),
                "target_pdf_page_lineage_present": bool(tgt) and all(r.get("pdf_page") for r in tgt),
                "source_lineage": json.dumps(lineage(src)), "target_lineage": json.dumps(lineage(tgt)),
            }
            for label, rows in (("source", src), ("target", tgt)):
                for field in ("eligible_applicants", "bonus_permits", "regular_permits"):
                    result[f"{label}_official_{'applicants' if field == 'eligible_applicants' else field}"] = rows[0].get(field) if rows else ""
            output.append(result)
    write_csv(OUT / "audit_3886_collapse_verification.csv", output)
    write_csv(OUT / "deer_9fold_final_website_calc.csv", deer)
    gaps = json.loads((OUT / "le_gap_resolution_summary.json").read_text())["resolutions"]
    exported = []
    for row in gaps:
        exported.append({"source_year": row["fold"].split("_")[0], "hunt_code": row["hunt_code"], "residency": row["residency"],
                         "points": row["points"], "p_draw": "", "algorithm_status": "NO_TRANSITION_EVIDENCE",
                         "public_permits_target": row["source_award_proxy_verified"],
                         "no_transition_reason": "Source-only replay found no carried-forward cohort at this point and no observed adjacent historical transition; one-applicant counterfactual certainty is withheld.",
                         "source_file": row["prior_year_source_file"], "pdf_page": row["prior_year_source_page"],
                         "original_algorithm_status": "NOT_SCORED_CONDITIONAL_RUNG_NO_TRANSITION_EVIDENCE",
                         "prior_year_point_applicants": row["prior_year_eligible_applicants"],
                         "prior_year_point_awards": row["prior_year_successful_applicants"],
                         "independent_evidence": json.dumps(row)})
    write_csv(OUT / "le_32_no_transition_prediction_annotations.csv", exported)
    summary = {"rows": len(output), "eight_fold_rows_2017_through_2024": sum(r["source_year"] <= 2024 for r in output),
               "claimed_prior_3886_count_reproduced": False, "prior_3886_evidence_location": "Not supplied; no causal reduction claimed",
               "current_counts_by_requested_category": dict(Counter(r["requested_v1_category"] for r in output)),
               "verified_findings": dict(Counter(r["verified_finding"] for r in output)),
               "all_errors_retained": all(r["remains_in_frozen_accuracy_metrics"] for r in output),
               "deer_scored_rows": len(deer), "annotated_intentional_blanks": len(exported),
               "warning": "The supplied classifier catch-all is a hypothesis, not proof of zero demand. No numeric errors excluded and no historic source values changed. Current freeze predates V1/V2; no quota/key repair is falsely attributed to these attachments.",
               "inputs_sha256": inputs}
    (OUT / "residual_error_audit_summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({k: v for k, v in summary.items() if k != "inputs_sha256"}, indent=2))


if __name__ == "__main__":
    main()
