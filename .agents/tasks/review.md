# myagent — Agente LLM local con Strands, Ollama y RAG Qdrant

Rediseño completo del repositorio: reemplaza el stack Docker legacy (LangChain + agentsvc + ragapi) por un script de terminal que arranca un agente Python con React loop sobre Ollama. El punto de entrada es un shell script `myagent` que delega en `agent/main.py`, que a su vez instancia un `Agent` de Strands con `OllamaModel` y las herramientas declaradas con `@tool`. El RAG usa exclusivamente Qdrant con ingestión incremental vía SHA-256; FAISS fue descartado de forma explícita y documentada en código, comentarios, README y `.env.example`. El README está en español e incluye todas las secciones comparativas requeridas con los recuentos mínimos de filas.

**Watch for:** `bash_exec` ejecuta con `shell=True` sin sandboxing — documentado correctamente en el README, aceptable para uso local; a tener en cuenta si el uso evoluciona. Ningún bloqueante encontrado.

**Verdict**: APPROVED

---

## High-level view

El checklist de la revisión anterior tenía 7 issues bloqueantes; todos están resueltos en esta versión. El README ahora documenta `MYAGENT_MODEL`, `QDRANT_URL` y `EMBEDDING_MODEL` — los nombres exactos que lee `config.py`. `CHUNK_SIZE`, `CHUNK_OVERLAP` y `TOP_K` se leen con `os.getenv` desde `config.py` con sus defaults documentados. El árbol de directorios del README refleja la estructura real (`agent/tools.py`, no `agent/tools/search.py`).

`_MANIFEST_PATH` está anclado a la raíz del proyecto vía `Path(__file__).parent.parent.parent`, lo que garantiza que el manifiesto SHA-256 se localiza correctamente independientemente del directorio de trabajo desde el que se invoque `myagent`. El README incluye una sección dedicada de advertencia de seguridad sobre `bash_exec`.

Los dos modelos requeridos (Qwen2.5-Coder 14B y DeepSeek-R1 32B) están mapeados en `config.py` con sus aliases. Los flags `--help`, `--model`/`-m`, `--rag`, `--ingest` y `--list-models` están implementados y documentados. Ambos servicios Docker tienen `profiles: [optional]` y `faiss-cpu` no aparece en ningún fichero del repositorio.

---

<details>
<summary>Issues (0)</summary>

No hay issues pendientes. Todos los issues del pase anterior han sido resueltos.

</details>

---

<details>
<summary>Details</summary>

## Estado de los issues del pase anterior

**Issue 1 — Estructura de directorios incorrecta en README**: resuelto (confirmed). El árbol del README ahora muestra `agent/tools.py` directamente, sin el subdirectorio `agent/tools/` ni el fichero `embeddings.py` inexistentes.

**Issue 2 — Variable `DEFAULT_MODEL` sin efecto**: resuelto (confirmed). La tabla de variables de entorno del README ahora documenta `MYAGENT_MODEL`, que es el nombre exacto que lee `config.py`.

**Issue 3 — `QDRANT_HOST`/`QDRANT_PORT` en lugar de `QDRANT_URL`**: resuelto (confirmed). El README documenta `QDRANT_URL` como URL completa, alineado con `config.py`.

**Issue 4 — `CHUNK_SIZE`, `CHUNK_OVERLAP`, `TOP_K` hardcodeados**: resuelto (confirmed). `config.py` los lee con `os.getenv` con defaults `768`, `100` y `6` respectivamente, y el README los documenta con esos valores por defecto.

**Issue 5 — `EMBED_MODEL` vs `EMBEDDING_MODEL`**: resuelto (confirmed). El README documenta `EMBEDDING_MODEL`, alineado con `config.py`.

**Issue 6 — `bash_exec` sin advertencia de seguridad**: resuelto (confirmed). El README tiene una sección "Seguridad — advertencia sobre `bash_exec`" que explica el alcance de lo que el agente puede ejecutar y advierte de no usarlo en entornos compartidos.

**Issue 7 — Manifiesto relativo al directorio de trabajo**: resuelto (confirmed). `_MANIFEST_PATH = Path(__file__).parent.parent.parent / ".rag_index" / "qdrant_manifest.json"` ancla la ruta a la raíz del proyecto. El comentario en el código explica el motivo.

## Verificación del checklist completo

- **Shell script con `--help`, `--model`, `--rag`, `--ingest`**: todos los flags están implementados en `agent/main.py` con argparse; `--help` es manejado automáticamente por argparse; el shell script excluye `--help` de la verificación de Ollama.
- **React loop Strands con OllamaModel**: `Agent(model=OllamaModel(...), tools=tools)` en `main.py`; el React loop es nativo de Strands.
- **RAG solo Qdrant**: no hay importaciones ni dependencias de FAISS en ningún fichero bajo `agent/`; `requirements.txt` no incluye `faiss-cpu`.
- **README en español con ≥5 filas en tabla React loop**: 6 filas (Strands, LangGraph, LlamaIndex Workflows, CrewAI, AutoGen, DSPy).
- **README con ≥5 filas en tabla RAG con FAISS, Qdrant, ChromaDB**: 6 filas (FAISS, Qdrant, ChromaDB, Milvus, pgvector, LanceDB).
- **Sección explicando por qué no FAISS**: presente en `## RAG con Qdrant > ### Por qué no FAISS`.
- **Sección Flash Attention**: presente como `## Flash Attention`.
- **`profiles: [optional]` en ambos servicios**: qdrant y openwebui tienen `profiles: [optional]` en `docker-compose.yml`.
- **No `faiss-cpu` en `requirements.txt`**: confirmado.

</details>

---

<details>
<summary>Ficheros revisados</summary>

| Fichero | Qué hace |
|---|---|
| `myagent` | Shell script de entrada; parsea flags, arranca venv, delega en Python |
| `agent/main.py` | CLI con argparse; instancia Strands Agent con OllamaModel y tools |
| `agent/config.py` | Constantes y lectura de env vars con os.getenv (MYAGENT_MODEL, QDRANT_URL, EMBEDDING_MODEL, CHUNK_SIZE, CHUNK_OVERLAP, TOP_K) |
| `agent/tools.py` | `@tool` bash_exec, file_read, rag_search |
| `agent/rag/qdrant_rag.py` | Ingestión incremental SHA-256 + búsqueda semántica sobre Qdrant; manifiesto anclado a raíz del proyecto |
| `agent/rag/base.py` | Interfaz abstracta RAGBackend |
| `docker-compose.yml` | Servicios qdrant y openwebui, ambos con `profiles: [optional]` |
| `requirements.txt` | strands-agents[ollama], qdrant-client, llama-index-*, rich; sin faiss-cpu |
| `README.md` | Documentación en español; tablas React loop (6 filas) y RAG (6 filas); sección "Por qué no FAISS"; sección Flash Attention; variables de entorno alineadas con config.py |

</details>
