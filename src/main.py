"""Kaf Extract — API-First Data Extraction Micro-Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from src.routers import auth, extract, health, keys, metrics, subscriptions, vouchers, webhooks, admin_payments, schedules


def _run_migrations_sync(connection, alembic_cfg):
    """Run alembic migrations synchronously (called via conn.run_sync)."""
    from alembic import command
    alembic_cfg.attributes["connection"] = connection
    command.upgrade(alembic_cfg, "head")


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

    # Register dev API key if needed
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=[
        "X-RateLimit-Limit",
        "X-RateLimit-Remaining",
        "X-RateLimit-Reset",
        "Retry-After",
    ],
)


# Attach rate-limit headers from request.state to responses
@app.middleware("http")
async def add_rate_limit_headers(request, call_next):
    response = await call_next(request)
    headers = getattr(request.state, "rate_limit_headers", None)
    if headers:
        for key, value in headers.items():
            response.headers[key] = value
    return response


# API routes
app.include_router(extract.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(health.router)
app.include_router(keys.router, prefix="/api/v1")
app.include_router(metrics.router)
app.include_router(subscriptions.router)
app.include_router(vouchers.router)
app.include_router(admin_payments.router)
app.include_router(webhooks.router)
app.include_router(schedules.router, prefix="/api/v1")

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
