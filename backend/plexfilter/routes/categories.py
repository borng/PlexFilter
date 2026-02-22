"""Category tree route with module-level cache."""

from typing import Any

from fastapi import APIRouter

from ..services.vidangel import build_category_tree, get_categories

router = APIRouter(prefix="/api/categories", tags=["categories"])

# Module-level cache (populated on first request)
_cache: list[dict[str, Any]] | None = None


@router.get("")
def list_categories():
    """Return the full VidAngel category tree (cached after first call)."""
    global _cache
    if _cache is None:
        categories = get_categories()
        _cache = build_category_tree(categories)
    return _cache
