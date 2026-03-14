"""Unit tests for local detection pipeline behavior and sync progress integration."""

from __future__ import annotations

import types

import pytest

import plexfilter.config
import plexfilter.database
from plexfilter.database import get_db, init_db
from plexfilter.services.local_detection import LocalDetectionService
from plexfilter.services.sync import SyncService


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(plexfilter.config.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.database.settings, "database_path", db_path)
    monkeypatch.setattr(plexfilter.config.settings, "local_detection_enabled", True)
    monkeypatch.setattr(plexfilter.config.settings, "local_detection_stage1_model", "freepik")
    init_db()


def _seed_library(title: str = "Unknown Movie") -> None:
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO library (plex_key, title, year, tmdb_id, imdb_id, media_type, media_path)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("k1", title, 2024, None, None, "movie", "/tmp/fake.mp4"),
        )
        db.commit()
    finally:
        db.close()


def test_stage1_falls_back_to_passthrough_on_classifier_init_failure(monkeypatch):
    frame_times = [(0.0, "/tmp/frame1.jpg"), (1.0, "/tmp/frame2.jpg")]

    fake_torch = types.ModuleType("torch")
    fake_torch.float16 = object()
    fake_torch.float32 = object()

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

    fake_torch.cuda = _Cuda()

    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = object()

    fake_detector_mod = types.ModuleType("nsfw_image_detector")

    class _Detector:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("bf16 unsupported")

    fake_detector_mod.NSFWDetector = _Detector

    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "PIL", fake_pil)
    monkeypatch.setitem(__import__("sys").modules, "nsfw_image_detector", fake_detector_mod)

    selected = LocalDetectionService._stage1_select_candidates(frame_times)
    assert selected.candidates == frame_times
    assert selected.mode == "nudenet_only"


def test_stage1_skips_when_gpu_vram_is_too_low(monkeypatch):
    frame_times = [(0.0, "/tmp/frame1.jpg")]
    calls = {"detector_inits": 0}
    monkeypatch.setattr(plexfilter.config.settings, "local_detection_stage1_min_vram_gb", 6.0)

    fake_torch = types.ModuleType("torch")
    fake_torch.float16 = object()
    fake_torch.float32 = object()

    class _Cuda:
        @staticmethod
        def is_available() -> bool:
            return True

        @staticmethod
        def get_device_properties(_idx: int):
            return types.SimpleNamespace(total_memory=4 * 1024 * 1024 * 1024)

        @staticmethod
        def is_bf16_supported() -> bool:
            return False

    fake_torch.cuda = _Cuda()

    class _Img:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    fake_image_mod = types.SimpleNamespace(open=lambda _path: _Img())
    fake_pil = types.ModuleType("PIL")
    fake_pil.Image = fake_image_mod

    fake_detector_mod = types.ModuleType("nsfw_image_detector")

    class _Detector:
        def __init__(self, *args, **kwargs):
            calls["detector_inits"] += 1

        def predict_proba(self, _image):
            return {"neutral": 1.0}

    fake_detector_mod.NSFWDetector = _Detector

    monkeypatch.setitem(__import__("sys").modules, "torch", fake_torch)
    monkeypatch.setitem(__import__("sys").modules, "PIL", fake_pil)
    monkeypatch.setitem(__import__("sys").modules, "nsfw_image_detector", fake_detector_mod)

    selected = LocalDetectionService._stage1_select_candidates(frame_times)

    assert selected.candidates == frame_times
    assert selected.mode == "nudenet_only"
    assert calls["detector_inits"] == 0


def test_sync_library_item_forwards_local_progress_events(monkeypatch):
    _seed_library()

    monkeypatch.setattr(
        "plexfilter.services.sync.vidangel.search_works",
        lambda *_args, **_kwargs: {"results": []},
    )

    def fake_detect(self, library_id, on_progress=None):
        if on_progress is not None:
            on_progress(
                {
                    "phase": "local",
                    "status": "running_detector",
                    "title": "Unknown Movie",
                    "frames_total": 10,
                    "frames_done": 5,
                }
            )
        return {"matched": True, "tag_count": 0, "tag_set_id": -library_id, "source": "local"}

    monkeypatch.setattr(
        "plexfilter.services.sync.LocalDetectionService.detect_library_item",
        fake_detect,
    )

    events: list[dict] = []
    result = SyncService().sync_library_item(1, on_detail_progress=events.append)

    assert result["matched"] is True
    assert result["source"] == "local"
    assert events, "expected local progress callback event"
    assert events[-1]["status"] == "running_detector"
    assert events[-1]["frames_done"] == 5
