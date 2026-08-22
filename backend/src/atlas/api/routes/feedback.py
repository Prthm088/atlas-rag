from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from atlas.auth import CurrentUser
from atlas.database import get_db
from atlas.errors import AppError
from atlas.schemas import FeedbackRequest, FeedbackResponse

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackResponse, status_code=status.HTTP_201_CREATED)
async def save_feedback(
    payload: FeedbackRequest,
    user: CurrentUser,
    session: AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    result = await session.execute(
        text(
            """
            insert into public.feedback (user_id, message_id, rating, comment)
            select :user_id, m.id, :rating, :comment
            from public.messages m
            where m.id = :message_id and m.user_id = :user_id and m.role = 'assistant'
            on conflict (user_id, message_id) do update
              set rating = excluded.rating, comment = excluded.comment
            returning id, message_id, rating, comment, created_at
            """
        ),
        {
            "user_id": user.id,
            "message_id": payload.message_id,
            "rating": payload.rating,
            "comment": payload.comment,
        },
    )
    row = result.mappings().first()
    if row is None:
        raise AppError("message_not_found", "The answer does not exist.", status_code=404)
    await session.commit()
    return FeedbackResponse(**dict(row))
