"""Local nudity detection service for unmatched library items.

Pipeline:
1) Extract frames every N seconds with ffmpeg.
2) Optional fast-pass classifier (currently a pass-through scaffold).
3) Run NudeNet detection on candidate frames.
4) Merge adjacent frame hits into timestamp segments.
5) Store segments as tags using a synthetic local tag_set_id.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..config import settings
from ..database import get_db

ProgressFn = Callable[[dict[str, Any]], None]


# Map NudeNet labels to PlexFilter category names.
_LABEL_TO_CATEGORY = {
    "FEMALE_BREAST_EXPOSED": "Female Nudity",
    "FEMALE_GENITALIA_EXPOSED": "Female Genital Nudity",
    "MALE_GENITALIA_EXPOSED": "Male Genital Nudity",
    "BUTTOCKS_EXPOSED": "Buttocks Nudity",
    "ANUS_EXPOSED": "Explicit Nudity",
    "FEMALE_BREAST_COVERED": "Suggestive",
    "FEMALE_GENITALIA_COVERED": "Suggestive",
    "BUTTOCKS_COVERED": "Suggestive",
    "ANUS_COVERED": "Suggestive",
    "MALE_BREAST_EXPOSED": "Male Chest",
}


@dataclass
class FrameHit:
    ts: float
    label: str
    score: float


@dataclass
class Stage1Selection:
    candidates: list[tuple[float, str]]
    mode: str
    reason: str | None = None


class LocalDetectionService:
    def detect_library_item(
        self,
        library_id: int,
        on_progress: ProgressFn | None = None,
    ) -> dict[str, Any]:
        all_frame_times: list[tuple[float, str]] = []
        try:
            item = self._get_library_item(library_id)
            if item is None:
                return {"matched": False, "error": f"library_id {library_id} not found"}

            media_path = item.get("media_path")
            if not media_path:
                return {
                    "matched": False,
                    "error": "missing media_path in library row (rescan Plex to populate file paths)",
                }

            if not os.path.exists(media_path):
                return {
                    "matched": False,
                    "error": f"media file does not exist: {media_path}",
                }

            if shutil.which("ffmpeg") is None:
                return {"matched": False, "error": "ffmpeg not available in PATH"}

            if on_progress:
                on_progress({"phase": "local", "status": "extracting_frames", "title": item.get("title")})

            interval = max(settings.local_detection_sample_interval_sec, 0.25)
            all_frame_times = self._extract_frame_times(media_path, interval)
            if not all_frame_times:
                return {"matched": False, "error": "no frames extracted"}

            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "stage1_classifier",
                        "title": item.get("title"),
                        "frames_total": len(all_frame_times),
                    }
                )

            stage1 = self._stage1_select_candidates(
                all_frame_times,
                on_progress=on_progress,
            )
            candidates = stage1.candidates
            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "stage1_selected",
                        "title": item.get("title"),
                        "pipeline_mode": stage1.mode,
                        "frames_total": len(all_frame_times),
                        "frames_flagged": len(candidates),
                        "reason": stage1.reason,
                    }
                )
            if not candidates:
                self._store_local_result(library_id, [])
                return {
                    "matched": True,
                    "tag_count": 0,
                    "tag_set_id": -library_id,
                    "source": "local",
                    "pipeline_mode": stage1.mode,
                    "frames_extracted": len(all_frame_times),
                    "frames_stage1_candidates": 0,
                    "segment_count": 0,
                }

            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "running_detector",
                        "title": item.get("title"),
                        "frames_total": len(candidates),
                        "frames_done": 0,
                        "pipeline_mode": stage1.mode,
                    }
                )

            hits = self._run_nudenet(
                candidates,
                threshold=settings.local_detection_nudenet_threshold,
                on_progress=on_progress,
            )
            if not hits:
                self._store_local_result(library_id, [])
                return {
                    "matched": True,
                    "tag_count": 0,
                    "tag_set_id": -library_id,
                    "source": "local",
                    "pipeline_mode": stage1.mode,
                    "frames_extracted": len(all_frame_times),
                    "frames_stage1_candidates": len(candidates),
                    "segment_count": 0,
                }

            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "segmenting",
                        "title": item.get("title"),
                        "hit_count": len(hits),
                    }
                )
            segments = self._hits_to_segments(
                hits,
                frame_window=interval,
                merge_gap=settings.local_detection_merge_gap_sec,
            )
            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "storing_tags",
                        "title": item.get("title"),
                        "segment_count": len(segments),
                    }
                )
            tag_count = self._store_local_result(library_id, segments)
            return {
                "matched": True,
                "tag_count": tag_count,
                "tag_set_id": -library_id,
                "source": "local",
                "pipeline_mode": stage1.mode,
                "frames_extracted": len(all_frame_times),
                "frames_stage1_candidates": len(candidates),
                "segment_count": len(segments),
            }
        except Exception as exc:
            return {"matched": False, "error": f"local detection failed: {exc}"}
        finally:
            self._cleanup_frame_cache(all_frame_times)

    @staticmethod
    def _get_library_item(library_id: int) -> dict[str, Any] | None:
        db = get_db()
        try:
            row = db.execute("SELECT * FROM library WHERE id = ?", (library_id,)).fetchone()
            return dict(row) if row else None
        finally:
            db.close()

    @staticmethod
    def _extract_frame_times(media_path: str, interval: float) -> list[tuple[float, str]]:
        """Return list of ``(timestamp_sec, frame_path)`` extracted by ffmpeg."""
        tmpdir = tempfile.mkdtemp(prefix="plexfilter_frames_cache_")
        pattern = str(Path(tmpdir) / "frame_%07d.jpg")
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            media_path,
            "-vf",
            f"fps=1/{interval}",
            "-q:v",
            "3",
            pattern,
        ]
        subprocess.run(cmd, check=True)

        frame_paths = sorted(Path(tmpdir).glob("frame_*.jpg"))
        return [(idx * interval, str(frame_path)) for idx, frame_path in enumerate(frame_paths)]

    @staticmethod
    def _run_nudenet(
        frame_times: list[tuple[float, str]],
        threshold: float,
        on_progress: ProgressFn | None = None,
    ) -> list[FrameHit]:
        try:
            from nudenet import NudeDetector
        except Exception as exc:  # pragma: no cover - depends on optional dependency
            raise RuntimeError(
                "nudenet is required for local detection (pip install nudenet)"
            ) from exc

        detector = NudeDetector()
        hits: list[FrameHit] = []

        for idx, (ts, frame_path) in enumerate(frame_times, start=1):
            detections = detector.detect(frame_path) or []
            best: dict[str, float] = {}
            for det in detections:
                label = (det.get("class") or "").upper()
                score = float(det.get("score") or 0.0)
                if score < threshold:
                    continue
                if label not in _LABEL_TO_CATEGORY:
                    continue
                prev = best.get(label)
                if prev is None or score > prev:
                    best[label] = score

            for label, score in best.items():
                hits.append(FrameHit(ts=ts, label=label, score=score))

            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "running_detector",
                        "frames_total": len(frame_times),
                        "frames_done": idx,
                    }
                )

        return hits

    @staticmethod
    def _stage1_select_candidates(
        frame_times: list[tuple[float, str]],
        on_progress: ProgressFn | None = None,
    ) -> Stage1Selection:
        """Fast-pass classifier. Falls back to pass-through when unavailable."""
        if settings.local_detection_stage1_model.lower() != "freepik":
            return Stage1Selection(candidates=frame_times, mode="nudenet_only", reason="stage1_disabled")

        try:
            import torch
            from PIL import Image
            from nsfw_image_detector import NSFWDetector
        except Exception:
            return Stage1Selection(
                candidates=frame_times,
                mode="nudenet_only",
                reason="stage1_dependencies_missing",
            )

        if not LocalDetectionService._can_use_freepik_stage1(torch):
            if on_progress:
                on_progress(
                    {
                        "phase": "local",
                        "status": "stage1_skipped",
                        "reason": "insufficient_gpu",
                    }
                )
            return Stage1Selection(candidates=frame_times, mode="nudenet_only", reason="insufficient_gpu")

        severity_rank = {"neutral": 0, "low": 1, "medium": 2, "high": 3}
        min_rank = severity_rank.get(settings.local_detection_stage1_severity.lower(), 2)

        device = "cuda"
        dtype = torch.float16
        try:
            detector = NSFWDetector(device=device, dtype=dtype)
        except Exception:
            return Stage1Selection(candidates=frame_times, mode="nudenet_only", reason="stage1_init_failed")
        kept: list[tuple[float, str]] = []

        try:
            for idx, (ts, frame_path) in enumerate(frame_times, start=1):
                with Image.open(frame_path) as image:
                    probs = detector.predict_proba(image)

                top_label = max(probs, key=probs.get)
                if severity_rank.get(top_label, 0) >= min_rank:
                    kept.append((ts, frame_path))

                if on_progress:
                    on_progress(
                        {
                            "phase": "local",
                            "status": "stage1_classifier",
                            "frames_total": len(frame_times),
                            "frames_done": idx,
                            "frames_flagged": len(kept),
                        }
                    )
        except Exception:
            return Stage1Selection(candidates=frame_times, mode="nudenet_only", reason="stage1_inference_failed")

        if on_progress:
            on_progress(
                {
                    "phase": "local",
                    "status": "stage1_complete",
                    "frames_total": len(frame_times),
                    "frames_flagged": len(kept),
                }
            )
        return Stage1Selection(candidates=kept, mode="two_stage")

    @staticmethod
    def _can_use_freepik_stage1(torch_mod: Any) -> bool:
        cuda = getattr(torch_mod, "cuda", None)
        if cuda is None or not callable(getattr(cuda, "is_available", None)):
            return False
        if not cuda.is_available():
            return False

        min_vram_gb = max(float(settings.local_detection_stage1_min_vram_gb), 0.0)
        get_props = getattr(cuda, "get_device_properties", None)
        if callable(get_props):
            try:
                total_memory = float(get_props(0).total_memory)
                vram_gb = total_memory / (1024**3)
                if vram_gb < min_vram_gb:
                    return False
            except Exception:
                return False

        if settings.local_detection_stage1_require_bf16:
            bf16_supported = getattr(cuda, "is_bf16_supported", None)
            if not callable(bf16_supported):
                return False
            try:
                if not bf16_supported():
                    return False
            except Exception:
                return False

        return True

    @staticmethod
    def _hits_to_segments(
        hits: list[FrameHit],
        frame_window: float,
        merge_gap: float,
    ) -> list[dict[str, Any]]:
        by_label: dict[str, list[FrameHit]] = {}
        for hit in hits:
            by_label.setdefault(hit.label, []).append(hit)

        segments: list[dict[str, Any]] = []
        for label, label_hits in by_label.items():
            label_hits.sort(key=lambda h: h.ts)
            cur_start = label_hits[0].ts
            cur_end = label_hits[0].ts + frame_window
            best_score = label_hits[0].score

            for hit in label_hits[1:]:
                hit_start = hit.ts
                hit_end = hit.ts + frame_window
                if hit_start - cur_end <= merge_gap:
                    cur_end = max(cur_end, hit_end)
                    best_score = max(best_score, hit.score)
                    continue

                segments.append(
                    {
                        "label": label,
                        "category_name": _LABEL_TO_CATEGORY[label],
                        "start_sec": round(cur_start, 3),
                        "end_sec": round(cur_end, 3),
                        "confidence": best_score,
                    }
                )
                cur_start = hit_start
                cur_end = hit_end
                best_score = hit.score

            segments.append(
                {
                    "label": label,
                    "category_name": _LABEL_TO_CATEGORY[label],
                    "start_sec": round(cur_start, 3),
                    "end_sec": round(cur_end, 3),
                    "confidence": best_score,
                }
            )

        segments.sort(key=lambda s: (s["start_sec"], s["category_name"]))
        return segments

    @staticmethod
    def _store_local_result(library_id: int, segments: list[dict[str, Any]]) -> int:
        now = datetime.now(timezone.utc).isoformat()
        tag_set_id = -library_id

        db = get_db()
        try:
            db.execute(
                """
                INSERT INTO matches (library_id, vidangel_work_id, tag_set_id, source,
                                     match_method, tag_count, last_synced)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(library_id) DO UPDATE SET
                    vidangel_work_id = excluded.vidangel_work_id,
                    tag_set_id       = excluded.tag_set_id,
                    source           = excluded.source,
                    match_method     = excluded.match_method,
                    tag_count        = excluded.tag_count,
                    last_synced      = excluded.last_synced
                """,
                (library_id, -library_id, tag_set_id, "local", "local_nudity", len(segments), now),
            )

            # Replace local tags for this title.
            db.execute("DELETE FROM tags WHERE tag_set_id = ?", (tag_set_id,))

            for idx, segment in enumerate(segments, start=1):
                digest = hashlib.blake2s(
                    f"{library_id}:{idx}:{segment['label']}:{segment['start_sec']}:{segment['end_sec']}".encode(),
                    digest_size=8,
                ).digest()
                synthetic_id = int.from_bytes(digest, byteorder="big", signed=False) & 0x7FFF_FFFF_FFFF_FFFF

                description = f"{segment['label']} ({segment['confidence']:.2f})"
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
                        synthetic_id,
                        tag_set_id,
                        9000 + idx,
                        segment["category_name"],
                        "Nudity",
                        description,
                        "visual",
                        segment["start_sec"],
                        segment["end_sec"],
                    ),
                )

            db.commit()
            return len(segments)
        finally:
            db.close()

    @staticmethod
    def _cleanup_frame_cache(frame_times: list[tuple[float, str]]) -> None:
        if not frame_times:
            return

        cache_dir = Path(frame_times[0][1]).parent
        for _ts, frame_path in frame_times:
            try:
                os.remove(frame_path)
            except OSError:
                pass

        try:
            shutil.rmtree(cache_dir, ignore_errors=True)
        except OSError:
            pass
