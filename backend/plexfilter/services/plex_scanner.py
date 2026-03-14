"""Plex library scanner service — discovers movies and extracts GUIDs."""

from datetime import datetime, timezone

from plexapi.server import PlexServer

from ..config import settings
from ..database import get_db


def store_item(
    plex_key: str,
    title: str,
    year: int | None = None,
    tmdb_id: str | None = None,
    imdb_id: str | None = None,
    media_type: str = "movie",
    thumb_url: str | None = None,
    media_path: str | None = None,
    duration_sec: float | None = None,
) -> None:
    """Insert or update a library item keyed on plex_key."""
    db = get_db()
    db.execute(
        """
        INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type, thumb_url, media_path, duration_sec, last_scanned)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(plex_key) DO UPDATE SET
            title = excluded.title,
            year = excluded.year,
            tmdb_id = excluded.tmdb_id,
            imdb_id = excluded.imdb_id,
            media_type = excluded.media_type,
            thumb_url = excluded.thumb_url,
            media_path = excluded.media_path,
            duration_sec = excluded.duration_sec,
            last_scanned = excluded.last_scanned
        """,
        (
            plex_key,
            title,
            year,
            tmdb_id,
            imdb_id,
            media_type,
            thumb_url,
            media_path,
            duration_sec,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    db.commit()
    db.close()


def get_items(limit: int = 50, offset: int = 0) -> list[dict]:
    """Return library items ordered by title with LIMIT/OFFSET pagination."""
    db = get_db()
    rows = db.execute(
        "SELECT * FROM library ORDER BY title LIMIT ? OFFSET ?",
        (limit, offset),
    ).fetchall()
    db.close()
    return [dict(row) for row in rows]


@staticmethod
def extract_guids(guids: list[str]) -> dict:
    """Parse Plex GUID strings into a dict with tmdb_id and imdb_id keys.

    Example input: ["tmdb://845783", "imdb://tt7339792", "tvdb://12345"]
    Returns: {"tmdb_id": "845783", "imdb_id": "tt7339792"}
    """
    result: dict[str, str | None] = {"tmdb_id": None, "imdb_id": None}
    for guid in guids:
        if guid.startswith("tmdb://"):
            result["tmdb_id"] = guid.removeprefix("tmdb://")
        elif guid.startswith("imdb://"):
            result["imdb_id"] = guid.removeprefix("imdb://")
    return result


def scan_plex() -> int:
    """Connect to Plex, scan the Movies section, and store every item.

    Returns the number of items stored.
    """
    plex = PlexServer(settings.plex_url, settings.plex_token)
    movies_section = plex.library.section("Movies")
    count = 0
    for movie in movies_section.all():
        guid_strings = [g.id for g in movie.guids]
        ids = extract_guids(guid_strings)
        media_path = None
        if movie.media and movie.media[0].parts:
            media_path = movie.media[0].parts[0].file
        store_item(
            plex_key=str(movie.ratingKey),
            title=movie.title,
            year=movie.year,
            tmdb_id=ids.get("tmdb_id"),
            imdb_id=ids.get("imdb_id"),
            media_type="movie",
            thumb_url=movie.thumb,
            media_path=media_path,
            duration_sec=(movie.duration / 1000.0) if movie.duration else None,
        )
        count += 1
    return count
