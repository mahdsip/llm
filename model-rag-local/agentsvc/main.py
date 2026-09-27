import os
import json
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

APP = FastAPI(title="RAG Agent Service", version="1.1.0")

RAG_API_BASE = os.getenv("RAG_API_BASE", "http://ragapi:8000")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.1:8b")


@tool
def search_rag(question: str) -> str:
    """Search the user's local document collection. Use this for questions that may be answered by personal/local documents."""
    r = requests.post(
        f"{RAG_API_BASE}/query",
        json={"question": question},
        timeout=300,
    )
    r.raise_for_status()
    data = r.json()
    return json.dumps(data, ensure_ascii=False)


llm = ChatOllama(
    model=LLM_MODEL,
    base_url=OLLAMA_BASE_URL,
    temperature=0,
)
llm_tools = llm.bind_tools([search_rag])

SYSTEM_PROMPT = """Eres el asistente local del usuario.
Tienes acceso a una herramienta llamada search_rag que busca en sus documentos locales.
Cuando la pregunta pueda depender de información de esos documentos, utiliza search_rag antes de responder.
No inventes información que no esté respaldada por el contexto recuperado.
Si la herramienta no encuentra información suficiente, dilo claramente.
Puedes responder directamente sin la herramienta para preguntas generales que no dependan de los documentos locales.
Responde en español salvo que el usuario pida otro idioma."""


class ChatRequest(BaseModel):
    message: str


def run_agent(message: str) -> tuple[str, list]:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=message),
    ]

    first = llm_tools.invoke(messages)
    sources = []

    if getattr(first, "tool_calls", None):
        messages.append(first)
        for call in first.tool_calls:
            if call["name"] != "search_rag":
                continue
            result = search_rag.invoke(call["args"])
            data = json.loads(result)
            sources.extend(data.get("sources", []))
            messages.append(
                ToolMessage(
                    content=result,
                    tool_call_id=call["id"],
                )
            )

        final = llm_tools.invoke(messages)
        return str(final.content), sources

    return str(first.content), sources


@APP.get("/health")
def health():
    return {"status": "ok"}


@APP.get("/v1/models")
def models():
    return {
        "object": "list",
        "data": [
            {
                "id": LLM_MODEL,
                "object": "model",
                "owned_by": "local-rag",
            }
        ],
    }


@APP.post("/chat")
def chat(req: ChatRequest):
    try:
        answer, sources = run_agent(req.message)
        return {"answer": answer, "sources": sources}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@APP.post("/v1/chat/completions")
def chat_completions(payload: dict):
    try:
        messages = payload.get("messages", [])
        user_messages = [m.get("content", "") for m in messages if m.get("role") == "user"]
        message = user_messages[-1] if user_messages else ""

        answer, sources = run_agent(message)
        return {
            "id": "local-rag-chat",
            "object": "chat.completion",
            "created": 0,
            "model": payload.get("model", LLM_MODEL),
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": answer,
                    },
                    "finish_reason": "stop",
                }
            ],
            "sources": sources,
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
