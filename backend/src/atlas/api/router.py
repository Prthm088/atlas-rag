from fastapi import APIRouter

from atlas.api.routes import account, chat, conversations, documents, feedback, health

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(account.router)
api_router.include_router(documents.router)
api_router.include_router(conversations.router)
api_router.include_router(chat.router)
api_router.include_router(feedback.router)
