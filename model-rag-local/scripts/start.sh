#!/usr/bin/env bash
set -euo pipefail

mkdir -p qdrant_data state
chmod 755 qdrant_data state

docker compose build
docker compose up -d

echo
echo "Servicios:"
docker compose ps
echo
echo "Ahora descarga los modelos:"
echo "  docker exec -it ollama ollama pull nomic-embed-text"
echo "  docker exec -it ollama ollama pull llama3.1:8b"
