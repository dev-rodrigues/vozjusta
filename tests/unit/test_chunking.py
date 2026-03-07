from rag_core.chunking import chunk_text, clean_text


def test_clean_text_normalizes_whitespace() -> None:
    raw = "  linha 1\n\nlinha\t\t2   "
    assert clean_text(raw) == "linha 1 linha 2"


def test_chunk_text_creates_overlap_chunks() -> None:
    text = " ".join(["texto"] * 500)
    chunks = chunk_text(text, chunk_size=120, overlap=20)

    assert len(chunks) > 1
    assert all(len(item) <= 120 for item in chunks)


def test_chunk_text_rejects_invalid_overlap() -> None:
    try:
        chunk_text("abc", chunk_size=100, overlap=100)
        raise AssertionError("Era esperado ValueError")
    except ValueError:
        assert True
