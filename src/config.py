from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # LLM
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"

    # Database
    database_url: str
    db_ssl: bool = False  # set automatically from ?sslmode=require in database_url

    @field_validator("database_url", mode="before")
    @classmethod
    def normalise_db_url(cls, v: str) -> str:
        """asyncpg doesn't support ?sslmode=require in the URL — handled via connect_args."""
        if isinstance(v, str):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1) if v.startswith("postgresql://") else v
        return v

    # Prefect
    prefect_api_url: str = ""
    prefect_api_key: str = ""

    # App
    upload_dir: Path = Path("./data/uploads")
    log_level: str = "INFO"
    app_env: str = "development"

    @field_validator("upload_dir", mode="before")
    @classmethod
    def create_upload_dir(cls, v: str) -> Path:
        p = Path(v)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache
def get_settings() -> Settings:
    return Settings()
