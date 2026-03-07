from rag_core.citations import extract_citations


def test_extract_citations_deduplicates_indexes() -> None:
    answer = "Texto [fonte:2] e outro [FONTE:1] e repetido [fonte:2]"
    citations = extract_citations(answer)
    assert [item.index for item in citations] == [1, 2]
