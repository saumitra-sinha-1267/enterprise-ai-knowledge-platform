"""Unit tests for embedding generation and vector search.
"""

import numpy as np
import pytest

from app.retrieval.embeddings import embedding_service, EMBEDDING_DIMENSION
from app.retrieval.vector_store import get_vector_store


def test_embedding_dimensions_and_normalization():
    """Verify generated embeddings have expected dimension and unit length."""
    text = "Enterprise architecture guidelines for high availability microservices."
    vec = embedding_service.embed_query(text)

    assert len(vec) == EMBEDDING_DIMENSION
    norm = np.linalg.norm(np.array(vec))
    assert pytest.approx(norm, abs=1e-3) == 1.0


def test_batch_embedding_consistency():
    """Verify batch embedding produces consistent vectors matching single query."""
    texts = [
        "Human Resources annual leave policy.",
        "Corporate finance procurement limits.",
    ]
    batch_vecs = embedding_service.embed_texts(texts)
    assert len(batch_vecs) == 2
    assert len(batch_vecs[0]) == EMBEDDING_DIMENSION
    assert len(batch_vecs[1]) == EMBEDDING_DIMENSION

    single_vec = embedding_service.embed_query(texts[0])
    # Vectors should be identical
    cos_sim = np.dot(batch_vecs[0], single_vec)
    assert pytest.approx(cos_sim, abs=1e-4) == 1.0


def test_vector_store_filtering():
    """Verify vector store search respects department and access level boundaries."""
    vector_store = get_vector_store()
    query_vec = embedding_service.embed_query("PTO and vacation days")

    # Search allowing only HR
    hr_results = vector_store.search(
        query_vector=query_vec,
        allowed_departments=["hr"],
        allowed_access_levels=["public", "internal", "confidential"],
        top_k=4,
    )
    for hit in hr_results:
        assert hit.department == "hr"

    # Search allowing only Engineering
    eng_results = vector_store.search(
        query_vector=query_vec,
        allowed_departments=["engineering"],
        allowed_access_levels=["public", "internal"],
        top_k=4,
    )
    for hit in eng_results:
        assert hit.department == "engineering"
