# Kaf Extract — Implementation Plan

## Task Breakdown

### Phase 1: Scaffold (Hamza — direct)
- [x] Project directory structure
- [x] SPEC.md
- [ ] requirements.txt + pyproject.toml
- [ ] src/config.py — env-based settings
- [ ] src/models/extract.py — Pydantic models
- [ ] src/models/apikey.py — API key model
- [ ] Dockerfile + docker-compose.yml
- [ ] .env.example + .gitignore + README.md

### Phase 2: Core (Worker: kimi-k2.6 — Senior Engineer)
- [ ] src/main.py — FastAPI app with routes mounted
- [ ] src/services/extractor.py — Playwright extraction engine
- [ ] src/routers/extract.py — POST /api/v1/extract endpoint
- [ ] src/routers/health.py — GET /health endpoint

### Phase 3: Security (Hamza — direct)
- [ ] src/services/auth.py — API key hashing + validation
- [ ] src/middleware/rate_limit.py — slowapi rate limiter
- [ ] src/api/routes.py — Route definitions with dependencies

### Phase 4: Testing (Worker: glm-5.1 — QA Engineer)
- [ ] tests/test_health.py — Health endpoint tests
- [ ] tests/test_extract.py — Extract endpoint tests (mock browser)
- [ ] tests/test_auth.py — Auth + rate limit tests

### Phase 5: Review & Polish
- [ ] Code quality review
- [ ] Fix any issues
- [ ] Final integration test

### Phase 6: Ship
- [ ] Git init, commit, push to GitHub
- [ ] Create Dokploy project
- [ ] Deploy from GitHub

## Worker Assignments

| Task | Worker | Model |
|------|--------|-------|
| Core API + Extractor | kimi-k2.6 | ollama-cloud/kimi-k2.6 |
| Tests | glm-5.1 | ollama-cloud/glm-5.1 |
| Scaffolding | Hamza (direct) | N/A |
