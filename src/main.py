"""Kaf Extract — API-First Data Extraction Micro-Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.routers import auth, extract, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — verify Crawl4AI browser works, init DB."""
    # Verify Crawl4AI
    try:
        from src.services.extractor import extractor_service
        crawler = await extractor_service._get_crawler()
    except Exception as e:
        import sys
        print(f"WARNING: Browser check failed (non-fatal): {e}", file=sys.stderr)

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
)

# API routes
app.include_router(extract.router, prefix="/api/v1")
app.include_router(auth.router)
app.include_router(health.router)
