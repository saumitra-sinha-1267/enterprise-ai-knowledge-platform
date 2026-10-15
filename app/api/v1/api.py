"""API v1 master router aggregating endpoints.
"""

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.rag import router as rag_router
from app.api.v1.health import router as health_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["Health"])
api_router.include_router(auth_router, prefix="/auth", tags=["Authentication & Identity"])
api_router.include_router(documents_router, prefix="/documents", tags=["Document Lifecycle"])
api_router.include_router(rag_router, prefix="/rag", tags=["Secure RAG & Retrieval"])
