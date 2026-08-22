from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.config import Settings
from atlas.services.gemini import GeminiProvider

SUMMARY_SYSTEM = """
Summarize the conversation for future context. Preserve the user's goals, constraints, definitions,
decisions, and unresolved questions. Do not add facts. Do not copy citations. Return plain text only.
""".strip()


async def load_conversation_context(
    session: AsyncSession,
    *,
    conversation_id: UUID,
    user_id: UUID,
    recent_limit: int,
) -> tuple[str | None, list[tuple[str, str]]]:
    conversation = await session.execute(
        text("select summary from public.conversations where id = :id and user_id = :user_id"),
        {"id": conversation_id, "user_id": user_id},
    )
    summary = conversation.scalar_one_or_none()
    rows = await session.execute(
        text(
            """
            select role::text, content
            from public.messages
            where conversation_id = :conversation_id
              and user_id = :user_id
              and status = 'completed'
            order by created_at desc
            limit :message_limit
            """
        ),
        {
            "conversation_id": conversation_id,
            "user_id": user_id,
            "message_limit": recent_limit,
        },
    )
    messages = [(str(row[0]), str(row[1])) for row in reversed(rows.all())]
    return summary, messages


async def maybe_update_summary(
    session: AsyncSession,
    *,
    settings: Settings,
    provider: GeminiProvider,
    conversation_id: UUID,
    user_id: UUID,
) -> None:
    state = await session.execute(
        text(
            """
            select c.summary_message_count, count(m.id)::int as message_count
            from public.conversations c
            left join public.messages m
              on m.conversation_id = c.id and m.status = 'completed'
            where c.id = :conversation_id and c.user_id = :user_id
            group by c.id
            """
        ),
        {"conversation_id": conversation_id, "user_id": user_id},
    )
    row = state.first()
    if row is None:
        return
    summarized, total = int(row[0]), int(row[1])
    if total < settings.conversation_summary_trigger or total - summarized < 6:
        return
    messages = await session.execute(
        text(
            """
            select role::text, content
            from public.messages
            where conversation_id = :conversation_id
              and user_id = :user_id
              and status = 'completed'
            order by created_at asc
            """
        ),
        {"conversation_id": conversation_id, "user_id": user_id},
    )
    transcript = "\n".join(f"{row[0].upper()}: {row[1]}" for row in messages)
    summary = await provider.generate_text(
        prompt=transcript[:48000],
        system_instruction=SUMMARY_SYSTEM,
        max_output_tokens=700,
        temperature=0.0,
    )
    await session.execute(
        text(
            """
            update public.conversations
            set summary = :summary, summary_message_count = :message_count
            where id = :conversation_id and user_id = :user_id
            """
        ),
        {
            "summary": summary,
            "message_count": total,
            "conversation_id": conversation_id,
            "user_id": user_id,
        },
    )
    await session.commit()
