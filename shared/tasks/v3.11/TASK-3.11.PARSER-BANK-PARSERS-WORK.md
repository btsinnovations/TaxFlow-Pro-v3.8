# TASK-3.11.PARSER — Bank Parser Expansion

**Owner:** Jane  
**Goal:** Inventory, normalize, and integrate all existing bank parsers into v3.11 with auto-detection and fixtures.

## Current State

- Parsers likely live in `backend/parsers/` or `backend/parser/` directory.
- `backend/api.py` has transaction import endpoints.
- Parser count/branding in frontend may be stale.
- Tests: **missing**

## Files

- Inspect `backend/parsers/`, `backend/parser/`, and any `institution_*.py` files.
- Create/update `backend/parsers/detect.py` with auto-detection function.
- `backend/tests/test_parser_detection.py` — new
- `frontend/src/components/Hero.tsx` or branding component — update count.
- `docs/SUPPORTED_INSTITUTIONS.md` — new or update.

## Tasks

1. **Inventory (3.11.PARSER.01)**
   - List every parser module.
   - Confirm each implements a common interface: `can_parse(rows/headers)` + `parse(rows, account_id, user_id)` returning list of transaction dicts.

2. **Normalize interface (3.11.PARSER.02)**
   - Add `detect.py` registry of parsers.
   - Add `POST /api/transactions/detect-parser` endpoint that accepts sample rows and returns parser name + confidence.

3. **Fixtures (3.11.PARSER.03)**
   - Add minimal CSV sample fixture for each supported institution under `backend/tests/fixtures/parsers/`.
   - Test each parser against its fixture.

4. **Branding update (3.11.PARSER.04)**
   - Update institution count in Hero / landing page.

5. **Documentation (3.11.PARSER.05)**
   - Write `docs/SUPPORTED_INSTITUTIONS.md` with institution list and input format notes.

## Tests Required

- `test_detect_parser_returns_correct_institution`
- `test_detect_parser_unknown_returns_none`
- `test_all_parsers_have_fixtures`
- `test_parser_interface_contract`

## Constraints

- No external API calls during tests.
- Maintain backward compatibility with existing parser endpoints.

## Report

Files changed, test command + result, blockers.
