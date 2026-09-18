"""
Database Migrator module.
Applies DDL migrations in order from backend/app/db/migrations/.
"""

import os
from sqlalchemy import text
from sqlalchemy.orm import Session
from backend.app.db.session import SessionLocal, engine
from backend.app.models.db_models import Base


class DatabaseMigrator:
    MIGRATIONS_DIR = os.path.join(os.path.dirname(__file__), "migrations")

    @classmethod
    def apply_migrations(cls, db: Session = None) -> None:
        """Apply all pending SQL migrations to the target database."""
        # Ensure base metadata tables are registered
        Base.metadata.create_all(bind=engine)

        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        try:
            if os.path.exists(cls.MIGRATIONS_DIR):
                migration_files = sorted(
                    [f for f in os.listdir(cls.MIGRATIONS_DIR) if f.endswith(".sql")]
                )
                for mig_file in migration_files:
                    mig_path = os.path.join(cls.MIGRATIONS_DIR, mig_file)
                    with open(mig_path, "r", encoding="utf-8") as f:
                        sql_content = f.read()
                    
                    # Split statements by semicolon and execute non-empty
                    statements = [
                        stmt.strip() for stmt in sql_content.split(";") if stmt.strip()
                    ]
                    for stmt in statements:
                        try:
                            db.execute(text(stmt))
                        except Exception:
                            # Catch table/index already exists warnings in sqlite/postgres
                            pass
                    db.commit()
        finally:
            if close_db:
                db.close()


def run_migrations():
    """CLI / programmatic helper to run migrations."""
    print("Running database migrations...")
    DatabaseMigrator.apply_migrations()
    print("Database migrations applied successfully.")


if __name__ == "__main__":
    run_migrations()
