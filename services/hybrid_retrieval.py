"""Lightweight hybrid BM25 + dense retrieval for portfolio evidence."""
import re
from functools import lru_cache
from typing import Any, Dict, List


from config.logging import logger
from config.settings import settings


@lru_cache(maxsize=1)
def get_embedder():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(settings.EMBEDDING_MODEL)


class HybridRetriever:
    def __init__(self, documents: List[Dict[str, Any]], embedder=None):
        self.documents = documents or []
        self.embedder = embedder or get_embedder()
        try:
            from rank_bm25 import BM25Okapi
            self._bm25 = BM25Okapi([self._tokens(d.get("text", "")) for d in self.documents]) if self.documents else None
        except ImportError:
            self._bm25 = None
        self._embeddings = self.embedder.encode(
            [d.get("text", "") for d in self.documents],
            normalize_embeddings=True,
            show_progress_bar=False,
        ) if self.documents else None

    @staticmethod
    def _tokens(text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9+#./-]+", (text or "").lower())

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        if not self.documents:
            return []
        k = min(max(1, k), len(self.documents))
        if self._bm25:
            sparse = self._bm25.get_scores(self._tokens(query))
        else:
            query_tokens = set(self._tokens(query))
            sparse = [len(query_tokens & set(self._tokens(d.get("text", "")))) for d in self.documents]
        q = self.embedder.encode(query, normalize_embeddings=True, show_progress_bar=False)
        try:
            import numpy as np
            q = np.asarray(q).reshape(-1)
        except Exception:
            pass
        dense = self._embeddings @ q
        s_min, s_max = min(sparse), max(sparse)
        s_range = (s_max - s_min) or 1.0
        ranked = []
        for i, doc in enumerate(self.documents):
            sparse_norm = (float(sparse[i]) - s_min) / s_range
            dense_norm = (float(dense[i]) + 1.0) / 2.0
            score = 0.45 * sparse_norm + 0.55 * dense_norm
            ranked.append((score, doc))
        ranked.sort(key=lambda x: x[0], reverse=True)
        return [{**doc, "retrieval_score": round(score, 4)} for score, doc in ranked[:k]]


def build_profile_documents(profile) -> List[Dict[str, Any]]:
    docs = []
    if getattr(profile, "resume_text", None):
        text = profile.resume_text
        chunks = [text[i:i + 1200] for i in range(0, len(text), 1000)]
        docs.extend({"id": f"resume_{i}", "text": chunk, "source": "resume"} for i, chunk in enumerate(chunks) if chunk.strip())
    if getattr(profile, "skills", None):
        docs.append({"id": "skills", "text": "Skills: " + ", ".join(profile.skills), "source": "profile"})
    if getattr(profile, "objective", None):
        docs.append({"id": "objective", "text": profile.objective, "source": "profile"})
    return docs
