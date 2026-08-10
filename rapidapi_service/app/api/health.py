"""Health/liveness/readiness endpoints (Plan section 44)."""
from fastapi import APIRouter, HTTPException, Request

from app import config
from app.fetcher import client as fetcher_client
from app.ratelimit import redis as redis_state

router = APIRouter(tags=["Health"])


@router.get("/health")
def health_check():
    """Public liveness probe — exposes only service name and version.
    Use /health/details (requires HEALTH_DETAILS_SECRET header) for full operational status."""
    return {
        "status": "online",
        "service": "Web Metadata & Contact Extractor API",
        "version": config.APP_VERSION,
    }


@router.get("/health/details")
def health_details(request: Request):
    """Protected operational health endpoint.
    Requires X-Health-Secret header matching HEALTH_DETAILS_SECRET env var.
    Returns Redis mode, status, engine details and configuration flags for monitoring."""
    if config.HEALTH_DETAILS_SECRET:
        provided = request.headers.get("x-health-secret", "")
        if not provided or provided != config.HEALTH_DETAILS_SECRET:
            raise HTTPException(status_code=403, detail="Invalid or missing X-Health-Secret header.")
    return {
        "status": "online",
        "service": "Web Metadata & Contact Extractor API",
        "version": config.APP_VERSION,
        "engine": "FastAPI + ORJSON + Selectolax + HTTP/2 + Async DNS + IP-Pinned Anti-SSRF Shield",
        "rapidapi_protected": bool(config.RAPIDAPI_PROXY_SECRET),
        "trust_proxy": config.TRUST_PROXY,
        "trusted_proxy_networks": len(config.TRUSTED_PROXY_NETWORKS),
        "rate_limiter_mode": redis_state.redis_mode,
        "redis_status": redis_state.redis_status,
        "redis_configured": bool(config.REDIS_URL),
    }


@router.get("/health/ready")
def health_ready():
    """Kubernetes/Render readiness probe.
    Returns 200 when the process is ready to serve traffic (HTTP client initialized).
    Returns 503 when still starting up. Does NOT expose internal details."""
    if fetcher_client.http_client is None:
        raise HTTPException(status_code=503, detail="Service not ready: HTTP client not initialized.")
    return {"status": "ready"}
