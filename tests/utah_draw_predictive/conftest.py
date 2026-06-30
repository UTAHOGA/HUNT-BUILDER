from __future__ import annotations

import pytest


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """No stale external-repo skip hook is needed after repo-local path repair."""

    return None
