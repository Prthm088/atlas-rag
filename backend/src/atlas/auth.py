import asyncio
from dataclasses import dataclass
from functools import lru_cache
from typing import Annotated, Any
from uuid import UUID

import httpx
import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from atlas.config import Settings, get_settings
from atlas.errors import AppError

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class AuthUser:
    id: UUID
    email: str | None
    role: str
    claims: dict[str, Any]


@lru_cache
def _jwk_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=600)


async def _verify_with_jwks(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.jwks_url or not settings.auth_issuer:
        raise AppError("auth_not_configured", "Authentication is unavailable.", status_code=503)
    client = _jwk_client(settings.jwks_url)
    try:
        key = await asyncio.to_thread(client.get_signing_key_from_jwt, token)
        return jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256", "EdDSA"],
            audience=settings.supabase_jwt_audience,
            issuer=settings.auth_issuer,
            options={"require": ["exp", "sub", "role"]},
        )
    except (jwt.PyJWTError, ValueError) as exc:
        raise AppError("invalid_token", "Your session is invalid or expired.", status_code=401) from exc


async def _verify_remotely(token: str, settings: Settings) -> dict[str, Any]:
    if not settings.supabase_url or not settings.supabase_publishable_key:
        raise AppError("auth_not_configured", "Authentication is unavailable.", status_code=503)
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            response = await client.get(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/user",
                headers={
                    "apikey": settings.supabase_publishable_key,
                    "Authorization": f"Bearer {token}",
                },
            )
    except httpx.HTTPError as exc:
        raise AppError("auth_unavailable", "Authentication is temporarily unavailable.", status_code=503) from exc
    if response.status_code != 200:
        raise AppError("invalid_token", "Your session is invalid or expired.", status_code=401)
    data = response.json()
    return {
        "sub": data.get("id"),
        "email": data.get("email"),
        "role": data.get("role", "authenticated"),
        "email_confirmed_at": data.get("email_confirmed_at"),
    }


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthUser:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError("authentication_required", "Please sign in to continue.", status_code=401)
    token = credentials.credentials
    claims = (
        await _verify_with_jwks(token, settings)
        if settings.auth_verify_mode == "jwks"
        else await _verify_remotely(token, settings)
    )
    try:
        user_id = UUID(str(claims["sub"]))
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("invalid_token", "Your session is invalid or expired.", status_code=401) from exc
    return AuthUser(
        id=user_id,
        email=claims.get("email"),
        role=str(claims.get("role", "authenticated")),
        claims=claims,
    )


CurrentUser = Annotated[AuthUser, Depends(get_current_user)]
