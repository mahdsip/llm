# Proyectos LLM

> **⚠️ Repositorio en rediseño.** El proyecto local (`model-rag-local/`) ha sido renombrado a [`legacy/`](legacy/) y se conserva como referencia histórica. El nuevo sistema — un agente de terminal con React loop (Strands), selección de modelo (Qwen 14B / DeepSeek-R1-32B), RAG intercambiable (FAISS / Qdrant) y punto de entrada `./myagent` — está siendo construido sobre esa base. La documentación completa se actualizará al finalizar la reestructuración.

Dos implementaciones de un sistema de pregunta-respuesta con recuperación de documentos (RAG), cada una con sus dos submódulos bien diferenciados:

- **Módulo LLM** — interpreta la pregunta, decide si consultar los documentos, evalúa el contexto recuperado y elabora la respuesta final
- **Módulo RAG** — genera embeddings, almacena vectores y recupera fragmentos relevantes; nunca produce lenguaje

---

## Proyecto 1 — Local

**Repositorio:** [`model-rag-local/`](model-rag-local/)

Despliegue completamente local sobre Linux sin GPU dedicada, usando contenedores Docker. Ningún dato sale al exterior: tanto el modelo de lenguaje como el de embeddings corren en la propia máquina vía Ollama.

### Submódulo LLM — `agentsvc`

`llama3.1:8b` corriendo en Ollama es el cerebro del sistema. Por cada pregunta:

1. **Interpreta** la pregunta del usuario
2. **Decide** si necesita buscar en los documentos locales (function calling con `search_rag`)
3. Si sí, **lanza la consulta** al submódulo RAG
4. **Evalúa** los fragmentos recuperados y los integra como contexto
5. **Elabora** la respuesta final fundamentada en esos documentos

LangChain orquesta este ciclo en `agentsvc`. Ollama sirve el modelo en la propia máquina, sin ninguna llamada a API externa.

### Submódulo RAG — `ragapi`

`ragapi` no genera lenguaje. Solo se encarga de:

- Indexar los documentos locales con chunking configurable
- Generar embeddings con `nomic-embed-text` (también en Ollama local)
- Almacenar los vectores en Qdrant
- Devolver únicamente fragmentos de texto ante consultas de similitud

### Flujo

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

| | Tecnología |
|---|---|
| LLM | Ollama · `llama3.1:8b` · LangChain |
| Embeddings | Ollama · `nomic-embed-text` |
| Vector store | Qdrant |
| Interfaz | OpenWebUI |

**Detalles completos:** [`model-rag-local/README.md`](model-rag-local/README.md)

---

## Proyecto 2 — Nube (AWS)

**Repositorio:** [github.com/mahdsip/familIA](https://github.com/mahdsip/familIA)

Despliegue en AWS (`eu-central-1`) enteramente con Terraform, sin servidores siempre encendidos. El acceso está autenticado con IAM/SigV4 y todos los datos van cifrados con una clave KMS propia.

### Submódulo LLM — Lambda `orchestrator`

Claude Haiku 4.5 (vía Bedrock, inference profile regional `eu`) actúa como cerebro. Por cada pregunta:

1. **Clasifica** la intención: pregunta personal/familiar vs. conocimiento general
2. **Auto-detecta** la persona y el tema a partir de un listado inyectado en el despliegue (sin nombres en el código)
3. Si es personal, **consulta** el submódulo RAG con los filtros de persona/tema detectados
4. **Evalúa** los fragmentos recuperados y genera una respuesta fundamentada con citas de fuente
5. Si no encuentra nada en el RAG, **se detiene** — no inventa ni cae a conocimiento general

El punto de entrada es `POST /ask` en API Gateway, llamado desde una Raspberry Pi con OpenVoice vía proxy SigV4.

### Submódulo RAG — Lambda `retriever` + Bedrock Knowledge Base

La Lambda `retriever` no genera lenguaje. Solo se encarga de:

- Indexar documentos subidos a S3 (con chunking jerárquico y parsing multimodal de PDFs e imágenes)
- Generar embeddings con Titan Text Embeddings v2 (1024 dims, inmutables)
- Almacenar los vectores en S3 Vectors (cifrado KMS)
- Devolver únicamente fragmentos con metadatos (owner, topic, fecha, ruta S3) ante consultas del orchestrator

La re-indexación es automática: se dispara por evento `ObjectCreated` en S3 y tiene un ciclo semanal de seguridad vía EventBridge.

### Flujo

```
Raspberry Pi (OpenVoice)
  │
  └──[SigV4]──► API Gateway → Lambda orchestrator
                                  │  (Haiku 4.5: clasifica + decide)
                                  │
                          pregunta personal
                                  │
                                  └──► Lambda retriever
                                           │
                                     Bedrock KB → S3 Vectors
                                           │
                    ◄── fragmentos + metadatos ┘
                                  │
                          Haiku 4.5 (evalúa + responde)
                                  │
                             Usuario
```

**Flujo de ingestión:**

```
Documentos locales ──aws s3 sync──► S3 (KMS)
  → evento ObjectCreated → Lambda auto_sync
  → Bedrock StartIngestionJob → Titan v2 embeddings → S3 Vectors (KMS)
```

| | Tecnología |
|---|---|
| LLM | Amazon Bedrock · Claude Haiku 4.5 |
| Embeddings | Amazon Bedrock · Titan Text v2 · 1024 dims |
| Vector store | S3 Vectors (KMS cifrado) |
| Chunking | Jerárquico + parsing multimodal FM |
| Infraestructura | Terraform · AWS Lambda · API Gateway · EventBridge |
| Auth | IAM / SigV4 |

**Detalles completos:** [github.com/mahdsip/familIA](https://github.com/mahdsip/familIA)

---

## Comparativa

| | Local | Nube (AWS) |
|---|---|---|
| **LLM** | Ollama `llama3.1:8b` | Bedrock Claude Haiku 4.5 |
| **Embeddings** | `nomic-embed-text` (Ollama) | Bedrock Titan Text v2 · 1024 dims |
| **Vector store** | Qdrant | S3 Vectors (KMS) |
| **Chunking** | LlamaIndex configurable | Jerárquico + parsing FM |
| **Orquestación LLM** | LangChain · `agentsvc` | Lambda `orchestrator` |
| **Orquestación RAG** | LlamaIndex · `ragapi` | Lambda `retriever` + Bedrock KB |
| **Auth** | Red local | IAM / SigV4 |
| **Coste** | 0 € (hardware propio) | Pay-per-use |
| **Privacidad** | Total — ningún dato sale | Datos en AWS · KMS CMK |
