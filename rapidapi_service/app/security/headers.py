"""RapidAPI proxy-secret verification dependency."""
from typing import Optional
from fastapi import Header

from app import config
from app.core.errors import AppError, AUTH_FORBIDDEN


def verify_rapidapi_secret(x_rapidapi_proxy_secret: Optional[str] = Header(None)):
    if config.RAPIDAPI_PROXY_SECRET and x_rapidapi_proxy_secret != config.RAPIDAPI_PROXY_SECRET:
        raise AppError(
            status_code=403,
            code=AUTH_FORBIDDEN,
            detail="Access denied: Invalid or missing X-RapidAPI-Proxy-Secret header."
        )
