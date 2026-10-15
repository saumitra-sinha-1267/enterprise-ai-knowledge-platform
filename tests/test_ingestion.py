"""Unit and integration tests for document parsing, chunking, and ingestion pipeline.
"""

import io
import docx
import pytest
from fastapi import HTTPException

from app.ingestion.parser import DocumentParser
from app.ingestion.chunker import TextChunker, ParsedSection
from app.ingestion.pipeline import ingestion_pipeline
from app.security.input_validator import validate_file_upload


def test_txt_parser():
    """Verify clean text extraction from TXT bytes."""
    sample_text = "Enterprise knowledge management.\n\nSection 1: Data Governance."
    sections = DocumentParser.parse("governance.txt", sample_text.encode("utf-8"))
    assert len(sections) == 1
    assert "Enterprise knowledge management" in sections[0].text
    assert sections[0].page_number == 1


def test_docx_parser():
    """Verify DOCX parsing using in-memory generated document."""
    doc = docx.Document()
    doc.add_heading("Architecture Overview", level=1)
    doc.add_paragraph("This document outlines the distributed streaming architecture.")
    doc.add_paragraph("Kafka topics are partitioned across availability zones.")

    buffer = io.BytesIO()
    doc.save(buffer)
    docx_bytes = buffer.getvalue()

    sections = DocumentParser.parse("architecture.docx", docx_bytes)
    assert len(sections) >= 1
    assert "Kafka topics are partitioned" in sections[0].text


def test_chunker_boundaries_and_overlap():
    """Verify that chunks respect target sizes and maintain configurable overlap."""
    chunker = TextChunker(chunk_size=150, chunk_overlap=30)
    
    p1 = "The enterprise security architecture adheres to zero-trust network principles."
    p2 = "All intra-cluster service communication occurs via mutual TLS using Istio service mesh."
    p3 = "Service access tokens are cryptographically signed using RS256 and rotated hourly."
    
    sections = [ParsedSection(text=f"{p1}\n\n{p2}\n\n{p3}", page_number=1)]
    chunks = chunker.chunk_sections(sections)

    assert len(chunks) >= 2
    for c in chunks:
        assert len(c.text) > 0
        assert c.page_number == 1
        assert c.token_count > 0


def test_duplicate_document_rejection(test_users, db_session):
    """Verify that duplicate file ingestion is blocked with 409 Conflict."""
    admin = test_users["admin"]
    sample_bytes = b"Unique enterprise secret document for deduplication test 12345."

    # First ingestion succeeds
    doc1 = ingestion_pipeline.ingest_document(
        filename="unique_test.txt",
        content=sample_bytes,
        department="general",
        access_level="public",
        user=admin,
        db=db_session,
    )
    assert doc1 is not None

    # Second ingestion with identical bytes must raise HTTP 409 Conflict
    with pytest.raises(HTTPException) as exc_info:
        ingestion_pipeline.ingest_document(
            filename="duplicate_test.txt",
            content=sample_bytes,
            department="general",
            access_level="public",
            user=admin,
            db=db_session,
        )
    assert exc_info.value.status_code == 409
    assert "Duplicate document detected" in exc_info.value.detail


def test_malformed_file_rejections():
    """Verify rejection of empty, oversized, or invalid file extensions."""
    from fastapi import UploadFile

    # Unsupported format (.exe)
    dummy_exe = UploadFile(filename="malicious_payload.exe", file=io.BytesIO(b"MZ\x90\x00"))
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(dummy_exe, b"MZ\x90\x00")
    assert exc_info.value.status_code == 400
    assert "Unsupported file format" in exc_info.value.detail

    # Empty file (0 bytes)
    empty_txt = UploadFile(filename="empty.txt", file=io.BytesIO(b""))
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(empty_txt, b"")
    assert exc_info.value.status_code == 400
    assert "empty" in exc_info.value.detail

    # Invalid PDF binary signature
    corrupt_pdf = UploadFile(filename="corrupt.pdf", file=io.BytesIO(b"Not a real PDF"))
    with pytest.raises(HTTPException) as exc_info:
        validate_file_upload(corrupt_pdf, b"Not a real PDF")
    assert exc_info.value.status_code == 400
    assert "binary signature" in exc_info.value.detail
