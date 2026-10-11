#!/usr/bin/env bash
# scripts/install.sh — Instala Ollama (si no está) y las dependencias Python
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# ---- Ollama -------------------------------------------------------
if command -v ollama &>/dev/null; then
    echo "[install] Ollama ya está instalado: $(ollama --version 2>/dev/null || true)"
else
    echo "[install] Ollama no encontrado. Instalando..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

# ---- Virtualenv ---------------------------------------------------
if [ ! -d "$REPO_ROOT/.venv" ]; then
    echo "[install] Creando virtualenv en .venv ..."
    python3 -m venv "$REPO_ROOT/.venv"
fi

# shellcheck source=/dev/null
source "$REPO_ROOT/.venv/bin/activate"

# ---- Dependencias Python ------------------------------------------
echo "[install] Instalando dependencias Python en .venv ..."
pip install -r "$REPO_ROOT/requirements.txt"

echo "[install] ¡Listo! Ejecuta './myagent --list-models' para verificar."
