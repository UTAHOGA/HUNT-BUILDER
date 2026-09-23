import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parents[1] / 'scripts/build-current-hunt-eligibility-2026.py'
spec = importlib.util.spec_from_file_location('current_hunt_eligibility', path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_current_evidence_not_quota_or_history_controls_selection():
    assert module.classify({'permits_2026_total': '100'}, {}, {}, {}) == 'REFERENCE_UNVERIFIED'
    assert module.classify({}, {'fetch_status': 'OK', 'hunt_year': '2026'}, {}, {}) == 'CURRENT_PLANNER'
    assert module.classify({}, {'fetch_status': 'OK', 'hunt_year': '2025'}, {}, {}) == 'REFERENCE_UNVERIFIED'


def test_retired_status_overrules_old_active_baseline():
    assert module.classify({'permit_allotment_2026_status': 'RETIRED_2026_SUCCESSOR_PD1050'}, {}, {'universe_status': 'ACTIVE_RECONCILIATION_ROW'}, {}) == 'HISTORICAL_REFERENCE'


def test_conflicting_evidence_requires_review_not_silent_inclusion():
    assert module.classify({'hunt_class': 'Discontinued No Successor'}, {'fetch_status': 'OK', 'hunt_year': '2026'}, {}, {}) == 'EVIDENCE_CONFLICT_REVIEW'


def test_manifest_reproduces_all_input_identities_without_deleting_history():
    result = module.build()
    current, archive = set(result['current_codes']), set(result['historical_reference_codes'])
    assert not current & archive
    assert current | archive == set(result['records'])
    assert 'PD1025' in archive and 'PD1050' in current
    assert 'BR7008' in archive and 'BR7022' in current
