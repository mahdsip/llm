import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Iterable

from llama_index.core import Document, Settings, SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

from gpx_reader import read_gpx

DOCS_DIR = Path(os.getenv("DOCS_DIR", "/data/docs"))
STATE_DIR = Path(os.getenv("STATE_DIR", "/data/state"))
MANIFEST = STATE_DIR / "manifest.json"
ERROR_LOG = STATE_DIR / "ingest_errors.log"
COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_documents")
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "768"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "100"))

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper()),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(ERROR_LOG, encoding="utf-8")],
)
log = logging.getLogger("rag-ingest")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    try:
        return json.loads(MANIFEST.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_manifest(data: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def configure_models() -> None:
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBEDDING_MODEL,
        base_url=OLLAMA_URL,
        ollama_additional_kwargs={"keep_alive": "5m"},
    )
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_URL,
        request_timeout=120.0,
    )


def iter_files() -> Iterable[Path]:
    ignored = {".git", "__pycache__"}
    for path in sorted(DOCS_DIR.rglob("*")):
        if path.is_file() and not any(part in ignored for part in path.parts):
            yield path


def load_one(path: Path) -> list[Document]:
    if path.suffix.lower() == ".gpx":
        return [read_gpx(path)]

    # LlamaIndex's file readers handle PDF/DOCX/PPTX/XLSX/TXT/MD, etc.
    reader = SimpleDirectoryReader(
        input_files=[str(path)],
        filename_as_id=True,
        recursive=False,
        raise_on_error=True,
    )
    return reader.load_data()


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    configure_models()

    client = QdrantClient(url=QDRANT_URL)
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    manifest = load_manifest()
    processed = 0
    skipped = 0
    failed = 0

    # We use the manifest to avoid re-reading unchanged files.
    # The collection itself is persistent in Qdrant.
    splitter = SentenceSplitter(chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP)

    for path in iter_files():
        rel = str(path.relative_to(DOCS_DIR))
        try:
            digest = sha256_file(path)
            previous = manifest.get(rel)
            if previous and previous.get("sha256") == digest:
                skipped += 1
                continue

            documents = load_one(path)
            for doc in documents:
                doc.metadata.update({
                    "source_path": rel,
                    "file_name": path.name,
                    "sha256": digest,
                })
                doc.id_ = f"file:{rel}"

            # Build nodes and insert into the persistent Qdrant collection.
            nodes = splitter.get_nodes_from_documents(documents)
            for i, node in enumerate(nodes):
                node.metadata["source_path"] = rel
                node.metadata["sha256"] = digest
                node.id_ = f"{digest}:{i}"

            VectorStoreIndex(
                nodes=nodes,
                storage_context=storage_context,
                show_progress=False,
            )
            manifest[rel] = {
                "sha256": digest,
                "size": path.stat().st_size,
                "mtime": path.stat().st_mtime,
            }
            processed += 1
            log.info("Procesado: %s", rel)

        except Exception as exc:
            failed += 1
            log.exception("No se pudo procesar %s: %s", rel, exc)

    save_manifest(manifest)
    log.info(
        "FIN ingestión: procesados=%d, sin cambios=%d, errores=%d",
        processed, skipped, failed
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
