# TaxFlow Pro v3.10 — Platform Packaging Build Guide

## Prerequisites

### All platforms

- Python 3.10+ with `pip`
- `pip install pyinstaller`
- Node.js 18+ and `npm` (for frontend build)
- TaxFlow Pro project dependencies:
  ```bash
  pip install -r requirements.txt
  ```
- Vendored binaries provided by Bundles B+C:
  - `vendored/tesseract/tesseract` (+ `tessdata/`)
  - `vendored/poppler/pdftotext`, `pdfimages`, DLLs

### Windows

- One of:
  - NSIS (`makensis` on PATH) — preferred
  - Inno Setup (`iscc` on PATH) — fallback
- Optional: 7-Zip for archive helpers

### macOS

- Xcode Command Line Tools (for `iconutil`, `codesign`)
- `create-dmg` for DMG generation (optional)

### Linux

- `appimagetool` for AppImage generation (optional)

## Reproducible Build Steps

### 1. Build frontend

```bash
cd frontend
npm ci
npm run build
```

Confirm `frontend/dist/index.html` exists.

### 2. Bundle backend with PyInstaller

From the project root:

```bash
cd scripts/packaging
python build_all.py
```

This detects the host OS, copies `taxflow_launcher.py` from Bundles B+C (or
the scaffold if unavailable), and produces a platform-specific installer in
`dist/installers/`.

### 3. Platform-specific commands

Only run the target builder if cross-compiling from a matching host:

```bash
# Windows
python windows/build_windows.py

# macOS
python macos/build_macos.py

# Linux
python linux/build_linux.py
```

### 4. Force build during development

If vendored binaries are still missing from Bundles B+C, you can build a
partial bundle for testing:

```bash
python build_all.py --force
```

The resulting bundle will run but OCR/PDF features may fail until the binaries
are added.

## Output Layout

```
dist/
├── pyinstaller/
│   ├── TaxFlowPro/             # Windows/Linux onedir bundle
│   └── TaxFlowPro.app/         # macOS bundle
└── installers/
    ├── TaxFlowPro-3.10.0-Setup.exe
    ├── TaxFlowPro-3.10.0.dmg
    └── TaxFlowPro-3.10.0-linux.tar.gz
```

## User Data Directories

| Platform | Path |
|----------|------|
| Windows | `%LOCALAPPDATA%\TaxFlowPro` |
| macOS | `~/Library/Application Support/TaxFlowPro` |
| Linux | `~/.local/share/TaxFlowPro` |

Subdirectories: `db`, `backups`, `uploads`, `ml`, `logs`.

## Silent / Uninstall

### Windows (NSIS)

```cmd
TaxFlowPro-3.10.0-Setup.exe /S
"%LOCALAPPDATA%\TaxFlowPro\uninst.exe" /S
```

### macOS

Drag `TaxFlowPro.app` to Trash. User data remains in `~/Library/Application Support/TaxFlowPro`.

### Linux

Delete the extracted directory. User data remains in `~/.local/share/TaxFlowPro`.

## Signing

### macOS

Unsigned by default. To sign, export your Developer ID:

```bash
export CODE_SIGN_IDENTITY="Developer ID Application: Your Name"
python macos/build_macos.py
```

Notarization is intentionally not automated because it requires Apple-paid
certificates and credentials.

### Windows

Neither NSIS nor Inno Setup scripts apply code signing by default. To sign
the resulting `.exe`, use `signtool` as a post-build step:

```cmd
signtool sign /a /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 dist\installers\TaxFlowPro-3.10.0-Setup.exe
```

## Smoke Test

After installing or extracting:

```bash
python scripts/packaging/smoke_test.py
```

Automated checks:
1. Launch app / wait for server health.
2. Upload `fixtures/sample_statement.pdf`.
3. Categorize a transaction.
4. Export transactions CSV.
5. Run backup and restore.

Manual smoke test is also documented in `docs/frontend-smoke-test.md`.

## Known Limitations

- The scaffold launcher (`taxflow_launcher_scaffold.py`) is used only when
  `scripts/taxflow_launcher.py` is missing. It should be replaced by the real
  launcher from Bundles B+C before release.
- macOS bundle is unsigned unless `CODE_SIGN_IDENTITY` is set.
- AppImage requires `appimagetool` and only builds on Linux.
- Windows installer wrapper requires NSIS or Inno Setup to be installed.
