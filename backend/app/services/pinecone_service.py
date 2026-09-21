"""
Pinecone Vector Database Service.
Provides index management, deterministic vector upsert, vector deletion, namespace management,
and semantic retrieval abstractions.
"""

import logging
from typing import Any, Dict, List, Optional
from backend.app.config import settings

logger = logging.getLogger(__name__)


class PineconeService:
    _instance: Optional["PineconeService"] = None

    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.environment = settings.PINECONE_ENVIRONMENT
        self.index_name = settings.PINECONE_INDEX_NAME
        self.namespace_prefix = settings.PINECONE_NAMESPACE_PREFIX
        self.dimension = settings.PINECONE_DIMENSION
        self.metric = settings.PINECONE_METRIC
        self.client = None
        self.is_connected = False
        self._in_memory_vectors: Dict[str, Dict[str, Any]] = {}
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Pinecone client connection if valid credentials are provided."""
        if not self.api_key or "placeholder" in self.api_key:
            self.is_connected = False
            return

        try:
            from pinecone import Pinecone
            self.client = Pinecone(api_key=self.api_key)
            self.is_connected = True
        except Exception as e:
            logger.warning(f"Pinecone connection initialization failed: {e}")
            self.is_connected = False

    def health_check(self) -> Dict[str, Any]:
        """Return connectivity status and configured index metadata."""
        return {
            "status": "connected" if self.is_connected else "configured_placeholder",
            "index_name": self.index_name,
            "environment": self.environment,
            "namespace_prefix": self.namespace_prefix,
            "dimension": self.dimension,
            "metric": self.metric,
            "embedding_model": settings.EMBEDDING_MODEL,
            "in_memory_vectors_count": len(self._in_memory_vectors),
        }

    def get_namespace(self, collection_id: Optional[str] = None) -> str:
        """Construct deterministic Pinecone namespace."""
        if collection_id:
            return f"{self.namespace_prefix}:{collection_id}"
        return self.namespace_prefix

    def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Upsert embedded document chunk vectors with metadata payload.
        Idempotent by deterministic vector ID.
        """
        if not vectors:
            return True

        target_namespace = namespace or self.namespace_prefix

        # Always maintain in-memory store for local testing/fallback
        for v in vectors:
            key = f"{target_namespace}:{v['id']}"
            self._in_memory_vectors[key] = {
                "id": v["id"],
                "values": v.get("values", []),
                "metadata": dict(v.get("metadata") or {}),
                "namespace": target_namespace,
            }

        if not self.is_connected or not self.client:
            logger.info(f"[Pinecone Stub] Successfully upserted {len(vectors)} vectors in placeholder mode.")
            return True

        try:
            index = self.client.Index(self.index_name)
            batch_size = 100
            for i in range(0, len(vectors), batch_size):
                batch = vectors[i : i + batch_size]
                index.upsert(vectors=batch, namespace=target_namespace)
            return True
        except Exception as e:
            logger.error(f"Pinecone upsert error: {e}")
            raise RuntimeError(f"Pinecone vector upsert failed: {str(e)}") from e

    def delete_vectors(
        self,
        ids: Optional[List[str]] = None,
        filter_dict: Optional[Dict[str, Any]] = None,
        delete_all: bool = False,
        namespace: Optional[str] = None,
    ) -> bool:
        """
        Delete vectors by deterministic IDs, metadata filter, or wipe namespace.
        """
        target_namespace = namespace or self.namespace_prefix

        # Remove from in-memory fallback store
        if delete_all:
            keys_to_del = [k for k, v in self._in_memory_vectors.items() if v["namespace"] == target_namespace]
            for k in keys_to_del:
                self._in_memory_vectors.pop(k, None)
        elif ids:
            for vec_id in ids:
                key = f"{target_namespace}:{vec_id}"
                self._in_memory_vectors.pop(key, None)
        elif filter_dict:
            keys_to_del = []
            for k, v in self._in_memory_vectors.items():
                if v["namespace"] == target_namespace:
                    match = True
                    for f_key, f_val in filter_dict.items():
                        if v["metadata"].get(f_key) != f_val:
                            match = False
                            break
                    if match:
                        keys_to_del.append(k)
            for k in keys_to_del:
                self._in_memory_vectors.pop(k, None)

        if not self.is_connected or not self.client:
            logger.info(f"[Pinecone Stub] Successfully deleted vectors in placeholder mode.")
            return True

        try:
            index = self.client.Index(self.index_name)
            if delete_all:
                index.delete(delete_all=True, namespace=target_namespace)
            elif ids:
                batch_size = 100
                for i in range(0, len(ids), batch_size):
                    batch = ids[i : i + batch_size]
                    index.delete(ids=batch, namespace=target_namespace)
            elif filter_dict:
                index.delete(filter=filter_dict, namespace=target_namespace)
            return True
        except Exception as e:
            logger.error(f"Pinecone vector deletion error: {e}")
            raise RuntimeError(f"Pinecone vector deletion failed: {str(e)}") from e

    def query_vectors(
        self,
        vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Query nearest neighbor chunk vectors filtered by collection/version/metadata."""
        target_namespace = namespace or self.namespace_prefix

        if self.is_connected and self.client:
            try:
                index = self.client.Index(self.index_name)
                res = index.query(
                    vector=vector,
                    top_k=top_k,
                    filter=filter_dict,
                    include_metadata=True,
                    namespace=target_namespace,
                )
                return res.get("matches", [])
            except Exception as e:
                logger.error(f"Pinecone vector query error: {e}")

        # In-memory cosine similarity search (fallback / local testing mode)
        import math

        candidates = []
        for v in self._in_memory_vectors.values():
            if namespace and v["namespace"] != target_namespace:
                continue

            # Check metadata filters
            if filter_dict:
                match = True
                for f_k, f_v in filter_dict.items():
                    if f_k in v["metadata"]:
                        val = v["metadata"][f_k]
                        if isinstance(f_v, bool):
                            if bool(val) != f_v:
                                match = False
                                break
                        elif str(val).lower() != str(f_v).lower():
                            match = False
                            break
                if not match:
                    continue

            cand_vec = v["values"]
            if cand_vec and len(cand_vec) == len(vector):
                dot = sum(a * b for a, b in zip(vector, cand_vec))
                norm1 = math.sqrt(sum(a * a for a in vector))
                norm2 = math.sqrt(sum(b * b for b in cand_vec))
                cos_sim = dot / (norm1 * norm2) if (norm1 > 0 and norm2 > 0) else 0.0
                raw_score = max(0.0, min(1.0, cos_sim))
                candidates.append({
                    "id": v["id"],
                    "score": round(raw_score, 4),
                    "metadata": v["metadata"],
                })

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:top_k]


pinecone_service = PineconeService()
