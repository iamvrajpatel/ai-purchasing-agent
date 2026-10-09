import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.config import get_settings

templates = Jinja2Templates(directory="app/templates")
router = APIRouter(prefix="/recommendations")


async def backend_get(path: str):
    try:
        async with httpx.AsyncClient(timeout=2) as client:
            response = await client.get(f"{get_settings().backend_api_url.rstrip('/')}{path}")
    except httpx.RequestError:
        return None
    return response.json() if response.status_code < 400 else None


@router.get("", response_class=HTMLResponse)
async def recommendations(request: Request):
    rows = await backend_get("/api/v1/recommendations") or []
    return templates.TemplateResponse(request, "recommendations.html", {"recommendations": rows, "active": "recommendations"})


@router.get("/{recommendation_id}", response_class=HTMLResponse)
async def recommendation_detail(recommendation_id: int, request: Request):
    recommendation = await backend_get(f"/api/v1/recommendations/{recommendation_id}")
    return templates.TemplateResponse(request, "recommendation_detail.html", {"recommendation": recommendation, "active": "recommendations"})

