from __future__ import annotations

from ipaddress import ip_address

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpRequest


def get_client_ip(request: HttpRequest) -> str | None:
    source = settings.CLIENT_IP_SOURCE
    if source == "remote_addr":
        raw_ip = request.META.get("REMOTE_ADDR") or ""
    elif source == "render_cloudflare":
        raw_ip = request.META.get("HTTP_CF_CONNECTING_IP") or ""
    else:
        raise ImproperlyConfigured("Unsupported CLIENT_IP_SOURCE.")

    try:
        value = raw_ip.strip()
        if "%" in value:
            return None
        return str(ip_address(value))
    except ValueError:
        return None


def get_client_ip_key(request: HttpRequest) -> str:
    return get_client_ip(request) or "no-ip"
