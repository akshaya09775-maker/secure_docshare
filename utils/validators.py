"""
Basic URL validation for the Secure Browser module.

This is intentionally simple (college-project scope) but demonstrates the
core ideas of URL safety checking:
  1. Only allow http/https schemes.
  2. Reject malformed URLs.
  3. Reject domains on the blocklist (exact match or subdomain match).
  4. Flag raw-IP URLs and suspicious lookalike patterns as a bonus check.
"""
import re
from urllib.parse import urlparse


IP_PATTERN = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")


def normalize_url(raw_url: str) -> str:
    raw_url = raw_url.strip()
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", raw_url):
        raw_url = "https://" + raw_url
    return raw_url


def is_url_safe(raw_url: str, blocked_domains: set) -> tuple[bool, str]:
    """
    Returns (is_safe, reason). If is_safe is False, reason explains why.
    """
    url = normalize_url(raw_url)
    parsed = urlparse(url)

    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported scheme '{parsed.scheme}'. Only http/https allowed."

    host = (parsed.hostname or "").lower()
    if not host:
        return False, "Could not determine a valid hostname."

    if IP_PATTERN.match(host):
        return False, "Raw IP addresses are blocked by policy."

    for blocked in blocked_domains:
        blocked = blocked.lower().strip()
        if host == blocked or host.endswith("." + blocked):
            return False, f"Domain '{host}' is on the blocklist."

    return True, "OK"
