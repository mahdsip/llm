# Instalación desde cero

## 1. Sistema

El proyecto se diseñó para Linux x86-64. KDE Neon es un derivado de Ubuntu; Docker recomienda seguir las instrucciones de Ubuntu para los derivados Ubuntu, aunque el soporte oficial se refiere a Ubuntu.

Comprobar:
```bash
uname -m
cat /etc/os-release
```

Debe aparecer `x86_64`/`amd64`.

Actualizar:
```bash
sudo apt update
sudo apt full-upgrade -y
sudo reboot
```

## 2. Git

```bash
sudo apt install -y git curl ca-certificates
git --version
```

## 3. Docker Engine

Ejecutar:
```bash
chmod +x scripts/install-docker.sh
./scripts/install-docker.sh
```

Después cerrar sesión y volver a entrar.

Comprobar:
```bash
docker --version
docker compose version
docker run hello-world
```

## 4. Repositorio

```bash
cd ~
git clone <URL_DEL_REPOSITORIO> rag-local
cd rag-local
```

## 5. Documentos

El proyecto espera:
```text
$DOCUMENTS_DIR_HOST
```

No se copian al repositorio.

Comprobar:
```bash
test -d "$DOCUMENTS_DIR_HOST" && echo OK
```

## 6. Permisos

```bash
mkdir -p qdrant_data state
chmod 755 qdrant_data state
```

## 7. Arranque

```bash
docker compose build
docker compose up -d
docker compose ps
```

## 8. Modelos Ollama

Muy importante: instalar explícitamente ambos:

```bash
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it ollama ollama pull llama3.1:8b
```

Comprobar:
```bash
docker exec -it ollama ollama list
```

## 9. Pruebas

```bash
curl -s http://localhost:6333/collections
curl -s http://localhost:8000/health
curl -s http://localhost:8100/health
```

## 10. Primera ingestión

```bash
docker exec -it ragapi python ingest.py
```

Para seguir el proceso:
```bash
docker logs -f ragapi
```

Errores:
```bash
cat state/ingest_errors.log
```

Estado:
```bash
cat state/manifest.json
```

## 11. Prueba RAG

```bash
curl -s http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"Resume qué documentos hay disponibles."}'
```

## 12. OpenWebUI

Abrir:
```text
http://localhost:3000
```

## 13. Reinicio futuro

Después de un reinicio del BMAX:
```bash
cd ~/rag-local
docker compose up -d
```

No hay que reinstalar Docker ni volver a descargar los modelos mientras los datos persistentes sigan intactos.

## 14. Actualización del repositorio

```bash
git pull
docker compose build
docker compose up -d
```


## 15. Conexión OpenWebUI -> agentsvc

Desde OpenWebUI configura una conexión de proveedor compatible con OpenAI usando:

```text
Base URL: http://agentsvc:8100/v1
```

El modelo será:

```text
llama3.1:8b
```

El agente utiliza Llama 3.1 para decidir cuándo llamar a `search_rag`.

El flujo de una pregunta documental es:

```text
OpenWebUI
   ↓
agentsvc
   ↓
Llama 3.1
   ↓
tool: search_rag
   ↓
ragapi
   ↓
Qdrant + nomic-embed-text
   ↓
contexto recuperado
   ↓
Llama 3.1
   ↓
respuesta
```
