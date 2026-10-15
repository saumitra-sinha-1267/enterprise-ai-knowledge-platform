"""Document ingestion pipeline orchestrator.

Coordinates extraction, deduplication, chunking, embedding generation,
relational tracking, and vector indexing with strict permission checks.
"""

import hashlib
import logging
import uuid
from typing import Optional, Tuple
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth.models import User
from app.auth.rbac import can_user_upload_to_department, can_user_delete_document
from app.config import settings
from app.ingestion.chunker import TextChunker
from app.ingestion.parser import DocumentParser
from app.models.document import DocumentRecord, DocumentChunkRecord
from app.retrieval.embeddings import embedding_service
from app.retrieval.vector_store import get_vector_store
from app.security.audit_log import AuditLogger, EVENT_DOC_INGESTED, EVENT_DOC_DELETED, EVENT_ACCESS_DENIED
from app.security.input_validator import validate_department_and_access

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """Orchestrates end-to-end document intake, chunking, and dual-store persistence."""

    def __init__(self):
        self.chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
        )

    def ingest_document(
        self,
        filename: str,
        content: bytes,
        department: str,
        access_level: str,
        user: User,
        db: Session,
    ) -> DocumentRecord:
        """Process, chunk, embed, and index an enterprise document with strict access controls."""
        dept, level = validate_department_and_access(department, access_level)

        # Enforce server-side authorization: can this user ingest to target department?
        if not can_user_upload_to_department(user, dept):
            AuditLogger.log_event(
                event_type=EVENT_ACCESS_DENIED,
                user_id=user.id,
                username=user.username,
                role=user.role,
                department=user.department,
                details={
                    "action": "document_upload",
                    "target_department": dept,
                    "target_level": level,
                    "filename": filename,
                },
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User role '{user.role}' is not authorized to upload documents to '{dept}' department.",
            )

        # Content hash calculation for deduplication
        content_hash = hashlib.sha256(content).hexdigest()
        existing_doc = db.query(DocumentRecord).filter(DocumentRecord.content_hash == content_hash).first()
        if existing_doc:
            logger.info(f"Duplicate document detected (hash: {content_hash[:12]}). Existing doc_id: {existing_doc.doc_id}")
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Duplicate document detected. This file has already been ingested as '{existing_doc.filename}' (ID: {existing_doc.doc_id}).",
            )

        # 1. Parse text sections
        try:
            sections = DocumentParser.parse(filename, content)
        except Exception as e:
            logger.error(f"Failed to parse document '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Document parsing failed: {str(e)}",
            )

        if not sections:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document contains no readable text content.",
            )

        # 2. Chunk sections
        chunks = self.chunker.chunk_sections(sections)
        if not chunks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document text could not be split into meaningful chunks.",
            )

        doc_id = str(uuid.uuid4())
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "unknown"

        # 3. Create relational database document record
        doc_record = DocumentRecord(
            doc_id=doc_id,
            filename=filename,
            content_hash=content_hash,
            file_type=f".{ext}",
            file_size_bytes=len(content),
            department=dept,
            access_level=level,
            chunk_count=len(chunks),
            status="processed",
            uploaded_by_id=user.id,
        )
        db.add(doc_record)
        db.flush()  # Flush to assign doc_record.id

        # 4. Create chunk records and vector payload
        chunk_records = []
        vector_records = []
        chunk_texts = []

        for c in chunks:
            chunk_rec = DocumentChunkRecord(
                document_id=doc_record.id,
                chunk_index=c.chunk_index,
                page_number=c.page_number,
                content=c.text,
                token_count=c.token_count,
            )
            chunk_records.append(chunk_rec)
            chunk_texts.append(c.text)

            vector_records.append({
                "document_id": doc_record.id,
                "doc_id": doc_id,
                "filename": filename,
                "department": dept,
                "access_level": level,
                "chunk_index": c.chunk_index,
                "page_number": c.page_number,
                "text": c.text,
            })

        db.add_all(chunk_records)

        # 5. Generate embeddings
        try:
            vectors = embedding_service.embed_texts(chunk_texts)
        except Exception as e:
            db.rollback()
            logger.error(f"Embedding generation failed for '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Embedding generation failed: {str(e)}",
            )

        # 6. Index into vector store
        try:
            vector_store = get_vector_store()
            vector_store.insert_chunks(vector_records, vectors)
        except Exception as e:
            db.rollback()
            logger.error(f"Vector database indexing failed for '{filename}': {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Vector store indexing failed: {str(e)}",
            )

        db.commit()
        db.refresh(doc_record)

        # Audit log ingestion event
        AuditLogger.log_event(
            event_type=EVENT_DOC_INGESTED,
            user_id=user.id,
            username=user.username,
            role=user.role,
            department=user.department,
            details={
                "doc_id": doc_id,
                "filename": filename,
                "department": dept,
                "access_level": level,
                "chunks": len(chunks),
                "file_size": len(content),
            },
            success=True,
        )

        logger.info(f"Successfully ingested '{filename}' (doc_id={doc_id}) with {len(chunks)} chunks.")
        return doc_record

    def delete_document(self, doc_id: str, user: User, db: Session) -> bool:
        """Authorize and delete a document from both vector store and relational database."""
        doc = db.query(DocumentRecord).filter(DocumentRecord.doc_id == doc_id).first()
        if not doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID '{doc_id}' not found.",
            )

        # Validate deletion permissions
        if not can_user_delete_document(user, doc.uploaded_by_id, doc.department):
            AuditLogger.log_event(
                event_type=EVENT_ACCESS_DENIED,
                user_id=user.id,
                username=user.username,
                role=user.role,
                department=user.department,
                details={
                    "action": "document_delete",
                    "doc_id": doc_id,
                    "doc_owner": doc.uploaded_by_id,
                    "doc_department": doc.department,
                },
                success=False,
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to delete this document.",
            )

        # Remove from vector store
        try:
            vector_store = get_vector_store()
            vector_store.delete_by_doc_id(doc_id)
        except Exception as e:
            logger.warning(f"Error removing points from vector store for '{doc_id}': {e}")

        # Remove from relational DB
        filename = doc.filename
        dept = doc.department
        db.delete(doc)
        db.commit()

        # Audit log deletion
        AuditLogger.log_event(
            event_type=EVENT_DOC_DELETED,
            user_id=user.id,
            username=user.username,
            role=user.role,
            department=user.department,
            details={"doc_id": doc_id, "filename": filename, "department": dept},
            success=True,
        )

        return True


ingestion_pipeline = IngestionPipeline()
