"""HTMX-driven server-rendered views using Jinja2 templates."""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@router.get("/", response_class=HTMLResponse)
async def index(request: Request) -> Any:
    """Landing page / dashboard."""
    return templates.TemplateResponse(request, "base.html")
