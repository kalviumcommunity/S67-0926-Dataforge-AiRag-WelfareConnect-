"""
Integration tests for database migrations and idempotent seeding.
"""

from sqlalchemy.orm import Session
from backend.app.db.migrator import DatabaseMigrator
from backend.app.db.seed import seed_database
from backend.app.models.db_models import (
    Document,
    DocumentCollection,
    Role,
    User,
)


def test_migrations_and_seeding_idempotency(db_session: Session):
    """Verify that migrations and seeding can be run multiple times safely."""
    # First run
    DatabaseMigrator.apply_migrations(db_session)
    seed_database(db_session)

    # Second run (must not fail or duplicate primary keys)
    DatabaseMigrator.apply_migrations(db_session)
    seed_database(db_session)

    roles_count = db_session.query(Role).count()
    assert roles_count >= 4

    admin_count = db_session.query(User).filter(User.email == "admin.dev@welfareconnect.local").count()
    assert admin_count == 1

    sample_col = db_session.query(DocumentCollection).filter(DocumentCollection.slug == "housing-urban-affairs").first()
    assert sample_col is not None

    sample_doc = db_session.query(Document).filter(Document.collection_id == sample_col.id).first()
    assert sample_doc is not None
    assert sample_doc.file_hash is not None
