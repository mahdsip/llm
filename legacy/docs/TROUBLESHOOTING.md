# Troubleshooting

## Qdrant: `wget: not found` o `curl: not found`

No usar directamente la imagen de Qdrant para el healthcheck. El proyecto usa `qdrant.Dockerfile`, que instala ambos programas.

Reconstruir:
```bash
docker compose build qdrant --no-cache
docker compose up -d qdrant
```

## Qdrant: `Permission denied` en `/qdrant/storage`

Comprobar:
```bash
ls -ld qdrant_data
```

Corregir:
```bash
sudo chown -R 1000:1000 qdrant_data
chmod 755 qdrant_data
docker compose up -d qdrant
```

## `IDF_EMBEDDING_MODELS` / incompatibilidad qdrant-client

No actualizar aleatoriamente las librerías de LlamaIndex/Qdrant.

Reconstruir con los pins:
```bash
docker compose build ragapi --no-cache
docker compose up -d ragapi
```

## `SimpleDirectoryReader` no se encuentra

Usar:
```python
from llama_index.core import SimpleDirectoryReader
```

No utilizar imports antiguos de `llama_index.readers`.

## `docx2txt` faltante

Ya está incluido en `ragapi/requirements.txt`.

## PPTX intenta descargar `vit-gpt2`

La configuración incluye:
```text
RAG_DISABLE_SLIDE_CAPTIONING=true
```

Si una versión futura del reader ignora esta variable, revisar el reader de PPTX antes de cambiar dependencias.

## `FileNotDecryptedError`

El PDF está protegido/cifrado. El ingest continúa y el archivo queda registrado en:
```text
state/ingest_errors.log
```

## `PdfStreamError` / PDF corrupto

El archivo no puede ser interpretado correctamente. No debe detener toda la ingestión.

## `/data/storage` ocupado

No borrar el directorio de montaje con `shutil.rmtree`.

El estado de esta versión se guarda en:
```text
/data/state
```

## `docker exec ragapi ...` falla porque el contenedor reinicia

Usar:
```bash
docker compose run --rm ragapi python ingest.py
```

Y revisar:
```bash
docker compose logs --tail=200 ragapi
```

## Ollama responde `model not found`

Descargar manualmente:
```bash
docker exec -it ollama ollama pull nomic-embed-text
docker exec -it ollama ollama pull llama3.1:8b
```

## OpenWebUI no responde

```bash
docker compose ps
docker compose logs --tail=200 openwebui
```

Comprobar:
```text
http://localhost:3000
```
