from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent
class Settings(BaseSettings):
    """Configuration settings for the Ask My Docs RAG system."""
    OPENAI_API_KEY: str = '' 
    OPENAI_MODEL: str = 'gpt-4o-mini'
    XAI_API_KEY: str = ''
    XAI_MODEL: str = 'grok-4.5'
    GROK_API_KEY: str = ''
    GROQ_API_KEY: str = ''
    LLM_PROVIDER: str = 'openai'
    GROQ_MODEL: str = 'llama-3.3-70b-versatile'

    OPENAI_USE_ENV_PROXY: bool = False
    EMBEDDING_MODEL: str = 'all-MiniLM-L6-v2'
    RERANKER_MODEL: str = 'cross-encoder/ms-marco-MiniLM-L-6-v2'
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    BM25_TOP_K: int = 50
    VECTOR_TOP_K: int = 50
    RRF_K: int = 60
    RERANK_TOP_K: int = 5
    FUSION_TOP_K: int = 50
    MAX_CONTEXT_CHARS: int = 12_000
    DATA_DIR: str = 'data'
    DOCS_DIR: str = 'docs'
    ALLOWED_DOCS_ROOT: str = 'docs'
    ALLOWED_ORIGINS: str = ''
    OBSERVABILITY_TRACE_PATH: str = 'observability/traces.jsonl'
    INPUT_COST_PER_1K_TOKENS: float = 0.00015
    OUTPUT_COST_PER_1K_TOKENS: float = 0.00060

    model_config = SettingsConfigDict(env_file=PROJECT_ROOT / ".env", env_file_encoding="utf-8", extra="ignore")

@lru_cache()
def get_settings() -> Settings:
    """Get the cached application settings."""
    return Settings()

