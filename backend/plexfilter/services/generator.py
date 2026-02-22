"""PlexAutoSkip JSON generator — builds skip/mute marker files from profiles."""

from __future__ import annotations

import json
from typing import Any

from ..config import settings
from ..database import get_db
from . import profiles


class Generator:
    """Generates PlexAutoSkip-compatible JSON marker data from a filter profile."""

    def generate(self, profile_id: int) -> dict[str, list[dict[str, Any]]]:
        """Build a dict of ``{guid: [segments]}`` for a given profile.

        Each segment is ``{"start": ms, "end": ms, "mode": "skip"|"volume"}``.
        """
        profile = profiles.get(profile_id)
        if profile is None:
            raise ValueError(f"Profile {profile_id} not found")

        filters = json.loads(profile["filters"]) if isinstance(profile["filters"], str) else profile["filters"]

        # Get all matched titles (JOIN library + matches)
        db = get_db()
        try:
            rows = db.execute(
                """
                SELECT l.tmdb_id, m.tag_set_id
                FROM library l
                JOIN matches m ON m.library_id = l.id
                WHERE l.tmdb_id IS NOT NULL
                """
            ).fetchall()
        finally:
            db.close()

        output: dict[str, list[dict[str, Any]]] = {}

        for row in rows:
            tmdb_id = row["tmdb_id"]
            tag_set_id = row["tag_set_id"]

            # Fetch tags for this title
            db = get_db()
            try:
                tag_rows = db.execute(
                    "SELECT * FROM tags WHERE tag_set_id = ?", (tag_set_id,)
                ).fetchall()
            finally:
                db.close()

            segments: list[dict[str, Any]] = []
            for tag_row in tag_rows:
                tag = dict(tag_row)
                if not profiles.should_filter(tag, filters):
                    continue

                tag_type = tag.get("type", "").lower()
                if tag_type == "audio":
                    mode = "volume"
                else:
                    # visual, audiovisual, or anything else → skip
                    mode = "skip"

                segments.append({
                    "start": int(tag["start_sec"] * 1000),
                    "end": int(tag["end_sec"] * 1000),
                    "mode": mode,
                })

            if segments:
                # Sort by start time, then merge adjacent
                segments.sort(key=lambda s: s["start"])
                segments = self._merge_segments(segments)
                output[f"tmdb://{tmdb_id}"] = segments

        return output

    @staticmethod
    def _merge_segments(
        segments: list[dict[str, Any]], gap_ms: int = 2000
    ) -> list[dict[str, Any]]:
        """Merge adjacent segments with the same mode when the gap is <= *gap_ms*."""
        if not segments:
            return segments

        merged: list[dict[str, Any]] = [segments[0].copy()]
        for seg in segments[1:]:
            prev = merged[-1]
            if seg["mode"] == prev["mode"] and seg["start"] - prev["end"] <= gap_ms:
                prev["end"] = max(prev["end"], seg["end"])
            else:
                merged.append(seg.copy())
        return merged

    def generate_and_write(self, profile_id: int) -> dict:
        """Generate markers and write to the configured PlexAutoSkip JSON path."""
        markers = self.generate(profile_id)
        payload = {"markers": markers}
        with open(settings.plexautoskip_json_path, "w") as f:
            json.dump(payload, f, indent=2)
        return payload
