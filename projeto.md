# Projeto: Chatbot de Orientação sobre Discriminação no Trabalho

## 1. Visão Geral

Este projeto tem como objetivo desenvolver um **chatbot inteligente** capaz de orientar trabalhadores sobre **discriminação e assédio no ambiente de trabalho**, utilizando **Inteligência Artificial e Recuperação de Informação Jurídica (RAG – Retrieval Augmented Generation)**.

O sistema irá responder perguntas relacionadas a:

- Assédio moral
- Discriminação racial
- Discriminação de gênero
- Igualdade salarial
- Direitos trabalhistas
- Como denunciar casos de discriminação

O chatbot será alimentado por **leis trabalhistas brasileiras, documentos oficiais e materiais institucionais**, garantindo que as respostas sejam baseadas em fontes confiáveis.

---

# 2. Objetivos do Projeto

## Objetivo Geral

Criar uma plataforma baseada em IA capaz de fornecer **orientação jurídica básica sobre discriminação no trabalho**, promovendo acesso à informação e direitos trabalhistas.

## Objetivos Específicos

- Facilitar o entendimento de direitos trabalhistas
- Combater desinformação jurídica
- Orientar trabalhadores sobre canais de denúncia
- Disponibilizar respostas baseadas em legislação brasileira
- Criar uma base tecnológica extensível para educação jurídica

---

# 3. Problema que o Projeto Resolve

Muitos trabalhadores enfrentam situações como:

- humilhação no trabalho
- discriminação racial
- desigualdade salarial
- abuso de autoridade
- perseguição profissional

Entretanto, grande parte das pessoas **não sabe identificar quando seus direitos estão sendo violados**, nem **como denunciar corretamente**.

Este projeto busca **democratizar o acesso à informação jurídica**, permitindo que qualquer pessoa possa compreender seus direitos de forma simples.

---

# 4. Escopo do Sistema

O sistema permitirá que usuários façam perguntas como:

- "O que é assédio moral no trabalho?"
- "Meu chefe pode me humilhar na frente dos outros?"
- "Discriminação racial no trabalho é crime?"
- "O que fazer se sofrer discriminação?"
- "Como denunciar uma empresa?"

O chatbot responderá com base em:

- legislação brasileira
- documentos institucionais
- orientações oficiais

Sempre apresentando **fontes e referências legais**.

---

# 5. Fontes Jurídicas Utilizadas

O sistema utilizará como base:

## Constituição Federal
Princípios fundamentais de igualdade e dignidade.

## Consolidação das Leis do Trabalho (CLT)

Principais dispositivos sobre proteção ao trabalhador.

## Lei 7.716/1989
Define crimes resultantes de preconceito racial.

## Estatuto da Igualdade Racial (Lei 12.288/2010)

Garantias de igualdade racial no Brasil.

## Lei 9.799/1999

Proíbe práticas discriminatórias no trabalho.

## Lei 14.611/2023

Lei de igualdade salarial entre homens e mulheres.

## Convenção 111 da OIT

Combate à discriminação em emprego e profissão.

## Materiais institucionais

Cartilhas e orientações do:

- Ministério Público do Trabalho (MPT)
- Tribunal Superior do Trabalho (TST)
- Ministério do Trabalho

---

# 6. Arquitetura Tecnológica

O sistema será construído utilizando arquitetura baseada em **RAG (Retrieval Augmented Generation)**.

Fluxo geral:

```
Usuário pergunta
       ↓
Gerar embedding da pergunta
       ↓
Buscar trechos relevantes na base jurídica
       ↓
Enviar contexto + pergunta para LLM
       ↓
Gerar resposta baseada nas fontes
```

---

# 7. Stack Tecnológica (100% gratuita)

## Backend

Python + FastAPI

Motivo:
- leve
- rápido
- ideal para APIs

---

## Modelo de Linguagem (LLM)

Ollama rodando modelo open-source local.

Exemplos de modelos:

- Llama
- Mistral
- Gemma

---

## Embeddings

Sentence Transformers

Modelos recomendados:

- bge-m3
- multilingual-e5

---

## Banco Vetorial

PostgreSQL + pgvector

Motivo:
- simples
- open source
- fácil de operar

---

## Reranking

bge-reranker

Melhora a precisão da busca jurídica.

---

# 8. Arquitetura do Backend

Estrutura sugerida:

```
backend/
│
├── app/
│
├── api/
│   ├── routes/
│
├── core/
│   ├── config.py
│   ├── prompts.py
│
├── rag/
│   ├── ingest.py
│   ├── embeddings.py
│   ├── retrieval.py
│   ├── rerank.py
│   ├── generation.py
│
├── domain/
│   ├── models/
│   ├── services/
│
├── infra/
│   ├── db/
│   ├── vector/
│   ├── llm/
│
└── tests/
```

---

# 9. Pipeline de Ingestão de Documentos

O processo de ingestão consiste em:

1. Coletar documentos jurídicos
2. Extrair texto
3. Dividir em trechos menores (chunks)
4. Gerar embeddings
5. Salvar no banco vetorial

Cada chunk armazenará:

- texto
- lei
- artigo
- fonte
- URL oficial
- embedding

---

# 10. API do Sistema

Endpoints principais:

### Perguntar ao chatbot

```
POST /api/v1/ask
```

Body:

```
{
  "question": "O que é assédio moral no trabalho?"
}
```

---

### Ingestão de documentos

```
POST /api/v1/ingest/document
```

---

### Listar fontes jurídicas

```
GET /api/v1/sources
```

---

### Health check

```
GET /api/v1/health
```

---

# 11. Estrutura da Resposta da IA

Exemplo de resposta:

```
{
  "answer": "Assédio moral é caracterizado por condutas repetitivas que humilham ou constrangem o trabalhador.",
  "sources": [
    {
      "title": "Cartilha Assédio Moral - MPT",
      "url": "https://mpt.mp.br",
      "excerpt": "Assédio moral consiste em exposição repetitiva..."
    }
  ],
  "disclaimer": "Resposta informativa. Não substitui orientação jurídica profissional."
}
```

---

# 12. Segurança e Ética

O sistema seguirá princípios importantes:

## Não substituir advogado

O chatbot é apenas informativo.

## Respostas baseadas em fonte

O modelo não poderá inventar leis.

## Privacidade

Nenhum dado pessoal será armazenado sem consentimento.

## LGPD

O sistema seguirá princípios da Lei Geral de Proteção de Dados.

---

# 13. Possíveis Evoluções Futuras

Fases futuras do projeto incluem:

- chatbot com voz
- aplicativo mobile
- painel de curadoria jurídica
- classificação automática de denúncias
- integração com canais de denúncia oficiais
- assistente de coleta de evidências
- analytics sobre discriminação no trabalho

---

# 14. Impacto Social Esperado

Este projeto pode:

- aumentar o acesso à informação jurídica
- ajudar trabalhadores a reconhecer abusos
- incentivar denúncias de discriminação
- apoiar políticas de igualdade no trabalho
- promover educação sobre direitos humanos

---

# 15. Licença do Projeto

Sugestão:

MIT License

ou

Apache 2.0

---
