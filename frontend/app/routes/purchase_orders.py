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
    return response.json() if response.status_code < 400 else None


@router.get("/purchase-orders", response_class=HTMLResponse)
async def purchase_orders(request: Request):
    rows = await backend_get("/api/v1/purchase-orders") or []
    return templates.TemplateResponse(request, "purchase_orders.html", {"purchase_orders": rows, "active": "purchase-orders"})


@router.get("/purchase-orders/{purchase_order_id}", response_class=HTMLResponse)
async def purchase_order_detail(purchase_order_id: int, request: Request):
    row = await backend_get(f"/api/v1/purchase-orders/{purchase_order_id}")
    return templates.TemplateResponse(request, "purchase_order_detail.html", {"purchase_order": row, "active": "purchase-orders"})


@router.get("/approvals", response_class=HTMLResponse)
async def approvals(request: Request):
    rows = await backend_get("/api/v1/approvals") or []
    return templates.TemplateResponse(request, "approvals.html", {"approvals": rows, "active": "approvals"})

