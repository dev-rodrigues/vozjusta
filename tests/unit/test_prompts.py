from rag_core.prompts import DISCLAIMER_TEXT, build_system_prompt, build_user_prompt


def test_build_system_prompt_mentions_ptbr_and_citations() -> None:
    prompt = build_system_prompt()
    assert "português brasileiro" in prompt
    assert "[fonte:N]" in prompt


def test_build_user_prompt_contains_context_and_question() -> None:
    prompt = build_user_prompt(
        "O que é assédio moral?",
        [
            {
                "title": "Cartilha MPT",
                "authority": "MPT",
                "legal_ref": "CLT",
                "excerpt": "Trecho legal",
            }
        ],
    )
    assert "Pergunta do usuário" in prompt
    assert "Cartilha MPT" in prompt


def test_disclaimer_is_informative() -> None:
    assert "Não substitui" in DISCLAIMER_TEXT
