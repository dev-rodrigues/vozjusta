"""Legal knowledge base package for VozJusta."""

from .ingestion import IngestionSummary, run_ingestion
from .loader import load_documents
from .manifest import ManifestMetadata, read_manifest

__all__ = [
    "IngestionSummary",
    "ManifestMetadata",
    "load_documents",
    "read_manifest",
    "run_ingestion",
]
