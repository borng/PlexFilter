import pytest

import plexfilter.config
import plexfilter.database
from plexfilter.database import init_db
from plexfilter.services import profiles


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)
    init_db()


def test_create_profile():
    row = profiles.create("Kids", filters={"Language": True})
    assert row["id"] is not None
    assert row["name"] == "Kids"


def test_update_filters():
    row = profiles.create("Test", filters={"Language": True})
    profiles.update(row["id"], filters={"Language": True, "Language:f-word": False})
    updated = profiles.get(row["id"])
    import json
    parsed = json.loads(updated["filters"])
    assert parsed["Language"] is True
    assert parsed["Language:f-word"] is False


def test_filter_resolution_group_enabled():
    tag = {"id": 1, "category_name": "f-word", "category_group": "Language"}
    filters = {"Language": True}
    assert profiles.should_filter(tag, filters) is True


def test_filter_resolution_category_override():
    tag = {"id": 1, "category_name": "f-word", "category_group": "Language"}
    filters = {"Language": True, "Language:f-word": False}
    assert profiles.should_filter(tag, filters) is False


def test_filter_resolution_tag_override():
    tag = {"id": 100, "category_name": "f-word", "category_group": "Language"}
    filters = {"Language": True, "tag:100": False}
    assert profiles.should_filter(tag, filters) is False


def test_filter_resolution_group_disabled():
    tag = {"id": 1, "category_name": "punch", "category_group": "Violence"}
    filters = {"Language": True}
    assert profiles.should_filter(tag, filters) is False


def test_list_profiles():
    profiles.create("Alpha", filters={})
    profiles.create("Beta", filters={})
    result = profiles.list_all()
    assert len(result) == 2


def test_delete_profile():
    row = profiles.create("Temp", filters={})
    profiles.delete(row["id"])
    assert profiles.get(row["id"]) is None
