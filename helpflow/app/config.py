from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings; no credentials are stored in source code."""

    app_env: str = "development"
    database_url: str = "sqlite:///./data/helpflow.db"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = ""
    embedding_provider: str = "sentence-transformers"
    embedding_model: str = ""
    jwt_secret_key: str = ""
    admin_registration_token: str = ""
    access_token_expire_minutes: int = 60
    api_url: str = "http://localhost:8000"
    cors_origins: str = "http://localhost:8501,http://127.0.0.1:8501"
    log_level: str = "INFO"
    log_dir: str = "data/logs"
    log_timezone: str = "Asia/Kolkata"
    data_dir: str = "data"
    backup_dir: str = "data/backups"
    rag_dir: str = "data/vector_index"
    rate_limit_per_minute: int = Field(default=120, ge=10, le=10000)

    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]


settings = Settings()
