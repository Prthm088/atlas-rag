import hashlib
import math
import re
from dataclasses import dataclass

from atlas.services.parsers import ParsedDocument, SourceBlock


@dataclass(slots=True)
class ChunkDraft:
    index: int
    content: str
    content_hash: str
    token_count: int
    page_start: int | None
    page_end: int | None
    section_path: list[str]


def approximate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _split_oversized(text: str, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    sentences = re.split(r"(?<=[.!?])\s+", text)
    pieces: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_chars:
            if current:
                pieces.append(current.strip())
                current = ""
            start = 0
            while start < len(sentence):
                end = min(len(sentence), start + max_chars)
                pieces.append(sentence[start:end].strip())
                if end == len(sentence):
                    break
                start = max(start + 1, end - overlap_chars)
            continue
        candidate = f"{current} {sentence}".strip()
        if current and len(candidate) > max_chars:
            pieces.append(current.strip())
            prefix = current[-overlap_chars:].strip()
            current = f"{prefix} {sentence}".strip()
        else:
            current = candidate
    if current:
        pieces.append(current.strip())
    return [piece for piece in pieces if piece]


def _block_parts(block: SourceBlock, max_chars: int, overlap_chars: int) -> list[SourceBlock]:
    return [
        SourceBlock(text=part, page=block.page, section_path=block.section_path)
        for part in _split_oversized(block.text, max_chars, overlap_chars)
    ]


def chunk_document(
    document: ParsedDocument,
    *,
    max_tokens: int = 780,
    overlap_tokens: int = 90,
) -> list[ChunkDraft]:
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    expanded = [
        part
        for block in document.blocks
        for part in _block_parts(block, max_chars=max_chars, overlap_chars=overlap_chars)
    ]
    drafts: list[ChunkDraft] = []
    buffer: list[SourceBlock] = []
    buffer_length = 0

    def flush() -> None:
        nonlocal buffer_length
        if not buffer:
            return
        content = "\n\n".join(item.text.strip() for item in buffer if item.text.strip()).strip()
        if not content:
            buffer.clear()
            buffer_length = 0
            return
        pages = [item.page for item in buffer if item.page is not None]
        section = max((item.section_path for item in buffer), key=len, default=[])
        digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if not drafts or drafts[-1].content_hash != digest:
            drafts.append(
                ChunkDraft(
                    index=len(drafts),
                    content=content,
                    content_hash=digest,
                    token_count=approximate_tokens(content),
                    page_start=min(pages) if pages else None,
                    page_end=max(pages) if pages else None,
                    section_path=list(section),
                )
            )
        carry_text = content[-overlap_chars:].strip()
        carry = SourceBlock(
            text=carry_text,
            page=buffer[-1].page,
            section_path=buffer[-1].section_path,
        ) if carry_text else None
        buffer.clear()
        if carry is not None:
            buffer.append(carry)
            buffer_length = len(carry.text)
        else:
            buffer_length = 0

    for block in expanded:
        added = len(block.text) + (2 if buffer else 0)
        section_changed = bool(buffer and block.section_path != buffer[-1].section_path)
        if buffer and (buffer_length + added > max_chars or section_changed):
            flush()
        buffer.append(block)
        buffer_length += added
    flush()
    return drafts
