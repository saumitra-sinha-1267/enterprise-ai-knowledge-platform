"""High-level semantic retrieval service enforcing server-side RBAC filters.
"""

import logging
from typing import List

from app.auth.models import User
from app.auth.rbac import get_allowed_departments_for_user, get_allowed_access_levels_for_user
from app.config import settings
from app.retrieval.embeddings import embedding_service
from app.retrieval.vector_store import get_vector_store, ScoredChunk
from app.security.audit_log import AuditLogger, EVENT_ACCESS_DENIED

logger = logging.getLogger(__name__)


def retrieve_relevant_chunks(
    query: str,
    user: User,
    top_k: int = None,
    threshold: float = None,
) -> List[ScoredChunk]:
    """Execute RBAC-filtered semantic search against the vector database.
    
    Ensures that chunks belonging to unauthorized departments or classification
    levels NEVER enter the retrieval result set or the LLM context.
    """
    top_k = top_k or settings.RETRIEVAL_TOP_K
    threshold = threshold if threshold is not None else settings.SIMILARITY_THRESHOLD

    # Derive server-side authorized access scopes from verified user claims
    allowed_departments = get_allowed_departments_for_user(user)
    allowed_access_levels = get_allowed_access_levels_for_user(user)

    logger.info(
        f"User '{user.username}' (role={user.role}, dept={user.department}) querying RAG. "
        f"Authorized departments: {allowed_departments}, levels: {allowed_access_levels}"
    )

    # Generate query embedding
    query_vector = embedding_service.embed_query(query)

    # Perform filtered search at the vector database layer
    vector_store = get_vector_store()
    raw_results = vector_store.search(
        query_vector=query_vector,
        allowed_departments=allowed_departments,
        allowed_access_levels=allowed_access_levels,
        top_k=top_k,
        threshold=threshold,
    )

    # Defense-in-depth: Secondary application-layer filter verification
    verified_results: List[ScoredChunk] = []
    for chunk in raw_results:
        if chunk.department in allowed_departments and chunk.access_level in allowed_access_levels:
            verified_results.append(chunk)
        else:
            # Audit log any unexpected boundary violation
            AuditLogger.log_event(
                event_type=EVENT_ACCESS_DENIED,
                user_id=user.id,
                username=user.username,
                role=user.role,
                department=user.department,
                details={
                    "violation": "chunk_dropped_by_secondary_verification",
                    "chunk_department": chunk.department,
                    "chunk_access_level": chunk.access_level,
                    "doc_id": chunk.doc_id,
                },
                success=False,
            )

    return verified_results
