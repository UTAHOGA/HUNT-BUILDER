import hashlib

import pytest

from pipeline.scripts.ingest.download_bear_turkey_pdfs import (
    existing_official_archive as find_bear_turkey_archive,
)
from pipeline.scripts.ingest.download_draw_pdfs_from_manifest import (
    existing_official_archive as find_big_game_archive,
)


@pytest.mark.parametrize("finder", [find_big_game_archive, find_bear_turkey_archive])
def test_existing_archive_is_reused_by_url_basename(tmp_path, finder):
    retained = tmp_path / "2025/pdf/draw_odds/official_dwr_archive/big_game/25_bg-odds.pdf"
    retained.parent.mkdir(parents=True)
    retained.write_bytes(b"%PDF-official")
    assert finder(tmp_path, "2025", "https://wildlife.utah.gov/pdf/bg/2025/25_bg-odds.pdf") == retained


@pytest.mark.parametrize("finder", [find_big_game_archive, find_bear_turkey_archive])
def test_conflicting_same_name_archive_copies_fail_closed(tmp_path, finder):
    for folder, data in (("big_game", b"%PDF-a"), ("legacy", b"%PDF-b")):
        retained = tmp_path / f"2025/pdf/draw_odds/official_dwr_archive/{folder}/same.pdf"
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(data)
    with pytest.raises(RuntimeError, match="Conflicting official archive"):
        finder(tmp_path, "2025", "https://wildlife.utah.gov/pdf/same.pdf")


def test_identical_same_name_archive_aliases_choose_deterministically(tmp_path):
    for folder in ("big_game", "legacy"):
        retained = tmp_path / f"2025/pdf/draw_odds/official_dwr_archive/{folder}/same.pdf"
        retained.parent.mkdir(parents=True, exist_ok=True)
        retained.write_bytes(b"%PDF-same")
    result = find_big_game_archive(tmp_path, "2025", "https://wildlife.utah.gov/pdf/same.pdf")
    assert hashlib.sha256(result.read_bytes()).hexdigest() == hashlib.sha256(b"%PDF-same").hexdigest()
