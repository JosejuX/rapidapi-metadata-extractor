"""Prometheus scrape endpoint (Plan section 39)."""
from fastapi import APIRouter, Response

from app.observability.metrics import CONTENT_TYPE_LATEST, render_metrics

router = APIRouter(tags=["Observability"])


@router.get("/metrics", include_in_schema=False)
def metrics_endpoint():
    """Prometheus text-exposition-format scrape target. Unauthenticated by
    convention (standard Prometheus/Grafana practice — network-level access
    control, e.g. a private scrape network or reverse-proxy rule, is the
    expected protection layer, not an application-level secret)."""
    return Response(content=render_metrics(), media_type=CONTENT_TYPE_LATEST)
