# Vendored Binaries

TaxFlow Pro bundles the binary dependencies it needs so the application can run
without system-wide installs.

| Vendor     | Location                | Purpose                          |
|------------|-------------------------|----------------------------------|
| Tesseract  | `vendored/tesseract/`   | OCR engine used by upload/parser |
| Poppler    | `vendored/poppler/`     | PDF text + image extraction      |

## Poppler

Poppler is distributed as a portable Windows zip from
[oschwartz10612/poppler-windows](https://github.com/oschwartz10612/poppler-windows/releases).
`scripts/vendor_binaries.py` downloads the zip and extracts the directory that
contains `pdftotext.exe` directly into `vendored/poppler/`.

Required binaries (all are present after vendoring):

- `pdftotext.exe`
- `pdfimages.exe`
- `pdfinfo.exe`
- `pdftoppm.exe`

Plus the matching Poppler DLLs (`poppler.dll`, `poppler-cpp.dll`, `freetype.dll`,
etc.).

## Tesseract

Tesseract is more complicated: the official upstream Windows release is an NSIS
installer, **not** a portable zip. There is no official `tesseract-*.zip` for
recent 64-bit Windows releases.

### Vendored files

After vendoring, `vendored/tesseract/` must contain:

- `tesseract.exe`
- `tessdata/` directory with at least `eng.traineddata`
- all required DLLs (the installer ships ~40 `lib*.dll` files)

### How `scripts/vendor_binaries.py` handles it

1. Downloads the NSIS installer from the official tesseract-ocr GitHub release:
   `https://github.com/tesseract-ocr/tesseract/releases/download/5.5.0/tesseract-ocr-w64-setup-5.5.0.20241111.exe`
2. Runs the installer silently into a temporary directory:
   `tesseract-setup.exe /S /D=C:\path\to\temp\tesseract-install`
3. Copies the portable subset (`tesseract.exe`, `*.dll`, `tessdata/`) into
   `vendored/tesseract/`.

### Important NSIS / UAC note

The Tesseract installer sometimes requires Administrator elevation. If a normal
subprocess call fails with `WinError 740` ("The requested operation requires
elevation"), `vendor_binaries.py` falls back to `ShellExecuteW` with the
`runas` verb. This will surface a UAC prompt when run interactively. In a
non-interactive/CI environment, the installer must be run under an account that
already has the right to install software, or UAC must be disabled.

### Manual fallback

If automated vendoring fails, install Tesseract manually and copy the files:

1. Download `tesseract-ocr-w64-setup-5.5.0.20241111.exe` from
   <https://github.com/tesseract-ocr/tesseract/releases/tag/5.5.0>.
2. Run the installer with the default options (it will install to
   `C:\Program Files\Tesseract-OCR`).
3. Copy from the install directory:
   - `tesseract.exe` -> `vendored/tesseract/tesseract.exe`
   - `tessdata/` -> `vendored/tesseract/tessdata/`
   - every `*.dll` in the install root -> `vendored/tesseract/`

### Chocolatey (not used automatically)

You can also install via Chocolatey, but the launcher prefers the vendored copy:

```powershell
choco install tesseract
```

After installing, copy the same files from the Chocolatey install directory into
`vendored/tesseract/`, or set `TESSERACT_CMD` and `TESSDATA_PREFIX` environment
variables manually.

## Verifying the launcher sees the binaries

Run the launcher with a clean local root and disabled browser open:

```powershell
$env:TAXFLOW_LOCAL_ROOT='C:\tmp\taxflow-test'
$env:TAXFLOW_NO_BROWSER='true'
$env:TAXFLOW_PORT='8002'
python scripts/taxflow_launcher.py
```

Then check health:

```powershell
Invoke-WebRequest -Uri 'http://127.0.0.1:8002/api/health' -UseBasicParsing
```

A `200` response means the backend started successfully and the vendored
binaries were detected.
