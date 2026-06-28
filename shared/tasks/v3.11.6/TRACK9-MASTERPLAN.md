# TaxFlow Pro v3.11.6 — Track 9 Masterplan (B7 Packaging & Platform Hardening)

**Branch:** `v3.11.6-dev-PHASE5-TRACK9-packaging-hardening`  
**Cut from:** `v3.11.6-dev` (HEAD `4822447`)  
**Goal:** Close the v3.11.5 deferred packaging/hardening gaps: single-instance enforcement, macOS `.app`/DMG packaging, and staged trust-signal documentation.

---

## Why Track 9 Exists

B1–B6 delivered the complete bookkeeping backend and frontend shell. v3.11.5 deferred three hardening items:
1. Single-instance enforcement on port 8000
2. macOS `.app` / DMG packaging
3. Staged trust signals for Windows/Linux/macOS

Track 9 resolves these so v3.11.6 can be tagged and packaged cleanly.

---

## Modules & Acceptance Criteria

### B7.01 — Single-Instance Enforcement on Port 8000

**Files to create/update:**
- `backend/local/single_instance.py` (new)
- `scripts/taxflow_launcher.py` (update)
- `backend/tests/test_single_instance.py` (new)

**Requirements:**
- Detect an already-running TaxFlow Pro instance bound to `127.0.0.1:8000`.
- If running, attempt to bring its window to foreground and exit the second instance cleanly.
- If stale/unresponsive, replace it after a short timeout.
- Write a PID/socket lock file in `LOCAL_ROOT` for fast detection.
- Support Windows, Ubuntu, and macOS.

**Acceptance:**
- `test_single_instance.py` passes
- Second launch reuses first instance
- Stale process is replaced
- Lock file cleaned up on exit

---

### B7.02 — macOS `.app` / DMG Packaging

**Files to create/update:**
- `scripts/packaging/macos/build_macos.py`
- `scripts/packaging/macos/TaxFlowPro.app.template/`
- `scripts/packaging/macos/create_dmg.sh`

**Requirements:**
- Build a PyInstaller bundle for macOS.
- Wrap it in a `.app` bundle with Info.plist, icon, and launcher script.
- Create a `.dmg` for distribution.
- Document the Apple Developer / notarization path in the script comments.
- Smoke-test on macOS if a host is available.

**Acceptance:**
- `build_macos.py` runs without errors on macOS
- `.app` launches
- Data directory created in `~/Library/Application Support/TaxFlowPro`
- `/health` returns `production_mode: true`

**Note:** If no macOS host is available locally, deliver the build scripts and note that runtime smoke testing is deferred.

---

### B7.03 — Staged Trust Signals

**Files to create/update:**
- `docs/KNOWN_ISSUES.md`
- `scripts/packaging/windows/build_windows.py`
- `scripts/packaging/linux/build_linux.py`
- `scripts/packaging/macos/build_macos.py`

**Requirements:**
- Document Windows trust path: Microsoft Defender submission (free) + optional OV cert.
- Document Linux trust path: GPG-signed `.deb` + optional PPA/Flatpak.
- Document macOS trust path: Apple Developer + notarization.
- Build scripts accept optional signing env vars without breaking unsigned builds.
- No cert purchase required for v3.11.6 baseline.

**Acceptance:**
- `KNOWN_ISSUES.md` / packaging README documents all three trust paths
- Build scripts don't fail when signing env vars are absent
- Existing Windows and Linux builds still pass

---

## Technical Notes

- Keep single-instance logic platform-aware but cross-platform where possible.
- Use `psutil` or socket probing for process detection; avoid heavy dependencies.
- Window-foreground logic is platform-specific:
  - Windows: `ctypes.windll.user32.SetForegroundWindow` / `AllowSetForegroundWindow`
  - Ubuntu: `wmctrl` or D-Bus
  - macOS: AppleScript or `NSApplication`
- For lock files, prefer a socket bound to `127.0.0.1:0` with a stored port file, or a PID file in `LOCAL_ROOT`.
- Do not change the default server port (8000) unless required.
- Trust-signal docs should reference Josh's prior directive that public trust signals are deferred; friends/family distribution does not need certs.

---

## Definition of Done

- B7.01 implemented and tested
- B7.02 build scripts delivered (runtime smoke test if macOS host available)
- B7.03 trust-signal documentation updated
- `backend/tests` regression still passes (SQLite)
- Frontend build still passes
- Branch pushed to origin
- No merge to `v3.11.6-dev` without James approval

---

## Suggested Execution Order

1. B7.01 single-instance enforcement (highest user value + easiest to verify)
2. B7.03 staged trust signals (docs + build script env var support)
3. B7.02 macOS packaging (depends on macOS host availability)

---

## Assignment

- **Primary builder:** Jane Clawd
- **Validator:** glm-5.2:cloud for final review
- **Orchestrator approval:** James before merge
