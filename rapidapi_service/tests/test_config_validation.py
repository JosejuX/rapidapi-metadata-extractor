"""pydantic-settings migration (Plan §46): invalid configuration must fail
fast with a clear error at startup, not surface as a confusing runtime bug.

app.config evaluates Settings() once at import time and every other module
holds a reference to that same module object, so each test that reloads it
under a patched environment MUST reload it back to defaults afterward —
otherwise a mutated RATE_LIMIT_PER_MINUTE etc. would leak into unrelated
tests that run later in the same process. Teardown explicitly pops the env
vars itself (rather than relying on monkeypatch's revert-then-fixture-
teardown ordering, which isn't something to depend on here) before doing
the final reload, so restoration doesn't depend on fixture teardown order."""
import importlib
import os

import pytest
from pydantic import ValidationError

import app.config as config_module

_ENV_VARS_UNDER_TEST = (
    "RATE_LIMIT_PER_MINUTE", "STREAM_SOFT_LIMIT", "STREAM_HARD_LIMIT",
    "CACHE_MAXSIZE", "CACHE_TTL_SECONDS", "ALLOWED_ORIGINS", "TRUSTED_PROXY_IPS",
)


@pytest.fixture(autouse=True)
def _restore_config_after_test():
    yield
    for var in _ENV_VARS_UNDER_TEST:
        os.environ.pop(var, None)
    importlib.reload(config_module)


def _reload_with_env(**env):
    for key, value in env.items():
        os.environ[key] = value
    return importlib.reload(config_module)


def test_negative_rate_limit_raises_at_import():
    os.environ["RATE_LIMIT_PER_MINUTE"] = "-5"
    with pytest.raises(ValidationError):
        importlib.reload(config_module)


def test_soft_limit_above_hard_limit_raises_at_import():
    os.environ["STREAM_SOFT_LIMIT"] = "999999999"
    os.environ["STREAM_HARD_LIMIT"] = "100"
    with pytest.raises(ValidationError):
        importlib.reload(config_module)


def test_valid_override_is_applied():
    reloaded = _reload_with_env(RATE_LIMIT_PER_MINUTE="120")
    assert reloaded.RATE_LIMIT_PER_MINUTE == 120


def test_defaults_unchanged_with_no_env_vars():
    for var in _ENV_VARS_UNDER_TEST:
        os.environ.pop(var, None)
    reloaded = importlib.reload(config_module)
    assert reloaded.RATE_LIMIT_PER_MINUTE == 60
    assert reloaded.STREAM_SOFT_LIMIT == 64 * 1024
    assert reloaded.STREAM_HARD_LIMIT == 256 * 1024
    assert reloaded.CACHE_MAXSIZE == 5000
    assert reloaded.CACHE_TTL_SECONDS == 900
    assert reloaded.ALLOWED_ORIGINS == ["*"]


def test_allowed_origins_parses_comma_separated_list():
    reloaded = _reload_with_env(ALLOWED_ORIGINS="https://example.com,https://foo.example.com")
    assert reloaded.ALLOWED_ORIGINS == ["https://example.com", "https://foo.example.com"]


def test_trusted_proxy_ips_parses_valid_cidrs_and_skips_invalid():
    reloaded = _reload_with_env(TRUSTED_PROXY_IPS="10.0.0.0/8, not-a-cidr, 192.168.1.0/24")
    assert len(reloaded.TRUSTED_PROXY_NETWORKS) == 2
