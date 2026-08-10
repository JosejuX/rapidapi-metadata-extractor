"""
`/api/v1/extract?fields=X` (Plan §37 "fields no debe significar
automáticamente 'hacer todo y luego borrar'") — external review feedback:
requesting a narrow field via `/extract` should cost the same as calling the
matching specialized endpoint, not silently run the full pipeline and
discard everything else.
"""
from unittest import mock

import httpx
from fastapi.testclient import TestClient

import app.fetcher.client as fetcher_client
from app.cache.l1 import cache as l1_cache
from app.main import app

FIXTURE_HTML = b"""<html><head><title>Fields Lazy Fixture</title>
<meta name="description" content="A fixture page for fields laziness tests.">
<script src="/_next/static/chunks/x.js"></script>
</head><body><h1>Hi</h1><p>Contact: info@fields-lazy.com</p></body></html>"""


async def _fake_ssrf(url):
    return (url, "fields-lazy-fixture.ssrfcheck")


def _fixed_transport(body: bytes):
    class FixedTransport(httpx.AsyncBaseTransport):
        async def handle_async_request(self, request):
            return httpx.Response(200, headers={"content-type": "text/html"}, content=body)
    return FixedTransport()


def _hit(fields: str):
    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        return client.get(f"/api/v1/extract?url=https://fields-lazy-fixture.ssrfcheck/page&fields={fields}")


def test_fields_tech_only_never_builds_html_tree():
    with mock.patch("app.extraction.pipeline.HTMLParser") as mock_parser:
        res = _hit("detected_technologies")
        assert res.status_code == 200
        assert res.json()["detected_technologies"] == ["Next.js"]
        mock_parser.assert_not_called()


def test_fields_security_only_never_builds_html_tree():
    with mock.patch("app.extraction.pipeline.HTMLParser") as mock_parser:
        res = _hit("security_score_percentage")
        assert res.status_code == 200
        assert "security_score_percentage" in res.json()
        mock_parser.assert_not_called()


def test_fields_metadata_only_returns_requested_field():
    res = _hit("metadata")
    assert res.status_code == 200
    data = res.json()
    assert data["metadata"]["title"] == "Fields Lazy Fixture"
    assert "detected_technologies" not in data
    assert "markdown_content" not in data


def test_fields_and_dedicated_endpoint_share_a_cache_entry():
    l1_cache.clear()
    fetcher_client.http_client = httpx.AsyncClient(transport=_fixed_transport(FIXTURE_HTML))
    with mock.patch("app.fetcher.client.validate_url_ssrf", _fake_ssrf):
        client = TestClient(app)
        r1 = client.get("/api/v1/extract?url=https://fields-lazy-fixture.ssrfcheck/shared&fields=detected_technologies")
        assert r1.status_code == 200
        r2 = client.get("/api/v1/tech-stack?url=https://fields-lazy-fixture.ssrfcheck/shared")
        assert r2.status_code == 200
        assert r2.json()["execution_time_ms"] == 0.01  # cache hit, reused from the /extract?fields= call


def test_fields_quality_falls_back_to_full_pipeline():
    res = _hit("quality")
    assert res.status_code == 200
    data = res.json()
    assert "quality" in data
    assert isinstance(data["quality"]["score"], float)


def test_unknown_field_name_returns_only_base_fields():
    res = _hit("nonexistent_field,another_fake")
    assert res.status_code == 200
    data = res.json()
    assert "metadata" not in data
    assert "detected_technologies" not in data
    assert "url" in data and "execution_time_ms" in data
