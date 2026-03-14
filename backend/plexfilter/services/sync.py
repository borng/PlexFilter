"""Sync service — ties VidAngel tag data to Plex library items."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from ..database import get_db
from ..config import settings
from . import vidangel
from .local_detection import LocalDetectionService


class SyncService:
    """Orchestrates matching Plex library items to VidAngel works and
    fetching/storing their filter tags."""

    def __init__(self) -> None:
        self._cat_map: dict[int, dict[str, Any]] | None = None

    # ------------------------------------------------------------------
    # Lazy category map
    # ------------------------------------------------------------------

    @property
    def cat_map(self) -> dict[int, dict[str, Any]]:
        """Fetch VidAngel categories once and build an {id: cat_dict} lookup."""
        if self._cat_map is None:
            categories = vidangel.get_categories()
            self._cat_map = {c["id"]: c for c in categories}
        return self._cat_map

    # ------------------------------------------------------------------
    # Single-item sync
    # ------------------------------------------------------------------

    def sync_library_item(
        self,
        library_id: int,
        on_detail_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        """Match a single library row to VidAngel and store tags.

        Returns a result dict:
            {"matched": True, "tag_count": N, "tag_set_id": N}
            or
            {"matched": False, "error": "reason"}
        """
        return self._sync_library_item(library_id, on_detail_progress=on_detail_progress)

    def _sync_library_item(
        self,
        library_id: int,
        on_detail_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        db = get_db()
        try:
            row = db.execute(
                "SELECT * FROM library WHERE id = ?", (library_id,)
            ).fetchone()
            if row is None:
                return {"matched": False, "error": f"library_id {library_id} not found"}
            item = dict(row)
        finally:
            db.close()

        title = item["title"]
        year = item.get("year")

        # --- Search VidAngel by title ---
        try:
            search_resp = vidangel.search_works(title)
        except Exception as exc:
            return self._fallback_to_local(
                library_id=library_id,
                reason=f"search failed: {exc}",
                on_detail_progress=on_detail_progress,
            )

        results = search_resp.get("results", [])
        if not results:
            return self._fallback_to_local(
                library_id=library_id,
                reason=f"no VidAngel results for '{title}'",
                on_detail_progress=on_detail_progress,
            )

        # --- Match by year, fallback to first result ---
        work = results[0]
        if year is not None:
            for r in results:
                if r.get("year") == year:
                    work = r
                    break

        work_id = work["id"]

        # --- Get movie detail for tag_set_id ---
        try:
            detail = vidangel.get_movie_detail(work_id)
        except Exception as exc:
            return self._fallback_to_local(
                library_id=library_id,
                reason=f"movie detail failed: {exc}",
                on_detail_progress=on_detail_progress,
            )

        offerings = detail.get("offerings", [])
        tag_set_id: int | None = None
        for offering in offerings:
            tsid = offering.get("tag_set_id")
            if tsid:
                tag_set_id = tsid
                break

        if tag_set_id is None:
            return self._fallback_to_local(
                library_id=library_id,
                reason="no tag_set_id in offerings",
                on_detail_progress=on_detail_progress,
            )

        # --- Fetch tag set and enrich ---
        try:
            tag_set_resp = vidangel.get_tag_set(tag_set_id)
        except Exception as exc:
            return self._fallback_to_local(
                library_id=library_id,
                reason=f"tag set fetch failed: {exc}",
                on_detail_progress=on_detail_progress,
            )

        raw_tags = tag_set_resp.get("tags", [])
        enriched = vidangel.enrich_tags(raw_tags, self.cat_map)

        # --- Upsert match ---
        now = datetime.now(timezone.utc).isoformat()
        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO matches (library_id, vidangel_work_id, tag_set_id,
                                     source, match_method, tag_count, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_id) DO UPDATE SET
                    vidangel_work_id = excluded.vidangel_work_id,
                    tag_set_id       = excluded.tag_set_id,
                    source           = excluded.source,
                    match_method     = excluded.match_method,
                    tag_count        = excluded.tag_count,
                    last_synced      = excluded.last_synced
                """,
                (
                    library_id,
                    work_id,
                    tag_set_id,
                    "vidangel",
                    "title+year",
                    len(enriched),
                    now,
                ),
            )

            # --- Upsert tags (UNIQUE on vidangel_id) ---
            for tag in enriched:
                db.execute(
                    """
                    INSERT INTO tags (vidangel_id, tag_set_id, category_id,
                                      category_name, category_group,
                                      description, type, start_sec, end_sec)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(vidangel_id) DO UPDATE SET
                        tag_set_id     = excluded.tag_set_id,
                        category_id    = excluded.category_id,
                        category_name  = excluded.category_name,
                        category_group = excluded.category_group,
                        description    = excluded.description,
                        type           = excluded.type,
                        start_sec      = excluded.start_sec,
                        end_sec        = excluded.end_sec
                    """,
                    (
                        tag["id"],
                        tag_set_id,
                        tag.get("category_id", 0),
                        tag.get("category_name", ""),
                        tag.get("category_group", ""),
                        tag.get("description", ""),
                        tag.get("type", ""),
                        tag.get("start_approx", 0.0),
                        tag.get("end_approx", 0.0),
                    ),
                )

            db.commit()
        finally:
            db.close()

        return {
            "matched": True,
            "tag_count": len(enriched),
            "tag_set_id": tag_set_id,
            "source": "vidangel",
        }

    # ------------------------------------------------------------------
    # Bulk sync
    # ------------------------------------------------------------------

    def sync_all(
        self,
        on_progress: Callable[[int, int], None] | None = None,
        on_detail_progress: Callable[[int, int, dict[str, Any]], None] | None = None,
    ) -> list[dict[str, Any]]:
        """Sync every library item.  Returns a list of per-item result dicts.

        *on_progress*, if supplied, is called as ``on_progress(current, total)``
        after each item.
        """
        db = get_db()
        try:
            rows = db.execute("SELECT id FROM library ORDER BY id").fetchall()
        finally:
            db.close()

        total = len(rows)
        results: list[dict[str, Any]] = []

        for idx, row in enumerate(rows, start=1):
            detail_callback: Callable[[dict[str, Any]], None] | None = None
            if on_detail_progress is not None:
                detail_callback = lambda event, cur=idx: on_detail_progress(cur, total, event)

            result = self._sync_library_item(row["id"], on_detail_progress=detail_callback)
            results.append(result)

            if on_progress is not None:
                on_progress(idx, total)

            if idx < total:
                time.sleep(0.5)

        return results

    @staticmethod
    def _fallback_to_local(
        library_id: int,
        reason: str,
        on_detail_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> dict[str, Any]:
        if not settings.local_detection_enabled:
            return {"matched": False, "error": reason}

        try:
            local_result = LocalDetectionService().detect_library_item(
                library_id,
                on_progress=on_detail_progress,
            )
        except Exception as exc:
            return {
                "matched": False,
                "error": reason,
                "fallback_error": f"local detection failed: {exc}",
            }

        local_result["fallback_reason"] = reason
        return local_result
