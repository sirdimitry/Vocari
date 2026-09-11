"""Builds VocariSetup-X.Y.Z.exe from an already-built dist/Vocari/ folder
(see README "Сборка .exe" for that step) plus installer/vocari.iss.

Usage:
    .venv\\Scripts\\python.exe installer\\build_installer.py

Requires Inno Setup 6 (ISCC.exe) — https://jrsoftware.org/isinfo.php, or
`winget install JRSoftware.InnoSetup` — and installer/vc_redist.x64.exe
(download once from https://aka.ms/vs/17/release/vc_redist.x64.exe and drop
it next to this script; gitignored, not checked in, since it's a ~25 MB
third-party binary).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
INSTALLER_DIR = Path(__file__).resolve().parent

ISCC_CANDIDATES = [
    Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe"),
    Path(r"C:\Program Files\Inno Setup 6\ISCC.exe"),
    Path.home() / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe",
]


def find_iscc() -> Path:
    for candidate in ISCC_CANDIDATES:
        if candidate.exists():
            return candidate
    raise SystemExit(
        "ISCC.exe (Inno Setup compiler) not found. Install Inno Setup 6 "
        "(https://jrsoftware.org/isinfo.php or `winget install JRSoftware.InnoSetup`)."
    )


def read_version() -> str:
    text = (PROJECT_ROOT / "vocari" / "__version__.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("__version__"):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise SystemExit("Could not read __version__ from vocari/__version__.py")


def main() -> None:
    dist_dir = PROJECT_ROOT / "dist" / "Vocari"
    if not (dist_dir / "Vocari.exe").exists():
        raise SystemExit(
            f"{dist_dir}\\Vocari.exe not found — build the .exe first "
            "(see README \"Сборка .exe\": pyinstaller vocari.spec)."
        )
    if not (INSTALLER_DIR / "vc_redist.x64.exe").exists():
        print(
            "Warning: installer/vc_redist.x64.exe is missing — the installer "
            "will still build, but won't be able to install the VC++ "
            "Redistributable for a client who doesn't already have it. "
            "Download: https://aka.ms/vs/17/release/vc_redist.x64.exe",
            file=sys.stderr,
        )

    version = read_version()
    iscc = find_iscc()
    print(f"Version: {version}")
    subprocess.run(
        [str(iscc), f"/DMyAppVersion={version}", str(INSTALLER_DIR / "vocari.iss")],
        check=True,
        cwd=INSTALLER_DIR,
    )


if __name__ == "__main__":
    main()
