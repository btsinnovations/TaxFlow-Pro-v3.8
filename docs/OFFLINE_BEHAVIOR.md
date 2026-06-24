# TaxFlow Pro — Offline Behavior & Feature Matrix

**Scope:** `backend/`, `frontend/`, `scripts/`  
**Runtime mode:** Default is `offline` (`TAXFLOW_RUNTIME_MODE=offline`).  
**Last updated:** 2026-06-23

---

## 1. Local-first promise

TaxFlow Pro v3.9 is designed to run entirely on the user's machine. No bank credentials, transaction data, documents, or ML training data leave the device in default configuration.

All core features — PDF parsing, OCR, categorization, encryption, backup/restore, reporting, and model training — execute locally using installed Python packages and optional local binaries (Tesseract, Poppler, PostgreSQL).

---

## 2. Feature availability matrix

| Feature | Default offline mode | `TAXFLOW_RUNTIME_MODE=online` | Notes |
|---|---|---|---|
| **PDF upload & parsing** | ✅ Available | ✅ Available | Uses local `pdfplumber` / `PyPDF2` + optional local OCR. |
| **Transaction categorization (rule)** | ✅ Available | ✅ Available | Rule-based via `categories.yaml`. |
| **Transaction categorization (ML)** | ✅ Available | ✅ Available | Local scikit-learn model trained on user's own labeled data. |
| **Bank statement reconciliation** | ✅ Available | ✅ Available | Manual upload + running-balance checks. |
| **General ledger & journal entries** | ✅ Available | ✅ Available | |
| **Depreciation schedules** | ✅ Available | ✅ Available | |
| **Flag / note system** | ✅ Available | ✅ Available | |
| **Export (CSV, QIF, Excel, JSON)** | ✅ Available | ✅ Available | |
| **Signed exports / audit trail** | ✅ Available | ✅ Available | HMAC signed with local secret. |
| **Local backup / restore** | ✅ Available | ✅ Available | Encrypted snapshots controlled by user. |
| **SQLCipher encrypted DB** | ✅ Available | ✅ Available | Opt-in via `DATABASE_URL` or config. |
| **Local user auth** | ✅ Available | ✅ Available | Master password + optional keyfile. |
| **Bootstrap / self-test** | ✅ Available | ✅ Available | `/api/health/bootstrap` checks local deps. |
| **Plaid / live bank feeds** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["plaid"] = True` + valid credentials | No credentials ship with app. |
| **Stripe / billing** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["stripe"] = True` | |
| **SMTP email** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["smtp_email"] = True` | |
| **OAuth login** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["oauth_login"] = True` | Local JWT is default. |
| **Telemetry / analytics** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["telemetry"] = True` | Never enabled by default. |
| **Auto update check** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["auto_update_check"] = True` | |
| **Cloud ML inference** | ❌ Disabled | ⚠️ Requires `FEATURE_FLAGS["cloud_ml"] = True` | Local ML is default. |
| **External fonts (Google Fonts)** | ⚠️ Loaded in dev/web build | ⚠️ Loaded in dev/web build | No data flows through it; vendor for offline installer. |

---

## 3. Cloud-gated features

All cloud or network-dependent features are controlled by `FEATURE_FLAGS` in `backend/local/settings.py`:

```python
FEATURE_FLAGS = {
    "plaid": False,
    "stripe": False,
    "smtp_email": False,
    "oauth_login": False,
    "telemetry": False,
    "auto_update_check": False,
    "cloud_ml": False,
}
```

To enable a feature, set the corresponding env var and change `FEATURE_FLAGS` at runtime (not recommended unless you are self-hosting and understand the data flow):

```bash
# Example: opt-in to SMTP only
export TAXFLOW_RUNTIME_MODE=online
export TAXFLOW_FEATURE_SMTP_EMAIL=true
```

Any code path that calls `guard_cloud_call("plaid")` or `guard_feature("stripe")` will raise `RuntimeError` if the feature is disabled or the runtime is offline.

---

## 4. External assets

### Google Fonts

The development / web build loads fonts from:
- `https://fonts.googleapis.com`
- `https://fonts.gstatic.com`

**Impact:** UI-only. No transaction data, credentials, or files are sent.

**Offline-installer path:** Vendor the required font files into `frontend/public/fonts/`, update `frontend/index.html` to reference the local copies, and remove the Google Fonts `<link>` tags.

---

## 5. User-facing messaging guidance

When a feature is unavailable due to offline mode, the application must tell the user clearly and actionably:

| Scenario | Message |
|---|---|
| User tries to enable Plaid / bank feed | "Bank feeds are disabled in offline mode. To connect accounts, switch to online mode and configure Plaid credentials." |
| User tries to send email report | "Email sending is disabled in offline mode. Export the report to a file instead." |
| User tries OAuth login | "OAuth login is disabled. Use your local master password." |
| Local ML model not trained | "No trained model found. Upload and label at least 10 transactions, then click Train Model." |
| OCR binary missing | "OCR is not available. Install Tesseract and Poppler to scan image-based PDFs." |

All messages should avoid blaming the user. Provide the local alternative when one exists.

---

## 6. Dev vs production defaults

| Setting | Development | Production | Why |
|---|---|---|---|
| `TAXFLOW_RUNTIME_MODE` | `offline` | `offline` | Safe default. |
| `TAXFLOW_ENVIRONMENT` | `development` | `production` | Controls log verbosity. |
| `TAXFLOW_LOCAL_ROOT` | `.` | User data dir (e.g., `%LOCALAPPDATA%\TaxFlow`) | Keeps user data outside install dir. |
| `SQLCIPHER_PASSWORD` | Prompt at first run | Prompt at first run | Never hardcode. |
| `FEATURE_FLAGS` | All `False` | All `False` | No cloud leaks by default. |

---

## 7. Data-flow summary

- **Never leaves device:** PDFs, transactions, credentials, model weights, backups.
- **Only local network:** Frontend ↔ backend on `127.0.0.1:8000` (default).
- **Optional outbound only when explicitly enabled:** Plaid, Stripe, SMTP, OAuth, telemetry, update checks, cloud ML.
- **UI-only external request:** Google Fonts in web/dev build.

---

## 8. Verification

The following should hold in any default-offline test run:

- `is_offline()` returns `True`.
- `guard_cloud_call("plaid")` raises `RuntimeError`.
- `feature_enabled("stripe")` is `False`.
- `/api/health/bootstrap` reports ready without making outbound calls.
- Model training endpoint (`POST /api/ml/train`) succeeds without external APIs.
- PDF upload, export, and backup all succeed without network.

See `backend/tests/test_local_first.py` and `backend/tests/test_bootstrap.py` for the test implementation.
