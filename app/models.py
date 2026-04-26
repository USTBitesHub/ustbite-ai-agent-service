from pydantic import BaseModel
from typing import Any


class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"


class ToolCallInfo(BaseModel):
    tool: str
    args: dict[str, Any]
    result: Any


class ChatResponse(BaseModel):
    response: str
    tool_calls_made: list[ToolCallInfo] = []


class HealthResponse(BaseModel):
    status: str
    ollama: str
