#!/usr/bin/env bash
# scripts/pull-models.sh — Descarga los modelos Ollama necesarios
set -euo pipefail

echo "[pull-models] Descargando modelos de lenguaje ..."
ollama pull qwen2.5-coder:14b
echo "[pull-models] qwen2.5-coder:14b listo."

ollama pull deepseek-r1:32b
echo "[pull-models] deepseek-r1:32b listo."

echo "[pull-models] Descargando modelo de embeddings para RAG ..."
ollama pull nomic-embed-text
echo "[pull-models] nomic-embed-text listo."

echo "[pull-models] Todos los modelos descargados correctamente."
