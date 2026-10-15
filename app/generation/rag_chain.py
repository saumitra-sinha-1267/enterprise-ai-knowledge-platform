"""End-to-end RAG orchestrator integrating RBAC retrieval, prompt guard, and grounded generation.
"""

import logging
from typing import List, Optional
from pydantic import BaseModel, Field

from app.auth.models import User
from app.config import settings
from app.generation.llm_client import get_llm_client, NOT_FOUND_MESSAGE
from app.generation.prompt_templates import format_rag_prompt
from app.retrieval.search import retrieve_relevant_chunks
from app.retrieval.vector_store import ScoredChunk
from app.security.audit_log import AuditLogger, EVENT_PROMPT_INJECTION, EVENT_RAG_QUERY
from app.security.prompt_guard import prompt_guard

logger = logging.getLogger(__name__)


class Citation(BaseModel):
    """Source reference proving answer provenance."""
    filename: str
    doc_id: str
    chunk_index: int
    page_number: Optional[int] = None
    department: str
    similarity_score: float
    snippet: str


class RAGResponse(BaseModel):
    """Standardized response from the Secure RAG pipeline."""
    query: str
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    is_grounded: bool = True
    prompt_guard_flagged: bool = False
    prompt_guard_reason: Optional[str] = None


class RAGChain:
    """Orchestrates security-screened retrieval, prompting, generation, and citation synthesis."""

    def __init__(self):
        self.llm = get_llm_client()

    def answer_question(
        self,
        question: str,
        user: User,
        top_k: Optional[int] = None,
        threshold: Optional[float] = None,
    ) -> RAGResponse:
        """Process an employee query through safety screening, RBAC retrieval, and grounded synthesis."""
        # 1. Prompt Injection & Input Validation Check
        guard_res = prompt_guard.validate_query(question)
        if not guard_res.is_safe:
            AuditLogger.log_event(
                event_type=EVENT_PROMPT_INJECTION,
                user_id=user.id,
                username=user.username,
                role=user.role,
                department=user.department,
                details={
                    "query": question[:200],
                    "reason": guard_res.reason,
                    "risk_level": guard_res.risk_level,
                },
                success=False,
            )
            return RAGResponse(
                query=question,
                answer=(
                    f"Request Rejected: Security guardrail violation detected. "
                    f"Detail: {guard_res.reason}. "
                    f"Please submit valid enterprise domain queries."
                ),
                citations=[],
                is_grounded=False,
                prompt_guard_flagged=True,
                prompt_guard_reason=guard_res.reason,
            )

        sanitized_query = guard_res.sanitized_input

        # 2. Server-side RBAC retrieval
        retrieved_chunks = retrieve_relevant_chunks(
            query=sanitized_query,
            user=user,
            top_k=top_k,
            threshold=threshold,
        )

        # 3. Handle zero-chunk retrieval
        if not retrieved_chunks:
            logger.info(f"Zero matching chunks found for user '{user.username}' on query: '{question}'")
            return RAGResponse(
                query=question,
                answer=NOT_FOUND_MESSAGE,
                citations=[],
                is_grounded=False,
                prompt_guard_flagged=False,
            )

        # 4. Construct prompt isolating context in untrusted tags
        prompt = format_rag_prompt(query=sanitized_query, retrieved_chunks=retrieved_chunks)

        # 5. Generate LLM response
        raw_answer = self.llm.generate(prompt)

        # 6. Validate output against accidental credential or delimiter leakage
        is_clean, verified_answer = prompt_guard.validate_output(raw_answer)
        if not is_clean:
            logger.warning(f"Output scrubber redacted content for query '{question}'.")

        # 7. Construct structured citations
        citations = []
        for chunk in retrieved_chunks:
            snippet = chunk.text[:220].strip() + ("..." if len(chunk.text) > 220 else "")
            citations.append(
                Citation(
                    filename=chunk.filename,
                    doc_id=chunk.doc_id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    department=chunk.department,
                    similarity_score=round(chunk.score, 4),
                    snippet=snippet,
                )
            )

        # 8. Log successful query audit event
        AuditLogger.log_event(
            event_type=EVENT_RAG_QUERY,
            user_id=user.id,
            username=user.username,
            role=user.role,
            department=user.department,
            details={
                "query": sanitized_query[:100],
                "retrieved_chunk_count": len(retrieved_chunks),
                "top_score": max([c.similarity_score for c in citations]) if citations else 0.0,
            },
            success=True,
        )

        is_grounded = NOT_FOUND_MESSAGE not in verified_answer

        return RAGResponse(
            query=question,
            answer=verified_answer,
            citations=citations,
            is_grounded=is_grounded,
            prompt_guard_flagged=False,
        )


rag_chain = RAGChain()
