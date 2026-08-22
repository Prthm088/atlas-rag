from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.auth import CurrentUser
from atlas.database import get_db
from atlas.errors import AppError
from atlas.schemas import (
    CitationResponse,
    ConversationCreateRequest,
    ConversationListResponse,
    ConversationResponse,
    ConversationUpdateRequest,
    MessageListResponse,
    MessageResponse,
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=ConversationListResponse)
async def list_conversations(
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ConversationListResponse:
    result = await session.execute(
        text(
            """
            select c.id, c.title, c.summary, c.created_at, c.updated_at,
                   count(m.id)::int as message_count
            from public.conversations c
            left join public.messages m on m.conversation_id = c.id
            where c.user_id = :user_id
            group by c.id
            order by c.updated_at desc
            """
        ),
        {"user_id": user.id},
    )
    items = [ConversationResponse(**dict(row._mapping)) for row in result]
    return ConversationListResponse(items=items, total=len(items))


@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    payload: ConversationCreateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    title = (payload.title or "New conversation").strip() or "New conversation"
    result = await session.execute(
        text(
            """
            insert into public.conversations (user_id, title)
            values (:user_id, :title)
            returning id, title, summary, created_at, updated_at, 0::int as message_count
            """
        ),
        {"user_id": user.id, "title": title},
    )
    await session.commit()
    return ConversationResponse(**dict(result.mappings().one()))


@router.patch("/{conversation_id}", response_model=ConversationResponse)
async def update_conversation(
    conversation_id: UUID,
    payload: ConversationUpdateRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> ConversationResponse:
    result = await session.execute(
        text(
            """
            update public.conversations set title = :title
            where id = :id and user_id = :user_id
            returning id, title, summary, created_at, updated_at,
              (select count(*)::int from public.messages where conversation_id = :id) as message_count
            """
        ),
        {"title": payload.title.strip(), "id": conversation_id, "user_id": user.id},
    )
    row = result.mappings().first()
    if row is None:
        raise AppError("conversation_not_found", "The conversation does not exist.", status_code=404)
    await session.commit()
    return ConversationResponse(**dict(row))


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> Response:
    result = await session.execute(
        text("delete from public.conversations where id = :id and user_id = :user_id returning id"),
        {"id": conversation_id, "user_id": user.id},
    )
    if result.scalar_one_or_none() is None:
        raise AppError("conversation_not_found", "The conversation does not exist.", status_code=404)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{conversation_id}/messages", response_model=MessageListResponse)
async def list_messages(
    conversation_id: UUID,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> MessageListResponse:
    exists = await session.execute(
        text("select 1 from public.conversations where id = :id and user_id = :user_id"),
        {"id": conversation_id, "user_id": user.id},
    )
    if exists.first() is None:
        raise AppError("conversation_not_found", "The conversation does not exist.", status_code=404)
    message_rows = await session.execute(
        text(
            """
            select id, conversation_id, role::text, status::text, content, created_at
            from public.messages
            where conversation_id = :conversation_id and user_id = :user_id
            order by created_at asc
            limit 300
            """
        ),
        {"conversation_id": conversation_id, "user_id": user.id},
    )
    citation_rows = await session.execute(
        text(
            """
            select c.id, c.message_id, c.label, c.document_id, c.document_name,
                   c.page_start, c.page_end, c.section_path, c.quote
            from public.citations c
            join public.messages m on m.id = c.message_id
            where m.conversation_id = :conversation_id and c.user_id = :user_id
            order by c.message_id, c.label
            """
        ),
        {"conversation_id": conversation_id, "user_id": user.id},
    )
    citations: dict[UUID, list[CitationResponse]] = defaultdict(list)
    for row in citation_rows.mappings():
        message_id = row["message_id"]
        data = dict(row)
        data.pop("message_id")
        citations[message_id].append(CitationResponse(**data))
    items = []
    for row in message_rows.mappings():
        data = dict(row)
        data["citations"] = citations.get(row["id"], [])
        items.append(MessageResponse(**data))
    return MessageListResponse(items=items, total=len(items))
