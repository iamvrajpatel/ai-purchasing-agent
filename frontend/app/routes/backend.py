import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from app.config import get_settings

router = APIRouter(prefix="/backend", tags=["backend-proxy"])


@router.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    settings = get_settings()
    url = f"{settings.backend_api_url.rstrip('/')}/{path}"
    body = await request.body()
    headers = {"x-buyer-user": settings.mock_buyer_user}
    content_type = request.headers.get("content-type")
    if content_type:
        headers["content-type"] = content_type
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.request(request.method, url, content=body or None, headers=headers, params=request.query_params)
    try:
        content = response.json()
    except ValueError:
        content = {"detail": response.text}
    return JSONResponse(status_code=response.status_code, content=content)

