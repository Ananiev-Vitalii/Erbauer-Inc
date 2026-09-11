import requests
from django.conf import settings

TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(
    token: str, remote_ip: str | None = None
) -> dict[str, object]:
    if not token:
        return {"success": False, "error_codes": ["missing-input-response"]}

    secret_key = getattr(settings, "CF_TURNSTILE_SECRET_KEY", "")
    if not secret_key:
        return {"success": False, "error_codes": ["missing-secret"]}

    payload = {
        "secret": secret_key,
        "response": token,
    }

    if remote_ip:
        payload["remoteip"] = remote_ip

    try:
        response = requests.post(TURNSTILE_VERIFY_URL, data=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return {"success": False, "error_codes": ["internal-request-failed"]}
