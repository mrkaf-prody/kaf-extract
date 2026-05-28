"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Kaf Extract configuration."""

    # Database
    database_url: str = (
        "postgresql+asyncpg://kafextract:kafextract@postgres:5432/kafextract"
    )

    # Legacy API Key (dev default, retained for backward compat)
    dev_api_key: str = "kaf-extract-dev-key-change-in-production"

    # JWT Auth
    jwt_secret: str = "change-me-in-production-use-a-long-random-string"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # Browser
    playwright_headless: bool = True
    playwright_timeout_ms: int = 30000

    # Crawl4AI
    crawl4ai_headless: bool = True
    crawl4ai_page_timeout_ms: int = 30000
    crawl4ai_chrome_path: str = ""
    crawl4ai_verbose: bool = False

    # Ollama (for AI extraction via LLMExtractionStrategy)
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "kimi-k2.6:cloud"
    ollama_api_key: str = "ollama"  # Ollama doesn't require a real key but Crawl4AI expects one

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
