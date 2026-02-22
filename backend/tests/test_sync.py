"""Integration tests for the sync service (hits real VidAngel API)."""

import tempfile
import os

import pytest

from plexfilter.database import get_db, init_db
from plexfilter.services.sync import SyncService


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture()
def temp_db(monkeypatch, tmp_path):
    """Create a temporary SQLite database and patch settings in both
    plexfilter.config and plexfilter.database so get_db() uses it."""
    db_path = str(tmp_path / "test_sync.db")

    import plexfilter.config
    import plexfilter.database

    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)

    init_db()
    return db_path


@pytest.fixture()
def seeded_db(temp_db):
    """Insert a known library row and return the database path."""
    db = get_db()
    db.execute(
        """
        INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("99999", "Operation Fortune: Ruse de Guerre", 2023, "845783", "tt7339792", "movie"),
    )
    db.commit()
    db.close()
    return temp_db


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_sync_single_title(seeded_db):
    """Sync library_id=1 and verify the match and tags are stored."""
    svc = SyncService()
    result = svc.sync_library_item(1)

    assert result["matched"] is True, f"Expected matched=True, got: {result}"
    assert result["tag_count"] > 50, f"Expected >50 tags, got {result['tag_count']}"
    assert result["tag_set_id"] > 0, f"Expected tag_set_id>0, got {result['tag_set_id']}"

    # Verify match row in DB
    db = get_db()
    match_row = db.execute(
        "SELECT * FROM matches WHERE library_id = 1"
    ).fetchone()
    assert match_row is not None, "No match row found for library_id=1"
    assert match_row["tag_set_id"] > 0

    # Verify tags are stored with enriched fields
    tags = db.execute(
        "SELECT * FROM tags WHERE tag_set_id = ?", (match_row["tag_set_id"],)
    ).fetchall()
    db.close()

    assert len(tags) > 50, f"Expected >50 tags in DB, got {len(tags)}"

    # Check enrichment fields are populated on at least some tags
    has_cat_name = any(t["category_name"] for t in tags)
    has_cat_group = any(t["category_group"] for t in tags)
    assert has_cat_name, "No tags have category_name populated"
    assert has_cat_group, "No tags have category_group populated"


def test_store_tags_deduplicates(seeded_db):
    """Syncing the same item twice should not duplicate matches or tags."""
    svc = SyncService()

    result1 = svc.sync_library_item(1)
    assert result1["matched"] is True

    result2 = svc.sync_library_item(1)
    assert result2["matched"] is True

    db = get_db()

    # Only 1 match row for library_id=1
    match_count = db.execute(
        "SELECT COUNT(*) as cnt FROM matches WHERE library_id = 1"
    ).fetchone()["cnt"]
    assert match_count == 1, f"Expected 1 match row, got {match_count}"

    # Tags should not be duplicated (each vidangel_id is UNIQUE)
    tag_set_id = result1["tag_set_id"]
    tag_count = db.execute(
        "SELECT COUNT(*) as cnt FROM tags WHERE tag_set_id = ?", (tag_set_id,)
    ).fetchone()["cnt"]
    db.close()

    assert tag_count == result1["tag_count"], (
        f"Tag count mismatch after double sync: DB has {tag_count}, "
        f"first sync returned {result1['tag_count']}"
    )
