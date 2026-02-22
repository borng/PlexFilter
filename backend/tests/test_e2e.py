"""End-to-end test: seed library -> sync with VidAngel -> create profile -> generate JSON."""

import json

import pytest

import plexfilter.config
import plexfilter.database
from plexfilter.database import get_db, init_db
from plexfilter.services.plex_scanner import store_item
from plexfilter.services.sync import SyncService
from plexfilter.services import profiles as ProfileService
from plexfilter.services.generator import Generator


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


@pytest.fixture()
def test_env(tmp_path, monkeypatch):
    """Create a temporary DB and patch both config and database settings
    so every module resolves the same paths."""
    db_path = str(tmp_path / "test.db")
    json_path = str(tmp_path / "custom.json")

    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.config.settings, "plexautoskip_json_path", json_path)

    init_db()
    return tmp_path


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_full_pipeline(test_env):
    """Exercises the entire PlexFilter pipeline end-to-end:

    1. Seed a library item via PlexScanner.store_item()
    2. Sync with VidAngel (real API) via SyncService
    3. Create a filter profile via ProfileService
    4. Generate PlexAutoSkip JSON via Generator
    5. Verify the output file structure
    """
    tmp_path = test_env

    # ── Step 1: Seed library ──────────────────────────────────────
    store_item(
        plex_key="12345",
        title="Operation Fortune: Ruse de Guerre",
        year=2023,
        tmdb_id="845783",
        imdb_id="tt7339792",
        media_type="movie",
    )

    # Verify the row landed
    db = get_db()
    row = db.execute("SELECT * FROM library WHERE plex_key = '12345'").fetchone()
    db.close()
    assert row is not None, "store_item() did not insert the library row"
    assert row["title"] == "Operation Fortune: Ruse de Guerre"
    assert row["tmdb_id"] == "845783"

    # ── Step 2: Sync with VidAngel ────────────────────────────────
    svc = SyncService()
    result = svc.sync_library_item(library_id=1)

    assert result["matched"] is True, f"Sync failed: {result}"
    assert result["tag_count"] > 100, (
        f"Expected >100 tags for this movie, got {result['tag_count']}"
    )

    # ── Step 3: Create filter profile ─────────────────────────────
    profile = ProfileService.create(
        "Family",
        filters={"Language": True, "Violence": True},
        mode="skip",
    )

    assert profile is not None, "ProfileService.create() returned None"
    assert profile["id"] > 0
    assert profile["name"] == "Family"

    # ── Step 4: Generate PlexAutoSkip JSON ────────────────────────
    gen = Generator()
    payload = gen.generate_and_write(profile_id=profile["id"])

    # ── Step 5: Verify the output file ────────────────────────────
    json_path = tmp_path / "custom.json"
    assert json_path.exists(), f"Expected output file at {json_path}"

    with open(json_path) as f:
        data = json.load(f)

    # Top-level structure
    assert "markers" in data, "Output JSON missing 'markers' key"

    markers = data["markers"]

    # At least one tmdb:// GUID key
    tmdb_keys = [k for k in markers if k.startswith("tmdb://")]
    assert len(tmdb_keys) >= 1, (
        f"Expected at least one tmdb:// key in markers, got keys: {list(markers.keys())}"
    )

    # Check that segments have the required fields with valid values
    for guid_key in tmdb_keys:
        segments = markers[guid_key]
        assert len(segments) > 0, f"No segments for {guid_key}"

        for seg in segments:
            assert "start" in seg, f"Segment missing 'start': {seg}"
            assert "end" in seg, f"Segment missing 'end': {seg}"
            assert "mode" in seg, f"Segment missing 'mode': {seg}"
            assert seg["mode"] in ("skip", "volume"), (
                f"Invalid mode '{seg['mode']}' — expected 'skip' or 'volume'"
            )
            assert isinstance(seg["start"], int), f"start should be int (ms), got {type(seg['start'])}"
            assert isinstance(seg["end"], int), f"end should be int (ms), got {type(seg['end'])}"
            assert seg["end"] >= seg["start"], (
                f"Segment end ({seg['end']}) should be >= start ({seg['start']})"
            )
