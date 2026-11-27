"""Embedding model integration using Sentence Transformers with fallback capability.
"""

import hashlib
import logging
from typing import List, Union
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)

EMBEDDING_DIMENSION = 384  # Dimension for all-MiniLM-L6-v2


class EmbeddingService:
    """Generates normalized vector embeddings for text chunks and queries using FastEmbed (ONNX) or fallback."""

    def __init__(self, model_name: str = None, device: str = None):
        self.model_name = model_name or settings.EMBEDDING_MODEL_NAME or "sentence-transformers/all-MiniLM-L6-v2"
        self._fastembed_model = None
        self._st_model = None
        self._fallback_mode = False
        self._init_model()

    def _init_model(self) -> None:
        """Attempt to load ultra-lightweight FastEmbed ONNX model; fallback gracefully if unavailable."""
        # 1. FastEmbed (ONNX) - uses ~35MB RAM, NO PyTorch/CUDA dependencies
        try:
            from fastembed import TextEmbedding
            logger.info(f"Loading FastEmbed ONNX model 'sentence-transformers/all-MiniLM-L6-v2'...")
            self._fastembed_model = TextEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
            logger.info("FastEmbed ONNX model loaded successfully.")
            return
        except Exception as e:
            logger.info(f"FastEmbed not loaded ({e}), trying SentenceTransformer fallback...")

        # 2. SentenceTransformer (PyTorch) fallback
        try:
            import os
            import gc
            os.environ["OMP_NUM_THREADS"] = "1"
            os.environ["MKL_NUM_THREADS"] = "1"
            try:
                import torch
                torch.set_num_threads(1)
            except Exception:
                pass

            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading SentenceTransformer model '{self.model_name}' on CPU...")
            self._st_model = SentenceTransformer(self.model_name, device="cpu")
            gc.collect()
            logger.info("SentenceTransformer model loaded successfully.")
            return
        except Exception as e:
            logger.warning(
                f"Could not load SentenceTransformer '{self.model_name}' ({e}). "
                f"Operating in deterministic offline vector mode."
            )
            self._fallback_mode = True

    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of text strings into normalized vectors."""
        if not texts:
            return []

        # 1. FastEmbed ONNX path (ultra-low memory)
        if self._fastembed_model is not None:
            try:
                embeddings = list(self._fastembed_model.embed(texts))
                return [e.tolist() for e in embeddings]
            except Exception as e:
                logger.warning(f"FastEmbed encoding error ({e}). Using fallback.")

        # 2. SentenceTransformer path
        if not self._fallback_mode and self._st_model is not None:
            try:
                embeddings = self._st_model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                return embeddings.tolist()
            except Exception as e:
                logger.warning(f"SentenceTransformer encoding error ({e}). Using offline embedding fallback.")

        # 3. Deterministic offline embedding generator using hashing and word trigrams
        return [self._offline_hash_embed(t) for t in texts]

    def embed_query(self, query: str) -> List[float]:
        """Embed a single query string into a vector."""
        vectors = self.embed_texts([query])
        return vectors[0] if vectors else [0.0] * EMBEDDING_DIMENSION

    def _offline_hash_embed(self, text: str) -> List[float]:
        """Generate a deterministic pseudo-semantic 384-dimensional unit vector."""
        vec = np.zeros(EMBEDDING_DIMENSION, dtype=np.float32)
        words = text.lower().split()
        if not words:
            return vec.tolist()

        for word in words:
            # Deterministic hash bucket
            h = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
            idx = h % EMBEDDING_DIMENSION
            sign = 1.0 if (h // EMBEDDING_DIMENSION) % 2 == 0 else -1.0
            vec[idx] += sign

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()


# Global singleton instance
embedding_service = EmbeddingService()
