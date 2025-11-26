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


import os
import threading

class FAISSService:
    """
    Shared FAISS service per agent type (singleton).
    Persistent index (saved/loaded from disk).
    """
    _instances: Dict[str, 'FAISSService'] = {}
    _lock = threading.Lock()

    def __new__(cls, agent_type: str):
        if agent_type not in cls._instances:
            with cls._lock:
                if agent_type not in cls._instances:
                    instance = super().__new__(cls)
                    cls._instances[agent_type] = instance
        return cls._instances[agent_type]

    def __init__(self, agent_type: str):
        if hasattr(self, '_initialized'):
            return
        self.agent_type = agent_type
        self.dimension = settings.FAISS_DIMENSION
        self.index_path = f"./faiss_indexes/{agent_type}.index"
        self.documents_path = f"./faiss_indexes/{agent_type}_docs.json"
        self.metadata_path = f"./faiss_indexes/{agent_type}_meta.json"
        os.makedirs("./faiss_indexes", exist_ok=True)
        if os.path.exists(self.index_path):
            self.index = faiss.read_index(self.index_path)
        else:
            self.index = faiss.IndexFlatL2(self.dimension)
        # Load docs/metadata
        import json
        if os.path.exists(self.documents_path):
            with open(self.documents_path, "r", encoding="utf-8") as f:
                self.documents = json.load(f)
        else:
            self.documents = []
        if os.path.exists(self.metadata_path):
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)
        else:
            self.metadata = []
        self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self._initialized = True
        logger.info(f"FAISSService initialized for agent type '{agent_type}' (docs: {len(self.documents)})")
    
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
    
    def add_document(self, text: str, metadata: Optional[Dict[str, Any]] = None, store_text: bool = True):
        """
        Add a document to the FAISS index.
        Args:
            text: Document text
            metadata: Optional metadata about the document
            store_text: Should store the text (default True)
        """
        embedding = self._get_embedding(text)
        self.index.add(np.array([embedding]))
        self.documents.append(text if store_text else "")
        self.metadata.append(metadata or {})
        self.save()
        logger.info(f"Added document to FAISS index for agent '{self.agent_type}' (total: {len(self.documents)})")

    def save(self):
        faiss.write_index(self.index, self.index_path)
        import json
        with open(self.documents_path, "w", encoding="utf-8") as f:
            json.dump(self.documents, f)
        with open(self.metadata_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f)
    
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
            logger.warning(f"No documents in FAISS index for agent '{self.agent_type}'")
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
        
        logger.info(f"FAISS search for agent '{self.agent_type}': {len(results)} results above threshold")
        return results
    
    def clear(self):
        """Clear the FAISS index."""
        self.index = faiss.IndexFlatL2(self.dimension)
        self.documents = []
        self.metadata = []
        self.save()
        logger.info(f"Cleared FAISS index for agent '{self.agent_type}'")
    
    def size(self) -> int:
        """Get number of documents in index."""
        return len(self.documents)
