# TASK-3.10.02 — Profile Roles & Memberships

**Owner:** Jane (when assigned)
**Goal:** Add role-based access per profile.

## Files

- `backend/models.py` — add `profile_memberships` table
- `backend/local/roles.py` — role constants and permission checks
- `backend/auth.py` / `backend/routers/auth.py` — load membership with user
- `backend/routers/profiles.py` — manage memberships
- `backend/tests/test_roles.py`

## Requirements

1. Roles: `admin`, `accountant` (read-only), `bookkeeper` (edit, no admin), `viewer`.
2. Each user has one role per profile via `profile_memberships`.
3. Profile creator defaults to `admin`.
4. Only admins can change roles.
5. Permission helpers:
   - `can_read(profile_id, current_user)`
   - `can_write(profile_id, current_user)`
   - `can_admin(profile_id, current_user)`
6. Update `get_current_user` dependency to resolve profile membership.

## Tests

- Assign role to user.
- Read-only accountant blocked from POST/PUT/DELETE.
- Bookkeeper allowed to create transactions, blocked from role changes.
- Admin can promote/demote.
- Creator is admin.

## Constraints

- No cloud auth; all local.
- Must respect `TAXFLOW_SINGLE_USER` default.
- All changes tested.
