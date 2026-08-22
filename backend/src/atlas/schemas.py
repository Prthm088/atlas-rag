from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HealthResponse(APIModel):
    status: Literal["ok", "degraded"]
    service: str
    version: str
    missing_configuration: list[str] = []


class ProfileResponse(APIModel):
    id: UUID
    email: str | None
    display_name: str | None = None
    document_count: int = 0
    storage_bytes: int = 0
    max_documents: int
    max_storage_bytes: int


class UploadIntentRequest(APIModel):
    filename: str = Field(min_length=1, max_length=240)
    mime_type: str = Field(min_length=1, max_length=120)
    size_bytes: int = Field(gt=0)


class UploadIntentResponse(APIModel):
    document_id: UUID
    version_id: UUID
    storage_bucket: str
    storage_path: str
    upload_token: str


class UploadCompleteRequest(APIModel):
    upload_token: str = Field(min_length=20, max_length=200)


class DocumentResponse(APIModel):
    id: UUID
    name: str
    mime_type: str
    size_bytes: int
    status: str
    error_code: str | None = None
    error_message: str | None = None
    chunk_count: int = 0
    job_stage: str | None = None
    job_progress: int | None = None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(APIModel):
    items: list[DocumentResponse]
    total: int


class JobResponse(APIModel):
    id: UUID
    document_id: UUID
    status: str
    stage: str
    progress: int
    attempt_count: int
    error_code: str | None = None
    error_message: str | None = None
    updated_at: datetime


class SignedUrlResponse(APIModel):
    url: str
    expires_in: int


class ConversationCreateRequest(APIModel):
    title: str | None = Field(default=None, max_length=120)


class ConversationUpdateRequest(APIModel):
    title: str = Field(min_length=1, max_length=120)


class ConversationResponse(APIModel):
    id: UUID
    title: str
    summary: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationListResponse(APIModel):
    items: list[ConversationResponse]
    total: int


class CitationResponse(APIModel):
    id: UUID
    label: int
    document_id: UUID
    document_name: str
    page_start: int | None = None
    page_end: int | None = None
    section_path: list[str] = []
    quote: str


class MessageResponse(APIModel):
    id: UUID
    conversation_id: UUID
    role: Literal["user", "assistant"]
    status: str
    content: str
    created_at: datetime
    citations: list[CitationResponse] = []


class MessageListResponse(APIModel):
    items: list[MessageResponse]
    total: int


class ChatRequest(APIModel):
    conversation_id: UUID
    content: str = Field(min_length=1, max_length=8000)


class FeedbackRequest(APIModel):
    message_id: UUID
    rating: Literal[-1, 1]
    comment: str | None = Field(default=None, max_length=1000)


class FeedbackResponse(APIModel):
    id: UUID
    message_id: UUID
    rating: int
    comment: str | None
    created_at: datetime


class DeleteAccountRequest(APIModel):
    confirmation: Literal["DELETE MY ACCOUNT"]


class PageResult(APIModel):
    items: list[Any]
    total: int
