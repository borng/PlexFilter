"""Unit tests for the PlexAutoSkip JSON generator."""

import json

import pytest

import plexfilter.config
import plexfilter.database
from plexfilter.database import get_db, init_db
from plexfilter.services import profiles
from plexfilter.services.generator import Generator


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    """Create a temp DB and patch the plexautoskip output path."""
    db_path = str(tmp_path / "test.db")
    json_path = str(tmp_path / "custom.json")
    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.config.settings, "plexautoskip_json_path", json_path)
    init_db()


def _seed(profile_filters=None):
    """Insert a library row, match, 3 tags, and a profile. Return profile id."""
    if profile_filters is None:
        profile_filters = {"Language": True, "Violence": True, "Nudity": True}

    db = get_db()
    try:
        db.execute(
            """INSERT INTO library (plex_key, title, tmdb_id, media_type)
               VALUES (?, ?, ?, ?)""",
            ("100", "Test Movie", "55555", "movie"),
        )
        db.execute(
            """INSERT INTO matches (library_id, vidangel_work_id, tag_set_id,
                                    match_method, tag_count)
               VALUES (?, ?, ?, ?, ?)""",
            (1, 9999, 5000, "tmdb", 3),
        )
        db.execute(
            """INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                 category_name, category_group, description,
                                 type, start_sec, end_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1001, 5000, 10, "f-word", "Language", "f-word usage", "audio", 30.0, 31.0),
        )
        db.execute(
            """INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                 category_name, category_group, description,
                                 type, start_sec, end_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1002, 5000, 20, "Gore", "Violence", "graphic gore", "audiovisual", 60.0, 65.0),
        )
        db.execute(
            """INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                 category_name, category_group, description,
                                 type, start_sec, end_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (1003, 5000, 30, "Female Nudity", "Nudity", "nudity scene", "visual", 120.0, 130.0),
        )
        db.commit()
    finally:
        db.close()

    row = profiles.create("Kids", filters=profile_filters, mode="skip")
    return row["id"]


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_generate_json():
    """Output should contain tmdb://55555 with 3 segments."""
    profile_id = _seed()
    gen = Generator()
    output = gen.generate(profile_id)

    assert "tmdb://55555" in output
    assert len(output["tmdb://55555"]) == 3


def test_audio_tags_get_volume_mode():
    """Audio-type tags (f-word) should have mode 'volume'."""
    profile_id = _seed()
    gen = Generator()
    output = gen.generate(profile_id)

    segments = output["tmdb://55555"]
    audio_seg = [s for s in segments if s["start"] == 30000]
    assert len(audio_seg) == 1
    assert audio_seg[0]["mode"] == "volume"


def test_visual_tags_get_skip_mode():
    """Audiovisual-type tags (gore) should have mode 'skip'."""
    profile_id = _seed()
    gen = Generator()
    output = gen.generate(profile_id)

    segments = output["tmdb://55555"]
    av_seg = [s for s in segments if s["start"] == 60000]
    assert len(av_seg) == 1
    assert av_seg[0]["mode"] == "skip"


def test_merge_adjacent_segments():
    """Two audio tags within 2s gap should merge into one segment."""
    profile_id = _seed()

    # Clear existing tags and insert two close audio tags
    db = get_db()
    try:
        db.execute("DELETE FROM tags")
        db.execute(
            """INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                 category_name, category_group, description,
                                 type, start_sec, end_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (2001, 5000, 10, "f-word", "Language", "f-word #1", "audio", 30.0, 31.0),
        )
        db.execute(
            """INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                 category_name, category_group, description,
                                 type, start_sec, end_sec)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (2002, 5000, 10, "f-word", "Language", "f-word #2", "audio", 32.5, 33.0),
        )
        db.commit()
    finally:
        db.close()

    gen = Generator()
    output = gen.generate(profile_id)

    segments = output["tmdb://55555"]
    assert len(segments) == 1
    assert segments[0]["start"] == 30000
    assert segments[0]["end"] == 33000
    assert segments[0]["mode"] == "volume"


def test_write_custom_json():
    """generate_and_write should create a file with {markers: {tmdb://55555: [...]}}."""
    profile_id = _seed()
    gen = Generator()
    gen.generate_and_write(profile_id)

    with open(plexfilter.config.settings.plexautoskip_json_path) as f:
        data = json.load(f)

    assert "markers" in data
    assert "tmdb://55555" in data["markers"]
    assert len(data["markers"]["tmdb://55555"]) == 3


def test_filtered_tags_excluded():
    """With only Language=True, only the f-word tag should appear."""
    profile_id = _seed(profile_filters={"Language": True})
    gen = Generator()
    output = gen.generate(profile_id)

    segments = output["tmdb://55555"]
    assert len(segments) == 1
    assert segments[0]["start"] == 30000
    assert segments[0]["mode"] == "volume"
