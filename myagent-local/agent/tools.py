"""Herramientas Strands disponibles para el agente.

Todas las funciones están decoradas con @tool y siguen el contrato
de Strands Agents SDK.
"""

import subprocess
from pathlib import Path

from strands import tool

from agent.config import EMBEDDING_MODEL, OLLAMA_HOST, QDRANT_COLLECTION, QDRANT_URL

# Límite de salida para bash_exec (caracteres)
_BASH_MAX_CHARS = 4000
# Límite de lectura para file_read (bytes)
_FILE_MAX_BYTES = 50 * 1024  # 50 KB
# Timeout de ejecución para bash_exec (segundos)
_BASH_TIMEOUT = 30


@tool
def bash_exec(command: str) -> str:
    """Ejecuta un comando de shell y devuelve stdout+stderr.

    Solo ejecuta lo que el usuario pide explícitamente.
    La salida se trunca a 4000 caracteres.

    Args:
        command: Comando de shell a ejecutar.

    Returns:
        Salida combinada de stdout y stderr (truncada si es necesario).
    """
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=_BASH_TIMEOUT,
        )
        output = result.stdout + result.stderr
        if len(output) > _BASH_MAX_CHARS:
            output = output[:_BASH_MAX_CHARS] + "\n… [salida truncada]"
        return output
    except subprocess.TimeoutExpired:
        return f"[Error] El comando superó el tiempo límite de {_BASH_TIMEOUT}s."
    except Exception as exc:
        return f"[Error] {exc}"


@tool
def file_read(path: str) -> str:
    """Lee el contenido de un fichero (máximo 50 KB).

    Args:
        path: Ruta al fichero a leer.

    Returns:
        Contenido del fichero como cadena de texto.
    """
    try:
        fpath = Path(path)
        if not fpath.exists():
            return f"[Error] El fichero no existe: {path}"
        if not fpath.is_file():
            return f"[Error] La ruta no es un fichero: {path}"

        raw = fpath.read_bytes()
        if len(raw) > _FILE_MAX_BYTES:
            raw = raw[:_FILE_MAX_BYTES]
            return raw.decode("utf-8", errors="replace") + "\n… [fichero truncado a 50 KB]"
        return raw.decode("utf-8", errors="replace")
    except Exception as exc:
        return f"[Error] {exc}"


@tool
def file_write(path: str, content: str) -> str:
    """Escribe o sobreescribe el contenido completo de un fichero.

    Crea el fichero y los directorios padre si no existen.
    ADVERTENCIA: sobreescribe sin confirmación. Úsalo solo cuando el usuario
    haya pedido explícitamente crear o modificar un fichero.

    Args:
        path: Ruta al fichero (absoluta o relativa al directorio actual).
        content: Contenido completo a escribir en el fichero.

    Returns:
        Mensaje de confirmación con ruta absoluta y número de caracteres escritos,
        o descripción del error si falla.
    """
    try:
        fpath = Path(path).resolve()
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return f"Fichero escrito: {fpath} ({len(content)} caracteres)"
    except Exception as exc:
        return f"[Error] {exc}"


@tool
def list_dir(path: str = ".") -> str:
    """Lista el contenido de un directorio mostrando tipo, tamaño y nombre.

    Args:
        path: Ruta del directorio a listar. Por defecto el directorio actual.

    Returns:
        Listado de entradas con [d] para directorios y [f] para ficheros,
        tamaño en bytes para ficheros, o error si la ruta no existe.
    """
    try:
        dpath = Path(path).resolve()
        if not dpath.exists():
            return f"[Error] La ruta no existe: {path}"
        if not dpath.is_dir():
            return f"[Error] La ruta no es un directorio: {path}"
        entries = sorted(dpath.iterdir(), key=lambda p: (p.is_file(), p.name))
        if not entries:
            return f"El directorio está vacío: {dpath}"
        lines = [f"Directorio: {dpath}", ""]
        for entry in entries:
            if entry.is_dir():
                lines.append(f"  [d]  {entry.name}/")
            else:
                size = entry.stat().st_size
                lines.append(f"  [f]  {size:>10} B  {entry.name}")
        return "\n".join(lines)
    except Exception as exc:
        return f"[Error] {exc}"


@tool
def rag_search(query: str) -> str:
    """Busca en la colección de documentos locales indexados en Qdrant.

    Utiliza esta herramienta cuando la pregunta pueda responderse con
    información de los documentos del usuario. Devuelve fragmentos de
    texto relevantes (no una respuesta generada por LLM).

    Args:
        query: Pregunta o términos de búsqueda.

    Returns:
        Fragmentos de texto relevantes separados por líneas de separación.
    """
    # Importación local para evitar carga del cliente Qdrant en arranques
    # sin --rag
    from agent.rag.qdrant_rag import QdrantBackend

    backend = QdrantBackend(
        qdrant_url=QDRANT_URL,
        collection=QDRANT_COLLECTION,
        ollama_host=OLLAMA_HOST,
        embedding_model=EMBEDDING_MODEL,
    )
    chunks = backend.search(query)
    if not chunks:
        return "No se encontraron documentos relevantes para la consulta."
    return "\n\n---\n\n".join(chunks)
