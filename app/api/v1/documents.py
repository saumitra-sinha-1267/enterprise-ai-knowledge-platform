"""Document ingestion and lifecycle management endpoints.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, get_current_user
from app.auth.models import User, DepartmentEnum, AccessLevelEnum
from app.auth.rbac import get_allowed_departments_for_user, can_user_access_document
from app.ingestion.pipeline import ingestion_pipeline
from app.models.document import DocumentRecord
from app.security.input_validator import validate_file_upload

router = APIRouter()


@router.post("/upload", status_code=status.HTTP_201_CREATED, summary="Ingest enterprise document")
async def upload_document(
    file: UploadFile = File(...),
    department: str = Form(default=DepartmentEnum.GENERAL.value),
    access_level: str = Form(default=AccessLevelEnum.INTERNAL.value),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Upload and ingest a PDF, DOCX, or TXT document into the secure knowledge platform."""
    content = await file.read()
    
    # Validate extension, size, and magic signature
    filename, ext = validate_file_upload(file, content)

    # Ingest through pipeline with server-side RBAC validation
    doc_record = ingestion_pipeline.ingest_document(
        filename=filename,
        content=content,
        department=department,
        access_level=access_level,
        user=current_user,
        db=db,
    )

    return {
        "message": f"Document '{filename}' ingested and indexed successfully.",
        "doc_id": doc_record.doc_id,
        "filename": doc_record.filename,
        "department": doc_record.department,
        "access_level": doc_record.access_level,
        "chunk_count": doc_record.chunk_count,
        "file_size_bytes": doc_record.file_size_bytes,
        "status": doc_record.status,
    }


@router.get("/", summary="List accessible enterprise documents")
def list_documents(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Return all enterprise documents the authenticated user is authorized to view."""
    allowed_depts = get_allowed_departments_for_user(current_user)

    # Filter strictly by user's permitted departments
    documents = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.department.in_(allowed_depts))
        .order_by(DocumentRecord.created_at.desc())
        .all()
    )

    result = []
    for d in documents:
        result.append({
            "id": d.id,
            "doc_id": d.doc_id,
            "filename": d.filename,
            "file_type": d.file_type,
            "file_size_bytes": d.file_size_bytes,
            "department": d.department,
            "access_level": d.access_level,
            "chunk_count": d.chunk_count,
            "status": d.status,
            "uploaded_by_id": d.uploaded_by_id,
            "created_at": d.created_at.isoformat() if d.created_at else None,
        })
    return result


@router.get("/status/{doc_id}", summary="Check document ingestion status")
def get_document_status(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve processing status and chunk statistics for an ingested document."""
    doc = db.query(DocumentRecord).filter(DocumentRecord.doc_id == doc_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{doc_id}' not found.",
        )

    if not can_user_access_document(current_user, doc.department, doc.access_level):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not authorized to inspect this document.",
        )

    return {
        "doc_id": doc.doc_id,
        "filename": doc.filename,
        "department": doc.department,
        "access_level": doc.access_level,
        "chunk_count": doc.chunk_count,
        "status": doc.status,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


@router.delete("/{doc_id}", summary="Delete an ingested document")
def delete_document(
    doc_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Delete a document and purge its vector index if the user holds required privileges."""
    ingestion_pipeline.delete_document(doc_id=doc_id, user=current_user, db=db)
    return {"message": f"Document '{doc_id}' and all associated vectors deleted successfully."}
