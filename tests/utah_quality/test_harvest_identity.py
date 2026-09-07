from engine.utah.quality.harvest_identity import (
    harvest_identity_compatible,
    hunt_name_compatible,
    resolve_identity_match,
)


def test_hunt_name_compatibility_normalizes_expected_dwr_variants() -> None:
    assert hunt_name_compatible("Diamond Mtn Landowner Association", "Diamond Mtn")
    assert hunt_name_compatible("La Sal Mtns, North", "LaSal, Mtns-North")
    assert hunt_name_compatible("Black Hawk", "Blackhawk")
    assert hunt_name_compatible("Folley Ridge", "Folly Ridge")


def test_hunt_name_compatibility_preserves_meaningful_unit_identity() -> None:
    assert not hunt_name_compatible("Manti", "Fishlake (Conservation)")
    assert not hunt_name_compatible("Riverview Ranch LLC", "Cactus Ranch LLC")


def test_identity_requires_code_species_and_name_and_never_boundary() -> None:
    source = {
        "hunt_code": "EA1270",
        "species": "Elk",
        "hunt_name": "Manti",
        "boundary_id": "shared-boundary",
    }
    target = {
        "hunt_code": "EA1270",
        "species": "Elk",
        "hunt_name": "Fishlake (Conservation)",
        "boundary_id": "shared-boundary",
    }

    assert not harvest_identity_compatible(source, target)
    resolution = resolve_identity_match(source, [target])
    assert resolution.status == "HUNT_CODE_NAME_OR_SPECIES_MISMATCH"
