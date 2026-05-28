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

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Rate limiting
    rate_limit_requests: int = 100
    rate_limit_window_seconds: int = 60

    # ------------------------------------------------------------------
    # Phase 4: Payment system
    # ------------------------------------------------------------------

    # Active payment provider: "lemonsqueezy", "paddle", or "manual"
    payment_provider: str = "manual"

    # LemonSqueezy
    lemonsqueezy_api_key: str = ""
    lemonsqueezy_store_id: str = ""
    lemonsqueezy_webhook_secret: str = ""
    lemonsqueezy_test_mode: bool = True
    # Plan variant IDs (set these in production)
    lemonsqueezy_variant_hobby: str = ""
    lemonsqueezy_variant_pro: str = ""
    lemonsqueezy_variant_enterprise: str = ""

    # Paddle
    paddle_api_key: str = ""
    paddle_webhook_secret: str = ""
    paddle_test_mode: bool = True
    # Paddle price IDs per plan
    paddle_price_hobby: str = ""
    paddle_price_pro: str = ""
    paddle_price_enterprise: str = ""

    # Trial system
    trial_duration_days: int = 7
    trial_extraction_limit: int = 100

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "noreply@kafextract.com"

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


settings = Settings()
