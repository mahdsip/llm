"""Backend RAG basado en Qdrant + LlamaIndex + Ollama embeddings.

Qdrant fue elegido sobre FAISS porque soporta upserts incrementales: solo
los documentos nuevos o modificados se re-ingresan. FAISS requiere
reconstruir el índice completo en cada cambio de documentos, lo que es
demasiado costoso para colecciones dinámicas.
"""

import hashlib
import json
import logging
from pathlib import Path

from llama_index.core import Settings, StorageContext, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.core.readers import SimpleDirectoryReader
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from agent.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    EMBEDDING_MODEL,
    MYAGENT_MODEL,
    OLLAMA_HOST,
    QDRANT_COLLECTION,
    QDRANT_URL,
    TOP_K,
)
from agent.rag.base import RAGBackend

log = logging.getLogger(__name__)

# Directorio donde se persiste el manifiesto SHA-256 — anclado a la raíz
# del proyecto para que el path sea correcto independientemente del
# directorio de trabajo desde el que se invoque myagent.
_MANIFEST_PATH = Path(__file__).parent.parent.parent / ".rag_index" / "qdrant_manifest.json"


# ---------------------------------------------------------------------------
# Helpers de manifiesto (patrón de legacy/ragapi/ingest.py)
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _load_manifest() -> dict:
    if not _MANIFEST_PATH.exists():
        return {}
    try:
        return json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_manifest(data: dict) -> None:
    _MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    _MANIFEST_PATH.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def _iter_files(root: Path):
    """Recorre recursivamente *root* ignorando directorios de sistema."""
    ignored = {".git", "__pycache__", ".rag_index"}
    for path in sorted(root.rglob("*")):
        if path.is_file() and not any(part in ignored for part in path.parts):
            yield path


# ---------------------------------------------------------------------------
# Backend
# ---------------------------------------------------------------------------

class QdrantBackend(RAGBackend):
    """Backend RAG basado en Qdrant + LlamaIndex + Ollama embeddings.

    Qdrant fue elegido sobre FAISS porque soporta upserts incrementales.
    FAISS requiere una reconstrucción completa del índice en cada cambio
    de documentos, lo que es demasiado costoso para colecciones dinámicas.
    """

    def __init__(
        self,
        qdrant_url: str = QDRANT_URL,
        collection: str = QDRANT_COLLECTION,
        ollama_host: str = OLLAMA_HOST,
        embedding_model: str = EMBEDDING_MODEL,
        llm_model: str = MYAGENT_MODEL,
    ) -> None:
        self.qdrant_url = qdrant_url
        self.collection = collection
        self.ollama_host = ollama_host
        self.embedding_model = embedding_model
        self.llm_model = llm_model

    def _configure_settings(self) -> None:
        """Configura LlamaIndex Settings con los modelos de Ollama."""
        Settings.embed_model = OllamaEmbedding(
            model_name=self.embedding_model,
            base_url=self.ollama_host,
            ollama_additional_kwargs={"keep_alive": "5m"},
        )
        Settings.llm = Ollama(
            model=self.llm_model,
            base_url=self.ollama_host,
            request_timeout=120.0,
        )

    def _client_and_store(self):
        """Retorna (QdrantClient, QdrantVectorStore, StorageContext)."""
        client = QdrantClient(url=self.qdrant_url)
        vector_store = QdrantVectorStore(
            client=client, collection_name=self.collection
        )
        storage_ctx = StorageContext.from_defaults(vector_store=vector_store)
        return client, vector_store, storage_ctx

    # ------------------------------------------------------------------
    # ingest
    # ------------------------------------------------------------------

    def ingest(self, path: str) -> int:
        """Indexa documentos en *path* de forma incremental.

        Solo procesa ficheros nuevos o modificados (verificado con SHA-256).
        Los documentos existentes sin cambios se saltan. Este comportamiento
        incremental es la razón principal para usar Qdrant en lugar de FAISS.

        Returns:
            Número de documentos efectivamente procesados.
        """
        self._configure_settings()
        _, _, storage_ctx = self._client_and_store()

        root = Path(path)
        if not root.exists():
            raise FileNotFoundError(f"La ruta no existe: {path}")

        files = [root] if root.is_file() else list(_iter_files(root))
        manifest = _load_manifest()
        splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

        processed = 0
        skipped = 0
        failed = 0

        for fpath in files:
            rel = str(fpath.relative_to(root.parent if root.is_file() else root))
            try:
                digest = _sha256_file(fpath)
                if manifest.get(rel, {}).get("sha256") == digest:
                    skipped += 1
                    continue

                reader = SimpleDirectoryReader(
                    input_files=[str(fpath)],
                    filename_as_id=True,
                    recursive=False,
                    raise_on_error=True,
                )
                documents = reader.load_data()
                for doc in documents:
                    doc.metadata.update(
                        {"source_path": rel, "file_name": fpath.name, "sha256": digest}
                    )
                    doc.id_ = f"file:{rel}"

                nodes = splitter.get_nodes_from_documents(documents)
                for i, node in enumerate(nodes):
                    node.metadata["source_path"] = rel
                    node.metadata["sha256"] = digest
                    node.id_ = f"{digest}:{i}"

                VectorStoreIndex(
                    nodes=nodes,
                    storage_context=storage_ctx,
                    show_progress=False,
                )
                manifest[rel] = {
                    "sha256": digest,
                    "size": fpath.stat().st_size,
                    "mtime": fpath.stat().st_mtime,
                }
                processed += 1
                log.info("Procesado: %s", rel)

            except Exception as exc:
                failed += 1
                log.exception("No se pudo procesar %s: %s", rel, exc)

        _save_manifest(manifest)
        log.info(
            "Ingestión completada — procesados=%d, sin cambios=%d, errores=%d",
            processed,
            skipped,
            failed,
        )
        return processed

    # ------------------------------------------------------------------
    # search
    # ------------------------------------------------------------------

    def search(self, query: str, k: int = TOP_K) -> list[str]:
        """Recupera los *k* fragmentos de texto más relevantes para *query*.

        Returns:
            Lista de cadenas de texto (fragmentos crudos, sin respuesta LLM).
        """
        self._configure_settings()
        _, vector_store, _ = self._client_and_store()

        index = VectorStoreIndex.from_vector_store(
            vector_store=vector_store,
            embed_model=Settings.embed_model,
        )
        retriever = index.as_retriever(similarity_top_k=k)
        nodes = retriever.retrieve(query)
        return [node.get_content() for node in nodes]
