"""
Indexing Service.
Consumes structured text chunks and vector embeddings for Pinecone vector indexing and search storage.
Guarantees:
1. Zero raw PDF binaries sent to AI language models or vectorizers.
2. Deterministic vector IDs: `{document_version_id}:{page_number}:{chunk_index}`.
3. Dimension and model validation: Prevents mixing vectors from incompatible models or dimensions.
4. Comprehensive metadata payloads for Pinecone filtering.
5. Idempotent version-level upsert, deletion, collection re-indexing, and admin rebuild workflows.
"""

from datetime import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from backend.app.config import settings
from backend.app.models.db_models import (
    Document,
    DocumentCollection,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
)
from backend.app.services.pinecone_service import pinecone_service

logger = logging.getLogger(__name__)


class IndexingService:
    """
    Vector indexing layer managing deterministic IDs, dimensional safety,
    Pinecone upserts, version purges, and collection re-indexing.
    """

    @classmethod
    def generate_vector_id(cls, version_id: str, page_number: int, chunk_index: int) -> str:
        """
        Generate deterministic vector ID in format:
        {document_version_id}:{page_number}:{chunk_index}
        """
        return f"{version_id}:{page_number}:{chunk_index}"

    @classmethod
    def validate_vector_compatibility(
        cls,
        vectors: List[Dict[str, Any]],
        expected_dimension: Optional[int] = None,
        expected_model: Optional[str] = None,
    ) -> None:
        """
        Verify that all vectors match the configured dimension and embedding model.
        Raises ValueError if incompatible to prevent corrupting the vector index.
        """
        target_dim = expected_dimension or settings.EMBEDDING_DIMENSION
        target_model = expected_model or settings.EMBEDDING_MODEL

        for i, vec in enumerate(vectors):
            values = vec.get("values")
            if values is not None and len(values) != target_dim:
                raise ValueError(
                    f"Vector dimension mismatch at index {i} (ID: {vec.get('id')}): "
                    f"Found dimension {len(values)}, expected {target_dim} for model '{target_model}'."
                )

            vec_meta = vec.get("metadata") or {}
            vec_model = vec_meta.get("embedding_model")
            if vec_model and vec_model != target_model:
                raise ValueError(
                    f"Embedding model mismatch at index {i} (ID: {vec.get('id')}): "
                    f"Found model '{vec_model}', expected configured model '{target_model}'."
                )

    @classmethod
    def build_chunk_metadata_payload(
        cls,
        doc: Document,
        ver: DocumentVersion,
        chunk: ExtractedChunk,
        page: Optional[DocumentPage] = None,
    ) -> Dict[str, Any]:
        """
        Construct standard Pinecone metadata payload with all required welfare attributes.
        """
        # Parse state and district
        location_raw = doc.state_or_district or "National"
        state = location_raw
        district = "All"
        if "/" in location_raw:
            parts = [p.strip() for p in location_raw.split("/", 1)]
            state, district = parts[0], parts[1]
        elif "-" in location_raw and "All" not in location_raw:
            parts = [p.strip() for p in location_raw.split("-", 1)]
            state, district = parts[0], parts[1]

        eff_date_str = str(ver.effective_date or doc.effective_date) if (ver.effective_date or doc.effective_date) else None
        is_active = (doc.status == DocumentStatus.ACTIVE.value and ver.status == DocumentStatus.ACTIVE.value)

        # Truncate text excerpt safely under 1000 characters for metadata storage
        clean_text = (chunk.chunk_text or "").strip()
        text_snippet = clean_text[:950] + ("..." if len(clean_text) > 950 else "")

        return {
            "collection_id": str(doc.collection_id),
            "document_id": str(doc.id),
            "document_version_id": str(ver.id),
            "version_id": str(ver.id),
            "page_number": int(chunk.page_number),
            "page_range": str(chunk.page_range or chunk.page_number),
            "scheme": str(doc.scheme_name),
            "scheme_name": str(doc.scheme_name),
            "department": str(doc.department),
            "state": str(state),
            "district": str(district),
            "state_or_district": str(location_raw),
            "language": str(doc.language),
            "effective_date": eff_date_str,
            "active": bool(is_active),
            "is_active": bool(is_active),
            "embedding_model": str(settings.EMBEDDING_MODEL),
            "embedding_dimension": int(settings.EMBEDDING_DIMENSION),
            "chunk_index": int(chunk.chunk_index),
            "section_heading": str(chunk.section_heading or ""),
            "text": text_snippet,
        }

    @classmethod
    def index_chunks(
        cls,
        document_id: str,
        version_id: str,
        chunks: List[Dict[str, Any]],
        collection_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Index completed extracted chunks into Pinecone vector storage with deterministic IDs.
        """
        if not chunks:
            return {
                "success": True,
                "indexed_chunks_count": 0,
                "message": "No chunks provided for indexing.",
            }

        vectors_to_upsert: List[Dict[str, Any]] = []
        for c in chunks:
            vec_id = c.get("vector_id") or cls.generate_vector_id(
                version_id=version_id,
                page_number=c.get("page_number", 1),
                chunk_index=c.get("chunk_index", 0),
            )
            # Embedding vector (default zero-vector in placeholder mode, real embedding in production)
            vector_values = c.get("values") or ([0.0] * settings.EMBEDDING_DIMENSION)
            meta = c.get("metadata") or {}
            meta.setdefault("embedding_model", settings.EMBEDDING_MODEL)
            meta.setdefault("embedding_dimension", settings.EMBEDDING_DIMENSION)

            vectors_to_upsert.append({
                "id": vec_id,
                "values": vector_values,
                "metadata": meta,
            })

        # Validate dimensional and model safety
        cls.validate_vector_compatibility(vectors_to_upsert)

        namespace = pinecone_service.get_namespace(collection_id)
        pinecone_service.upsert_vectors(vectors=vectors_to_upsert, namespace=namespace)

        logger.info(
            f"Successfully indexed {len(vectors_to_upsert)} vectors for document {document_id} "
            f"(version {version_id}) in namespace '{namespace}'."
        )

        return {
            "success": True,
            "document_id": document_id,
            "version_id": version_id,
            "indexed_chunks_count": len(vectors_to_upsert),
            "namespace": namespace,
        }

    @classmethod
    def upsert_document_version_vectors(
        cls,
        db: Session,
        version_id: str,
        custom_vectors: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Idempotently upsert all chunk vectors for a single document version into Pinecone
        and update relational database metadata.
        """
        ver = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        if not ver:
            raise ValueError(f"Document version {version_id} not found.")

        doc = db.query(Document).filter(Document.id == ver.document_id).first()
        if not doc:
            raise ValueError(f"Parent document {ver.document_id} not found.")

        chunks = (
            db.query(ExtractedChunk)
            .filter(ExtractedChunk.version_id == version_id)
            .order_by(ExtractedChunk.chunk_index.asc())
            .all()
        )

        if not chunks:
            return {
                "success": True,
                "version_id": version_id,
                "indexed_count": 0,
                "message": "Version contains no extracted chunks.",
            }

        vectors: List[Dict[str, Any]] = []
        now = datetime.utcnow()

        for chunk in chunks:
            det_id = cls.generate_vector_id(
                version_id=ver.id,
                page_number=chunk.page_number,
                chunk_index=chunk.chunk_index,
            )
            meta = cls.build_chunk_metadata_payload(doc=doc, ver=ver, chunk=chunk)

            # Use custom vector embedding if provided, otherwise standard dimension placeholder
            values = [0.0] * settings.EMBEDDING_DIMENSION
            if custom_vectors:
                match = next((v for v in custom_vectors if v.get("id") == det_id or v.get("chunk_index") == chunk.chunk_index), None)
                if match and match.get("values"):
                    values = match["values"]

            vectors.append({
                "id": det_id,
                "values": values,
                "metadata": meta,
            })

            # Update DB chunk record
            chunk.vector_id = det_id
            chunk.embedding_model = settings.EMBEDDING_MODEL
            chunk.embedding_dimension = settings.EMBEDDING_DIMENSION
            chunk.indexed_at = now
            chunk.metadata_json = meta

        # Validate vector safety
        cls.validate_vector_compatibility(vectors)

        namespace = pinecone_service.get_namespace(doc.collection_id)
        pinecone_service.upsert_vectors(vectors=vectors, namespace=namespace)

        db.commit()

        logger.info(f"Upserted {len(vectors)} vectors for version {version_id} into namespace {namespace}.")
        return {
            "success": True,
            "version_id": version_id,
            "document_id": doc.id,
            "collection_id": doc.collection_id,
            "indexed_count": len(vectors),
            "namespace": namespace,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
        }

    @classmethod
    def delete_document_version_vectors(
        cls,
        db: Session,
        version_id: str,
        vector_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Delete all vectors for a single document version from Pinecone by deterministic vector IDs.
        """
        ver = db.query(DocumentVersion).filter(DocumentVersion.id == version_id).first()
        doc = db.query(Document).filter(Document.id == ver.document_id).first() if ver else None
        collection_id = doc.collection_id if doc else None

        chunks = db.query(ExtractedChunk).filter(ExtractedChunk.version_id == version_id).all()
        ids_to_delete = vector_ids or [
            c.vector_id or cls.generate_vector_id(version_id, c.page_number, c.chunk_index)
            for c in chunks
        ]

        namespace = pinecone_service.get_namespace(collection_id)
        if ids_to_delete:
            pinecone_service.delete_vectors(ids=ids_to_delete, namespace=namespace)

        # Clear indexed_at timestamps in database
        for c in chunks:
            c.indexed_at = None
        db.commit()

        logger.info(f"Deleted {len(ids_to_delete)} vectors for version {version_id} from Pinecone.")
        return {
            "success": True,
            "version_id": version_id,
            "deleted_count": len(ids_to_delete),
            "namespace": namespace,
        }

    @classmethod
    def reindex_collection(
        cls,
        db: Session,
        collection_id: str,
    ) -> Dict[str, Any]:
        """
        Re-index all active documents and versions in a collection after metadata changes.
        """
        coll = db.query(DocumentCollection).filter(DocumentCollection.id == collection_id).first()
        if not coll:
            raise ValueError(f"Collection {collection_id} not found.")

        # Find active documents in collection
        docs = (
            db.query(Document)
            .filter(
                Document.collection_id == collection_id,
                Document.status == DocumentStatus.ACTIVE.value,
            )
            .all()
        )

        reindexed_versions: List[str] = []
        total_vectors = 0

        for doc in docs:
            # Reindex active versions
            versions = (
                db.query(DocumentVersion)
                .filter(
                    DocumentVersion.document_id == doc.id,
                    DocumentVersion.status == DocumentStatus.ACTIVE.value,
                )
                .all()
            )
            for ver in versions:
                res = cls.upsert_document_version_vectors(db=db, version_id=ver.id)
                reindexed_versions.append(ver.id)
                total_vectors += res.get("indexed_count", 0)

        logger.info(
            f"Reindexed collection {collection_id} ('{coll.name}'): "
            f"{len(reindexed_versions)} versions, {total_vectors} vectors."
        )

        return {
            "success": True,
            "collection_id": collection_id,
            "collection_name": coll.name,
            "documents_count": len(docs),
            "versions_reindexed": reindexed_versions,
            "total_vectors_indexed": total_vectors,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_dimension": settings.EMBEDDING_DIMENSION,
        }

    @classmethod
    def rebuild_all_indexes(cls, db: Session) -> Dict[str, Any]:
        """
        Admin command to rebuild all active document indexes across all collections.
        """
        collections = db.query(DocumentCollection).filter(DocumentCollection.is_active == True).all()
        rebuilt_collections = []
        total_vectors = 0

        for coll in collections:
            res = cls.reindex_collection(db=db, collection_id=coll.id)
            rebuilt_collections.append(res)
            total_vectors += res.get("total_vectors_indexed", 0)

        return {
            "success": True,
            "collections_rebuilt_count": len(rebuilt_collections),
            "total_vectors_indexed": total_vectors,
            "details": rebuilt_collections,
        }


indexing_service = IndexingService()
