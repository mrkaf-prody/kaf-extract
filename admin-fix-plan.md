# Kaf Extract — Admin Dashboard Fix Plan

**Date:** 2026-05-29  
**Scope:** All admin panel pages + backend routers + SQL models  
**Target:** Productionize every admin screen with real API data

---

## Executive Summary

The admin panel has **5 categories of bugs** blocking production use:

1. **API path mismatch** — frontend calls `/v1/...`, backend serves `/api/v1/...` → 404
2. **2FA hard block** — `admin_required` enforces TOTP but no setup flow exists → 403 lockout
3. **Mock data** — Overview, Analytics, Monitor, Features, Audit Logs are 100% fake
4. **Missing SQL model** — No `AuditLog` table, so audit trail is impossible
5. **Missing backend endpoints** — No analytics aggregation, no feature flags API, no audit log CRUD

---

## Phase 1: Unblock Admin Access (Priority: CRITICAL)

### 1.1 Fix 2FA Enforcement
**Problem:** `admin_required` raises 403 if `totp_enabled == false`, but no setup UI exists.

**Decision needed from Mr. K:**
- **Option A (Recommended):** Temporarily **relax** `admin_required` to only check `role == admin`. Move 2FA enforcement to a later hardening phase after the dashboard is functional.
- **Option B:** Build full TOTP setup (QR code generation, verify endpoint, backup codes) in both backend and admin Profile page.

**My recommendation:** Option A for now. 2FA is a security enhancement, not a blocker for business operations. We can ship the dashboard first, then harden with 2FA in a dedicated security sprint.

### 1.2 Files to touch:
- `src/middleware/auth.py` — comment out or gate the `totp_enabled` check
- `admin/src/pages/ProfilePage.tsx` — add a "2FA (coming soon)" placeholder so users know it's on the roadmap

---

## Phase 2: Fix API Path Mismatches (Priority: CRITICAL)

### 2.1 Frontend path corrections
All admin pages must prefix API calls with `/api/v1` instead of `/v1`.

| Page | Current Path | Correct Path |
|------|-------------|--------------|
| SubscriptionsPage.tsx | `/v1/admin/subscriptions` | `/api/v1/admin/subscriptions` |
| VouchersPage.tsx | `/v1/admin/vouchers` | `/api/v1/admin/vouchers` |
| PaymentsPage.tsx | `/v1/admin/payments` | `/api/v1/admin/payments` |
| OverviewPage.tsx | (mock, will be `/api/v1/admin/stats`) | `/api/v1/admin/stats` |
| MonitorPage.tsx | (mock, will be `/metrics`) | `/metrics` |

### 2.2 Backend verification
- `src/routers/admin.py` — already has `/api/v1/admin` prefix ✅
- `src/routers/admin_payments.py` — already has `/api/v1/admin/payments` prefix ✅
- `src/routers/vouchers.py` — already has `/api/v1` prefix ✅

**Fix:** Search/replace all `apiFetch('/v1/...')` → `apiFetch('/api/v1/...')` in admin pages.

---

## Phase 3: Real Data — Overview + Monitor (Priority: HIGH)

### 3.1 OverviewPage.tsx — wire to `/api/v1/admin/stats`
**Backend already exists:** `src/routers/admin.py` has `@router.get("/stats")` returning real DB counts:
- `total_users` — `SELECT COUNT(*) FROM users`
- `active_subscriptions` — `SELECT COUNT(*) FROM subscriptions WHERE status='active'`
- `api_calls_today` — from `src.services.metrics.get_metrics()`
- `error_rate_percent` — computed from metrics

**Frontend changes:**
- Replace `setTimeout` mock with `apiFetch('/api/v1/admin/stats')`
- Replace `generateChartData()` with `/metrics` endpoint for 24h chart data
- Replace empty `RECENT_ACTIVITY` with a new `/api/v1/admin/activity` endpoint OR use usage_logs table

### 3.2 MonitorPage.tsx — wire to `/metrics`
**Backend already exists:** `src/routers/metrics.py` returns:
- `requests_total`, `cache_hits`, `cache_misses`
- `avg_duration_ms`, `error_count`, `uptime_seconds`
- `db_status`, `redis_status`, `queue_depth`

**Frontend changes:**
- Replace `generateMockMetrics()` with `apiFetch('/metrics')`
- Remove `recent_errors` mock; either add a real errors endpoint or hide that panel until Phase 5

---

## Phase 4: Real Data — Subscriptions + Vouchers + Payments (Priority: HIGH)

### 4.1 SubscriptionsPage.tsx
**Backend already exists:** `src/routers/admin.py` `@router.get("/subscriptions")` with search/status/plan filters.

**Frontend changes:**
- Fix path to `/api/v1/admin/subscriptions`
- Wire `handleChangePlan` and `handleCancel` to real PATCH/POST endpoints
- Add backend endpoints if missing: `PATCH /api/v1/admin/subscriptions/{id}` and `POST /api/v1/admin/subscriptions/{id}/cancel`

### 4.2 VouchersPage.tsx
**Backend already exists:** `src/routers/vouchers.py` has:
- `POST /api/v1/admin/vouchers/generate`
- `GET /api/v1/admin/vouchers`
- `GET /api/v1/admin/vouchers/export`
- `DELETE /api/v1/admin/vouchers/{id}`

**Frontend changes:**
- Fix path to `/api/v1/admin/vouchers`
- Verify export endpoint uses `/api/v1/admin/vouchers/export`

### 4.3 PaymentsPage.tsx
**Backend already exists:** `src/routers/admin_payments.py` has:
- `GET /api/v1/admin/payments` — returns masked provider config
- `PATCH /api/v1/admin/payments` — updates provider config

**Frontend changes:**
- Fix path to `/api/v1/admin/payments`
- Transaction history section is empty (no endpoint). Decision needed:
  - **Option A:** Hide transaction table until LemonSqueezy webhooks are live
  - **Option B:** Add `GET /api/v1/admin/payments/transactions` returning `Invoice` table rows

**My recommendation:** Option A for now. Hide the "Transaction History" panel behind a "Coming soon" badge. Payment transactions require live provider webhooks which aren't configured yet.

---

## Phase 5: Real Data — Analytics (Priority: MEDIUM)

### 5.1 Problem
AnalyticsPage shows MRR, ARPU, churn rate, trial conversion, signups per day — all randomly generated.

### 5.2 Decision needed from Mr. K:
- **Option A:** Build a comprehensive analytics aggregation endpoint (`GET /api/v1/admin/analytics?range=7d|30d|90d`) that queries:
  - `User.created_at` for signup trends
  - `Subscription.plan + current_period_end` for MRR
  - `Trial` table for conversion rates
  - `UsageLog` for API call volume
  
- **Option B:** Remove the Analytics page from the admin nav until we have enough real revenue data to make charts meaningful.

**My recommendation:** Option A. Even with low user counts, showing real data (even if flat) builds trust. We can hide the page if `total_users < 5`.

### 5.3 New backend endpoint needed:
```python
@router.get("/analytics")
async def admin_analytics(
    range: str = Query("30d"),  # 7d, 30d, 90d
    admin: dict = Depends(admin_required),
    db: AsyncSession = Depends(get_db),
):
    # Return: mrr, arpu, churn_rate, trial_conversion, signups_per_day[], revenue_by_plan[]
```

---

## Phase 6: Real Data — Features + Audit Logs (Priority: MEDIUM)

### 6.1 FeaturesPage.tsx
**Current state:** Pure mock toggle switches that don't persist.

**Decision needed from Mr. K:**
- **Option A:** Add a `features` JSONB column to `Subscription` or a dedicated `FeatureFlag` SQL model + CRUD endpoints. This is the "proper" way but takes 2-3 hours.
- **Option B:** Remove the Features page from admin nav for v2.0. Feature flags are an advanced need for when you have 100+ users.

**My recommendation:** Option B. Feature flags are premature optimization at this stage. Remove from nav, re-add when needed.

### 6.2 AuditLogsPage.tsx
**Current state:** Pure mock with randomized fake logs.

**Backend work needed:**
1. Add `AuditLog` SQL model to `sql_models.py`:
```python
class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g. "user.suspend"
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[str] = mapped_column(String(100), nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

2. Create Alembic migration for the new table
3. Add `POST /api/v1/admin/logs` (internal, for services to call) and `GET /api/v1/admin/logs` (for admin panel)
4. Instrument all admin mutations to write audit records:
   - `user.update`, `user.delete`, `user.suspend`
   - `subscription.cancel`, `subscription.upgrade`
   - `voucher.generate`, `voucher.invalidate`
   - `payment.config_update`

**Frontend changes:**
- Replace `generateMockLogs()` with `apiFetch('/api/v1/admin/logs')`
- Keep existing filter UI (action type, admin email, date range)
- Keep CSV export

---

## Phase 7: Build & Deploy (Priority: CRITICAL)

### 7.1 Test matrix
| Page | Test |
|------|------|
| Overview | Stats load from DB, chart from /metrics |
| Users | Real user list, suspend/activate/delete persist |
| Subscriptions | Real subscription list, filters work |
| Vouchers | Generate + list + invalidate + export CSV |
| Payments | Provider config save/load, masked keys |
| Monitor | Live metrics refresh every 5s |
| Analytics | Real signup/MRR data (if Phase 5 built) |
| Audit Logs | Real audit trail (if Phase 6 built) |
| Profile | Password change works, 2FA placeholder shown |

### 7.2 Deployment steps
1. `cd admin && npm run build`
2. `cd .. && docker build -t kaf-extract .`
3. Push to Dokploy app `A4IIVk3534rQ1fXByUmtc`
4. Verify at `https://extract.kafcenter.com/admin/`

---

## Time Estimates

| Phase | Hours | Priority |
|-------|-------|----------|
| 1 — Unblock 2FA | 0.5h | CRITICAL |
| 2 — Fix API paths | 0.5h | CRITICAL |
| 3 — Overview + Monitor | 1.5h | HIGH |
| 4 — Subscriptions + Vouchers + Payments | 1.0h | HIGH |
| 5 — Analytics endpoint + page | 2.0h | MEDIUM |
| 6 — Audit Log model + endpoints + instrumentation | 2.5h | MEDIUM |
| 6 — Features (defer/remove) | 0.25h | LOW |
| 7 — Build + Deploy + Test | 1.0h | CRITICAL |
| **Total** | **~9.25h** | |

---

## Mr. K Decisions Needed

1. **2FA:** Relax the hard block now and add proper TOTP later? (Recommended: Yes)
2. **Analytics:** Build real analytics endpoint or defer? (Recommended: Build it)
3. **Feature Flags:** Remove from nav until v2.1? (Recommended: Yes, remove)
4. **Audit Logs:** Build full audit trail now or defer? (Recommended: Build it — compliance is non-negotiable for a SaaS)
5. **Transaction History:** Hide "Coming soon" until LemonSqueezy webhooks are live? (Recommended: Yes)

Reply with **"Execute all phases"** or tell me which to skip/modify, and I'll start immediately.
