"""Library routes — browse Plex library items with match status."""

from fastapi import APIRouter, HTTPException

from ..database import get_db

router = APIRouter(prefix="/api/library", tags=["library"])


@router.get("")
def list_library(limit: int = 50, offset: int = 0):
    """List library items with match-status badge (LEFT JOIN matches)."""
    db = get_db()
    try:
        rows = db.execute(
            """
            SELECT l.*,
                   m.vidangel_work_id,
                   m.tag_set_id,
                   m.tag_count,
                   m.last_synced,
                   CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END AS matched
            FROM library l
            LEFT JOIN matches m ON m.library_id = l.id
            ORDER BY l.title
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        db.close()


@router.get("/{library_id}")
def get_library_item(library_id: int):
    """Single library item with match info and all tags sorted by start_sec."""
    db = get_db()
    try:
        row = db.execute(
            """
            SELECT l.*,
                   m.vidangel_work_id,
                   m.tag_set_id,
                   m.tag_count,
                   m.last_synced,
                   CASE WHEN m.id IS NOT NULL THEN 1 ELSE 0 END AS matched
            FROM library l
            LEFT JOIN matches m ON m.library_id = l.id
            WHERE l.id = ?
            """,
            (library_id,),
        ).fetchone()

        if row is None:
            raise HTTPException(status_code=404, detail="Library item not found")

        item = dict(row)

        # Attach tags if matched
        tags = []
        if item.get("tag_set_id"):
            tag_rows = db.execute(
                "SELECT * FROM tags WHERE tag_set_id = ? ORDER BY start_sec",
                (item["tag_set_id"],),
            ).fetchall()
            tags = [dict(t) for t in tag_rows]

        item["tags"] = tags
        return item
    finally:
        db.close()
