from __future__ import annotations

from engine.utah.models import Hunt, Quota, UtahRuleConfig
from engine.utah.quota_forecast import forecast_quota
from engine.utah.rules import derive_quota


def test_quota_approved_overrides_forecast():
    forecast = forecast_quota(10, approved_quota=12, proposed_quota=8, trend_pct=0.25)
    assert forecast.quota_mean == 12.0
    assert forecast.quota_source == "approved"


def test_derived_bonus_quota_uses_total_when_missing():
    hunt = Hunt(hunt_code="DB1001", species="mule deer", hunt_type="limited_entry", rule_system="bonus")
    quota = Quota(draw_year=2026, hunt_code="DB1001", species="mule deer", total_public_permits=10, quota_source="forecast")
    resolved = derive_quota(quota, hunt, UtahRuleConfig.default())
    assert resolved.reserved_quota == 5
    assert resolved.random_quota == 5


def test_derived_bonus_quota_rounds_odd_permit_to_max_pool():
    hunt = Hunt(hunt_code="DB1001", species="mule deer", hunt_type="limited_entry", rule_system="bonus")
    quota = Quota(draw_year=2026, hunt_code="DB1001", species="mule deer", total_public_permits=3, quota_source="forecast")
    resolved = derive_quota(quota, hunt, UtahRuleConfig.default())
    assert resolved.reserved_quota == 2
    assert resolved.random_quota == 1


def test_youth_reserve_applies_to_general_season_deer_only():
    quota = Quota(draw_year=2026, hunt_code="DB1501", species="mule deer", total_public_permits=100, quota_source="forecast")

    deer = Hunt(hunt_code="DB1501", species="mule deer", hunt_type="general_season", rule_system="preference")
    elk = Hunt(hunt_code="EB1007", species="elk", hunt_type="general_season", rule_system="preference")

    assert derive_quota(quota, deer, UtahRuleConfig.default()).youth_reserved_quota == 20
    assert derive_quota(quota, elk, UtahRuleConfig.default()).youth_reserved_quota is None


def test_youth_reserve_applies_to_antlerless_deer_elk_and_doe_pronghorn_only():
    config = UtahRuleConfig.default()
    valid_species = ("deer", "elk", "pronghorn")

    for species in valid_species:
        hunt = Hunt(hunt_code="TEST", species=species, hunt_type="antlerless", rule_system="preference")
        quota = Quota(draw_year=2026, hunt_code="TEST", species=species, total_public_permits=50, quota_source="forecast")
        assert derive_quota(quota, hunt, config).youth_reserved_quota == 10

    moose = Hunt(hunt_code="MB1001", species="moose", hunt_type="antlerless", rule_system="bonus")
    quota = Quota(draw_year=2026, hunt_code="MB1001", species="moose", total_public_permits=50, quota_source="forecast")
    assert derive_quota(quota, moose, config).youth_reserved_quota is None


def test_turkey_bonus_quota_does_not_get_twenty_percent_youth_reserve():
    hunt = Hunt(hunt_code="TK1003", species="turkey", hunt_type="limited_entry", rule_system="bonus")
    quota = Quota(draw_year=2026, hunt_code="TK1003", species="turkey", total_public_permits=20, quota_source="forecast")

    resolved = derive_quota(quota, hunt, UtahRuleConfig.default())

    assert resolved.reserved_quota == 10
    assert resolved.random_quota == 10
    assert resolved.youth_reserved_quota is None
