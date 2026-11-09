"""Punto de entrada CLI de myagent.

Uso:
    myagent [--model/-m <modelo>] [--rag] [--ingest <directorio>] [--list-models] [--safe]

Ejemplos:
    myagent                          # usa el modelo por defecto (qwen)
    myagent -m deepseek              # cambia a DeepSeek-R1-32B
    myagent -m glm                   # cambia a GLM-4 9B
    myagent -m qwen --rag            # activa búsqueda en documentos locales
    myagent --ingest ~/docs --rag    # indexa ~/docs y activa RAG
    myagent --safe -m qwen           # pide confirmación antes de cada bash_exec
    myagent --list-models            # muestra modelos disponibles
"""

import argparse
import sys

from rich.console import Console
from rich.table import Table

from agent.config import MODELS, MYAGENT_MODEL, OLLAMA_HOST

console = Console()

SYSTEM_PROMPT = """Eres el asistente local del usuario, especializado en programación y tareas técnicas.

Tienes acceso a las siguientes herramientas:
- **bash_exec**: ejecuta comandos de shell en la máquina del usuario. En modo --safe pide confirmación antes de ejecutar.
- **file_read**: lee el contenido de ficheros locales (hasta 50 KB).
- **file_write**: crea o sobreescribe ficheros. Úsalo solo cuando el usuario pida explícitamente crear o modificar un fichero.
- **list_dir**: lista el contenido de un directorio mostrando tipo, tamaño y nombre de cada entrada.
- **rag_search** (disponible solo si se activó --rag): busca en la colección de documentos locales indexados. Úsala cuando la pregunta pueda estar respondida por los documentos del usuario.

Directrices:
- Usa bash_exec para comprobar el entorno, ejecutar código o resolver dudas sobre el sistema.
- Usa file_read para inspeccionar ficheros concretos cuando el usuario lo solicite.
- Usa file_write para crear o modificar ficheros cuando el usuario lo pida explícitamente; no lo uses de forma proactiva.
- Usa list_dir para explorar la estructura de directorios cuando necesites orientarte en el sistema de ficheros.
- Usa rag_search antes de responder preguntas que puedan depender de documentos locales.
- No inventes información que no esté respaldada por el contexto recuperado o por conocimiento real.
- Si una herramienta no encuentra información suficiente, dilo claramente.
- Responde en español salvo que el usuario pida otro idioma.
- Sé conciso y técnico. Prefiere ejemplos de código sobre explicaciones largas."""


def _resolve_model(model_arg: str | None) -> str:
    """Resuelve alias de modelo ('qwen', 'deepseek') o acepta el nombre completo."""
    if model_arg is None:
        return MYAGENT_MODEL
    return MODELS.get(model_arg, model_arg)


def _print_models() -> None:
    """Imprime la tabla de modelos disponibles."""
    table = Table(title="Modelos disponibles", show_lines=True)
    table.add_column("Alias", style="cyan", no_wrap=True)
    table.add_column("Modelo Ollama", style="green")
    table.add_column("Descripción")

    table.add_row(
        "qwen",
        "qwen2.5-coder:14b",
        "Qwen 2.5 Coder 14B — optimizado para código, 14B parámetros",
    )
    table.add_row(
        "deepseek",
        "deepseek-r1:32b",
        "DeepSeek-R1 32B — razonamiento avanzado con cadenas <think>, 32B parámetros",
    )
    table.add_row(
        "glm",
        "glm4:9b",
        "GLM-4 9B — modelo chino/inglés denso, buen rendimiento en código, ~6 GB VRAM",
    )
    table.add_row(
        "glm-flash",
        "glm-4.7-flash",
        "GLM-4.7 Flash — MoE 30B-A3B (3B activos), requiere ~16 GB VRAM",
    )
    console.print(table)
    console.print(
        "\n[dim]Puedes usar también cualquier nombre de modelo Ollama directamente con -m.[/dim]"
    )


def _build_parser() -> argparse.ArgumentParser:
    description = """myagent — Agente LLM local en terminal (Strands + Ollama)

Modelos disponibles:
  qwen       qwen2.5-coder:14b    Código y scripting (14B, ~10 GB VRAM)
  deepseek   deepseek-r1:32b      Razonamiento complejo (32B, ~20 GB VRAM)
  glm        glm4:9b              General + código (9B, ~6 GB VRAM)
  glm-flash  glm-4.7-flash        MoE 30B-A3B, alta calidad (~16 GB VRAM)

Herramientas disponibles en el agente:
  bash_exec   Ejecuta comandos de shell
  file_read   Lee ficheros (hasta 50 KB)
  file_write  Crea o sobreescribe ficheros
  list_dir    Lista el contenido de un directorio
  rag_search  Búsqueda semántica en documentos (solo con --rag)

Ejemplos:
  myagent                                    Inicia con modelo por defecto (qwen)
  myagent -m deepseek                        Usa DeepSeek-R1 32B
  myagent -m glm                             Usa GLM-4 9B
  myagent --rag                              Activa búsqueda en documentos
  myagent --ingest ~/docs -m qwen --rag      Indexa ~/docs y activa RAG
  myagent --safe -m qwen                     Pide confirmación antes de cada comando
  myagent --list-models                      Muestra modelos y sale

Nota --safe:
  En modo seguro, cada llamada a bash_exec muestra el comando y espera
  confirmación [s/N] antes de ejecutarlo. Recomendado cuando trabajas en
  directorios importantes o ejecutas tareas de alto impacto.

Nota RAG:
  RAG requiere Qdrant corriendo (docker compose --profile optional up qdrant)
  y el modelo de embeddings nomic-embed-text (ollama pull nomic-embed-text).
  Usa --ingest <directorio> para indexar documentos antes del chat."""

    parser = argparse.ArgumentParser(
        prog="myagent",
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-m",
        "--model",
        metavar="MODELO",
        default=None,
        help='Alias de modelo ("qwen", "deepseek", "glm", "glm-flash") o nombre completo de Ollama.',
    )
    parser.add_argument(
        "--rag",
        action="store_true",
        default=False,
        help="Activa la herramienta rag_search (requiere Qdrant).",
    )
    parser.add_argument(
        "--ingest",
        metavar="DIRECTORIO",
        default=None,
        help="Indexa el directorio en Qdrant antes de iniciar el chat.",
    )
    parser.add_argument(
        "--list-models",
        action="store_true",
        default=False,
        help="Muestra los modelos disponibles y sale.",
    )
    parser.add_argument(
        "--safe",
        action="store_true",
        default=False,
        help=(
            "Modo seguro: pide confirmación [s/N] antes de ejecutar cada comando "
            "con bash_exec. Recomendado cuando trabajas en directorios importantes."
        ),
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_models:
        _print_models()
        sys.exit(0)

    # Importaciones diferidas para agilizar --list-models y arranques rápidos
    from strands import Agent
    from strands.models.ollama import OllamaModel

    from agent.tools import bash_exec, file_read, file_write, list_dir

    model_id = _resolve_model(args.model)

    # --ingest: indexar documentos antes del chat
    if args.ingest:
        from agent.rag.qdrant_rag import QdrantBackend

        console.print(f"[bold yellow]Indexando documentos en:[/bold yellow] {args.ingest}")
        with console.status("[bold green]Indexando…[/bold green]"):
            backend = QdrantBackend()
            count = backend.ingest(args.ingest)
        console.print(f"[bold green]✓[/bold green] Indexados {count} documento(s).")
        # --ingest implica --rag para el chat posterior
        args.rag = True

    # Herramientas disponibles
    tools: list = [bash_exec, file_read, file_write, list_dir]

    if args.safe:
        from strands import tool as strands_tool

        @strands_tool
        def bash_exec(command: str) -> str:  # noqa: F811
            """Ejecuta un comando de shell (con confirmación previa en modo --safe).

            Args:
                command: Comando a ejecutar.

            Returns:
                Stdout y stderr combinados (máx. 4000 caracteres).
            """
            console.print(f"[yellow]⚠ bash_exec:[/yellow] {command}")
            answer = console.input("[bold]¿Ejecutar? [s/N]:[/bold] ").strip().lower()
            if answer not in {"s", "si", "sí", "y", "yes"}:
                return "[Cancelado por el usuario]"
            from agent.tools import bash_exec as _real_bash_exec
            return _real_bash_exec(command)
        tools[0] = bash_exec  # reemplaza el bash_exec importado

    if args.rag:
        from agent.tools import rag_search
        tools.append(rag_search)

    ollama_model = OllamaModel(
        host=OLLAMA_HOST,
        model_id=model_id,
        temperature=0.7,
    )

    agent = Agent(
        model=ollama_model,
        system_prompt=SYSTEM_PROMPT,
        tools=tools,
    )

    console.print(
        f"[bold cyan]myagent[/bold cyan] — modelo: [green]{model_id}[/green]"
        + (" | [yellow]RAG activo[/yellow]" if args.rag else "")
    )
    console.print("[dim]Escribe tu mensaje. 'exit' o 'quit' para salir.[/dim]\n")

    while True:
        try:
            user_input = console.input("[bold blue]Tú:[/bold blue] ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Hasta luego.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "salir"}:
            console.print("[dim]Hasta luego.[/dim]")
            break

        with console.status("[bold green]Pensando…[/bold green]"):
            response = agent(user_input)

        console.print(f"\n[bold green]Agente:[/bold green] {response}\n")


if __name__ == "__main__":
    main()
