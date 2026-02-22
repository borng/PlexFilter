"""PlexAutoSkip JSON generation routes."""

from fastapi import APIRouter, HTTPException

from ..services.generator import Generator

router = APIRouter(prefix="/api/generate", tags=["generate"])


@router.post("")
def generate_and_write(profile_id: int = 1):
    """Generate PlexAutoSkip markers and write to the configured JSON path."""
    gen = Generator()
    try:
        payload = gen.generate_and_write(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return payload


@router.get("/preview/{profile_id}")
def preview(profile_id: int):
    """Preview generated markers without writing to disk."""
    gen = Generator()
    try:
        result = gen.generate(profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return result
