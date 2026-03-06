"""Text cleaning and chunking helpers."""

from __future__ import annotations

import re


_WHITESPACE_RE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Normalize whitespace and trim document text."""
    if not text:
        return ""
    normalized = _WHITESPACE_RE.sub(" ", text)
    return normalized.strip()


def _split_at_whitespace(segment: str, max_len: int) -> str:
    if len(segment) <= max_len:
        return segment

    split_at = segment.rfind(" ", 0, max_len)
    if split_at <= 0:
        return segment[:max_len]
    return segment[:split_at]


def chunk_text(text: str, chunk_size: int = 900, overlap: int = 120) -> list[str]:
    """Split text into overlapping chunks while preserving readability."""
    cleaned = clean_text(text)
    if not cleaned:
        return []

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")

    chunks: list[str] = []
    step = chunk_size - overlap
    start = 0

    while start < len(cleaned):
        window = cleaned[start : start + chunk_size]
        piece = _split_at_whitespace(window, chunk_size).strip()
        if piece:
            chunks.append(piece)

        if start + chunk_size >= len(cleaned):
            break
        start += step

    return chunks
