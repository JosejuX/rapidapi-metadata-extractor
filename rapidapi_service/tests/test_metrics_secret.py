"""
METRICS_SECRET (Plan feedback: /metrics being open by default is easy to
accidentally expose on a self-hosted `docker run` with the port published
to the internet). Same opt-in pattern as HEALTH_DETAILS_SECRET: unset by
default (still fully open, matches existing documented behavior), set it to
require an X-Metrics-Secret header.
"""
from fastapi.testclient import TestClient

from app import config
from app.main import app


def test_metrics_open_by_default_when_no_secret_configured():
    assert config.METRICS_SECRET is None
    client = TestClient(app)
    res = client.get("/metrics")
    assert res.status_code == 200
    assert "requests_total" in res.text


def test_metrics_requires_header_when_secret_configured(monkeypatch):
    monkeypatch.setattr(config, "METRICS_SECRET", "topsecret123")
    client = TestClient(app)
    try:
        res_no_header = client.get("/metrics")
        assert res_no_header.status_code == 403

        res_wrong = client.get("/metrics", headers={"X-Metrics-Secret": "wrong"})
        assert res_wrong.status_code == 403

        res_correct = client.get("/metrics", headers={"X-Metrics-Secret": "topsecret123"})
        assert res_correct.status_code == 200
        assert "requests_total" in res_correct.text
    finally:
        monkeypatch.setattr(config, "METRICS_SECRET", None)
