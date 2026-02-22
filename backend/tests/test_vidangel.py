"""Integration tests for the VidAngel API client (hits real API)."""

import pytest

from plexfilter.services.vidangel import (
    build_category_tree,
    enrich_tags,
    get_categories,
    get_movie_detail,
    get_tag_set,
    search_works,
)


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _cat_map_from(categories: list[dict]) -> dict[int, dict]:
    """Build {id: cat_dict} lookup from a flat category list."""
    return {c["id"]: c for c in categories}


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


def test_get_categories():
    """Should return >100 categories each with id, display_title, parent_id."""
    cats = get_categories()
    assert isinstance(cats, list)
    assert len(cats) > 100, f"Expected >100 categories, got {len(cats)}"

    sample = cats[0]
    assert "id" in sample
    assert "display_title" in sample
    assert "parent_id" in sample


def test_build_category_tree():
    """Tree should contain root groups like 'Language' and 'Violence'."""
    cats = get_categories()
    tree = build_category_tree(cats)

    assert isinstance(tree, list)
    assert len(tree) > 0, "Tree has no root nodes"

    root_titles = {node["display_title"] for node in tree}
    assert "Language" in root_titles, f"'Language' not in roots: {root_titles}"
    assert "Violence" in root_titles, f"'Violence' not in roots: {root_titles}"

    # Roots should have children
    for node in tree:
        if node["display_title"] in ("Language", "Violence"):
            assert len(node["children"]) > 0, (
                f"Root '{node['display_title']}' has no children"
            )


def test_search_works():
    """Searching 'Operation Fortune' should return at least one result."""
    result = search_works("Operation Fortune")
    assert isinstance(result, dict)
    assert "results" in result
    assert len(result["results"]) > 0, "No results for 'Operation Fortune'"

    titles = [w.get("title", "") for w in result["results"]]
    matched = any("Operation Fortune" in t for t in titles)
    assert matched, f"No title contains 'Operation Fortune': {titles}"


def test_get_movie_detail():
    """work_id 695260 should be 'Operation Fortune: Ruse de Guerre'
    and should have offerings with tag_set_id."""
    movie = get_movie_detail(695260)
    assert isinstance(movie, dict)
    assert "Operation Fortune" in movie.get("title", ""), (
        f"Unexpected title: {movie.get('title')}"
    )

    offerings = movie.get("offerings", [])
    assert len(offerings) > 0, "No offerings found"

    tag_set_ids = [o.get("tag_set_id") for o in offerings if o.get("tag_set_id")]
    assert len(tag_set_ids) > 0, "No offering has a tag_set_id"


def test_get_tag_set():
    """tag_set_id 58076 should return >50 tags with required fields."""
    ts = get_tag_set(58076)
    assert isinstance(ts, dict)

    tags = ts.get("tags", [])
    assert len(tags) > 50, f"Expected >50 tags, got {len(tags)}"

    sample = tags[0]
    for field in ("start_approx", "end_approx", "category_id", "description", "type"):
        assert field in sample, f"Tag missing field '{field}': {list(sample.keys())}"


def test_get_tag_set_with_category_names():
    """Enriched tags should have category_name and category_group."""
    cats = get_categories()
    cat_map = _cat_map_from(cats)

    ts = get_tag_set(58076)
    tags = ts.get("tags", [])
    enriched = enrich_tags(tags, cat_map)

    assert len(enriched) == len(tags)

    # Every enriched tag should have the two new keys
    for tag in enriched:
        assert "category_name" in tag, f"Missing category_name: {tag.get('id')}"
        assert "category_group" in tag, f"Missing category_group: {tag.get('id')}"

    # At least some should have non-empty values
    names = {t["category_name"] for t in enriched}
    groups = {t["category_group"] for t in enriched}
    assert len(names - {""}) > 0, "All category_name values are empty"
    assert len(groups - {""}) > 0, "All category_group values are empty"
