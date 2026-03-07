"""
Centralized Configuration Management.
Loads from .env file or environment variables. No external dependencies required.
"""

import os
from typing import Optional


def _load_dotenv():
    """Load .env file if it exists."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_dotenv()


class Settings:
    """
    Centralized Configuration — reads from environment variables with sensible defaults.
    """

    # API Keys
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    AIRTABLE_API_KEY: Optional[str] = os.getenv("AIRTABLE_API_KEY")
    AIRTABLE_BASE_ID: Optional[str] = os.getenv("AIRTABLE_BASE_ID")
    EXTENSION_API_KEY: Optional[str] = os.getenv("EXTENSION_API_KEY")

    # Paths and System Settings
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    APP_NAME: str = os.getenv("APP_NAME", "AI Interview Copilot")
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    CHROMA_DB_PATH: str = os.path.join(BASE_DIR, "chroma_db")

    # LLM Backend Toggle: "ollama" (default, local) or "groq" (cloud)
    LLM_BACKEND: str = os.getenv("LLM_BACKEND", "ollama")

    # Ollama Config (local LLM)
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2")

    # Groq Config (cloud LLM) — used when LLM_BACKEND=groq
    PLANNER_MODEL: str = os.getenv("PLANNER_MODEL", "llama-3.3-70b-versatile")
    VERIFIER_MODEL: str = os.getenv("VERIFIER_MODEL", "llama-3.3-70b-versatile")
    FACT_CHECKER_MODEL: str = os.getenv("FACT_CHECKER_MODEL", "llama-3.3-70b-versatile")
    QGEN_MODEL: str = os.getenv("QGEN_MODEL", "llama-3.3-70b-versatile")

    # RAG Config
    EMBEDDING_MODEL_NAME: str = os.getenv("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2")
    CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "500"))
    CHUNK_OVERLAP: int = int(os.getenv("CHUNK_OVERLAP", "50"))


# Singleton
settings = Settings()

# Ensure necessary directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
