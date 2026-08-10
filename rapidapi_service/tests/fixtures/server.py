"""
tests/fixtures/server.py — Local HTML fixture server for offline/deterministic tests.
Plan §47: Test with local HTML fixtures instead of live sites.
Plan §48: Full SSRF test matrix using local fixtures.

Usage:
    python -m tests.fixtures.server        # starts server on port 19877
    python tests/run_fixture_tests.py      # runs all fixture-based tests
"""
import threading
import http.server
import os

FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "html")
PORT = 19877


class FixtureHandler(http.server.SimpleHTTPRequestHandler):
    """Serves static HTML files from the fixtures/html/ directory."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=FIXTURE_DIR, **kwargs)

    def log_message(self, format, *args):
        pass  # suppress request logs during tests


def start_fixture_server(port: int = PORT) -> http.server.HTTPServer:
    """Start the fixture server in a daemon thread. Returns the server object."""
    server = http.server.HTTPServer(("127.0.0.1", port), FixtureHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server
