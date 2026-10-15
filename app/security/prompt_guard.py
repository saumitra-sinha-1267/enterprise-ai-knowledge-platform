"""Prompt Injection Protection and Adversarial Detection Engine.

Security Note & Limitations:
---------------------------
Heuristic pattern matching and structural sandboxing provide meaningful defense
against known prompt injection, delimiter breakout, and role-override vectors.
However, prompt-based defenses do NOT offer cryptographic or mathematical guarantees
against sophisticated semantic evasion, multi-turn jailbreaks, or token obfuscation.

Therefore, our primary security boundary is SERVER-SIDE RBAC RETRIEVAL FILTERING:
unauthorized documents are filtered out before reaching the vector search result,
meaning unauthorized facts never enter the LLM's context window regardless of what
the user or the model does.
"""

import re
from dataclasses import dataclass
from typing import Optional, List, Tuple


@dataclass
class PromptGuardResult:
    is_safe: bool
    risk_level: str  # "LOW", "MEDIUM", "HIGH", "CRITICAL"
    reason: Optional[str] = None
    sanitized_input: str = ""


# Common injection signatures and jailbreak patterns
INJECTION_PATTERNS = [
    # Instruction overrides and policy bypasses
    (r"(?i)\bignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directions|prompts|rules)", "Instruction override attempt"),
    (r"(?i)\bdisregard\s+(all\s+)?(previous|prior|system)\s+(instructions|directives|prompts)", "Directive disregard attempt"),
    (r"(?i)\bforget\s+(your|all)\s+(rules|instructions|system\s+prompt|guidelines)", "System rule reset attempt"),
    (r"(?i)\byou\s+are\s+now\s+(unrestricted|jailbroken|dan|root|god\s+mode|developer\s+mode)\b", "Role hijacking / persona spoofing"),
    (r"(?i)\bbypass\s+(all\s+)?(safety|security|policy|restrictions|filters)", "Safety bypass attempt"),

    # Delimiter and context breakout tokens
    (r"</?(untrusted_documents|document|context|system_prompt|instructions|metadata)>", "Delimiter breakout / tag injection"),
    (r"\[/?(SYSTEM|ADMIN|USER|INSTRUCTIONS)\]", "Delimiter breakout / system tag injection"),
    (r"===\s*(SYSTEM|ADMIN|OVERRIDE|ROOT)\s*===", "Structural block spoofing"),
    (r"```(system|prompt|admin)", "Codeblock tag spoofing"),

    # Exfiltration and secret extraction attempts
    (r"(?i)\b(print|reveal|output|display|dump|leak|show|give\s+me)\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(system\s+prompt|secret\s+key|api\s+key|credentials|internal\s+rules|password)", "System prompt / secret exfiltration attempt"),
    (r"(?i)\bwhat\s+(is|are)\s+your\s+(exact\s+)?(system\s+prompt|initial\s+instructions|secret\s+instructions)", "System prompt introspection attempt"),
]

# Sensitive token signatures that must NEVER leak in outputs
OUTPUT_LEAK_PATTERNS = [
    (r"(?i)(sk-[a-zA-Z0-9]{20,})", "Potential OpenAI API key leaked"),
    (r"(?i)(secret_key\s*=\s*['\"][^'\"]+['\"])", "Potential secret key leaked"),
    (r"(?i)(password\s*=\s*['\"][^'\"]+['\"])", "Potential plaintext credential leaked"),
    (r"<untrusted_documents>", "Raw system delimiter leaked in output"),
]


class PromptGuard:
    """Prompt sanitization and injection detection service."""

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._compiled_input_patterns = [
            (re.compile(pattern), reason) for pattern, reason in INJECTION_PATTERNS
        ]
        self._compiled_output_patterns = [
            (re.compile(pattern), reason) for pattern, reason in OUTPUT_LEAK_PATTERNS
        ]

    def validate_query(self, user_query: str) -> PromptGuardResult:
        """Analyze a user query for adversarial prompt injection patterns.
        
        Returns PromptGuardResult indicating whether the query is safe to proceed.
        """
        if not self.enabled:
            return PromptGuardResult(is_safe=True, risk_level="LOW", sanitized_input=user_query)

        if not user_query or not user_query.strip():
            return PromptGuardResult(is_safe=True, risk_level="LOW", sanitized_input="")

        text = user_query.strip()

        # Check for length anomalies
        if len(text) > 2000:
            return PromptGuardResult(
                is_safe=False,
                risk_level="HIGH",
                reason="Query exceeds maximum allowed length of 2000 characters.",
                sanitized_input=text[:2000],
            )

        # Check known malicious regex patterns
        for regex, reason in self._compiled_input_patterns:
            if regex.search(text):
                return PromptGuardResult(
                    is_safe=False,
                    risk_level="HIGH",
                    reason=f"Security alert: {reason}",
                    sanitized_input=text,
                )

        # Basic sanitization of XML/HTML brackets to prevent structural delimiter hijacking
        sanitized = text.replace("<untrusted_documents>", "&lt;untrusted_documents&gt;")
        sanitized = sanitized.replace("</untrusted_documents>", "&lt;/untrusted_documents&gt;")

        return PromptGuardResult(
            is_safe=True,
            risk_level="LOW",
            reason=None,
            sanitized_input=sanitized,
        )

    def validate_output(self, response_text: str) -> Tuple[bool, str]:
        """Verify the generated response does not contain sensitive tokens or leaks.
        
        Returns (is_clean, scrubbed_response).
        """
        if not self.enabled or not response_text:
            return True, response_text

        scrubbed = response_text
        flagged = False

        for regex, reason in self._compiled_output_patterns:
            if regex.search(scrubbed):
                flagged = True
                scrubbed = regex.sub("[REDACTED_SENSITIVE_CONTENT]", scrubbed)

        return not flagged, scrubbed


# Global singleton instance
prompt_guard = PromptGuard()
