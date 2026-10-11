# myagent

Agente LLM local interactivo en terminal: selección de modelo, React loop con Strands y RAG incremental con Qdrant, todo corriendo en tu propia máquina.

---

## Arquitectura

```
./myagent (shell)
    └── agent/main.py
            └── Strands Agent  ← React loop
                    └── OllamaModel
                            ├── qwen2.5-coder:14b
                            └── deepseek-r1:32b

(lateral — opcional)
    agent/rag/qdrant_rag.py
            └── Qdrant  ← docker compose --profile optional up qdrant
```

El shell script `myagent` es el punto de entrada. Parsea argumentos, activa el entorno virtual y delega en `agent/main.py`. El agente Python ejecuta el React loop de Strands, llama a los tools definidos con `@tool` y, si se activa `--rag`, conecta con Qdrant para recuperación semántica.

---

## Inicio rápido

### Prerrequisitos

- [Ollama](https://ollama.com) ≥ 0.1.33
- Python 3.11+
- Docker (opcional — solo para Qdrant y OpenWebUI)

### Instalación

```bash
git clone <repo>
cd llm

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

chmod +x myagent
```

### Descargar modelos

```bash
ollama pull qwen2.5-coder:14b
ollama pull deepseek-r1:32b
ollama pull nomic-embed-text   # necesario para RAG
```

### Uso

```bash
./myagent                              # menú interactivo
./myagent -m qwen                      # Qwen2.5-Coder 14B
./myagent -m deepseek                  # DeepSeek-R1 32B
./myagent -m qwen --rag --ingest ./docs/   # con RAG
./myagent --list-models
```

---

## Modelos disponibles

| Alias | Modelo Ollama | Parámetros | Uso recomendado |
|---|---|---|---|
| `qwen` | `qwen2.5-coder:14b` | 14 B | Código, depuración, scripts |
| `deepseek` | `deepseek-r1:32b` | 32 B | Razonamiento complejo, análisis |

Puedes añadir modelos adicionales editando `agent/config.py` sin modificar el script de entrada.

---

## Flash Attention

Ollama gestiona Flash Attention automáticamente desde la versión 0.1.33. No existe ningún flag `--flash-attention` en `myagent` porque no es necesario: Ollama lo activa solo cuando detecta soporte en el hardware.

**Cuándo se activa:**

- GPU NVIDIA con CUDA (compute capability ≥ 8.0 recomendado, aunque funciona desde 7.x)
- GPU AMD con ROCm
- Apple Silicon con Metal

**Variables de entorno para control manual:**

| Variable | Valor | Efecto |
|---|---|---|
| `OLLAMA_FLASH_ATTENTION` | `1` | Fuerza Flash Attention aunque Ollama no lo detecte |
| `OLLAMA_FLASH_ATTENTION` | `0` | Desactiva Flash Attention explícitamente |

Si tu GPU lo soporta y no ves mejora, prueba `OLLAMA_FLASH_ATTENTION=1 ./myagent -m deepseek`.

---

## React loop — comparativa de frameworks

| Framework | Loop nativo | Soporte Ollama | Complejidad setup | Licencia | Observaciones |
|---|---|---|---|---|---|
| **Strands Agents** | ✅ ReAct built-in | ✅ nativo | Baja | Apache-2.0 | `@tool` decorator, mínimas dependencias |
| LangGraph | ✅ grafo de estados | ✅ via LangChain | Media | MIT | Muy potente, verboso para casos simples |
| LlamaIndex Workflows | ✅ event-driven | ✅ | Media | MIT | Buena integración con RAG propio |
| CrewAI | ✅ multi-agente | ✅ | Media | MIT | Orientado a equipos de agentes, overhead innecesario en single-agent |
| AutoGen | ✅ multi-agente | ⚠️ via adaptador | Alta | MIT | Microsoft; excesivo para un agente local |
| DSPy | ❌ no loop nativo | ⚠️ | Alta | MIT | Optimización de prompts, no orquestación de agentes |

**Por qué Strands:** soporte nativo de Ollama sin capas de abstracción extra, decorador `@tool` para registrar herramientas con una línea, dependencias mínimas (no arrastra LangChain ni LlamaIndex), y licencia Apache-2.0 compatible con uso privado y comercial. Para un agente de terminal single-model es la opción con menor fricción.

---

## RAG con Qdrant

### Por qué Qdrant

Qdrant ofrece upserts incrementales: cuando un documento cambia, solo ese chunk se re-ingest, sin tocar el resto del índice. Esto encaja con colecciones de documentos que evolucionan (notas, código fuente, documentación viva).

### Por qué no FAISS

**FAISS y documentos dinámicos:** FAISS almacena el índice en ficheros binarios planos. Cuando un documento cambia, es necesario reconstruir el índice completo (no hay upserts parciales). Para colecciones de documentos que cambian con frecuencia esto es costoso en tiempo y cómputo. Qdrant, en cambio, soporta upserts incrementales — solo los documentos nuevos o modificados necesitan ser re-ingestados.

### Arrancar Qdrant

```bash
docker compose --profile optional up qdrant
```

El servicio queda disponible en `http://localhost:6333`. La UI de administración está en `http://localhost:6333/dashboard`.

### Ingestar documentos

```bash
./myagent --ingest ./docs/ -m qwen --rag
```

El flag `--ingest` recorre el directorio, genera chunks, crea embeddings con `nomic-embed-text` (descargado automáticamente si no está) y los almacena en Qdrant. Las ejecuciones sucesivas solo actualizan los documentos modificados.

### Modelo de embeddings

`nomic-embed-text` vía Ollama. Se descarga automáticamente en el primer `--ingest` si no está disponible. Dimensión: 768. No requiere GPU (funciona en CPU con velocidad aceptable).

---

## Comparativa de backends RAG

| Backend | Tipo | Persistencia | Ingest incremental | Servidor requerido | Escalabilidad | Licencia | Cuándo usarlo |
|---|---|---|---|---|---|---|---|
| **FAISS** | In-process | Ficheros binarios | ❌ rebuild completo | No | Millones de vecs (estático) | MIT | Colecciones estáticas, prototipado rápido |
| **Qdrant** | Server/Docker | Base de datos | ✅ upserts | Sí (Docker) | Alta, filtrado avanzado | Apache-2.0 | **Este proyecto** — docs dinámicos |
| **ChromaDB** | In-process/Server | SQLite/servidor | ✅ | Opcional | Media | Apache-2.0 | Prototipado, fácil setup |
| **Milvus** | Server | Base de datos | ✅ | Sí (pesado) | Muy alta | Apache-2.0 | Producción a gran escala |
| **pgvector** | PostgreSQL ext | PostgreSQL | ✅ | Sí (Postgres) | Media-alta | PostgreSQL License | Ya tienes Postgres en tu stack |
| **LanceDB** | In-process | Ficheros Lance | ✅ | No | Alta | Apache-2.0 | Alternativa moderna a FAISS con upserts |

**Recomendación:** para este proyecto (documentos que cambian) se eligió Qdrant por sus upserts incrementales y su filtrado avanzado por metadatos. Si no quieres levantar un servidor Docker, LanceDB es la mejor alternativa a FAISS con soporte de upserts y sin proceso externo.

---

## Servicios opcionales

Los servicios opcionales (Qdrant y OpenWebUI) están definidos en `docker-compose.yml` bajo el perfil `optional`, de forma que `docker compose up` sin argumentos no los arranca.

```bash
# Solo Qdrant
docker compose --profile optional up qdrant

# Solo OpenWebUI
docker compose --profile optional up openwebui

# Ambos
docker compose --profile optional up
```

OpenWebUI queda disponible en `http://localhost:3000` y se conecta automáticamente al servidor Ollama local.

---

## Variables de entorno

Crea un fichero `.env` en la raíz del proyecto. Todas las variables son opcionales; los valores por defecto funcionan para un uso estándar.

| Variable | Por defecto | Descripción |
|---|---|---|
| `OLLAMA_HOST` | `http://localhost:11434` | URL del servidor Ollama |
| `OLLAMA_FLASH_ATTENTION` | _(no definida)_ | `1` para forzar Flash Attention, `0` para desactivarla |
| `DEFAULT_MODEL` | `qwen` | Alias del modelo usado cuando no se pasa `-m` |
| `QDRANT_HOST` | `localhost` | Host donde corre Qdrant |
| `QDRANT_PORT` | `6333` | Puerto gRPC/HTTP de Qdrant |
| `QDRANT_COLLECTION` | `myagent` | Nombre de la colección de vectores |
| `EMBED_MODEL` | `nomic-embed-text` | Modelo de embeddings (via Ollama) |
| `CHUNK_SIZE` | `512` | Tamaño de chunk en tokens para ingestión |
| `CHUNK_OVERLAP` | `64` | Solapamiento entre chunks consecutivos |
| `TOP_K` | `5` | Número de fragmentos recuperados en cada consulta RAG |

---

## Estructura del proyecto

```
llm/
├── myagent                    # Punto de entrada: shell script
├── agent/
│   ├── main.py                # Inicialización del agente Strands
│   ├── config.py              # Mapa alias → modelo Ollama, defaults
│   ├── tools/
│   │   └── search.py          # Tools registradas con @tool (web, filesystem…)
│   └── rag/
│       ├── qdrant_rag.py      # Ingestión y consulta contra Qdrant
│       └── embeddings.py      # Wrapper nomic-embed-text vía Ollama
├── docs/                      # Documentos de ejemplo para ingestar
├── docker-compose.yml         # Servicios opcionales: Qdrant, OpenWebUI
├── requirements.txt           # Dependencias Python (strands-agents, qdrant-client…)
├── .env.example               # Plantilla de variables de entorno
├── legacy/                    # Proyecto anterior (model-rag-local renombrado)
│   └── README.md
└── README.md                  # Este fichero
```

---

## Legacy

El directorio [`legacy/`](legacy/) contiene el proyecto original `model-rag-local` — un stack Docker completo con LangChain, `agentsvc`, `ragapi` y OpenWebUI sobre `llama3.1:8b`. Se conserva como referencia histórica y no recibe mantenimiento activo.
