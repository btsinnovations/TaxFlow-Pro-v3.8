"""PyInstaller adapter for scripts/taxflow_launcher.py.

PyInstaller needs a single entry script inside the repo when running from the
project root. This shim imports and calls the launcher created by Bundles B+C.
It also resolves paths correctly whether running from source or from a
PyInstaller bundle (where sys.path and __file__ differ).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# PyInstaller sets sys.frozen and sys._MEIPASS. When frozen, the executable
# lives inside the onedir bundle; project code is next to the executable.
if getattr(sys, "frozen", False):
    # _MEIPASS points to the extracted bundle root (e.g. dist/pyinstaller/.../_internal)
    _bundle_root = Path(sys._MEIPASS)
    # In onedir mode, the executable is at bundle_root/taxflow.exe or
    # bundle_root/_internal/taxflow.exe depending on PyInstaller version.
    _project_root = _bundle_root
else:
    _project_root = Path(__file__).resolve().parents[2]

# Ensure the project root is importable.
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

os.environ.setdefault("TAXFLOW_ENVIRONMENT", "production")
os.environ.setdefault("TAXFLOW_RUNTIME_MODE", "offline")


def main() -> int:
    launcher_path = _project_root / "scripts" / "taxflow_launcher.py"
    if not launcher_path.exists():
        print(f"TaxFlow launcher not found: {launcher_path}", file=sys.stderr)
        return 1

    # Load the launcher module by path to avoid shadowing.
    import importlib.util

    spec = importlib.util.spec_from_file_location("taxflow_launcher", launcher_path)
    if spec is None or spec.loader is None:
        print("Could not create module spec for launcher", file=sys.stderr)
        return 1

    launcher = importlib.util.module_from_spec(spec)
    sys.modules["taxflow_launcher"] = launcher
    spec.loader.exec_module(launcher)

    if not hasattr(launcher, "main"):
        print("Launcher module has no main() function", file=sys.stderr)
        return 1

    return int(launcher.main())


if __name__ == "__main__":
    sys.exit(main())
