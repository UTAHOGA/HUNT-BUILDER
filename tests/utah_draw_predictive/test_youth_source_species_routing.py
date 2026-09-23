"""Explicit source species must outrank the shared reserve display label."""
import pytest

from engine.utah_draw_predictive.run_all_families import _youth_draw_pool_for_row


@pytest.mark.parametrize('species,code,pool', [
    ('Deer', 'DA1000', 'youth_antlerless_deer'),
    ('Elk', 'EA1000', 'youth_antlerless_elk'),
    ('Pronghorn', 'PD1000', 'youth_doe_pronghorn'),
])
def test_official_species_outranks_generic_antlerless_doe_label(species, code, pool):
    row = dict(species=species, hunt_code=code, source_is_youth='true',
               hunt_type='Youth Antlerless/Doe Reserve', draw_pool='youth',
               draw_design='YOUTH_ANTLERLESS_OR_DOE_RESERVE')
    assert _youth_draw_pool_for_row(row) == pool


def test_doe_deer_text_is_not_a_pronghorn_identity():
    row = dict(species='', hunt_code='DA1000', hunt_name='Youth antlerless doe deer',
               draw_pool='youth', draw_design='YOUTH_ANTLERLESS_OR_DOE_RESERVE')
    assert _youth_draw_pool_for_row(row) == 'youth_antlerless_deer'
