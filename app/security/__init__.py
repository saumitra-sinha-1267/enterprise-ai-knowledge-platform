"""Security package init."""
from app.security.prompt_guard import PromptGuard, prompt_guard, PromptGuardResult
from app.security.input_validator import (
    validate_file_upload,
    validate_department_and_access,
    sanitize_text,
    ALLOWED_EXTENSIONS,
    MAX_FILE_SIZE_BYTES,
)
from app.security.audit_log import (
    AuditLogger,
    EVENT_AUTH_SUCCESS,
    EVENT_AUTH_FAILURE,
    EVENT_ACCESS_DENIED,
    EVENT_PROMPT_INJECTION,
    EVENT_DOC_INGESTED,
    EVENT_DOC_DELETED,
    EVENT_RAG_QUERY,
)
