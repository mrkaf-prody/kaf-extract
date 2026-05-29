"""Application configuration loaded from environment variables."""

import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Kaf Extract configuration."""

    # Database
    database_url: str = (
        "postgresql+asyncpg://kafextract:kafextract@postgres:5432/kafextract"
    )

    # Legacy API Key — disabled in production, must set JWT_SECRET
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

    # Redis
    redis_url: str = "redis://redis:***@kafextract.com"

    # --- Payment Provider ---
    payment_provider: str = "manual"  # "lemonsqueezy", "paddle", or "manual"

    # --- LemonSqueezy ---
    lemonsqueezy_api_key: str = ""
    lemonsqueezy_store_id: str = ""
    lemonsqueezy_webhook_secret: str = ""
    lemonsqueezy_test_mode: bool = os.environ.get("PAYMENT_TEST_MODE", "true").lower() == "true"

    # LemonSqueezy variant IDs (one per plan)
    lemonsqueezy_variant_hobby: str = ""
    lemonsqueezy_variant_pro: str = ""
    lemonsqueezy_variant_enterprise: str = ""

    # --- Paddle ---
    paddle_api_key: str = ""
    paddle_webhook_secret: str = ""
    paddle_test_mode: bool = True
    paddle_price_hobby: str = ""
    paddle_price_pro: str = ""
    paddle_price_enterprise: str = ""

    # --- Manual (voucher-based) ---
    manual_trial_extractions: int = 100
    manual_trial_days: int = 14

    # --- Auto-trial config (used by src.services.trials.start_trial) ---
    trial_duration_days: int = 7
    trial_extraction_limit: int = 100

    # Invoices
    invoices_dir: str = "/app/data/invoices"

    # Plan definitions
    plans: dict = {
        "hobby": {
            "name": "Hobby",
            "price_cents": 0,
            "extractions_per_month": 1000,
            "features": ["Basic extraction", "Community support"],
        },
        "pro": {
            "name": "Pro",
            "price_cents": 2900,
            "extractions_per_month": 50000,
            "features": [
                "AI-powered extraction",
                "Batch processing",
                "Priority support",
                "Export formats",
            ],
        },
        "enterprise": {
            "name": "Enterprise",
            "price_cents": 19900,
            "extractions_per_month": 500000,
            "features": [
                "Everything in Pro",
                "Custom integrations",
                "Dedicated support",
                "SLA guarantee",
                "SSO",
            ],
        },
    }

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._validate_security()

    def _validate_security(self) -> None:
        """Enforce production security: crash hard if defaults are still in place."""
        is_production = os.environ.get("ENVIRONMENT", "").lower() == "production"
        if not is_production:
            return  # Dev mode — defaults are fine

        if self.jwt_secret == "change-me-in-production-use-a-long-random-string":
            raise RuntimeError(
                "JWT_SECRET is still the default value. "
                "Set JWT_SECRET environment variable in production."
            )

        # Warn about dev API key but don't crash — some setups use it
        if self.dev_api_key == "kaf-extract-dev-key-change-in-production":
            import sys
            print(
                "WARNING: DEV_API_KEY is default. Set DEV_API_KEY env var in production.",
                file=sys.stderr,
            )


settings = Settings()
