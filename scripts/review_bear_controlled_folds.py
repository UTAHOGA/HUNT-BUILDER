"""Hash-linked Bear-only acceptance/publication review; never promotes data."""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.audit_bear_controlled_candidates import new_directory, protected_data, pdf_lanes
from scripts.audit_bear_pdf_truth_year import digest, dump
from scripts.build_bear_pdf_history_audit import read_rows, write_rows
from scripts.build_blind_acceptance_review import THRESHOLDS
from scripts.build_prediction_family_certification_registry import build_registry
from scripts.promote_certified_prediction_candidate import validate_certification_publication_gate
from engine.utah_draw_predictive.certification import annotate_prediction_rows


def review(folds, out):
    out = new_directory(out)
    before = protected_data()
    summaries = json.loads((folds/"acceptance_summary.json").read_text())
    expected = {f"{y}_to_{y+1}" for y in range(2020, 2025)}
    if {p.name for p in folds.glob("*_to_*") if p.is_dir()} != expected:
        raise ValueError("Expected exactly the five adjacent folds")
    freezes, final_rows, diagnostics, unscorable, gap_counts = [], [], [], Counter(), Counter()
    all_actual_counts = Counter()
    cutoff_failures = Counter()
    for fold in sorted(folds.glob("*_to_*")):
        freeze = json.loads((fold/"prediction_phase/forecast_freeze.json").read_text())
        if not freeze.get("read_guard_installed_before_model_imports"):
            raise ValueError("Import-time source guard was not proven")
        for path, expected_hash in freeze["source_hashes"].items():
            if digest(ROOT/path) != expected_hash:
                raise ValueError(f"Frozen source changed: {path}")
        for field, path in (("bear_implementation_sha256", "engine/utah_draw_predictive/bear.py"),
                            ("mixed_implementation_sha256", "engine/utah_predictive_mixed/materialize.py"),
                            ("quota_implementation_sha256", "engine/utah_predictive_mixed/quota.py"),
                            ("classifier_implementation_sha256", "engine/utah_draw_predictive/classifier.py"),
                            ("historical_adapter_implementation_sha256", "engine/utah_draw_predictive/run_all_families.py"),
                            ("orchestrator_sha256", "scripts/audit_bear_controlled_candidates.py"),
                            ("scorer_sha256", "tools/prediction_accuracy_backtest/score_full_engine_draw_line_aware.py")):
            if digest(ROOT/path) != freeze[field]:
                raise ValueError(f"Implementation changed after freeze: {path}")
        freezes.append({"fold": fold.name, **freeze})
        source_year = freeze["source_year"]
        for stage in ("family", "final"):
            if digest(fold/f"prediction_phase/{stage}_predictions.csv") != freeze[f"{stage}_sha256"]:
                raise ValueError("Forecast changed after freeze")
        family = read_rows(fold/"prediction_phase/family_predictions.csv")
        final = read_rows(fold/"prediction_phase/final_predictions.csv")
        if [(r["hunt_code"], r["residency"], r["points"], r["p_draw"]) for r in family] != [
            (r["hunt_code"], r["residency"], r["points"], r["p_draw"]) for r in final]:
            raise ValueError("Final calculation changed Bear family probabilities")
        final_rows.extend(final)
        key = lambda r: (r["hunt_code"], r["residency"], r["points"])
        predictions = {key(r): r for r in family}
        if len(predictions) != len(family):
            raise ValueError("Duplicate forecast identity")
        source = pdf_lanes(source_year)
        actual = pdf_lanes(source_year+1)
        source_quota, target_quota = Counter(), Counter()
        source_points = {key(r): r for r in source}
        target_points = {key(r): r for r in actual}
        for r in source:
            source_quota[key(r)[:2]] += int(r["total_permits"])
        for r in actual:
            target_quota[key(r)[:2]] += int(r["total_permits"])
            if int(r["eligible_applicants"]) > 0 and r["observed_success_fraction"] != "":
                all_actual_counts[r["draw_pool"]] += 1
        for r in read_rows(fold/"final_comparison/draw_line_aware_actual_ladder_scoring_rows.csv"):
            unscorable[r["scoring_decision"]] += 1
        for r in read_rows(fold/"final_comparison/draw_line_aware_actual_gap_classifications.csv"):
            gap_counts[r["actual_gap_classification"] or "UNRESOLVED"] += 1
        for r in read_rows(fold/"final_comparison/draw_line_aware_prediction_vs_actual_rowlevel.csv"):
            if r["scoring_decision"] != "score_probability":
                continue
            k = key(r)
            prediction, observed = predictions[k], target_points[k]
            prior = source_points.get(k, {})
            uncapped = prediction.get("p_draw_before_existing_ceiling", "")
            if uncapped and float(uncapped) >= .999999 and float(r["actual_probability"]) < .999999:
                cutoff_failures[r["bear_draw_subtype"]] += 1
            if float(r["absolute_error"]) <= .25:
                continue
            diagnostics.append({"fold": fold.name, **r, "source_applicants_at_point": prior.get("eligible_applicants", ""),
                                "source_bonus_awards_at_point": prior.get("bonus_permits", ""),
                                "source_random_awards_at_point": prior.get("regular_permits", ""),
                                "forecast_applicants_above": prediction.get("applicants_above", ""),
                                "forecast_applicants_at_level": prediction.get("applicants_at_level", ""),
                                "source_year_awards_proxy": source_quota[k[:2]], "target_year_actual_awards": target_quota[k[:2]],
                                "later_quota_changed": source_quota[k[:2]] != target_quota[k[:2]],
                                "actual_applicants_at_level": observed["eligible_applicants"],
                                "actual_pdf": observed["source_file"], "actual_pdf_page": observed["pdf_page"],
                                "p_draw_before_existing_ceiling": uncapped,
                                "removed_from_accuracy": False})
    if any(len({f[field] for f in freezes}) != 1 for field in ("bear_implementation_sha256", "mixed_implementation_sha256")):
        raise ValueError("Model changed between folds")
    write_rows(out/"large_error_diagnostics.csv", diagnostics)
    write_rows(out/"acceptance_by_draw_design.csv", summaries["results"]["final"])
    manifest = {"acceptance_standard": "ADR-0006", "thresholds": THRESHOLDS,
                "historical_truth_authority_gate": {"status": "PASS", "fold_count": 5,
                    "historical_database_csv_read_count": 0, "database_csv_role": "CURRENT_TARGET_IDENTITY_AND_PERMIT_REFERENCE_ONLY",
                    "historical_draw_truth_role": "FROZEN_OFFICIAL_PDF_REEXTRACTIONS_NUMERICALLY_RECONCILED_TO_YEARLY_CANONICALS",
                    "folds": freezes},
                "final_probability_gate": {"status": "PASS", "entrypoint": "engine.utah_predictive_mixed.materialize.mixed_row",
                                           "contract": "BEAR_FAMILY_MECHANICS_PRESERVED_V1", "rows": len(final_rows)},
                "development_folds": ["2020_to_2021", "2021_to_2022", "2022_to_2023"],
                "untuned_evaluation_folds": ["2023_to_2024", "2024_to_2025"]}
    dump(out/"acceptance_review_manifest.json", manifest)
    registry = build_registry(out)
    dump(out/"candidate_certification_registry.json", registry)
    annotation = annotate_prediction_rows(final_rows, registry)
    write_rows(out/"publication_contract.csv", final_rows)
    publication = validate_certification_publication_gate(out/"publication_contract.csv")
    dump(out/"publication_gate.json", {**publication, "annotation": annotation,
                                      "does_not_authorize_release": True})
    report = {"release_decision": "DO_NOT_PROMOTE", "certified_bear_designs": registry["certified_designs"],
              "actual_scoreable_rows_by_program": dict(all_actual_counts),
              "actual_inventory_dispositions": dict(unscorable), "source_classified_gaps": dict(gap_counts),
              "large_error_rows": len(diagnostics),
              "large_errors_with_changed_quota": sum(r["later_quota_changed"] for r in diagnostics),
              "large_errors_with_two_or_fewer_actual_applicants": sum(int(r["actual_applicants_at_level"]) <= 2 for r in diagnostics),
              "uncapped_false_certainty_diagnostic": dict(cutoff_failures),
              "existing_099_ceiling_not_a_model_repair": True, "production_changes": False,
              "remaining_blockers": ["BEAR_ACCURACY_THRESHOLDS", "RESTRICTED_PURSUIT_EVIDENCE_BELOW_400",
                                     "SAVED_PRODUCTION_ARTIFACTS_INVALID", "PREEXISTING_PROJECT_MEMORY_FAILURES"]}
    dump(out/"release_readiness.json", report)
    after = protected_data()
    dump(out/"protected_after.json", {"files": after, "changed": [p for p in before if before[p] != after[p]]})
    if before != after:
        raise ValueError("Protected data changed")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folds", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    review(args.folds.resolve(), args.out_dir)
