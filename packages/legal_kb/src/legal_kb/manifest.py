"""Manifest parsing for curated legal documents."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field, HttpUrl


class ManifestMetadata(BaseModel):
    title: str = Field(min_length=3, max_length=320)
    authority: str = Field(min_length=2, max_length=120)
    source_url: HttpUrl
    source_type: str = Field(min_length=2, max_length=64)
    legal_ref: str = Field(min_length=2, max_length=180)
    effective_date: date | None = None


def read_manifest(path: Path) -> ManifestMetadata:
    if not path.exists():
        raise FileNotFoundError(f"Manifest não encontrado: {path}")

    data = json.loads(path.read_text(encoding="utf-8"))
    return ManifestMetadata.model_validate(data)
