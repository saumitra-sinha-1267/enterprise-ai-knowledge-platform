"""System health checks and readiness monitoring.
"""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.config import settings
from app.retrieval.vector_store import get_vector_store

router = APIRouter()


@router.get("/health", summary="System Health Probe")
def health_check(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """Check connectivity to relational database, vector database, and service components."""
    # Check SQL Database
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Vector Database
    vector_status = "healthy"
    vector_count = 0
    try:
        vs = get_vector_store()
        vector_count = vs.count()
    except Exception as e:
        vector_status = f"unhealthy: {str(e)}"

    is_overall_healthy = (db_status == "healthy") and (vector_status == "healthy")

    return {
        "status": "healthy" if is_overall_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT.value,
        "database": {
            "status": db_status,
            "engine": "sqlite" if settings.DATABASE_URL.startswith("sqlite") else "postgresql",
        },
        "vector_store": {
            "status": vector_status,
            "type": settings.VECTOR_DB_TYPE.value,
            "indexed_vectors": vector_count,
        },
        "llm_provider": settings.LLM_PROVIDER.value,
        "embedding_model": settings.EMBEDDING_MODEL_NAME,
    }
