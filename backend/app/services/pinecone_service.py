"""
Pinecone Vector Database Service.
Provides index management, vector upsert, and semantic retrieval abstractions.
"""

from typing import Any, Dict, List, Optional
from backend.app.config import settings


class PineconeService:
    _instance: Optional["PineconeService"] = None

    def __init__(self):
        self.api_key = settings.PINECONE_API_KEY
        self.environment = settings.PINECONE_ENVIRONMENT
        self.index_name = settings.PINECONE_INDEX_NAME
        self.dimension = settings.PINECONE_DIMENSION
        self.metric = settings.PINECONE_METRIC
        self.client = None
        self.is_connected = False
        self._init_client()

    def _init_client(self) -> None:
        """Initialize Pinecone client connection if valid credentials are provided."""
        if not self.api_key or "placeholder" in self.api_key:
            # Graceful placeholder mode for local development before AI pipeline prompt
            self.is_connected = False
            return

        try:
            # pinecone v3 client
            from pinecone import Pinecone
            self.client = Pinecone(api_key=self.api_key)
            self.is_connected = True
        except Exception:
            self.is_connected = False

    def health_check(self) -> Dict[str, Any]:
        """Return connectivity status and configured index metadata."""
        return {
            "status": "connected" if self.is_connected else "configured_placeholder",
            "index_name": self.index_name,
            "environment": self.environment,
            "dimension": self.dimension,
            "metric": self.metric,
        }

    def upsert_vectors(
        self,
        vectors: List[Dict[str, Any]],
        namespace: Optional[str] = None
    ) -> bool:
        """Upsert embedded document chunk vectors with metadata payload."""
        if not self.is_connected or not self.client:
            return True  # Stubbed success in placeholder mode

        try:
            index = self.client.Index(self.index_name)
            index.upsert(vectors=vectors, namespace=namespace)
            return True
        except Exception:
            return False

    def query_vectors(
        self,
        vector: List[float],
        top_k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None,
        namespace: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Query nearest neighbor chunk vectors filtered by collection/version."""
        if not self.is_connected or not self.client:
            return []

        try:
            index = self.client.Index(self.index_name)
            res = index.query(
                vector=vector,
                top_k=top_k,
                filter=filter_dict,
                include_metadata=True,
                namespace=namespace
            )
            return res.get("matches", [])
        except Exception:
            return []


pinecone_service = PineconeService()
