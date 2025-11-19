"""
RAG Layer: Semantic search with FAISS + caching with Redis.
Retrieves similar specs from cache and returns enhanced context for LLM.
"""
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional

import redis
from faiss import IndexFlatL2
import numpy as np

logger = logging.getLogger(__name__)

class RAGRetriever:
    """Manages semantic search (FAISS) and result caching (Redis)."""
    
    def __init__(self, redis_host: str = "localhost", redis_port: int = 6381, 
                 index_dimension: int = 384):
        """Initialize FAISS index and Redis connection."""
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, 
                                        decode_responses=True, socket_connect_timeout=5)
        self.index = IndexFlatL2(index_dimension)
        self.embeddings_store = []  # Store embeddings in memory (simple; scale with DB)
        self.spec_to_id = {}  # Map spec hash → index ID
        self.id_to_result = {}  # Store results locally
        logger.info("RAGRetriever initialized with Redis and FAISS.")
    
    def _hash_spec(self, spec: str) -> str:
        """Generate hash for spec."""
        return hashlib.md5(spec.encode()).hexdigest()
    
    def _embed_spec(self, spec: str) -> np.ndarray:
        """Generate embedding for spec (placeholder; use real embedding model in production)."""
        # Simple hash-based embedding for POC; replace with SentenceTransformer, OpenAI embeddings, etc.
        spec_clean = spec.lower()[:200]
        embedding = np.array([ord(c) % 256 for c in spec_clean], dtype=np.float32)
        # Pad/truncate to 384 dims
        if len(embedding) < 384:
            embedding = np.pad(embedding, (0, 384 - len(embedding)), mode='constant')
        else:
            embedding = embedding[:384]
        embedding = embedding / (np.linalg.norm(embedding) + 1e-8)  # Normalize
        return embedding.reshape(1, -1)
    
    def lookup_or_generate(self, spec: str, 
                          generator_func) -> Dict[str, Any]:
        """
        Check cache/FAISS for similar spec. If hit, return cached result.
        If miss, call generator_func to produce new result, cache it, return it.
        
        Args:
            spec: Input specification text.
            generator_func: Callable that takes spec and returns result dict.
        
        Returns:
            Dict with keys: {
                "source": "cache" | "generated",
                "similarity": float (if cache hit),
                "result": {...test cases...}
            }
        """
        spec_hash = self._hash_spec(spec)
        print(f"[RAG] lookup_or_generate called. Spec hash: {spec_hash}")
        
        # Check Redis first (exact match)
        redis_key = f"spec:{spec_hash}"
        print(f"[RAG] Redis key: {redis_key}")
        print(f"[RAG] Attempting to get from Redis...")
        try:
            cached_result = self.redis_client.get(redis_key)
        except Exception as e:
            print(f"[RAG] ERROR getting from Redis: {e}")
            cached_result = None
        print(f"[RAG] Redis get result: type={type(cached_result)}, value={cached_result if cached_result is None else '(len=' + str(len(cached_result)) + ')'}")
        if cached_result:
            msg = f"[RAG] Cache hit (Redis) for spec hash {spec_hash}"
            print(msg)
            logger.info(msg)
            return {
                "source": "cache",
                "similarity": 1.0,
                "result": json.loads(cached_result)
            }
        else:
            print(f"[RAG] No Redis cache hit, will check FAISS")
        
        # Check FAISS for similar specs
        print(f"[RAG] Checking FAISS index. Current size: {len(self.embeddings_store)}")
        if len(self.embeddings_store) > 0:
            embedding = self._embed_spec(spec)
            distances, indices = self.index.search(embedding, k=1)
            similarity = 1.0 / (1.0 + distances[0][0])  # Convert distance to similarity
            print(f"[RAG] FAISS search: similarity={similarity:.4f}, threshold=0.7")
            if similarity > 0.7:  # Threshold for "similar enough"
                similar_hash = list(self.spec_to_id.values())[indices[0][0]]
                cached_key = f"spec:{similar_hash}"
                cached_result = self.redis_client.get(cached_key)
                if cached_result:
                    msg = f"[RAG] FAISS hit (similarity={similarity:.2f}) for spec hash {spec_hash}"
                    print(msg)
                    logger.info(msg)
                    return {
                        "source": "faiss_cache",
                        "similarity": float(similarity),
                        "result": json.loads(cached_result)
                    }
            else:
                print(f"[RAG] FAISS similarity below threshold ({similarity:.4f} < 0.7), will generate new")
        else:
            print(f"[RAG] FAISS index is empty, will generate new")
        
        # Cache miss: generate new result
        msg = f"[RAG] Cache miss for spec hash {spec_hash}; calling generator_func..."
        print(msg)
        logger.info(msg)
        result = generator_func(spec)
        print(f"[RAG] Generator returned result with {len(result)} items")
        
        # Store in Redis
        self.redis_client.setex(redis_key, 86400, json.dumps(result))  # 24h TTL
        print(f"[RAG] Stored result in Redis with key {redis_key}")
        
        # Update FAISS index
        embedding = self._embed_spec(spec)
        self.embeddings_store.append(embedding[0])
        self.index.add(embedding)
        self.spec_to_id[len(self.embeddings_store) - 1] = spec_hash
        print(f"[RAG] Updated FAISS index. New size: {len(self.embeddings_store)}")
        
        msg = f"[RAG] Stored result in cache for spec hash {spec_hash}"
        logger.info(msg)
        return {
            "source": "generated",
            "similarity": None,
            "result": result
        }
    
    def enhance_prompt_with_context(self, spec: str, cached_similar: Optional[Dict]) -> str:
        """
        If RAG returned a similar cached result, enhance the prompt with that context.
        
        Args:
            spec: Original spec.
            cached_similar: Result dict from lookup_or_generate (if source is cache/faiss_cache).
        
        Returns:
            Enhanced prompt string.
        """
        if not cached_similar or cached_similar["source"] == "generated":
            return spec
        
        # Augment prompt with similar test cases for few-shot learning
        similar_cases = cached_similar["result"].get("test_cases", [])
        if similar_cases:
            context = "Similar test cases from cache (for reference):\n"
            for tc in similar_cases[:3]:  # Limit to 3 examples
                context += f"- {tc.get('title', 'N/A')}\n"
            return f"{spec}\n\n{context}"
        return spec
