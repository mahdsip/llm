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

Despliegue completamente local sobre Linux sin GPU dedicada, usando contenedores Docker. **Ningún dato sale al exterior**: tanto el modelo de lenguaje como el modelo de embeddings corren en la propia máquina vía Ollama.

#### Módulo LLM — `agentsvc`

`llama3.1:8b` corriendo en Ollama es el cerebro del sistema. Por cada pregunta:

1. **Interpreta** la pregunta del usuario
2. **Decide** si necesita buscar en los documentos locales (via function calling con `search_rag`)
3. Si sí, **lanza la consulta** al módulo RAG
4. **Evalúa** los fragmentos recuperados y los integra como contexto
5. **Elabora** la respuesta final fundamentada en esos documentos

LangChain orquesta este ciclo en `agentsvc`. Ollama sirve el modelo directamente en la máquina, sin ninguna llamada a API externa.

#### Módulo RAG — `ragapi`

`ragapi` no genera lenguaje. Solo se encarga de:

- Indexar los documentos locales con chunking configurable
- Generar embeddings con `nomic-embed-text` (también en Ollama local)
- Almacenar los vectores en Qdrant
- Responder consultas de similitud devolviendo únicamente fragmentos de texto

#### Flujo completo

```
OpenWebUI → agentsvc → llama3.1:8b (interpreta + decide)
                │
                └──[search_rag]──► ragapi → Qdrant
                                      │
                ◄── fragmentos ────────┘
                │
                └──► llama3.1:8b (evalúa + responde)
                │
             Usuario
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
