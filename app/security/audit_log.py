"""Security audit logging module.

Records all authentication attempts, authorization denials, prompt injection detections,
and document lifecycle events in structured JSON format for compliance and monitoring.
"""

from datetime import datetime
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("security.audit")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        fmt='%(asctime)s [AUDIT] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)


class AuditLogger:
    """Security audit logger producing structured event logs."""

    @staticmethod
    def log_event(
        event_type: str,
        user_id: Optional[int] = None,
        username: Optional[str] = None,
        role: Optional[str] = None,
        department: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        success: bool = True,
    ) -> None:
        """Record a structured security audit event."""
        payload = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "event_type": event_type,
            "success": success,
            "actor": {
                "user_id": user_id,
                "username": username or "anonymous",
                "role": role or "unknown",
                "department": department or "unknown",
            },
            "details": details or {},
        }
        log_str = json.dumps(payload, default=str)
        if success:
            logger.info(log_str)
        else:
            logger.warning(log_str)


# Predefined event types
EVENT_AUTH_SUCCESS = "AUTH_LOGIN_SUCCESS"
EVENT_AUTH_FAILURE = "AUTH_LOGIN_FAILURE"
EVENT_ACCESS_DENIED = "AUTHORIZATION_ACCESS_DENIED"
EVENT_PROMPT_INJECTION = "PROMPT_INJECTION_DETECTED"
EVENT_DOC_INGESTED = "DOCUMENT_INGESTED"
EVENT_DOC_DELETED = "DOCUMENT_DELETED"
EVENT_RAG_QUERY = "RAG_QUERY_EXECUTED"
