"""Configuración central de myagent.

Lee variables de entorno (con python-dotenv) y expone constantes
usadas por el resto del paquete.
"""

import os

from dotenv import load_dotenv

# Carga .env si existe en el directorio de trabajo o en la raíz del proyecto
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"),
            override=False)

# ---------------------------------------------------------------------------
# Modelos disponibles
# ---------------------------------------------------------------------------
MODELS: dict[str, str] = {
    "qwen": "qwen2.5-coder:14b",
    "deepseek": "deepseek-r1:32b",
}

# ---------------------------------------------------------------------------
# Configuración de Ollama y modelo activo
# ---------------------------------------------------------------------------
OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MYAGENT_MODEL: str = os.getenv("MYAGENT_MODEL", MODELS["qwen"])

# ---------------------------------------------------------------------------
# Configuración RAG
# ---------------------------------------------------------------------------
RAG_BACKEND: str = os.getenv("RAG_BACKEND", "faiss")          # "faiss" | "qdrant"
RAG_DOCS_DIR: str = os.getenv("RAG_DOCS_DIR", "./docs")

# FAISS
FAISS_INDEX_DIR: str = os.getenv("FAISS_INDEX_DIR", ".rag_index/faiss")

# Qdrant
QDRANT_URL: str = os.getenv("QDRANT_URL", "http://localhost:6333")
QDRANT_COLLECTION: str = os.getenv("QDRANT_COLLECTION", "myagent_docs")

# Modelo de embeddings (debe estar disponible en Ollama o como modelo local)
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
