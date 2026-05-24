"""REST endpoints for report export (HTML + PDF)."""

from fastapi import APIRouter

router = APIRouter(prefix="/exports", tags=["exports"])
