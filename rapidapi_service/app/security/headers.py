"""Reverse-proxy secret verification dependency.

Each marketplace (RapidAPI, Zyla, ...) injects its own header with its own
secret, so a leak on one marketplace's side doesn't expose traffic from the
others — checked as an allowlist of configured secrets rather than a single
shared one.
"""
from typing import Optional

from fastapi import Header

from app import config
from app.core.errors import AUTH_FORBIDDEN, AppError


def verify_rapidapi_secret(
    x_rapidapi_proxy_secret: Optional[str] = Header(None),
    x_zyla_proxy_secret: Optional[str] = Header(None),
):
    configured_secrets = {s for s in (config.RAPIDAPI_PROXY_SECRET, config.ZYLA_PROXY_SECRET) if s}
    if not configured_secrets:
        return
    if x_rapidapi_proxy_secret in configured_secrets or x_zyla_proxy_secret in configured_secrets:
        return
    raise AppError(
        status_code=403,
        code=AUTH_FORBIDDEN,
        detail="Access denied: Invalid or missing proxy secret header."
    )
