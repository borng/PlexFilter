"""Profile CRUD routes."""

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..services import profiles as svc

router = APIRouter(prefix="/api/profiles", tags=["profiles"])


class ProfileCreate(BaseModel):
    name: str
    filters: dict = {}
    mode: str = "skip"
    plex_user: Optional[str] = None


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    filters: Optional[dict] = None
    mode: Optional[str] = None
    plex_user: Optional[str] = None


@router.get("")
def list_profiles():
    return svc.list_all()


@router.post("", status_code=201)
def create_profile(body: ProfileCreate):
    return svc.create(
        name=body.name,
        filters=body.filters,
        mode=body.mode,
        plex_user=body.plex_user,
    )


@router.get("/{profile_id}")
def get_profile(profile_id: int):
    profile = svc.get(profile_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/{profile_id}")
def update_profile(profile_id: int, body: ProfileUpdate):
    existing = svc.get(profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    svc.update(
        profile_id,
        name=body.name,
        filters=body.filters,
        mode=body.mode,
        plex_user=body.plex_user,
    )
    return svc.get(profile_id)


@router.delete("/{profile_id}", status_code=204)
def delete_profile(profile_id: int):
    existing = svc.get(profile_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    svc.delete(profile_id)
