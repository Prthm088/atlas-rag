from pathlib import Path
from uuid import uuid4

import pytest
import respx
from fastapi.security import HTTPAuthorizationCredentials
from httpx import Response

from atlas.auth import get_current_user
from atlas.config import Settings
from atlas.errors import AppError
from atlas.services.rate_limit import InMemoryRateLimiter
from atlas.services.storage import FilesystemStorage, validate_storage_path


def test_storage_paths_reject_traversal() -> None:
    for path in ("../secret.txt", "/absolute.txt", "user/../../secret.txt"):
        with pytest.raises(AppError) as caught:
            validate_storage_path(path)
        assert caught.value.code == "invalid_storage_path"


@pytest.mark.asyncio
async def test_filesystem_storage_stays_inside_root(tmp_path: Path) -> None:
    target = tmp_path / "user" / "document.txt"
    target.parent.mkdir()
    target.write_bytes(b"private data")
    storage = FilesystemStorage(tmp_path)

    assert await storage.exists("user/document.txt")
    assert await storage.download("user/document.txt") == b"private data"
    await storage.delete("user/document.txt")
    assert not target.exists()


@pytest.mark.asyncio
async def test_remote_auth_uses_verified_supabase_identity() -> None:
    user_id = uuid4()
    settings = Settings(
        auth_verify_mode="remote",
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="public-key",
    )
    with respx.mock:
        route = respx.get("https://project.supabase.co/auth/v1/user").mock(
            return_value=Response(
                200,
                json={
                    "id": str(user_id),
                    "email": "reader@example.com",
                    "role": "authenticated",
                    "email_confirmed_at": "2026-08-22T00:00:00Z",
                },
            )
        )
        user = await get_current_user(
            HTTPAuthorizationCredentials(scheme="Bearer", credentials="verified-token"),
            settings,
        )
    assert route.called
    assert user.id == user_id
    assert user.email == "reader@example.com"


@pytest.mark.asyncio
async def test_remote_auth_rejects_invalid_session() -> None:
    settings = Settings(
        auth_verify_mode="remote",
        supabase_url="https://project.supabase.co",
        supabase_publishable_key="public-key",
    )
    with respx.mock:
        respx.get("https://project.supabase.co/auth/v1/user").mock(return_value=Response(401))
        with pytest.raises(AppError) as caught:
            await get_current_user(
                HTTPAuthorizationCredentials(scheme="Bearer", credentials="expired-token"),
                settings,
            )
    assert caught.value.code == "invalid_token"
    assert caught.value.status_code == 401


@pytest.mark.asyncio
async def test_rate_limiter_fails_closed_after_limit() -> None:
    limiter = InMemoryRateLimiter()
    await limiter.enforce("user:chat", limit=2, window_seconds=60)
    await limiter.enforce("user:chat", limit=2, window_seconds=60)
    with pytest.raises(AppError) as caught:
        await limiter.enforce("user:chat", limit=2, window_seconds=60)
    assert caught.value.code == "rate_limit_exceeded"
    assert caught.value.details and caught.value.details["retry_after_seconds"] >= 1
