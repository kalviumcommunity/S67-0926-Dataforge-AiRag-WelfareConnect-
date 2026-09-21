"""
CLI Tool for Vector Index Rebuild and Collection Re-indexing.
Usage:
    python -m backend.app.workers.rebuild_index --all
    python -m backend.app.workers.rebuild_index --collection-id <uuid>
    python -m backend.app.workers.rebuild_index --version-id <uuid>
"""

import argparse
import sys
from backend.app.db.session import SessionLocal
from backend.app.services.indexing_service import indexing_service


def main():
    parser = argparse.ArgumentParser(description="Rebuild Pinecone Vector Indexes and Metadata for WelfareConnect.")
    parser.add_argument("--all", action="store_true", help="Rebuild all active document collections")
    parser.add_argument("--collection-id", type=str, help="Re-index a specific document collection by ID")
    parser.add_argument("--version-id", type=str, help="Re-index a specific document version by ID")

    args = parser.parse_args()

    db = SessionLocal()
    try:
        if args.all:
            print("Starting complete rebuild of all document vector indexes...")
            res = indexing_service.rebuild_all_indexes(db=db)
            print(f"Rebuild completed successfully! Rebuilt {res['collections_rebuilt_count']} collections, {res['total_vectors_indexed']} vectors.")
        elif args.collection_id:
            print(f"Reindexing collection {args.collection_id}...")
            res = indexing_service.reindex_collection(db=db, collection_id=args.collection_id)
            print(f"Collection re-indexed: {res['documents_count']} documents, {res['total_vectors_indexed']} vectors.")
        elif args.version_id:
            print(f"Reindexing document version {args.version_id}...")
            res = indexing_service.upsert_document_version_vectors(db=db, version_id=args.version_id)
            print(f"Version re-indexed: {res['indexed_count']} vectors.")
        else:
            parser.print_help()
            sys.exit(1)
    except Exception as e:
        print(f"Rebuild failed: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
