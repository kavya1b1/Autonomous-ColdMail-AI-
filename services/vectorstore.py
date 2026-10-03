"""ChromaDB vector store service for RAG"""
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Any, Optional
from config.settings import settings
from config.logging import logger


class VectorStoreService:
    """ChromaDB vector store with semantic search"""

    def __init__(self):
        self.client = chromadb.PersistentClient(
            path=settings.CHROMA_PERSIST_DIR,
            settings=ChromaSettings(anonymized_telemetry=False)
        )
        self.collection = self.client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION
        )
        self.embedder = SentenceTransformer(settings.EMBEDDING_MODEL)
        logger.info("VectorStoreService initialized")

    def add_company(self, company_id: str, company_data: Dict[str, Any]) -> bool:
        """Add company profile to vector store"""
        try:
            text = f"{company_data.get('name', '')} {company_data.get('description', '')} "
            text += f"{company_data.get('industry', '')} {' '.join(company_data.get('tech_stack', []))}"

            embedding = self.embedder.encode(text).tolist()

            self.collection.add(
                ids=[f"company_{company_id}"],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{**company_data, "record_type": "company"}]
            )
            logger.info(f"Company added to vector store: {company_id}")
            return True
        except Exception as e:
            logger.error(f"Vector store add error: {e}")
            return False

    def add_email(self, email_id: str, email_data: Dict[str, Any]) -> bool:
        """Add generated email to vector store"""
        try:
            text = f"{email_data.get('subject', '')} {email_data.get('body', '')}"
            embedding = self.embedder.encode(text).tolist()

            self.collection.add(
                ids=[f"email_{email_id}"],
                embeddings=[embedding],
                documents=[text],
                metadatas=[{**email_data, "record_type": "email"}]
            )
            return True
        except Exception as e:
            logger.error(f"Vector store add email error: {e}")
            return False

    def search_similar_companies(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for similar companies"""
        try:
            embedding = self.embedder.encode(query).tolist()
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where={"record_type": "company"}
            )
            return results.get("metadatas", [[]])[0]
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def search_similar_emails(self, query: str, n_results: int = 5) -> List[Dict]:
        """Search for similar emails (for RAG context)"""
        try:
            embedding = self.embedder.encode(query).tolist()
            results = self.collection.query(
                query_embeddings=[embedding],
                n_results=n_results,
                where={"record_type": "email"}
            )
            return results.get("metadatas", [[]])[0]
        except Exception as e:
            logger.error(f"Vector search error: {e}")
            return []

    def get_relevant_context(self, company_name: str, skills: List[str]) -> str:
        """Get relevant context for email generation"""
        query = f"{company_name} {' '.join(skills)}"
        similar = self.search_similar_emails(query, n_results=3)

        context_parts = []
        for item in similar:
            if item and "body" in item:
                context_parts.append(f"Previous successful email: {item['body'][:200]}...")

        return "\n".join(context_parts) if context_parts else ""
