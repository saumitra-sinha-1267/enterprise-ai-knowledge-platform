"""Pluggable LLM client supporting Offline Mock, OpenAI, Anthropic, and Ollama providers.
"""

from abc import ABC, abstractmethod
import logging
import re
from typing import Dict, Any, Optional

import requests

from app.config import settings, LLMProviderType
from app.generation.prompt_templates import SYSTEM_INSTRUCTION

logger = logging.getLogger(__name__)

NOT_FOUND_MESSAGE = "Based on the provided enterprise documents, sufficient information was not found to answer this question."


class BaseLLMClient(ABC):
    """Abstract interface for LLM generation."""

    @abstractmethod
    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_INSTRUCTION) -> str:
        """Generate a context-grounded response."""
        pass


class OfflineMockLLMClient(BaseLLMClient):
    """Deterministic, zero-cost LLM simulator for offline environments, demos, and testing.
    
    Extracts relevant facts directly from the provided <untrusted_documents> context block.
    If the context lacks matching information, returns the standard insufficient information notice.
    """

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_INSTRUCTION) -> str:
        # Extract question
        q_match = re.search(r"EMPLOYEE QUESTION:\s*(.*?)(?:\n\nREMINDER:|$)", user_prompt, re.DOTALL)
        query = q_match.group(1).strip().lower() if q_match else ""

        # Extract context block
        ctx_match = re.search(r"<untrusted_documents>(.*?)</untrusted_documents>", user_prompt, re.DOTALL)
        if not ctx_match:
            return NOT_FOUND_MESSAGE

        raw_context = ctx_match.group(1).strip()
        if not raw_context:
            return NOT_FOUND_MESSAGE

        # Split context into sources
        sources = re.split(r"--- Context Source \[\d+\] ---", raw_context)
        valid_sources = [s.strip() for s in sources if s.strip()]

        if not valid_sources:
            return NOT_FOUND_MESSAGE

        # Filter query tokens (ignore common stop words)
        stop_words = {"what", "is", "the", "are", "how", "for", "and", "or", "to", "in", "of", "a", "an", "do", "does", "can", "tell", "me", "about"}
        q_tokens = [w for w in re.findall(r"\b\w{3,}\b", query) if w not in stop_words]

        # Require at least 2 distinct query tokens to match when query has >= 3 tokens
        min_matches = 2 if len(q_tokens) >= 3 else 1
        best_sentences = []
        found_source_info = None

        for source_block in valid_sources:
            lines = source_block.splitlines()
            file_line = lines[0] if lines else "Unknown File"
            content_text = "\n".join(lines[2:]) if len(lines) > 2 else source_block

            # Check sentence matches
            sentences = re.split(r"(?<=[.!?])\s+", content_text)
            for s in sentences:
                s_lower = s.lower()
                matches = sum(1 for t in q_tokens if t in s_lower)
                if matches >= min_matches:
                    clean_s = s.strip().replace("\n", " ")
                    if len(clean_s) > 15:
                        best_sentences.append((matches, clean_s, file_line))

        if not best_sentences:
            return NOT_FOUND_MESSAGE

        # Sort sentences by keyword relevance
        best_sentences.sort(key=lambda x: x[0], reverse=True)
        top_facts = [s[1] for s in best_sentences[:2]]
        file_ref = best_sentences[0][2]

        answer = " ".join(top_facts)
        return f"{answer} (Source: {file_ref})"


class OpenAILLMClient(BaseLLMClient):
    """OpenAI API client using REST endpoint."""

    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.api_base = settings.OPENAI_API_BASE.rstrip("/")
        self.model = settings.OPENAI_MODEL

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_INSTRUCTION) -> str:
        if not self.api_key:
            logger.warning("OPENAI_API_KEY is not configured. Falling back to OfflineMockLLMClient.")
            return OfflineMockLLMClient().generate(user_prompt, system_prompt)

        url = f"{self.api_base}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 800,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}. Falling back to OfflineMockLLMClient.")
            return OfflineMockLLMClient().generate(user_prompt, system_prompt)


class AnthropicLLMClient(BaseLLMClient):
    """Anthropic Claude API client."""

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model = settings.ANTHROPIC_MODEL

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_INSTRUCTION) -> str:
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY is not configured. Falling back to OfflineMockLLMClient.")
            return OfflineMockLLMClient().generate(user_prompt, system_prompt)

        url = "https://api.anthropic.com/v1/messages"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = {
            "model": self.model,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "max_tokens": 800,
            "temperature": 0.0,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["content"][0]["text"].strip()
        except Exception as e:
            logger.error(f"Anthropic API call failed: {e}. Falling back to OfflineMockLLMClient.")
            return OfflineMockLLMClient().generate(user_prompt, system_prompt)


class OllamaLLMClient(BaseLLMClient):
    """Local Ollama instance integration."""

    def __init__(self):
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL

    def generate(self, user_prompt: str, system_prompt: str = SYSTEM_INSTRUCTION) -> str:
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.0},
        }
        try:
            resp = requests.post(url, json=payload, timeout=45)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"].strip()
        except Exception as e:
            logger.error(f"Ollama call failed: {e}. Falling back to OfflineMockLLMClient.")
            return OfflineMockLLMClient().generate(user_prompt, system_prompt)


def get_llm_client() -> BaseLLMClient:
    """Factory creating the configured LLM client instance."""
    provider = settings.LLM_PROVIDER
    if provider == LLMProviderType.OPENAI:
        return OpenAILLMClient()
    elif provider == LLMProviderType.ANTHROPIC:
        return AnthropicLLMClient()
    elif provider == LLMProviderType.OLLAMA:
        return OllamaLLMClient()
    else:
        return OfflineMockLLMClient()
