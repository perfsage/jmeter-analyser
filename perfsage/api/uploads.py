"""REST endpoints for JMeter file uploads."""

from fastapi import APIRouter

router = APIRouter(prefix="/uploads", tags=["uploads"])
