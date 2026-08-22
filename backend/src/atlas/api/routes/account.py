import httpx
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.auth import CurrentUser
from atlas.config import Settings, get_settings
from atlas.database import get_db
from atlas.errors import AppError
from atlas.schemas import DeleteAccountRequest, ProfileResponse
from atlas.services.storage import get_storage

router = APIRouter(prefix="/account", tags=["account"])


@router.get("/me", response_model=ProfileResponse)
async def get_profile(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> ProfileResponse:
    await session.execute(
        text("insert into public.profiles (id) values (:user_id) on conflict (id) do nothing"),
        {"user_id": user.id},
    )
    result = await session.execute(
        text(
            """
            select p.id, p.display_name,
                   count(d.id) filter (where d.deleted_at is null)::int as document_count,
                   coalesce(sum(d.size_bytes) filter (where d.deleted_at is null), 0)::bigint as storage_bytes
            from public.profiles p
            left join public.documents d on d.user_id = p.id
            where p.id = :user_id
            group by p.id
            """
        ),
        {"user_id": user.id},
    )
    row = result.mappings().one()
    await session.commit()
    return ProfileResponse(
        id=row["id"],
        email=user.email,
        display_name=row["display_name"],
        document_count=row["document_count"],
        storage_bytes=row["storage_bytes"],
        max_documents=settings.max_documents_per_user,
        max_storage_bytes=settings.max_storage_bytes_per_user,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_account(
    payload: DeleteAccountRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    del payload
    rows = await session.execute(
        text("select storage_path from public.documents where user_id = :user_id"),
        {"user_id": user.id},
    )
    storage = get_storage(settings)
    for (path,) in rows.all():
        await storage.delete(str(path))
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise AppError("auth_not_configured", "Account deletion is unavailable.", status_code=503)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.delete(
                f"{settings.supabase_url.rstrip('/')}/auth/v1/admin/users/{user.id}",
                headers={
                    "apikey": settings.supabase_service_role_key,
                    "Authorization": f"Bearer {settings.supabase_service_role_key}",
                },
            )
    except httpx.HTTPError as exc:
        raise AppError("account_deletion_failed", "The account could not be deleted.", status_code=503) from exc
    if response.status_code not in (200, 204, 404):
        raise AppError("account_deletion_failed", "The account could not be deleted.", status_code=503)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
