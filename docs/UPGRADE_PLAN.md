# Kaf Extract — v1.0 Upgrade Plan (Final)

**Date:** May 27, 2026  
**Prepared by:** Hamza (CEO)  
**Current:** v0.1.0 MVP → **Target:** v1.0.0 Production  
**Revision:** v2.0 — Admin Dashboard + Multi-Payment + Voucher System  

---

## Decision Log

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Backend engine | **Crawl4AI** (Apache 2.0) | Zero legal risk. 1 container vs 6+. |
| Database | **PostgreSQL** | Production-grade for users, keys, vouchers, billing |
| Auth | **DIY JWT** | Free. Migrate to Clerk when >50 users |
| Repo structure | **Monorepo** | `/backend` + `/frontend` + `/admin` |
| Admin Dashboard | **Week 2 — NOT deferred** | Mr. K requirement: full management from day 1 |
| Payment strategy | **Multi-provider + Voucher** | Stripe optional. LemonSqueezy/Paddle fallback. Offline vouchers. |
| Phase order | **1 → 3 (Admin) → 2 → 4 (Payments)** | Admin first so we can manage users before billing |

---

## Current State Audit

| Component | Status | Notes |
|-----------|--------|-------|
| Extraction API | ✅ Live | Single URL, CSS/XPath, raw Playwright |
| Auth | ✅ Basic | Hardcoded dev key, bcrypt in-memory |
| Rate Limiting | ❌ Removed | Was crashing container (slowapi) |
| Database | ⚠️ SQLite | File-based, no concurrency |
| Caching | ❌ None | Every request hits the target URL |
| Admin Dashboard | ❌ None | Cannot manage users, subscriptions, features |
| Payments | ❌ None | No billing, no vouchers, nothing |
| **New: Extraction Engine** | ⚠️ Raw Playwright | Migrating to Crawl4AI (Apache 2.0) |

---

## Architecture Target (v1.0)

```
┌──────────────────────────────────────────────────────────────────┐
│                        Kaf Extract v1.0                          │
├──────────────────┬───────────────────┬───────────────────────────┤
│   User Frontend  │  Admin Dashboard  │      Backend API          │
│   (React SPA)    │  (React SPA)      │      (FastAPI)            │
├──────────────────┼───────────────────┼───────────────────────────┤
│ Landing Page     │ User Management   │ POST /extract             │
│ Sign Up / Login  │ Subscription Mgmt │ POST /extract/batch       │
│ API Key Manager  │ Feature Toggles   │ POST /extract/ai          │
│ Usage Dashboard  │ Voucher System    │ GET  /extract/{job_id}    │
│ Playground       │ API Call Monitor  │ POST /keys                │
│ Billing Portal   │ Revenue Analytics │ GET  /keys                │
│                  │ Payment Settings  │ DEL  /keys/{id}           │
│                  │ Audit Logs        │ GET  /metrics             │
│                  │                   │ GET  /usage               │
│                  │                   │ POST /webhooks            │
├──────────────────┴───────────────────┴───────────────────────────┤
│                      Infrastructure                              │
├──────────────────┬───────────────────┬───────────────────────────┤
│ Crawl4AI         │ PostgreSQL        │ Redis                     │
│ (extraction)     │ (users/keys/      │ (cache + queue +          │
│ Apache 2.0       │  vouchers/logs)   │  rate limiting)           │
│ 1 container      │                   │                           │
├──────────────────┼───────────────────┼───────────────────────────┤
│ RQ/arq           │ Dokploy           │ Resend (email)            │
│ (job queue)      │ (deployment)      │                           │
├──────────────────┼───────────────────┼───────────────────────────┤
│ Payment Gateway  │ Let's Encrypt     │ Voucher Engine            │
│ (Stripe/Lemon/   │ (SSL)             │ (offline payments)        │
│  Paddle/Manual)  │                   │                           │
└──────────────────┴───────────────────┴───────────────────────────┘
```

### Payment Architecture

```
                    ┌─────────────────────────┐
                    │    Payment Dispatcher    │
                    │  (pluggable providers)    │
                    └───────────┬─────────────┘
                                │
        ┌───────────────────────┼───────────────────────┐
        │                       │                       │
        ▼                       ▼                       ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│    Stripe     │     │ LemonSqueezy  │     │ Voucher System│
│  (optional)   │     │   (backup)    │     │  (offline)    │
└───────────────┘     └───────────────┘     └───────────────┘
                                                     │
                                              ┌──────┴──────┐
                                              │ Admin Panel │
                                              │ Generate    │
                                              │ Redeem      │
                                              │ Track       │
                                              └─────────────┘
```

---

## Phase 1: Foundation + Crawl4AI (Week 1)

*Replace Playwright with Crawl4AI. Build the reliable core.*

| Ticket | Description | Effort | Worker |
|--------|-------------|--------|--------|
| **P1-0** | **🔑 Crawl4AI integration** — Replace raw Playwright with Crawl4AI. CSS extraction (`JsonCssExtractionStrategy`), LLM extraction with Ollama (kimi-k2.6 / glm-5.1), built-in caching (`CacheMode.ENABLED`). Crawl4AI Dockerfile. | 4h | Kimi |
| **P1-1** | **PostgreSQL migration** — Migrate from SQLite. Full schema: `users`, `api_keys`, `usage_logs`, `subscriptions`, `vouchers`, `feature_flags`, `audit_logs`. Alembic migrations. Seed admin user. | 4h | GLM |
| **P1-2** | **Redis cache + queue** — Redis cache (5-min TTL by URL+schema hash). RQ/arq job queue for async extraction. `POST /extract` → `job_id`, poll `GET /extract/{job_id}`. | 3h | Kimi |
| **P1-3** | **Redis rate limiting** — Sliding window per-key. Configurable by tier. Replaces broken slowapi. | 2h | GLM |
| **P1-4** | **API key management** — Full CRUD: `POST/GET/DELETE /api/v1/keys`. Per-key metadata (label, tier, rate_limit, status). Admin-only. Persisted to PostgreSQL. | 2h | Kimi |
| **P1-5** | **Metrics + health** — `GET /health`, `GET /metrics` (requests, cache hits, avg latency, queue depth, error rate). | 1h | GLM |
| **P1-6** | **User accounts** — DIY JWT auth. `POST /auth/register`, `POST /auth/login`, `POST /auth/refresh`. Email verification via Resend. Role system (admin/user). | 3h | GLM |
| **P1-7** | **Docker + Dokploy deploy** — Multi-service docker-compose: API, Crawl4AI, PostgreSQL, Redis. Deploy to Dokploy. | 2h | Hamza |

---

## Phase 3: Admin Dashboard (Week 2 — PROMOTED)

*Mr. K's requirement: full management before billing. Control everything.*

| Ticket | Description | Effort | Worker |
|--------|-------------|--------|--------|
| **P3-1** | **Admin layout + auth** — React SPA with admin login. Sidebar navigation: Dashboard, Users, Subscriptions, Features, Vouchers, Payments, Logs. Role-based access (admin only). | 4h | Kimi |
| **P3-2** | **User management panel** — Table of all users with search/filter. View user details (API keys, usage, subscription). Activate/suspend/delete users. Impersonate (login as user for support). | 3h | Kimi |
| **P3-3** | **Subscription management** — View all subscriptions. Manually activate/cancel/upgrade/downgrade. Override tier limits. Add bonus credits. Subscription history timeline. | 3h | GLM |
| **P3-4** | **Feature flags system** — Backend: `feature_flags` table (feature_name, enabled, tier_required). Admin can toggle features per-user or globally. Frontend: feature gating component. | 2h | Kimi |
| **P3-5** | **API call monitor** — Real-time dashboard: requests/min, active jobs, queue depth, error rate. Filter by user/API key/endpoint. Drill down to individual request logs. | 3h | GLM |
| **P3-6** | **Voucher management panel** — Generate batch vouchers (prefix, quantity, value, expiry). List/search/redeem vouchers. Track redemption (who, when, IP). Export unused codes to CSV. | 3h | Kimi |
| **P3-7** | **Payment settings** — Configure active payment provider (Stripe/LemonSqueezy/Paddle/Manual). API keys per provider. Switch providers without code changes. Test mode toggle. | 2h | GLM |
| **P3-8** | **Revenue + analytics dashboard** — MRR chart, churn rate, conversion funnel, top users by usage. Export reports. | 2h | GLM |
| **P3-9** | **Audit logs** — Every admin action logged: who, what, when, IP. Filterable table. Immutable (append-only). | 2h | Kimi |

---

## Phase 2: Core Product Expansion (Week 3)

*What users pay for. Admin dashboard is already live.*

| Ticket | Description | Effort | Worker |
|--------|-------------|--------|--------|
| **P2-1** | **Multi-URL batch extraction** — `POST /api/v1/extract/batch`. Uses Crawl4AI `arun_many()` with `MemoryAdaptiveDispatcher`. | 3h | Kimi |
| **P2-2** | **Webhook callbacks** — Optional `webhook_url` on extract. POSTs results when job completes. Retry logic (3x exponential backoff). | 3h | Kimi |
| **P2-3** | **LLM extraction endpoint** — `POST /api/v1/extract/ai` with `LLMExtractionStrategy`. Supports kimi/glm via Ollama. No selectors needed. | 2h | GLM |
| **P2-4** | **Screenshot extraction** — Crawl4AI built-in screenshot. Type `screenshot` in schema. Base64 PNG response. | 1h | GLM |
| **P2-5** | **Export formats** — `?format=csv`, `?format=markdown`, `?format=xml`. Content negotiation via `Accept` header. | 1h | GLM |
| **P2-6** | **User dashboard** — Non-admin user view: API keys, usage charts, billing portal link, profile settings. Lighter version of admin panel. | 3h | GLM |

---

## Phase 4: Monetization — Multi-Payment + Voucher (Week 4)

*Revenue with zero dependency on any single payment provider.*

| Ticket | Description | Effort | Worker |
|--------|-------------|--------|--------|
| **P4-1** | **Payment dispatcher** — Abstract `PaymentProvider` base class. Pluggable: Stripe, LemonSqueezy, Paddle, Manual. Configure active provider in admin panel. Test mode per provider. | 4h | Kimi |
| **P4-2** | **LemonSqueezy integration** — Primary alternative to Stripe. Subscription tiers, webhook handling, license key validation. No Stripe account needed. Free to start. | 3h | Kimi |
| **P4-3** | **Paddle integration** (optional) — Billing infrastructure for global tax compliance. Use if LemonSqueezy doesn't work for our region. | 2h | GLM |
| **P4-4** | **Voucher system — Backend** — Voucher codes: prefix-based (e.g., `KAF-XXXX-XXXX`), configurable value (days or credits), expiry date, max redemptions, redemption tracking. `POST /api/v1/vouchers/redeem`. Anti-abuse: rate limit, IP tracking. | 3h | Kimi |
| **P4-5** | **Voucher system — Frontend** — Redeem voucher on signup or in dashboard. Shows "Voucher applied: Pro plan, 30 days". Admin panel for batch generation + export. | 2h | GLM |
| **P4-6** | **Trial system** — 7-day free trial (100 extractions). Auto-activates on signup. No credit card required. Admin can extend trials. Email reminders on day 3 and day 6 via Resend. | 2h | GLM |
| **P4-7** | **Manual payment flow** — For offline/voucher-only users. Admin marks payment as "received" (cash, bank transfer, crypto). System activates subscription. Receipt generated. | 2h | Kimi |
| **P4-8** | **Invoice generation** — PDF invoices for all payment types. Downloadable from user dashboard. Custom branding (Kaf Center logo). | 2h | GLM |

---

## Phase 5: Revenue-Ready Features (COMPLETE ✅)

| Ticket | Description | Effort | Status |
|--------|-------------|--------|:------:|
| **P5-1** | API docs + SDKs (Python async, JS/TS zero-dep, cURL examples, dev portal) | 4h | ✅ Complete |
| **P5-2** | Scheduled extractions (cron via croniter, arq enqueue, webhook on completion) | 4h | ✅ Complete |
| **P5-3** | Exports & integrations (Slack Block Kit, history API, Google Sheets pipeline) | 3h | ✅ Complete |
| **P5-4** | Team accounts (orgs, owner/admin/member/viewer roles, per-member usage) | 5h | ✅ Complete |
| **P5-5** | Usage alerts + quotas (80/90/100% thresholds, Resend email, hard caps) | 3h | ✅ Complete |

### Tier 3 (Deferred — activate at 50+ paying users)

| Ticket | Description | Effort |
|--------|-------------|--------|
| P6-1 | Proxy rotation pool (residential + datacenter) | 5h |
| P6-2 | Anti-bot detection bypass | 4h |
| P6-3 | Firecrawl Cloud fallback (when anti-bot needed) | 4h |
| P6-4 | White-label option (custom domain, branding) | 6h |

### Phase 5 Stats

| Metric | Value |
|--------|:-----:|
| API endpoints deployed | 43 |
| Database migrations | 005 |
| SDKs shipped | Python (httpx) + JS/TS (fetch) |
| Admin panels | 2 (Dashboard + Dev Portal) |
| Deployed at | extract.kafcenter.com + ai.kafcenter.com |

---

## Payment Provider Comparison

| Provider | Setup | Fees | Stripe Account Needed? | Best For |
|----------|-------|------|----------------------|----------|
| **LemonSqueezy** ✅ | 10 min | 5% + $0.50 | **No** | Startups, global tax handled |
| **Paddle** | 30 min | 5% + $0.50 | **No** | SaaS with global customers |
| **Stripe** (optional) | 30 min | 2.9% + $0.30 | **Yes** | US/European businesses |
| **Voucher System** ✅ | Built by us | **0%** | **No** | Offline, cash, crypto, promotions |
| **Manual** ✅ | Built by us | **0%** | **No** | Direct bank transfers |

**Recommendation:** Launch with **LemonSqueezy + Voucher System**. Add Stripe later if needed. LemonSqueezy handles global tax (VAT/GST) automatically — huge time saver.

---

## Voucher System Design

```
┌──────────────────────────────────────────────────────┐
│                  VOUCHER ENGINE                       │
├──────────────────────────────────────────────────────┤
│                                                      │
│  Admin generates vouchers:                           │
│  ┌─────────────────────────────────────────────┐     │
│  │ Prefix:   KAF-                               │     │
│  │ Quantity: 100                                │     │
│  │ Value:    30 days Pro plan                   │     │
│  │ Expiry:   2026-12-31                         │     │
│  │ Max uses: 1 per user                         │     │
│  │         [Generate & Export CSV]              │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  User redeems:                                       │
│  ┌─────────────────────────────────────────────┐     │
│  │ Enter code: [KAF-A7X9-B2M4]                 │     │
│  │         [Redeem]                             │     │
│  └─────────────────────────────────────────────┘     │
│                                                      │
│  Code format:  KAF-XXXX-XXXX                         │
│  (36^8 = 2.8 trillion combinations)                  │
│                                                      │
│  Tracking:                                           │
│  • Who redeemed (user_id)                            │
│  • When (timestamp)                                  │
│  • IP address                                        │
│  • What they got (plan, duration)                    │
└──────────────────────────────────────────────────────┘
```

### Voucher API Endpoints

| Endpoint | Admin | Description |
|----------|:-----:|-------------|
| `POST /api/v1/admin/vouchers/generate` | ✅ | Generate batch of voucher codes |
| `GET /api/v1/admin/vouchers` | ✅ | List all vouchers with filters |
| `GET /api/v1/admin/vouchers/export` | ✅ | Export unused codes as CSV |
| `DELETE /api/v1/admin/vouchers/{id}` | ✅ | Invalidate a voucher |
| `POST /api/v1/vouchers/redeem` | — | Redeem a voucher code |
| `GET /api/v1/vouchers/history` | — | User's redemption history |

---

## Admin Dashboard — Full Feature Map

```
Admin Panel (/admin)
│
├── 📊 Overview
│   ├── MRR (monthly recurring revenue)
│   ├── Active users (today/week/month)
│   ├── Total API calls (24h)
│   ├── Queue depth
│   ├── Error rate
│   └── Recent signups
│
├── 👥 Users
│   ├── Search/filter/sort
│   ├── User detail (keys, usage, subscription, vouchers)
│   ├── Activate / Suspend / Delete
│   ├── Impersonate (login as user)
│   ├── Manual credit adjustment
│   └── Export users CSV
│
├── 💳 Subscriptions
│   ├── All active subscriptions
│   ├── Upgrade / Downgrade / Cancel
│   ├── Override tier limits
│   ├── Add bonus extractions
│   ├── Subscription history
│   └── Churn analytics
│
├── 🎫 Vouchers
│   ├── Generate batch
│   ├── List / Search / Filter
│   ├── Redemption log
│   ├── Export unused
│   └── Invalidate codes
│
├── ⚙️ Features
│   ├── Feature list with toggles
│   ├── Per-user overrides
│   ├── Tier requirements
│   └── A/B test flags
│
├── 📈 Analytics
│   ├── API calls over time
│   ├── Cache hit rate
│   ├── Avg latency (p50/p95/p99)
│   ├── Top users by usage
│   ├── Top domains extracted
│   └── Revenue charts
│
├── 💰 Payments
│   ├── Active provider selector
│   ├── Provider API keys
│   ├── Test/Live mode toggle
│   ├── Transaction history
│   └── Manual payment entry
│
├── 📋 Audit Logs
│   ├── Filter by admin/user/action
│   ├── Search
│   ├── Export
│   └── Immutable log
│
└── 🔔 Settings
    ├── Global rate limits
    ├── Trial duration
    ├── Email templates
    └── Maintenance mode
```

---

## Pricing Tiers

| Tier | Price | Extractions/mo | Rate Limit | Features |
|------|-------|---------------|------------|----------|
| **Free Trial** | $0 (7 days) | 100 | 10/min | CSS extraction only |
| **Hobby** | $19/mo | 5,000 | 60/min | CSS + Markdown + Screenshots |
| **Pro** | $99/mo | 50,000 | 300/min | + LLM extraction + Batch + Webhooks |
| **Enterprise** | Custom | Custom | Custom | + Proxy rotation + Anti-bot + SLA |

**Voucher values:** Same as above — voucher gives N days of a plan.  
**Example:** "KAF-PRO-30D" = 30 days of Pro plan, no credit card needed.

---

## Rollout Schedule (Revised)

```
Week 1:  Phase 1 — Foundation + Crawl4AI
         ├── Day 1-2: P1-0 Crawl4AI + P1-1 PostgreSQL schema
         ├── Day 3-4: P1-2 Redis cache/queue + P1-3 Rate limiting
         ├── Day 5-6: P1-4 Key management + P1-5 Metrics + P1-6 User accounts
         └── Day 7:   P1-7 Docker + Dokploy deploy

Week 2:  Phase 3 — Admin Dashboard (PROMOTED)
         ├── Day 1-2: P3-1 Admin layout + auth + P3-2 User management
         ├── Day 3-4: P3-3 Subscription mgmt + P3-4 Feature flags
         ├── Day 5-6: P3-5 API monitor + P3-6 Voucher panel + P3-7 Payment settings
         └── Day 7:   P3-8 Analytics + P3-9 Audit logs

Week 3:  Phase 2 — Core Product
         ├── Day 1-2: P2-1 Batch extraction + P2-2 Webhooks
         ├── Day 3-4: P2-3 LLM extraction + P2-4 Screenshots
         ├── Day 5-6: P2-5 Export formats + P2-6 User dashboard
         └── Day 7:   Integration testing

Week 4:  Phase 4 — Multi-Payment + Voucher
         ├── Day 1-2: P4-1 Payment dispatcher + P4-2 LemonSqueezy
         ├── Day 3-4: P4-4 Voucher backend + P4-5 Voucher frontend
         ├── Day 5-6: P4-6 Trial system + P4-7 Manual payments + P4-8 Invoices
         └── Day 7:   End-to-end test + 🚀 LAUNCH
```

---

## Database Schema (Key Tables)

```sql
-- Users & Auth
users (id, email, password_hash, name, role, status, created_at)
api_keys (id, user_id, key_hash, label, tier, rate_limit, status, last_used_at)
refresh_tokens (id, user_id, token_hash, expires_at)

-- Usage
usage_logs (id, api_key_id, endpoint, url, duration_ms, status, created_at)
extraction_cache (id, cache_key_hash, result_json, created_at, expires_at)

-- Subscriptions & Payments
subscriptions (id, user_id, plan, status, starts_at, ends_at, provider, provider_id)
payment_transactions (id, user_id, amount, currency, provider, status, metadata)
invoices (id, user_id, transaction_id, pdf_path, created_at)

-- Vouchers
vouchers (id, code, plan, duration_days, extraction_credits, expires_at, max_uses, 
          used_count, created_by, created_at, status)
voucher_redemptions (id, voucher_id, user_id, redeemed_at, ip_address)

-- Feature Flags
feature_flags (id, name, description, enabled, tier_required, created_at)
user_feature_overrides (id, user_id, feature_id, enabled)

-- Admin
audit_logs (id, admin_id, action, target_type, target_id, details_json, ip, created_at)
admin_sessions (id, admin_id, token_hash, expires_at)
```

---

## Worker Assignments

| Worker | Model | Provider | Role |
|--------|-------|----------|------|
| **Hamza** | deepseek-v4-pro | DeepSeek | CEO — architecture, review, Dokploy deploys |
| **Kimi** | kimi-k2.6:cloud | Ollama Cloud | Senior Engineer — Crawl4AI, admin dashboard, payment dispatcher |
| **GLM** | glm-5.1:cloud | Ollama Cloud | Full-Stack — PostgreSQL, Redis, API monitor, vouchers |
| **OpenCode** | deepseek-v4-pro | DeepSeek | QA — code review, test coverage |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|-----------|
| Crawl4AI browser fails in Docker | High | Pre-built Docker image with Chromium |
| Payment provider rejects web scraping | Medium | Multi-provider: switch LemonSqueezy → Paddle → Manual |
| Voucher abuse (brute force) | Medium | Rate limit 5 attempts/hour per IP. Ban after 20 failures. |
| Admin panel security breach | High | JWT + role check on every endpoint. Audit log immutable. |
| PostgreSQL slow with large usage_logs | Low | Partition by month. Archive > 90 days. |
| Ollama Cloud downtime | Medium | CSS extraction works without LLM |

---

## Success Metrics (v1.0 Launch)

- [ ] 99% uptime over first 30 days
- [ ] P95 extraction latency < 5 seconds
- [ ] Cache hit rate > 40%
- [ ] < $60/mo infrastructure cost (PostgreSQL + Redis added)
- [ ] Admin dashboard fully functional (all 9 panels)
- [ ] At least 1 paying customer via LemonSqueezy OR voucher
- [ ] Zero AGPL-3.0 code in our repo

---

*Plan v2.0 approved by Mr. K. Admin dashboard = non-negotiable. Payments = flexible. Ready to execute.*
