from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass


class AuthenticationError(ValueError):
    """Raised when an API token cannot be authenticated."""


@dataclass(frozen=True)
class Principal:
    subject: str
    roles: frozenset[str]

    def require(self, role: str) -> None:
        if role not in self.roles:
            raise PermissionError(f"role '{role}' is required")


def issue_token(subject: str, roles: set[str], secret: str, ttl_seconds: int = 3600) -> str:
    if not subject or not secret:
        raise ValueError("subject and secret are required")
    expires_at = int(time.time()) + ttl_seconds
    role_text = ",".join(sorted(roles))
    body = f"{subject}|{role_text}|{expires_at}"
    signature = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"forgeai.v1.{body}|{signature}"


def authenticate_token(token: str | None, secret: str | None) -> Principal:
    if not token or not secret or not token.startswith("forgeai.v1."):
        raise AuthenticationError("missing or invalid authorization token")
    raw = token.removeprefix("forgeai.v1.")
    parts = raw.split("|")
    if len(parts) != 4:
        raise AuthenticationError("invalid authorization token")
    subject, role_text, expiry_text, supplied_signature = parts
    body = "|".join(parts[:3])
    expected_signature = hmac.new(
        secret.encode(), body.encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, supplied_signature):
        raise AuthenticationError("invalid authorization token")
    try:
        expires_at = int(expiry_text)
    except ValueError as exc:
        raise AuthenticationError("invalid token expiry") from exc
    if expires_at <= int(time.time()):
        raise AuthenticationError("authorization token expired")
    roles = frozenset(filter(None, role_text.split(",")))
    return Principal(subject=subject, roles=roles)
