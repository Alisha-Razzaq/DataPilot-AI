"""Load settings from environment variables and an optional .env file."""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/config.py → repository root (DataPilot-AI/)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Typed application configuration.

    Values are read from the process environment, then from a local .env file.
    Field names map to uppercase env vars (APP_NAME, APP_ENV, MAX_UPLOAD_BYTES).
    """

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "DataPilot AI"
    app_env: str = "development"
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MiB
    uploads_dir: Path = PROJECT_ROOT / "data" / "uploads"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3.1-flash-lite"
    supabase_url: str = ""
    supabase_secret_key: str = ""
    supabase_storage_bucket: str = "datasets"

    @property
    def supabase_configured(self) -> bool:
        return bool(
            self.supabase_url.strip()
            and self.supabase_secret_key.strip()
            and self.supabase_storage_bucket.strip()
        )

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() == "production"


settings = Settings()
