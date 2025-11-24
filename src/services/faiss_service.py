"""
FAISS-based vector search service for session-local semantic search.
Each user session gets its own FAISS index.
"""
import logging
import numpy as np
import faiss
from typing import List, Dict, Any, Optional
from openai import OpenAI
from src.config.settings import settings

logger = logging.getLogger(__name__)


class FAISSService:
    """
    Session-local FAISS service for semantic search.
    
    Features:
    - One FAISS index per user session
    - OpenAI embeddings for vectorization
    - Fast similarity search within user's data
    """
    
    def __init__(self, user_id: str):
        """
        Initialize FAISS service for a specific user session.
        
        Args:
            user_id: Unique user identifier
        """
        self.user_id = user_id
        self.dimension = settings.FAISS_DIMENSION
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        
        logger.info(f"FAISSService initialized for user {user_id}")
    
    def _get_embedding(self, text: str) -> np.ndarray:
        """
        Get OpenAI embedding for text.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector as numpy array
        """
        response = self.openai_client.embeddings.create(
            model="text-embedding-ada-002",
            input=text
        )
        embedding = response.data[0].embedding
        return np.array(embedding, dtype=np.float32)
    
    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Add a document to the FAISS index.
        
        Args:
            text: Document text
            metadata: Optional metadata about the document
        """
        embedding = self._get_embedding(text)
        self.index.add(np.array([embedding]))
        self.documents.append(text)
        self.metadata.append(metadata or {})
        
        logger.info(f"Added document to FAISS index for user {self.user_id} (total: {len(self.documents)})")
    
    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of results with text, metadata, and similarity score
        """
        if len(self.documents) == 0:
            logger.warning(f"No documents in FAISS index for user {self.user_id}")
            return []
        
        query_embedding = self._get_embedding(query)
        distances, indices = self.index.search(np.array([query_embedding]), min(top_k, len(self.documents)))
        
        results = []
        for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
            if idx < len(self.documents):
                # Convert L2 distance to similarity (0-1 range, higher is better)
                similarity = 1 / (1 + distance)
                
                if similarity >= settings.FAISS_SIMILARITY_THRESHOLD:
                    results.append({
                        "text": self.documents[idx],
                        "metadata": self.metadata[idx],
                        "similarity": float(similarity),
                        "rank": i + 1
                    })
        
        logger.info(f"FAISS search for user {self.user_id}: {len(results)} results above threshold")
        return results
    
    def clear(self):
        """Clear the FAISS index."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.metadata = []
        logger.info(f"Cleared FAISS index for user {self.user_id}")
    
    def size(self) -> int:
        """Get number of documents in index."""
        return len(self.documents)
