# Implementation Plan — myagent

## Findings from codebase exploration

### Existing code assessment
| File | Reusable? | What to extract |
|---|---|---|
| `model-rag-local/agentsvc/main.py` | Partially | System prompt pattern (Spanish-first), tool dispatch shape (`run_agent` while-loop), `search_rag` tool signature |
| `model-rag-local/ragapi/main.py` | Partially | Qdrant client setup, `OllamaEmbedding` usage, `QdrantVectorStore` + `VectorStoreIndex` query engine |
| `model-rag-local/ragapi/ingest.py` | Yes | SHA-256 manifest pattern for incremental ingest, `SentenceSplitter` chunking params (768/100), `iter_files` traversal |
| `model-rag-local/docker-compose.yml` | Partially | Qdrant service definition (reuse with `profiles: [optional]`), openwebui service |
| Dockerfiles, scripts/install-docker.sh | No | Not relevant for a native shell-based tool |

**Decision on model-rag-local/**: Keep as `legacy/` subfolder. Renaming (not deleting) preserves git history and the existing README still documents the old project. A note in the new README links to it.

### Key design decisions confirmed

1. **Strands OllamaModel**: Confirmed to exist natively in `strands-agents[ollama]` package (class `strands.models.ollama.OllamaModel`). Install: `pip install 'strands-agents[ollama]'`. No custom wrapper needed. The agent gets tools via `Agent(model=ollama_model, tools=[...])` and Strands dispatches the React loop automatically.

2. **Flash Attention**: Ollama auto-enables it when the system supports it (`OLLAMA_FLASH_ATTENTION=1` is the env var to force it; default is auto). No user-facing flag in `myagent`. Document in README that users can export `OLLAMA_FLASH_ATTENTION=1` to force it or `=0` to disable on unstable hardware.

3. **Exact Ollama model names** (confirmed on ollama.com):
   - `qwen2.5-coder:14b` — Qwen2.5 Coder series, 14B, code-focused
   - `deepseek-r1:32b` — DeepSeek-R1 32B distill (Qwen base, reasoning with `<think>` chains)

4. **React loop**: Strands `Agent` runs the loop natively via its `__call__`. No manual while loop needed. Tools are Python functions decorated with `@tool`.

5. **RAG default**: FAISS (no server, pure Python). Qdrant optional (`RAG_BACKEND=qdrant` env var + `docker compose --profile optional up`).

6. **Embedding model for FAISS**: `all-MiniLM-L6-v2` via `sentence-transformers`. 384-dim, downloads automatically on first use (~90MB), no server needed. Qdrant backend reuses Ollama's `nomic-embed-text` for consistency with the existing ragapi pattern.

---

## Files to create

```
/home/mahdsip/Software/llm/
├── myagent                        # shell entry point
├── agent/
│   ├── __init__.py
│   ├── main.py                    # CLI logic + Strands Agent setup
│   ├── config.py                  # env vars, model registry, RAG config
│   ├── tools.py                   # @tool: bash_exec, file_read, rag_search
│   └── rag/
│       ├── __init__.py
│       ├── base.py                # abstract RAGBackend
│       ├── faiss_rag.py           # FAISS + sentence-transformers
│       └── qdrant_rag.py          # qdrant-client (adapted from ragapi/main.py)
├── scripts/
│   ├── install.sh
│   └── pull-models.sh
├── requirements.txt
├── pyproject.toml
├── .env.example
├── docker-compose.yml
├── README.md                      # full rewrite
└── legacy/                        # git mv model-rag-local/ legacy/
```

---

## Implementation order

- [ ] 1. Rename `model-rag-local/` to `legacy/` via `git mv`.
      Keeps git history intact. Update root `README.md` references once.
      Files: `legacy/` (renamed), `README.md` (reference update)
      Verify: `git status` shows rename; directory structure is correct.

- [ ] 2. Create `agent/config.py` — all runtime configuration in one place.
      Reads env vars: `MYAGENT_MODEL` (default `qwen2.5-coder:14b`), `OLLAMA_HOST`
      (default `http://localhost:11434`), `RAG_BACKEND` (default `faiss`),
      `RAG_DOCS_DIR`, `QDRANT_URL` (default `http://localhost:6333`),
      `QDRANT_COLLECTION` (default `myagent_docs`), `EMBEDDING_MODEL`
      (default `nomic-embed-text` for Qdrant, `all-MiniLM-L6-v2` for FAISS).
      Defines `MODELS` dict: `{"qwen": "qwen2.5-coder:14b", "deepseek": "deepseek-r1:32b"}`.
      Files: `agent/__init__.py`, `agent/config.py`
      Verify: `python -c "from agent.config import MODELS, RAG_BACKEND; print(MODELS)"` prints the dict.

- [ ] 3. Create `agent/rag/base.py` — abstract base class `RAGBackend`.
      Methods: `ingest(path: str) -> int` (returns doc count), `search(query: str, k: int = 6) -> list[str]`.
      Files: `agent/rag/__init__.py`, `agent/rag/base.py`
      Verify: `python -c "from agent.rag.base import RAGBackend"` succeeds.

- [ ] 4. Create `agent/rag/faiss_rag.py` — FAISS backend.
      Uses `sentence-transformers` (`all-MiniLM-L6-v2`) for embeddings; `faiss-cpu` for index.
      Index persisted at `.rag_index/faiss/` (configurable via `FAISS_INDEX_DIR`).
      Reuse the SHA-256 manifest pattern from `legacy/ragapi/ingest.py` for incremental ingest.
      `ingest(path)` walks the directory, chunks text (768 chars / 100 overlap), embeds, upserts into a `faiss.IndexFlatL2` saved with `faiss.write_index` + a companion JSON manifest.
      `search(query, k)` loads the saved index, encodes the query, returns top-k text chunks.
      Files: `agent/rag/faiss_rag.py`
      Verify: `python -c "from agent.rag.faiss_rag import FAISSBackend"` succeeds (deps must be installed).

- [ ] 5. Create `agent/rag/qdrant_rag.py` — Qdrant backend.
      Adapted from `legacy/ragapi/main.py` and `legacy/ragapi/ingest.py`.
      Uses `qdrant-client` + `llama-index-vector-stores-qdrant` + `llama-index-embeddings-ollama`.
      `ingest(path)` replicates the LlamaIndex `SentenceSplitter` + `VectorStoreIndex` pattern from `legacy/ragapi/ingest.py`.
      `search(query, k)` builds a query engine (same as `legacy/ragapi/main.py` `build_engine`) but returns raw text chunks (not an LLM-generated answer).
      Files: `agent/rag/qdrant_rag.py`
      Verify: `python -c "from agent.rag.qdrant_rag import QdrantBackend"` succeeds.

- [ ] 6. Create `agent/tools.py` — Strands `@tool`-decorated functions.
      Three tools:
      - `bash_exec(command: str) -> str`: runs command in subprocess with timeout (30s), returns stdout+stderr (truncated to 4000 chars). Security note in docstring: only runs what the user explicitly requests.
      - `file_read(path: str) -> str`: reads a file and returns content (max 50KB).
      - `rag_search(query: str) -> str`: instantiates the configured backend (from `agent/config.py`) and calls `search(query)`. Returns joined chunks.
      Import style follows the Strands `@tool` decorator pattern (`from strands import tool`).
      Files: `agent/tools.py`
      Verify: `python -c "from agent.tools import bash_exec, file_read, rag_search"` succeeds.

- [ ] 7. Create `agent/main.py` — CLI entry point (called by the `myagent` shell script).
      - Parses `--model` / `-m` flag (choices: `qwen`, `deepseek`, or a raw model name), `--rag` flag to enable RAG, `--ingest <dir>` to trigger ingest before starting chat, `--list-models` to print available models.
      - Instantiates `OllamaModel(host=OLLAMA_HOST, model_id=<resolved>, temperature=0.7)`.
      - Builds tool list: always `[bash_exec, file_read]`, plus `rag_search` if `--rag` or `RAG_BACKEND` env is set.
      - System prompt in Spanish (adapted from `legacy/agentsvc/main.py`): introduces the agent, lists tools, instructs to use `rag_search` for document questions.
      - Creates `Agent(model=ollama_model, system_prompt=SYSTEM_PROMPT, tools=tools)`.
      - Runs a `while True` input loop: reads a line, passes to `agent(line)`, prints response. `exit`/`quit` breaks.
      - `--ingest <dir>` instantiates the configured `RAGBackend` and calls `ingest(dir)` before starting the loop.
      Files: `agent/main.py`
      Verify: `python -m agent.main --list-models` prints the model table.

- [ ] 8. Create `myagent` shell script.
      Sets `PYTHONPATH` to the repo root, then execs `python -m agent.main "$@"`.
      `chmod +x myagent`.
      Example invocation line in script comments: `myagent -m qwen`, `myagent -m deepseek --rag --ingest ~/docs`.
      Files: `myagent`
      Verify: `./myagent --list-models` prints model table.

- [ ] 9. Create `requirements.txt` and `pyproject.toml`.
      `requirements.txt` (pinned versions):
      ```
      strands-agents[ollama]==0.2.1
      faiss-cpu==1.9.0
      sentence-transformers==3.3.1
      qdrant-client==1.11.1
      llama-index-core==0.11.23
      llama-index-llms-ollama==0.3.3
      llama-index-embeddings-ollama==0.3.0
      llama-index-vector-stores-qdrant==0.3.0
      python-dotenv==1.0.1
      ```
      `pyproject.toml`: minimal PEP 517 config pointing to requirements.txt, Python ≥ 3.11.
      Files: `requirements.txt`, `pyproject.toml`
      Verify: `pip install -r requirements.txt --dry-run` resolves without conflicts.

- [ ] 10. Create `scripts/install.sh` and `scripts/pull-models.sh`.
      `install.sh`: checks for Ollama, installs it via `curl -fsSL https://ollama.com/install.sh | sh` if missing, then runs `pip install -r requirements.txt`.
      `pull-models.sh`: runs `ollama pull qwen2.5-coder:14b` and `ollama pull deepseek-r1:32b` with progress output.
      Files: `scripts/install.sh`, `scripts/pull-models.sh`
      Verify: `bash -n scripts/install.sh && bash -n scripts/pull-models.sh` (syntax check only, no network).

- [ ] 11. Create `.env.example` and `docker-compose.yml`.
      `.env.example`: documents all env vars from `agent/config.py`.
      `docker-compose.yml`: two services, both with `profiles: [optional]`:
      - `qdrant`: reuse the working config from `legacy/docker-compose.yml` (same image, ports, healthcheck, volume).
      - `openwebui`: `ghcr.io/open-webui/open-webui:main`, port 3000, profile `optional`.
      Files: `.env.example`, `docker-compose.yml`
      Verify: `docker compose config` validates the file.

- [ ] 12. Write `README.md` (full rewrite).
      Sections:
      - Overview + architecture diagram (text-art)
      - Quick start (install + pull models + run)
      - Model selection table (qwen vs deepseek with use-case guidance)
      - **React loop frameworks comparison table** (Strands, LangChain/LangGraph, LlamaIndex, CrewAI, AutoGen) — columns: local-LLM support, tool calling, React loop, complexity, license
      - **RAG backends comparison table** (FAISS vs Qdrant) — columns: setup, persistence, server needed, best for
      - Flash Attention note (auto-enabled by Ollama; env vars to force/disable)
      - Optional services (Qdrant + OpenWebUI via docker compose profile)
      - Legacy note linking to `legacy/`
      Files: `README.md`
      Verify: `python -m markdown README.md > /dev/null` (requires `markdown` pip package; or just confirm the file renders in a browser).

---

## What to reuse verbatim / adapt

| Source | What | Destination |
|---|---|---|
| `legacy/agentsvc/main.py` `SYSTEM_PROMPT` | Spanish system prompt text | `agent/main.py` |
| `legacy/agentsvc/main.py` `search_rag` | Tool signature pattern | `agent/tools.py` `rag_search` |
| `legacy/ragapi/ingest.py` `sha256_file`, `load_manifest`, `save_manifest`, `iter_files` | Incremental ingest helpers | `agent/rag/faiss_rag.py` |
| `legacy/ragapi/main.py` `build_engine` | Qdrant query engine | `agent/rag/qdrant_rag.py` `search()` |
| `legacy/ragapi/ingest.py` `main()` ingest loop | LlamaIndex ingest pipeline | `agent/rag/qdrant_rag.py` `ingest()` |
| `legacy/docker-compose.yml` qdrant service | Qdrant service definition | `docker-compose.yml` |

## What NOT to carry forward

- `agentsvc` Dockerfile, `ragapi` Dockerfile, `qdrant.Dockerfile` — not needed (native install)
- LangChain dependency — replaced by Strands
- FastAPI + uvicorn — not needed for a CLI tool
- `scripts/install-docker.sh` — not needed (Ollama is native, Qdrant is optional)
- `agentsvc/requirements.txt`, `ragapi/requirements.txt` — replaced by top-level `requirements.txt`
