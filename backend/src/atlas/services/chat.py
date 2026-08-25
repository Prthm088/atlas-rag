import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID, uuid4

import structlog
from sqlalchemy import text

from atlas.config import Settings
from atlas.database import get_session_factory
from atlas.errors import AppError
from atlas.services.gemini import GeminiProvider, GenerationUsage
from atlas.services.memory import load_conversation_context, maybe_update_summary
from atlas.services.retrieval import (
    GROUNDED_SYSTEM_INSTRUCTION,
    Evidence,
    HybridRetriever,
    build_grounded_prompt,
)

logger = structlog.get_logger("chat")
CITATION_GROUP_PATTERN = re.compile(r"\[(C\d+(?:\s*,\s*C\d+)*)\]")
CITATION_LABEL_PATTERN = re.compile(r"C(\d+)")


def sse_event(event: str, data: dict[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def prepare_chat(
    *,
    conversation_id: UUID,
    user_id: UUID,
    content: str,
) -> tuple[UUID, UUID]:
    factory = get_session_factory()
    if factory is None:
        raise AppError("database_unavailable", "The database is unavailable.", status_code=503)
    user_message_id, assistant_message_id = uuid4(), uuid4()
    async with factory() as session:
        conversation = await session.execute(
            text("select title from public.conversations where id = :id and user_id = :user_id for update"),
            {"id": conversation_id, "user_id": user_id},
        )
        row = conversation.first()
        if row is None:
            raise AppError("conversation_not_found", "The conversation does not exist.", status_code=404)
        await session.execute(
            text(
                """
                insert into public.messages (id, conversation_id, user_id, role, status, content, completed_at)
                values (:user_id_message, :conversation_id, :user_id, 'user', 'completed', :content, now()),
                       (:assistant_id, :conversation_id, :user_id, 'assistant', 'pending', '', null)
                """
            ),
            {
                "user_id_message": user_message_id,
                "assistant_id": assistant_message_id,
                "conversation_id": conversation_id,
                "user_id": user_id,
                "content": content,
            },
        )
        if str(row[0]) == "New conversation":
            title = content.strip().replace("\n", " ")[:72]
            await session.execute(
                text("update public.conversations set title = :title where id = :id"),
                {"title": title or "New conversation", "id": conversation_id},
            )
        await session.execute(
            text("update public.conversations set updated_at = now() where id = :id"),
            {"id": conversation_id},
        )
        await session.commit()
    return user_message_id, assistant_message_id


def _validate_citations(content: str, evidence: list[Evidence]) -> tuple[str, list[tuple[int, Evidence]]]:
    valid: list[tuple[int, Evidence]] = []
    seen: set[int] = set()

    def replace(match: re.Match[str]) -> str:
        markers: list[str] = []
        for raw_index in CITATION_LABEL_PATTERN.findall(match.group(1)):
            index = int(raw_index)
            if index < 1 or index > len(evidence):
                markers.append("[citation unavailable]")
                continue
            if index not in seen:
                seen.add(index)
                valid.append((index, evidence[index - 1]))
            markers.append(f"[C{index}]")
        return " ".join(markers)

    canonical = CITATION_GROUP_PATTERN.sub(replace, content)
    valid.sort(key=lambda item: item[0])
    return canonical, valid


async def _persist_completed_answer(
    *,
    settings: Settings,
    conversation_id: UUID,
    user_id: UUID,
    assistant_message_id: UUID,
    content: str,
    evidence: list[Evidence],
    usage: GenerationUsage,
    latency_ms: int,
) -> list[dict[str, object]]:
    canonical, used = _validate_citations(content, evidence)
    factory = get_session_factory()
    if factory is None:
        raise AppError("database_unavailable", "The database is unavailable.", status_code=503)
    citation_events: list[dict[str, object]] = []
    async with factory() as session:
        await session.execute(
            text(
                """
                update public.messages
                set status = 'completed', content = :content, model = :model,
                    input_tokens = :input_tokens, output_tokens = :output_tokens,
                    latency_ms = :latency_ms, completed_at = now()
                where id = :message_id and user_id = :user_id
                """
            ),
            {
                "content": canonical,
                "model": settings.gemini_chat_model,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "latency_ms": latency_ms,
                "message_id": assistant_message_id,
                "user_id": user_id,
            },
        )
        for rank, (label, item) in enumerate(used):
            citation_id = uuid4()
            quote = item.content[:1000]
            await session.execute(
                text(
                    """
                    insert into public.citations (
                      id, message_id, user_id, document_id, version_id, chunk_id,
                      label, rank, document_name, page_start, page_end, section_path, quote
                    ) values (
                      :id, :message_id, :user_id, :document_id, :version_id, :chunk_id,
                      :label, :rank, :document_name, :page_start, :page_end, :section_path, :quote
                    )
                    """
                ),
                {
                    "id": citation_id,
                    "message_id": assistant_message_id,
                    "user_id": user_id,
                    "document_id": item.document_id,
                    "version_id": item.version_id,
                    "chunk_id": item.chunk_id,
                    "label": label,
                    "rank": rank,
                    "document_name": item.document_name,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "section_path": item.section_path,
                    "quote": quote,
                },
            )
            citation_events.append(
                {
                    "id": str(citation_id),
                    "label": label,
                    "document_id": str(item.document_id),
                    "document_name": item.document_name,
                    "page_start": item.page_start,
                    "page_end": item.page_end,
                    "section_path": item.section_path,
                    "quote": quote,
                }
            )
        await session.execute(
            text("update public.conversations set updated_at = now() where id = :id and user_id = :user_id"),
            {"id": conversation_id, "user_id": user_id},
        )
        await session.commit()
        try:
            await maybe_update_summary(
                session,
                settings=settings,
                provider=GeminiProvider(settings),
                conversation_id=conversation_id,
                user_id=user_id,
            )
        except AppError:
            logger.warning("conversation_summary_skipped", conversation_id=str(conversation_id))
    return citation_events


async def _persist_failed_answer(message_id: UUID, user_id: UUID, code: str, message: str) -> None:
    factory = get_session_factory()
    if factory is None:
        return
    async with factory() as session:
        await session.execute(
            text(
                """
                update public.messages
                set status = 'failed', error_code = :code, error_message = :message, completed_at = now()
                where id = :id and user_id = :user_id
                """
            ),
            {"code": code, "message": message[:1000], "id": message_id, "user_id": user_id},
        )
        await session.commit()


async def stream_chat(
    *,
    settings: Settings,
    conversation_id: UUID,
    user_id: UUID,
    question: str,
    user_message_id: UUID,
    assistant_message_id: UUID,
    request_id: str,
    is_disconnected: Callable[[], Awaitable[bool]],
) -> AsyncIterator[str]:
    yield sse_event(
        "meta",
        {
            "conversation_id": str(conversation_id),
            "user_message_id": str(user_message_id),
            "assistant_message_id": str(assistant_message_id),
        },
    )
    started = time.perf_counter()
    provider = GeminiProvider(settings)
    factory = get_session_factory()
    if factory is None:
        yield sse_event("error", {"code": "database_unavailable", "message": "The database is unavailable."})
        return
    try:
        async with factory() as session:
            summary, recent = await load_conversation_context(
                session,
                conversation_id=conversation_id,
                user_id=user_id,
                recent_limit=settings.conversation_recent_messages,
            )
            if recent and recent[-1] == ("user", question):
                recent = recent[:-1]
            query_embedding = await provider.embed_query(question)
            evidence = await HybridRetriever(settings).retrieve(
                session,
                user_id=user_id,
                query=question,
                query_embedding=query_embedding,
            )
        usage = GenerationUsage()
        if not evidence:
            answer = (
                "I couldn’t find enough evidence in your ready documents to answer that. "
                "Try uploading a relevant source or asking with more specific terms."
            )
            yield sse_event("token", {"text": answer})
        else:
            prompt = build_grounded_prompt(
                question=question,
                evidence=evidence,
                conversation_summary=summary,
                recent_messages=recent,
            )
            parts: list[str] = []
            async for chunk in provider.stream_answer(
                prompt=prompt,
                system_instruction=GROUNDED_SYSTEM_INSTRUCTION,
            ):
                if await is_disconnected():
                    await _persist_failed_answer(
                        assistant_message_id, user_id, "client_disconnected", "The response was cancelled."
                    )
                    return
                if chunk.usage:
                    usage = chunk.usage
                if chunk.text:
                    parts.append(chunk.text)
                    yield sse_event("token", {"text": chunk.text})
            answer = "".join(parts).strip()
            if not answer:
                raise AppError("empty_generation", "The answer service returned an empty response.", status_code=503)
        latency_ms = round((time.perf_counter() - started) * 1000)
        citation_events = await _persist_completed_answer(
            settings=settings,
            conversation_id=conversation_id,
            user_id=user_id,
            assistant_message_id=assistant_message_id,
            content=answer,
            evidence=evidence,
            usage=usage,
            latency_ms=latency_ms,
        )
        for citation in citation_events:
            yield sse_event("citation", citation)
        canonical, _ = _validate_citations(answer, evidence)
        yield sse_event(
            "done",
            {
                "message_id": str(assistant_message_id),
                "content": canonical,
                "latency_ms": latency_ms,
            },
        )
    except AppError as exc:
        await _persist_failed_answer(assistant_message_id, user_id, exc.code, exc.message)
        yield sse_event(
            "error",
            {"code": exc.code, "message": exc.message, "request_id": request_id},
        )
    except Exception:
        logger.exception("chat_stream_failed", request_id=request_id)
        await _persist_failed_answer(
            assistant_message_id,
            user_id,
            "chat_internal_error",
            "The answer could not be completed.",
        )
        yield sse_event(
            "error",
            {
                "code": "chat_internal_error",
                "message": "The answer could not be completed.",
                "request_id": request_id,
            },
        )
