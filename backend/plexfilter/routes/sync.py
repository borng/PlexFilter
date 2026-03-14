"""Sync and Plex connection routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..config import settings
from ..services.plex_scanner import scan_plex
from ..services.local_detection import LocalDetectionService
from ..services.sync import SyncService

router = APIRouter(prefix="/api", tags=["sync"])

# Module-level sync status tracker
_sync_status: dict = {
    "running": False,
    "current": 0,
    "total": 0,
    "results": [],
    "error": None,
    "local_fallback_count": 0,
    "last_action": "",
}


def _run_sync():
    """Background task that syncs all library items."""
    global _sync_status
    _sync_status["running"] = True
    _sync_status["current"] = 0
    _sync_status["total"] = 0
    _sync_status["results"] = []
    _sync_status["error"] = None
    _sync_status["local_fallback_count"] = 0
    _sync_status["last_action"] = "starting"

    try:
        svc = SyncService()

        def on_progress(current: int, total: int):
            _sync_status["current"] = current
            _sync_status["total"] = total
            _sync_status["last_action"] = f"synced {current}/{total}"

        def on_detail_progress(current: int, total: int, event: dict):
            _sync_status["current"] = current
            _sync_status["total"] = total

            title = event.get("title")
            status = event.get("status") or "processing"
            frames_done = event.get("frames_done")
            frames_total = event.get("frames_total")
            frames_flagged = event.get("frames_flagged")
            hit_count = event.get("hit_count")
            segment_count = event.get("segment_count")

            if isinstance(frames_done, int) and isinstance(frames_total, int) and frames_total > 0:
                detail = f"{status} {frames_done}/{frames_total}"
            elif isinstance(frames_flagged, int) and isinstance(frames_total, int) and frames_total > 0:
                detail = f"{status} flagged {frames_flagged}/{frames_total}"
            elif isinstance(hit_count, int):
                detail = f"{status} hits={hit_count}"
            elif isinstance(segment_count, int):
                detail = f"{status} segments={segment_count}"
            else:
                detail = status

            if title:
                _sync_status["last_action"] = f"{title}: {detail}"
            else:
                _sync_status["last_action"] = detail

        results = svc.sync_all(on_progress=on_progress, on_detail_progress=on_detail_progress)
        _sync_status["results"] = results
        _sync_status["local_fallback_count"] = len(
            [r for r in results if r.get("source") == "local"]
        )
        _sync_status["last_action"] = "completed"
    except Exception as exc:
        _sync_status["error"] = str(exc)
    finally:
        _sync_status["running"] = False


@router.post("/sync")
def start_sync(background_tasks: BackgroundTasks):
    """Start a background sync of all library items."""
    if _sync_status["running"]:
        raise HTTPException(status_code=409, detail="Sync already in progress")
    background_tasks.add_task(_run_sync)
    return {"status": "started"}


@router.post("/sync/{library_id}")
def sync_single(library_id: int):
    """Sync a single library item (foreground)."""
    svc = SyncService()
    result = svc.sync_library_item(library_id)
    return result


@router.post("/local-detection/{library_id}")
def local_detect_single(library_id: int):
    """Run local nudity detection for one title regardless of VidAngel match."""
    result = LocalDetectionService().detect_library_item(library_id)
    if not result.get("matched"):
        raise HTTPException(status_code=400, detail=result.get("error", "local detection failed"))
    return result


@router.get("/sync/status")
def sync_status():
    """Return current sync status."""
    return _sync_status


@router.post("/plex/connect")
def plex_connect(plex_url: str, plex_token: str):
    """Save Plex connection settings."""
    settings.plex_url = plex_url
    settings.plex_token = plex_token
    return {"status": "connected", "plex_url": plex_url}


@router.post("/plex/scan")
def plex_scan():
    """Scan Plex library and store items."""
    if not settings.plex_url or not settings.plex_token:
        raise HTTPException(
            status_code=400,
            detail="Plex not connected. POST /api/plex/connect first.",
        )
    count = scan_plex()
    return {"status": "scanned", "count": count}
