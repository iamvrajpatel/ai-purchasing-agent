import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


async def backend_get(path: str):
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{get_settings().backend_api_url.rstrip('/')}{path}")
    except httpx.RequestError:
        return None
    if response.status_code >= 400:
        return None
    return response.json()


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    summary = await backend_get("/api/v1/dashboard/summary") or {}
    return templates.TemplateResponse(request, "dashboard.html", {"summary": summary, "active": "dashboard"})

