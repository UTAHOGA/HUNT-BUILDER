from tools.engine_feeder_contract import feeders_for_group


def test_engine_feeder_contract_paths_are_unique_and_nonblank():
    feeders = feeders_for_group()
    assert feeders
    keys = [(item.group, item.path) for item in feeders]
    assert all(group and path for group, path in keys)
    assert len(keys) == len(set(keys))


def test_required_contracts_declare_consumer_modules():
    for feeder in feeders_for_group():
        if feeder.required:
            assert feeder.consumer_module
