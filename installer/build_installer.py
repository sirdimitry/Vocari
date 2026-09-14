"""Builds VocariSetup-X.Y.Z.exe from an already-built dist/Vocari/ folder
(see README "Сборка .exe" for that step) plus installer/vocari.iss.

Usage:
    .venv\\Scripts\\python.exe installer\\build_installer.py [--publish]

Requires Inno Setup 6 (ISCC.exe) — https://jrsoftware.org/isinfo.php, or
`winget install JRSoftware.InnoSetup` — and installer/vc_redist.x64.exe
(download once from https://aka.ms/vs/17/release/vc_redist.x64.exe and drop
it next to this script; gitignored, not checked in, since it's a ~25 MB
third-party binary).

--publish uploads the freshly-built installer to this repo's "latest"
GitHub release (https://github.com/sirdimitry/Vocari/releases/tag/latest) —
a stable link that always points at the newest build, so anyone testing the
app (or just downloading it) never needs a fresh link each version. Not run
by default: publishing is a visible, public action and shouldn't happen as
a side effect of a plain local build. Requires the `gh` CLI, already
authenticated (this is how the "latest" release itself was first created).
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


def publish_latest_release(installer_path: Path, version: str) -> None:
    import shutil

    if shutil.which("gh") is None:
        raise SystemExit("--publish needs the GitHub CLI (`gh`), not found on PATH: https://cli.github.com/")

    # The "latest" release should only ever have *this* version's installer
    # attached — drop any differently-named asset left over from a previous
    # version before uploading the new one (--clobber below only replaces an
    # asset with the exact same name, which changes every version).
    existing = subprocess.run(
        ["gh", "release", "view", "latest", "--json", "assets", "--jq", ".assets[].name"],
        capture_output=True, text=True, cwd=PROJECT_ROOT,
    )
    if existing.returncode == 0:
        for name in existing.stdout.split():
            if name and name != installer_path.name:
                subprocess.run(["gh", "release", "delete-asset", "latest", name, "--yes"], cwd=PROJECT_ROOT, check=True)

    subprocess.run(
        ["gh", "release", "upload", "latest", str(installer_path), "--clobber"],
        cwd=PROJECT_ROOT, check=True,
    )
    notes = (
        f"Последняя собранная версия Vocari (сейчас: v{version}). Этот релиз всегда "
        "указывает на самую свежую сборку — тег и ссылка не меняются, файл обновляется "
        "при выходе новой версии.\n\n"
        "Установка: скачайте VocariSetup-*.exe и запустите — ставится без прав "
        "администратора в %LOCALAPPDATA%\\Programs\\Vocari (как Discord/VS Code). "
        "Подробности — в README."
    )
    subprocess.run(["gh", "release", "edit", "latest", "--notes", notes], cwd=PROJECT_ROOT, check=True)
    print("Published: https://github.com/sirdimitry/Vocari/releases/tag/latest")


def main() -> None:
    publish = "--publish" in sys.argv

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

    if publish:
        installer_path = INSTALLER_DIR / "output" / f"VocariSetup-{version}.exe"
        publish_latest_release(installer_path, version)


if __name__ == "__main__":
    main()
