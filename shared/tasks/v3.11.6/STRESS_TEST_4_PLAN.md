# TaxFlow Pro v3.11.6 — Stress Test 4 Plan
## Destructive Boundaries & Extreme Edge Cases

**Date:** 2026-07-01  
**Source:** btsinnovations / CPA team request  
**Branch:** `v3.11.6-dev`  
**Target:** TaxFlow Pro v3.11.6  

---

## Objective
Prove TaxFlow Pro v3.11.6 survives hostility, edge-case catastrophes, and extreme concurrency — after Stress Tests 1–3 proved it handles scale and volume.

## Hardware Constraints
- **No Docker.** All tests run natively on Windows 10.
- **Limited disk space.** No massive log generation. No saving mutated files to disk — generate in-memory.
- **Steady CPU/Memory.** Concurrency limits respected to prevent host lockups.

---

## Phase 1: Concurrency Integrity

### 1.1 Double-Spend / Race Condition Test
- **Action:** 50 concurrent API requests post transactions debiting/crediting the same ledger account at the same millisecond.
- **Success:** Ledger balances (SUM(debits)==SUM(credits)); exactly one succeeds; rest return 409/423; zero silent overwrites.

### 1.2 Audit Trail Immutability Under Load
- **Action:** 20 users create/edit/delete transactions while a script hammers `GET /api/audit/logs` and attempts DELETE/PUT on audit records.
- **Success:** Audit logs strictly append-only; all alteration attempts return 405/403.

### 1.3 Multi-Tenant RLS Bleed Under High Concurrency
- **Action:** 100 concurrent users from 10 tenants query the same heavy tables at the same millisecond.
- **Success:** No cross-tenant reads; RLS holds under connection-pool thrashing.

---

## Phase 2: Environmental Hostility & Chaos Engineering

### 2.1 Mid-Transaction DB/Network Drop
- **Action:** Start 5,000-transaction batch import; at 50%, kill PostgreSQL or unmap SQLite network drive.
- **Success:** App catches broken pipe; transaction rolls back; UI shows "Connection Lost" state.

### 2.2 Windows File Lock Contention (Antivirus Simulation)
- **Action:** Place exclusive read-lock on SQLite file for 5 seconds while app writes.
- **Success:** App queues/retry or fails gracefully; no unhandled `sqlite3.OperationalError: database is locked` crash.

### 2.3 Network Latency & Packet Loss Injection
- **Action:** Local proxy injects 500ms delay + 5% packet loss into localhost traffic.
- **Success:** Frontend shows loading states, doesn't freeze; backend doesn't exhaust thread pool.

---

## Phase 3: Frontend DOM, Memory, & UI Edge Cases

### 3.1 Massive DOM Rendering
- **Action:** Load General Ledger report with 10,000+ rows without pagination.
- **Success:** Browser tab doesn't crash; smooth rendering if virtualized.

### 3.2 State Thrashing / Memory Leaks
- **Action:** Open/close 50 complex modals in rapid succession, 100 times; monitor JS heap.
- **Success:** Heap usage plateaus; no linear growth from uncleared intervals/listeners.

### 3.3 Localization & Layout Breaking
- **Action:** Switch to RTL language; input German compound words and CJK characters; generate PDF.
- **Success:** Grid doesn't break; PDF doesn't truncate text or crash on font embedding.

---

## Phase 4: Deep Domain, Time, & Compute Boundaries

### 4.1 DST & Timezone Hopping
- **Action:** Transactions dated on Spring Forward / Fall Back nights across timezones.
- **Success:** Timestamps correct; no vanishing/duplicating; period-close boundaries align.

### 4.2 Fiscal Year Boundary Smashing
- **Action:** Post/close periods at 2026-12-31 23:59:59.999 and 2027-01-01 00:00:00.000.
- **Success:** Strict fiscal-year separation; zero balance leakage.

### 4.3 Heavy Compute & Report Generation Queueing
- **Action:** Trigger 20 complex PDF reports across 5 users simultaneously.
- **Success:** Queue/controlled thread pool; no OOM; temp files cleaned immediately.

---

## Phase 5: Security, Abuse, & Integration Failures

### 5.1 Rate Limiting Under DDoS
- **Action:** 500 concurrent connections brute-forcing `/api/auth/login`.
- **Success:** Rate limiter returns 429 without DB degradation or blocking legitimate IPs.

### 5.2 JWT Thrashing & Revocation
- **Action:** Fire 1,000 valid JWTs; revoke user session halfway.
- **Success:** Backend immediately rejects remaining tokens; no grace-period caching.

### 5.3 Webhook / Integration Callback Storm
- **Action:** Mock server sleeps 30s or returns 500s; trigger 100 outbound webhooks.
- **Success:** Circuit breaker trips; requests stop after threshold; logs failure; doesn't block main thread.

---

## Phase 6: Data Lifecycle & Migration Stress

### 6.1 Pagination & Cursor Exhaustion
- **Action:** Query transaction list up to page 10,000 or past-end cursor on 5M-row table.
- **Success:** No full table scan; returns empty/404 in <50ms without CPU spike.

### 6.2 Schema Migration Under Load
- **Action:** 100K transactions; run v3.11.6 migrations while background reads/writes occur.
- **Success:** Migration completes without unacceptable table locks; active reads/writes queue or fail gracefully.

---

## Phase 7: Real-World Document Ingestion & Parser Edge Cases

### 7.1 Layout Drift & Format Mutation (Silent Drop Test)
- **Action:** Mutate a known-good PDF in-memory (shift columns, change fonts, whitespace); feed 20 variations.
- **Success:** Parser adapts OR cleanly fails with manual-review flag. **Zero silent data corruption.**

### 7.2 PDF Quality & OCR Degradation (Bad Scan Test)
- **Action:** Degrade clean PDF to 150 DPI + noise + blur; feed OCR pipeline.
- **Success:** OCR doesn't crash; low confidence flagged as "Manual Review Required"; no silent guesses.

### 7.3 Multi-Account & Multi-Page Stitching (Frankenstein Test)
- **Action:** In-memory 12-page PDF: marketing header (2), checking (5), T&Cs (1), savings (4).
- **Success:** Parser splits accounts correctly; ignores junk; no transaction leakage.

### 7.4 Unregistered Institution & Generic Fallback (Neobank Test)
- **Action:** Scrub metadata, rename to "NeoBank X", alter routing; feed engine.
- **Success:** Routes to generic fallback parser; extracts with warning OR cleanly rejects with manual mapping prompt. No 500s.

---

## Governance & Constraints

- **Resource monitoring:** Keep Windows Resource Monitor open. Abort if RAM >85% or CPU pinned at 100% for >2 min.
- **Zero disk footprint for Phase 7:** Use `io.BytesIO()` and stream payloads. Do not write mutated PDFs to disk.
- **Sequential OCR:** Phase 7 tests run one at a time (or max concurrency 2).
- **No production code changes on failure:** Log, revert environment, and report to Josh for architectural review.
- **No commits/pushes:** All chaos scripts remain local.
- **Subagent restriction:** No autonomous subagents for Phase 2 (Chaos) or Phase 7 (Parser Edge Cases). Must run via direct CLI scripts in main session.

---

## Status
- [ ] Initial risk review and environment baseline
- [ ] Phase 1 — Concurrency Integrity
- [ ] Phase 2 — Environmental Hostility
- [ ] Phase 3 — Frontend Edge Cases
- [ ] Phase 4 — Domain / Time / Compute Boundaries
- [ ] Phase 5 — Security / Abuse / Integrations
- [ ] Phase 6 — Data Lifecycle / Migration
- [ ] Phase 7 — Document Ingestion & Parser Edge Cases
- [ ] Final report and verdict
