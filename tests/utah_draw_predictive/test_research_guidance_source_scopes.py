import pytest

from scripts.build_certified_research_contract_candidate import (
    PROTECTED_DRAW_PERMIT_QUOTA_FIELDS, attach_source_scopes, sanitize_public_row,
)


@pytest.mark.parametrize('status', ['', 'INSUFFICIENT_EVIDENCE', 'EXPERIMENTAL_NOT_CERTIFIED',
                                    'PROVISIONALLY_VALIDATED_LIMITED_EVIDENCE', 'CERTIFIED'])
def test_unsupported_guidance_removed_without_changing_facts(status):
    row = {field: f'retained-{field}' for field in PROTECTED_DRAW_PERMIT_QUOTA_FIELDS}
    row.update(hunt_code='BR1013', residency='Resident', prediction_certification_status=status,
               projected_draw_line_2026=2, trend='GREEN', draw_outlook='STRONG', gap=-1,
               projected_draw_line_2025=3, harvest_success_pct='61.2', hunter_satisfaction='4.1')
    result = sanitize_public_row(row)
    for field in PROTECTED_DRAW_PERMIT_QUOTA_FIELDS:
        assert result[field] == row[field]
    for field in ('projected_draw_line_2026', 'trend', 'gap', 'draw_outlook'):
        assert field not in result
    for field in ('projected_draw_line_2025', 'harvest_success_pct', 'hunter_satisfaction'):
        assert result[field] == row[field]


@pytest.mark.parametrize('probability', ['0', '0.005', '0.5', '0.995', '1'])
def test_certified_core_probability_and_guidance_unchanged(probability):
    row = dict(hunt_code='DB1510', residency='Nonresident', prediction_certification_status='CERTIFIED',
               certified_p_draw_mean=probability, projected_draw_line_2026='2', trend='GREEN')
    assert sanitize_public_row(row) == row


def test_composite_labels_preserve_catalog_and_historical_lineage_separately():
    detail = dict(source_authority='DATABASE.csv', source_file='2026/DATABASE.csv',
                  candidate_frozen_prediction_sha256='recorded-hash',
                  research_summary_rows=[{'source_file': '2025 Black Bear Draw odds.pdf'}],
                  research_ladder_rows=[{'source_file': '2026/DATABASE.csv'}])
    result = attach_source_scopes(sanitize_public_row(detail))
    assert result['source_authority'] == 'FIELD_SCOPED_RESEARCH_COMPOSITE'
    provenance = result['source_provenance']
    assert provenance['current_catalog']['source_file'] == '2026/DATABASE.csv'
    assert provenance['historical_draw_results']['recorded_source_files'] == ['2025 Black Bear Draw odds.pdf']
    assert provenance['future_predictions']['artifact_sha256'] == 'recorded-hash'
    assert attach_source_scopes(result) == result
    assert attach_source_scopes({})['source_provenance']['historical_draw_results']['lineage_status'] == 'NOT_PRESENT_IN_THIS_PAYLOAD'
