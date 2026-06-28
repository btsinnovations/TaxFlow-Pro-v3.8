# Known Issues & Trust Signals — TaxFlow Pro v3.11.6

## Platform Trust Signals

TaxFlow Pro is a local-first desktop application. For friends/family distribution,
no code-signing certificates are required. The following staged trust paths are
documented for future expansion.

### Windows

1. **Baseline (free):** Submit the unsigned `.exe` to Microsoft Defender for
   analysis via the [Microsoft Security Intelligence submission
   portal](https://www.microsoft.com/en-us/wdsi/filesubmission). After analysis,
   Defender stops flagging the binary on machines with SmartScreen disabled or
   after the user clicks "Run anyway."

2. **Stage 2 (optional):** Purchase an OV (Organization Validation) code-signing
   certificate (~$200/year). Sign the `.exe` with `signtool`. This removes
   SmartScreen warnings after a short reputation-building period.

3. **Stage 3 (future):** EV (Extended Validation) certificate for immediate
   SmartScreen trust without reputation building.

**Build script:** `scripts/packaging/windows/build_windows.py`
- Accepts `TAXFLOW_SIGNING_CERT` and `TAXFLOW_SIGNING_PASSWORD` env vars
- If absent, produces an unsigned build (no failure)

### Linux

1. **Baseline (free):** Distribute a `.deb` package with GPG signing using a
   self-generated key. Users install with `dpkg -i` after verifying the
   signature manually.

2. **Stage 2 (optional):** Publish to a PPA on Launchpad or package as Flatpak
   on Flathub for distribution-channel trust.

3. **Stage 3 (future):** Snap store publication for Ubuntu integration.

**Build script:** `scripts/packaging/linux/build_linux.py`
- Accepts `TAXFLOW_GPG_KEY_ID` env var for signing
- If absent, produces an unsigned `.deb` (no failure)

### macOS

1. **Baseline (free):** Distribute the `.dmg` with instructions for users to
   right-click → Open to bypass Gatekeeper. No Apple Developer account needed.

2. **Stage 2 (optional):** Apple Developer ID ($99/year). Sign the `.app` with
   `codesign` and notarize with `xcrun notarytool`. This removes Gatekeeper
   warnings entirely.

3. **Stage 3 (future):** Mac App Store distribution (requires sandboxing and
   App Store review).

**Build script:** `scripts/packaging/macos/build_macos.py`
- Accepts `APPLE_DEVELOPER_ID` and `APPLE_APP_SPECIFIC_PASSWORD` env vars
- If absent, produces an unsigned `.app` (no failure)

## Current Limitations

- **Single-user mode:** Multi-user collaboration is not yet supported in
  offline mode. The app defaults to `TAXFLOW_SINGLE_USER=true`.
- **No cloud sync:** Data stays local. Backup/export is manual.
- **No auto-update:** Updates require manual download and reinstall.
- **macOS notarization:** Requires Apple Developer account. Scripts are ready
  but signing is deferred until a Developer ID is obtained.