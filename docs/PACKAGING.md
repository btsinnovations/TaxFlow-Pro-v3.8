# TaxFlow Pro v3.10 Packaging Guide

## Supported targets

| Platform | Script | Output |
|---|---|---|
| Windows | `scripts/build_windows.py` | `dist/TaxFlowPro/` + `dist/installer/TaxFlowPro-3.10.0-Setup.exe` |
| Linux tarball | `scripts/build_linux.py` | `dist/linux/TaxFlowPro-3.10.0-linux.tar.gz` + `dist/linux/AppDir/` |
| Linux AppImage | `appimagetool dist/linux/AppDir` | `TaxFlowPro-3.10.0-x86_64.AppImage` |
| Linux .deb | `scripts/build_deb.py` | `dist/deb/taxflow-pro_3.10.0_amd64.deb` |
| macOS | `scripts/build_macos.py` | `dist/macos/TaxFlowPro.app/` + `dist/macos/TaxFlowPro-3.10.0.dmg` |

## Windows

```powershell
python scripts/build_windows.py
```

Requires:
- Node.js / npm
- Python 3.12+
- PyInstaller (`pip install pyinstaller`)
- Inno Setup 6 (`ISCC.exe` on PATH)

## Linux (Ubuntu/Debian)

### One-command install (.deb)

```bash
# On Ubuntu machine
sudo apt install -y dpkg-dev
python3 scripts/build_deb.py
sudo dpkg -i dist/deb/taxflow-pro_3.10.0_amd64.deb
# If dependency errors occur, run:
sudo apt --fix-broken install -y

# Launch from anywhere
taxflow-pro
```

### Portable tarball

```bash
python3 scripts/build_linux.py
tar -xzf dist/linux/TaxFlowPro-3.10.0-linux.tar.gz -C dist/linux
cd dist/linux/TaxFlowPro
./setup_linux.sh   # installs tesseract-ocr, poppler-utils, python deps
./TaxFlowPro.sh
```

### AppImage

```bash
python3 scripts/build_linux.py
wget https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage
chmod +x appimagetool
./appimagetool dist/linux/AppDir dist/linux/TaxFlowPro-3.10.0-x86_64.AppImage
chmod +x dist/linux/TaxFlowPro-3.10.0-x86_64.AppImage
./dist/linux/TaxFlowPro-3.10.0-x86_64.AppImage
```

## macOS

```bash
python3 scripts/build_macos.py
```

Requires macOS host. Creates `.app` and `.dmg`.

## Cross-platform notes

- User data lives outside the install directory (local data dir resolution in `scripts/taxflow_launcher.py`).
- Linux/macOS fall back to system `tesseract` and `pdftotext` if vendored Windows binaries are absent.
- No cloud calls; default mode remains offline-first.
