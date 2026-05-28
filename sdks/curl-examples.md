# Kaf Extract API — cURL Examples

**Base URL:** `https://extract.kafcenter.com`

---

## 🔑 Authentication

### Register a new account

```bash
curl -X POST https://extract.kafcenter.com/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "password": "secure_password_123",
    "name": "Dev User"
  }'
```

**Response (201):**
```json
{
  "access_token": "eyJhbGci...",
  "refresh_token": "eyJhbGci...",
  "token_type": "bearer"
}
```

### Login

```bash
curl -X POST https://extract.kafcenter.com/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "dev@example.com",
    "password": "secure_password_123"
  }'
```

---

## 📦 Core Extraction

### Basic CSS Extraction

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://books.toscrape.com",
    "schema": {
      "fields": [
        {"name": "title", "selector": "h1", "type": "text"},
        {"name": "price", "selector": ".price_color", "type": "text"},
        {"name": "stock", "selector": ".availability", "type": "text"}
      ]
    }
  }'
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "title": "A Light in the Attic",
    "price": "£51.77",
    "stock": "In stock"
  },
  "metadata": {
    "url": "https://books.toscrape.com",
    "duration_ms": 1234,
    "timestamp": "2026-05-28T12:00:00Z"
  }
}
```

### Attribute Extraction

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://books.toscrape.com",
    "schema": {
      "fields": [
        {"name": "image_src", "selector": ".thumbnail img", "type": "attribute", "attribute": "src"},
        {"name": "link_href", "selector": "article a", "type": "attribute", "attribute": "href"}
      ]
    }
  }'
```

### Markdown Extraction

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://example.com",
    "schema": {
      "fields": [
        {"name": "content", "type": "markdown"}
      ]
    }
  }'
```

### CSV Export

```bash
curl -X POST "https://extract.kafcenter.com/api/v1/extract?format=csv" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://books.toscrape.com",
    "schema": {
      "fields": [
        {"name": "title", "selector": "h1", "type": "text"},
        {"name": "price", "selector": ".price_color", "type": "text"}
      ]
    }
  }'
```

---

## 🤖 AI Extraction (No Selectors)

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract/ai \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/",
    "instruction": "Extract the book title, product description, price, and stock availability as JSON",
    "model": "kimi-k2.6:cloud",
    "format": "json"
  }'
```

**Response (200):**
```json
{
  "status": "success",
  "data": {
    "title": "A Light in the Attic",
    "description": "It's hard to imagine a world without A Light in the Attic...",
    "price": "£51.77",
    "stock": "In stock (22 available)"
  },
  "metadata": {
    "url": "https://books.toscrape.com/...",
    "duration_ms": 3421,
    "timestamp": "2026-05-28T12:00:00Z"
  }
}
```

---

## 📸 Screenshots

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract/screenshot \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://example.com",
    "full_page": true
  }'
```

---

## 📊 Batch Extraction

```bash
curl -X POST https://extract.kafcenter.com/api/v1/extract/batch \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "urls": [
      "https://books.toscrape.com/catalogue/page-1.html",
      "https://books.toscrape.com/catalogue/page-2.html"
    ],
    "schema": {
      "fields": [
        {"name": "title", "selector": "h3 a", "type": "text"},
        {"name": "price", "selector": ".price_color", "type": "text"}
      ]
    }
  }'
```

---

## ⏳ Async Jobs

### Submit async extraction

```bash
curl -X POST "https://extract.kafcenter.com/api/v1/extract?async=true" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: kaf_your_api_key" \
  -d '{
    "url": "https://example.com",
    "schema": {
      "fields": [{"name": "title", "selector": "h1", "type": "text"}]
    },
    "webhook_url": "https://your-app.com/webhooks/kaf"
  }'
```

**Response (200):**
```json
{
  "status": "queued",
  "data": {
    "job_id": "job_abc123",
    "status": "queued"
  },
  "metadata": {
    "url": "https://example.com",
    "duration_ms": 0,
    "timestamp": "2026-05-28T12:00:00Z"
  }
}
```

### Poll for results

```bash
curl https://extract.kafcenter.com/api/v1/extract/job_abc123 \
  -H "X-API-Key: kaf_your_api_key"
```

---

## 🎫 Vouchers

### Redeem a voucher

```bash
curl -X POST https://extract.kafcenter.com/api/v1/vouchers/redeem \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"code": "KAF-A7X9-B2M4"}'
```

### View redemption history

```bash
curl https://extract.kafcenter.com/api/v1/vouchers/history \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## 🏥 Health Check

```bash
curl https://extract.kafcenter.com/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "0.2.0",
  "db_status": "healthy",
  "redis_status": "healthy"
}
```

---

## ⚡ Rate Limits

All extraction endpoints return rate limit headers:

```bash
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1716901200
```

When exceeded (HTTP 429):
```bash
Retry-After: 45
```
