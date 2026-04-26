import logging
import ollama
from fastapi import FastAPI, Request
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


@app.post("/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    auth_header = request.headers.get("Authorization", "")
    logger.info("Chat request | session=%s | message=%s", body.session_id, body.message)
    return await run_agent(body.message, body.session_id, auth_header)


@app.get("/health", response_model=HealthResponse)
async def health():
    try:
        client = ollama.AsyncClient(host=settings.OLLAMA_HOST)
        await client.list()
        ollama_status = "reachable"
    except Exception as e:
        logger.warning("Ollama unreachable: %s", e)
        ollama_status = f"unreachable: {e}"

    return HealthResponse(status="ok", ollama=ollama_status)
