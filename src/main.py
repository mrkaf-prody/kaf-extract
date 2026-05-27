"""Kaf Extract — API-First Data Extraction Micro-Service."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import settings
from src.routers import extract, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle — verify Playwright browser works."""
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"]
            )
            await browser.close()
    except Exception as e:
        import sys
        print(f"WARNING: Browser check failed (non-fatal): {e}", file=sys.stderr)
    yield


app = FastAPI(
    title="Kaf Extract",
    description="API-First Data Extraction Micro-Service — Give us a URL and a schema, we give you structured JSON.",
    version="0.1.0",
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

app.include_router(extract.router, prefix="/api/v1")
app.include_router(health.router)
