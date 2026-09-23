from pathlib import Path
import json

import pytest

from scripts.review_all_year_family_scoring import (
    build_design_residency_rows,
    resolve_gap_review_history,
    review,
    write_scored_subset,
)
from scripts.build_blind_acceptance_review import build_design_rows


def test_incomplete_nine_fold_run_cannot_emit_combined_result(tmp_path: Path):
    with pytest.raises(ValueError, match='Incomplete fold'):
        review(tmp_path)
    assert not (tmp_path / 'review').exists()


def test_review_refuses_to_replace_previous_evidence(tmp_path: Path):
    (tmp_path / 'review').mkdir()
    retained = tmp_path / 'review/retained.txt'
    retained.write_text('preserve')
    with pytest.raises(ValueError, match='overwrite'):
        review(tmp_path)
    assert retained.read_text() == 'preserve'


def test_gap_only_family_is_not_lost_from_combined_review():
    result = build_design_rows([], [{'draw_design': 'PREFERENCE_DEDICATED_HUNTER',
                                    'fold': '2017_to_2018', 'is_unclassified': True}])
    assert len(result) == 1
    assert result[0]['joined_rows'] == 0
    assert result[0]['unclassified_actual_gap_rows'] == 1
    assert result[0]['acceptance_status'] == 'NOT_ACCEPTED'


def test_empty_error_subset_keeps_scored_schema(tmp_path: Path):
    path = tmp_path / 'empty.csv'
    write_scored_subset(path, [], [{'fold': '2017_to_2018', 'predicted_probability': 0.1}])
    assert path.read_text().strip() == 'fold,predicted_probability'


def test_residency_acceptance_slices_cannot_be_hidden_by_combined_family_result():
    rows = [
        {
            'draw_design': 'PREFERENCE_ANTLERLESS_ELK',
            'fold': '2023_to_2024',
            'residency': 'Resident',
            'predicted_probability': 0.50,
            'actual_probability': 0.49,
            'error': 0.01,
            'absolute_error': 0.01,
            'tail_error_over_25pp': False,
            'false_guarantee': False,
        },
        {
            'draw_design': 'PREFERENCE_ANTLERLESS_ELK',
            'fold': '2023_to_2024',
            'residency': 'Nonresident',
            'predicted_probability': 0.60,
            'actual_probability': 0.00,
            'error': 0.60,
            'absolute_error': 0.60,
            'tail_error_over_25pp': True,
            'false_guarantee': False,
        },
    ]

    result = build_design_residency_rows(rows, [])

    assert [(row['residency'], row['joined_rows']) for row in result] == [
        ('Nonresident', 1),
        ('Resident', 1),
    ]
    assert all(row['draw_design'] == 'PREFERENCE_ANTLERLESS_ELK' for row in result)


def test_gap_review_uses_canonical_long_truth_when_optional_copy_is_absent(tmp_path: Path):
    isolated = tmp_path / 'isolated_truth/official_source_truth_combined.csv'
    canonical = tmp_path / 'draw_results_long.csv'
    canonical.write_text('canonical source-only history\n')

    assert resolve_gap_review_history(isolated, canonical) == canonical

    isolated.parent.mkdir(parents=True)
    isolated.write_text('retained isolated history\n')
    assert resolve_gap_review_history(isolated, canonical) == isolated


@pytest.mark.parametrize('bad_contract', ['forecast_hash', 'source_year', 'source_hash'])
def test_scoped_candidate_freeze_fails_closed(tmp_path: Path, monkeypatch, bad_contract):
    import scripts.review_all_year_family_scoring as module

    # Complete score-file presence is required even to begin a nine-fold review.
    for year in range(2017, 2026):
        comparison = tmp_path / f'source_{year}/{year}_to_{year+1}/comparison_phase'
        comparison.mkdir(parents=True)
        (comparison / 'draw_line_aware_prediction_vs_actual_rowlevel.csv').write_text('header\n')
    folder = tmp_path / 'source_2017/2017_to_2018/prediction_phase'
    folder.mkdir()
    final = folder / 'final_public_predictions.csv'
    final.write_text('family\n')
    source = tmp_path / 'source.csv'
    source.write_text('source evidence\n')
    monkeypatch.setattr(module, 'canonical_actual', lambda year: source)
    freeze = dict(final_sha256=module.sha256(final), source_year=2017,
                  source_sha256=module.sha256(source))
    if bad_contract == 'forecast_hash':
        freeze['final_sha256'] = 'changed'
    elif bad_contract == 'source_year':
        freeze['source_year'] = 2018
    else:
        freeze['source_sha256'] = 'changed'
    (folder / 'candidate_freeze.json').write_text(json.dumps(freeze))
    with pytest.raises(ValueError, match='Candidate (forecast changed|source-year contract mismatch)'):
        review(tmp_path, forecast_candidate_base=tmp_path)
    assert not (tmp_path / 'review/summary.json').exists()
