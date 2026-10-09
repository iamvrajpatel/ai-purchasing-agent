from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from app.api.routes import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.utils.exceptions import AuthorizationError, DomainError, NotFoundError, ValidationError

configure_logging()
settings = get_settings()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(DomainError)
async def domain_error_handler(_request: Request, exc: DomainError):
    status = 400
    if isinstance(exc, NotFoundError):
        status = 404
    elif isinstance(exc, AuthorizationError):
        status = 403
    elif isinstance(exc, ValidationError):
        status = 422
    return JSONResponse(status_code=status, content={"detail": exc.message, "code": exc.code})


@app.exception_handler(OperationalError)
async def database_operational_error_handler(_request: Request, exc: OperationalError):
    return JSONResponse(
        status_code=503,
        content={
            "detail": "Database connection failed. Check DATABASE_URL and PostgreSQL credentials, then run migrations and seed data.",
            "code": "DATABASE_CONNECTION_ERROR",
        },
    )


@app.exception_handler(SQLAlchemyError)
async def database_error_handler(_request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={"detail": "Database operation failed.", "code": "DATABASE_ERROR"},
    )


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(api_router)

