import json
from typing import Any, cast
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

import atlas.services.jobs as jobs_module
from atlas.config import Settings
from atlas.services.chunking import ChunkDraft
from atlas.services.jobs import JobRunner


@pytest.mark.asyncio
async def test_publish_checks_the_document_update_result(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    document_id = uuid4()
    version_id = uuid4()
    job_id = uuid4()
    session = AsyncMock()
    no_rows = MagicMock()
    document_update = MagicMock()
    document_update.scalar_one_or_none.return_value = document_id
    session.execute.side_effect = [
        no_rows,
        no_rows,
        no_rows,
        document_update,
        no_rows,
        no_rows,
    ]
    context = AsyncMock()
    context.__aenter__.return_value = session
    factory = MagicMock(return_value=context)
    monkeypatch.setattr(jobs_module, "get_session_factory", lambda: factory)

    runner = JobRunner(
        Settings(
            supabase_url="https://project.supabase.co",
            supabase_service_role_key="service-role-key",
            gemini_api_key="gemini-key",
        )
    )
    details: dict[str, Any] = {
        "document_id": document_id,
        "version_id": version_id,
        "user_id": user_id,
    }
    chunk = ChunkDraft(
        index=0,
        content="Grounded source text.",
        content_hash="hash",
        token_count=4,
        page_start=None,
        page_end=None,
        section_path=[],
    )

    await runner._publish(
        job_id=job_id,
        details=details,
        checksum="checksum",
        chunks=[chunk],
        vectors=[[0.0] * 768],
        character_count=len(chunk.content),
        page_count=None,
        parser_metadata={"format": "markdown"},
    )

    document_update.scalar_one_or_none.assert_called_once_with()
    no_rows.scalar_one_or_none.assert_not_called()
    audit_call = session.execute.await_args_list[5]
    assert "cast(:metadata as jsonb)" in str(audit_call.args[0])
    audit_parameters = cast(dict[str, Any], audit_call.args[1])
    assert json.loads(audit_parameters["metadata"]) == {
        "chunk_count": 1,
        "version_id": str(version_id),
    }
    session.commit.assert_awaited_once_with()
