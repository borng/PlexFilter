"""Unit tests for the Plex scanner service (no real Plex server needed)."""

import pytest

from plexfilter import database
from plexfilter.config import settings
from plexfilter.database import init_db
from plexfilter.services.plex_scanner import extract_guids, get_items, store_item


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Point the database at a temporary file and initialise the schema."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(settings, "database_path", db_path)
    monkeypatch.setattr(database.settings, "database_path", db_path)
    init_db()


def test_store_library_item():
    """Insert one item and verify it exists with the correct fields."""
    store_item(plex_key="/library/metadata/1", title="Inception", year=2010, tmdb_id="27205")
    rows = get_items()
    assert len(rows) == 1
    assert rows[0]["title"] == "Inception"
    assert rows[0]["tmdb_id"] == "27205"


def test_store_item_upsert():
    """Inserting the same plex_key twice should update, not duplicate."""
    store_item(plex_key="/library/metadata/2", title="Old Title", year=2020)
    store_item(plex_key="/library/metadata/2", title="New Title", year=2020)
    rows = get_items()
    assert len(rows) == 1
    assert rows[0]["title"] == "New Title"


def test_get_library_items():
    """Verify LIMIT and OFFSET pagination."""
    for i in range(5):
        store_item(plex_key=f"/library/metadata/{i}", title=f"Movie {i:02d}", year=2020 + i)

    page1 = get_items(limit=3)
    assert len(page1) == 3

    page2 = get_items(limit=3, offset=3)
    assert len(page2) == 2


def test_extract_guids():
    """Parse GUID strings into tmdb_id and imdb_id."""
    guids = ["tmdb://845783", "imdb://tt7339792", "tvdb://12345"]
    result = extract_guids(guids)
    assert result["tmdb_id"] == "845783"
    assert result["imdb_id"] == "tt7339792"
