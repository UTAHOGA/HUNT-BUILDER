from engine.utah_draw_predictive.classifier import classify_runtime_row


def test_phase15_youth_coverage_fields_are_present() -> None:
    draw_only = classify_runtime_row(
        {
            "hunt_code": "EB1007",
            "hunt_name": "Draw-only Youth Any Bull/Hunters Choice Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Any Bull",
            "hunt_class": "Youth",
            "weapon": "Any Legal Weapon",
            "source_dataset": "predictive",
        }
    )
    general_youth = classify_runtime_row(
        {
            "hunt_code": "EB1011",
            "hunt_name": "Youth General Season Bull Elk",
            "species": "Elk",
            "sex_type": "Bull",
            "hunt_type": "General Season - Youth",
            "hunt_class": "General Bull",
            "weapon": "Any Legal Weapon",
            "source_dataset": "predictive",
        }
    )

    assert draw_only["draw_system_type"] == "YOUTH_GENERAL_ANY_BULL_ELK"
    assert draw_only["algorithm_status"] == "IN_SCOPE_MODEL_PENDING"
    assert draw_only["target_scope"] == "TARGET"
    assert general_youth["draw_system_type"] == "YOUTH_OTC_OR_AVAILABILITY"
    assert general_youth["algorithm_status"] == "EXCLUDED_NOT_PREDICTIVE_DRAW"
