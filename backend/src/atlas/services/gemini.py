import asyncio
from collections.abc import AsyncIterator
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Literal

from google import genai
from google.genai import types

from atlas.config import Settings
from atlas.errors import AppError


@dataclass(slots=True)
class GenerationUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(slots=True)
class GenerationChunk:
    text: str
    usage: GenerationUsage | None = None


class GeminiProvider:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    @cached_property
    def client(self) -> genai.Client:
        if not self.settings.gemini_api_key:
            raise AppError("ai_not_configured", "The AI provider has not been configured.", status_code=503)
        return genai.Client(api_key=self.settings.gemini_api_key)

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return await self._embed(texts, "RETRIEVAL_DOCUMENT")

    async def embed_query(self, text: str) -> list[float]:
        rows = await self._embed([text], "RETRIEVAL_QUERY")
        return rows[0]

    async def _embed(
        self,
        texts: list[str],
        task_type: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"],
    ) -> list[list[float]]:
        if not texts:
            return []

        def call() -> list[list[float]]:
            response = self.client.models.embed_content(
                model=self.settings.gemini_embedding_model,
                contents=texts,
                config=types.EmbedContentConfig(
                    task_type=task_type,
                    output_dimensionality=self.settings.embedding_dimensions,
                ),
            )
            embeddings = response.embeddings or []
            values = [list(item.values or []) for item in embeddings]
            if len(values) != len(texts) or any(
                len(vector) != self.settings.embedding_dimensions for vector in values
            ):
                raise RuntimeError("Embedding provider returned an unexpected shape")
            return values

        try:
            return await asyncio.to_thread(call)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "embedding_provider_error",
                "The document could not be embedded because the AI provider is unavailable.",
                status_code=503,
            ) from exc

    async def generate_text(
        self,
        *,
        prompt: str,
        system_instruction: str,
        max_output_tokens: int = 1200,
        temperature: float = 0.1,
    ) -> str:
        def call() -> str:
            response = self.client.models.generate_content(
                model=self.settings.gemini_chat_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                ),
            )
            return (response.text or "").strip()

        try:
            result = await asyncio.to_thread(call)
        except AppError:
            raise
        except Exception as exc:
            raise AppError(
                "generation_provider_error",
                "The answer service is temporarily unavailable.",
                status_code=503,
            ) from exc
        if not result:
            raise AppError("empty_generation", "The answer service returned an empty response.", status_code=503)
        return result

    async def stream_answer(
        self,
        *,
        prompt: str,
        system_instruction: str,
        max_output_tokens: int = 1800,
    ) -> AsyncIterator[GenerationChunk]:
        queue: asyncio.Queue[tuple[str, Any]] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def publish(kind: str, value: Any) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, (kind, value))

        def produce() -> None:
            try:
                usage = GenerationUsage()
                response = self.client.models.generate_content_stream(
                    model=self.settings.gemini_chat_model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=system_instruction,
                        temperature=0.1,
                        max_output_tokens=max_output_tokens,
                    ),
                )
                for chunk in response:
                    metadata = getattr(chunk, "usage_metadata", None)
                    if metadata:
                        usage.input_tokens = getattr(metadata, "prompt_token_count", None)
                        usage.output_tokens = getattr(metadata, "candidates_token_count", None)
                    if chunk.text:
                        publish("chunk", GenerationChunk(text=chunk.text))
                publish("usage", usage)
            except Exception as exc:  # the exception is safely mapped on the async side
                publish("error", exc)
            finally:
                publish("done", None)

        producer = asyncio.create_task(asyncio.to_thread(produce))
        try:
            while True:
                kind, value = await queue.get()
                if kind == "chunk":
                    yield value
                elif kind == "usage":
                    yield GenerationChunk(text="", usage=value)
                elif kind == "error":
                    raise AppError(
                        "generation_provider_error",
                        "The answer service is temporarily unavailable.",
                        status_code=503,
                    ) from value
                elif kind == "done":
                    break
        finally:
            await asyncio.gather(producer, return_exceptions=True)
