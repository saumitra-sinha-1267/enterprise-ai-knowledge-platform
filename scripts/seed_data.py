"""Database and knowledge base seeding script.

Initializes relational tables, registers demo personas, and ingests
the enterprise sample documents across HR, Finance, Engineering, and General scopes.
"""

import logging
import os
import sys
from pathlib import Path

# Ensure project root is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from sqlalchemy.orm import Session

from app.auth.models import User, DepartmentEnum, AccessLevelEnum
from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.ingestion.pipeline import ingestion_pipeline
from app.models.document import DocumentRecord

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("seed_data")

BASE_DIR = Path(__file__).resolve().parent.parent
SAMPLE_DOCS_DIR = BASE_DIR / "data" / "sample_documents"

SAMPLE_INGESTION_SPECS = [
    {
        "filename": "company_code_of_conduct.txt",
        "department": DepartmentEnum.GENERAL.value,
        "access_level": AccessLevelEnum.PUBLIC.value,
        "uploader_username": "admin",
    },
    {
        "filename": "hr_leave_and_benefits_policy.txt",
        "department": DepartmentEnum.HR.value,
        "access_level": AccessLevelEnum.INTERNAL.value,
        "uploader_username": "hr_manager",
    },
    {
        "filename": "finance_q3_budget_and_procurement.txt",
        "department": DepartmentEnum.FINANCE.value,
        "access_level": AccessLevelEnum.CONFIDENTIAL.value,
        "uploader_username": "finance_lead",
    },
    {
        "filename": "engineering_microservices_architecture.txt",
        "department": DepartmentEnum.ENGINEERING.value,
        "access_level": AccessLevelEnum.INTERNAL.value,
        "uploader_username": "engineer_lead",
    },
]


def seed_all():
    """Execute complete initial database and vector store bootstrap."""
    logger.info("Initializing relational schema and seeding user accounts...")
    db: Session = SessionLocal()
    try:
        init_db(db)
        
        # Load sample documents
        for spec in SAMPLE_INGESTION_SPECS:
            file_path = SAMPLE_DOCS_DIR / spec["filename"]
            if not file_path.exists():
                logger.warning(f"Sample file '{file_path}' not found, skipping.")
                continue

            with open(file_path, "rb") as f:
                content = f.read()

            uploader = db.query(User).filter(User.username == spec["uploader_username"]).first()
            if not uploader:
                logger.error(f"Uploader user '{spec['uploader_username']}' not found.")
                continue

            # Check if document already ingested
            existing = db.query(DocumentRecord).filter(DocumentRecord.filename == spec["filename"]).first()
            if existing:
                logger.info(f"Document '{spec['filename']}' already exists (ID: {existing.doc_id}), skipping re-ingestion.")
                continue

            try:
                doc = ingestion_pipeline.ingest_document(
                    filename=spec["filename"],
                    content=content,
                    department=spec["department"],
                    access_level=spec["access_level"],
                    user=uploader,
                    db=db,
                )
                logger.info(
                    f"Successfully ingested '{doc.filename}' | Dept: {doc.department.upper()} | "
                    f"Chunks: {doc.chunk_count} | DocID: {doc.doc_id[:8]}..."
                )
            except Exception as e:
                logger.error(f"Failed to ingest '{spec['filename']}': {e}")

        logger.info("\n=== Enterprise AI Knowledge Platform Ready ===")
        total_docs = db.query(DocumentRecord).count()
        total_users = db.query(User).count()
        logger.info(f"Total Users: {total_users} | Total Enterprise Documents: {total_docs}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_all()
