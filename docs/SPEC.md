# Spec: Kaf Extract — API-First Data Extraction Micro-Service

**Version:** 0.1.0-MVP  
**Author:** Hamza (CEO, Kaf Center)  
**Date:** May 27, 2026  
**Status:** Planning → Building

---

## Elevator Pitch

"Give us a URL and a schema → we give you structured JSON." A REST API that handles headless browser extraction, proxy rotation, and anti-bot bypass — so developers don't have to.

## Problem

Companies need structured data from websites (competitor pricing, job listings, real estate listings) but scraping is complex, brittle, and constantly breaking. Developers waste hours on Playwright scripts, CSS selectors, and anti-bot evasion.

## Solution

A single API endpoint: `POST /api/v1/extract`  
- Input: `{url, schema: {fields: [{name, selector, type}]}}`  
- Output: `{status, data: {...}, metadata: {duration_ms, cached}}`  
- We handle: headless browser, Playwright, retries, proxy rotation, anti-bot  

## Target Users

- Data analysts who need structured web data
- Market researchers tracking competitor prices
- Job board aggregators
- Real estate price trackers
- Indie developers who don't want to write scraping code

## MVP Scope

### IN scope (v0.1.0)
- POST /api/v1/extract — single URL extraction with CSS/XPath selectors
- API key authentication (via X-API-Key header)
- Rate limiting (100 req/min per key)
- JSON response with structured data
- OpenAPI docs at /docs (Swagger UI)
- Health check at /health
- Docker support (Dockerfile + docker-compose)
- Browser-based extraction via Playwright
- Error handling with meaningful messages

### OUT of scope (v1+)
- Multi-URL batch extraction
- Proxy rotation (use single headless browser for MVP)
- Caching layer
- Webhook callbacks
- Dashboard / GUI
- User management / billing
- JavaScript-rendered selectors (MVP: CSS/XPath only)

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| **Framework** | FastAPI (Python 3.11+) | Async, auto-docs, type safety |
| **Browser** | Playwright (Chromium) | Best headless browser, stealth support |
| **Database** | SQLite (MVP) → PostgreSQL (later) | Zero-config for MVP |
| **Auth** | API keys (hashed in DB) | Simple, stateless |
| **Rate Limiting** | In-memory (slowapi) | Lightweight for MVP |
| **Container** | Docker + docker-compose | Dokploy-native |
| **Testing** | pytest + pytest-asyncio | Async test support |
| **Linting** | ruff | Fast Python linter |

## API Design

### POST /api/v1/extract

```json
// Request
{
  "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
  "schema": {
    "fields": [
      {"name": "title", "selector": "h1", "type": "text"},
      {"name": "price", "selector": ".price_color", "type": "text"},
      {"name": "in_stock", "selector": ".availability", "type": "exists"}
    ]
  }
}

// Response (200)
{
  "status": "success",
  "data": {
    "title": "A Light in the Attic",
    "price": "£51.77",
    "in_stock": true
  },
  "metadata": {
    "url": "https://books.toscrape.com/...",
    "duration_ms": 1234,
    "timestamp": "2026-05-27T22:00:00Z"
  }
}

// Response (error)
{
  "status": "error",
  "error": {
    "code": "EXTRACTION_FAILED",
    "message": "Selector '.price_color' not found on page"
  }
}
```

### GET /health
```json
{"status": "healthy", "version": "0.1.0"}
```

## Architecture

```
Client (API key) → FastAPI (rate limit) → ExtractService → Playwright Browser → URL
                                               ↓
                                          Structured JSON ← CSS/XPath selectors
```

## File Structure

```
data-extractor/
├── src/
│   ├── main.py              # FastAPI app entrypoint
│   ├── config.py             # Settings from env vars
│   ├── api/
│   │   └── routes.py         # All API routes
│   ├── routers/
│   │   ├── extract.py        # POST /api/v1/extract
│   │   └── health.py         # GET /health
│   ├── services/
│   │   ├── extractor.py      # Playwright extraction logic
│   │   └── auth.py           # API key validation
│   ├── models/
│   │   ├── extract.py        # Pydantic models for extract
│   │   └── apikey.py         # API key model
│   └── middleware/
│       └── rate_limit.py     # Rate limiting middleware
├── tests/
│   ├── test_extract.py       # Extraction endpoint tests
│   ├── test_health.py        # Health check tests
│   └── test_auth.py          # Auth tests
├── docs/
│   └── SPEC.md               # This file
├── scripts/
│   └── run.sh                # Local dev runner
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── pyproject.toml
├── .env.example
├── .gitignore
└── README.md
```

## Success Criteria

- [ ] POST /api/v1/extract returns structured JSON for a known public page
- [ ] Invalid API key returns 401
- [ ] Rate limit exceeded returns 429
- [ ] Missing selector returns meaningful error
- [ ] Health check returns 200
- [ ] Docker build succeeds
- [ ] All tests pass (pytest)
- [ ] OpenAPI docs accessible at /docs

---

*This spec is the north star. All implementation decisions trace back to this document.*
