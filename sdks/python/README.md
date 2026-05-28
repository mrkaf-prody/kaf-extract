# Kaf Extract Python SDK

**AI-powered web data extraction API client.** Built on Crawl4AI with Redis caching,
async job queue, and AI extraction via Ollama.

```bash
pip install kaf-extract
```

## Quick Start

```python
from kaf_extract import KafExtract

client = KafExtract(api_key="kaf_your_api_key")

# Extract page title and price
result = client.extract_sync("https://books.toscrape.com", fields=[
    {"name": "title", "selector": "h1", "type": "text"},
    {"name": "price", "selector": ".price_color", "type": "text"},
])

print(result.data["title"])   # "A Light in the Attic"
print(result.data["price"])   # "£51.77"
```

## Features

| Feature | Method |
|---------|--------|
| CSS/XPath extraction | `client.extract()` |
| AI extraction (no selectors) | `client.extract_ai()` |
| Batch (up to 50 URLs) | `client.extract_batch()` |
| Screenshots | `client.screenshot()` |
| Async jobs + webhooks | `extract(async_mode=True, webhook_url=...)` |
| CSV/Markdown export | `extract(output_format="csv")` |
| JWT auth (register/login) | `client.register()`, `client.login()` |
| Voucher redemption | `client.redeem_voucher()` |

## Async Usage

```python
import asyncio
from kaf_extract import KafExtract

async def main():
    async with KafExtract(api_key="kaf_xxx") as client:
        # AI extraction — no selectors needed
        result = await client.extract_ai(
            "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/",
            instruction="Extract the book title, price, and stock status as JSON",
        )
        print(result.data)

        # Batch extraction
        batch = await client.extract_batch(
            urls=["https://example.com/page1", "https://example.com/page2"],
            fields=[{"name": "title", "selector": "h1", "type": "text"}],
        )
        print(f"{batch.succeeded}/{batch.total} succeeded")

asyncio.run(main())
```

## API Reference

See [docs.kafcenter.com](https://extract.kafcenter.com/docs) for full API documentation.

## Requirements

- Python 3.10+
- `httpx` and `pydantic` (installed automatically)

## License

MIT — [Kaf Center](https://kafcenter.com)
