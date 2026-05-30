"""Kaf Extract — API-First Data Extraction Micro-Service."""

import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from src.routers import auth, extract, health, keys, metrics, subscriptions, vouchers, webhooks, admin_payments, schedules, integrations, organizations, usage
from src.routers.admin import router as admin_router


def _run_migrations_sync(connection, alembic_cfg):
    """Run alembic migrations synchronously (called via conn.run_sync)."""
    from alembic import command
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


# ── Platform-defined feature flags ────────────────────────────────────────
# These are seeded on startup. Admins can toggle on/off and assign to plans.
# No plan binding by default — admin assigns via the Plans tab.

PLATFORM_FEATURE_FLAGS = [
    # Core Extraction
    {"key": "css_extraction", "name": "CSS Selector Extraction", "description": "Extract text, HTML, attributes, and existence checks via CSS selectors", "default_enabled": True},
    {"key": "ai_extraction", "name": "AI-Powered Extraction", "description": "LLM-based extraction using natural language instructions", "default_enabled": True},
    {"key": "markdown_extraction", "name": "Markdown Extraction", "description": "Convert any web page to clean markdown content", "default_enabled": True},
    {"key": "screenshot_capture", "name": "Screenshot Capture", "description": "Full-page screenshots as base64-encoded images", "default_enabled": True},
    {"key": "batch_extraction", "name": "Batch Extraction", "description": "Extract from multiple URLs in a single request (up to 50)", "default_enabled": True},
    {"key": "async_extraction", "name": "Async Extraction", "description": "Non-blocking extraction with job queue and polling", "default_enabled": True},
    {"key": "webhook_callbacks", "name": "Webhook Callbacks", "description": "HMAC-SHA256 signed result delivery to custom endpoints", "default_enabled": True},
    # Scheduling & Automation
    {"key": "scheduled_extractions", "name": "Scheduled Extractions", "description": "Cron-based recurring extractions (hourly, daily, weekly)", "default_enabled": True},
    # Export & Integrations
    {"key": "csv_export", "name": "CSV Export", "description": "Export extracted data as CSV files", "default_enabled": True},
    {"key": "slack_integration", "name": "Slack Notifications", "description": "Send extraction results to Slack via webhook", "default_enabled": True},
    # API & Developer Tools
    {"key": "api_access", "name": "REST API Access", "description": "Full REST API with 43+ endpoints and OpenAPI docs", "default_enabled": True},
    {"key": "python_sdk", "name": "Python SDK", "description": "pip install kaf-extract — full Python client library", "default_enabled": True},
    {"key": "javascript_sdk", "name": "JavaScript SDK", "description": "npm install kaf-extract — full JS/TypeScript client library", "default_enabled": True},
    {"key": "api_docs", "name": "Interactive API Docs", "description": "Swagger/OpenAPI UI for testing and exploration", "default_enabled": True},
    # Security
    {"key": "two_factor_auth", "name": "Two-Factor Authentication", "description": "TOTP-based 2FA with QR code setup and backup codes", "default_enabled": True},
    # Collaboration
    {"key": "organizations", "name": "Organizations & Teams", "description": "Team management with roles (owner, admin, member, viewer)", "default_enabled": True},
    # Billing & Subscription
    {"key": "trial_system", "name": "Free Trial", "description": "7-day free trial with 100 extractions for new users", "default_enabled": True},
    {"key": "voucher_system", "name": "Voucher Codes", "description": "Create, redeem, and manage discount voucher codes", "default_enabled": True},
    {"key": "invoice_generation", "name": "Invoice Generation", "description": "Automatic PDF invoice generation for payments", "default_enabled": True},
    # User Dashboard
    {"key": "extraction_history", "name": "Extraction History", "description": "View and search past extractions with pagination", "default_enabled": True},
    {"key": "usage_dashboard", "name": "Usage Dashboard", "description": "Real-time extraction counts, limits, and remaining quota", "default_enabled": True},
    # Admin
    {"key": "admin_analytics", "name": "Admin Analytics", "description": "Platform-wide extraction stats, MRR, revenue by plan, error rates", "default_enabled": True},
]


async def _seed_feature_flags():
    """Seed platform-defined feature flags into the database (idempotent)."""
    from sqlalchemy import select
    from src.db import async_session_factory
    from src.models.sql_models import FeatureFlag

    async with async_session_factory() as session:
        for flag_data in PLATFORM_FEATURE_FLAGS:
            result = await session.execute(
                select(FeatureFlag).where(FeatureFlag.key == flag_data["key"])
            )
            existing = result.scalar_one_or_none()
            if not existing:
                flag = FeatureFlag(
                    key=flag_data["key"],
                    name=flag_data["name"],
                    description=flag_data["description"],
                    default_enabled=flag_data["default_enabled"],
                    requires_plan=None,  # No plan binding — admin assigns later
                )
                session.add(flag)
        await session.commit()

    # Count how many were seeded vs already existed
    async with async_session_factory() as session:
        result = await session.execute(select(FeatureFlag))
        total = len(result.scalars().all())
    import sys
    print(f"Feature flags: {total} total in database ({len(PLATFORM_FEATURE_FLAGS)} platform-defined)", file=sys.stderr)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — init Redis, verify Crawl4AI, init DB."""
    # Run database migrations
    try:
        from alembic.config import Config
        from sqlalchemy import create_engine
        from src.config import settings
        
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url.replace("+asyncpg", ""))
        
        sync_engine = create_engine(settings.database_url.replace("+asyncpg", ""))
        with sync_engine.connect() as conn:
            _run_migrations_sync(conn, alembic_cfg)
            conn.commit()
        sync_engine.dispose()
    except Exception as e:
        import sys
        print(f"WARNING: Migration failed (non-fatal): {e}", file=sys.stderr)

    # Ensure all tables exist (auto-create new models — safe for existing tables)
    try:
        from src.db import create_tables
        await create_tables()
    except Exception as e:
        import sys
        print(f"WARNING: Auto table creation failed (non-fatal): {e}", file=sys.stderr)

    # Seed feature flags (platform-defined, idempotent)
    try:
        await _seed_feature_flags()
    except Exception as e:
        import sys
        print(f"WARNING: Feature flags seeding failed (non-fatal): {e}", file=sys.stderr)

    # Connect Redis (caching + rate limiter + job queue)
    try:
        from src.services.cache import connect_redis
        await connect_redis()
    except Exception as e:
        import sys
        print(f"WARNING: Redis connection failed (non-fatal): {e}", file=sys.stderr)

    # Verify Crawl4AI
    try:
        from src.services.extractor import extractor_service
        crawler = await extractor_service._get_crawler()
    except Exception as e:
        import sys
        print(f"WARNING: Browser check failed (non-fatal): {e}", file=sys.stderr)

    # Pre-load payment providers (triggers self-registration)
    try:
        import src.services.payments  # noqa: F401
    except Exception as e:
        import sys
        print(f"WARNING: Payment provider init failed (non-fatal): {e}", file=sys.stderr)

    # Skip dev API key registration in production — use JWT instead
    try:
        from src.models.apikey import _register_dev_key
        _register_dev_key()
    except Exception:
        pass

    # Start background scheduler for recurring extractions
    try:
        from src.services.scheduler import start_scheduler
        start_scheduler()
    except Exception as e:
        import sys
        print(f"WARNING: Scheduler start failed (non-fatal): {e}", file=sys.stderr)

    yield

    # Stop scheduler
    try:
        from src.services.scheduler import stop_scheduler
        await stop_scheduler()
    except Exception:
        pass

    # Clean up on shutdown
    try:
        from src.services.extractor import extractor_service
        await extractor_service.close()
    except Exception:
        pass

    # Dispose DB engine
    try:
        from src.db import engine
        await engine.dispose()
    except Exception:
        pass

    # Close Redis
    try:
        from src.services.cache import close_redis
        await close_redis()
    except Exception:
        pass

    # Close arq pool
    try:
        from src.services.queue import close_arq_pool
        await close_arq_pool()
    except Exception:
        pass


app = FastAPI(
    title="Kaf Extract",
    description="API-First Data Extraction Micro-Service — Give us a URL and a schema, we give you structured JSON.",
    version="0.2.0",
    docs_url="/docs",
    lifespan=lifespan,
)

# --- CORS Middleware ---

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://ai.kafcenter.com",
        "https://extract.kafcenter.com",
        "https://mgmt.kafcenter.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
        "X-Request-ID",
    ],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)


# --- Global Rate Limit Middleware ---

_RATE_LIMIT_WINDOW = 60  # seconds
_RATE_LIMIT_MAX = 100    # requests per window per IP
_rate_limit_store: dict[str, list[float]] = {}


@app.middleware("http")
async def global_rate_limit_middleware(request, call_next):
    """Apply a simple in-memory fixed-window rate limit per client IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW

    # Get or init the request log for this IP
    requests_log = _rate_limit_store.get(client_ip, [])
    requests_log = [t for t in requests_log if t > window_start]
    _rate_limit_store[client_ip] = requests_log

    if len(requests_log) >= _RATE_LIMIT_MAX:
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please try again later."},
            headers={
                "X-RateLimit-Limit": str(_RATE_LIMIT_MAX),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(now + _RATE_LIMIT_WINDOW)),
                "Retry-After": str(_RATE_LIMIT_WINDOW),
            },
        )

    requests_log.append(now)
    response = await call_next(request)

    # Attach rate-limit headers
    remaining = _RATE_LIMIT_MAX - len(requests_log)
    response.headers["X-RateLimit-Limit"] = str(_RATE_LIMIT_MAX)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    response.headers["X-RateLimit-Reset"] = str(int(now + _RATE_LIMIT_WINDOW))

    return response


# --- Rate-limit headers from extract-specific dependency ---

@app.middleware("http")
async def add_extract_rate_limit_headers(request, call_next):
    """Attach rate-limit headers from request.state (set by extract deps)."""
    response = await call_next(request)
    headers = getattr(request.state, "rate_limit_headers", None)
    if headers:
        for key, value in headers.items():
            response.headers[key] = str(value)
    return response


# API routes
app.include_router(schedules.router, prefix="/api/v1")
app.include_router(integrations.router, prefix="/api/v1")
app.include_router(extract.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(keys.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(metrics.router)
app.include_router(subscriptions.router)
app.include_router(vouchers.router)
app.include_router(admin_payments.router)
app.include_router(webhooks.router)
app.include_router(usage.router, prefix="/api/v1")
app.include_router(admin_router)

# ── Admin Dashboard (SPA) ──────────────────────────────────────────

ADMIN_DIR = os.path.join(os.path.dirname(__file__), "admin_static")

@app.get("/admin/{full_path:path}", include_in_schema=False)
async def admin_spa_fallback(full_path: str):
    """Serve admin SPA — fallback to index.html for client-side routing."""
    file_path = os.path.join(ADMIN_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(ADMIN_DIR, "index.html"))

@app.get("/admin", include_in_schema=False)
async def admin_index():
    return FileResponse(os.path.join(ADMIN_DIR, "index.html"))

# Mount static assets (JS, CSS, images) — at root because Vite builds with root-relative paths
if os.path.isdir(ADMIN_DIR):
    app.mount("/assets", StaticFiles(directory=os.path.join(ADMIN_DIR, "assets")), name="admin_assets")
    # Also serve root-level files (favicon, icons) — define individually to avoid closure bug
    fv_path = os.path.join(ADMIN_DIR, "favicon.svg")
    if os.path.isfile(fv_path):
        @app.get("/favicon.svg", include_in_schema=False)
        async def _serve_favicon():
            return FileResponse(fv_path)
    ic_path = os.path.join(ADMIN_DIR, "icons.svg")
    if os.path.isfile(ic_path):
        @app.get("/icons.svg", include_in_schema=False)
        async def _serve_icons():
            return FileResponse(ic_path)

# ── User Dashboard (SPA) ──────────────────────────────────────────

DASHBOARD_DIR = os.path.join(os.path.dirname(__file__), "..", "user-dashboard", "dist")

# Mount static assets FIRST so they take priority over SPA fallback
if os.path.isdir(os.path.join(DASHBOARD_DIR, "assets")):
    app.mount("/dashboard/assets", StaticFiles(directory=os.path.join(DASHBOARD_DIR, "assets")), name="dashboard_assets")

# Serve dashboard favicon to avoid 404 noise
dashboard_fv = os.path.join(DASHBOARD_DIR, "favicon.svg")
if os.path.isfile(dashboard_fv):
    @app.get("/dashboard/favicon.svg", include_in_schema=False)
    async def _serve_dash_favicon():
        return FileResponse(dashboard_fv)

# SPA fallback — serve index.html for all non-asset paths under /dashboard/
@app.get("/dashboard/{full_path:path}", include_in_schema=False)
async def dashboard_spa_fallback(full_path: str):
    """Serve user dashboard SPA — fallback to index.html for client-side routing."""
    file_path = os.path.join(DASHBOARD_DIR, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))

@app.get("/dashboard", include_in_schema=False)
async def dashboard_index():
    return FileResponse(os.path.join(DASHBOARD_DIR, "index.html"))
