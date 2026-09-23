import csv
import json

import pytest

from scripts.review_bear_foundation_restore import lineage, unique, write_diagnostics


def test_replay_duplicate_keys_fail_closed():
    row = {'hunt_code': 'BR7000', 'residency': 'Resident', 'points': '5'}
    with pytest.raises(ValueError, match='Duplicate replay key'):
        unique([row, dict(row)])


def test_residencies_remain_distinct():
    rows = [{'hunt_code': 'BR7000', 'residency': lane, 'points': '5'}
            for lane in ('Resident', 'Nonresident')]
    assert len(unique(rows)) == 2


def test_lineage_preserves_multiple_pages_and_endpoint_reference():
    rows = [{'source_file': 'official.pdf', 'pdf_page': str(page), 'source_path': 'archive/official.pdf'}
            for page in (10, 11)]
    rows.append({'source_file': 'UtahDraws endpoint', 'source_path': 'archived_endpoint.json'})
    assert len(json.loads(lineage(rows + [rows[0]]))) == 3


def test_empty_diagnostics_retain_schema_and_refuse_overwrite(tmp_path):
    path = tmp_path / 'empty.csv'
    write_diagnostics(path, [], ['hunt_code', 'residency', 'points'])
    with path.open() as stream:
        reader = csv.DictReader(stream)
        assert reader.fieldnames == ['hunt_code', 'residency', 'points']
        assert list(reader) == []
    with pytest.raises(FileExistsError):
        write_diagnostics(path, [], ['hunt_code'])
