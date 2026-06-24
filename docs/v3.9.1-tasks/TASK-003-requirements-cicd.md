# TASK-003: Requirements Cleanup + CI/CD

## Status
Inbox

## Goal
Clean and pin Python dependencies, split dev vs production, add missing `sqlcipher3` if in scope, and create a GitHub Actions workflow for tests.

## Depends On
TASK-001 audit identifying unused dependencies.

## Deliverables
1. `requirements.txt` — pinned, minimal production deps
2. `requirements-dev.txt` — test/lint/dev tools
3. `.github/workflows/tests.yml` — runs backend + pipeline tests on push/PR
4. `.env.example` documenting production env vars

## Acceptance Criteria
- `pip install -r requirements-dev.txt && pytest backend/tests/ tests/` passes
- CI workflow is syntactically valid and targets correct Python versions
- No unused deps remain in production requirements
