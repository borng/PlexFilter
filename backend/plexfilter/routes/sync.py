"""Sync and Plex connection routes."""

from fastapi import APIRouter, BackgroundTasks, HTTPException

from ..config import settings
from ..services.plex_scanner import scan_plex
from ..services.sync import SyncService

router = APIRouter(prefix="/api", tags=["sync"])

# Module-level sync status tracker
_sync_status: dict = {
    "running": False,
    "current": 0,
    "total": 0,
    "results": [],
    "error": None,
}


def _run_sync():
    """Background task that syncs all library items."""
    global _sync_status
    _sync_status["running"] = True
    _sync_status["current"] = 0
    _sync_status["total"] = 0
    _sync_status["results"] = []
    _sync_status["error"] = None

    try:
        svc = SyncService()

        def on_progress(current: int, total: int):
            _sync_status["current"] = current
            _sync_status["total"] = total

        results = svc.sync_all(on_progress=on_progress)
        _sync_status["results"] = results
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
