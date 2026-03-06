"""Load curated legal documents and metadata from a directory."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .manifest import ManifestMetadata, read_manifest


SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown"}


@dataclass(frozen=True)
class LoadedDocument:
    file_path: Path
    manifest_path: Path
    text: str
    manifest: ManifestMetadata


def _manifest_for_file(file_path: Path) -> Path:
    return file_path.with_name(f"{file_path.stem}.manifest.json")


def load_documents(root_path: str | Path) -> list[LoadedDocument]:
    base = Path(root_path)
    if not base.exists() or not base.is_dir():
        raise FileNotFoundError(f"Pasta de ingestão inválida: {base}")

    loaded: list[LoadedDocument] = []

    for file_path in sorted(base.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue

        manifest_path = _manifest_for_file(file_path)
        manifest = read_manifest(manifest_path)
        text = file_path.read_text(encoding="utf-8")

        loaded.append(
            LoadedDocument(
                file_path=file_path,
                manifest_path=manifest_path,
                text=text,
                manifest=manifest,
            )
        )

    return loaded
