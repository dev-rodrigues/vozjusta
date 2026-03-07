from pathlib import Path

from legal_kb.loader import load_documents
from legal_kb.manifest import read_manifest


def test_read_manifest(tmp_path: Path) -> None:
    manifest_path = tmp_path / "doc.manifest.json"
    manifest_path.write_text(
        """
        {
          "title": "Lei Teste",
          "authority": "Planalto",
          "source_url": "https://www.planalto.gov.br/",
          "source_type": "lei",
          "legal_ref": "Lei X",
          "effective_date": "2023-01-01"
        }
        """,
        encoding="utf-8",
    )

    manifest = read_manifest(manifest_path)
    assert manifest.title == "Lei Teste"
    assert str(manifest.source_url) == "https://www.planalto.gov.br/"


def test_load_documents_reads_manifest_pair(tmp_path: Path) -> None:
    text_path = tmp_path / "documento.md"
    manifest_path = tmp_path / "documento.manifest.json"

    text_path.write_text("conteúdo da lei", encoding="utf-8")
    manifest_path.write_text(
        """
        {
          "title": "Documento",
          "authority": "MPT",
          "source_url": "https://mpt.mp.br/",
          "source_type": "cartilha",
          "legal_ref": "Cartilha",
          "effective_date": "2021-05-10"
        }
        """,
        encoding="utf-8",
    )

    docs = load_documents(tmp_path)
    assert len(docs) == 1
    assert docs[0].file_path.name == "documento.md"
