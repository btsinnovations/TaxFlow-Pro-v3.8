# TASK-002: Frontend Placeholder Cleanup

## Status
Inbox

## Goal
Replace all remaining placeholder pages in the v3.9 frontend with real components, and remove mock API files / ghost routes.

## Depends On
TASK-001 audit identifying exact placeholder locations.

## Deliverables
1. Updated frontend source with placeholders replaced
2. Deleted mock API / ghost route files
3. Frontend smoke test result documented

## Acceptance Criteria
- `grep -r "PlaceholderPage" frontend/src/` returns nothing
- `grep -r "mockAPI" frontend/src/` returns nothing (unless intentionally retained)
- Frontend dev server starts without errors
- Boot/login/protected-route flow passes manual smoke test
