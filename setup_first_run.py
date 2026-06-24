#!/usr/bin/env python3
"""
First-run setup for Financial ETL Pipeline.
Copies categories.yaml.example to categories.yaml, sets up directories,
installs optional watchdog service, and initializes PaddleOCR.
"""

import sys
import subprocess
import platform
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.resolve()
CONFIG_PY = PROJECT_ROOT / "phase3_pipeline" / "config.py"
CATEGORIES_EXAMPLE = PROJECT_ROOT / "categories.yaml.example"
CATEGORIES_YAML = PROJECT_ROOT / "categories.yaml"
LOGS_DIR = PROJECT_ROOT / "logs"
OUTPUT_DIR = PROJECT_ROOT / "output"

def print_header(text):
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60)

def ask_yes_no(prompt, default=True):
    yn = "Y/n" if default else "y/N"
    ans = input(f"{prompt} [{yn}]: ").strip().lower()
    return default if not ans else ans in ("y", "yes")

def ask_path(prompt, default):
    print(f"{prompt} (default: {default})")
    val = input("> ").strip()
    return Path(val) if val else Path(default)

def detect_downloads():
    home = Path.home()
    return home / "Downloads" if platform.system() != "Windows" else home / "Downloads"

def check_python():
    if sys.version_info < (3,9):
        print("Error: Python 3.9+ required.")
        return False
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro} – OK")
    return True

def create_directories():
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Created directories: {LOGS_DIR}, {OUTPUT_DIR}")

def copy_categories():
    if not CATEGORIES_EXAMPLE.exists():
        print(f"Error: {CATEGORIES_EXAMPLE} not found. Cannot create categories.yaml")
        return False
    if CATEGORIES_YAML.exists():
        overwrite = ask_yes_no(f"{CATEGORIES_YAML} already exists. Overwrite with defaults?", default=False)
        if not overwrite:
            print("Keeping existing categories.yaml")
            return True
    shutil.copy2(CATEGORIES_EXAMPLE, CATEGORIES_YAML)
    print(f"Copied {CATEGORIES_EXAMPLE} -> {CATEGORIES_YAML}")
    return True

def update_config(input_dir, output_dir, output_format):
    import re
    if not CONFIG_PY.exists():
        print(f"Error: {CONFIG_PY} not found. Cannot update.")
        return False
    with open(CONFIG_PY, "r") as f:
        content = f.read()
    content = re.sub(r'WATCHDOG_INPUT_DIR\s*=\s*"[^"]*"', f'WATCHDOG_INPUT_DIR = "{input_dir}"', content)
    content = re.sub(r'WATCHDOG_OUTPUT_DIR\s*=\s*"[^"]*"', f'WATCHDOG_OUTPUT_DIR = "{output_dir}"', content)
    content = re.sub(r'WATCHDOG_OUTPUT_FORMAT\s*=\s*"[^"]*"', f'WATCHDOG_OUTPUT_FORMAT = "{output_format}"', content)
    with open(CONFIG_PY, "w") as f:
        f.write(content)
    print(f"Updated {CONFIG_PY}.")
    return True

def setup_paddleocr():
    print_header("Setting up PaddleOCR")
    try:
        from paddleocr import PaddleOCR
        print("Initializing PaddleOCR (downloading models if needed)...")
        PaddleOCR(lang='en')
        print("✓ PaddleOCR ready")
        return True
    except Exception as e:
        print(f"✗ PaddleOCR initialization failed: {e}")
        return False

def install_watchdog_linux(input_dir, output_dir, output_format):
    service_name = "financial-watchdog"
    service_path = Path.home() / ".config/systemd/user" / f"{service_name}.service"
    service_path.parent.mkdir(parents=True, exist_ok=True)
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = shutil.which("python")
    content = f"""[Unit]
Description=Financial ETL Watchdog
After=network.target

[Service]
Type=simple
WorkingDirectory={PROJECT_ROOT}
Environment="PATH={Path(venv_python).parent}:/usr/bin:/bin"
ExecStart={venv_python} -m phase3_pipeline.watchdog --input-dir "{input_dir}" --output-dir "{output_dir}" --format {output_format}
Restart=on-failure
RestartSec=10

[Install]
WantedBy=default.target
"""
    service_path.write_text(content)
    subprocess.run(["systemctl", "--user", "daemon-reload"])
    subprocess.run(["systemctl", "--user", "enable", service_name])
    subprocess.run(["systemctl", "--user", "start", service_name])
    print("Linux systemd service installed.")

def install_watchdog_macos(input_dir, output_dir, output_format):
    plist_name = "com.financial.watchdog"
    plist_path = Path.home() / "Library/LaunchAgents" / f"{plist_name}.plist"
    plist_path.parent.mkdir(parents=True, exist_ok=True)
    venv_python = PROJECT_ROOT / "venv" / "bin" / "python"
    if not venv_python.exists():
        venv_python = shutil.which("python3")
    content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{plist_name}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{venv_python}</string>
        <string>-m</string>
        <string>phase3_pipeline.watchdog</string>
        <string>--input-dir</string>
        <string>{input_dir}</string>
        <string>--output-dir</string>
        <string>{output_dir}</string>
        <string>--format</string>
        <string>{output_format}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{PROJECT_ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOGS_DIR}/watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>{LOGS_DIR}/watchdog_error.log</string>
</dict>
</plist>"""
    plist_path.write_text(content)
    subprocess.run(["launchctl", "load", str(plist_path)])
    subprocess.run(["launchctl", "start", plist_name])
    print("macOS LaunchAgent installed.")

def install_watchdog_windows(input_dir, output_dir, output_format):
    task_name = "Financial ETL Watchdog"
    batch = PROJECT_ROOT / "start_watchdog.bat"
    batch.write_text(f"""@echo off
cd /d {PROJECT_ROOT}
call venv\\Scripts\\activate.bat
python -m phase3_pipeline.watchdog --input-dir "{input_dir}" --output-dir "{output_dir}" --format {output_format}
""")
    cmd = ["schtasks", "/create", "/tn", task_name, "/tr", str(batch), "/sc", "onlogon", "/f", "/rl", "HIGHEST"]
    subprocess.run(cmd, capture_output=True)
    print("Windows scheduled task created.")

def main():
    print_header("Financial ETL Pipeline – First‑Run Setup")
    if not check_python():
        sys.exit(1)
    create_directories()
    default_input = detect_downloads()
    default_output = PROJECT_ROOT / "output"
    print("\nWe'll set up your directories and configuration.")
    input_dir = ask_path("Where are your bank statements (PDF/CSV) located?", default_input)
    output_dir = ask_path("Where should processed QIF/CSV files be saved?", default_output)
    output_format = input("Output format? (qif/csv) [qif]: ").strip().lower()
    if output_format not in ("qif","csv"):
        output_format = "qif"
    if not copy_categories():
        sys.exit(1)
    if not update_config(str(input_dir), str(output_dir), output_format):
        sys.exit(1)
    setup_paddleocr()
    if ask_yes_no("Install watchdog background service? (auto‑process new files)", default=False):
        system = platform.system()
        if system == "Linux":
            install_watchdog_linux(input_dir, output_dir, output_format)
        elif system == "Darwin":
            install_watchdog_macos(input_dir, output_dir, output_format)
        elif system == "Windows":
            install_watchdog_windows(input_dir, output_dir, output_format)
        else:
            print(f"Unsupported OS: {system}")
    else:
        print("Skipping watchdog installation.")
    print_header("Setup Complete!")
    print("\nNext steps:")
    print("1. Edit categories.yaml if needed.")
    print("2. Drop PDF statements into your input folder.")
    print("3. Import the generated QIF files into HomeBank.")

if __name__ == "__main__":
    main()
