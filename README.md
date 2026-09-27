# Proyectos LLM

Repositorio que agrupa tres implementaciones de sistemas de pregunta-respuesta con recuperación de documentos (RAG), diferenciando claramente el **módulo LLM** (comprensión de la pregunta y elaboración de la respuesta) del **módulo RAG** (generación de embeddings y almacenamiento vectorial).

---

## Arquitectura conceptual

Todos los proyectos siguen la misma separación de responsabilidades:

```
Usuario
   │
   ▼
┌─────────────────────────────────┐
│         MÓDULO LLM              │
│  · Entiende la pregunta         │
│  · Clasifica intención          │
│  · Decide si consultar el RAG   │
│  · Elabora la respuesta final   │
└────────────────┬────────────────┘
                 │ consulta contextual
                 ▼
┌─────────────────────────────────┐
│         MÓDULO RAG              │
│  · Genera embeddings            │
│  · Almacena vectores            │
│  · Recupera fragmentos          │
│  · No genera lenguaje           │
└─────────────────────────────────┘
```

---

## Proyectos

### 1. RAG local — `model-rag-local/`

Despliegue completamente local sobre Linux sin GPU dedicada, usando contenedores Docker. El modelo de lenguaje corre **en la propia máquina** vía Ollama — ningún dato sale al exterior.

| Módulo | Servicio | Tecnología | Rol |
|--------|---------|-----------|-----|
| **LLM** | `agentsvc` + Ollama | `llama3.1:8b` · LangChain | El modelo local recibe la pregunta, decide si necesita consultar los documentos (function calling con `search_rag`), evalúa los fragmentos recuperados y redacta la respuesta final. Ollama sirve el modelo directamente en la máquina, sin llamada externa |
| **RAG** | `ragapi` | LlamaIndex · `nomic-embed-text` · Qdrant | Indexa documentos locales, genera embeddings con `nomic-embed-text` (también en Ollama local) y responde consultas de similitud devolviendo solo fragmentos — nunca genera lenguaje |

**Ciclo completo por pregunta:**
```
Usuario
  │
  ▼
OpenWebUI
  │
  ▼
agentsvc  ──[1. interpreta la pregunta]──► llama3.1:8b (Ollama local)
  │                                              │
  │         [2. ¿necesito documentos?] ◄─────────┘
  │                    │ sí
  ▼                    ▼
agentsvc ──[3. lanza search_rag]──► ragapi (RAG)
                                        │
                                    [4. búsqueda vectorial]
                                        │
                                    Qdrant ──► fragmentos relevantes
                                        │
  agentsvc ◄──[5. devuelve chunks]──────┘
  │
  ▼
[6. llama3.1:8b evalúa los fragmentos y elabora respuesta]
  │
  ▼
Usuario ◄── respuesta final con fuentes
```

**Detalles:** [`model-rag-local/README.md`](model-rag-local/README.md)

---

### 2. LLM en nube — repo [familIA](https://github.com/mahdsip/familIA)

Módulo LLM desplegado en AWS dentro del proyecto familIA. Se encarga exclusivamente de la clasificación de intención, el enrutamiento y la generación de respuesta. El RAG es independiente (ver módulo siguiente).

| Módulo | Servicio | Tecnología | Rol |
|--------|---------|-----------|-----|
| **LLM — Orchestrator** | Lambda `orchestrator` | Amazon Bedrock · Claude Haiku 4.5 (vía inference profile regional `eu`) | Clasifica la intención (personal vs. general), auto-detecta persona/tema, consulta el RAG si es pregunta personal y genera la respuesta fundamentada con citas |

**Flujo:**
```
Raspberry Pi (OpenVoice) → proxy SigV4 → API Gateway
    → Lambda orchestrator (Haiku 4.5)
          │  pregunta personal
          └──► Lambda retriever (RAG puro, ver módulo 3)
                    │  fragmentos + metadatos
                    ◄──────────────────────────
          │
          └──► Bedrock (Haiku 4.5) → respuesta con fuentes
```

**Repositorio:** [github.com/mahdsip/familIA](https://github.com/mahdsip/familIA)

---

### 3. RAG en nube — repo [familIA](https://github.com/mahdsip/familIA)

Módulo RAG desplegado en AWS dentro del mismo proyecto familIA, **completamente desacoplado del LLM**. Solo genera vectores, los almacena y devuelve fragmentos — nunca produce texto de respuesta.

| Módulo | Servicio | Tecnología | Rol |
|--------|---------|-----------|-----|
| **RAG — Retriever** | Lambda `query` + Bedrock Knowledge Base | Amazon Bedrock Retrieve · Titan Text Embeddings v2 (1024 dims) · S3 Vectors | Genera embeddings de documentos, los almacena en S3 Vectors (KMS cifrado) y devuelve solo fragmentos relevantes sin generación de lenguaje |
| **Ingestión** | Lambda `auto_sync` + EventBridge | Bedrock Knowledge Base · chunking jerárquico · parsing multimodal FM | Re-indexa automáticamente al subir documentos (evento S3) o semanalmente. Soporta PDFs escaneados, tablas y JPEGs con EXIF |

**Flujo de ingestión:**
```
Documentos locales ──aws s3 sync──► S3 (KMS) → evento ObjectCreated
    → Lambda auto_sync → Bedrock StartIngestionJob
        → Titan v2 embeddings → S3 Vectors (KMS)
```

**Flujo de consulta:**
```
Lambda orchestrator (LLM) ──► Lambda retriever
    → Bedrock Knowledge Base Retrieve
        → S3 Vectors → fragmentos + metadatos (owner, topic, fecha, fuente)
    ◄── chunks sin generar texto ──────────────────────────────────────────
```

**Repositorio:** [github.com/mahdsip/familIA](https://github.com/mahdsip/familIA)

---

## Comparativa rápida

| | RAG local | LLM en nube | RAG en nube |
|---|---|---|---|
| **Entorno** | Linux local · Docker | AWS Lambda | AWS Lambda |
| **Región** | — | `eu-central-1` | `eu-central-1` |
| **LLM** | Ollama `llama3.1:8b` | Bedrock Claude Haiku 4.5 | — |
| **Embeddings** | `nomic-embed-text` (Ollama) | — | Bedrock Titan Text v2 · 1024 dims |
| **Vector store** | Qdrant | — | S3 Vectors (KMS cifrado) |
| **Chunking** | LlamaIndex (configurable) | — | Jerárquico + parsing FM |
| **Orquestación** | LangChain · agentsvc | Lambda orchestrator | Lambda auto_sync + retriever |
| **Auth** | Red local | IAM / SigV4 | IAM / SigV4 |
| **Coste** | 0 € (hardware propio) | Pay-per-use (céntimos/pregunta) | Pay-per-use (ingestión única) |
| **Privacidad** | Total (sin salida de datos) | Datos en AWS · KMS CMK | Datos en AWS · KMS CMK |
