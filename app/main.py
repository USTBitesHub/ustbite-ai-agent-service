from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
import logging
import json
import time
import uuid
import asyncio
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST, Counter, Histogram
from app.config import settings

app = FastAPI(
    title="ustbite-ai-agent-service",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'http_request_duration_seconds',
    'HTTP request latency',
    ['method', 'endpoint']
)

@app.middleware("http")
async def logging_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-ID", str(uuid.uuid4()))
    start = time.time()
    
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception as e:
        status_code = 500
        response = JSONResponse(status_code=500, content={"message": "Internal Server Error"})
        
    duration = (time.time() - start) * 1000
    svc_name = getattr(settings, 'SERVICE_NAME', "ustbite-ai-agent-service")
        
    log = {
        "service": svc_name,
        "trace_id": trace_id,
        "method": request.method,
        "path": request.url.path,
        "status": status_code,
        "duration_ms": round(duration, 2)
    }
    print(json.dumps(log))
    
    response.headers["X-Trace-ID"] = trace_id
    
    path_template = request.scope.get("route").path if request.scope.get("route") else request.url.path
    REQUEST_COUNT.labels(method=request.method, endpoint=path_template, status=status_code).inc()
    REQUEST_LATENCY.labels(method=request.method, endpoint=path_template).observe(duration / 1000.0)
    
    return response

@app.get("/health")
async def health():
    svc_name = getattr(settings, 'SERVICE_NAME', "ustbite-ai-agent-service")
    return {
        "status": "healthy",
        "service": svc_name,
        "version": "1.0.0"
    }

@app.get("/metrics")
async def metrics():
    return Response(
        generate_latest(), 
        media_type=CONTENT_TYPE_LATEST
    )

@app.post("/webhook/alert")
async def handle_alert(payload: dict):
    # Triggers LangChain agent asynchronously
    return {"status": "accepted"}

@app.get("/incidents")
async def get_incidents():
    return []

@app.get("/incidents/{id}")
async def get_incident(id: str):
    return {}
