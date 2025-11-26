"""
FAISS-based semantic search service (OPTIONAL).
Provides per-user vector search using OpenAI embeddings.
Each user gets their own FAISS instance for isolation.
"""
import logging
from typing import List, Dict, Any, Optional
import numpy as np
import faiss
from openai import AsyncOpenAI
from config.settings import settings

logger = logging.getLogger(__name__)


class FAISSService:
    """
    FAISS-based semantic search for a specific user.
    
    Features:
    - Per-user isolation
    - OpenAI embeddings (text-embedding-ada-002)
    - Fast similarity search
    - In-memory storage
    
    Note: This is OPTIONAL. Remove if you don't need semantic search.
    """
    
    def __init__(self, user_id: str):
        """
        Initialize FAISS service for a user.
        
        Args:
            user_id: User identifier
        """
        self.user_id = user_id
        self.dimension = settings.FAISS_DIMENSION
        self.similarity_threshold = settings.FAISS_SIMILARITY_THRESHOLD
        
        # Initialize FAISS index (L2 distance)
        self.index = faiss.IndexFlatL2(self.dimension)
        
        # Store original documents and metadata
        self.documents: List[str] = []
        self.metadata: List[Dict[str, Any]] = []
        
        # OpenAI client for embeddings
        self.openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        
        logger.info(f"FAISSService initialized for user {user_id}")
    
    async def _create_embedding(self, text: str) -> List[float]:
        """
        Create embedding for text using OpenAI.
        
        Args:
            text: Text to embed
        
        Returns:
            Embedding vector
        """
        try:
            response = await self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            raise
    
    async def add_document(self, text: str, metadata: Dict[str, Any]):
        """
        Add document to FAISS index.
        
        Args:
            text: Document text
            metadata: Document metadata
        """
        try:
            # Create embedding
            embedding = await self._create_embedding(text)
            
            # Convert to numpy array
            vector = np.array([embedding], dtype='float32')
            
            # Add to FAISS index
            self.index.add(vector)
            
            # Store document and metadata
            self.documents.append(text)
            self.metadata.append(metadata)
            
            logger.info(f"Added document to FAISS for user {self.user_id} (total: {len(self.documents)})")
        except Exception as e:
            logger.error(f"Failed to add document to FAISS: {e}")
            raise
    
    async def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Search for similar documents.
        
        Args:
            query: Search query
            top_k: Number of results to return
        
        Returns:
            List of similar documents with metadata and similarity scores
        """
        if self.index.ntotal == 0:
            logger.warning(f"FAISS index empty for user {self.user_id}")
            return []
        
        try:
            # Create query embedding
            query_embedding = await self._create_embedding(query)
            query_vector = np.array([query_embedding], dtype='float32')
            
            # Search FAISS index
            distances, indices = self.index.search(query_vector, min(top_k, self.index.ntotal))
            
            # Convert to results
            results = []
            for i, (distance, idx) in enumerate(zip(distances[0], indices[0])):
                if idx < len(self.documents):
                    # Convert L2 distance to similarity score (0-1)
                    similarity = 1 / (1 + distance)
                    
                    if similarity >= self.similarity_threshold:
                        results.append({
                            "document": self.documents[idx],
                            "metadata": self.metadata[idx],
                            "similarity": float(similarity),
                            "rank": i + 1
                        })
            
            logger.info(f"FAISS search for user {self.user_id}: {len(results)} results above threshold")
            return results
        except Exception as e:
            logger.error(f"Failed to search FAISS: {e}")
            return []
    
    def size(self) -> int:
        """Get number of documents in index."""
        return len(self.documents)
