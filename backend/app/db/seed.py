"""
Database seeding module.
Seeds roles, development administrator, sample collection, document, and citation entities.
"""

from datetime import datetime
from sqlalchemy.orm import Session
from backend.app.core.security import hash_password
from backend.app.db.migrator import DatabaseMigrator
from backend.app.db.session import SessionLocal, engine
from backend.app.models.db_models import (
    AuditEvent,
    Citation,
    Department,
    Document,
    DocumentCollection,
    DocumentMetadata,
    DocumentPage,
    DocumentStatus,
    DocumentVersion,
    ExtractedChunk,
    QuestionAnswer,
    Role,
    SearchSession,
    User,
)
from backend.app.models.schemas import ROLE_PERMISSIONS, UserRole


def seed_database(db: Session = None) -> None:
    """Run migrations and populate seed data idempotently."""
    DatabaseMigrator.apply_migrations(db)

    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # 1. Seed Standard Roles
        roles_data = [
            (
                "role-00000000-0000-4000-8000-000000000001",
                UserRole.SYSTEM_ADMIN.value,
                "Full system administration and user management",
                ROLE_PERMISSIONS[UserRole.SYSTEM_ADMIN],
            ),
            (
                "role-00000000-0000-4000-8000-000000000002",
                UserRole.SCHEME_ADMIN.value,
                "Scheme-level document upload, versioning and catalog management",
                ROLE_PERMISSIONS[UserRole.SCHEME_ADMIN],
            ),
            (
                "role-00000000-0000-4000-8000-000000000003",
                UserRole.HELPDESK.value,
                "Frontline citizen counter and query resolution staff",
                ROLE_PERMISSIONS[UserRole.HELPDESK],
            ),
            (
                "role-00000000-0000-4000-8000-000000000004",
                UserRole.CITIZEN.value,
                "Public user searching for welfare scheme eligibility",
                ROLE_PERMISSIONS[UserRole.CITIZEN],
            ),
        ]

        for r_id, r_name, r_desc, r_perms in roles_data:
            role = db.query(Role).filter(Role.name == r_name).first()
            if not role:
                role = Role(
                    id=r_id,
                    name=r_name,
                    description=r_desc,
                    permissions=r_perms,
                )
                db.add(role)
        db.commit()

        # 2. Seed Department
        dept_mohua = db.query(Department).filter(Department.code == "MOHUA").first()
        if not dept_mohua:
            dept_mohua = Department(
                id="dept-00000000-0000-4000-8000-000000000001",
                name="Ministry of Housing and Urban Affairs",
                code="MOHUA",
                description="Nodal central ministry for urban poverty alleviation and housing schemes.",
            )
            db.add(dept_mohua)
            db.commit()

        # 3. Seed Dev Administrator
        admin_email = "admin.dev@welfareconnect.local"
        dev_admin = db.query(User).filter(User.email == admin_email).first()
        admin_role = db.query(Role).filter(Role.name == UserRole.SYSTEM_ADMIN.value).first()
        if not dev_admin:
            dev_admin = User(
                id="b0000000-0000-4000-8000-000000000001",
                email=admin_email,
                password_hash=hash_password("Admin@123456"),
                full_name="Local Development Administrator",
                role_id=admin_role.id if admin_role else None,
                role=UserRole.SYSTEM_ADMIN.value,
                department="Department of Information Technology & Digital Services",
                department_id=dept_mohua.id,
                is_active=True,
            )
            db.add(dev_admin)

        # 4. Seed Helpdesk Staff
        staff_email = "helpdesk.staff@welfareconnect.local"
        dev_staff = db.query(User).filter(User.email == staff_email).first()
        helpdesk_role = db.query(Role).filter(Role.name == UserRole.HELPDESK.value).first()
        if not dev_staff:
            dev_staff = User(
                id="b0000000-0000-4000-8000-000000000002",
                email=staff_email,
                password_hash=hash_password("Staff@123456"),
                full_name="Frontline Helpdesk Officer",
                role_id=helpdesk_role.id if helpdesk_role else None,
                role=UserRole.HELPDESK.value,
                department="Citizen Helpdesk Services",
                department_id=dept_mohua.id,
                is_active=True,
            )
            db.add(dev_staff)
        db.commit()

        # 5. Seed Sample Collection
        col_slug = "housing-urban-affairs"
        sample_col = db.query(DocumentCollection).filter(DocumentCollection.slug == col_slug).first()
        if not sample_col:
            sample_col = DocumentCollection(
                id="col-0000000-0000-4000-8000-000000000001",
                department_id=dept_mohua.id,
                name="Housing & Urban Affairs (PMAY)",
                slug=col_slug,
                description="Official operational circulars, income eligibility matrices, and subsidy guidelines for Pradhan Mantri Awas Yojana Urban.",
                is_active=True,
            )
            db.add(sample_col)
            db.commit()

        # 6. Seed Sample Document with all required fields
        doc_id = "doc-0000000-0000-4000-8000-000000000001"
        sample_doc = db.query(Document).filter(Document.id == doc_id).first()
        if not sample_doc:
            sample_doc = Document(
                id=doc_id,
                collection_id=sample_col.id,
                scheme_name="Pradhan Mantri Awas Yojana - Urban (PMAY-U)",
                department="Ministry of Housing and Urban Affairs",
                state_or_district="National / All States",
                language="en",
                publication_date=datetime(2024, 1, 15),
                effective_date=datetime(2024, 4, 1),
                original_filename="PMAY-U-Operational-Guidelines-2024.pdf",
                storage_file_key="raw-documents/housing-urban-affairs/doc-001/v1/PMAY-U-Guidelines.pdf",
                mime_type="application/pdf",
                file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                version_number=1,
                status=DocumentStatus.ACTIVE.value,
            )
            db.add(sample_doc)
            db.commit()

        # 7. Seed Sample Document Version
        ver_id = "ver-0000000-0000-4000-8000-000000000001"
        sample_ver = db.query(DocumentVersion).filter(DocumentVersion.id == ver_id).first()
        if not sample_ver:
            sample_ver = DocumentVersion(
                id=ver_id,
                document_id=sample_doc.id,
                version_number=1,
                original_filename="PMAY-U-Operational-Guidelines-2024.pdf",
                storage_file_key="raw-documents/housing-urban-affairs/doc-001/v1/PMAY-U-Guidelines.pdf",
                mime_type="application/pdf",
                file_hash="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                file_size_bytes=2450128,
                total_pages=48,
                status=DocumentStatus.ACTIVE.value,
                effective_date=datetime(2024, 4, 1),
                change_summary="Initial operational guidelines release for financial year 2024-25.",
            )
            db.add(sample_ver)
            db.commit()

        # 8. Seed Sample Document Page
        page_id = "page-000000-0000-4000-8000-000000000014"
        sample_page = db.query(DocumentPage).filter(DocumentPage.id == page_id).first()
        if not sample_page:
            sample_page = DocumentPage(
                id=page_id,
                version_id=sample_ver.id,
                document_id=sample_doc.id,
                page_number=14,
                raw_text=(
                    "Clause 4.2: Credit Linked Subsidy Scheme (CLSS) Eligibility. "
                    "EWS households having an annual income up to Rs. 3,00,000 are eligible for an interest "
                    "subsidy of 6.5% for a tenure of 20 years on housing loans up to Rs. 6,00,000."
                ),
                storage_image_path="page-artifacts/doc-001/v1/pages/page-014.webp",
                word_count=42,
            )
            db.add(sample_page)
            db.commit()

        # 9. Seed Sample Extracted Text Chunk
        chunk_id = "chunk-00000-0000-4000-8000-000000000001"
        sample_chunk = db.query(ExtractedChunk).filter(ExtractedChunk.id == chunk_id).first()
        if not sample_chunk:
            sample_chunk = ExtractedChunk(
                id=chunk_id,
                page_id=sample_page.id,
                version_id=sample_ver.id,
                document_id=sample_doc.id,
                chunk_index=0,
                chunk_text=(
                    "EWS households having an annual income up to Rs. 3,00,000 are eligible for "
                    "interest subsidy of 6.5% for a tenure of 20 years on housing loans up to Rs. 6,00,000 under PMAY-U."
                ),
                token_count=36,
                start_char_offset=0,
                end_char_offset=174,
                vector_id="vec-pmay-001-c001",
            )
            db.add(sample_chunk)
            db.commit()

        # 10. Seed Sample Metadata
        meta_id = "meta-000000-0000-4000-8000-000000000001"
        sample_meta = db.query(DocumentMetadata).filter(DocumentMetadata.id == meta_id).first()
        if not sample_meta:
            sample_meta = DocumentMetadata(
                id=meta_id,
                document_id=sample_doc.id,
                version_id=sample_ver.id,
                meta_key="max_income_ews",
                meta_value="300000",
                data_type="integer",
            )
            db.add(sample_meta)
            db.commit()

        # 11. Seed Sample Audit Event
        audit_id = "audit-0000-0000-4000-8000-000000000001"
        sample_audit = db.query(AuditEvent).filter(AuditEvent.id == audit_id).first()
        if not sample_audit:
            sample_audit = AuditEvent(
                id=audit_id,
                user_id=dev_admin.id,
                action_type="SYSTEM_SEEDED",
                entity_table="system",
                entity_id="seed-001",
                metadata_json={"status": "INITIAL_SEED_COMPLETE", "collections_seeded": 1, "documents_seeded": 1},
                ip_address="127.0.0.1",
            )
            db.add(sample_audit)
            db.commit()

    finally:
        if close_db:
            db.close()


def run_seed():
    """CLI runner for seed script."""
    print("Seeding database with initial roles, admin account, and sample collection...")
    seed_database()
    print("Database seeding completed successfully.")


if __name__ == "__main__":
    run_seed()
