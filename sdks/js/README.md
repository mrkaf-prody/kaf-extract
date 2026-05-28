# Kaf Extract JavaScript/TypeScript SDK

**AI-powered web data extraction API client.** Built on Crawl4AI with Redis caching,
async job queue, and AI extraction via Ollama.

```bash
npm install kaf-extract
```

## Quick Start

```ts
import { KafExtract } from "kaf-extract";

const client = new KafExtract({ apiKey: "kaf_your_api_key" });

// Extract page title and price
const result = await client.extract("https://books.toscrape.com", {
  fields: [
    { name: "title", selector: "h1", type: "text" },
    { name: "price", selector: ".price_color", type: "text" },
  ],
});

console.log(result.data?.title);  // "A Light in the Attic"
console.log(result.data?.price);  // "£51.77"
```

## Features

| Feature | Method |
|---------|--------|
| CSS/XPath extraction | `client.extract()` |
| AI extraction (no selectors) | `client.extractAI()` |
| Batch (up to 50 URLs) | `client.extractBatch()` |
| Screenshots | `client.screenshot()` |
| Async jobs + webhooks | `extract({ async: true, webhookUrl: "..." })` |
| CSV/Markdown export | `extract({ format: "csv" })` |
| JWT auth (register/login) | `client.register()`, `client.login()` |
| Voucher redemption | `client.redeemVoucher()` |

## Examples

### AI Extraction (no selectors needed)

```ts
const result = await client.extractAI(
  "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/",
  "Extract the book title, price, and stock status as JSON"
);
```

### Batch Extraction

```ts
const batch = await client.extractBatch(
  ["https://example.com/page1", "https://example.com/page2"],
  {
    fields: [{ name: "title", selector: "h1", type: "text" }],
  }
);
console.log(`${batch.succeeded}/${batch.total} succeeded`);
```

### Screenshots

```ts
const shot = await client.screenshot("https://example.com", {
  fullPage: true,
});
// shot.data?.screenshot is a base64-encoded PNG
```

## API Reference

See [extract.kafcenter.com/docs](https://extract.kafcenter.com/docs) for full API documentation.

## License

MIT — [Kaf Center](https://kafcenter.com)
