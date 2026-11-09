# myagent — agente conversacional local con React loop y RAG incremental

Esta implementación reescribe el repositorio desde cero sobre un nuevo stack: shell script `myagent` como punto de entrada, agente Strands con React loop sobre Ollama, y RAG incremental contra Qdrant. El objetivo del rediseño era eliminar la dependencia de Docker para el flujo principal, simplificar la selección de modelos desde la terminal, y construir un pipeline RAG que soporte actualizaciones de documentos sin reconstruir el índice completo. Los servicios Docker (Qdrant, OpenWebUI) son estrictamente opcionales y no arrancan con `docker compose up` a secas.

Watch for: `bash_exec` ejecuta shell arbitrario con los permisos del usuario — el README lo advierte, pero no hay ningún mecanismo de confirmación en tiempo de ejecución. La herramienta `rag_search` instancia `QdrantBackend` en cada llamada, creando una conexión nueva al cliente Qdrant por query; en conversaciones largas con RAG activo esto acumula conexiones sin reutilización. El flag `--help` lo gestiona argparse implícitamente, pero el shell script solo corta la verificación de Ollama para `-h/--help`; si argparse añade algún alias en el futuro podría fallar silenciosamente el check.

**Verdict**: APPROVED

---

## High-level view

El shell script actúa como un thin wrapper: comprueba que Ollama esté en marcha (salvo para `--help` y `--list-models`), activa el virtualenv si existe, y delega todo el parsing de argumentos a `agent/main.py` vía `python -m`. El diseño evita duplicar lógica entre bash y Python.

El agente usa `OllamaModel` de Strands directamente, sin capas LangChain. Los tools `bash_exec`, `file_read` y `rag_search` se registran con `@tool` y solo se cargan cuando son necesarios: `rag_search` no se importa si `--rag` no está activo, lo que evita conectarse a Qdrant en arranques normales.

El backend RAG hereda de una interfaz abstracta `RAGBackend`, pero solo existe una implementación (Qdrant). La elección de Qdrant sobre FAISS está justificada en el código, en el README y en `requirements.txt`: colecciones dinámicas con upserts incrementales frente a reconstrucción completa del índice. El manifiesto SHA-256 persiste en `.rag_index/qdrant_manifest.json` y permite saltarse ficheros no modificados entre ejecuciones de `--ingest`.

El `docker-compose.yml` define ambos servicios opcionales (Qdrant y OpenWebUI) bajo el perfil `optional`, de modo que `docker compose up` sin argumentos no arranca ninguno. Flash Attention no se expone como flag porque Ollama lo gestiona automáticamente desde v0.1.33; el README documenta `OLLAMA_FLASH_ATTENTION` para control manual.

---

<details>
<summary>Issues (5)</summary>

1. **Conexión Qdrant por llamada en rag_search** — `QdrantBackend` se instancia dentro de `rag_search` en cada invocación del tool, abriendo un nuevo `QdrantClient` por query. En conversaciones largas con RAG activo esto acumula conexiones sin reutilización. El backend debería instanciarse una vez en `main()` y capturarse en el closure del tool o pasarse vía `functools.partial`.

2. **bash_exec sin confirmación del usuario** — El agente puede ejecutar cualquier comando de shell de forma autónoma. Considerar un modo `--safe` que muestre el comando y pida confirmación antes de `subprocess.run`, especialmente relevante si el agente procesa ficheros de terceros ingestados con `--ingest`.

3. **Chunks obsoletos no se purgan en Qdrant** — Al actualizar un fichero, los vectores de la versión anterior (identificados por el sha viejo) quedan en la colección indefinidamente. En colecciones que evolucionan mucho, los vectores huérfanos se acumulan. Añadir un paso de borrado por `source_path` antes de re-indexar un fichero modificado.

4. **Dependencia implícita de curl en el shell script** — La verificación de Ollama falla sin mensaje útil si `curl` no está en el PATH. Añadir un preflight `command -v curl` o implementar el check en Python para eliminar la dependencia.

5. **Temperatura fija no configurable para DeepSeek-R1** — `temperature=0.7` está hardcodeada para todos los modelos. DeepSeek-R1 funciona mejor con 0.1-0.3. Exponer `MYAGENT_TEMPERATURE` como variable de entorno en `config.py` y `.env.example`.

</details>

---

<details>
<summary>Detalles</summary>

### Shell script: dependencia de curl y exposición de .env

La verificación de Ollama usa `curl -s http://localhost:11434` — si `curl` no está en el PATH del sistema (entornos minimalistas, algunos contenedores), el script falla con un error poco descriptivo antes de activar el virtualenv. Un preflight con `command -v curl` o una alternativa con `python3 -c "import urllib.request..."` sería más robusto.

La carga de `.env` con `set -o allexport` + `source` expone todas las variables del fichero como variables de entorno del proceso Python hijo. Si `.env` contiene variables con nombres que colisionen con variables del sistema (`PATH`, `HOME`, `USER`), podría causar problemas silenciosos. El patrón más seguro sería usar `python-dotenv` exclusivamente (ya lo hace `config.py`) y eliminar la carga desde bash.

### Temperatura fija para DeepSeek-R1

El agente se instancia con `temperature=0.7` para todos los modelos. Para DeepSeek-R1 (modelo de razonamiento con cadenas `<think>`), un valor de 0.1-0.3 produce razonamientos más consistentes. La temperatura no está expuesta como variable de entorno ni como flag, así que el único ajuste posible hoy es editar `main.py` directamente. Añadir `MYAGENT_TEMPERATURE` a `config.py` y a `.env.example` sería un cambio de una línea.

### RAG: manifest SHA-256 e identificadores de chunk

El path del manifiesto está anclado a la raíz del proyecto con `Path(__file__).parent.parent.parent`, lo que funciona correctamente independientemente del directorio de trabajo. Los chunks se identifican por `{sha256}:{chunk_index}`: cuando un fichero cambia, su nuevo sha produce IDs distintos, pero los IDs viejos permanecen en Qdrant — no hay lógica de borrado de chunks obsoletos. En colecciones que evolucionan mucho, los vectores huérfanos de versiones anteriores se acumulan sin nunca ser purgados.

### Conexión Qdrant por llamada (confirmed)

En `tools.py`, `rag_search` instancia `QdrantBackend(...)` en cada invocación del tool. `QdrantBackend.__init__` no abre conexión, pero `search()` llama a `_client_and_store()` que crea `QdrantClient(url=...)` y `QdrantVectorStore(...)` en cada llamada. El cliente `qdrant-client` tiene pooling interno, pero crear un nuevo objeto `QdrantClient` por query no es el patrón recomendado y puede generar overhead de handshake en conversaciones largas. El fix natural sería instanciar el backend una sola vez en `main()` y capturarlo en el closure del tool o usar `functools.partial`.

### bash_exec: superficie de ataque (confirmed)

`bash_exec` ejecuta `subprocess.run(command, shell=True, ...)` con los permisos del proceso `myagent`. El timeout de 30 s y el truncado a 4000 caracteres limitan el impacto de salidas masivas o bucles, pero no la ejecución en sí. El riesgo se amplifica si el usuario ingest a documentos de terceros con `--ingest`: un documento podría contener instrucciones que el LLM interprete como comandos a ejecutar (prompt injection → shell execution).

### Cobertura de tests

No existe directorio `tests/` ni ficheros de test. Para un proyecto de esta naturaleza (herramienta personal), la ausencia de tests formales es comprensible, pero las rutas críticas sin cobertura son:

- El parsing de argumentos y la resolución de alias de modelo en `_resolve_model`.
- La lógica de manifiesto SHA-256 en `qdrant_rag.py` (skip de ficheros no modificados, actualización tras cambio).
- El comportamiento de `rag_search` cuando Qdrant no está disponible (actualmente propagaría la excepción del cliente hasta el agente sin captura).

</details>

---

<details>
<summary>Mapa de ficheros</summary>

| Fichero | Cambio |
|---|---|
| `myagent` | Shell script nuevo — entrypoint, verificación Ollama, activación de venv |
| `agent/main.py` | CLI con argparse, inicialización de Strands Agent, loop conversacional |
| `agent/config.py` | Constantes centrales: alias de modelos, URLs de servicios, parámetros RAG |
| `agent/tools.py` | Tools `bash_exec`, `file_read`, `rag_search` con decorador `@tool` |
| `agent/rag/base.py` | Interfaz abstracta `RAGBackend` |
| `agent/rag/qdrant_rag.py` | Backend Qdrant con ingestión incremental SHA-256 y búsqueda semántica |
| `requirements.txt` | Dependencias Python: strands-agents, qdrant-client, llama-index, rich |
| `docker-compose.yml` | Servicios opcionales Qdrant y OpenWebUI bajo perfil `optional` |
| `README.md` | Documentación en español con tablas comparativas de frameworks y backends RAG |

</details>
