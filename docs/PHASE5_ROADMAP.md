# TaxFlow Pro Phase 5 Roadmap — Advanced Intelligence & Scale

**Status:** Rough draft — future features, not approved for development  
**Audience:** Long-term product planning  
**Goal:** Define advanced features for a mature local-first accounting platform.

---

## 1. AI-Assisted Anomaly Detection

### 1.1 Local Anomaly Scoring
- Use locally trained model or statistical heuristics
- Flag transactions that deviate from client history
- Examples: duplicate vendors, unusual amounts, off-hours activity

### 1.2 Pattern-Based Alerts
- Detect missing recurring transactions
- Warn on category drift
- Surface transactions needing manual review

### 1.3 Confidence-Driven Review Queue
- Rank transactions by anomaly score
- Preparer sees highest-risk items first

---

## 2. Forecasting Engine

### 2.1 Recurring Pattern Detection
- Identify repeating transactions (rent, subscriptions, payroll)
- Confidence score per detected pattern

### 2.2 Cash Flow Projection
- 30/60/90-day cash forecast per client
- Based on historical inflows/outflows and recurring items

### 2.3 Budget vs. Actual
- Simple budget input per category
- Variance reporting with alerts

---

## 3. Multi-Currency Support

### 3.1 Foreign Transaction Handling
- Store original currency + amount
- Local exchange rate cache with manual override

### 3.2 FX Gain/Loss Calculation
- Realized/unrealized FX impact on transfers
- Report in functional currency

### 3.3 Currency-Agnostic Export
- Export in original or converted amounts

---

## 4. Subscription & Recurring Revenue Tracking

### 4.1 Recurring Revenue Recognition
- For clients with subscription businesses
- Monthly recognized revenue schedule

### 4.2 Customer Lifetime Value Estimation
- Simple cohort-based LTV from recurring payment data

### 4.3 Churn Signal Detection
- Flag customers who stopped paying

---

## 5. Mobile Companion App

### 5.1 Receipt Capture
- Camera → local OCR
- Link receipt to existing or new transaction

### 5.2 Transaction Review
- Approve/categorize/reject transactions on mobile
- Syncs to local desktop app on same LAN

### 5.3 Mileage / Expense Entry
- Manual mileage log
- Business/personal split

---

## 6. Open Banking Alternative

### 6.1 OFX Direct Connect
- Download statements directly from bank via OFX (where supported)
- No third-party aggregator

### 6.2 Statement Auto-Fetch Scheduler
- Periodic OFX polling locally
- Encrypted credential storage

### 6.3 QFX Import Improvements
- Better handling of investment accounts (optional)

---

## 7. Plugin / Extension System

### 7.1 Local Plugin API
- Register custom parsers, categorizers, exporters
- Hot-load plugins from `plugins/` directory

### 7.2 Third-Party Local Plugins
- Signed plugin packages
- Sandboxed execution

### 7.3 Marketplace Foundation
- Discovery/install UI shell
- Plugin compatibility check

---

## 8. White-Label & Firm Deployment

### 8.1 Custom Branding
- Firm logo, colors, report templates
- Per-firm default chart of accounts

### 8.2 Batch Client Operations
- Bulk import/export across all clients
- Firm-level analytics dashboard

### 8.3 Deployment Tooling
- Silent installer for firm-wide rollout
- Configuration preset files

---

## 9. Desktop Wrapper / Native App

### 9.1 Electron or Tauri Shell
- System tray icon
- Auto-start with OS
- Window management

### 9.2 OS-Level Integration
- File associations for statement PDFs
- "Open with TaxFlow" context menu

### 9.3 Native Notifications
- Import complete, backup reminder, due date alerts

---

## 10. Long-Term Architecture Ideas

- CRDT-based local sync between devices
- Optional encrypted backup to user-owned object storage
- Offline-first PWA mode

---

*Rough draft for discussion only — no implementation approved.*
