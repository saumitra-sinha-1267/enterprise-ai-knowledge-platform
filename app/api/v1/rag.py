"""RAG Retrieval and Grounded Question Answering endpoints.
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.auth.models import User
from app.generation.rag_chain import rag_chain, RAGResponse
from app.retrieval.search import retrieve_relevant_chunks

router = APIRouter()


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=1500, description="Natural language enterprise question")
    top_k: Optional[int] = Field(default=None, ge=1, le=20, description="Max chunks to retrieve")
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0, description="Minimum similarity score")


@router.post("/query", response_model=RAGResponse, summary="Ask question with RBAC-secured RAG")
def query_rag(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
) -> RAGResponse:
    """Submit a question to the Secure RAG system.
    
    The pipeline enforces:
    1. Prompt injection screening.
    2. Server-side pre-filtering against user's permitted departments and access levels.
    3. Grounded answer generation using verified context.
    4. Exact source citations containing filename, page number, and similarity score.
    5. Fallback notice if documents lack the requested facts.
    """
    response = rag_chain.answer_question(
        question=request.query,
        user=current_user,
        top_k=request.top_k,
        threshold=request.threshold,
    )
    return response


@router.post("/search-preview", summary="Inspect retrieved chunks without LLM synthesis")
def search_preview(
    request: QueryRequest,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Inspect which document chunks are returned for a query under the user's RBAC scope."""
    chunks = retrieve_relevant_chunks(
        query=request.query,
        user=current_user,
        top_k=request.top_k,
        threshold=request.threshold,
    )
    return [
        {
            "chunk_id": c.chunk_id,
            "filename": c.filename,
            "department": c.department,
            "access_level": c.access_level,
            "chunk_index": c.chunk_index,
            "page_number": c.page_number,
            "similarity_score": round(c.score, 4),
            "text": c.text,
        }
        for c in chunks
    ]
