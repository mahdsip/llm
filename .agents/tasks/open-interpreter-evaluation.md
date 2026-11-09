# Evaluación: Open Interpreter y GLM para el stack local existente

**Fecha:** julio 2025  
**Autor:** Agente de investigación  
**Estado:** READ-ONLY — ningún cambio aplicado al repositorio

---

## Resumen ejecutivo

**Recomendación: Opción C — extender `myagent` directamente.**

El stack (`strands-agents` + Ollama + Qdrant) ya tiene las piezas fundamentales en su sitio. Añadir tres tools nuevas (`file_write`, `list_dir`, `confirm_exec`) en `agent/tools.py` y registrar el alias GLM en `config.py` entrega las mismas capacidades de Open Interpreter en 1-2 horas de trabajo, sin introducir una segunda herramienta competidora, sin conflictos de entorno y con total integración en el React loop existente.

---

## 1. Open Interpreter versión Rust (oficial)

**Repositorio:** [openinterpreter/openinterpreter](https://github.com/OpenInterpreter/open-interpreter)

La versión actual (2025) es una **reimplementación completa en Rust** basada en el Codex CLI de OpenAI, no es continuación del Python original. El README la describe explícitamente como "a fork of OpenAI's Codex".

### 1.1 Soporte Ollama

- Ollama está soportado como **proveedor nativo de primer nivel** ("Built-In Runtime Provider", junto con OpenAI y Amazon Bedrock). ID de proveedor: `ollama`. Wire API: `responses` (OpenAI Responses API).
- Para modelos que no tienen harness específico se puede usar `--chat-completions` para forzar el Chat Completions path, compatible con cualquier modelo servido por Ollama.
- Configuración típica: lanzar `interpreter`, seleccionar `/model` → ollama → modelo deseado. No requiere API key.

### 1.2 Compatibilidad con GLM vía Ollama

- Open Interpreter tiene **providers dedicados** para GLM en la nube (Z.AI/Zhipu): `zai`, `zai-coding-plan`, `zai-zcode`, `zhipuai`. Estos requieren `ZAI_API_KEY` o `ZHIPU_API_KEY` y apuntan a endpoints remotos.
- Para GLM **local vía Ollama** (el caso de interés), se puede seleccionar el provider `ollama` y apuntar al modelo `glm4:9b` o `glm-4.7-flash` exactamente igual que cualquier otro modelo. No hay harness especializado para GLM+Ollama, pero funciona con `--chat-completions` o `wire_api = "chat"`.

### 1.3 Integración con el proyecto Python (Strands)

- **Son herramientas complementarias pero completamente independientes.** Open Interpreter Rust es un binario standalone (`interpreter`), no una librería Python importable.
- No interfiere con el virtualenv, los paquetes Python ni Ollama.
- **No hay integración directa**: para invocar Open Interpreter desde `myagent` habría que lanzar un subproceso. Esto sería una integración frágil y poco natural para el React loop de Strands.
- Son concurrentes en el acceso a Ollama, no en conflicto: Ollama admite múltiples clientes simultáneos.

### 1.4 Acceso al sistema de archivos en Linux

- Sí: acceso completo con varios modos de sandbox configurables.
  - `read-only` — solo lectura de archivos permitidos.
  - `workspace-write` — escritura dentro de los roots activos.
  - `danger-full-access` — sin límite de sandbox.
- Enforcement en Linux mediante **Bubblewrap, seccomp y kernel sandboxing**.
- Política de aprobación configurable: `untrusted` (pide confirmación), `on-request`, `never`.
- Comandos pueden **leer, crear, actualizar, renombrar y borrar archivos**.

### 1.5 Coexistencia con myagent

- Sin conflictos: `interpreter` es un binario separado en `PATH`.
- Ambos usan Ollama como backend; no compiten.
- La única fricción es que son **dos herramientas de terminal distintas** con flujos de trabajo separados, sin contexto compartido.

### 1.6 Issues conocidos con Ollama (Rust)

- Hay issues reportados ([#1865](https://github.com/openinterpreter/openinterpreter/issues/1865), [#1633](https://github.com/openinterpreter/openinterpreter/issues/1633)) donde Ollama genera tool calls que Open Interpreter no ejecuta correctamente. El proveedor `ollama` usa `wire_api = "responses"` (Responses API), pero modelos locales no siempre devuelven el formato esperado.
- Instalación en Ubuntu reportó problemas recientes ([#1689](https://github.com/openinterpreter/openinterpreter/issues/1689)).

---

## 2. Open Interpreter versión Python legacy (endolith/open-interpreter)

**Repositorio:** [endolith/open-interpreter](https://github.com/endolith/open-interpreter)

Fork comunitario mantenido por endolith. En su propio README se describe como "a vibe-coded mess" y está 8068 commits por detrás del original principal actual (Rust). Es la continuación del Python original de 2023-2024.

### 2.1 Soporte Ollama

- El Python original siempre soportó Ollama vía LiteLLM. El fork endolith hereda esto.
- Configuración: `interpreter --model ollama/qwen2.5-coder:14b`. LiteLLM actúa como capa de abstracción.
- **Problemas documentados:** múltiples issues reportan fallos con modelos locales + Ollama en versiones recientes del Python original ([#1086](https://github.com/openinterpreter/openinterpreter/issues/1086), [#1169](https://github.com/openinterpreter/openinterpreter/issues/1169), [#1371](https://github.com/OpenInterpreter/open-interpreter/issues/1371)). La integración es inconsistente con modelos que no son OpenAI-native.

### 2.2 Acceso al sistema de archivos

- Sí, ejecuta Python y bash localmente. Acceso completo a FS (sin sandbox por defecto en el Python original, pide confirmación si está en modo seguro).

### 2.3 Compatibilidad con el stack actual

- **Conflicto de dependencias potencial:** instala `litellm` y una versión específica de `openai` que puede chocar con `strands-agents[ollama]` en el mismo virtualenv.
- Si se instala en un venv separado, no hay conflicto técnico, pero tampoco hay integración.
- El mantenimiento del fork endolith es limitado y el proyecto Python original fue **abandonado oficialmente** en favor de la versión Rust.

---

## 3. Extender myagent directamente

### 3.1 Qué tiene ya el proyecto

Leyendo `agent/tools.py` directamente:

| Tool actual | Funcionalidad |
|---|---|
| `bash_exec(command)` | Ejecuta comandos de shell; stdout+stderr, timeout 30s, truncado a 4000 chars |
| `file_read(path)` | Lee ficheros hasta 50 KB |
| `rag_search(query)` | Búsqueda semántica en Qdrant |

El `SYSTEM_PROMPT` en `main.py` ya instruye al modelo a usar `bash_exec` para ejecutar código y explorar el entorno.

### 3.2 Qué le falta para igualar a Open Interpreter

| Capacidad | Open Interpreter | myagent actual | Trabajo necesario |
|---|---|---|---|
| Leer ficheros | ✅ | ✅ `file_read` | — |
| Ejecutar comandos bash | ✅ | ✅ `bash_exec` | — |
| Escribir/crear ficheros | ✅ | ❌ | `file_write` tool |
| Listar directorios | ✅ | Parcial (vía `bash_exec ls`) | `list_dir` tool opcional |
| Confirmación antes de ejecutar | ✅ (configurable) | ❌ | Wrapper `confirm_exec` o flag `--safe` |
| Editar ficheros (patch/diff) | ✅ | ❌ | `file_patch` tool opcional |
| Soporte múltiples lenguajes | Python, JS, Shell | Shell (bash) | `python_exec` tool opcional |

**Lo esencial que falta son 2-3 tools:**

1. **`file_write(path, content)`** — escribe o sobreescribe un fichero completo. ~15 líneas.
2. **`list_dir(path)`** — devuelve listado de un directorio con metadatos básicos (tipo, tamaño). ~20 líneas. (Alternativa: `bash_exec("ls -la /ruta")` ya funciona.)
3. **`confirm_exec(command)`** — wraper de `bash_exec` que antes de ejecutar muestra el comando y pide confirmación por consola si el comando es destructivo. ~30 líneas. Esto es lo que diferencia la experiencia de Open Interpreter: el modelo puede ejecutar código pero el usuario aprueba lo peligroso.

### 3.3 Estimación de esfuerzo

| Tarea | Ficheros | Tiempo estimado |
|---|---|---|
| Añadir `file_write` a `tools.py` | `agent/tools.py` | 20 min |
| Añadir `list_dir` a `tools.py` | `agent/tools.py` | 15 min |
| Añadir `confirm_exec` a `tools.py` | `agent/tools.py` | 30 min |
| Registrar tools en `main.py` y actualizar `SYSTEM_PROMPT` | `agent/main.py` | 15 min |
| Añadir flag `--safe` que activa confirmaciones | `agent/main.py` | 20 min |
| Tests básicos | `tests/` | 30 min |
| **Total** | | **~2 horas** |

---

## 4. GLM en Ollama

### 4.1 Nombres exactos en el repositorio Ollama

| Modelo | Nombre en Ollama | Descripción |
|---|---|---|
| GLM-4 9B | `glm4:9b` | Modelo denso 9B, multilingual, competitive con Llama 3 8B |
| GLM-4.7 Flash | `glm-4.7-flash` | MoE 30B-A3B (solo 3B activos por token), "30B quality at 3B speed" |

Nota: `glm-4.7-flash` es un modelo MoE de 30B parámetros totales pero con solo ~3B activos por inferencia (Mixture-of-Experts). Pese al nombre "Flash", **no es un modelo pequeño** en disco.

### 4.2 Requisitos de VRAM

| Modelo | VRAM mínima | VRAM recomendada | Notas |
|---|---|---|---|
| `glm4:9b` | ~6 GB (Q4) | ~8 GB | Denso 9B; Q4_K_M ≈ 6 GB según regla 0.6 GB/B |
| `glm-4.7-flash` | ~16 GB (Q4 cuantizado) | 24 GB | MoE 30B-A3B; pesos completos ≈ 20-25 GB, Q4 ≈ 16 GB |

Fuentes: [Unsloth GLM-4.7-Flash guide](https://unsloth.ai/docs/models/glm-4.7-flash), [WaveSpeed guide](https://wavespeed.ai/blog/posts/glm-4-7-flash-local/), [DataCamp tutorial](https://www.datacamp.com/tutorial/using-claude-code-with-ollama-local-models).

### 4.3 ¿Cuál es mejor para scripting en Linux?

**Para scripting bash/python en Linux: `glm4:9b` si VRAM < 12 GB, `glm-4.7-flash` si hay 16+ GB.**

- `glm4:9b` es un modelo denso bien afinado para código, con rendimiento comparable a Llama 3 8B. Cabe cómodamente en GPUs de 8 GB.
- `glm-4.7-flash` tiene métricas de coding superiores (benchmark 30B-class) con el coste de inferencia de un modelo 3B. Requiere 16 GB de VRAM mínimo para el cuantizado Q4 comunitario.
- Para el stack actual que ya corre `qwen2.5-coder:14b` (necesita ~10 GB) y `deepseek-r1:32b` (necesita ~20 GB), **`glm4:9b` es el complemento más sensato** si la GPU tiene 8-12 GB libres, ya que es el modelo GLM más ligero disponible en Ollama por defecto.

---

## 5. Tabla comparativa de opciones

| Criterio | A: OI Rust + Ollama | B: OI Python (endolith) | C: Extender myagent | D: Otra (aio-cli, etc.) |
|---|---|---|---|---|
| Integración con Strands | Ninguna (binario independiente) | Ninguna | Total (mismo loop) | — |
| Soporte Ollama | ✅ Nativo (builtin provider) | ⚠️ Via LiteLLM (issues conocidos) | ✅ Ya funciona | — |
| Acceso FS Linux | ✅ (con sandbox/aprobación) | ✅ (sin sandbox por defecto) | ✅ tras añadir tools | — |
| GLM vía Ollama | ✅ (provider ollama) | ✅ (litellm) | ✅ (alias en config.py) | — |
| Coexistencia con myagent | ✅ (sin conflictos técnicos) | ⚠️ (conflicto deps venv) | ✅ (es la misma herramienta) | — |
| Esfuerzo de puesta en marcha | 30 min (instalar + configurar) | 45 min + resolver conflictos | ~2 horas (implementar tools) | — |
| Mantenimiento futuro | Bajo (binario autónomo) | Alto (fork no mantenido) | Bajo (mismo proyecto) | — |
| Context compartido con RAG | ❌ | ❌ | ✅ (--rag ya funciona) | — |
| Confirmación antes de ejecutar | ✅ (configurable) | ✅ (modo seguro) | Con `confirm_exec` | — |
| Calidad con modelos locales | ⚠️ (issues con Ollama tool calls) | ⚠️ (issues con Ollama local) | ✅ (battle-tested) | — |
| Riesgo de romper el stack | Ninguno | ⚠️ (conflicto deps) | Bajo (cambios aditivos) | — |

---

## 6. Recomendación final

### Opción C: extender myagent

**Justificación:**

1. **El stack ya funciona.** Strands + Ollama + Qdrant está operativo. La experiencia de "agente en terminal con acceso al sistema de archivos" ya existe parcialmente: `bash_exec` ejecuta comandos y `file_read` lee ficheros. Solo faltan las piezas de escritura y confirmación.

2. **Contexto compartido.** Open Interpreter (ambas versiones) no tiene acceso al índice Qdrant ni al historial de `myagent`. Extender `myagent` mantiene el contexto unificado: el agente puede buscar en documentos (`rag_search`), leer un fichero (`file_read`), modificarlo (`file_write`) y ejecutar comandos (`bash_exec`) en la misma sesión.

3. **Issues conocidos de OI con Ollama local.** El proveedor `ollama` de Open Interpreter Rust usa `wire_api = "responses"` (Responses API), que modelos locales no implementan completamente. Issues [#1865](https://github.com/openinterpreter/openinterpreter/issues/1865) y [#1633](https://github.com/openinterpreter/openinterpreter/issues/1633) muestran que los tool calls generados por Ollama no se ejecutan correctamente en la versión actual. La integración `--chat-completions` es más estable pero pierde algunos harness.

4. **Open Interpreter Rust como complemento opcional.** Nada impide instalar `interpreter` para sesiones independientes (por ejemplo, para proyectos fuera del stack RAG). Puede coexistir sin conflictos.

5. **GLM es trivial de añadir.** Un alias en `config.py` es suficiente.

---

## 7. Plan de implementación (Opción C)

### 7.1 Tools a añadir en `agent/tools.py`

```python
@tool
def file_write(path: str, content: str) -> str:
    """Escribe o sobreescribe el contenido de un fichero.
    
    Crea el fichero y los directorios padre si no existen.
    Úsalo solo cuando el usuario haya pedido explícitamente crear o modificar un fichero.

    Args:
        path: Ruta al fichero.
        content: Contenido a escribir.

    Returns:
        Mensaje de confirmación o error.
    """
    try:
        fpath = Path(path).expanduser().resolve()
        fpath.parent.mkdir(parents=True, exist_ok=True)
        fpath.write_text(content, encoding="utf-8")
        return f"Fichero escrito: {fpath} ({len(content)} caracteres)"
    except Exception as exc:
        return f"[Error] {exc}"


@tool
def list_dir(path: str = ".") -> str:
    """Lista el contenido de un directorio con tipo y tamaño.

    Args:
        path: Ruta del directorio a listar (por defecto, directorio actual).

    Returns:
        Listado de entradas con tipo (d/f), tamaño y nombre.
    """
    try:
        dpath = Path(path).expanduser().resolve()
        if not dpath.is_dir():
            return f"[Error] No es un directorio: {path}"
        lines = []
        for entry in sorted(dpath.iterdir(), key=lambda e: (e.is_file(), e.name)):
            kind = "f" if entry.is_file() else "d"
            size = entry.stat().st_size if entry.is_file() else "-"
            lines.append(f"[{kind}] {entry.name}  ({size} bytes)")
        return "\n".join(lines) if lines else "(directorio vacío)"
    except Exception as exc:
        return f"[Error] {exc}"
```

### 7.2 Cambios en `agent/main.py`

- Añadir `file_write` y `list_dir` a la lista `tools` en `main()`.
- Actualizar `SYSTEM_PROMPT` para mencionar las nuevas tools.
- Añadir flag `--safe` que, cuando está activo, muestra una confirmación antes de cada llamada a `bash_exec` (implementable con un wrapper que imprima el comando y pida `[s/N]` antes de ejecutarlo).

### 7.3 GLM en `agent/config.py`

```python
MODELS: dict[str, str] = {
    "qwen": "qwen2.5-coder:14b",
    "deepseek": "deepseek-r1:32b",
    "glm": "glm4:9b",           # denso 9B, ~6 GB VRAM (Q4)
    # "glm-flash": "glm-4.7-flash",  # MoE 30B-A3B, requiere ~16 GB VRAM
}
```

Usar `glm4:9b` como alias `glm` por defecto ya que encaja mejor con GPUs de 8-12 GB. El alias `glm-flash` puede añadirse opcionalmente para hardware con 16+ GB.

### 7.4 Actualizar `_print_models()` en `main.py`

Añadir fila GLM a la tabla de `--list-models`.

---

## 8. Si aun así se quiere Open Interpreter Rust como herramienta adicional

Instalación y configuración con Ollama (complementaria, no sustituta):

```bash
# Instalación
curl -fsSL https://www.openinterpreter.com/install | sh

# Usar Ollama como proveedor
interpreter
# En el TUI: /model → ollama → glm4:9b (o cualquier modelo descargado)

# O directamente con chat-completions (más estable con Ollama):
interpreter --chat-completions
```

Configuración persistente en `~/.openinterpreter/config.toml`:
```toml
model_provider = "ollama"
model = "glm4:9b"
sandbox_mode = "workspace-write"
approval_policy = "on-request"
```

Para GLM vía API Z.AI (nube, requiere cuenta):
```bash
export ZAI_API_KEY="..."
interpreter -c 'model_provider="zai"' -m glm-4.7-flash
```

> **Nota:** Para GLM local vía Ollama el provider correcto es `ollama`, no `zai`. El provider `zai` apunta a los endpoints en la nube de Z.AI y requiere API key de pago.

---

## Fuentes consultadas

- [OpenInterpreter/openinterpreter — README](https://github.com/OpenInterpreter/open-interpreter) — descripción oficial Rust, providers, filesystem
- [openinterpreter.com/docs/terminal/providers](https://www.openinterpreter.com/docs/terminal/providers) — tabla de providers, Ollama builtin, wire APIs
- [openinterpreter.com/docs/terminal/sandbox](https://www.openinterpreter.com/docs/terminal/sandbox) — sandbox modes, Linux enforcement
- [openinterpreter.com/docs/terminal/zai-glm](https://www.openinterpreter.com/docs/terminal/zai-glm) — providers GLM, ZCode harness
- [endolith/open-interpreter](https://github.com/endolith/open-interpreter) — fork Python comunitario
- [ollama.com/library/glm-4.7-flash](https://ollama.com/library/glm-4.7-flash) — modelo oficial en Ollama
- [ollama.com/library/glm4:latest](https://ollama.com/library/glm4:latest) — glm4 9B en Ollama
- [unsloth.ai/docs/models/glm-4.7-flash](https://unsloth.ai/docs/models/glm-4.7-flash) — requisitos VRAM GLM-4.7-Flash (24 GB recomendado)
- [strands-agents/tools README](https://github.com/strands-agents/tools/blob/main/README.md) — tools del SDK (ahora deprecadas en favor de SDK vended tools)
- GitHub issues #1865, #1633, #1689, #1086 de openinterpreter/openinterpreter — problemas conocidos Ollama+OI

*Content was rephrased for compliance with licensing restrictions.*
