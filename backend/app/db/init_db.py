"""
Database initialization and dataset seeding wrapper.
"""

from sqlalchemy.orm import Session
from backend.app.db.seed import seed_database


def init_db(db: Session = None) -> None:
    """Create all tables, apply migrations, and populate initial seed data."""
    seed_database(db)


if __name__ == "__main__":
    init_db()
    print("Database successfully initialized, migrated, and seeded.")
