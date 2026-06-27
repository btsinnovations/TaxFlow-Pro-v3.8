# TaxFlow Pro v3.11.5 — Platform Installers

This directory contains the cross-platform installer build system for
TaxFlow Pro v3.11.5. It produces:

- Windows: `TaxFlowPro-3.11.5-Setup.exe` (Inno Setup or NSIS)
- Linux: `TaxFlowPro-3.11.5-linux.tar.gz` (portable tarball)
- macOS: `TaxFlowPro.app` + `TaxFlowPro-3.11.5.dmg` (deferred; see Known Issues)

## Status

v3.11.5 build is functional on Windows and Linux hosts. macOS bundling is
blocked on host availability and Apple Developer/code-signing decisions.

## Files

| File | Purpose |
|------|---------|
| `build_all.py` | Entry point. Detects host OS, runs the right sub-build, and copies artifacts to `dist/installers/`. |
| `shared.py` | Shared constants: version, data dirs, file globs, helper utilities. |
| `launcher_adapter.py` | Shim used by PyInstaller to import `scripts/taxflow_launcher.py` from the repo root. |
| `windows/build_windows.py` | PyInstaller + NSIS/Inno Setup wrapper for Windows. |
| `windows/installer.nsi` | NSIS installer script template. |
| `windows/installer.iss` | Inno Setup installer script template. |
| `linux/build_linux.py` | Tarball builder. |
| `linux/AppRun` | AppImage entry script. |
| `assets/icon.svg` | Source icon. |
| `smoke_test.py` | Automated smoke test against a running packaged app. |
| `smoke_ci.py` | Lightweight CI smoke test for production-mode behavior. |
| `BUILD.md` | Full build / reproducibility instructions. |

## Quick Start

From the project root:

```bash
cd scripts/packaging
python build_all.py
```

Artifacts land in `dist/installers/`.

## Windows Build

```bash
cd scripts/packaging
python windows/build_windows.py
```

Requires:
- Python 3.10+, PyInstaller
- `makensis` (NSIS) or `iscc` (Inno Setup)
- Frontend built (`npm run build`)

## Linux Build

```bash
cd scripts/packaging
python linux/build_linux.py
```

Produces a portable `.tar.gz`. AppImage is optional and requires `appimagetool`.

## macOS Build

```bash
cd scripts/packaging
python macos/build_macos.py
```

**Deferred.** macOS bundling requires a macOS host and Apple Developer/code-signing
decisions. See `docs/KNOWN_ISSUES.md` Section 6.

## CI Smoke Test

```bash
python scripts/packaging/smoke_ci.py
```

Builds the frontend, starts the app in production mode, and confirms:
- `/api/tests/` returns 404
- `/api/health` reports `production_mode: true`

## Packaging Smoke Test

After installing or extracting a package:

```bash
python scripts/packaging/smoke_test.py
```

## Constraints

- User data lives **outside** the install directory.
- Installer must work **offline** after download.
- No paid signing / notarization without explicit James/Josh approval.
- All paths are computed at runtime per platform.
- Windows and Linux builds are tested in CI; macOS is deferred.
