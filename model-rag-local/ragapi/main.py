import os
import subprocess
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from llama_index.core import Settings, VectorStoreIndex
from llama_index.embeddings.ollama import OllamaEmbedding
from llama_index.llms.ollama import Ollama
from llama_index.vector_stores.qdrant import QdrantVectorStore
from qdrant_client import QdrantClient

APP = FastAPI(title="Local RAG API", version="1.0.0")

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION = os.getenv("QDRANT_COLLECTION", "rag_documents")
OLLAMA_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")
TOP_K = int(os.getenv("TOP_K", "6"))


class QueryRequest(BaseModel):
    question: str
    top_k: int | None = None


def build_engine():
    Settings.embed_model = OllamaEmbedding(
        model_name=EMBEDDING_MODEL,
        base_url=OLLAMA_URL,
    )
    Settings.llm = Ollama(
        model=LLM_MODEL,
        base_url=OLLAMA_URL,
        request_timeout=120.0,
    )
    client = QdrantClient(url=QDRANT_URL)
    vector_store = QdrantVectorStore(client=client, collection_name=COLLECTION)
    index = VectorStoreIndex.from_vector_store(
        vector_store=vector_store,
        embed_model=Settings.embed_model,
    )
    return index.as_query_engine(
        similarity_top_k=TOP_K,
        response_mode="compact",
    )


@APP.get("/health")
def health():
    return {"status": "ok"}


@APP.post("/ingest")
def ingest():
    result = subprocess.run(
        ["/usr/local/bin/python", "/app/ingest.py"],
        capture_output=True,
        text=True,
        timeout=3600,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=500,
            detail={"stdout": result.stdout[-4000:], "stderr": result.stderr[-4000:]},
        )
    return {"status": "ok", "output": result.stdout[-8000:]}


@APP.post("/query")
def query(req: QueryRequest):
    try:
        engine = build_engine()
        response = engine.query(req.question)
        sources = []
        for node in getattr(response, "source_nodes", []) or []:
            sources.append({
                "score": node.score,
                "text": node.node.get_content()[:1000],
                "metadata": node.node.metadata,
            })
        return {"answer": str(response), "sources": sources}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
