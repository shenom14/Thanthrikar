from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    """
    Centralized Configuration Management.
    Loads from .env file or environment variables.
    """
    # API Keys
    GROQ_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    AIRTABLE_API_KEY: Optional[str] = None
    AIRTABLE_BASE_ID: Optional[str] = None
    EXTENSION_API_KEY: Optional[str] = None
    
    # Ollama Config
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    
    # Paths and System Settings
    ENVIRONMENT: str = "development"
    APP_NAME: str = "AI Interview Copilot"
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    CHROMA_DB_PATH: str = os.path.join(BASE_DIR, "chroma_db")
    
    # LLM Config
    PLANNER_MODEL: str = "llama3.2"
    VERIFIER_MODEL: str = "llama3.2"
    FACT_CHECKER_MODEL: str = "llama3.2"
    QGEN_MODEL: str = "llama3.2"
    
    # RAG Config
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"
    CHUNK_SIZE: int = 500
    CHUNK_OVERLAP: int = 50
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Instantiate singleton for import across project
settings = Settings()

# Ensure necessary local directories exist
os.makedirs(settings.DATA_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_DB_PATH, exist_ok=True)
