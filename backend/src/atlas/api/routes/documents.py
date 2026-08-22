import hashlib
import hmac
import secrets
from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.auth import CurrentUser
from atlas.config import Settings, get_settings
from atlas.database import get_db
from atlas.errors import AppError
from atlas.schemas import (
    DocumentListResponse,
    DocumentResponse,
    JobResponse,
    SignedUrlResponse,
    UploadCompleteRequest,
    UploadIntentRequest,
    UploadIntentResponse,
)
from atlas.services.parsers import sanitize_filename, validate_declared_type
from atlas.services.rate_limit import rate_limiter
from atlas.services.storage import get_storage

router = APIRouter(prefix="/documents", tags=["documents"])

DOCUMENT_SELECT = """
select d.id, d.name, d.mime_type, d.size_bytes, d.status::text, d.error_code,
       d.error_message, coalesce(v.chunk_count, 0)::int as chunk_count,
       j.stage as job_stage, j.progress as job_progress,
       d.created_at, d.updated_at
from public.documents d
left join public.document_versions v on v.id = d.active_version_id
left join lateral (
  select stage, progress
  from public.ingestion_jobs
  where document_id = d.id
  order by created_at desc
  limit 1
) j on true
where d.user_id = :user_id and d.deleted_at is null
"""


def _document_response(row: object) -> DocumentResponse:
    mapping = row if isinstance(row, dict) else row._mapping  # type: ignore[attr-defined]
    return DocumentResponse(**dict(mapping))


@router.get("", response_model=DocumentListResponse)
async def list_documents(user: CurrentUser, session: AsyncSession = Depends(get_db)) -> DocumentListResponse:
    result = await session.execute(
        text(DOCUMENT_SELECT + " order by d.created_at desc"),
        {"user_id": user.id},
    )
    items = [_document_response(row) for row in result]
    return DocumentListResponse(items=items, total=len(items))


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    result = await session.execute(
        text(DOCUMENT_SELECT + " and d.id = :document_id"),
        {"user_id": user.id, "document_id": document_id},
    )
    row = result.first()
    if row is None:
        raise AppError("document_not_found", "The document does not exist or is not accessible.", status_code=404)
    return _document_response(row)


@router.post("/upload-intents", response_model=UploadIntentResponse, status_code=status.HTTP_201_CREATED)
async def create_upload_intent(
    payload: UploadIntentRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> UploadIntentResponse:
    await rate_limiter.enforce(
        f"upload:{user.id}", limit=settings.uploads_per_hour, window_seconds=3600
    )
    filename = sanitize_filename(payload.filename)
    validate_declared_type(filename, payload.mime_type)
    if payload.size_bytes > settings.max_file_bytes:
        raise AppError(
            "file_too_large",
            f"Files are limited to {settings.max_file_bytes // (1024 * 1024)} MB.",
            status_code=413,
        )
    usage = await session.execute(
        text(
            """
            select count(*)::int as document_count, coalesce(sum(size_bytes), 0)::bigint as storage_bytes
            from public.documents
            where user_id = :user_id and deleted_at is null and status <> 'deleting'
            """
        ),
        {"user_id": user.id},
    )
    current = usage.mappings().one()
    if int(current["document_count"]) >= settings.max_documents_per_user:
        raise AppError("document_quota_exceeded", "Delete a document before uploading another.", status_code=409)
    if int(current["storage_bytes"]) + payload.size_bytes > settings.max_storage_bytes_per_user:
        raise AppError("storage_quota_exceeded", "This upload would exceed your storage allowance.", status_code=409)

    document_id, version_id = uuid4(), uuid4()
    raw_token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    storage_path = f"{user.id}/{document_id}/original/{filename}"
    await session.execute(
        text(
            """
            insert into public.documents (
              id, user_id, name, mime_type, size_bytes, storage_path,
              status, upload_token_hash, upload_token_expires_at
            ) values (
              :id, :user_id, :name, :mime_type, :size_bytes, :storage_path,
              'awaiting_upload', :token_hash, now() + interval '30 minutes'
            )
            """
        ),
        {
            "id": document_id,
            "user_id": user.id,
            "name": filename,
            "mime_type": payload.mime_type,
            "size_bytes": payload.size_bytes,
            "storage_path": storage_path,
            "token_hash": token_hash,
        },
    )
    await session.execute(
        text(
            """
            insert into public.document_versions (id, document_id, user_id, version_number)
            values (:id, :document_id, :user_id, 1)
            """
        ),
        {"id": version_id, "document_id": document_id, "user_id": user.id},
    )
    await session.execute(
        text(
            """
            insert into public.audit_events (user_id, action, target_type, target_id)
            values (:user_id, 'document.upload_intent_created', 'document', :document_id)
            """
        ),
        {"user_id": user.id, "document_id": document_id},
    )
    await session.commit()
    return UploadIntentResponse(
        document_id=document_id,
        version_id=version_id,
        storage_bucket=settings.supabase_storage_bucket,
        storage_path=storage_path,
        upload_token=raw_token,
    )


@router.post("/{document_id}/complete", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def complete_upload(
    document_id: UUID,
    payload: UploadCompleteRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    result = await session.execute(
        text(
            """
            select d.storage_path, d.upload_token_hash, d.upload_token_expires_at, v.id as version_id
            from public.documents d
            join public.document_versions v on v.document_id = d.id and v.version_number = 1
            where d.id = :document_id and d.user_id = :user_id
              and d.status = 'awaiting_upload' and d.deleted_at is null
            for update
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    document = result.mappings().first()
    if document is None:
        raise AppError("document_not_found", "The upload is no longer available.", status_code=404)
    supplied_hash = hashlib.sha256(payload.upload_token.encode()).hexdigest()
    expires_at: datetime = document["upload_token_expires_at"]
    now = datetime.now(expires_at.tzinfo)
    if expires_at <= now or not hmac.compare_digest(supplied_hash, str(document["upload_token_hash"])):
        raise AppError("invalid_upload_token", "The upload confirmation is invalid or expired.", status_code=401)
    storage = get_storage(settings)
    if not await storage.exists(str(document["storage_path"])):
        raise AppError("upload_missing", "Upload the file before confirming it.", status_code=409)
    job = await session.execute(
        text(
            """
            insert into public.ingestion_jobs (
              user_id, document_id, version_id, max_attempts, payload
            ) values (
              :user_id, :document_id, :version_id, :max_attempts,
              jsonb_build_object('reason', 'initial_upload')
            )
            returning id, document_id, status::text, stage, progress, attempt_count,
                      error_code, error_message, updated_at
            """
        ),
        {
            "user_id": user.id,
            "document_id": document_id,
            "version_id": document["version_id"],
            "max_attempts": settings.job_max_attempts,
        },
    )
    await session.execute(
        text("update public.documents set status = 'queued' where id = :id and user_id = :user_id"),
        {"id": document_id, "user_id": user.id},
    )
    await session.commit()
    return JobResponse(**dict(job.mappings().one()))


@router.get("/{document_id}/job", response_model=JobResponse)
async def get_document_job(
    document_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> JobResponse:
    result = await session.execute(
        text(
            """
            select id, document_id, status::text, stage, progress, attempt_count,
                   error_code, error_message, updated_at
            from public.ingestion_jobs
            where document_id = :document_id and user_id = :user_id
            order by created_at desc limit 1
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppError("job_not_found", "No processing job exists for this document.", status_code=404)
    return JobResponse(**dict(row))


@router.post("/{document_id}/retry", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
@router.post("/{document_id}/reprocess", response_model=JobResponse, status_code=status.HTTP_202_ACCEPTED)
async def retry_document(
    document_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> JobResponse:
    document = await session.execute(
        text(
            """
            select id from public.documents
            where id = :document_id and user_id = :user_id
              and status in ('failed', 'ready') and deleted_at is null
            for update
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    if document.first() is None:
        raise AppError(
            "document_not_reprocessable",
            "Only ready or failed documents can be reprocessed.",
            status_code=409,
        )
    version = await session.execute(
        text(
            """
            insert into public.document_versions (document_id, user_id, version_number)
            select :document_id, :user_id, coalesce(max(version_number), 0) + 1
            from public.document_versions where document_id = :document_id
            returning id
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    version_id = version.scalar_one()
    job = await session.execute(
        text(
            """
            insert into public.ingestion_jobs (user_id, document_id, version_id, max_attempts, payload)
            values (:user_id, :document_id, :version_id, :max_attempts,
                    jsonb_build_object('reason', 'manual_retry'))
            returning id, document_id, status::text, stage, progress, attempt_count,
                      error_code, error_message, updated_at
            """
        ),
        {
            "user_id": user.id,
            "document_id": document_id,
            "version_id": version_id,
            "max_attempts": settings.job_max_attempts,
        },
    )
    await session.execute(
        text("update public.documents set status = 'queued', error_code = null, error_message = null where id = :id"),
        {"id": document_id},
    )
    await session.commit()
    return JobResponse(**dict(job.mappings().one()))


@router.get("/{document_id}/source-url", response_model=SignedUrlResponse)
async def get_source_url(
    document_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> SignedUrlResponse:
    result = await session.execute(
        text(
            """
            select storage_path from public.documents
            where id = :document_id and user_id = :user_id and deleted_at is null
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    path = result.scalar_one_or_none()
    if path is None:
        raise AppError("document_not_found", "The document does not exist or is not accessible.", status_code=404)
    expires_in = 300
    url = await get_storage(settings).create_signed_url(str(path), expires_in)
    return SignedUrlResponse(url=url, expires_in=expires_in)


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> Response:
    result = await session.execute(
        text(
            """
            update public.documents set status = 'deleting'
            where id = :document_id and user_id = :user_id and deleted_at is null
            returning storage_path
            """
        ),
        {"document_id": document_id, "user_id": user.id},
    )
    path = result.scalar_one_or_none()
    if path is None:
        raise AppError("document_not_found", "The document does not exist or is not accessible.", status_code=404)
    await session.commit()
    await get_storage(settings).delete(str(path))
    await session.execute(
        text("delete from public.documents where id = :document_id and user_id = :user_id"),
        {"document_id": document_id, "user_id": user.id},
    )
    await session.execute(
        text(
            """
            insert into public.audit_events (user_id, action, target_type, target_id)
            values (:user_id, 'document.deleted', 'document', :document_id)
            """
        ),
        {"user_id": user.id, "document_id": document_id},
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
