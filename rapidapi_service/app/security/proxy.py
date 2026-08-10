"""Trusted-proxy client IP resolution (Plan section 8.5)."""
import ipaddress

from fastapi import Request

from app import config


def resolve_client_ip(request: Request) -> str:
    """Returns the client IP to use for rate limiting.
    Only trusts X-Forwarded-For when TRUST_PROXY is enabled AND (if configured)
    the direct peer IP belongs to one of TRUSTED_PROXY_NETWORKS."""
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not config.TRUST_PROXY:
        return client_ip

    peer_trusted = True
    if config.TRUSTED_PROXY_NETWORKS:
        try:
            peer_ip_obj = ipaddress.ip_address(client_ip)
            peer_trusted = any(peer_ip_obj in net for net in config.TRUSTED_PROXY_NETWORKS)
        except ValueError:
            peer_trusted = False

    if peer_trusted:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            client_ip = forwarded_for.split(",")[0].strip()

    return client_ip
