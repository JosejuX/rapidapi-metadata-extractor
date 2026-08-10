"""
Application entrypoint — thin wiring only (Plan section 2: split the monolith
into modules without changing behavior). All actual logic lives in the
config / core / security / fetcher / cache / ratelimit / extraction / models /
api / ui packages; this file just assembles the FastAPI app from them.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import ORJSONResponse

from app import config
from app.api import (
    contacts,
    demo,
    extract,
    health,
    links,
    markdown,
    metadata,
    observability,
    schema,
    security,
    seo,
    tech_stack,
    ui,
)
from app.core.errors import AppError, app_error_handler
from app.core.tracing import add_request_id
from app.lifecycle import lifespan

app = FastAPI(
    title="Web Metadata & Contact Extractor API",
    description=(
        "Ultra-fast, enterprise REST API: Extended Metadata, Anti-SSRF Shield, "
        "Async Redis Rate Limiter (auto-reconnect + health observability), "
        "Multi-Worker Gunicorn, Favicon HD Engine, NLP Summary, HTTP/2, ORJSON."
    ),
    version=config.APP_VERSION,
    default_response_class=ORJSONResponse,
    lifespan=lifespan
)

# CORS: allow_credentials=False for security (API Key / Header Auth, no cookies).
# Origins default to "*" (see app.config.ALLOWED_ORIGINS docstring) but are
# configurable via ALLOWED_ORIGINS for self-hosted deployments that want to
# restrict to known frontends.
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# §32/40: X-Request-ID middleware — generate or preserve an inbound request ID
# for end-to-end tracing across logs, responses and monitoring.
app.middleware("http")(add_request_id)

# §34: structured error model — additive "error" object alongside the
# existing "detail" string; status codes and "detail" are unchanged for v1.
app.add_exception_handler(AppError, app_error_handler)

app.include_router(ui.router)
app.include_router(demo.router)
app.include_router(health.router)
app.include_router(observability.router)
app.include_router(extract.router)
app.include_router(metadata.router)
app.include_router(contacts.router)
app.include_router(tech_stack.router)
app.include_router(schema.router)
app.include_router(security.router)
app.include_router(markdown.router)
app.include_router(seo.router)
app.include_router(links.router)
