from __future__ import annotations

import hashlib
import hmac
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException

from forgeai.config import Settings, get_settings

ROLE_READER = "reader"
ROLE_REVIEWER = "reviewer"
ROLE_OPERATOR = "operator"


@dataclass(frozen=True)
class Principal:
    key_id: str
    roles: frozenset[str]

    def has_role(self, role: str) -> bool:
        return role in self.roles


def _parse_bearer(value: str | None) -> str:
    if not value:
        raise HTTPException(status_code=401, detail="bearer token required")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=401, detail="bearer token required")
    return token.strip()


def authenticate(
    authorization: str | None,
    settings: Settings,
) -> Principal:
    if not settings.auth_required:
        return Principal(
            key_id="development",
            roles=frozenset({ROLE_READER, ROLE_REVIEWER, ROLE_OPERATOR}),
        )

    token = _parse_bearer(authorization)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
    for key_id, roles in settings.api_key_roles.items():
        if hmac.compare_digest(digest, key_id):
            return Principal(key_id=key_id, roles=frozenset(roles))
    raise HTTPException(status_code=401, detail="invalid credentials")


def require_role(role: str) -> Callable[..., Principal]:
    def dependency(
        authorization: str | None = Header(None, alias="Authorization"),
        settings: Settings = Depends(get_settings),
    ) -> Principal:
        principal = authenticate(authorization, settings)
        if not principal.has_role(role):
            raise HTTPException(status_code=403, detail=f"role '{role}' is required")
        return principal

    return dependency
