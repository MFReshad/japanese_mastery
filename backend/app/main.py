from fastapi import FastAPI
from app.core import get_settings
from fastapi.middleware.cors import CORSMiddleware
from app.api.books import router as books_router
from app.api.imports import router as imports_router
from app.api.items import router as items_router
from app.api.library import router as library_router
from app.api.practice import router as practice_router
from app.api.progress import router as progress_router
from app.api.study import router as study_router
from app.api.vocabulary_order import router as vocabulary_order_router
from app.core.logging import configure_logging
from fastapi import Request
from fastapi.responses import JSONResponse
from app.errors import NotFound, Conflict, InvalidOperation
from sqlalchemy.exc import IntegrityError
import logging
import traceback
import secrets
import time
from uuid import uuid4


configure_logging()

app = FastAPI(title="Japanese Mastery API")


app.include_router(books_router)
app.include_router(items_router)
app.include_router(library_router)
app.include_router(practice_router)
app.include_router(progress_router)
app.include_router(imports_router)
app.include_router(study_router)
app.include_router(vocabulary_order_router)


@app.get("/health")
def health():
    return {"ok": True}


@app.exception_handler(NotFound)
@app.exception_handler(Conflict)
@app.exception_handler(InvalidOperation)
async def domain_error(request: Request, exc: Exception):
    return JSONResponse(
        status_code=404
        if isinstance(exc, NotFound)
        else 409
        if isinstance(exc, Conflict)
        else 400,
        content={"detail": str(exc)},
    )


@app.exception_handler(IntegrityError)
async def integrity_error(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409, content={"detail": "This change conflicts with existing data"}
    )


@app.middleware("http")
async def access_and_observability(request: Request, call_next):
    started = time.monotonic()
    request_id = uuid4().hex
    settings = get_settings()
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        expected = settings.personal_access_token
        test_only = (
            settings.allow_sqlite_for_tests
            and settings.sqlalchemy_database_url.startswith("sqlite")
        )
        if not expected and not test_only:
            return JSONResponse(
                status_code=503, content={"detail": "Personal access is not configured"}
            )
        if expected and not secrets.compare_digest(
            request.headers.get("authorization", ""), "Bearer " + expected
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Unlock personal access to make changes"},
            )
    try:
        response = await call_next(request)
    except Exception as exc:
        logging.getLogger("app.requests").error(
            "request_id=%s method=%s path=%s duration_ms=%.1f error=%s stack=%s",
            request_id,
            request.method,
            request.url.path,
            (time.monotonic() - started) * 1000,
            type(exc).__name__,
            "".join(traceback.format_tb(exc.__traceback__)),
        )
        response = JSONResponse(
            status_code=500,
            content={"detail": "Unexpected server error", "request_id": request_id},
        )
    duration = (time.monotonic() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["Server-Timing"] = f"app;dur={duration:.1f}"
    logging.getLogger("app.requests").info(
        "request_id=%s method=%s path=%s status=%s duration_ms=%.1f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )
    return response


# CORS wraps authentication errors too, so clients can classify 401/503.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
