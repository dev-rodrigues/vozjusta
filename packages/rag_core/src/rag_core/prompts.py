"""Prompt builders for legal RAG interactions."""

from __future__ import annotations

from typing import Sequence


DISCLAIMER_TEXT = (
    "Resposta informativa, com base em fontes públicas. "
    "Não substitui orientação jurídica profissional."
)


def build_system_prompt() -> str:
    return (
        "Você é um assistente jurídico informativo do projeto VozJusta. "
        "Responda SEMPRE em português brasileiro (pt-BR), de forma clara e acessível. "
        "Seja objetivo e conciso (máximo de 6 frases curtas). "
        "Use apenas o contexto fornecido. "
        "Se não houver suporte suficiente nas fontes, diga explicitamente que não há base bastante. "
        "Não invente leis, artigos, órgãos, números de processos ou URLs. "
        "Sempre inclua referência no formato [fonte:N] ao final de frases importantes."
    )


def build_user_prompt(question: str, contexts: Sequence[dict[str, str]]) -> str:
    ctx_lines: list[str] = []
    for idx, item in enumerate(contexts, start=1):
        title = item.get("title", "Fonte sem título")
        authority = item.get("authority", "Órgão não informado")
        legal_ref = item.get("legal_ref", "Referência não informada")
        excerpt = item.get("excerpt", "")
        ctx_lines.append(
            f"[FONTE {idx}]\\n"
            f"Título: {title}\\n"
            f"Órgão: {authority}\\n"
            f"Referência legal: {legal_ref}\\n"
            f"Trecho: {excerpt}"
        )

    context_block = "\n\n".join(ctx_lines)

    return (
        "Contexto recuperado:\n"
        f"{context_block}\n\n"
        f"Pergunta do usuário: {question}\n\n"
        "Instruções de resposta:\n"
        "1) Explique em linguagem simples e de forma breve.\n"
        "2) Cite as fontes com [fonte:N].\n"
        "3) Quando apropriado, indique canais oficiais de denúncia (MPT, sindicato, ouvidoria).\n"
        "4) Não faça aconselhamento jurídico individualizado.\n"
        "5) Limite a resposta a no máximo 120 palavras."
    )
