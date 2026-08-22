from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from atlas.auth import CurrentUser
from atlas.config import get_settings
from atlas.schemas import ChatRequest
from atlas.services.chat import prepare_chat, stream_chat
from atlas.services.rate_limit import rate_limiter

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(payload: ChatRequest, request: Request, user: CurrentUser) -> StreamingResponse:
    settings = get_settings()
    content = payload.content.strip()
    await rate_limiter.enforce(
        f"chat:{user.id}", limit=settings.chat_requests_per_minute, window_seconds=60
    )
    user_message_id, assistant_message_id = await prepare_chat(
        conversation_id=payload.conversation_id,
        user_id=user.id,
        content=content,
    )
    request_id = getattr(request.state, "request_id", "unknown")
    return StreamingResponse(
        stream_chat(
            settings=settings,
            conversation_id=payload.conversation_id,
            user_id=user.id,
            question=content,
            user_message_id=user_message_id,
            assistant_message_id=assistant_message_id,
            request_id=request_id,
            is_disconnected=request.is_disconnected,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
