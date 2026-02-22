"""
VidAngel API client service.

All endpoints are unauthenticated. Base URL comes from settings.vidangel_base_url.

Key endpoints:
  GET /v2/tag-categorizations/         - 147 filter categories (3-level hierarchy)
  GET /content/v2/works/?type=&search=  - search works (movies/shows)
  GET /content/v2/movies/{work_id}/     - movie detail with offerings[].tag_set_id
  GET /tag-sets/{tag_set_id}/           - all tags with start_approx/end_approx (seconds)
"""

from __future__ import annotations

from typing import Any

import httpx

from ..config import settings

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}

_TIMEOUT = 30.0


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------


def _base() -> str:
    return settings.vidangel_base_url.rstrip("/")


def get_categories() -> list[dict[str, Any]]:
    """Return the full list of tag-categorization dicts from VidAngel.

    Each dict has at least: id, display_title, key, parent_id, ordering.
    """
    url = f"{_base()}/v2/tag-categorizations/"
    resp = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def build_category_tree(categories: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build a nested tree from the flat category list.

    Returns a list of root nodes (parent_id is None), each with a ``children``
    key containing their sorted children (who in turn may have children).
    """
    by_id: dict[int, dict[str, Any]] = {}
    for cat in categories:
        node = dict(cat)
        node["children"] = []
        by_id[node["id"]] = node

    roots: list[dict[str, Any]] = []
    for node in by_id.values():
        parent_id = node.get("parent_id")
        if parent_id is None:
            roots.append(node)
        else:
            parent = by_id.get(parent_id)
            if parent is not None:
                parent["children"].append(node)

    # Sort roots and each children list by ordering
    def _sort(nodes: list[dict[str, Any]]) -> None:
        nodes.sort(key=lambda n: (n.get("ordering") or 0))
        for n in nodes:
            _sort(n["children"])

    _sort(roots)
    return roots


def search_works(
    query: str,
    media_type: str = "movie",
    limit: int = 20,
) -> dict[str, Any]:
    """Search VidAngel works (movies/shows).

    Returns the raw API response dict which contains ``results`` and ``count``.
    """
    url = f"{_base()}/content/v2/works/"
    params: dict[str, Any] = {
        "type": media_type,
        "search": query,
        "limit": limit,
    }
    resp = httpx.get(url, params=params, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_movie_detail(work_id: int | str) -> dict[str, Any]:
    """Get full movie detail including offerings with tag_set_id."""
    url = f"{_base()}/content/v2/movies/{work_id}/"
    resp = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def get_tag_set(tag_set_id: int | str) -> dict[str, Any]:
    """Get a tag-set by ID.  Contains ``tags`` list with timestamps."""
    url = f"{_base()}/tag-sets/{tag_set_id}/"
    resp = httpx.get(url, headers=_HEADERS, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def enrich_tags(
    tags: list[dict[str, Any]],
    cat_map: dict[int, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add ``category_name`` and ``category_group`` to each tag.

    *cat_map* is ``{category_id: category_dict}`` built from
    :func:`get_categories`.

    ``category_name`` is the leaf category's display_title.
    ``category_group`` is the root (top-level) ancestor's display_title,
    found by walking up the parent_id chain.
    """
    enriched: list[dict[str, Any]] = []
    for tag in tags:
        tag = dict(tag)  # shallow copy
        cat_id = tag.get("category_id")
        cat = cat_map.get(cat_id) if cat_id is not None else None

        if cat is not None:
            tag["category_name"] = cat.get("display_title", "")
            # Walk up to root
            ancestor = cat
            while ancestor.get("parent_id") is not None:
                parent = cat_map.get(ancestor["parent_id"])
                if parent is None:
                    break
                ancestor = parent
            tag["category_group"] = ancestor.get("display_title", "")
        else:
            tag["category_name"] = ""
            tag["category_group"] = ""

        enriched.append(tag)
    return enriched
