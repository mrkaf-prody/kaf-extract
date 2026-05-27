# Kaf Extract — API-First Data Extraction Micro-Service

> "Give us a URL and a schema → we give you structured JSON."

A REST API that handles headless browser extraction, CSS/XPath selectors, and anti-bot bypass — so developers don't have to.

## Quick Start

```bash
# Set API key
export DEV_API_KEY=your-secret-key

# Run with Docker
docker compose up -d

# Or run locally
pip install -r requirements.txt
playwright install chromium
uvicorn src.main:app --reload
```

## API Usage

```bash
curl -X POST http://localhost:8000/api/v1/extract \
  -H "X-API-Key: kaf-extract-dev-key-change-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
    "schema": {
      "fields": [
        {"name": "title", "selector": "h1", "type": "text"},
        {"name": "price", "selector": ".price_color", "type": "text"},
        {"name": "in_stock", "selector": ".availability", "type": "exists"}
      ]
    }
  }'
```

## API Docs

Once running, visit: http://localhost:8000/docs

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| DEV_API_KEY | `kaf-extract-dev-key-change-in-production` | API key for authentication |
| PLAYWRIGHT_HEADLESS | `true` | Run browser in headless mode |
| PLAYWRIGHT_TIMEOUT_MS | `30000` | Page load timeout |

## License

MIT — Kaf Center
