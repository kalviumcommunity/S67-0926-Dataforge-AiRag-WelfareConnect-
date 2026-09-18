"""
Database initialization and initial dataset seeding.
"""

from sqlalchemy.orm import Session
from backend.app.core.security import hash_password
from backend.app.db.session import SessionLocal, engine
from backend.app.models.db_models import (
    Base,
    Department,
    DocumentCollection,
    User,
)
from backend.app.models.schemas import UserRole


def init_db(db: Session = None) -> None:
    """Create all tables and seed initial administrator, staff, and departments."""
    Base.metadata.create_all(bind=engine)

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # 1. Seed Departments
        dept_it = db.query(Department).filter(Department.code == "DEPT_IT").first()
        if not dept_it:
            dept_it = Department(
                id="a0000000-0000-4000-8000-000000000001",
                name="Department of Information Technology & Digital Services",
                code="DEPT_IT",
                description="Central nodal agency for government digital portals and AI services.",
            )
            db.add(dept_it)

        dept_agri = db.query(Department).filter(Department.code == "DEPT_AGRI").first()
        if not dept_agri:
            dept_agri = Department(
                id="a0000000-0000-4000-8000-000000000002",
                name="Ministry of Agriculture & Farmers Welfare",
                code="DEPT_AGRI",
                description="Agricultural subsidies, credit support, and crop welfare schemes.",
            )
            db.add(dept_agri)

        dept_housing = db.query(Department).filter(Department.code == "DEPT_HOUSING").first()
        if not dept_housing:
            dept_housing = Department(
                id="a0000000-0000-4000-8000-000000000003",
                name="Ministry of Housing and Urban Affairs",
                code="DEPT_HOUSING",
                description="Affordable urban housing, credit-linked subsidies, and shelter assistance.",
            )
            db.add(dept_housing)

        db.commit()

        # 2. Seed Document Collections
        col_pmay = db.query(DocumentCollection).filter(DocumentCollection.slug == "housing-urban-affairs").first()
        if not col_pmay:
            col_pmay = DocumentCollection(
                id="col-0000000-0000-4000-8000-000000000001",
                department_id=dept_housing.id,
                name="Housing & Urban Affairs (PMAY)",
                slug="housing-urban-affairs",
                description="Official guidelines and circulars for Pradhan Mantri Awas Yojana Urban.",
                is_active=True,
            )
            db.add(col_pmay)

        col_pmkisan = db.query(DocumentCollection).filter(DocumentCollection.slug == "farmer-welfare-pmkisan").first()
        if not col_pmkisan:
            col_pmkisan = DocumentCollection(
                id="col-0000000-0000-4000-8000-000000000002",
                department_id=dept_agri.id,
                name="Agriculture & Farmer Welfare (PM-Kisan)",
                slug="farmer-welfare-pmkisan",
                description="Direct income support and operational circulars for farmer welfare.",
                is_active=True,
            )
            db.add(col_pmkisan)

        db.commit()

        # 3. Seed Dev Administrator (Prompt 05 Preservation)
        admin_email = "admin.dev@welfareconnect.local"
        dev_admin = db.query(User).filter(User.email == admin_email).first()
        if not dev_admin:
            dev_admin = User(
                id="b0000000-0000-4000-8000-000000000001",
                email=admin_email,
                password_hash=hash_password("Admin@123456"),
                full_name="Local Development Administrator",
                role=UserRole.SYSTEM_ADMIN.value,
                department="Department of Information Technology & Digital Services",
                department_id=dept_it.id,
                is_active=True,
            )
            db.add(dev_admin)

        # 4. Seed Dev Helpdesk Staff (Prompt 05 Preservation)
        staff_email = "helpdesk.staff@welfareconnect.local"
        dev_staff = db.query(User).filter(User.email == staff_email).first()
        if not dev_staff:
            dev_staff = User(
                id="b0000000-0000-4000-8000-000000000002",
                email=staff_email,
                password_hash=hash_password("Staff@123456"),
                full_name="Frontline Helpdesk Officer",
                role=UserRole.HELPDESK.value,
                department="Citizen Helpdesk Services",
                is_active=True,
            )
            db.add(dev_staff)

        db.commit()
    finally:
        if close_db:
            db.close()


if __name__ == "__main__":
    init_db()
    print("Database successfully initialized and seeded.")
