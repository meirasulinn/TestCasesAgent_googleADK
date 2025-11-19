"""
ADK Tools for RAG integration.
Implements RAG search and caching as ADK Tools.
"""
import logging
import json
import hashlib
from typing import Dict, Any, Optional
import redis
from faiss import IndexFlatL2
import numpy as np
from google.adk.tools import BaseTool

logger = logging.getLogger(__name__)


class RAGSearchTool(BaseTool):
    """ADK Tool for RAG search (Redis + FAISS)."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6381):
        """Initialize RAG search tool with Redis and FAISS."""
        super().__init__(
            name="rag_search",
            description="Search for similar cached test cases using Redis and FAISS"
        )
        self.redis_client = redis.Redis(
            host=redis_host, 
            port=redis_port, 
            decode_responses=True, 
            socket_connect_timeout=5
        )
        self.index = IndexFlatL2(384)
        self.embeddings_store = []
        self.spec_to_id = {}
        logger.info("RAGSearchTool initialized with Redis and FAISS")
    
    def _hash_spec(self, spec: str) -> str:
        """Generate hash for spec."""
        return hashlib.md5(spec.encode()).hexdigest()
    
    def _embed_spec(self, spec: str) -> np.ndarray:
        """Generate embedding for spec (hash-based POC)."""
        spec_clean = spec.lower()[:200]
        embedding = np.array([ord(c) % 256 for c in spec_clean], dtype=np.float32)
        if len(embedding) < 384:
            embedding = np.pad(embedding, (0, 384 - len(embedding)), mode='constant')
        else:
            embedding = embedding[:384]
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding.reshape(1, -1)
    
    async def run_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Search RAG cache for similar specs."""
        spec = input_data.get("spec", "")
        spec_hash = self._hash_spec(spec)
        
        print(f"[RAGSearchTool] Searching cache for spec hash: {spec_hash}")
        
        # Check Redis first
        redis_key = f"spec:{spec_hash}"
        cached_result = self.redis_client.get(redis_key)
        if cached_result:
            print(f"[RAGSearchTool] Redis cache hit!")
            return {
                "source": "cache",
                "similarity": 1.0,
                "result": json.loads(cached_result)
            }
        
        # Check FAISS
        print(f"[RAGSearchTool] Checking FAISS (size={len(self.embeddings_store)})")
        if len(self.embeddings_store) > 0:
            embedding = self._embed_spec(spec)
            distances, indices = self.index.search(embedding, k=1)
            similarity = 1.0 / (1.0 + distances[0][0])
            print(f"[RAGSearchTool] FAISS similarity: {similarity:.4f}")
            
            if similarity > 0.7:
                similar_hash = list(self.spec_to_id.values())[indices[0][0]]
                cached_key = f"spec:{similar_hash}"
                cached_result = self.redis_client.get(cached_key)
                if cached_result:
                    print(f"[RAGSearchTool] FAISS cache hit!")
                    return {
                        "source": "faiss_cache",
                        "similarity": float(similarity),
                        "result": json.loads(cached_result)
                    }
        
        print(f"[RAGSearchTool] Cache miss - will generate")
        return {
            "source": "miss",
            "similarity": None,
            "result": None
        }


class RAGCacheTool(BaseTool):
    """ADK Tool for caching and indexing results."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6381):
        """Initialize cache tool."""
        super().__init__(
            name="rag_cache",
            description="Cache test cases in Redis and index in FAISS"
        )
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            decode_responses=True,
            socket_connect_timeout=5
        )
        self.index = IndexFlatL2(384)
        self.embeddings_store = []
        self.spec_to_id = {}
    
    def _hash_spec(self, spec: str) -> str:
        """Generate hash for spec."""
        return hashlib.md5(spec.encode()).hexdigest()
    
    def _embed_spec(self, spec: str) -> np.ndarray:
        """Generate embedding for spec."""
        spec_clean = spec.lower()[:200]
        embedding = np.array([ord(c) % 256 for c in spec_clean], dtype=np.float32)
        if len(embedding) < 384:
            embedding = np.pad(embedding, (0, 384 - len(embedding)), mode='constant')
        else:
            embedding = embedding[:384]
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)
        return embedding.reshape(1, -1)
    
    async def run_async(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Cache results in Redis and FAISS."""
        spec = input_data.get("spec", "")
        results = input_data.get("results", [])
        spec_hash = self._hash_spec(spec)
        
        print(f"[RAGCacheTool] Caching spec hash: {spec_hash}")
        
        # Store in Redis
        redis_key = f"spec:{spec_hash}"
        self.redis_client.setex(redis_key, 86400, json.dumps(results))
        print(f"[RAGCacheTool] Stored in Redis with TTL=24h")
        
        # Update FAISS
        embedding = self._embed_spec(spec)
        self.embeddings_store.append(embedding[0])
        self.index.add(embedding)
        self.spec_to_id[len(self.embeddings_store) - 1] = spec_hash
        print(f"[RAGCacheTool] Updated FAISS index (size={len(self.embeddings_store)})")
        
        return {"status": "cached", "key": redis_key}
