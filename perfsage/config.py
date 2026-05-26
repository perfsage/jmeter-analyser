"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime settings; values come from environment / .env file."""

    debug: bool = False
    database_url: str = "sqlite:///./data/perfsage.db"
    data_dir: Path = Path("data")
    redis_url: str = "redis://127.0.0.1:6379"
    perfsage_secret: str = ""  # must be set via env; validator rejects empty/default
    max_upload_bytes: int = 2 * 1024**3  # 2 GB

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    @field_validator("perfsage_secret")
    @classmethod
    def secret_must_be_set(cls, v: str) -> str:
        if not v or v == "change-me-in-production":
            raise ValueError(
                "PERFSAGE_SECRET must be set to a non-default value in .env or environment"
            )
        return v


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
