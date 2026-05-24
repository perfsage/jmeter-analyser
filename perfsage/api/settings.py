"""REST endpoints for user/application settings."""

from fastapi import APIRouter

router = APIRouter(prefix="/settings", tags=["settings"])
