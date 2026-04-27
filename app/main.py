import asyncio
import logging
import ollama
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.models import ChatRequest, ChatResponse, HealthResponse
from app.agent import run_agent

logging.basicConfig(level=settings.LOG_LEVEL)
logger = logging.getLogger(__name__)

app = FastAPI(title="USTBite AI Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


_llm_semaphore = asyncio.Semaphore(1)


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    if _llm_semaphore.locked():
        raise HTTPException(status_code=429, detail="AI is busy processing another request. Please wait a moment and try again.")
    async with _llm_semaphore:
        auth_header = request.headers.get("Authorization", "")
        logger.info("Chat request | session=%s | message=%s", body.session_id, body.message)
        history = [h.model_dump() for h in body.history]
        return await run_agent(body.message, body.session_id, auth_header, history)


_ollama_status: dict = {"status": "unknown", "checked_at": 0.0}
_OLLAMA_CHECK_INTERVAL = 60.0


@app.get("/health", response_model=HealthResponse)
async def health():
    import time
    now = time.monotonic()
    if now - _ollama_status["checked_at"] > _OLLAMA_CHECK_INTERVAL:
        try:
            client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
            await client.list()
            _ollama_status["status"] = "reachable"
        except Exception as e:
            logger.warning("Ollama unreachable: %s", e)
            _ollama_status["status"] = f"unreachable: {e}"
        _ollama_status["checked_at"] = now

    return HealthResponse(status="ok", ollama=_ollama_status["status"])
