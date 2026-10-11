#!/usr/bin/env bash
# scripts/pull-models.sh — Descarga los modelos Ollama necesarios
set -euo pipefail

MODELS=(
    "qwen2.5-coder:14b"
    "deepseek-r1:32b"
)

for model in "${MODELS[@]}"; do
    echo "[pull-models] Descargando $model ..."
    ollama pull "$model"
    echo "[pull-models] $model listo."
done

echo "[pull-models] Todos los modelos descargados correctamente."
