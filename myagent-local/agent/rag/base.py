"""Clase base abstracta para backends RAG."""

from abc import ABC, abstractmethod


class RAGBackend(ABC):
    """Interfaz común para todos los backends de recuperación de documentos.

    El único backend implementado es Qdrant. FAISS fue descartado porque
    requiere reconstruir el índice completo en cada cambio de documentos;
    Qdrant soporta upserts incrementales, lo que lo hace adecuado para
    colecciones de documentos dinámicas.
    """

    @abstractmethod
    def ingest(self, path: str) -> int:
        """Indexa documentos en *path* (puede ser un fichero o directorio).

        Returns:
            Número de documentos procesados (los no modificados se saltan).
        """

    @abstractmethod
    def search(self, query: str, k: int = 6) -> list[str]:
        """Recupera los *k* fragmentos más relevantes para *query*.

        Returns:
            Lista de cadenas de texto (fragmentos), sin respuesta LLM.
        """
