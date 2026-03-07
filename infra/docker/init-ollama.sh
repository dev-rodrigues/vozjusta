#!/bin/sh
set -e

until ollama list >/dev/null 2>&1; do
  echo "Aguardando Ollama ficar disponível..."
  sleep 2
done

echo "Baixando modelo de geração..."
ollama pull llama3.1:8b

echo "Baixando modelo de embeddings..."
ollama pull nomic-embed-text

echo "Modelos prontos."
