"""Application configuration module.

Supports environment variables, .env file loading, and strongly typed settings.
"""

from enum import Enum
import os
from pathlib import Path
from typing import List, Optional
from pydantic import field_validator

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:
    from pydantic import BaseModel as BaseSettings
    SettingsConfigDict = dict


class EnvironmentType(str, Enum):
    DEVELOPMENT = "development"
    TESTING = "testing"
    PRODUCTION = "production"


class VectorDBType(str, Enum):
    QDRANT = "qdrant"
    MEMORY = "memory"
    CHROMA = "chroma"


class LLMProviderType(str, Enum):
    OFFLINE_MOCK = "offline_mock"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"


class Settings(BaseSettings):
    # Base paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent

    # Project metadata
    PROJECT_NAME: str = "Enterprise AI Knowledge Platform"
    ENVIRONMENT: EnvironmentType = EnvironmentType.DEVELOPMENT
    DEBUG: bool = True

    # Security & JWT
    SECRET_KEY: str = "dev_secret_jwt_key_enterprise_rag_2026_super_secure_random_token_demo"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Relational Database
    DATABASE_URL: str = "sqlite:///./enterprise_rag.db"

    # Vector Database
    VECTOR_DB_TYPE: VectorDBType = VectorDBType.QDRANT
    QDRANT_HOST: str = "localhost"
    QDRANT_PORT: int = 6333
    QDRANT_COLLECTION_NAME: str = "enterprise_knowledge_base"
    QDRANT_IN_MEMORY: bool = True

    # Embeddings
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DEVICE: str = "cpu"

    # Chunking & Retrieval Parameters
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 4
    SIMILARITY_THRESHOLD: float = 0.20

    # LLM Provider Configuration
    LLM_PROVIDER: LLMProviderType = LLMProviderType.OFFLINE_MOCK

    @field_validator("LLM_PROVIDER", mode="before")
    @classmethod
    def parse_llm_provider(cls, v):
        """Leniently parse LLM_PROVIDER to prevent crash if a URL or custom provider is passed."""
        if isinstance(v, str):
            v_str = v.strip().lower()
            if "http" in v_str or "groq" in v_str or "openai" in v_str or "gpt" in v_str:
                return LLMProviderType.OPENAI
            if v_str in ["offline_mock", "mock"]:
                return LLMProviderType.OFFLINE_MOCK
            if "anthropic" in v_str or "claude" in v_str:
                return LLMProviderType.ANTHROPIC
            if "ollama" in v_str:
                return LLMProviderType.OLLAMA
        return v
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_API_BASE: str = "https://api.openai.com/v1"

    ANTHROPIC_API_KEY: Optional[str] = None
    ANTHROPIC_MODEL: str = "claude-3-haiku-20240307"

    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3"

    # Security and Guardrails
    PROMPT_INJECTION_PROTECTION_ENABLED: bool = True
    MAX_QUERY_LENGTH: int = 1000
    AUDIT_LOG_ENABLED: bool = True

    # Backend API URL for Streamlit or client services
    BACKEND_API_URL: str = "http://localhost:8000"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


# Instantiate singleton settings
settings = Settings()
