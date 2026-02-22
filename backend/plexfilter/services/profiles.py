import json
from datetime import datetime, timezone

from ..database import get_db


def _row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    if row is None:
        return None
    return dict(row)


def create(name: str, filters: dict, mode: str = "skip", plex_user: str = None) -> dict:
    db = get_db()
    try:
        created_at = datetime.now(timezone.utc).isoformat()
        cur = db.execute(
            "INSERT INTO profiles (name, filters, mode, plex_user, created_at) VALUES (?, ?, ?, ?, ?)",
            (name, json.dumps(filters), mode, plex_user, created_at),
        )
        db.commit()
        row = db.execute("SELECT * FROM profiles WHERE id = ?", (cur.lastrowid,)).fetchone()
        return _row_to_dict(row)
    finally:
        db.close()


def get(profile_id: int) -> dict | None:
    db = get_db()
    try:
        row = db.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        db.close()


def list_all() -> list[dict]:
    db = get_db()
    try:
        rows = db.execute("SELECT * FROM profiles ORDER BY name").fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        db.close()


def update(profile_id: int, name: str = None, filters: dict = None, mode: str = None, plex_user: str = None):
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name)
    if filters is not None:
        fields.append("filters = ?")
        values.append(json.dumps(filters))
    if mode is not None:
        fields.append("mode = ?")
        values.append(mode)
    if plex_user is not None:
        fields.append("plex_user = ?")
        values.append(plex_user)
    if not fields:
        return
    values.append(profile_id)
    db = get_db()
    try:
        db.execute(f"UPDATE profiles SET {', '.join(fields)} WHERE id = ?", values)
        db.commit()
    finally:
        db.close()


def delete(profile_id: int):
    db = get_db()
    try:
        db.execute("DELETE FROM profiles WHERE id = ?", (profile_id,))
        db.commit()
    finally:
        db.close()


def should_filter(tag: dict, filters: dict) -> bool:
    """Three-level filter resolution (highest priority first).

    Level 3: tag-specific override   — key ``tag:{tag_id}``
    Level 2: category override       — key ``{group}:{category_name}``
    Level 1: group-level             — key ``{group}``

    Returns False when nothing matches.
    """
    tag_id = tag.get("id") or tag.get("vidangel_id")
    category_name = tag.get("category_name", "")
    group = tag.get("category_group", "")

    # Level 3 — tag-specific
    tag_key = f"tag:{tag_id}"
    if tag_key in filters:
        return bool(filters[tag_key])

    # Level 2 — category
    cat_key = f"{group}:{category_name}"
    if cat_key in filters:
        return bool(filters[cat_key])

    # Level 1 — group
    if group in filters:
        return bool(filters[group])

    return False
