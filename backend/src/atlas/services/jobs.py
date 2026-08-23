import asyncio
import hashlib
import json
import os
import socket
import time
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import text

from atlas.config import Settings
from atlas.database import get_session_factory
from atlas.errors import AppError
from atlas.services.chunking import ChunkDraft, chunk_document
from atlas.services.gemini import GeminiProvider
from atlas.services.parsers import parse_document
from atlas.services.retrieval import vector_literal
from atlas.services.storage import get_storage

logger = structlog.get_logger("jobs")


class JobRunner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.worker_id = f"{socket.gethostname()}:{os.getpid()}"
        self.storage = get_storage(settings)
        self.provider = GeminiProvider(settings)
        self._last_cleanup = 0.0

    async def run_forever(self) -> None:
        while True:
            try:
                if time.monotonic() - self._last_cleanup >= 300:
                    await self._cleanup_expired_uploads()
                    self._last_cleanup = time.monotonic()
                job = await self._claim_job()
                if job is None:
                    await asyncio.sleep(self.settings.job_poll_seconds)
                    continue
                await self._process(job)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("job_loop_error")
                await asyncio.sleep(min(10.0, self.settings.job_poll_seconds * 2))

    async def _cleanup_expired_uploads(self) -> None:
        factory = get_session_factory()
        if factory is None:
            return
        async with factory() as session:
            result = await session.execute(
                text(
                    """
                    select id, storage_path
                    from public.documents
                    where status = 'awaiting_upload' and upload_token_expires_at < now()
                    order by upload_token_expires_at
                    limit 25
                    """
                )
            )
            expired = result.mappings().all()
        for row in expired:
            try:
                await self.storage.delete(str(row["storage_path"]))
                async with factory() as session:
                    await session.execute(
                        text(
                            """
                            delete from public.documents
                            where id = :document_id and status = 'awaiting_upload'
                              and upload_token_expires_at < now()
                            """
                        ),
                        {"document_id": row["id"]},
                    )
                    await session.commit()
            except AppError:
                logger.warning("expired_upload_cleanup_failed", document_id=str(row["id"]))

    async def _claim_job(self) -> dict[str, Any] | None:
        factory = get_session_factory()
        if factory is None:
            return None
        async with factory() as session:
            await session.execute(
                text(
                    """
                    update public.ingestion_jobs
                    set status = case when attempt_count >= max_attempts then 'failed'::public.job_status
                                      else 'retrying'::public.job_status end,
                        stage = case when attempt_count >= max_attempts then 'failed' else 'queued' end,
                        available_at = now(), locked_at = null, locked_by = null,
                        error_code = 'worker_interrupted',
                        error_message = 'Processing was interrupted and will resume automatically.'
                    where status = 'running'
                      and coalesce(heartbeat_at, locked_at, updated_at) < now() - interval '10 minutes'
                    """
                )
            )
            result = await session.execute(
                text(
                    """
                    with candidate as (
                      select id
                      from public.ingestion_jobs
                      where status in ('pending', 'retrying')
                        and available_at <= now()
                        and attempt_count < max_attempts
                      order by available_at asc, created_at asc
                      for update skip locked
                      limit 1
                    )
                    update public.ingestion_jobs j
                    set status = 'running', stage = 'downloading', progress = greatest(progress, 5),
                        attempt_count = attempt_count + 1,
                        locked_at = now(), heartbeat_at = now(), locked_by = :worker_id,
                        error_code = null, error_message = null
                    from candidate
                    where j.id = candidate.id
                    returning j.id, j.user_id, j.document_id, j.version_id,
                              j.attempt_count, j.max_attempts
                    """
                ),
                {"worker_id": self.worker_id},
            )
            row = result.mappings().first()
            await session.commit()
            return dict(row) if row else None

    async def _process(self, job: dict[str, Any]) -> None:
        job_id = UUID(str(job["id"]))
        try:
            details = await self._load_details(job_id)
            await self._set_progress(job_id, "downloading", 8)
            payload = await self.storage.download(str(details["storage_path"]))
            if len(payload) != int(details["size_bytes"]):
                raise AppError(
                    "file_size_mismatch",
                    "The uploaded file size does not match the upload request.",
                    status_code=422,
                )
            if len(payload) > self.settings.max_file_bytes:
                raise AppError("file_too_large", "The uploaded file exceeds the size limit.", status_code=413)
            checksum = hashlib.sha256(payload).hexdigest()

            await self._set_progress(job_id, "parsing", 18)
            parsed = await asyncio.to_thread(
                parse_document,
                payload,
                str(details["name"]),
                str(details["mime_type"]),
                self.settings.max_pdf_pages,
            )
            chunks = await asyncio.to_thread(chunk_document, parsed)
            if not chunks:
                raise AppError("empty_document", "The document does not contain readable text.", status_code=422)
            if len(chunks) > self.settings.max_chunks_per_document:
                raise AppError(
                    "chunk_limit_exceeded",
                    "The document is too large to index on this deployment.",
                    status_code=413,
                )

            await self._set_progress(job_id, "embedding", 35)
            vectors: list[list[float]] = []
            batch_size = 24
            for start in range(0, len(chunks), batch_size):
                batch = chunks[start : start + batch_size]
                vectors.extend(await self.provider.embed_documents([chunk.content for chunk in batch]))
                progress = 35 + round(45 * min(1, (start + len(batch)) / len(chunks)))
                await self._set_progress(job_id, "embedding", progress)

            await self._publish(
                job_id=job_id,
                details=details,
                checksum=checksum,
                chunks=chunks,
                vectors=vectors,
                character_count=parsed.character_count,
                page_count=parsed.page_count,
                parser_metadata=parsed.metadata,
            )
            logger.info("ingestion_succeeded", job_id=str(job_id), chunk_count=len(chunks))
        except asyncio.CancelledError:
            raise
        except AppError as exc:
            await self._fail_or_retry(job, exc.code, exc.message, retryable=exc.status_code >= 500)
        except Exception:
            logger.exception("ingestion_unexpected_error", job_id=str(job_id))
            await self._fail_or_retry(
                job,
                "ingestion_internal_error",
                "The document could not be processed because of an internal error.",
                retryable=True,
            )

    async def _load_details(self, job_id: UUID) -> dict[str, Any]:
        factory = get_session_factory()
        if factory is None:
            raise AppError("database_unavailable", "The database is unavailable.", status_code=503)
        async with factory() as session:
            result = await session.execute(
                text(
                    """
                    select j.id, j.user_id, j.document_id, j.version_id,
                           d.name, d.mime_type, d.size_bytes, d.storage_path
                    from public.ingestion_jobs j
                    join public.documents d on d.id = j.document_id and d.user_id = j.user_id
                    join public.document_versions v on v.id = j.version_id and v.user_id = j.user_id
                    where j.id = :job_id and j.status = 'running' and d.deleted_at is null
                      and d.status <> 'deleting'
                    """
                ),
                {"job_id": job_id},
            )
            row = result.mappings().first()
            if row is None:
                raise AppError("job_not_found", "The ingestion job is no longer available.", status_code=404)
            return dict(row)

    async def _set_progress(self, job_id: UUID, stage: str, progress: int) -> None:
        factory = get_session_factory()
        if factory is None:
            return
        async with factory() as session:
            await session.execute(
                text(
                    """
                    update public.ingestion_jobs
                    set stage = :stage, progress = :progress, heartbeat_at = now()
                    where id = :job_id and status = 'running'
                    """
                ),
                {"stage": stage, "progress": progress, "job_id": job_id},
            )
            await session.execute(
                text(
                    """
                    update public.documents d
                    set status = 'processing'
                    from public.ingestion_jobs j
                    where j.id = :job_id and d.id = j.document_id and d.status <> 'deleting'
                    """
                ),
                {"job_id": job_id},
            )
            await session.commit()

    async def _publish(
        self,
        *,
        job_id: UUID,
        details: dict[str, Any],
        checksum: str,
        chunks: list[ChunkDraft],
        vectors: list[list[float]],
        character_count: int,
        page_count: int | None,
        parser_metadata: dict[str, object],
    ) -> None:
        if len(chunks) != len(vectors):
            raise RuntimeError("Chunk and embedding counts do not match")
        factory = get_session_factory()
        if factory is None:
            raise AppError("database_unavailable", "The database is unavailable.", status_code=503)
        version_id = UUID(str(details["version_id"]))
        async with factory() as session:
            await session.execute(
                text("delete from public.chunks where version_id = :version_id"),
                {"version_id": version_id},
            )
            statement = text(
                """
                insert into public.chunks (
                  document_id, version_id, user_id, chunk_index, content,
                  page_start, page_end, section_path, token_count, content_hash,
                  embedding, metadata
                ) values (
                  :document_id, :version_id, :user_id, :chunk_index, :content,
                  :page_start, :page_end, :section_path, :token_count, :content_hash,
                  cast(:embedding as extensions.vector), cast(:metadata as jsonb)
                )
                """
            )
            rows = [
                {
                    "document_id": details["document_id"],
                    "version_id": version_id,
                    "user_id": details["user_id"],
                    "chunk_index": chunk.index,
                    "content": chunk.content,
                    "page_start": chunk.page_start,
                    "page_end": chunk.page_end,
                    "section_path": chunk.section_path,
                    "token_count": chunk.token_count,
                    "content_hash": chunk.content_hash,
                    "embedding": vector_literal(vector),
                    "metadata": json.dumps({}),
                }
                for chunk, vector in zip(chunks, vectors, strict=True)
            ]
            await session.execute(statement, rows)
            await session.execute(
                text(
                    """
                    update public.document_versions
                    set status = 'published', embedding_model = :embedding_model,
                        embedding_dimensions = :dimensions, chunk_count = :chunk_count,
                        character_count = :character_count, page_count = :page_count,
                        metadata = cast(:metadata as jsonb), published_at = now()
                    where id = :version_id
                    """
                ),
                {
                    "embedding_model": self.settings.gemini_embedding_model,
                    "dimensions": self.settings.embedding_dimensions,
                    "chunk_count": len(chunks),
                    "character_count": character_count,
                    "page_count": page_count,
                    "metadata": json.dumps(parser_metadata),
                    "version_id": version_id,
                },
            )
            published = await session.execute(
                text(
                    """
                    update public.documents
                    set active_version_id = :version_id, status = 'ready',
                        checksum_sha256 = :checksum, error_code = null, error_message = null,
                        upload_token_hash = null, upload_token_expires_at = null
                    where id = :document_id and user_id = :user_id and status = 'processing'
                    returning id
                    """
                ),
                {
                    "version_id": version_id,
                    "checksum": checksum,
                    "document_id": details["document_id"],
                    "user_id": details["user_id"],
                },
            )
            if published.scalar_one_or_none() is None:
                raise AppError("job_cancelled", "Document processing was cancelled.", status_code=409)
            await session.execute(
                text(
                    """
                    update public.ingestion_jobs
                    set status = 'succeeded', stage = 'complete', progress = 100,
                        heartbeat_at = now(), completed_at = now(), locked_at = null, locked_by = null
                    where id = :job_id
                    """
                ),
                {"job_id": job_id},
            )
            await session.execute(
                text(
                    """
                    insert into public.audit_events (user_id, action, target_type, target_id, metadata)
                    values (:user_id, 'document.indexed', 'document', :document_id, cast(:metadata as jsonb))
                    """
                ),
                {
                    "user_id": details["user_id"],
                    "document_id": details["document_id"],
                    "metadata": json.dumps(
                        {"chunk_count": len(chunks), "version_id": str(version_id)}
                    ),
                },
            )
            await session.commit()

    async def _fail_or_retry(
        self,
        job: dict[str, Any],
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        attempts = int(job["attempt_count"])
        max_attempts = int(job["max_attempts"])
        should_retry = retryable and attempts < max_attempts
        delay_seconds = min(300, 15 * (2 ** max(0, attempts - 1)))
        factory = get_session_factory()
        if factory is None:
            return
        async with factory() as session:
            await session.execute(
                text(
                    """
                    update public.ingestion_jobs
                    set status = cast(:status as public.job_status),
                        stage = :stage,
                        available_at = case
                          when :retry then now() + (:delay * interval '1 second')
                          else available_at
                        end,
                        error_code = :code, error_message = :message,
                        locked_at = null, locked_by = null,
                        completed_at = case when :retry then null else now() end
                    where id = :job_id
                    """
                ),
                {
                    "status": "retrying" if should_retry else "failed",
                    "stage": "queued" if should_retry else "failed",
                    "retry": should_retry,
                    "delay": delay_seconds,
                    "code": code,
                    "message": message[:1000],
                    "job_id": job["id"],
                },
            )
            if not should_retry:
                await session.execute(
                    text(
                        """
                        update public.documents
                        set status = case
                              when active_version_id is null then 'failed'::public.document_status
                              else 'ready'::public.document_status
                            end,
                            error_code = :code, error_message = :message
                        where id = :document_id and user_id = :user_id and status <> 'deleting'
                        """
                    ),
                    {
                        "code": code,
                        "message": message[:1000],
                        "document_id": job["document_id"],
                        "user_id": job["user_id"],
                    },
                )
                await session.execute(
                    text("update public.document_versions set status = 'failed' where id = :version_id"),
                    {"version_id": job["version_id"]},
                )
            await session.commit()
        logger.warning(
            "ingestion_failed",
            job_id=str(job["id"]),
            error_code=code,
            retrying=should_retry,
        )
