# RAG local con OpenWebUI + Ollama + Qdrant + LlamaIndex + LangChain

Proyecto reproducible para montar desde cero un RAG local en un BMAX/PC Linux sin GPU dedicada.

## Arquitectura

- OpenWebUI: interfaz web, puerto 3000
- Ollama: LLM y embeddings, puerto 11434
- Qdrant: base vectorial, puertos 6333/6334
- ragapi: ingestión y consulta RAG, puerto 8000
- agentsvc: capa HTTP de orquestación, puerto 8100

Documentos:
`DOCUMENTS_DIR_HOST` -> `/data/docs` (solo lectura). La ruta real se configura en `.env` y nunca se guarda en Git.

## Modelos

LLM:
`llama3.1:8b`

Embeddings:
`nomic-embed-text`

Los modelos se descargan explícitamente; no se debe asumir que Ollama los descargará automáticamente.

## Instalación rápida

1. Instalar KDE Neon/Ubuntu y actualizar:
```bash
sudo apt update && sudo apt full-upgrade -y
```

2. Instalar Docker Engine y Compose:
```bash
chmod +x scripts/install-docker.sh
./scripts/install-docker.sh
```

Cerrar sesión y volver a entrar.

3. Clonar el repositorio:
```bash
git clone <URL_DEL_REPOSITORIO>
cd rag-local
```

4. Crear la configuración local:
```bash
cp .env.example .env
nano .env
```

Establece `DOCUMENTS_DIR_HOST` con la ruta absoluta de la carpeta de documentos de esta máquina.

Comprueba después la ruta configurada:
```bash
set -a; source .env; set +a
test -d "$DOCUMENTS_DIR_HOST" && echo OK
```

5. Crear almacenamiento local:
```bash
mkdir -p qdrant_data state
chmod 755 qdrant_data state
```

6. Construir y arrancar:
```bash
docker compose build
docker compose up -d
```

7. Descargar modelos:
```bash
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it ollama ollama pull llama3.1:8b
docker exec -it ollama ollama list
```

8. Comprobar servicios:
```bash
docker compose ps
curl http://localhost:6333/collections
curl http://localhost:8000/health
curl http://localhost:8100/health
```

9. Ejecutar la primera ingestión:
```bash
docker exec -it ragapi python ingest.py
```

Si `ragapi` estuviera reiniciándose, usar:
```bash
docker compose run --rm ragapi python ingest.py
```

10. Probar una pregunta:
```bash
curl -s http://localhost:8000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"¿Qué información hay en mis documentos?"}'
```

11. Configurar OpenWebUI para usar el agente RAG:

En OpenWebUI añade una conexión OpenAI-compatible apuntando a:
```text
http://agentsvc:8100/v1
```

El modelo publicado será:
```text
llama3.1:8b
```

Así el flujo será:
```text
OpenWebUI -> agentsvc -> Llama 3.1 -> search_rag -> ragapi -> Qdrant
```

12. Abrir OpenWebUI:
http://localhost:3000

## Ingestión incremental

El manifiesto está en:
`state/manifest.json`

Se calcula SHA-256 por archivo. Los archivos sin cambios se saltan.

Los errores quedan registrados en:
`state/ingest_errors.log`

## Endpoint de ingestión

```bash
curl -X POST http://localhost:8000/ingest
```

## Diagnóstico

Ver todos los contenedores:
```bash
docker compose ps
```

Logs:
```bash
docker compose logs -f qdrant
docker compose logs -f ollama
docker compose logs -f ragapi
docker compose logs -f agentsvc
docker compose logs -f openwebui
```

Recrear imágenes:
```bash
docker compose build --no-cache
docker compose up -d
```

## Correcciones incorporadas

### Qdrant sin curl/wget
Se utiliza `qdrant.Dockerfile` para instalar ambos.

### Permisos de Qdrant
Qdrant se ejecuta como UID/GID 1000 y usa `qdrant_data/`.

### LlamaIndex/Qdrant incompatibles
Se fijan versiones conocidas compatibles en `ragapi/requirements.txt`.

### SimpleDirectoryReader
Se importa desde `llama_index.core`.

### PPTX y descarga de modelos externos
Se establece `RAG_DISABLE_SLIDE_CAPTIONING=true`.

### `/data/storage` ocupado
No se elimina nunca el punto de montaje. El estado persistente se mantiene en `state/`.

### Ollama
Los modelos se descargan explícitamente con `ollama pull`.

## Seguridad

No subir a Git:

- documentos personales;
- `qdrant_data/`;
- `state/`;
- `.env`;
- claves/API tokens.

El `.gitignore` ya excluye estos datos.
