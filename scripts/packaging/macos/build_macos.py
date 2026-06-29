#!/usr/bin/env python3
"""macOS .app and DMG build script for TaxFlow Pro.

Builds a PyInstaller bundle, wraps it in a .app bundle, and creates a .dmg
for distribution.

Trust signals (B7.03):
  - Baseline: unsigned .dmg, users right-click → Open to bypass Gatekeeper
  - Stage 2: set APPLE_DEVELOPER_ID and APPLE_APP_SPECIFIC_PASSWORD env vars
    to sign and notarize the .app
  - Stage 3: Mac App Store (requires sandboxing — future)

Usage:
    python build_macos.py [--skip-dmg]

Environment variables (all optional):
    APPLE_DEVELOPER_ID         — Developer ID Application certificate name
    APPLE_APP_SPECIFIC_PASSWORD — App-specific password for notarytool
    APPLE_TEAM_ID              — Team ID for stapling
    PYINSTALLER_ARGS           — Extra args passed to PyInstaller
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

APP_NAME = "TaxFlow Pro"
BUNDLE_ID = "com.btsinnovations.taxflowpro"
VERSION = "3.11.6"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BUILD_DIR = PROJECT_ROOT / "dist"
APP_TEMPLATE = PROJECT_ROOT / "scripts/packaging/macos/TaxFlowPro.app.template"


def run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"[macos-build] {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def build_pyinstaller() -> int:
    """Build the PyInstaller one-dir bundle."""
    spec_args = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name", "TaxFlowPro",
        "--windowed",
        "--onedir",
        "--add-data", f"{PROJECT_ROOT}/backend:backend",
        "--add-data", f"{PROJECT_ROOT}/frontend/dist:frontend_dist",
        "--add-data", f"{PROJECT_ROOT}/alembic:alembic",
        "--add-data", f"{PROJECT_ROOT}/alembic.ini:.",
    ]
    extra = os.environ.get("PYINSTALLER_ARGS", "")
    if extra:
        spec_args.extend(extra.split())
    spec_args.append(str(PROJECT_ROOT / "scripts/taxflow_launcher.py"))
    return run(spec_args, cwd=PROJECT_ROOT)


def build_app_bundle() -> Path:
    """Wrap the PyInstaller output in a .app bundle."""
    app_path = BUILD_DIR / f"{APP_NAME}.app"
    if app_path.exists():
        shutil.rmtree(app_path)

    # Copy template
    if APP_TEMPLATE.exists():
        shutil.copytree(APP_TEMPLATE, app_path)
    else:
        app_path.mkdir(parents=True)
        (app_path / "Contents" / "MacOS").mkdir(parents=True, exist_ok=True)
        (app_path / "Contents" / "Resources").mkdir(parents=True, exist_ok=True)

    # Copy PyInstaller output into MacOS
    pyinstaller_out = BUILD_DIR / "TaxFlowPro"
    if pyinstaller_out.exists():
        dest = app_path / "Contents" / "MacOS"
        for item in pyinstaller_out.iterdir():
            dst_item = dest / item.name
            if item.is_dir():
                shutil.copytree(item, dst_item, dirs_exist_ok=True)
            else:
                shutil.copy2(item, dst_item)

    # Write Info.plist
    info_plist = app_path / "Contents" / "Info.plist"
    info_plist.write_text(f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>{APP_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>{BUNDLE_ID}</string>
    <key>CFBundleVersion</key>
    <string>{VERSION}</string>
    <key>CFBundleShortVersionString</key>
    <string>{VERSION}</string>
    <key>CFBundleExecutable</key>
    <string>TaxFlowPro</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>LSMinimumSystemVersion</key>
    <string>11.0</string>
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
""", encoding="utf-8")

    print(f"[macos-build] .app bundle created at {app_path}")
    return app_path


def sign_and_notarize(app_path: Path) -> int:
    """Sign and notarize the .app if Apple credentials are provided."""
    dev_id = os.environ.get("APPLE_DEVELOPER_ID")
    if not dev_id:
        print("[macos-build] APPLE_DEVELOPER_ID not set — skipping signing")
        return 0

    # Codesign
    ret = run([
        "codesign", "--deep", "--force",
        "--sign", dev_id,
        "--options", "runtime",
        str(app_path),
    ])
    if ret != 0:
        print("[macos-build] codesign failed", file=sys.stderr)
        return ret

    # Notarize
    password = os.environ.get("APPLE_APP_SPECIFIC_PASSWORD")
    team_id = os.environ.get("APPLE_TEAM_ID", "")
    if password:
        ret = run([
            "xcrun", "notarytool", "submit",
            str(app_path),
            "--apple-id", dev_id,
            "--password", password,
            "--team-id", team_id,
            "--wait",
        ])
        if ret != 0:
            print("[macos-build] notarization failed", file=sys.stderr)
            return ret

        # Staple
        run(["xcrun", "stapler", "staple", str(app_path)])

    print("[macos-build] signing and notarization complete")
    return 0


def create_dmg(app_path: Path) -> int:
    """Create a .dmg from the .app bundle."""
    dmg_path = BUILD_DIR / f"TaxFlowPro-{VERSION}.dmg"
    if dmg_path.exists():
        dmg_path.unlink()

    # Use hdiutil to create a read-write DMG, copy the app, then convert to compressed
    tmp_dmg = BUILD_DIR / "temp.dmg"
    ret = run([
        "hdiutil", "create", "-srcfolder", str(app_path),
        "-volname", APP_NAME,
        "-fs", "HFS+",
        "-format", "UDZO",
        str(dmg_path),
    ])
    if ret != 0:
        print("[macos-build] DMG creation failed", file=sys.stderr)
        return ret

    if tmp_dmg.exists():
        tmp_dmg.unlink()

    print(f"[macos-build] DMG created at {dmg_path}")
    return 0


def main() -> int:
    print(f"[macos-build] Building {APP_NAME} v{VERSION}")
    print(f"[macos-build] Project root: {PROJECT_ROOT}")

    # Step 1: PyInstaller
    ret = build_pyinstaller()
    if ret != 0:
        return ret

    # Step 2: .app bundle
    app_path = build_app_bundle()

    # Step 3: Sign and notarize (optional)
    ret = sign_and_notarize(app_path)
    if ret != 0:
        return ret

    # Step 4: DMG (unless --skip-dmg)
    if "--skip-dmg" not in sys.argv:
        ret = create_dmg(app_path)
        if ret != 0:
            return ret

    print("[macos-build] Build complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())