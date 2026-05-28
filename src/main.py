"""Kaf Extract — API-First Data Extraction Micro-Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import auth, extract, health, keys, metrics, subscriptions, vouchers, webhooks, admin_payments


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — init Redis, verify Crawl4AI, init DB."""
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

    yield

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
