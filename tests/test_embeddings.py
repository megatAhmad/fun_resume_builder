import numpy as np
from embeddings import embed, cosine_similarity, STRONG_MATCH_THRESHOLD, GAP_BRIDGE_THRESHOLD

def test_embed():
    text = "Software Engineer at Tech Corp"
    emb = embed(text)
    assert isinstance(emb, np.ndarray)
    assert emb.shape == (384,)
    assert emb.dtype == np.float32
    # Verify unit-normalized length
    assert np.isclose(np.linalg.norm(emb), 1.0, atol=1e-5)

def test_cosine_similarity():
    emb1 = embed("Python developer")
    emb2 = embed("Python software engineer")
    emb3 = embed("Accountant at a bank")

    score_similar = cosine_similarity(emb1, emb2)
    score_different = cosine_similarity(emb1, emb3)

    assert score_similar > score_different
    assert score_similar > 0.5
    assert score_different < 0.5
