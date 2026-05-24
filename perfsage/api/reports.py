"""REST endpoints for managing analysis reports."""

from fastapi import APIRouter

router = APIRouter(prefix="/reports", tags=["reports"])
