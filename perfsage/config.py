"""Application configuration via pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All runtime settings; values come from environment / .env file."""

    debug: bool = False
    database_url: str = "sqlite:///./data/perfsage.db"
    data_dir: Path = Path("data")
    redis_url: str = "redis://localhost:6379"
    perfsage_secret: str = "change-me-in-production"
    max_upload_bytes: int = 2 * 1024**3  # 2 GB

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Return a cached singleton Settings instance."""
    return Settings()
