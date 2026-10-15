"""Input validation and sanitization for files, queries, and metadata.
"""

import os
from typing import Tuple, Optional
from fastapi import HTTPException, UploadFile, status

from app.auth.models import DepartmentEnum, AccessLevelEnum

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024  # 15 MB limit
MAX_QUERY_LENGTH = 1000

# Magic headers for file type signature verification
MAGIC_HEADERS = {
    ".pdf": b"%PDF-",
    ".docx": b"PK\x03\x04",  # Standard ZIP signature for DOCX
}


def sanitize_text(text: str) -> str:
    """Remove null bytes and unprintable control characters while preserving formatting."""
    if not text:
        return ""
    # Strip null bytes and non-printable control characters (except newline, tab, cr)
    cleaned = "".join(ch for ch in text if ch == "\n" or ch == "\t" or ch == "\r" or (ord(ch) >= 32 and ord(ch) != 127))
    return cleaned.strip()


def validate_file_upload(file: UploadFile, content: bytes) -> Tuple[str, str]:
    """Validate uploaded document extension, size, and header signature.
    
    Returns (filename, normalized_extension).
    Raises HTTPException if invalid.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is missing or empty.",
        )

    _, ext = os.path.splitext(file.filename.lower())
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}",
        )

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty (0 bytes).",
        )

    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum permitted size of {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    # Magic byte signature check
    if ext in MAGIC_HEADERS:
        magic = MAGIC_HEADERS[ext]
        if not content.startswith(magic):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File content does not match the expected binary signature for {ext}.",
            )

    return file.filename, ext


def validate_department_and_access(department: str, access_level: str) -> Tuple[str, str]:
    """Ensure provided department and access levels match known enum values."""
    dept_lower = department.lower().strip()
    valid_depts = {e.value for e in DepartmentEnum}
    if dept_lower not in valid_depts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid department '{department}'. Must be one of: {', '.join(valid_depts)}",
        )

    level_lower = access_level.lower().strip()
    valid_levels = {e.value for e in AccessLevelEnum}
    if level_lower not in valid_levels:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid access level '{access_level}'. Must be one of: {', '.join(valid_levels)}",
        )

    return dept_lower, level_lower
