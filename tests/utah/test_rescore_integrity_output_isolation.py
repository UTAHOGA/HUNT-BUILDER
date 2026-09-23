from pathlib import Path

import pytest

from scripts.verify_observed_outcome_rescore_integrity import verify


def test_integrity_rerun_preserves_existing_evidence(tmp_path: Path):
    old, new, output = (tmp_path / name for name in ('old', 'new', 'fresh'))
    new.mkdir()
    prior = new / 'projection_integrity_and_duplicate_review.json'
    prior.write_text('retained audit')
    for year in range(2017, 2026):
        parent = old / 'parallel' if year >= 2020 else old
        for base in (parent, new):
            fold = base / f'source_{year}/{year}_to_{year+1}'
            projection = fold / 'scoring_projection'
            projection.mkdir(parents=True)
            (projection / 'actual_projection.csv').write_text('hunt_code,p_draw\nDB1001,0.5\n')
            (projection / 'forecast_projection.csv').write_text('hunt_code,p_draw\nDB1001,0.4\n')
            comparison = fold / 'comparison_phase'
            comparison.mkdir()
            (comparison / 'draw_line_aware_prediction_vs_actual_rowlevel.csv').write_text('scoring_decision\n')
    before = {p: p.read_bytes() for p in tmp_path.rglob('*') if p.is_file()}
    assert verify(old, new, output) == 0
    assert all(p.read_bytes() == data for p, data in before.items())
    assert prior.read_text() == 'retained audit'
    assert (output / 'projection_integrity_and_duplicate_review.json').is_file()


@pytest.mark.parametrize('name', ['projection_integrity_and_duplicate_review.json',
                                 'repeated_structural_scoring_keys.csv'])
def test_either_existing_output_blocks_overwrite(tmp_path: Path, name):
    output = tmp_path / 'fresh'
    output.mkdir()
    retained = output / name
    retained.write_text('preserve')
    with pytest.raises(ValueError, match='overwrite'):
        verify(tmp_path / 'missing-original', tmp_path / 'missing-rescore', output)
    assert retained.read_text() == 'preserve'
