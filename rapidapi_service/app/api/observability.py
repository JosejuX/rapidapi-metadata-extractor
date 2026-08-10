"""Prometheus scrape endpoint (Plan section 39)."""
from fastapi import APIRouter, HTTPException, Request, Response

from app import config
from app.observability.metrics import CONTENT_TYPE_LATEST, render_metrics

router = APIRouter(tags=["Observability"])


@router.get("/metrics", include_in_schema=False)
def metrics_endpoint(request: Request):
    """Prometheus text-exposition-format scrape target. Unauthenticated by
    default (standard Prometheus/Grafana practice — network-level access
    control, e.g. a private scrape network or reverse-proxy rule, is the
    expected protection layer, not an application-level secret). Set
    METRICS_SECRET to require an X-Metrics-Secret header matching it instead
    — e.g. for a self-hosted deployment where the port is reachable from the
    internet and there's no network-level control in front of it."""
    if config.METRICS_SECRET:
        provided = request.headers.get("x-metrics-secret", "")
        if not provided or provided != config.METRICS_SECRET:
            raise HTTPException(status_code=403, detail="Invalid or missing X-Metrics-Secret header.")
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
