"""Tests for local nudity detection fallback integration in SyncService."""

import pytest

import plexfilter.config
import plexfilter.database
from plexfilter.database import get_db, init_db
from plexfilter.services.sync import SyncService


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.config.settings, "local_detection_enabled", True)
    init_db()


def _seed_library(title: str = "Unknown Movie") -> None:
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type, media_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("k1", title, 2024, None, None, "movie", "/tmp/fake.mp4"),
        )
        db.commit()
    finally:
        db.close()


def test_falls_back_to_local_when_no_vidangel_results(monkeypatch):
    _seed_library()

    monkeypatch.setattr(
        "plexfilter.services.sync.vidangel.search_works",
        lambda *_args, **_kwargs: {"results": []},
    )

    def fake_detect(self, library_id, on_progress=None):
        return {"matched": True, "tag_count": 2, "tag_set_id": -library_id, "source": "local"}

    monkeypatch.setattr(
        "plexfilter.services.sync.LocalDetectionService.detect_library_item",
        fake_detect,
    )

    svc = SyncService()
    result = svc.sync_library_item(1)

    assert result["matched"] is True
    assert result["source"] == "local"
    assert "fallback_reason" in result


def test_returns_original_error_when_local_fallback_disabled(monkeypatch):
    _seed_library()
    monkeypatch.setattr(plexfilter.config.settings, "local_detection_enabled", False)

    monkeypatch.setattr(
        "plexfilter.services.sync.vidangel.search_works",
        lambda *_args, **_kwargs: {"results": []},
    )

    svc = SyncService()
    result = svc.sync_library_item(1)

    assert result["matched"] is False
    assert "no VidAngel results" in result["error"]


def test_fallback_surfaces_detector_failure(monkeypatch):
    _seed_library()

    monkeypatch.setattr(
        "plexfilter.services.sync.vidangel.search_works",
        lambda *_args, **_kwargs: {"results": []},
    )

    def fake_detect_fail(self, library_id, on_progress=None):
        raise RuntimeError("nudenet missing")

    monkeypatch.setattr(
        "plexfilter.services.sync.LocalDetectionService.detect_library_item",
        fake_detect_fail,
    )

    svc = SyncService()
    result = svc.sync_library_item(1)

    assert result["matched"] is False
    assert "fallback_error" in result
    assert "nudenet missing" in result["fallback_error"]
