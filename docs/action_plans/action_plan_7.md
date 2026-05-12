# Action Plan 7 - Production Hardening and CI

## Goal
Make Rex stable enough for daily founder use without losing data or silently failing.

## Why This Matters (Personal Context)
This phase turns Rex from a working prototype into a reliable daily companion the founder can trust with real life data (voice conversations, personal rules, budget tracking, dating context, immigration plans, etc.). The founder needs confidence that messages won’t be lost, the app won’t silently fail during background voice or long sessions, tests catch regressions, and the system is observable and recoverable -- especially as Rex becomes a core part of daily walking/co-pilot routines.

## Key Deliverables
- CI for backend tests, Flutter analyze, Flutter tests
- Structured logging
- Health/readiness endpoints
- Integration test mode for real Grok/Supabase smoke tests
- Basic monitoring and backup notes
- Optional rate limiting and auth if exposed beyond private use

## Estimated Time
3-6 focused days (solo founder pace)

## Dependencies
Can run in parallel after Action Plan 1 (Time-Aware Prompt Foundation) is complete. Ideally after Action Plan 2 (voice) for full coverage.

## Checklist (10 Actionable Steps)

1. [ ] **Audit current production readiness**
   - Exact files to create or modify: `docs/deployment.md`, `README.md`, `backend/app/main.py`, `backend/app/config.py`, existing tests under `tests/`, existing Flutter tests under `test/`
   - What must be implemented: Review the current deployment docs, environment variables, CORS behavior, backend lifespan setup, route health, logging, test commands, and Flutter build assumptions. Identify what is already production-ready and what needs hardening.
   - Success criteria: The production-hardening scope is clear, no runtime behavior changes are made during the audit, and the follow-up steps can be implemented without guessing.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `docs: audit production readiness`
   - Rough time estimate: 1-2 hours

2. [ ] **Add GitHub Actions CI workflow**
   - Exact files to create or modify: `.github/workflows/ci.yml`, optionally `.github/dependabot.yml`
   - What must be implemented: Create a CI workflow that runs backend tests, Flutter dependency resolution, `flutter analyze`, and `flutter test` on pull requests and pushes. Use caching for Python and Flutter dependencies where practical.
   - Success criteria: CI can run without real Grok or Supabase secrets, fails on backend test regressions, fails on Flutter analyzer errors, and fails on Flutter test regressions.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `ci: add backend and flutter checks`
   - Rough time estimate: 3-5 hours

3. [ ] **Add structured backend logging**
   - Exact files to create or modify: `backend/app/logging_config.py`, `backend/app/main.py`, `backend/app/config.py`, backend service files where errors are currently silent
   - What must be implemented: Add consistent structured logging for startup, shutdown, request errors, Grok failures, Supabase failures, memory extraction failures, file validation failures, and unexpected exceptions. Avoid logging secrets or sensitive full user messages by default.
   - Success criteria: Logs are useful for debugging production issues, redact sensitive values, include request/service context where safe, and do not spam normal successful chat flows.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `feat: add structured backend logging`
   - Rough time estimate: 4-6 hours

4. [ ] **Add health and readiness endpoints**
   - Exact files to create or modify: `backend/app/routes/health.py`, `backend/app/main.py`, `backend/app/services/ai_service.py`, `backend/app/services/memory_service.py`, `tests/test_health_routes.py`
   - What must be implemented: Add lightweight `/health` and `/ready` endpoints. `/health` should confirm the app process is alive. `/ready` should validate required config and optionally perform safe shallow checks for Grok/Supabase availability without expensive calls.
   - Success criteria: VPS monitoring can distinguish alive from ready, missing config produces clear readiness failure, and tests cover healthy, missing-config, and dependency-error cases without real external calls.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests/test_health_routes.py`
   - Suggested git commit message: `feat: add health and readiness endpoints`
   - Rough time estimate: 3-5 hours

5. [ ] **Create integration smoke test mode**
   - Exact files to create or modify: `tests/integration/test_grok_supabase_smoke.py`, `pytest.ini` or `pyproject.toml`, `.env.example`, `docs/deployment.md`
   - What must be implemented: Add optional integration tests that only run when an explicit environment flag is set. Smoke tests should validate real Grok connectivity, real Supabase connectivity, and a minimal chat/memory round trip against a safe test conversation.
   - Success criteria: Normal CI never calls real Grok or Supabase, local smoke tests can be run intentionally with real credentials, and failures produce clear setup guidance.
   - Verification / test command: `RUN_INTEGRATION_TESTS=1 PYTHONPATH=backend python3 -m pytest -q tests/integration`
   - Suggested git commit message: `test: add optional integration smoke tests`
   - Rough time estimate: 4-7 hours

6. [ ] **Document backup and restore procedures**
   - Exact files to create or modify: `docs/backup_restore.md`, `docs/deployment.md`, `README.md`
   - What must be implemented: Document how to back up Supabase data, export important tables, restore data, rotate service keys, protect `.env`, and recover the VPS service after a crash or redeploy.
   - Success criteria: A solo founder can follow the docs to avoid losing conversations, memories, rules, plans, commitments, and uploaded file metadata.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `docs: add backup and restore procedures`
   - Rough time estimate: 2-4 hours

7. [ ] **Add basic production runbook and systemd template**
   - Exact files to create or modify: `deploy/rex.service.example`, `docs/deployment.md`, `.env.example`
   - What must be implemented: Add a practical `systemd` service template for the FastAPI backend, plus commands for install, restart, status, logs, environment setup, rollback, and common failure recovery.
   - Success criteria: The VPS deployment path is copy-pasteable enough for private use, and future deployment changes do not depend on memory or ad hoc terminal history.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests`
   - Suggested git commit message: `docs: add systemd deployment runbook`
   - Rough time estimate: 2-4 hours

8. [ ] **Add lightweight error monitoring hooks**
   - Exact files to create or modify: `backend/app/config.py`, `backend/app/main.py`, `backend/app/logging_config.py`, optionally `lib/core/config/app_config.dart`
   - What must be implemented: Prepare optional monitoring integration without making it mandatory. Add config flags for error reporting, basic request IDs, and clear places to plug in Sentry or another lightweight service later.
   - Success criteria: Production errors can be traced through logs today, optional monitoring can be enabled later without refactoring core services, and no required third-party monitoring dependency is introduced unless intentionally chosen.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `feat: prepare lightweight error monitoring`
   - Rough time estimate: 3-5 hours

9. [ ] **Add private-instance safety controls**
   - Exact files to create or modify: `backend/app/config.py`, `backend/app/main.py`, `backend/app/dependencies.py`, `backend/app/routes/chat.py`, `docs/deployment.md`, tests under `tests/`
   - What must be implemented: Add optional private-instance controls such as a simple API key header, stricter CORS defaults, request size limits, and basic rate limiting if the backend is exposed publicly. Keep local development simple.
   - Success criteria: The private VPS instance is harder to abuse if exposed to the internet, existing Flutter/backend flows can be configured to pass the required key, and tests cover allowed/denied requests.
   - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
   - Suggested git commit message: `feat: add private instance safety controls`
   - Rough time estimate: 5-8 hours

10. [ ] **Run full validation and production readiness rehearsal**
    - Exact files to create or modify: No code changes expected unless validation exposes bugs
    - What must be implemented: Run full backend and Flutter validation, run optional integration smoke tests if credentials are available, rehearse backend startup with production-like env vars, confirm logs and health/readiness endpoints, and verify deployment docs are accurate.
    - Success criteria: CI-equivalent checks pass locally, optional smoke tests pass when enabled, deployment docs match reality, and Rex has a clear operational path for daily founder use.
    - Verification / test command: `PYTHONPATH=backend python3 -m pytest -q tests && flutter analyze && flutter test`
    - Suggested git commit message: `test: validate production hardening`
    - Rough time estimate: 3-6 hours

## Revision History
- 2026-05-12 - Action Plan 7 created from Alignment Plan and updated REX_VISION.md
