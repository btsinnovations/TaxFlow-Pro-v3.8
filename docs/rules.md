# TaxFlow Pro v3.9 — Categorization Rules

## Overview

The categorization rules engine automatically labels incoming transactions by matching their description against rule patterns. Each rule maps a matching pattern to a category and an optional general-ledger (GL) account. Rules are tenant-scoped and sorted by priority so the most specific rule wins.

## Rule model

A `CategorizationRule` contains:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Primary key |
| `tenant_id` | int | FK to `clients.id`; every rule belongs to a tenant |
| `name` | str | Human-readable category name (e.g. "Office Supplies") |
| `pattern` | str | Substring to match in transaction description |
| `gl_account_id` | int? | Optional FK to `gl_accounts.id` |
| `priority` | int | Higher number wins when multiple rules match |
| `enabled` | bool | Disabled rules are skipped |

## Matching logic

`backend/services/rules.py::apply_rules(transactions, rules)` performs the following for each transaction:

1. Filter to enabled rules whose `pattern` appears as a substring in `transaction.description` (case-insensitive).
2. Sort matching rules by `priority DESC`.
3. Assign the transaction the winning rule's `name` as its `category` and the rule's `gl_account_id` as its `gl_account_id`.
4. If no rule matches, `category` stays `"uncategorized"` and `gl_account_id` stays `None`.

## Integration

`backend/routers/upload.py` calls `apply_rules()` automatically after new transactions are created from a parsed statement. Rules are fetched fresh from the database for each upload, so edits take effect immediately.

## API

- `POST /api/rules/?tenant_id={id}` — create a rule
- `GET /api/rules/?tenant_id={id}` — list rules for a tenant
- `GET /api/rules/{id}?tenant_id={id}` — get one rule
- `PUT /api/rules/{id}?tenant_id={id}` — update a rule
- `DELETE /api/rules/{id}?tenant_id={id}` — delete a rule

## Best practices

- Use high-priority rules for specific merchants (e.g. "STARBUCKS") and low-priority rules for broad terms (e.g. "RESTAURANT").
- Keep descriptions lowercase/uppercase-agnostic — the engine normalizes case.
- Re-run a statement upload after editing rules to recategorize imported transactions.
