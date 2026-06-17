from __future__ import annotations
from functools import lru_cache
import numpy as np

STRONG_MATCH_THRESHOLD = 0.72
GAP_BRIDGE_THRESHOLD = 0.42

@lru_cache(maxsize=1)
def get_embedding_model():
    # sentence_transformers is imported lazily to avoid heavy loading on CLI/app startup
    # if embeddings aren't immediately needed.
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

def embed(text: str) -> np.ndarray:
    """
    Computes unit-normalized embeddings.
    """
    model = get_embedding_model()
    # MiniLM-L6-v2 produces 384 dimensional embeddings.
    embeddings = model.encode([text], normalize_embeddings=True)
    return embeddings[0].astype(np.float32)

def cosine_similarity(embedding1: np.ndarray, embedding2: np.ndarray) -> float:
    """
    Computes dot product, equivalent to cosine similarity for unit-normalized vectors.
    """
    return float(np.dot(embedding1, embedding2))
