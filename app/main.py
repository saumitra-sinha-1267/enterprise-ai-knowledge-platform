"""Enterprise AI Knowledge Platform - Secure RAG System
FastAPI Application Entrypoint.
"""

from contextlib import asynccontextmanager
import logging
from typing import Dict, Any

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1.api import api_router
from app.config import settings
from app.db.init_db import init_db

# Configure application logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("enterprise_rag")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle hooks: initialize database and seed demo personas."""
    logger.info("Initializing Enterprise AI Knowledge Platform...")
    try:
        init_db()
        logger.info("Database initialized and demo accounts ready.")
    except Exception as e:
        logger.error(f"Error during startup database initialization: {e}")
    yield
    logger.info("Enterprise AI Knowledge Platform shutting down.")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "Production-oriented Secure RAG System with Document-Level "
        "Role-Based Access Control (RBAC), Prompt Injection Guardrails, "
        "and Grounded Source Citations."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# Configure Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming request methods and paths."""
    logger.debug(f"HTTP {request.method} {request.url.path}")
    response = await call_next(request)
    return response


# Include Versioned API Routes
app.include_router(api_router, prefix="/api/v1")


@app.get("/", summary="Root Entrypoint")
def root() -> Dict[str, Any]:
    """Root endpoint welcoming users and pointing to OpenAPI documentation."""
    return {
        "service": settings.PROJECT_NAME,
        "status": "operational",
        "documentation": "/docs",
        "api_v1": "/api/v1",
        "features": [
            "Document Ingestion (PDF, DOCX, TXT)",
            "Server-Side RBAC Filtering",
            "Prompt Injection Defense & Delimiter Isolation",
            "Grounded Generation with Source Citations",
            "Qdrant Vector Database Integration",
        ],
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
