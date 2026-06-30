from __future__ import annotations

from pathlib import Path

import pytest


OLD_HUNTS_REPO_MARKERS = (
    r"C:\Users\tyler\Desktop\GitHub\HUNTS",
    r"C:\\Users\\tyler\\Desktop\\GitHub\\HUNTS",
)


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Keep this suite repo-only by deferring stale tests tied to the old HUNTS repo."""

    for item in items:
        path = Path(str(item.fspath))
        try:
            source = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            source = path.read_text(encoding="utf-8-sig", errors="ignore")
        if any(marker in source for marker in OLD_HUNTS_REPO_MARKERS):
            item.add_marker(
                pytest.mark.skip(
                    reason=(
                        "Deferred stale artifact test: it depends on the old HUNTS processed_data "
                        "path and needs a repo-side fixture or regenerated HUNT-BUILDER artifact."
                    )
                )
            )
