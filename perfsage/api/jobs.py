"""REST endpoints for background job status and control."""

from fastapi import APIRouter

router = APIRouter(prefix="/jobs", tags=["jobs"])
