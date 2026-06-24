# Frontend Smoke Test — TaxFlow Pro v3.9.1

**Status:** Auth context and API hooks are updated for the Stage 2 hybrid local-auth model.
A runtime end-to-end smoke test is not automated because the repo has no Jest/Playwright setup
and the backend must be running. This document records the manual checklist used to verify
behavior.

## Prerequisites
1. Backend dependencies installed: `pip install -r requirements.txt -r requirements-dev.txt`.
2. Backend running on `http://localhost:8000` (or the configured `VITE_API_BASE_URL`).
3. A fresh database so `/api/auth/status` returns `{"first_boot": true}`.
4. Browser dev tools open to the Network tab.

## Checklist

### 1. First boot flow
- [ ] Open the frontend in a browser.
- [ ] `AuthContext` calls `GET /api/auth/status` on mount.
- [ ] If `first_boot` is `true`, the `LoginModal` renders the **boot** prompt (single password field, no username).
- [ ] Enter a master password and confirm.
- [ ] UI calls `POST /api/auth/boot` with body `{ "password": "..." }`.
- [ ] Response contains `access_token`; token is stored in `localStorage` under `token`.
- [ ] UI then calls `GET /api/auth/me` with `Authorization: Bearer <token>` and displays the derived local username.

### 2. Subsequent login flow
- [ ] Clear `localStorage` token or reload with an already-initialized backend (`first_boot: false`).
- [ ] UI shows the login form (password field).
- [ ] Enter any username (ignored by local auth) and the master password.
- [ ] UI calls `POST /api/auth/login-json` with body `{ "username": "...", "password": "..." }`.
- [ ] Response contains `access_token`; token is stored in `localStorage`.

### 3. Authenticated protected request
- [ ] Navigate to a section that fetches clients/accounts.
- [ ] Confirm the request includes `Authorization: Bearer <token>`.
- [ ] `GET /api/clients/` returns HTTP 200 with the client list.
- [ ] Remove the token from `localStorage` and refresh.
- [ ] `GET /api/clients/` returns HTTP 401.

### 4. Logout flow
- [ ] Click logout.
- [ ] UI calls `POST /api/auth/logout` with the bearer token.
- [ ] Token is removed from `localStorage`.
- [ ] UI returns to the login modal.

## Notes
- The existing `useAPI.ts` already sends the bearer token via `fetchWithAuth` and the auth helpers.
- `AuthContext.tsx` already handles first-boot detection and stores the token correctly.
- No new frontend test framework was introduced; adding Playwright would require `npm install -D @playwright/test`
  and a running backend, which is outside the bounded Stage 3 backend scope.
- This checklist is the path taken for the smoke-test requirement.

## OCR (P1.2)

- The **Use OCR** switch in `UploadSection.tsx` sends `force_ocr=true` with PDF uploads.
- OCR is optional and off by default. It requires:
  - Tesseract OCR binary (`tesseract` on PATH)
  - Poppler (`pdftoppm` on PATH)
  - Python deps: `pytesseract`, `pdf2image`, `Pillow`
- Enable it only when uploading scanned/image-based PDF pages. Digital/text PDFs should leave OCR off for faster, more accurate extraction.
