"""Citation parser for model outputs."""

from __future__ import annotations

import re
from dataclasses import dataclass


_CITATION_RE = re.compile(r"\[fonte\s*:\s*(\d+)\]", re.IGNORECASE)


@dataclass(frozen=True)
class Citation:
    index: int


def extract_citations(answer: str) -> list[Citation]:
    """Extract citation tags in the format [fonte:N] from an answer."""
    matches = _CITATION_RE.findall(answer or "")
    deduped = sorted({int(value) for value in matches})
    return [Citation(index=value) for value in deduped]
