"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Kaf Extract configuration."""

    # Database
    database_url: str = "sqlite:///./data/kaf-extract.db"

    # API Key (dev default)
    dev_api_key: str = "kaf-extract-dev-key-change-in-production"

    # Browser
    playwright_headless: bool = True
    playwright_timeout_ms: int = 30000

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


settings = Settings()
