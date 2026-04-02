from __future__ import annotations

from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str | None:
    """
    Return the best-effort client IP address extracted from the request.

    Uses the first value from HTTP_X_FORWARDED_FOR when present,
    otherwise falls back to REMOTE_ADDR.

    Returns:
        Client IP as a string, or None if unavailable.
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        forwarded_ips = [ip.strip() for ip in x_forwarded_for.split(",") if ip.strip()]
        if forwarded_ips:
            return forwarded_ips[0]

    remote_addr = request.META.get("REMOTE_ADDR")
    return remote_addr or None


def get_client_ip_key(request: HttpRequest) -> str:
    """
    Return a stable cache-safe key based on the client IP.
    """
    return get_client_ip(request) or "no-ip"
