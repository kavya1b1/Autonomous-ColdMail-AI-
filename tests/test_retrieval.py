from services.hybrid_retrieval import HybridRetriever

class FakeEmbedder:
    def encode(self, texts, normalize_embeddings=True, show_progress_bar=False):
        import numpy as np
        if isinstance(texts, str): texts = [texts]
        vectors=[]
        for text in texts:
            t=text.lower(); vectors.append([1.0 if "python" in t else 0.0, 1.0 if "rag" in t else 0.0, 1.0])
        return np.array(vectors)

def test_hybrid_retrieval_returns_ranked_documents():
    docs=[{"id":"a","text":"Python RAG project"},{"id":"b","text":"Marketing project"}]
    results=HybridRetriever(docs, embedder=FakeEmbedder()).search("Python RAG", k=1)
    assert results[0]["id"] == "a"
