"""Summarize isolated all-family historical runs without promoting any design."""
from __future__ import annotations

import argparse
from collections import Counter
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.build_blind_acceptance_review import (
    THRESHOLDS, build_design_rows, load_actual_gap_fold, load_draw_line_fold, read_csv,
    load_historical_truth_authority_gate, metrics, write_csv,
)
from scripts.classify_historical_actual_gaps import run as classify_gaps
from scripts.run_historical_adjacent_full_engine_scoring import canonical_actual, sha256


CANONICAL_LONG_TRUTH = (
    ROOT / "data_truth/draw_results_truth/normalized/draw_results_long.csv"
)


def resolve_gap_review_history(
    isolated_history: Path,
    canonical_long_truth: Path = CANONICAL_LONG_TRUTH,
) -> Path | None:
    """Return the retained source-only history used to replay abstentions.

    Older fold packages copied their history into ``isolated_truth``. Current
    exact-code folds read the same frozen canonical-built long truth directly
    and therefore do not create that redundant copy. Gap classification must
    still replay documented NO_TRANSITION_EVIDENCE decisions from the actual
    source history; otherwise honest first-fold blanks are mislabeled as engine
    coverage defects merely because the optional copy is absent.
    """
    if isolated_history.is_file():
        return isolated_history
    if canonical_long_truth.is_file():
        return canonical_long_truth
    return None


def write_scored_subset(path: Path, subset: list[dict], scored: list[dict]) -> None:
    if subset:
        write_csv(path, subset)
    else:
        fields = list(scored[0]) if scored else ['fold', 'draw_design', 'hunt_code',
                    'residency', 'points', 'predicted_probability', 'actual_probability']
        with path.open('w', encoding='utf-8', newline='') as handle:
            csv.DictWriter(handle, fieldnames=fields).writeheader()


def build_design_residency_rows(rows: list[dict], gaps: list[dict]) -> list[dict]:
    """Apply the frozen design gates independently to each residency lane.

    Utah's resident and nonresident applicant populations are separate model
    inputs and can have materially different forecast stability.  The existing
    design-wide result remains available, but it may not conceal a failing
    residency slice in promotion review.
    """
    slices: list[dict] = []
    residencies = sorted(
        {
            str(row.get('residency') or '').strip() or 'All'
            for row in [*rows, *gaps]
        }
    )
    for residency in residencies:
        lane_rows = [
            row for row in rows
            if (str(row.get('residency') or '').strip() or 'All') == residency
        ]
        lane_gaps = [
            row for row in gaps
            if (str(row.get('residency') or '').strip() or 'All') == residency
        ]
        for design in build_design_rows(lane_rows, lane_gaps):
            slices.append({'residency': residency, **design})
    return sorted(slices, key=lambda row: (row['draw_design'], row['residency']))


def review(base: Path, protected_baseline: Path | None = None, frozen_base: Path | None = None, review_name: str = 'review', forecast_candidate_base: Path | None = None, source_end: int = 2025) -> dict:
    if Path(review_name).name != review_name:
        raise ValueError('Review name must be a directory name, not a path')
    out = base / review_name
    if out.exists():
        raise ValueError(f'Refusing to overwrite review: {out}')
    expected = []
    if source_end not in range(2017, 2026):
        raise ValueError('source_end must be between 2017 and 2025')
    for year in range(2017, source_end + 1):
        fold = f'{year}_to_{year + 1}'
        parent = base / 'parallel' if year >= 2020 and (base / 'parallel').exists() else base
        nested_root = parent / f'source_{year}' / fold
        direct_root = parent / fold
        root = nested_root if nested_root.is_dir() else direct_root
        score = root / 'comparison_phase/draw_line_aware_prediction_vs_actual_rowlevel.csv'
        if not score.is_file():
            raise ValueError(f'Incomplete fold; no combined result: {score}')
        expected.append((year, fold, root, score))
    out.mkdir(parents=True)
    all_rows, all_gaps, gap_evidence, per_fold, per_fold_residency, gates, emissions = [], [], [], [], [], [], []
    for year, fold, root, score in expected:
        frozen_parent = frozen_base / 'parallel' if frozen_base and year >= 2020 and (frozen_base / 'parallel').exists() else frozen_base
        frozen_root = frozen_parent / f'source_{year}' / fold if frozen_parent else root
        comparison = score.parent
        gaps_path = comparison / 'draw_line_aware_actual_ladder_scoring_rows.csv'
        sidecar = comparison / 'draw_line_aware_actual_gap_classifications.csv'
        if review_name != 'review':
            sidecar = out / f'{fold}_actual_gap_classifications.csv'
        history = frozen_root.parent / 'isolated_truth/official_source_truth_combined.csv'
        history_for_review = resolve_gap_review_history(history)
        final = frozen_root / 'prediction_phase/final_public_predictions.csv'
        if forecast_candidate_base is not None:
            final = forecast_candidate_base / f'source_{year}' / fold / 'prediction_phase/final_public_predictions.csv'
            candidate_gate = json.loads((final.parent / 'candidate_freeze.json').read_text(encoding='utf-8'))
            if candidate_gate['final_sha256'] != sha256(final):
                raise ValueError(f'Candidate forecast changed after freeze: {fold}')
            if candidate_gate['source_year'] != year or candidate_gate['source_sha256'] != sha256(canonical_actual(year)):
                raise ValueError(f'Candidate source-year contract mismatch: {fold}')
        with final.open(encoding='utf-8-sig', newline='') as handle:
            inventory = Counter((r.get('family', ''), r.get('draw_system_type', ''),
                                 r.get('algorithm_status', ''), bool(r.get('p_draw', '').strip()))
                                for r in csv.DictReader(handle))
        emissions.extend({'fold': fold, 'family': family, 'draw_design': design,
                          'algorithm_status': status, 'has_probability': present,
                          'emitted_rows_not_scored_population': count}
                         for (family, design, status, present), count in sorted(inventory.items()))
        if sidecar.exists():
            raise ValueError(f'Refusing to replace classifications: {sidecar}')
        projection = json.loads((root / 'scoring_projection/scoring_projection_manifest.json').read_text(encoding='utf-8'))
        classify_gaps(canonical_actual(year), gaps_path, sidecar, year, year + 1,
                      history_truth=history_for_review,
                      frozen_predictions=final if history_for_review else None,
                      reconcile_identities=projection.get('scoring_identity_reconciliation', False))
        rows = load_draw_line_fold(fold, score)
        gaps, _ = load_actual_gap_fold(fold, gaps_path, classification_path_override=sidecar)
        gap_evidence.extend({'fold': fold, **r} for r in read_csv(sidecar))
        gate = load_historical_truth_authority_gate(fold, frozen_root / 'comparison_phase' / score.name)
        projection = json.loads((root / 'scoring_projection/scoring_projection_manifest.json').read_text(encoding='utf-8'))
        if projection['frozen_forecast_sha256'] != sha256(final):
            raise ValueError(f'Rescore changed frozen forecast: {fold}')
        gate['scoring_sha256'] = sha256(score)
        if forecast_candidate_base is not None:
            gate['scoped_candidate_freeze'] = candidate_gate
        gates.append(gate)
        all_rows.extend(rows)
        all_gaps.extend(gaps)
        for design in build_design_rows(rows, gaps):
            per_fold.append({'fold': fold, **design})
        for design in build_design_residency_rows(rows, gaps):
            per_fold_residency.append({'fold': fold, **design})
        print(json.dumps({'fold': fold, **metrics(rows),
                          'unresolved_gaps': sum(r['is_unclassified'] for r in gaps)}), flush=True)
    combined = build_design_rows(all_rows, all_gaps)
    eight_rows = [r for r in all_rows if r['fold'] != '2025_to_2026']
    eight_gaps = [r for r in all_gaps if r['fold'] != '2025_to_2026']
    write_csv(out / 'all_years_by_family.csv', combined)
    write_csv(out / 'all_years_by_family_residency.csv', build_design_residency_rows(all_rows, all_gaps))
    write_csv(out / 'year_by_year_by_family.csv', per_fold)
    write_csv(out / 'year_by_year_by_family_residency.csv', per_fold_residency)
    write_csv(out / 'eight_fold_by_family.csv', build_design_rows(eight_rows, eight_gaps))
    eight_fold_residency = build_design_residency_rows(eight_rows, eight_gaps)
    write_csv(out / 'eight_fold_by_family_residency.csv', eight_fold_residency)
    write_csv(out / 'all_scored_rows.csv', all_rows)
    write_csv(out / 'all_actual_gaps.csv', all_gaps)
    write_csv(out / 'all_actual_gap_evidence.csv', gap_evidence)
    write_csv(out / 'family_emission_inventory.csv', emissions)
    write_scored_subset(out / 'false_guarantees.csv', [r for r in all_rows if r['false_guarantee']], all_rows)
    write_scored_subset(out / 'zero_forecast_positive_actual.csv',
              [r for r in all_rows if r['predicted_probability'] == 0 and r['actual_probability'] > 0], all_rows)
    write_scored_subset(out / 'high_error_rows.csv', [r for r in all_rows if r['tail_error_over_25pp']], all_rows)
    combined_metrics = metrics(all_rows)
    summary = {
        'status': 'LOCAL_RETROSPECTIVE_SCORING_NOT_A_PROMOTION',
        'completed_folds': len(expected), 'thresholds': THRESHOLDS,
        'source_year_window': f'2017-{source_end}',
        'generated_families': sorted({r['family'] for r in emissions}),
        'combined_window_metrics': combined_metrics,
        'combined_nine_fold_metrics': combined_metrics if source_end == 2025 else None,
        'combined_nine_fold_by_family': combined,
        'eight_fold_by_family': build_design_rows(eight_rows, eight_gaps),
        'eight_fold_by_family_residency': eight_fold_residency,
        'residency_acceptance_policy': (
            'Each supported resident/nonresident lane is measured independently; '
            'a design is not fully promotion-ready while an applicable residency slice fails.'
        ),
        'per_fold_by_family': per_fold,
        'per_fold_by_family_residency': per_fold_residency,
        'unresolved_gaps': sum(r['is_unclassified'] for r in all_gaps),
        'final_calculation_gates': gates,
        'limitations': [
            'Known retrospective years, not newly unseen holdouts.',
            ('2025_to_2026 retained separately from the adopted eight-fold acceptance window.'
             if source_end == 2025 else
             'Formal review contains only the adopted 2017_to_2018 through 2024_to_2025 acceptance window.'),
            'mixed_row called for every family; historical runtime prior and harvest blend inputs unavailable and passed as None.',
            'Physical model truth inputs contain canonical years only through each source year; this run does not claim an OS-level read-access audit.',
            'No quotas or numeric errors removed to improve scores; all gap classifications retained.',
            'Existing Bear probability ceiling is not evidence that uncapped certainty risk was repaired.',
            'Resident and nonresident evidence is reported separately; combined family metrics cannot mask a failing residency lane.',
        ],
        'database_truth_runtime_registry_modified': False,
        'frozen_forecast_base': str(frozen_base) if frozen_base else None,
        'forecast_candidate_base': str(forecast_candidate_base) if forecast_candidate_base else None,
    }
    identity_audit_path = base / 'identity_integrity.json'
    if identity_audit_path.exists():
        identity_audit = json.loads(identity_audit_path.read_text(encoding='utf-8'))
        summary['identity_integrity_audit'] = str(identity_audit_path)
        summary['source_dimension_gate'] = identity_audit['source_dimension_gate']
        summary['unresolved_actual_numeric_conflicts'] = identity_audit['unresolved_actual_numeric_conflicts']
        summary['certification_decision'] = 'WITHHELD_SOURCE_GATE_AND_FAMILY_ACCEPTANCE_REQUIRED'
    if protected_baseline is not None:
        baseline = json.loads(protected_baseline.read_text(encoding='utf-8'))
        after = {name: sha256(ROOT / name) for name in baseline}
        changed = [name for name in baseline if baseline[name] != after[name]]
        verification = {'baseline': str(protected_baseline), 'before': baseline,
                        'after': after, 'changed': changed}
        (out / 'protected_file_verification.json').write_text(
            json.dumps(verification, indent=2) + '\n', encoding='utf-8')
        summary['protected_file_changes'] = changed
        if changed:
            summary['status'] = 'BLOCKED_PROTECTED_FILE_CHANGED'
            summary['database_truth_runtime_registry_modified'] = True
    (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--protected-baseline', type=Path)
    parser.add_argument('--frozen-base', type=Path, help='Reuse original forecast/history evidence for an actual-projection-only rescore.')
    parser.add_argument('--review-name', default='review')
    parser.add_argument('--forecast-candidate-base', type=Path)
    parser.add_argument('--source-end', type=int, default=2025)
    args = parser.parse_args()
    result = review(args.base, args.protected_baseline, args.frozen_base, args.review_name, args.forecast_candidate_base, args.source_end)
    print(json.dumps(result['combined_window_metrics'], indent=2))
