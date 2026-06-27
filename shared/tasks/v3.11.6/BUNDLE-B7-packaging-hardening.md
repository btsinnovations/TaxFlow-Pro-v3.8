# Bundle B7 — Packaging & Platform Hardening

**Goal:** Close the v3.11.5 deferred hardening gaps and extend platform support to macOS.

---

## 3.11.6.B7.01 — Single-Instance Enforcement on Port 8000

### Files
- `scripts/taxflow_launcher.py`
- `backend/local/single_instance.py` (new)
- `backend/tests/test_single_instance.py`

### Requirements
- Before starting the server, check if another `TaxFlowPro` process is already bound to `127.0.0.1:8000`.
- If bound, bring existing window to foreground and exit cleanly.
- If stale/unresponsive, optionally kill and replace after a short timeout.
- Write a PID/socket lock file in `LOCAL_ROOT` for fast detection.
- Works on Windows, Ubuntu, and macOS.

### Tests
- Launch second instance → first window reused, second exits.
- Kill stale process → new instance starts.
- Lock file cleanup on clean exit.

---

## 3.11.6.B7.02 — macOS `.app` / DMG Packaging

### Files
- `scripts/packaging/macos/build_macos.py`
- `scripts/packaging/macos/TaxFlowPro.app.template/`
- `scripts/packaging/macos/create_dmg.sh`

### Requirements
- Build PyInstaller bundle for macOS.
- Wrap in `.app` bundle with Info.plist, icon, and launcher script.
- Create `.dmg` for distribution.
- Gatekeeper: document Apple Developer / notarization path (B7.03).
- Smoke-test on macOS host: clean install → BootGate → server healthy.

### Tests
- `.app` launches.
- Data directory created in `~/Library/Application Support/TaxFlowPro`.
- `/health` returns `production_mode: true`.

---

## 3.11.6.B7.03 — Staged Trust Signals

### Files
- `docs/KNOWN_ISSUES.md` updated
- `scripts/packaging/windows/build_windows.py`
- `scripts/packaging/linux/build_linux.py`
- `scripts/packaging/macos/build_macos.py`

### Requirements
- Document Windows trust path: Microsoft Defender submission (free) + optional OV cert.
- Document Linux trust path: GPG-signed `.deb` + optional PPA/Flatpak.
- Document macOS trust path: Apple Developer + notarization.
- If certs/keys are provided, wire signing into build scripts.
- No cert purchase decisions required for v3.11.6 baseline.

### Tests
- Documented steps are executable.
- Build scripts accept optional signing env vars without breaking unsigned builds.
