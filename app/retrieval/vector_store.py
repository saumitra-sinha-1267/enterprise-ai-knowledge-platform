"""Vector store abstraction and implementations supporting Qdrant and In-Memory storage.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from typing import Any, Dict, List, Optional
import uuid

import numpy as np

from app.config import settings, VectorDBType
from app.retrieval.embeddings import EMBEDDING_DIMENSION

logger = logging.getLogger(__name__)


@dataclass
class ScoredChunk:
    """Retrieved document chunk accompanied by provenance metadata and similarity score."""
    chunk_id: str
    document_id: int
    doc_id: str
    filename: str
    department: str
    access_level: str
    chunk_index: int
    page_number: Optional[int]
    text: str
    score: float


class BaseVectorStore(ABC):
    """Abstract interface for vector database storage and RBAC-filtered retrieval."""

    @abstractmethod
    def insert_chunks(self, records: List[Dict[str, Any]], vectors: List[List[float]]) -> None:
        """Insert chunk records and their corresponding dense vectors."""
        pass

    @abstractmethod
    def search(
        self,
        query_vector: List[float],
        allowed_departments: List[str],
        allowed_access_levels: List[str],
        top_k: int = 4,
        threshold: float = 0.20,
    ) -> List[ScoredChunk]:
        """Perform semantic search strictly constrained by server-authorized departments and levels."""
        pass

    @abstractmethod
    def delete_by_doc_id(self, doc_id: str) -> None:
        """Purge all chunk vectors belonging to a specific document ID."""
        pass

    @abstractmethod
    def count(self) -> int:
        """Return total number of vector points stored."""
        pass


class QdrantVectorStore(BaseVectorStore):
    """Qdrant vector store supporting in-memory embedded mode and remote server mode."""

    def __init__(self):
        from qdrant_client import QdrantClient
        from qdrant_client.http import models as rest_models

        self.models = rest_models
        self.collection_name = settings.QDRANT_COLLECTION_NAME

        if settings.QDRANT_IN_MEMORY:
            storage_path = settings.BASE_DIR / "qdrant_storage"
            logger.info(f"Initializing Qdrant client in persistent local storage mode at {storage_path}.")
            self.client = QdrantClient(path=str(storage_path))
        else:
            logger.info(f"Connecting to remote Qdrant server at {settings.QDRANT_HOST}:{settings.QDRANT_PORT}.")
            self.client = QdrantClient(host=settings.QDRANT_HOST, port=settings.QDRANT_PORT)

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        """Create Qdrant collection if it does not already exist."""
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.collection_name for c in collections)
            if not exists:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=self.models.VectorParams(
                        size=EMBEDDING_DIMENSION,
                        distance=self.models.Distance.COSINE,
                    ),
                )
                logger.info(f"Created Qdrant collection '{self.collection_name}'.")
        except Exception as e:
            logger.error(f"Error ensuring Qdrant collection: {e}")
            raise

    def insert_chunks(self, records: List[Dict[str, Any]], vectors: List[List[float]]) -> None:
        if not records or not vectors:
            return

        points = []
        for record, vec in zip(records, vectors):
            point_id = str(uuid.uuid4())
            payload = {
                "chunk_id": point_id,
                "document_id": record["document_id"],
                "doc_id": record["doc_id"],
                "filename": record["filename"],
                "department": record["department"],
                "access_level": record["access_level"],
                "chunk_index": record["chunk_index"],
                "page_number": record.get("page_number"),
                "text": record["text"],
            }
            points.append(
                self.models.PointStruct(
                    id=point_id,
                    vector=vec,
                    payload=payload,
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        logger.info(f"Upserted {len(points)} vectors into Qdrant collection '{self.collection_name}'.")

    def search(
        self,
        query_vector: List[float],
        allowed_departments: List[str],
        allowed_access_levels: List[str],
        top_k: int = 4,
        threshold: float = 0.20,
    ) -> List[ScoredChunk]:
        """Search Qdrant with pre-filtering on authorized department and access level values."""
        # Construct strict RBAC payload pre-filters
        filter_conditions = [
            self.models.FieldCondition(
                key="department",
                match=self.models.MatchAny(any=allowed_departments),
            ),
            self.models.FieldCondition(
                key="access_level",
                match=self.models.MatchAny(any=allowed_access_levels),
            ),
        ]
        rbac_filter = self.models.Filter(must=filter_conditions)

        if hasattr(self.client, "query_points"):
            res = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=rbac_filter,
                limit=top_k,
                score_threshold=threshold,
            )
            search_results = res.points
        elif hasattr(self.client, "search"):
            search_results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=rbac_filter,
                limit=top_k,
                score_threshold=threshold,
            )
        else:
            search_results = []

        scored_chunks: List[ScoredChunk] = []
        for hit in search_results:
            p = hit.payload
            scored_chunks.append(
                ScoredChunk(
                    chunk_id=str(hit.id),
                    document_id=p["document_id"],
                    doc_id=p["doc_id"],
                    filename=p["filename"],
                    department=p["department"],
                    access_level=p["access_level"],
                    chunk_index=p["chunk_index"],
                    page_number=p.get("page_number"),
                    text=p["text"],
                    score=float(hit.score),
                )
            )

        return scored_chunks

    def delete_by_doc_id(self, doc_id: str) -> None:
        """Remove all points associated with a document ID."""
        doc_filter = self.models.Filter(
            must=[
                self.models.FieldCondition(
                    key="doc_id",
                    match=self.models.MatchValue(value=doc_id),
                )
            ]
        )
        self.client.delete(
            collection_name=self.collection_name,
            points_selector=self.models.FilterSelector(filter=doc_filter),
        )
        logger.info(f"Deleted vectors for doc_id '{doc_id}' from Qdrant.")

    def count(self) -> int:
        try:
            info = self.client.get_collection(self.collection_name)
            return info.points_count or 0
        except Exception:
            return 0


class InMemoryVectorStore(BaseVectorStore):
    """Pure Python in-memory vector store for testing and zero-dependency environments."""

    def __init__(self):
        self.points: List[Dict[str, Any]] = []

    def insert_chunks(self, records: List[Dict[str, Any]], vectors: List[List[float]]) -> None:
        for record, vec in zip(records, vectors):
            self.points.append({
                "id": str(uuid.uuid4()),
                "vector": np.array(vec, dtype=np.float32),
                "payload": dict(record),
            })

    def search(
        self,
        query_vector: List[float],
        allowed_departments: List[str],
        allowed_access_levels: List[str],
        top_k: int = 4,
        threshold: float = 0.20,
    ) -> List[ScoredChunk]:
        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        scored: List[ScoredChunk] = []
        for pt in self.points:
            p = pt["payload"]
            # Strict RBAC filter: Department AND Access Level must match
            if p["department"] not in allowed_departments:
                continue
            if p["access_level"] not in allowed_access_levels:
                continue

            v = pt["vector"]
            v_norm = np.linalg.norm(v)
            cosine_sim = float(np.dot(q_vec, v) / (q_norm * v_norm)) if (q_norm * v_norm) > 0 else 0.0

            if cosine_sim >= threshold:
                scored.append(
                    ScoredChunk(
                        chunk_id=pt["id"],
                        document_id=p["document_id"],
                        doc_id=p["doc_id"],
                        filename=p["filename"],
                        department=p["department"],
                        access_level=p["access_level"],
                        chunk_index=p["chunk_index"],
                        page_number=p.get("page_number"),
                        text=p["text"],
                        score=cosine_sim,
                    )
                )

        scored.sort(key=lambda x: x.score, reverse=True)
        return scored[:top_k]

    def delete_by_doc_id(self, doc_id: str) -> None:
        self.points = [pt for pt in self.points if pt["payload"]["doc_id"] != doc_id]

    def count(self) -> int:
        return len(self.points)


_vector_store_instance: Optional[BaseVectorStore] = None


def get_vector_store() -> BaseVectorStore:
    """Retrieve or initialize the active vector store singleton."""
    global _vector_store_instance
    if _vector_store_instance is None:
        if settings.VECTOR_DB_TYPE == VectorDBType.MEMORY:
            _vector_store_instance = InMemoryVectorStore()
        else:
            try:
                _vector_store_instance = QdrantVectorStore()
            except Exception as e:
                logger.warning(f"Failed to initialize Qdrant ({e}). Falling back to InMemoryVectorStore.")
                _vector_store_instance = InMemoryVectorStore()
    return _vector_store_instance
